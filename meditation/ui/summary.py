"""Post-session text report with sparkline timeline."""

from ..session.recorder import SessionRecorder, RecordEntry
from ..session.state_machine import State
from ..config import Config


SPARK_CHARS = "▁▂▃▄▅▆▇█"
STATE_CHARS = {
    "CALIBRATING": "C",
    "MEDITATING": "·",
    "AGITATED": "!",
    "RECOVERING": "~",
    "COMPLETED": ".",
    "WAITING": "_",
}


def _sparkline(values: list[float], width: int) -> str:
    if not values:
        return ""
    # Bucket values into `width` bins
    bin_size = max(1, len(values) // width)
    bins = []
    for i in range(0, len(values), bin_size):
        chunk = values[i : i + bin_size]
        bins.append(sum(chunk) / len(chunk))
        if len(bins) >= width:
            break
    if not bins:
        return ""
    lo, hi = min(bins), max(bins)
    rng = hi - lo if hi > lo else 1
    return "".join(
        SPARK_CHARS[min(len(SPARK_CHARS) - 1, int((v - lo) / rng * (len(SPARK_CHARS) - 1)))]
        for v in bins
    )


def _format_duration(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def generate_summary(recorder: SessionRecorder, config: Config) -> str:
    entries = recorder.entries
    if not entries:
        return "No data recorded."

    duration = entries[-1].elapsed_sec
    hrs = [e.hr_bpm for e in entries]
    rmssd_vals = [e.hrv.rmssd for e in entries if e.hrv]

    # Time in each state
    state_time: dict[str, float] = {}
    for i, e in enumerate(entries):
        dt = 1.0
        if i + 1 < len(entries):
            dt = entries[i + 1].elapsed_sec - e.elapsed_sec
        state_time[e.state] = state_time.get(e.state, 0) + dt

    lines = []
    lines.append("=" * 60)
    lines.append("  MEDITATION SESSION SUMMARY")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Duration:    {_format_duration(duration)}")
    lines.append(f"  Avg HR:      {sum(hrs)/len(hrs):.0f} bpm")
    if rmssd_vals:
        lines.append(f"  Avg RMSSD:   {sum(rmssd_vals)/len(rmssd_vals):.1f} ms")
    lines.append("")

    # State breakdown
    lines.append("  Time in State:")
    for state_name in ["CALIBRATING", "MEDITATING", "AGITATED", "RECOVERING"]:
        sec = state_time.get(state_name, 0)
        pct = sec / duration * 100 if duration > 0 else 0
        lines.append(f"    {state_name:14s} {_format_duration(sec):>10s}  ({pct:4.1f}%)")
    lines.append("")

    # Agitation events
    events = recorder.agitation_events
    if events:
        lines.append(f"  Agitation Events: {len(events)}")
        for i, ev in enumerate(events, 1):
            dur = ev.duration_sec
            dur_str = _format_duration(dur) if dur else "ongoing"
            lines.append(f"    #{i}: at {_format_duration(ev.start_sec)}, "
                         f"duration {dur_str}, peak HR {ev.peak_hr} bpm, "
                         f"min RMSSD {ev.min_rmssd:.1f} ms")
            if ev.feedback_cues:
                lines.append(f"        Feedback levels used: {ev.feedback_cues}")
            if ev.criteria:
                lines.append(f"        Triggers: {', '.join(ev.criteria)}")
    else:
        lines.append("  Agitation Events: None")
    lines.append("")

    # Sparkline timelines
    width = min(config.sparkline_width, len(entries))
    lines.append(f"  HR Timeline:    {_sparkline([float(h) for h in hrs], width)}")
    if rmssd_vals:
        lines.append(f"  RMSSD Timeline: {_sparkline(rmssd_vals, width)}")

    # State timeline (1 char per minute)
    state_chars = []
    minute_entries: dict[int, list[str]] = {}
    for e in entries:
        minute = int(e.elapsed_sec / 60)
        minute_entries.setdefault(minute, []).append(e.state)
    for m in range(max(minute_entries.keys()) + 1 if minute_entries else 0):
        states = minute_entries.get(m, ["WAITING"])
        # Most common state in that minute
        most_common = max(set(states), key=states.count)
        state_chars.append(STATE_CHARS.get(most_common, "?"))
    lines.append(f"  State Timeline: {''.join(state_chars)}")
    lines.append(f"                  C=calibrating ·=meditating !=agitated ~=recovering")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
