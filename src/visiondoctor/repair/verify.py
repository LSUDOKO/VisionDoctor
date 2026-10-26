"""Verify a repair by re-scanning corrected frames (and re-predicting AI impact).

docs/03 §4: success iff the triggering check's severity drops to ≤ 1 AND predicted accuracy
recovers by ≥ 50% of the predicted loss AND the repair did not create a new fault (e.g. an
over-strong denoise reading as defocus). Otherwise the caller rolls back and escalates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.reference import Reference
from visiondoctor.health.scan import scan
from visiondoctor.health.types import HealthReport
from visiondoctor.repair import FAULT_FOR_REPAIR, CorrectionProfile

# Expected side effects: realign leaves a black (cropped) border; dehazing amplifies sensor
# noise by 1/t (judged by the impact predictor instead).
SIDE_EFFECTS: dict[str, set[str]] = {"realign": {"occlusion", "exposure"}, "dehaze": {"noise"}}

MATERIAL_LOSS = 0.15  # below this predicted loss, recovery is judged by "no harm" instead
NOISE_TOLERANCE = 0.1  # ≈ impact predictor MAE (results/final/e3_impact.json)

ImpactFn = Callable[[HealthReport, list[np.ndarray]], float]  # → predicted accuracy 0..1


@dataclass
class VerifyResult:
    recovered: bool
    fault: str
    severity_before: int
    severity_after: int
    acc_before: float | None
    acc_after: float | None
    report_after: HealthReport
    regressions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovered": self.recovered,
            "fault": self.fault,
            "severity_before": self.severity_before,
            "severity_after": self.severity_after,
            "predicted_accuracy_before": self.acc_before,
            "predicted_accuracy_after": self.acc_after,
            "overall_after": round(self.report_after.overall_score, 3),
            "regressions": self.regressions,
            "evidence_after": self.report_after.checks[self.fault].to_dict()["evidence"],
        }


def verify(
    camera_id: str,
    repair_type: str,
    profile: CorrectionProfile,
    frames: list[np.ndarray],
    reference: Reference,
    report_before: HealthReport,
    impact: ImpactFn | None = None,
    acc_before: float | None = None,
) -> VerifyResult:
    fault = FAULT_FOR_REPAIR[repair_type]
    corrected = [profile.apply(f) for f in frames]
    after = scan(camera_id, corrected, reference, CameraState())
    sev_b = report_before.checks[fault].severity
    sev_a = after.checks[fault].severity
    allowed = SIDE_EFFECTS.get(repair_type, set())
    regressions = [
        n
        for n, c in after.checks.items()
        if n != fault and n not in allowed and c.severity >= 3 and report_before.checks[n].severity <= 1
    ]
    ok = sev_a <= 1 and not regressions
    acc_a = None
    if impact is not None:
        acc_a = impact(after, corrected)
        if acc_before is not None:
            loss = 1.0 - acc_before
            if loss >= MATERIAL_LOSS:
                ok = ok and (acc_a - acc_before) >= 0.5 * loss
            else:
                # Predicted harm was small: the 50%-recovery test would be decided by predictor
                # noise, so only require that the repair did not make predicted accuracy worse.
                ok = ok and acc_a >= acc_before - NOISE_TOLERANCE
    return VerifyResult(ok, fault, sev_b, sev_a, acc_before, acc_a, after, regressions)
