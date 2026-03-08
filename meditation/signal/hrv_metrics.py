"""HRV metrics computed over a sliding window of RR intervals."""

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

from ..config import Config


@dataclass
class HRVResult:
    rmssd: float = 0.0
    sdnn: float = 0.0
    pnn50: float = 0.0
    mean_hr: float = 0.0
    sample_count: int = 0


class HRVComputer:
    def __init__(self, config: Config):
        self.cfg = config
        self._rr_buffer: deque[tuple[float, float]] = deque()  # (timestamp, rr_ms)
        self._last_compute: float = 0.0
        self._last_result: Optional[HRVResult] = None

    def add_rr(self, timestamp: float, rr_ms: float) -> Optional[HRVResult]:
        """Add an RR interval. Returns HRVResult if recomputation triggered."""
        self._rr_buffer.append((timestamp, rr_ms))

        # Trim to window
        cutoff = timestamp - self.cfg.hrv_window_sec
        while self._rr_buffer and self._rr_buffer[0][0] < cutoff:
            self._rr_buffer.popleft()

        # Recompute every hrv_recompute_sec
        if timestamp - self._last_compute >= self.cfg.hrv_recompute_sec:
            self._last_compute = timestamp
            self._last_result = self._compute()
            return self._last_result
        return None

    @property
    def latest(self) -> Optional[HRVResult]:
        return self._last_result

    def _compute(self) -> HRVResult:
        rr_values = [rr for _, rr in self._rr_buffer]
        n = len(rr_values)
        if n < 2:
            return HRVResult(sample_count=n)

        # Mean HR from mean RR
        mean_rr = sum(rr_values) / n
        mean_hr = 60000.0 / mean_rr if mean_rr > 0 else 0.0

        # SDNN
        variance = sum((rr - mean_rr) ** 2 for rr in rr_values) / n
        sdnn = math.sqrt(variance)

        # Successive differences
        diffs = [abs(rr_values[i + 1] - rr_values[i]) for i in range(n - 1)]

        # RMSSD
        rmssd = math.sqrt(sum(d ** 2 for d in diffs) / len(diffs)) if diffs else 0.0

        # pNN50
        nn50 = sum(1 for d in diffs if d > 50)
        pnn50 = nn50 / len(diffs) if diffs else 0.0

        return HRVResult(
            rmssd=rmssd,
            sdnn=sdnn,
            pnn50=pnn50,
            mean_hr=mean_hr,
            sample_count=n,
        )
