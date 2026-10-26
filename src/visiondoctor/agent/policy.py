"""Deterministic policy agent (docs/04 §3.1) — reproducible, no LLM, same tools and trace."""

from __future__ import annotations

from typing import Any

from visiondoctor.agent.base import AgentRun
from visiondoctor.config import get_settings
from visiondoctor.health.types import SOFTWARE_FIXABLE

FIX_ORDER = ["drift", "exposure", "haze", "color_cast", "noise"]  # geometry first, then photometry


async def run(r: AgentRun, camera_id: str, incident_id: str) -> str:
    cfg = get_settings()
    scan = await r.act("scan_camera", {"camera_id": camera_id}, "always re-scan before acting")
    faults = scan.get("faults") or []
    if "error" in scan:
        return "error"
    if not faults:
        await r.act("close_incident", {"incident_id": incident_id, "resolution": "transient"},
                    f"re-scan healthy (overall {scan.get('overall_score')}): fault was transient", changed_plan=True)
        return "closed_transient"
    names = [f["type"] for f in faults]
    diag = await r.act("diagnose", {"camera_id": camera_id}, f"faults {names}: localise and check fixability")
    imp = await r.act("predict_ai_impact", {"camera_id": camera_id},
                      "quantify harm to the downstream detector before choosing repair vs escalation")
    drop = float(imp.get("predicted_drop") or 0.0)
    cause = str(diag.get("likely_cause", ""))

    if cause.startswith("site-wide weather"):
        await r.act("set_watch", {"camera_id": camera_id, "scan_interval_s": 60},
                    f"{cause}: not a camera fault, rescan more often", changed_plan=True)
        await r.act("close_incident", {"incident_id": incident_id, "resolution": "watch"}, "weather, watch only")
        return "watch"

    if all(n in SOFTWARE_FIXABLE for n in names):
        fixed = await _repair_all(r, camera_id, names, drop)
        if fixed:
            await r.act("close_incident", {"incident_id": incident_id, "resolution": "auto_fixed"},
                        "all faults repaired and verified by re-scan")
            return "auto_fixed"

    return await _escalate(r, camera_id, incident_id, diag, drop, cfg.p_dispatch)


async def _repair_all(r: AgentRun, camera_id: str, names: list[str], drop: float) -> bool:
    for fault in sorted(names, key=FIX_ORDER.index):
        repair = {"drift": "realign", "exposure": "exposure_fix", "haze": "dehaze",
                  "color_cast": "white_balance", "noise": "denoise"}[fault]
        ap = await r.act("apply_repair", {"camera_id": camera_id, "repair": repair},
                         f"{fault} is software-fixable; predicted drop {drop:.2f} justifies a bounded {repair}")
        if not ap.get("applied"):
            return False
        ver = await r.act("verify_repair", {"camera_id": camera_id, "repair_id": ap["repair_id"]},
                          "a repair only counts if re-scan and re-prediction recover")
        if not ver.get("recovered"):
            await r.act("rollback_repair", {"camera_id": camera_id, "repair_id": ap["repair_id"]},
                        f"verification failed (sev {ver.get('severity_before')}→{ver.get('severity_after')}): roll back",
                        changed_plan=True)
            return False
    return True


async def _escalate(r: AgentRun, camera_id: str, incident_id: str, diag: dict[str, Any], drop: float, p_dispatch: float) -> str:
    faults = diag.get("faults") or [{}]
    top = faults[0]
    desc = await r.act("describe_fault", {"camera_id": camera_id, "region_bbox": top.get("region_bbox")},
                       f"{top.get('type')} needs a human: describe it for the technician", changed_plan=True)
    crit = int(diag.get("criticality", 3))
    priority = drop * crit
    if priority >= p_dispatch or top.get("type") in ("freeze", "occlusion"):
        action = "ptz_rehome" if top.get("type") == "drift" else "dispatch_technician"
        reason = (f"{top.get('type')} sev{top.get('severity')}: predicted drop {drop:.2f} × criticality {crit} = "
                  f"{priority:.2f} ≥ {p_dispatch}. {desc.get('caption', '')}")
        await r.act("request_human_approval", {"incident_id": incident_id, "action": action, "reason": reason[:500]},
                    f"priority {priority:.2f} above dispatch threshold {p_dispatch}")
        return "approval_requested"
    await r.act("set_watch", {"camera_id": camera_id, "scan_interval_s": 60},
                f"priority {priority:.2f} below dispatch threshold {p_dispatch}: watch")
    await r.act("close_incident", {"incident_id": incident_id, "resolution": "watch"}, "low impact, watchlist")
    return "watch"
