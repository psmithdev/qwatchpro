"""Terminal breathing bar cue (4s in, 2s hold, 6s out)."""

import time
from dataclasses import dataclass
from ..config import Config


@dataclass
class BreathingState:
    active: bool = False
    phase: str = ""  # "IN", "HOLD", "OUT", ""
    progress: float = 0.0  # 0.0 to 1.0 within current phase
    remaining_sec: float = 0.0
    cycle_start: float = 0.0


class BreathingCue:
    def __init__(self, config: Config):
        self.cfg = config
        self._cycle_start: float = 0.0
        self._active = False
        self._total_cycle = config.breathe_in_sec + config.breathe_hold_sec + config.breathe_out_sec

    def start(self):
        self._active = True
        self._cycle_start = time.time()

    def stop(self):
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def get_state(self) -> BreathingState:
        if not self._active:
            return BreathingState()

        now = time.time()
        elapsed = (now - self._cycle_start) % self._total_cycle

        if elapsed < self.cfg.breathe_in_sec:
            phase = "IN"
            progress = elapsed / self.cfg.breathe_in_sec
            remaining = self.cfg.breathe_in_sec - elapsed
        elif elapsed < self.cfg.breathe_in_sec + self.cfg.breathe_hold_sec:
            phase = "HOLD"
            hold_elapsed = elapsed - self.cfg.breathe_in_sec
            progress = hold_elapsed / self.cfg.breathe_hold_sec
            remaining = self.cfg.breathe_hold_sec - hold_elapsed
        else:
            phase = "OUT"
            out_elapsed = elapsed - self.cfg.breathe_in_sec - self.cfg.breathe_hold_sec
            progress = out_elapsed / self.cfg.breathe_out_sec
            remaining = self.cfg.breathe_out_sec - out_elapsed

        return BreathingState(
            active=True,
            phase=phase,
            progress=progress,
            remaining_sec=remaining,
            cycle_start=self._cycle_start,
        )
