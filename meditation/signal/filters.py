"""Artifact rejection and physiological range clamping for RR intervals."""

from collections import deque
from ..config import Config


class RRFilter:
    def __init__(self, config: Config):
        self.cfg = config
        self._prev_rr: float | None = None
        self._accepted = 0
        self._rejected = 0

    def accept(self, rr_ms: float) -> bool:
        """Return True if RR interval passes artifact rejection."""
        # Physiological range check
        if rr_ms < self.cfg.rr_min_ms or rr_ms > self.cfg.rr_max_ms:
            self._rejected += 1
            return False

        # Successive difference check
        if self._prev_rr is not None:
            diff = abs(rr_ms - self._prev_rr)
            if diff > self.cfg.rr_max_successive_diff_ms:
                self._rejected += 1
                return False

        self._prev_rr = rr_ms
        self._accepted += 1
        return True

    @property
    def quality(self) -> float:
        """Signal quality as fraction of accepted samples."""
        total = self._accepted + self._rejected
        if total == 0:
            return 1.0
        return self._accepted / total

    def reset(self):
        self._prev_rr = None
        self._accepted = 0
        self._rejected = 0
