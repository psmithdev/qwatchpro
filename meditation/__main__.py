"""Entry point: python -m meditation [--mock|--mac XX:XX] [--duration N] [--speed N] [--no-audio] [--headless]"""

import argparse
import asyncio
import time
import sys

from .config import Config
from .sensor.base import SensorSample
from .signal.filters import RRFilter
from .signal.rr_estimator import RREstimator
from .signal.hrv_metrics import HRVComputer
from .session.state_machine import SessionStateMachine, State
from .session.detector import AgitationDetector
from .session.recorder import SessionRecorder, RecordEntry
from .feedback.engine import FeedbackEngine
from .ui.summary import generate_summary


def parse_args():
    p = argparse.ArgumentParser(description="Meditation Biofeedback System")
    p.add_argument("--mock", action="store_true", help="Use mock sensor data")
    p.add_argument("--mac", type=str, help="QWatch MAC address for BLE connection")
    p.add_argument("--duration", type=float, default=45, help="Session duration in minutes")
    p.add_argument("--speed", type=float, default=1.0, help="Playback speed for mock (e.g. 10 = 10x)")
    p.add_argument("--no-audio", action="store_true", help="Disable audio feedback")
    p.add_argument("--headless", action="store_true", help="Run without curses UI (prints state changes)")
    return p.parse_args()


async def _run_pipeline(args, stdscr=None):
    """Core pipeline shared by curses and headless modes."""
    config = Config(default_duration_min=args.duration)
    if args.no_audio:
        config.audio_enabled = False

    # Initialize sensor
    if args.mac:
        from .sensor.qwatch_adapter import QWatchAdapter
        sensor = QWatchAdapter(config, args.mac)
    else:
        from .sensor.mock_adapter import MockAdapter
        sensor = MockAdapter(config, speed=args.speed)

    # Initialize pipeline
    rr_filter = RRFilter(config)
    rr_estimator = RREstimator(config)
    hrv_computer = HRVComputer(config)
    session = SessionStateMachine(config, args.duration)
    detector = AgitationDetector(config)
    feedback = FeedbackEngine(config)

    ui = None
    if stdscr is not None:
        import curses
        from .ui.terminal import TerminalUI
        ui = TerminalUI(config)
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(int(1000 / config.ui_refresh_hz / max(args.speed, 1)))

    await sensor.connect()

    first_sample = True
    recorder = None
    current_hr = 0
    current_hrv = None
    current_criteria: list[str] = []
    paused = False
    last_state = None

    try:
        async for sample in sensor.stream():
            now = sample.timestamp

            if first_sample:
                session.begin(start_time=now)
                recorder = SessionRecorder(now)
                first_sample = False

            elapsed = now - session.start_time

            if session.state == State.COMPLETED:
                break

            current_hr = sample.hr_bpm

            rr_ms = sample.rr_ms
            if rr_ms is None:
                rr_ms = rr_estimator.estimate(sample.hr_bpm)

            if not rr_filter.accept(rr_ms):
                continue

            hrv_result = hrv_computer.add_rr(now, rr_ms)
            if hrv_result:
                current_hrv = hrv_result

            if hrv_result:
                old_state = session.state
                new_state = session.update(hrv_result, rr_filter.quality, now)

                if session.baseline.ready and current_hrv:
                    _, current_criteria = detector.score(session.baseline, current_hrv)

                if old_state != State.AGITATED and new_state == State.AGITATED:
                    recorder.start_agitation(elapsed, current_criteria)
                elif old_state == State.AGITATED and new_state != State.AGITATED:
                    recorder.end_agitation(elapsed)

                if new_state == State.AGITATED and current_hrv:
                    recorder.update_agitation(current_hr, current_hrv.rmssd, feedback.level)

                # Headless state change logging
                if args.headless and new_state != last_state:
                    m, s = divmod(int(elapsed), 60)
                    print(f"  [{m:02d}:{s:02d}] {old_state.value} → {new_state.value}", flush=True)
                    last_state = new_state

            feedback_level = await feedback.update(session.state, time.time())

            recorder.record(RecordEntry(
                timestamp=now, elapsed_sec=elapsed, hr_bpm=current_hr,
                rr_ms=rr_ms, hrv=current_hrv, state=session.state.value,
                signal_quality=rr_filter.quality, feedback_level=feedback_level,
            ))

            # Curses UI rendering
            if ui and not paused:
                import curses
                try:
                    ui.render(
                        stdscr, state=session.state, elapsed_sec=elapsed,
                        remaining_sec=session.remaining_sec(now), hr_bpm=current_hr,
                        hrv=current_hrv, signal_quality=rr_filter.quality,
                        feedback_level=feedback_level,
                        breathing=feedback.breathing.get_state(),
                        criteria=current_criteria,
                    )
                except curses.error:
                    pass

            # Key input (curses mode only)
            if stdscr is not None:
                import curses
                try:
                    key = stdscr.getch()
                    if key == ord("q"):
                        break
                    elif key == ord("p"):
                        paused = not paused
                    elif key == ord("b"):
                        if feedback.breathing.active:
                            feedback.breathing.stop()
                        else:
                            feedback.breathing.start()
                except curses.error:
                    pass

    except asyncio.CancelledError:
        pass
    finally:
        await sensor.disconnect()

    return recorder, config


def main():
    args = parse_args()

    if not args.mac:
        args.mock = True

    if args.headless:
        print(f"Meditation session: {args.duration} min (speed {args.speed}x, headless)")
        recorder, config = asyncio.run(_run_pipeline(args))
        if recorder:
            print()
            print(generate_summary(recorder, config))
    else:
        import curses

        def curses_main(stdscr):
            return asyncio.run(_run_pipeline(args, stdscr))

        result = curses.wrapper(curses_main)
        if result:
            recorder, config = result
            print(generate_summary(recorder, config))


if __name__ == "__main__":
    main()
