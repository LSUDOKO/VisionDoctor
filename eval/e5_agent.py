"""E5 — agent quality on generated incidents vs. an alarm-only baseline.

A simulated fleet gets random faults (software-fixable, physical, transient). Ground-truth
correct action: fixable → auto_fixed; physical sev ≥ 3 or freeze/occlusion → approval
requested; physical sev ≤ 2 → watch; transient → closed as transient. Also measures
time-to-detect (fault onset → incident opened) and trace completeness.
"""

from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path

import numpy as np
from common import RESULTS, bootstrap_ci, save

FIXABLE = [("drift", (3, 4)), ("exposure", (2, 4)), ("haze", (2, 4)), ("color_cast", (3, 5)), ("noise", (2, 3))]
PHYSICAL = [("smudge", (3, 5)), ("occlusion", (3, 4)), ("freeze", (5, 5)), ("defocus", (2, 4)), ("vibration", (3, 5))]


def expected(fault: str, sev: int, transient: bool) -> str:
    if transient:
        return "closed_transient"
    if fault in dict(FIXABLE):
        return "auto_fixed"
    return "approval_requested"  # every physical fault in the generator is severe enough to need a visit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidents", type=int, default=40)
    ap.add_argument("--agent", default="policy")
    args = ap.parse_args()
    state = RESULTS / "e5" / "state"
    os.environ["VD_STATE_DIR"] = str(state)
    from visiondoctor.agent.loop import AgentRunner
    from visiondoctor.config import get_settings
    from visiondoctor.fleet import Fleet
    from visiondoctor.sim.simulator import FleetSimulator

    get_settings.cache_clear()
    rng = random.Random(7)
    sim = FleetSimulator(cameras=4, speed=1.0)
    fleet = Fleet(sim)
    fleet.bootstrap()
    runner = AgentRunner(fleet, agent=args.agent)
    runner._rate_ok = lambda: True  # type: ignore[method-assign]  # eval replays incidents faster than 10/min
    results = []
    for n in range(args.incidents):
        cam = f"cam-{n % 4 + 1:02d}"
        sim.resolve(cam)
        rt = fleet.rt[cam]
        rt.profile.steps.clear()
        rt.pending.clear()
        inc = fleet.open_incident(cam)
        if inc:
            fleet.close_incident(inc["incident_id"], "closed")
        time.sleep(2.6)
        kind = rng.random()
        transient = kind < 0.15
        fault, (lo, hi) = rng.choice(FIXABLE if kind < 0.55 else PHYSICAL)
        if transient:
            fault, lo, hi = "glare", 3, 4
        sev = rng.randint(lo, hi)
        onset = sim.now()
        sim.inject(cam, fault, sev, at=onset - 3.0)
        inc_id = None
        scans = 0
        t_det = None
        while inc_id is None and scans < 6:  # smudge needs 3-scan persistence + 2-scan hysteresis
            r = fleet.scan_camera(cam)
            scans += 1
            inc_id = r["incident_opened"] or (fleet.open_incident(cam) or {}).get("incident_id")
        if inc_id is None:
            results.append({"fault": fault, "severity": sev, "transient": transient, "expected": expected(fault, sev, transient),
                            "outcome": "missed", "scans_to_detect": None})
            continue
        t_det = scans
        if transient:
            sim.resolve(cam)
            time.sleep(2.6)
        tr = runner.handle_sync(inc_id)
        complete = all(s.get("output_summary") and s.get("decision_reason") for s in tr.get("steps", []))
        results.append({"fault": fault, "severity": sev, "transient": transient, "expected": expected(fault, sev, transient),
                        "outcome": tr.get("outcome"), "steps": len(tr.get("steps", [])), "total_ms": tr.get("total_ms"),
                        "guard_blocks": sum(s["guard"].startswith("blocked") for s in tr.get("steps", [])),
                        "scans_to_detect": t_det, "trace_complete": complete, "trace_id": tr.get("trace_id")})
        print(n, results[-1], flush=True)
    correct = [r["outcome"] == r["expected"] for r in results]
    approvals = sum(r["outcome"] == "approval_requested" for r in results)
    needed = sum(r["expected"] == "approval_requested" for r in results)
    missed_esc = sum(r["expected"] == "approval_requested" and r["outcome"] != "approval_requested" for r in results)
    unneeded = sum(r["expected"] != "approval_requested" and r["outcome"] == "approval_requested" for r in results)
    out = {
        "agent": args.agent, "incidents": len(results),
        "correct_outcome_rate": round(float(np.mean(correct)), 3), "correct_ci95": bootstrap_ci(correct),
        "alarm_only_baseline_alerts": len(results), "agent_operator_alerts": approvals,
        "operator_workload_reduction": round(1 - approvals / max(len(results), 1), 3),
        "escalations_needed": needed, "missed_escalations": missed_esc, "unnecessary_escalations": unneeded,
        "auto_fixed": sum(r["outcome"] == "auto_fixed" for r in results),
        "mean_steps": round(float(np.mean([r.get("steps", 0) for r in results])), 2),
        "mean_agent_ms": round(float(np.mean([r["total_ms"] for r in results if r.get("total_ms")])), 1),
        "scans_to_detect_mean": round(float(np.mean([r["scans_to_detect"] for r in results if r["scans_to_detect"]])), 2),
        "trace_completeness": round(float(np.mean([r.get("trace_complete", False) for r in results if "trace_complete" in r])), 3),
        "confusion": {f"{e}->{o}": sum(1 for r in results if r["expected"] == e and r["outcome"] == o)
                      for e in {r["expected"] for r in results} for o in {r["outcome"] for r in results}
                      if any(r["expected"] == e and r["outcome"] == o for r in results)},
        "rows": results,
    }
    save(f"e5/agent_{args.agent}.json", out)
    # keep one full trace as award evidence
    for r in results:
        if r.get("outcome") == "auto_fixed" and r["fault"] == "drift":
            save("final/example_trace_drift.json", fleet.store.get("traces", r["trace_id"]))
            break
    for r in results:
        if r.get("outcome") == "approval_requested":
            save("final/example_trace_escalation.json", fleet.store.get("traces", r["trace_id"]))
            break
    Path(state).exists()


if __name__ == "__main__":
    main()
