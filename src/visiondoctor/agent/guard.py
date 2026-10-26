"""Policy guard: runs on every tool call from either agent; verdicts go into the trace (docs/04 §4).

The guard only uses what it has seen flow through tool outputs in this run (latest scan
severities and evidence), so it works the same for in-process and remote MCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from visiondoctor.config import Settings, get_settings
from visiondoctor.repair import FAULT_FOR_REPAIR, check_bounds

ALLOWED_TOOLS = {
    "list_unhealthy_cameras", "scan_camera", "diagnose", "predict_ai_impact", "get_reference_comparison",
    "apply_repair", "verify_repair", "rollback_repair", "describe_fault", "request_human_approval",
    "create_maintenance_ticket", "set_watch", "close_incident",
}


@dataclass
class Verdict:
    allowed: bool
    reason: str = "allowed"

    def block(self) -> dict[str, Any]:
        return {"error": "blocked_by_guard", "reason": self.reason}


@dataclass
class Guard:
    camera_id: str
    incident_id: str
    cfg: Settings = field(default_factory=get_settings)
    approved: set[str] = field(default_factory=set)  # approval ids already granted
    severities: dict[str, int] = field(default_factory=dict)
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    repair_attempts: int = 0
    steps: int = 0
    tokens: int = 0
    blocks: int = 0

    def check(self, tool: str, args: dict[str, Any]) -> Verdict:
        self.steps += 1
        v = self._check(tool, args)
        if not v.allowed:
            self.blocks += 1
        return v

    def _check(self, tool: str, args: dict[str, Any]) -> Verdict:
        if tool not in ALLOWED_TOOLS:
            return Verdict(False, f"tool {tool} not on allowlist")
        if self.steps > self.cfg.max_agent_steps:
            return Verdict(False, f"step budget {self.cfg.max_agent_steps} exhausted")
        if self.tokens > self.cfg.max_agent_tokens:
            return Verdict(False, f"token budget {self.cfg.max_agent_tokens} exhausted")
        cam = args.get("camera_id")
        if cam is not None and cam != self.camera_id:
            return Verdict(False, f"agent is scoped to {self.camera_id}")
        inc = args.get("incident_id")
        if inc is not None and inc != self.incident_id:
            return Verdict(False, f"agent is scoped to incident {self.incident_id}")
        if tool == "apply_repair":
            return self._repair(args)
        if tool == "create_maintenance_ticket" and not self.approved:
            return Verdict(False, "no approved human approval for this incident")
        return Verdict(True)

    def _repair(self, args: dict[str, Any]) -> Verdict:
        repair = str(args.get("repair"))
        fault = FAULT_FOR_REPAIR.get(repair)
        if fault is None:
            return Verdict(False, f"unknown repair {repair}")
        if self.repair_attempts >= self.cfg.max_repair_attempts:
            return Verdict(False, f"max {self.cfg.max_repair_attempts} repair attempts per incident")
        sev = self.severities.get(fault, 0)
        if sev < 2:
            return Verdict(False, f"{fault} severity {sev} in latest scan (< 2): nothing to repair")
        if repair == "realign":
            ev = self.evidence.get("drift", {})
            ok, why = check_bounds("realign", {"H": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], **ev}, self.cfg)
            if not ok:
                return Verdict(False, f"realign out of bounds: {why}")
        params = args.get("params") or {}
        if params and repair != "realign":
            ok, why = check_bounds(repair, {**_defaults(repair), **params}, self.cfg)
            if not ok:
                return Verdict(False, why)
        self.repair_attempts += 1
        return Verdict(True)

    def observe(self, tool: str, out: dict[str, Any]) -> None:
        """Learn the latest scan state from tool outputs."""
        if tool == "scan_camera" and "severities" in out:
            self.severities = dict(out["severities"])
            self.evidence = dict(out.get("key_evidence", {}))
        elif tool == "verify_repair" and out.get("recovered"):
            self.severities[out.get("fault", "")] = int(out.get("severity_after", 0))


def _defaults(repair: str) -> dict[str, Any]:
    return {
        "exposure_fix": {"alpha": 1.0, "gamma": 1.0},
        "dehaze": {"omega": 0.9},
        "white_balance": {"gains": [1.0, 1.0, 1.0]},
        "denoise": {"h": 5.0},
    }.get(repair, {})
