"""Multi-criteria agitation detection."""

from ..config import Config
from .baseline import Baseline
from ..signal.hrv_metrics import HRVResult


class AgitationDetector:
    def __init__(self, config: Config):
        self.cfg = config

    def score(self, baseline: Baseline, current: HRVResult) -> tuple[int, list[str]]:
        """Return (criteria_met_count, list_of_triggered_criteria)."""
        triggered = []

        # 1. RMSSD drop >30%
        if baseline.mean_rmssd > 0:
            rmssd_drop = (baseline.mean_rmssd - current.rmssd) / baseline.mean_rmssd
            if rmssd_drop > self.cfg.rmssd_drop_pct:
                triggered.append(f"RMSSD -{rmssd_drop:.0%}")

        # 2. HR rise >8 bpm
        hr_rise = current.mean_hr - baseline.mean_hr
        if hr_rise > self.cfg.hr_rise_bpm:
            triggered.append(f"HR +{hr_rise:.0f}bpm")

        # 3. SDNN drop >25%
        if baseline.mean_sdnn > 0:
            sdnn_drop = (baseline.mean_sdnn - current.sdnn) / baseline.mean_sdnn
            if sdnn_drop > self.cfg.sdnn_drop_pct:
                triggered.append(f"SDNN -{sdnn_drop:.0%}")

        # 4. pNN50 drop >35%
        if baseline.mean_pnn50 > 0:
            pnn50_drop = (baseline.mean_pnn50 - current.pnn50) / baseline.mean_pnn50
            if pnn50_drop > self.cfg.pnn50_drop_pct:
                triggered.append(f"pNN50 -{pnn50_drop:.0%}")

        return len(triggered), triggered

    def is_agitated(self, baseline: Baseline, current: HRVResult) -> bool:
        count, _ = self.score(baseline, current)
        return count >= self.cfg.criteria_required

    def is_recovered(self, baseline: Baseline, current: HRVResult) -> bool:
        count, _ = self.score(baseline, current)
        return count == 0
