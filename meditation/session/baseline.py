"""Baseline statistics computed during calibration phase."""

import math
from dataclasses import dataclass, field


@dataclass
class Baseline:
    mean_hr: float = 0.0
    mean_rmssd: float = 0.0
    mean_sdnn: float = 0.0
    mean_pnn50: float = 0.0
    samples: int = 0

    @property
    def ready(self) -> bool:
        return self.samples >= 3


class BaselineAccumulator:
    def __init__(self):
        self._hr_vals: list[float] = []
        self._rmssd_vals: list[float] = []
        self._sdnn_vals: list[float] = []
        self._pnn50_vals: list[float] = []

    def add(self, mean_hr: float, rmssd: float, sdnn: float, pnn50: float):
        self._hr_vals.append(mean_hr)
        self._rmssd_vals.append(rmssd)
        self._sdnn_vals.append(sdnn)
        self._pnn50_vals.append(pnn50)

    def compute(self) -> Baseline:
        n = len(self._hr_vals)
        if n == 0:
            return Baseline()
        return Baseline(
            mean_hr=sum(self._hr_vals) / n,
            mean_rmssd=sum(self._rmssd_vals) / n,
            mean_sdnn=sum(self._sdnn_vals) / n,
            mean_pnn50=sum(self._pnn50_vals) / n,
            samples=n,
        )
