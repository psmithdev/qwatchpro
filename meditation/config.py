"""All thresholds, constants, and configuration for the meditation biofeedback system."""

from dataclasses import dataclass, field


@dataclass
class Config:
    # Session timing
    default_duration_min: float = 45.0
    calibration_min: float = 5.0
    calibration_max_min: float = 10.0
    calibration_quality_threshold: float = 0.70

    # Signal processing
    hrv_window_sec: float = 60.0
    hrv_recompute_sec: float = 5.0
    rr_min_ms: int = 300
    rr_max_ms: int = 2000
    rr_max_successive_diff_ms: int = 300
    rr_jitter_std_ms: float = 15.0

    # Agitation detection (need >= criteria_required of 4)
    criteria_required: int = 2
    rmssd_drop_pct: float = 0.30
    hr_rise_bpm: float = 8.0
    sdnn_drop_pct: float = 0.25
    pnn50_drop_pct: float = 0.35
    agitation_sustain_sec: float = 15.0
    recovery_sustain_sec: float = 30.0

    # Feedback
    feedback_cooldown_sec: float = 90.0
    feedback_initial_delay_sec: float = 10.0
    tone_freq_hz: float = 396.0
    tone_duration_sec: float = 2.0
    tone_volume: float = 0.3
    tone_volume_loud: float = 0.5

    # Breathing pattern (seconds)
    breathe_in_sec: float = 4.0
    breathe_hold_sec: float = 2.0
    breathe_out_sec: float = 6.0

    # UI
    ui_refresh_hz: float = 1.0
    sparkline_width: int = 40

    # Audio
    audio_enabled: bool = True
    audio_sample_rate: int = 44100
