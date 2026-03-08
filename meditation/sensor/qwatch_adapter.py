"""QWatch BLE sensor adapter — wraps existing qwatch_hr.py BLE logic."""

import asyncio
import time
from typing import AsyncIterator

from ..config import Config
from .base import SensorAdapter, SensorSample

try:
    from bleak import BleakClient
except ImportError:
    BleakClient = None

# BLE UUIDs (from qwatch_hr.py)
SERVICE_UUID = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

CMD_START_HEART_RATE = 105
CMD_STOP_HEART_RATE = 106
CMD_REAL_TIME_HEART_RATE = 30
TYPE_REALTIMEHEARTRATE = 6
FLAG_MASK_ERROR = 0x80


def _build_packet(cmd_key: int, sub_data: bytes = b"") -> bytes:
    packet = bytearray(16)
    packet[0] = cmd_key & 0xFF
    for i, b in enumerate(sub_data):
        if i + 1 < 15:
            packet[i + 1] = b & 0xFF
    packet[15] = sum(packet[:15]) & 0xFF
    return bytes(packet)


class QWatchAdapter(SensorAdapter):
    def __init__(self, config: Config, mac_address: str):
        self.cfg = config
        self.mac = mac_address
        self._client: BleakClient | None = None
        self._queue: asyncio.Queue[SensorSample] = asyncio.Queue()
        self._connected = False

    def _handle_notification(self, sender, data: bytearray):
        if len(data) != 16:
            return
        cmd_raw = data[0]
        cmd_key = cmd_raw & ~FLAG_MASK_ERROR
        payload = data[1:15]

        hr = 0
        if cmd_key == CMD_START_HEART_RATE:
            hr = payload[2] & 0xFF
        elif cmd_key == CMD_REAL_TIME_HEART_RATE:
            hr = payload[0]

        if hr > 0:
            sample = SensorSample(
                timestamp=time.time(),
                hr_bpm=hr,
                rr_ms=None,  # QWatch doesn't provide RR
                source="qwatch",
            )
            try:
                self._queue.put_nowait(sample)
            except asyncio.QueueFull:
                pass

    async def connect(self) -> None:
        if BleakClient is None:
            raise RuntimeError("bleak not installed: pip install bleak")
        self._client = BleakClient(self.mac, timeout=20.0)
        await self._client.connect()
        self._connected = True
        await self._client.start_notify(NOTIFY_UUID, self._handle_notification)
        # Start real-time HR
        pkt = _build_packet(CMD_START_HEART_RATE, bytes([TYPE_REALTIMEHEARTRATE, 0x01]))
        await self._client.write_gatt_char(WRITE_UUID, pkt, response=False)

    async def stream(self) -> AsyncIterator[SensorSample]:
        while self._connected:
            try:
                sample = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                yield sample
            except asyncio.TimeoutError:
                continue

    async def disconnect(self) -> None:
        self._connected = False
        if self._client and self._client.is_connected:
            try:
                pkt = _build_packet(CMD_STOP_HEART_RATE, bytes([TYPE_REALTIMEHEARTRATE, 0x00, 0x00]))
                await self._client.write_gatt_char(WRITE_UUID, pkt, response=False)
                await asyncio.sleep(0.5)
                await self._client.stop_notify(NOTIFY_UUID)
            except Exception:
                pass
            await self._client.disconnect()
