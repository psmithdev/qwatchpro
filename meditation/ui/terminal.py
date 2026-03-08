"""Curses-based minimal live display with 1Hz refresh."""

import asyncio
import curses
import time
from collections import deque

from ..config import Config
from ..session.state_machine import State
from ..feedback.breathing import BreathingState
from ..signal.hrv_metrics import HRVResult


SPARK_CHARS = "▁▂▃▄▅▆▇█"

STATE_COLORS = {
    State.WAITING: curses.COLOR_WHITE,
    State.CALIBRATING: curses.COLOR_YELLOW,
    State.MEDITATING: curses.COLOR_GREEN,
    State.AGITATED: curses.COLOR_RED,
    State.RECOVERING: curses.COLOR_CYAN,
    State.COMPLETED: curses.COLOR_BLUE,
}


def _mini_spark(values: list[float], width: int) -> str:
    if not values:
        return ""
    vals = values[-width:]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    rng = hi - lo if hi > lo else 1
    return "".join(
        SPARK_CHARS[min(len(SPARK_CHARS) - 1, int((v - lo) / rng * (len(SPARK_CHARS) - 1)))]
        for v in vals
    )


def _format_time(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class TerminalUI:
    def __init__(self, config: Config):
        self.cfg = config
        self._hr_history: deque[float] = deque(maxlen=config.sparkline_width)
        self._rmssd_history: deque[float] = deque(maxlen=config.sparkline_width)
        self._stdscr = None
        self._colors_init = False

    def _init_colors(self):
        if self._colors_init:
            return
        curses.start_color()
        curses.use_default_colors()
        for i, (state, color) in enumerate(STATE_COLORS.items(), 1):
            curses.init_pair(i, color, -1)
        # Pair 7: dim white for labels
        curses.init_pair(7, curses.COLOR_WHITE, -1)
        # Pair 8: breathing bar
        curses.init_pair(8, curses.COLOR_CYAN, -1)
        self._colors_init = True

    def _get_state_color(self, state: State) -> int:
        idx = list(STATE_COLORS.keys()).index(state) + 1 if state in STATE_COLORS else 7
        return curses.color_pair(idx)

    def render(
        self,
        stdscr,
        state: State,
        elapsed_sec: float,
        remaining_sec: float,
        hr_bpm: int,
        hrv: HRVResult | None,
        signal_quality: float,
        feedback_level: int,
        breathing: BreathingState,
        criteria: list[str],
    ):
        self._stdscr = stdscr
        self._init_colors()

        self._hr_history.append(float(hr_bpm))
        if hrv:
            self._rmssd_history.append(hrv.rmssd)

        stdscr.erase()
        h, w = stdscr.getmaxyx()

        row = 0
        dim = curses.color_pair(7) | curses.A_DIM

        # Title
        title = " MEDITATION BIOFEEDBACK "
        if w >= len(title) + 4:
            stdscr.addstr(row, (w - len(title)) // 2, title, curses.A_BOLD)
        row += 2

        # Time
        time_str = f"  {_format_time(elapsed_sec)} / {_format_time(elapsed_sec + remaining_sec)}"
        stdscr.addstr(row, 0, time_str, dim)
        row += 1

        # State
        state_attr = self._get_state_color(state) | curses.A_BOLD
        stdscr.addstr(row, 2, f"State: {state.value}", state_attr)
        if criteria and state == State.AGITATED:
            crit_str = f"  [{', '.join(criteria)}]"
            stdscr.addstr(row, 2 + len(f"State: {state.value}"), crit_str[:w - 30], curses.color_pair(4))
        row += 1

        # Signal quality bar
        q_bar_len = min(20, w - 20)
        q_filled = int(signal_quality * q_bar_len)
        q_str = f"  Signal: [{'█' * q_filled}{'░' * (q_bar_len - q_filled)}] {signal_quality:.0%}"
        stdscr.addstr(row, 0, q_str, dim)
        row += 2

        # HR
        hr_spark = _mini_spark(list(self._hr_history), min(self.cfg.sparkline_width, w - 20))
        stdscr.addstr(row, 2, f"HR:    {hr_bpm:3d} bpm  {hr_spark}", curses.color_pair(7))
        row += 1

        # HRV
        if hrv:
            rmssd_spark = _mini_spark(list(self._rmssd_history), min(self.cfg.sparkline_width, w - 20))
            stdscr.addstr(row, 2, f"RMSSD: {hrv.rmssd:5.1f} ms  {rmssd_spark}", curses.color_pair(7))
            row += 1
            stdscr.addstr(row, 2, f"SDNN:  {hrv.sdnn:5.1f} ms   pNN50: {hrv.pnn50:.2f}", dim)
            row += 1

        row += 1

        # Feedback level
        if feedback_level > 0:
            fb_str = f"  Feedback Level: {'●' * feedback_level}{'○' * (3 - feedback_level)}"
            stdscr.addstr(row, 0, fb_str, curses.color_pair(4) | curses.A_BOLD)
            row += 1

        # Breathing cue
        if breathing.active and row + 3 < h:
            row += 1
            self._render_breathing(stdscr, row, w, breathing)
            row += 3

        # Footer
        if h > row + 2:
            footer = " [q]uit  [p]ause  [b]reathe "
            stdscr.addstr(h - 1, (w - len(footer)) // 2, footer, dim)

        stdscr.refresh()

    def _render_breathing(self, stdscr, row: int, width: int, bs: BreathingState):
        bar_width = min(40, width - 10)
        attr = curses.color_pair(8)

        label = {"IN": "BREATHE IN ", "HOLD": "   HOLD    ", "OUT": "BREATHE OUT"}.get(
            bs.phase, ""
        )
        stdscr.addstr(row, 4, label, attr | curses.A_BOLD)
        row += 1

        if bs.phase == "IN":
            filled = int(bs.progress * bar_width)
            bar = "░" * filled + " " * (bar_width - filled)
        elif bs.phase == "HOLD":
            bar = "█" * bar_width
        else:  # OUT
            filled = int((1.0 - bs.progress) * bar_width)
            bar = "░" * filled + " " * (bar_width - filled)

        stdscr.addstr(row, 4, f"[{bar}]", attr)
        row += 1
        stdscr.addstr(row, 4, f"  {bs.remaining_sec:.0f}s", attr | curses.A_DIM)
