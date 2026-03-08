#!/usr/bin/env python3
"""
QWatch Pro Heart Rate Monitor - BLE Client for Linux
Reverse-engineered from QWatch_Pro_1.0.2.83.apk (com.qcwireless.qcwatch)

Protocol details (from com.oudmon.ble.base.communication):
- BLE Service UUID:  6e40fff0-b5a3-f393-e0a9-e50e24dcca9e
- Write Char UUID:   6e400002-b5a3-f393-e0a9-e50e24dcca9e
- Notify Char UUID:  6e400003-b5a3-f393-e0a9-e50e24dcca9e

Packet format (from BaseReqCmd):
- 16 bytes total (Constants.CMD_DATA_LENGTH = 16)
- Byte 0: command key
- Bytes 1-14: sub-data (command-specific payload)
- Byte 15: CRC (sum of bytes 0-14, masked to 0xFF)

Heart rate commands:
- CMD 105 (0x69): Start heart rate measurement
  - subdata[0] = type (1=HR, 2=BP, 3=SpO2, 6=realtime HR, etc.)
  - subdata[1] = sub param
- CMD 106 (0x6A): Stop heart rate measurement
- CMD  30 (0x1E): Real-time heart rate (response: byte[0] = HR value)
- CMD  21 (0x15): Read stored heart rate data

Response parsing (from QCDataParser):
- Response byte[0] & 0x7F = command key (high bit is error flag)
- Bytes 1-14: response data
- Byte 15: CRC
"""

import asyncio
import struct
import sys
import signal
from datetime import datetime

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)

# BLE UUIDs from Constants.java
SERVICE_UUID = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# Command keys from Constants.java
CMD_START_HEART_RATE = 105     # 0x69
CMD_STOP_HEART_RATE = 106      # 0x6A
CMD_REAL_TIME_HEART_RATE = 30  # 0x1E
CMD_GET_HEART_RATE = 21        # 0x15
CMD_GET_BATTERY = 3            # 0x03

# Start heart rate types from StartHeartRateReq.java
TYPE_HEARTRATE = 1
TYPE_BLOODPRESSURE = 2
TYPE_BLOODOXYGEN = 3
TYPE_FATIGUE = 4
TYPE_HEALTHCHECK = 5
TYPE_REALTIMEHEARTRATE = 6
TYPE_ECG = 7
TYPE_PRESSURE = 8
TYPE_BLOOD_SUGAR = 9
TYPE_HRV = 10
TYPE_BODY_TEMPERATURE = 11

FLAG_MASK_ERROR = 0x80

running = True


def build_packet(cmd_key: int, sub_data: bytes = b"") -> bytes:
    """Build a 16-byte command packet per BaseReqCmd.getData()"""
    packet = bytearray(16)
    packet[0] = cmd_key & 0xFF
    for i, b in enumerate(sub_data):
        if i + 1 < 15:
            packet[i + 1] = b & 0xFF
    # CRC: sum of bytes 0-14, masked to 0xFF
    crc = sum(packet[:15]) & 0xFF
    packet[15] = crc
    return bytes(packet)


def parse_response(data: bytes) -> tuple:
    """Parse a 16-byte response. Returns (cmd_key, is_error, payload)"""
    if len(data) != 16:
        return (None, True, data)
    cmd_raw = data[0]
    cmd_key = cmd_raw & ~FLAG_MASK_ERROR
    is_error = bool(cmd_raw & FLAG_MASK_ERROR)
    payload = data[1:15]
    # Verify CRC
    expected_crc = sum(data[:15]) & 0xFF
    if data[15] != expected_crc:
        print(f"  [CRC mismatch: expected {expected_crc:#04x}, got {data[15]:#04x}]")
    return (cmd_key, is_error, payload)


def notification_handler(sender, data: bytearray):
    """Handle BLE notifications from the watch"""
    ts = datetime.now().strftime("%H:%M:%S")
    hex_str = data.hex()

    cmd_key, is_error, payload = parse_response(bytes(data))
    err_flag = " [ERR]" if is_error else ""

    if cmd_key == CMD_START_HEART_RATE:
        # StartHeartRateRsp: type, errCode, value, sbp, dbp
        mtype = payload[0]
        err_code = payload[1]
        value = payload[2] & 0xFF
        type_names = {1: "HR", 2: "BP", 3: "SpO2", 4: "Fatigue", 5: "HealthCheck",
                      6: "RealtimeHR", 7: "ECG", 8: "Pressure", 9: "BloodSugar",
                      10: "HRV", 11: "Temperature"}
        tname = type_names.get(mtype, f"type={mtype}")
        if mtype == 2 and len(payload) >= 5:
            sbp = payload[3] & 0xFF
            dbp = payload[4] & 0xFF
            print(f"[{ts}] {tname}: {value} bpm | BP: {sbp}/{dbp} mmHg (err={err_code}){err_flag}")
        elif value > 0:
            print(f"[{ts}] {tname}: {value} bpm (err={err_code}){err_flag}")
        else:
            print(f"[{ts}] {tname}: measuring... (err={err_code}){err_flag}")

    elif cmd_key == CMD_REAL_TIME_HEART_RATE:
        # RealTimeHeartRateRsp: heart = payload[0]
        hr = payload[0]
        if hr > 0:
            print(f"[{ts}] Realtime HR: {hr} bpm{err_flag}")
        else:
            print(f"[{ts}] Realtime HR: waiting for reading...{err_flag}")

    elif cmd_key == CMD_GET_BATTERY:
        battery = payload[0] & 0xFF
        print(f"[{ts}] Battery: {battery}%{err_flag}")

    elif cmd_key == CMD_STOP_HEART_RATE:
        mtype = payload[0]
        value = payload[1] & 0xFF
        print(f"[{ts}] Stop measurement type={mtype}, last_value={value}{err_flag}")

    else:
        print(f"[{ts}] CMD {cmd_key:#04x}{err_flag}: {hex_str}")


async def scan_for_watch(timeout=10.0):
    """Scan for QWatch devices"""
    print(f"Scanning for QWatch devices ({timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    qwatch_devices = []
    for d, adv in devices.values():
        name = d.name or ""
        rssi = adv.rssi
        svc_uuids = [str(u).lower() for u in (adv.service_uuids or [])]
        is_qwatch_name = any(x in name.lower() for x in ["qwatch", "qc", "watch", "band", "smart", "h59"])
        is_qwatch_svc = SERVICE_UUID.lower() in svc_uuids
        if is_qwatch_name or is_qwatch_svc:
            qwatch_devices.append(d)
            match = "service UUID" if is_qwatch_svc else "name"
            print(f"  Found ({match}): {name or '(unnamed)'} [{d.address}] RSSI={rssi}")

    if not qwatch_devices:
        print("\nNo QWatch-like devices found. All nearby BLE devices:")
        for d, adv in sorted(devices.values(), key=lambda x: x[1].rssi or -999, reverse=True):
            name = d.name or "(unnamed)"
            print(f"  {name:30s} [{d.address}] RSSI={adv.rssi}")
        print("\nTip: Look for your watch name above and pass its MAC address as an argument.")

    return qwatch_devices


async def monitor_heart_rate(address: str):
    """Connect to QWatch and stream heart rate data"""
    global running

    print(f"Connecting to {address}...")

    async with BleakClient(address, timeout=20.0) as client:
        print(f"Connected: {client.is_connected}")

        # List services for debugging
        print("\nServices discovered:")
        for service in client.services:
            print(f"  {service.uuid}: {service.description}")
            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"    {char.uuid} [{props}]")

        # Subscribe to notifications on the notify characteristic
        print(f"\nSubscribing to notifications on {NOTIFY_UUID}...")
        await client.start_notify(NOTIFY_UUID, notification_handler)

        # Request battery level
        print("Requesting battery level...")
        pkt = build_packet(CMD_GET_BATTERY)
        await client.write_gatt_char(WRITE_UUID, pkt, response=False)
        await asyncio.sleep(1)

        # Start real-time heart rate measurement
        # StartHeartRateReq: cmd=105, subdata=[TYPE_REALTIMEHEARTRATE, action_param]
        print("Starting real-time heart rate measurement...")
        pkt = build_packet(CMD_START_HEART_RATE, bytes([TYPE_REALTIMEHEARTRATE, 0x01]))
        await client.write_gatt_char(WRITE_UUID, pkt, response=False)

        print("\n--- Streaming heart rate (Ctrl+C to stop) ---\n")

        try:
            while running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        # Stop heart rate measurement
        print("\nStopping measurement...")
        pkt = build_packet(CMD_STOP_HEART_RATE, bytes([TYPE_REALTIMEHEARTRATE, 0x00, 0x00]))
        await client.write_gatt_char(WRITE_UUID, pkt, response=False)
        await asyncio.sleep(1)

        await client.stop_notify(NOTIFY_UUID)
        print("Disconnected.")


async def main():
    global running

    def signal_handler(sig, frame):
        global running
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) > 1:
        address = sys.argv[1]
        await monitor_heart_rate(address)
    else:
        devices = await scan_for_watch()
        if devices:
            print(f"\nConnecting to first found device: {devices[0].name} [{devices[0].address}]")
            await monitor_heart_rate(devices[0].address)
        else:
            print("\nUsage: python3 qwatch_hr.py <MAC_ADDRESS>")
            print("Example: python3 qwatch_hr.py AA:BB:CC:DD:EE:FF")


if __name__ == "__main__":
    asyncio.run(main())
