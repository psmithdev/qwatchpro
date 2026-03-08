"""In-memory time-series logger for post-session analysis."""

from dataclasses import dataclass, field
from typing import Optional

from ..signal.hrv_metrics import HRVResult


@dataclass
class RecordEntry:
    timestamp: float
    elapsed_sec: float
    hr_bpm: int
    rr_ms: Optional[float]
    hrv: Optional[HRVResult]
    state: str
    signal_quality: float
    feedback_level: int = 0


@dataclass
class AgitationEvent:
    start_sec: float
    end_sec: Optional[float] = None
    peak_hr: int = 0
    min_rmssd: float = float("inf")
    feedback_cues: list[int] = field(default_factory=list)
    criteria: list[str] = field(default_factory=list)

    @property
    def duration_sec(self) -> Optional[float]:
        if self.end_sec is not None:
            return self.end_sec - self.start_sec
        return None


class SessionRecorder:
    def __init__(self, start_time: float):
        self.start_time = start_time
        self.entries: list[RecordEntry] = []
        self.agitation_events: list[AgitationEvent] = []
        self._current_agitation: Optional[AgitationEvent] = None

    def record(self, entry: RecordEntry):
        self.entries.append(entry)

    def start_agitation(self, elapsed_sec: float, criteria: list[str]):
        self._current_agitation = AgitationEvent(
            start_sec=elapsed_sec, criteria=criteria
        )
        self.agitation_events.append(self._current_agitation)

    def update_agitation(self, hr: int, rmssd: float, feedback_level: int):
        if self._current_agitation:
            self._current_agitation.peak_hr = max(self._current_agitation.peak_hr, hr)
            self._current_agitation.min_rmssd = min(
                self._current_agitation.min_rmssd, rmssd
            )
            if feedback_level > 0 and feedback_level not in self._current_agitation.feedback_cues:
                self._current_agitation.feedback_cues.append(feedback_level)

    def end_agitation(self, elapsed_sec: float):
        if self._current_agitation:
            self._current_agitation.end_sec = elapsed_sec
            self._current_agitation = None
