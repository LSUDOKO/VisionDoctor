"""Agent trace (docs/04 §5): every tool call with input, compact output, reason, guard verdict."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def summarize(tool: str, out: dict[str, Any]) -> str:
    """One-line, number-bearing summary of a tool output for the trace viewer."""
    if "error" in out:
        return f"{out['error']}: {out.get('reason', '')}".strip(": ")
    if tool == "scan_camera":
        faults = out.get("faults") or []
        if not faults:
            return f"healthy (overall {out.get('overall_score')})"
        parts = []
        for f in faults[:3]:
            ev = (out.get("key_evidence") or {}).get(f["type"], {})
            nums = ", ".join(f"{k}={v:.3g}" for k, v in list(ev.items())[:3] if isinstance(v, int | float))
            parts.append(f"{f['type']} sev{f['severity']}" + (f": {nums}" if nums else ""))
        return "; ".join(parts)
    if tool == "diagnose":
        fx = [f"{x['type']}→{x['repair']}{'' if x['within_bounds'] else ' (out of bounds)'}" for x in out.get("fixable", [])]
        return f"faults {[f['type'] for f in out.get('faults', [])]}; fixable {fx}; cause: {out.get('likely_cause')}"
    if tool == "predict_ai_impact":
        return f"predicted accuracy {out.get('predicted_accuracy')} (drop {out.get('predicted_drop')}, 90% CI {out.get('ci90')})"
    if tool == "apply_repair":
        return f"{out.get('repair')} applied ({out.get('repair_id')}), params {out.get('params')}" if out.get("applied") else str(out)
    if tool == "verify_repair":
        state = "recovered" if out.get("recovered") else "NOT recovered"
        return (f"{out.get('fault')} sev {out.get('severity_before')}→{out.get('severity_after')}, pred acc "
                f"{out.get('predicted_accuracy_before')}→{out.get('predicted_accuracy_after')} — {state}")
    if tool == "describe_fault":
        return f"\"{out.get('caption')}\" [{out.get('model')}]"
    if tool == "request_human_approval":
        return f"approval {out.get('approval_id')} {out.get('state')}"
    return ", ".join(f"{k}={v}" for k, v in list(out.items())[:4])


@dataclass
class Trace:
    incident_id: str
    camera_id: str
    agent: str
    trace_id: str = field(default_factory=lambda: "tr_" + uuid.uuid4().hex[:12])
    steps: list[dict[str, Any]] = field(default_factory=list)
    outcome: str = "unfinished"
    started: float = field(default_factory=time.time)
    total_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None

    def add(
        self, tool: str, args: dict[str, Any], out: dict[str, Any], reason: str, latency_ms: float, guard: str,
        changed_plan: bool = False,
    ) -> dict[str, Any]:
        step = {
            "i": len(self.steps) + 1,
            "tool": tool,
            "input": {k: v for k, v in args.items() if k != "params" or v},
            "output_summary": summarize(tool, out),
            "decision_reason": reason,
            "latency_ms": round(latency_ms, 1),
            "guard": guard,
            "changed_plan": changed_plan,
        }
        self.steps.append(step)
        return step

    def finish(self, outcome: str) -> None:
        self.outcome = outcome
        self.total_ms = round((time.time() - self.started) * 1000, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id, "incident_id": self.incident_id, "camera_id": self.camera_id,
            "agent": self.agent, "model": self.model, "steps": self.steps, "outcome": self.outcome,
            "started": self.started, "total_ms": self.total_ms, "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
        }
