"""Session state machine: WAITING → CALIBRATING → MEDITATING ⇄ AGITATED ⇄ RECOVERING → COMPLETED."""

import enum
import time

from ..config import Config
from ..signal.hrv_metrics import HRVResult
from .baseline import Baseline, BaselineAccumulator
from .detector import AgitationDetector


class State(enum.Enum):
    WAITING = "WAITING"
    CALIBRATING = "CALIBRATING"
    MEDITATING = "MEDITATING"
    AGITATED = "AGITATED"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"


class SessionStateMachine:
    def __init__(self, config: Config, duration_min: float):
        self.cfg = config
        self.duration_sec = duration_min * 60
        self.state = State.WAITING
        self.start_time: float = 0.0
        self.calibration_start: float = 0.0
        self.baseline = Baseline()
        self._baseline_acc = BaselineAccumulator()
        self._detector = AgitationDetector(config)
        self._agitated_since: float | None = None
        self._recovered_since: float | None = None
        self._signal_quality: float = 1.0
        self._last_now: float = 0.0

    def elapsed_sec(self, now: float | None = None) -> float:
        if self.start_time == 0:
            return 0.0
        return (now or self._last_now) - self.start_time

    def remaining_sec(self, now: float | None = None) -> float:
        return max(0.0, self.duration_sec - self.elapsed_sec(now))

    def begin(self, start_time: float | None = None):
        self.start_time = start_time or time.time()
        self._last_now = self.start_time
        self.calibration_start = self.start_time
        self.state = State.CALIBRATING

    def update(self, hrv: HRVResult | None, signal_quality: float, now: float) -> State:
        """Advance state machine. Call at every HRV recompute (~5s)."""
        self._signal_quality = signal_quality
        self._last_now = now
        elapsed = now - self.start_time

        if self.state == State.CALIBRATING:
            return self._update_calibrating(hrv, signal_quality, now, elapsed)
        elif self.state in (State.MEDITATING, State.AGITATED, State.RECOVERING):
            return self._update_active(hrv, now, elapsed)
        return self.state

    def _update_calibrating(self, hrv, quality, now, elapsed) -> State:
        if hrv and hrv.sample_count >= 2:
            self._baseline_acc.add(hrv.mean_hr, hrv.rmssd, hrv.sdnn, hrv.pnn50)

        cal_elapsed = now - self.calibration_start
        min_sec = self.cfg.calibration_min * 60
        max_sec = self.cfg.calibration_max_min * 60

        if cal_elapsed >= min_sec:
            baseline = self._baseline_acc.compute()
            if baseline.ready and (quality >= self.cfg.calibration_quality_threshold or cal_elapsed >= max_sec):
                self.baseline = baseline
                self.state = State.MEDITATING
        return self.state

    def _update_active(self, hrv, now, elapsed) -> State:
        # Check session end
        if elapsed >= self.duration_sec:
            self.state = State.COMPLETED
            return self.state

        if hrv is None:
            return self.state

        is_agitated = self._detector.is_agitated(self.baseline, hrv)
        is_recovered = self._detector.is_recovered(self.baseline, hrv)

        if self.state == State.MEDITATING:
            if is_agitated:
                if self._agitated_since is None:
                    self._agitated_since = now
                elif now - self._agitated_since >= self.cfg.agitation_sustain_sec:
                    self.state = State.AGITATED
                    self._agitated_since = None
                    self._recovered_since = None
            else:
                self._agitated_since = None

        elif self.state == State.AGITATED:
            if is_recovered:
                if self._recovered_since is None:
                    self._recovered_since = now
                elif now - self._recovered_since >= self.cfg.recovery_sustain_sec:
                    self.state = State.RECOVERING
            else:
                self._recovered_since = None

        elif self.state == State.RECOVERING:
            if is_agitated:
                self.state = State.AGITATED
                self._recovered_since = None
            elif is_recovered:
                self.state = State.MEDITATING
                self._recovered_since = None

        return self.state
