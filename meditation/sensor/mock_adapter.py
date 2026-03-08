"""Mock sensor adapter with scripted 45-min meditation scenario."""

import asyncio
import math
import random
import time
from typing import AsyncIterator

from ..config import Config
from .base import SensorAdapter, SensorSample

# Scenario phases: (start_min, end_min, hr_mean, rr_variability_ms, label)
SCENARIO = [
    (0, 5, 65, 50, "Calibration"),
    (5, 15, 63, 55, "Deepening"),
    (15, 25, 60, 60, "Deep meditation"),
    (25, 35, 61, 58, "Steady"),
    (35, 37, 68, 35, "Agitation onset"),
    (37, 40, 78, 20, "Agitation peak"),
    (40, 42, 70, 35, "Early recovery"),
    (42, 45, 63, 52, "Full recovery"),
]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


class MockAdapter(SensorAdapter):
    def __init__(self, config: Config, speed: float = 1.0):
        self.config = config
        self.speed = speed  # >1 = faster than real-time
        self._duration_min = config.default_duration_min

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def _get_phase(self, elapsed_min: float):
        """Get HR mean and RR variability for current time, interpolating between phases."""
        # Clamp to scenario range
        max_min = SCENARIO[-1][1]
        elapsed_min = min(elapsed_min, max_min - 0.001)

        for i, (start, end, hr, rr_var, label) in enumerate(SCENARIO):
            if start <= elapsed_min < end:
                # Interpolate toward next phase in the last 30s of this phase
                progress_in_phase = (elapsed_min - start) / (end - start)
                if i + 1 < len(SCENARIO) and progress_in_phase > 0.8:
                    next_hr = SCENARIO[i + 1][2]
                    next_rr = SCENARIO[i + 1][3]
                    blend = (progress_in_phase - 0.8) / 0.2
                    hr = _lerp(hr, next_hr, blend)
                    rr_var = _lerp(rr_var, next_rr, blend)
                return hr, rr_var, label
        # Past end of scenario
        return SCENARIO[-1][2], SCENARIO[-1][3], SCENARIO[-1][4]

    async def stream(self) -> AsyncIterator[SensorSample]:
        start = time.time()
        duration_sec = self._duration_min * 60
        sample_interval = 1.0 / self.speed
        t = 0.0

        while t < duration_sec:
            elapsed_min = t / 60.0
            hr_mean, rr_var, _label = self._get_phase(elapsed_min)

            # Respiratory sinus arrhythmia: 0.25 Hz sinusoid
            rsa = rr_var * 0.5 * math.sin(2 * math.pi * 0.25 * t)
            noise = random.gauss(0, rr_var * 0.3)
            base_rr = 60000.0 / hr_mean
            rr_ms = base_rr + rsa + noise
            rr_ms = max(300, min(2000, rr_ms))
            hr_bpm = int(round(60000.0 / rr_ms))

            yield SensorSample(
                timestamp=start + t,
                hr_bpm=hr_bpm,
                rr_ms=rr_ms,
                source="mock",
            )

            await asyncio.sleep(sample_interval)
            t += 1.0  # Always advance by 1 simulated second
