"""Derive synthetic RR intervals from HR-only streams."""

import random
from ..config import Config


class RREstimator:
    def __init__(self, config: Config):
        self.cfg = config

    def estimate(self, hr_bpm: int) -> float:
        """Convert HR to estimated RR with jitter. Returns RR in ms."""
        if hr_bpm <= 0:
            return 1000.0
        base_rr = 60000.0 / hr_bpm
        jitter = random.gauss(0, self.cfg.rr_jitter_std_ms)
        return max(self.cfg.rr_min_ms, min(self.cfg.rr_max_ms, base_rr + jitter))
