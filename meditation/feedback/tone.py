"""Sine wave tone generation via struct+wave+subprocess (no external deps)."""

import io
import math
import struct
import subprocess
import wave
import shutil
from ..config import Config


def _generate_wav(freq_hz: float, duration_sec: float, volume: float, sample_rate: int) -> bytes:
    """Generate a WAV file in memory."""
    n_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Fade in/out over 0.05s to avoid clicks
        fade_samples = int(sample_rate * 0.05)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * freq_hz * t) * volume
            # Apply fade
            if i < fade_samples:
                sample *= i / fade_samples
            elif i > n_samples - fade_samples:
                sample *= (n_samples - i) / fade_samples
            frames += struct.pack("<h", int(sample * 32767))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


async def play_tone(config: Config, loud: bool = False):
    """Play a gentle tone. Non-blocking via subprocess."""
    if not config.audio_enabled:
        return
    volume = config.tone_volume_loud if loud else config.tone_volume
    wav_data = _generate_wav(
        config.tone_freq_hz, config.tone_duration_sec, volume, config.audio_sample_rate
    )

    # Try aplay (ALSA), then paplay (PulseAudio), then skip
    for player in ["aplay", "paplay"]:
        if shutil.which(player):
            try:
                proc = subprocess.Popen(
                    [player, "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.stdin.write(wav_data)
                proc.stdin.close()
                return
            except OSError:
                continue
