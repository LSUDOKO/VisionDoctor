"""Repairs must fix their fault, report before/after metrics and respect bounds."""

from __future__ import annotations

import numpy as np
import pytest

from visiondoctor import repair
from visiondoctor.health.reference import Reference
from visiondoctor.health.scan import scan
from visiondoctor.repair.verify import verify
from visiondoctor.sim.faults import Fault

FIXABLE = [("drift", 5), ("drift", 3), ("exposure", 3), ("haze", 3), ("color_cast", 4), ("noise", 1), ("exposure", 2)]


def _faulty(burst: list[np.ndarray], name: str, sev: int, **params: float) -> list[np.ndarray]:
    flt = Fault(name, sev, seed=5, params=dict(params))
    return [flt.apply(f) for f in burst]


@pytest.mark.parametrize(("fault", "sev"), FIXABLE)
def test_repair_recovers(reference: Reference, burst: list[np.ndarray], fault: str, sev: int) -> None:
    frames = _faulty(burst, fault, sev)
    before = scan("cam-test", frames, reference)
    assert before.checks[fault].severity >= 2
    step = repair.plan(fault, before, reference)
    assert step is not None
    step = repair.finalize(step, frames[-1])
    ok, why = repair.check_bounds(step.type, step.params)
    assert ok, why
    res = verify("cam-test", step.type, repair.CorrectionProfile([step]), frames, reference, before)
    assert res.recovered, res.to_dict()
    assert res.severity_after < res.severity_before


def test_realign_residual_below_half_degree(reference: Reference, burst: list[np.ndarray]) -> None:
    frames = _faulty(burst, "drift", 5)  # 8° rotation + 7% shift
    before = scan("cam-test", frames, reference)
    assert abs(abs(before.checks["drift"].evidence["rot_deg"]) - 8.0) < 0.5
    step = repair.plan("drift", before, reference)
    assert step is not None
    fixed = [step.apply(f) for f in frames]
    after = scan("cam-test", fixed, reference)
    assert abs(after.checks["drift"].evidence["rot_deg"]) < 0.5


def test_bounds_block_large_rotation() -> None:
    H = np.eye(3).tolist()
    ok, why = repair.check_bounds("realign", {"H": H, "rot_deg": 25.0, "disp_pct_diag": 5.0, "inlier_ratio": 0.9})
    assert not ok and "rotation" in why
    assert not repair.check_bounds("exposure_fix", {"alpha": 1.0, "gamma": 3.0})[0]
    assert not repair.check_bounds("exposure_fix", {"alpha": 4.0, "gamma": 1.0})[0]
    assert not repair.check_bounds("denoise", {"h": 40})[0]
    assert not repair.check_bounds("white_balance", {"gains": [3.0, 1.0, 1.0]})[0]
    assert repair.check_bounds("dehaze", {"omega": 0.9})[0]


def test_profile_rollback(burst: list[np.ndarray]) -> None:
    s1 = repair.RepairStep("exposure_fix", {"alpha": 1.2, "gamma": 0.8})
    s2 = repair.RepairStep("denoise", {"h": 5})
    prof = repair.CorrectionProfile([s1, s2])
    assert [s.type for s in prof.without(s2.repair_id).steps] == ["exposure_fix"]
    assert prof.apply(burst[0]).shape == burst[0].shape
