"""Feedback dispatch with cooldown and 3-level escalation."""

import asyncio
import time

from ..config import Config
from ..session.state_machine import State
from .tone import play_tone
from .breathing import BreathingCue


class FeedbackEngine:
    def __init__(self, config: Config):
        self.cfg = config
        self.breathing = BreathingCue(config)
        self.level: int = 0  # 0=none, 1=tone, 2=breathing, 3=both+louder
        self._last_cue_time: float = 0.0
        self._agitated_since: float | None = None

    async def update(self, state: State, now: float) -> int:
        """Called each tick. Returns current feedback level (0-3)."""
        if state == State.AGITATED:
            if self._agitated_since is None:
                self._agitated_since = now

            # Wait initial delay before first cue
            if now - self._agitated_since < self.cfg.feedback_initial_delay_sec:
                return self.level

            # Check cooldown
            if now - self._last_cue_time < self.cfg.feedback_cooldown_sec and self.level > 0:
                return self.level

            # Escalate
            self.level = min(self.level + 1, 3)
            self._last_cue_time = now
            await self._deliver(self.level)

        elif state in (State.RECOVERING, State.MEDITATING):
            if self.level > 0:
                self.level = max(self.level - 1, 0)
                if self.level == 0:
                    self.breathing.stop()
            self._agitated_since = None

        elif state in (State.CALIBRATING, State.COMPLETED):
            self.level = 0
            self.breathing.stop()
            self._agitated_since = None

        return self.level

    async def _deliver(self, level: int):
        if level == 1:
            await play_tone(self.cfg, loud=False)
        elif level == 2:
            self.breathing.start()
        elif level == 3:
            await play_tone(self.cfg, loud=True)
            self.breathing.start()
