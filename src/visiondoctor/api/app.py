"""REST API for the dashboard (docs/02 §5). OpenAPI at /docs. All routes but /health need a JWT."""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from visiondoctor import cv_runtime
from visiondoctor.api.auth import current_user, require_group
from visiondoctor.config import ROOT, get_settings
from visiondoctor.fleet import OPEN_STATES, Fleet
from visiondoctor.observability.logging import setup
from visiondoctor.observability.metrics import timings
from visiondoctor.service import FleetService
from visiondoctor.sim.simulator import SCENARIO_DIR, FleetSimulator

STATE: dict[str, Any] = {}


def fleet() -> Fleet:
    f = STATE.get("fleet")
    if f is None:
        raise HTTPException(503, "fleet starting")
    return f  # type: ignore[no-any-return]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup()
    cams = int(os.environ.get("VD_CAMERAS", "12"))
    sim = FleetSimulator(cameras=cams, speed=float(os.environ.get("VD_SIM_SPEED", "1")),
                         truth_path=get_settings().results_dir / "sim" / "truth.jsonl")
    f = Fleet(sim)
    f.bootstrap()
    STATE["fleet"] = f
    if os.environ.get("VD_MONITOR", "1") == "1":
        svc = FleetService(f, float(os.environ.get("VD_SCAN_INTERVAL", "15")))
        svc.start()
        STATE["service"] = svc
    yield
    if "service" in STATE:
        STATE["service"].stop()


app = FastAPI(title="VisionDoctor API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("VD_CORS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    info = cv_runtime.summary()
    return {"status": "ok" if "fleet" in STATE else "starting", "opencv": info["version"], "is_cool": info["is_cool"],
            "cv2_file": info["cv2_file"], "machine": info["machine"], "agent": get_settings().agent,
            "backend": get_settings().backend}


@api.get("/summary")
def summary() -> dict[str, Any]:
    f = fleet()
    cams = f.store.query("cameras")
    incs = f.store.query("incidents", limit=500)
    day = time.time() - 86400
    accs = [c["predicted_ai_accuracy"] for c in cams if c.get("predicted_ai_accuracy") is not None]
    return {
        "cameras": len(cams),
        "healthy_pct": round(100 * sum(c.get("status") == "healthy" for c in cams) / max(len(cams), 1), 1),
        "by_status": {s: sum(c.get("status") == s for c in cams) for s in ("healthy", "watch", "degraded", "failed", "repairing")},
        "predicted_fleet_accuracy": round(sum(accs) / len(accs), 3) if accs else None,
        "open_incidents": sum(i["state"] in OPEN_STATES for i in incs),
        "awaiting_approval": sum(i["state"] == "awaiting_approval" for i in incs),
        "auto_fixed_today": sum(i["state"] == "repaired" and i["opened_at"] > day for i in incs),
        "false_alarms_today": sum(i["state"] == "false_alarm" and i["opened_at"] > day for i in incs),
        "is_cool": f.runtime_info["is_cool"],
    }


@api.get("/cameras")
def cameras() -> list[dict[str, Any]]:
    f = fleet()
    out = []
    for c in sorted(f.store.query("cameras"), key=lambda c: c["camera_id"]):
        c["thumbnail_url"] = f.store.blob_url(f"live/{c['camera_id']}.jpg")
        out.append(c)
    return out


@api.get("/cameras/{camera_id}")
def camera(camera_id: str) -> dict[str, Any]:
    f = fleet()
    c = f.store.get("cameras", camera_id)
    if c is None:
        raise HTTPException(404, "unknown camera")
    latest = f.store.query("health_reports", camera_id, limit=1)
    rt = f.rt.get(camera_id)
    return c | {
        "latest_report": latest[0] if latest else None,
        "images": f.reference_comparison(camera_id),
        "corrections": rt.profile.to_list() if rt else [],
        "open_incident": f.open_incident(camera_id),
        "active_sim_faults": f.sim.active_faults(camera_id),
    }


@api.get("/cameras/{camera_id}/history")
def history(camera_id: str, hours: float = 24) -> list[dict[str, Any]]:
    f = fleet()
    since = time.time() - hours * 3600
    rows = f.store.query("health_reports", camera_id, limit=2000, newest_first=False)
    return [{"ts": r["ts"], "overall": r["overall_score"], "predicted_ai_accuracy": r.get("predicted_ai_accuracy"),
             "severities": {k: v["severity"] for k, v in r["checks"].items()}} for r in rows if r["ts"] >= since]


@api.post("/cameras/{camera_id}/scan")
def scan_now(camera_id: str) -> dict[str, Any]:
    f = fleet()
    if camera_id not in f.rt:
        raise HTTPException(404, "unknown camera")
    return f.scan_camera(camera_id)


class Rollback(BaseModel):
    repair_id: str


@api.post("/cameras/{camera_id}/rollback")
def rollback(camera_id: str, body: Rollback) -> dict[str, Any]:
    return fleet().rollback_repair(camera_id, body.repair_id)


@api.get("/incidents")
def incidents(state: str | None = None) -> list[dict[str, Any]]:
    f = fleet()
    rows = f.store.query("incidents", limit=500)
    if state == "open":
        rows = [r for r in rows if r["state"] in OPEN_STATES]
    elif state:
        rows = [r for r in rows if r["state"] == state]
    for r in rows:
        r["evidence_urls"] = [f.store.blob_url(k) for k in r.get("evidence_keys", [])[:4]]
        if r.get("approval_id"):
            r["approval"] = f.store.get("approvals", r["approval_id"])
    return sorted(rows, key=lambda r: (r["state"] not in OPEN_STATES, -float(r.get("priority_score", 0))))


@api.get("/incidents/{incident_id}")
def incident(incident_id: str) -> dict[str, Any]:
    inc = fleet().get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, "unknown incident")
    return inc


def _decide(incident_id: str, approve: bool, user: dict[str, Any]) -> dict[str, Any]:
    f = fleet()
    inc = f.get_incident(incident_id)
    if inc is None or not inc.get("approval_id"):
        raise HTTPException(409, "incident has no pending approval")
    return f.decide(inc["approval_id"], approve, user["username"])


@api.post("/incidents/{incident_id}/approve")
def approve(incident_id: str, user: dict[str, Any] = Depends(require_group("operator"))) -> dict[str, Any]:
    return _decide(incident_id, True, user)


@api.post("/incidents/{incident_id}/reject")
def reject(incident_id: str, user: dict[str, Any] = Depends(require_group("operator"))) -> dict[str, Any]:
    return _decide(incident_id, False, user)


@api.post("/incidents/{incident_id}/false_alarm")
def false_alarm(incident_id: str, user: dict[str, Any] = Depends(require_group("operator"))) -> dict[str, Any]:
    return fleet().close_incident(incident_id, "false_alarm") | {"by": user["username"]}


@api.get("/traces/{trace_id}")
def trace(trace_id: str) -> dict[str, Any]:
    t = fleet().store.get("traces", trace_id)
    if t is None:
        raise HTTPException(404, "unknown trace")
    return t


@api.get("/traces")
def traces(limit: int = 50) -> list[dict[str, Any]]:
    rows = fleet().store.query("traces", limit=500)
    return sorted(rows, key=lambda t: -t.get("started", 0))[:limit]


@api.get("/bench")
def bench() -> dict[str, Any]:
    p = get_settings().results_dir / "bench" / "summary.json"
    final = ROOT / "results" / "final" / "bench_summary.json"
    for path in (p, final):
        if path.exists():
            return json.loads(path.read_text())  # type: ignore[no-any-return]
    return {"available": False}


@api.get("/metrics/ops")
def op_metrics() -> dict[str, Any]:
    import numpy as np

    return {k: {"n": len(v), "p50_ms": round(float(np.median(v)), 3), "p95_ms": round(float(np.percentile(v, 95)), 3)}
            for k, v in timings().items() if v}


@api.get("/scenarios")
def scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.yaml"))


class Scenario(BaseModel):
    name: str = "demo"


@api.post("/sim/scenario")
def start_scenario(body: Scenario, user: dict[str, Any] = Depends(require_group("admin"))) -> dict[str, Any]:
    if body.name not in scenarios():
        raise HTTPException(404, "unknown scenario")
    return fleet().sim.run_scenario(body.name) | {"by": user["username"]}


class Inject(BaseModel):
    camera_id: str
    fault: str
    severity: int = 3
    duration_s: float | None = None
    backdate_s: float = 0.0  # start the fault this many sim-seconds ago


@api.post("/sim/inject")
def inject(body: Inject, user: dict[str, Any] = Depends(require_group("admin"))) -> dict[str, Any]:
    f = fleet()
    if body.camera_id not in f.rt:
        raise HTTPException(404, "unknown camera")
    at = f.sim.now() - max(body.backdate_s, 0.0)
    return {"event_id": f.sim.inject(body.camera_id, body.fault, body.severity, body.duration_s, at=at)}


@api.get("/blobs/{key:path}")
def blob(key: str) -> Response:
    data = fleet().store.get_blob(key)
    if data is None:
        raise HTTPException(404, "not found")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


app.include_router(api)

_web = Path(os.environ.get("VD_WEB_DIST", ROOT / "web" / "dist"))
if _web.exists():
    app.mount("/", StaticFiles(directory=_web, html=True), name="web")
