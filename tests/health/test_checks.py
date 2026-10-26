"""Each check must catch its own injected fault at severity ≥ 3 and stay quiet on clean frames."""

from __future__ import annotations

import numpy as np
import pytest

from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.reference import Reference
from visiondoctor.health.scan import scan
from visiondoctor.sim.faults import EXPECTED_CHECK, Fault

# Faults whose primary check is reliable on the synthetic scene. spider_web is a VLM hint
# (night/IR) and is validated separately; occlusion at 100% is reported as a dead frame.
CASES = [f for f in EXPECTED_CHECK if f not in ("spider_web",)]
PERSISTENT = {"smudge"}  # needs 3 consecutive scans by design


def _scan_fault(reference: Reference, burst: list[np.ndarray], name: str, sev: int) -> dict[str, int]:
    flt = Fault(name, sev, seed=3)
    st = CameraState()
    frames = [flt.apply(f) for f in burst]
    n = 3 if name in PERSISTENT else 1
    for _ in range(n):
        rep = scan("cam-test", frames, reference, st)
    return {k: v.severity for k, v in rep.checks.items()}


def test_clean_burst_is_quiet(reference: Reference, burst: list[np.ndarray]) -> None:
    rep = scan("cam-test", burst, reference)
    loud = {k: v.severity for k, v in rep.checks.items() if v.severity >= 2}
    assert loud == {}
    assert rep.overall_score >= 0.8


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("sev", [3, 4, 5])
def test_fault_detected(reference: Reference, burst: list[np.ndarray], name: str, sev: int) -> None:
    sevs = _scan_fault(reference, burst, name, sev)
    expected = EXPECTED_CHECK[name]
    if name == "occlusion" and sev == 5:
        expected = "freeze"  # fully covered lens = uniform/dead frame
    # A heavy smear over a third of the lens is indistinguishable from an occluder; both are
    # physical faults with the same outcome (dispatch), so either check may claim it.
    alternatives = {"smudge": ("smudge", "occlusion")}.get(name, (expected,))
    assert max(sevs[a] for a in alternatives) >= 2, sevs


def test_report_serialises(reference: Reference, burst: list[np.ndarray]) -> None:
    d = scan("cam-test", burst, reference).to_dict()
    assert set(d["checks"]) == set(EXPECTED_CHECK.values())
    assert len(d["heatmap"]) == 8
