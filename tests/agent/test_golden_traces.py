"""Golden traces (docs/04 §6): scripted incidents → expected tool sequence and outcome."""

from __future__ import annotations

import time

from visiondoctor.agent.guard import Guard
from visiondoctor.agent.loop import AgentRunner
from visiondoctor.fleet import Fleet

from tests.agent.conftest import open_incident


def _tools(trace: dict) -> list[str]:  # type: ignore[type-arg]
    return [s["tool"] for s in trace["steps"]]


def test_drift_auto_fixed(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "drift", 4, at=-60)
    tr = runner.handle_sync(open_incident(fleet, "cam-01"))
    assert _tools(tr) == ["scan_camera", "diagnose", "predict_ai_impact", "apply_repair", "verify_repair", "close_incident"]
    assert tr["outcome"] == "auto_fixed"
    assert all(s["guard"] == "allowed" for s in tr["steps"])
    assert fleet.scan_camera("cam-01")["faults"] == []  # corrected stream is healthy now


def test_haze_auto_fixed(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "haze", 3, at=-60)
    tr = runner.handle_sync(open_incident(fleet, "cam-01"))
    assert "apply_repair" in _tools(tr) and tr["outcome"] == "auto_fixed", [s["output_summary"] for s in tr["steps"]]


def test_smudge_requests_approval(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "smudge", 4, at=-60)
    tr = runner.handle_sync(open_incident(fleet, "cam-01", scans=4))
    assert _tools(tr)[-2:] == ["describe_fault", "request_human_approval"]
    assert "apply_repair" not in _tools(tr)
    assert tr["outcome"] == "approval_requested"


def test_occlusion_requests_approval(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-02", "occlusion", 4, at=-60)
    tr = runner.handle_sync(open_incident(fleet, "cam-02"))
    assert tr["outcome"] == "approval_requested"


def test_freeze_requests_approval(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "freeze", 5, at=-60)
    tr = runner.handle_sync(open_incident(fleet, "cam-01"))
    assert tr["outcome"] == "approval_requested"


def test_transient_glare_closed(fleet: Fleet, runner: AgentRunner) -> None:
    eid = fleet.sim.inject("cam-01", "glare", 4, at=-60)
    inc = open_incident(fleet, "cam-01")
    fleet.sim.resolve("cam-01")  # glare passes before the agent looks again
    time.sleep(2.5)  # let the 5-frame burst window move past the glare
    tr = runner.handle_sync(inc)
    assert eid and _tools(tr) == ["scan_camera", "close_incident"]
    assert tr["outcome"] == "closed_transient"
    assert fleet.get_incident(inc)["state"] == "false_alarm"  # type: ignore[index]


def test_out_of_bounds_drift_blocked_then_escalated(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "drift", 5, at=-60, rot_deg=25.0, shift_frac=0.02)
    tr = runner.handle_sync(open_incident(fleet, "cam-01"))
    rep = [s for s in tr["steps"] if s["tool"] == "apply_repair"]
    assert rep and rep[0]["guard"].startswith("blocked")
    assert tr["outcome"] == "approval_requested"
    assert _tools(tr)[-1] == "request_human_approval"


def test_guard_rules() -> None:
    g = Guard("cam-01", "inc_1")
    g.observe("scan_camera", {"severities": {"drift": 1, "haze": 3}, "key_evidence": {}})
    assert not g.check("apply_repair", {"camera_id": "cam-01", "repair": "realign"}).allowed  # sev < 2
    assert g.check("apply_repair", {"camera_id": "cam-01", "repair": "dehaze"}).allowed
    assert not g.check("apply_repair", {"camera_id": "cam-01", "repair": "dehaze", "params": {"omega": 0.99}}).allowed
    assert not g.check("scan_camera", {"camera_id": "cam-02"}).allowed  # scoped
    assert not g.check("create_maintenance_ticket", {"incident_id": "inc_1", "fault_type": "x", "instructions": "y"}).allowed
    assert not g.check("rm_rf", {}).allowed


def test_approval_flow_creates_ticket_and_closes(fleet: Fleet, runner: AgentRunner) -> None:
    fleet.sim.inject("cam-01", "occlusion", 4, at=-60)
    inc_id = open_incident(fleet, "cam-01")
    runner.handle_sync(inc_id)
    inc = fleet.get_incident(inc_id)
    assert inc and inc["state"] == "awaiting_approval"
    ap = fleet.decide(inc["approval_id"], True, "judge@example.com")
    assert ap["state"] == "approved" and ap.get("ticket_id")
    assert fleet.get_incident(inc_id)["approved_by"] == "judge@example.com"  # type: ignore[index]
    fleet.sim.resolve("cam-01")  # technician fixed it
    time.sleep(2.5)
    fleet.scan_camera("cam-01")
    assert fleet.get_incident(inc_id)["state"] == "closed"  # type: ignore[index]
