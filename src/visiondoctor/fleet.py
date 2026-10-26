"""Fleet runtime: cameras, references, scans, incidents, repairs, approvals.

This is the single place where OpenCV results become fleet state. MCP tools (mcp_server/) are
thin, typed wrappers over these methods; the REST API reads the same storage.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visiondoctor import cv_runtime, repair
from visiondoctor.config import Settings, get_settings
from visiondoctor.health import heatmap
from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.reference import Reference, learn_reference
from visiondoctor.health.scan import scan
from visiondoctor.health.types import SOFTWARE_FIXABLE, HealthReport
from visiondoctor.impact.predictor import detector_baseline, predict_impact
from visiondoctor.observability.logging import get as get_log
from visiondoctor.observability.metrics import emit
from visiondoctor.privacy.face_blur import blur_faces
from visiondoctor.repair.verify import verify
from visiondoctor.sim.simulator import FleetSimulator
from visiondoctor.storage import get_storage
from visiondoctor.storage.base import Storage
from visiondoctor.vlm.describe import describe

log = get_log("fleet")
OPEN_STATES = ("open", "auto_repairing", "awaiting_approval", "dispatched")
IMMEDIATE = {"freeze": 4, "occlusion": 5}  # skip hysteresis for these severities
FIELD_FIX_DELAY_S = 20.0


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class CamRuntime:
    reference: Reference
    state: CameraState = field(default_factory=CameraState)
    profile: repair.CorrectionProfile = field(default_factory=repair.CorrectionProfile)
    last_report: HealthReport | None = None
    last_frames: list[np.ndarray] = field(default_factory=list)
    last_impact: dict[str, Any] | None = None
    unhealthy_streak: int = 0
    pending: dict[str, tuple[repair.RepairStep, HealthReport, float | None]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


class Fleet:
    def __init__(self, sim: FleetSimulator, storage: Storage | None = None, settings: Settings | None = None) -> None:
        self.sim = sim
        self.store = storage or get_storage()
        self.cfg = settings or get_settings()
        self.rt: dict[str, CamRuntime] = {}
        self.runtime_info = cv_runtime.summary()
        self.instance = self.runtime_info["machine"]
        self.on_incident: list[Any] = []  # callbacks(incident_id)

    # ---- setup -----------------------------------------------------------------------
    def ref_path(self, camera_id: str) -> Path:
        return Path(self.cfg.state_dir) / "references" / camera_id

    def bootstrap(self) -> None:
        """Register simulator cameras and learn (or load) their references."""
        for cid, cam in self.sim.cameras.items():
            p = self.ref_path(cid)
            ref = Reference.load(p) if p.with_suffix(".json").exists() else None
            if ref is None:
                frames = self.sim.calibration_frames(cid)
                ref = learn_reference(cid, frames, width=self.cfg.work_width)
                try:
                    ref.detector_baseline = detector_baseline(frames[::10])
                except FileNotFoundError:
                    ref.detector_baseline = {}
                ref.save(p)
                self.store.put_blob(f"references/{cid}.jpg", self._jpeg(ref.buckets["day"].background))
            self.rt[cid] = CamRuntime(ref)
            prof = self.store.get("profiles", cid)
            if prof:
                self.rt[cid].profile = repair.CorrectionProfile(
                    [repair.RepairStep(s["type"], s["params"], s["repair_id"]) for s in prof["steps"]]
                )
            doc = self.store.get("cameras", cid) or {}
            doc.update(
                camera_id=cid,
                name=doc.get("name", f"Camera {cid[-2:]} · {cam.site}"),
                site=cam.site,
                criticality=cam.criticality,
                stream_uri=f"sim://{cam.source}",
                reference_version=ref.version,
                status=doc.get("status", "healthy"),
                lat=doc.get("lat", 40.0 + hash(cid) % 100 / 1000),
                lon=doc.get("lon", -75.0 - hash(cid) % 100 / 1000),
            )
            self.store.put("cameras", cid, doc)

    # ---- frames ----------------------------------------------------------------------
    def burst(self, camera_id: str, n: int = 5) -> list[np.ndarray]:
        """Frames as the downstream AI sees them (raw stream + correction profile)."""
        rt = self.rt[camera_id]
        return [rt.profile.apply(f) for f in self.sim.burst(camera_id, n)]

    @staticmethod
    def _jpeg(img: np.ndarray, quality: int = 85) -> bytes:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else b""

    def _evidence(self, camera_id: str, rep: HealthReport, frame: np.ndarray) -> dict[str, str]:
        safe, _ = blur_faces(frame)
        ts = int(rep.ts * 1000)
        cur_key = self.store.put_blob(f"evidence/{camera_id}/{ts}_current.jpg", self._jpeg(safe))
        hm = heatmap.render(self.rt[camera_id].reference.prepare(safe), rep.heatmap)
        hm_key = self.store.put_blob(f"evidence/{camera_id}/{ts}_heatmap.jpg", self._jpeg(hm))
        self.store.put_blob(f"live/{camera_id}.jpg", self._jpeg(cv2.resize(safe, (320, 180))))
        return {"current": cur_key, "heatmap": hm_key, "reference": f"references/{camera_id}.jpg"}

    # ---- scanning --------------------------------------------------------------------
    def scan_camera(self, camera_id: str, frames: int = 5, impact: bool = True) -> dict[str, Any]:
        rt = self.rt[camera_id]
        with rt.lock:
            burst = self.burst(camera_id, frames)
            rep = scan(camera_id, burst, rt.reference, rt.state)
            rt.last_report, rt.last_frames = rep, burst
            imp = None
            if impact:
                try:
                    imp = predict_impact(rep, burst, rt.reference)
                except FileNotFoundError:
                    imp = None
            rt.last_impact = imp
            faults = rep.faults(self.cfg.incident_min_severity)
            ev_keys = self._evidence(camera_id, rep, burst[-1])
            doc = rep.to_dict() | {
                "faults": [{"type": c.name, "severity": c.severity} for c in faults],
                "predicted_ai_accuracy": imp["predicted_accuracy"] if imp else None,
                "predicted_drop": imp["predicted_drop"] if imp else None,
                "worker_instance": self.instance,
                "is_cool": self.runtime_info["is_cool"],
                "evidence_keys": ev_keys,
            }
            self.store.put("health_reports", camera_id, doc, sk=f"{rep.ts:.3f}")
            emit("ScanLatencyMs", rep.scan_ms, "Milliseconds", is_cool=str(self.runtime_info["is_cool"]).lower())
            incident_id = self._update_status(camera_id, rep, faults, imp)
        return self.report_summary(camera_id) | {"incident_opened": incident_id}

    def _status_for(self, rep: HealthReport) -> str:
        worst = max((c.severity for c in rep.checks.values()), default=0)
        if rep.checks["freeze"].severity >= 4 or rep.checks["occlusion"].severity >= 4:
            return "failed"
        return "healthy" if worst < 2 else "watch" if worst == 2 else "degraded"

    def _update_status(
        self, camera_id: str, rep: HealthReport, faults: list[Any], imp: dict[str, Any] | None
    ) -> str | None:
        rt = self.rt[camera_id]
        cam = self.store.get("cameras", camera_id) or {"camera_id": camera_id}
        open_inc = self.open_incident(camera_id)
        status = self._status_for(rep)
        if rt.pending:
            status = "repairing"
        cam.update(
            status=status,
            last_scan_at=rep.ts,
            overall_score=round(rep.overall_score, 3),
            predicted_ai_accuracy=imp["predicted_accuracy"] if imp else None,
            top_faults=[c.name for c in faults[:3]],
            corrections=[s.type for s in rt.profile.steps],
        )
        self.store.put("cameras", camera_id, cam)
        if not faults:
            rt.unhealthy_streak = 0
            if open_inc and open_inc["state"] == "dispatched":
                self.close_incident(open_inc["incident_id"], "field_fixed")
            return None
        rt.unhealthy_streak += 1
        immediate = any(c.severity >= IMMEDIATE.get(c.name, 9) for c in faults)
        if open_inc or (rt.unhealthy_streak < self.cfg.hysteresis_scans and not immediate):
            return None
        inc_id = _id("inc")
        crit = int(cam.get("criticality", 3))
        drop = float(imp["predicted_drop"]) if imp else 0.15 * max(c.severity for c in faults)
        inc = {
            "incident_id": inc_id,
            "camera_id": camera_id,
            "opened_at": time.time(),
            "fault_types": [c.name for c in faults],
            "severities": {c.name: c.severity for c in faults},
            "priority_score": round(drop * crit, 3),
            "predicted_drop": round(drop, 3),
            "criticality": crit,
            "state": "open",
            "repairs": [],
            "vlm_description": None,
            "evidence_keys": list(self.store.query("health_reports", camera_id, limit=1)[0]["evidence_keys"].values()),
            "approved_by": None,
            "trace_id": None,
            "site": cam.get("site"),
        }
        self.store.put("incidents", inc_id, inc, sk=f"{inc['opened_at']:.3f}")
        emit("IncidentsOpened", 1, "Count")
        log.info("incident_opened", incident_id=inc_id, camera_id=camera_id, faults=inc["fault_types"])
        for cb in self.on_incident:
            cb(inc_id)
        return inc_id

    def report_summary(self, camera_id: str) -> dict[str, Any]:
        rt = self.rt[camera_id]
        rep = rt.last_report
        if rep is None:
            return {"camera_id": camera_id, "error": "not scanned yet"}
        key_ev = {}
        for c in rep.faults(1):
            ev = c.to_dict()["evidence"]
            key_ev[c.name] = {k: v for k, v in ev.items() if k != "H" and not isinstance(v, list | dict)}
        return {
            "camera_id": camera_id,
            "overall_score": round(rep.overall_score, 3),
            "severities": {k: v.severity for k, v in rep.checks.items()},
            "faults": [{"type": c.name, "severity": c.severity} for c in rep.faults(self.cfg.incident_min_severity)],
            "key_evidence": key_ev,
            "reference_bucket": rep.reference_bucket,
            "scan_ms": round(rep.scan_ms, 1),
            "predicted_ai_accuracy": rt.last_impact["predicted_accuracy"] if rt.last_impact else None,
            "is_cool": self.runtime_info["is_cool"],
        }

    # ---- diagnosis & impact ------------------------------------------------------------
    def _ensure_report(self, camera_id: str) -> HealthReport:
        rt = self.rt[camera_id]
        if rt.last_report is None:
            self.scan_camera(camera_id)
        assert rt.last_report is not None
        return rt.last_report

    def diagnose(self, camera_id: str) -> dict[str, Any]:
        rep = self._ensure_report(camera_id)
        w, h = rep.heatmap.shape[1], rep.heatmap.shape[0]
        ref = self.rt[camera_id].reference
        faults, fixable = [], []
        for c in rep.faults(self.cfg.incident_min_severity):
            bbox = None
            if c.evidence.get("bboxes"):
                bbox = c.evidence["bboxes"][0]
            elif c.region_mask is not None and c.region_mask.any():
                ys, xs = np.nonzero(c.region_mask)
                tw, th = ref.width / w, ref.height / h
                bbox = [int(xs.min() * tw), int(ys.min() * th), int((xs.ptp() + 1) * tw), int((ys.ptp() + 1) * th)]
            faults.append({"type": c.name, "severity": c.severity, "region_bbox": bbox, "confidence": round(c.severity / 5, 2)})
            if c.name in SOFTWARE_FIXABLE:
                step = repair.plan(c.name, rep, ref)
                if step is not None and step.type != "white_balance":
                    ok, why = repair.check_bounds(step.type, step.params, self.cfg)
                else:
                    ok, why = step is not None, "ok"
                fixable.append({"type": c.name, "repair": repair.REPAIR_FOR_FAULT[c.name], "within_bounds": ok, "reason": why})
        return {"camera_id": camera_id, "faults": faults, "fixable": fixable, "likely_cause": self._likely_cause(camera_id, faults)}

    def _likely_cause(self, camera_id: str, faults: list[dict[str, Any]]) -> str:
        if not faults:
            return "no fault: camera healthy"
        top = faults[0]["type"]
        if top == "haze":
            site = self.sim.cameras[camera_id].site
            peers = [c for c, m in self.sim.cameras.items() if m.site == site and c != camera_id]
            hazy = sum(1 for p in peers if (r := self.rt[p].last_report) and r.checks["haze"].severity >= 2)
            if peers and hazy / len(peers) >= 0.5:
                return f"site-wide weather: haze on {hazy}/{len(peers)} other cameras at {site}"
            return "condensation or fog inside this camera's dome (other cameras at the site are clear)"
        return {
            "drift": "camera mount or PTZ preset moved",
            "vibration": "unstable mount or vibration source",
            "glare": "light source shining into the lens",
            "exposure": "iris/gain misconfiguration or lighting change",
            "occlusion": "object or covering blocking the lens",
            "smudge": "dirt, smear or spider web on the lens",
            "color_cast": "white-balance drift or stuck IR-cut filter",
            "noise": "low light or sensor degradation",
            "sharpness": "lens out of focus",
            "freeze": "stream frozen / encoder, network or power failure",
        }.get(top, top)

    def predict_ai_impact(self, camera_id: str) -> dict[str, Any]:
        rep = self._ensure_report(camera_id)
        rt = self.rt[camera_id]
        if rt.last_impact is None:
            rt.last_impact = predict_impact(rep, rt.last_frames, rt.reference)
        base = rt.reference.detector_baseline
        return rt.last_impact | {"camera_id": camera_id, "clean_detections_per_frame": round(base.get("count", 0), 1)}

    def reference_comparison(self, camera_id: str) -> dict[str, Any]:
        hr = self.store.query("health_reports", camera_id, limit=1)
        keys = hr[0]["evidence_keys"] if hr else {"reference": f"references/{camera_id}.jpg"}
        return {k: self.store.blob_url(v) for k, v in keys.items()}

    # ---- repairs ---------------------------------------------------------------------
    def apply_repair(self, camera_id: str, repair_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        rt = self.rt[camera_id]
        with rt.lock:
            rep = self._ensure_report(camera_id)
            fault = repair.FAULT_FOR_REPAIR[repair_type]
            step = repair.plan(fault, rep, rt.reference)
            if step is None:
                return {"applied": False, "error": f"no {fault} evidence to plan {repair_type}"}
            if params:
                step.params.update({k: v for k, v in params.items() if k not in ("H",)})
            step = repair.finalize(step, rt.last_frames[-1])
            ok, why = repair.check_bounds(step.type, step.params, self.cfg)
            if not ok:
                return {"applied": False, "error": "out_of_bounds", "reason": why}
            acc_before = rt.last_impact["predicted_accuracy"] if rt.last_impact else None
            rt.pending[step.repair_id] = (step, rep, acc_before)
            before = {"severity": rep.checks[fault].severity, "overall": round(rep.overall_score, 3), "predicted_accuracy": acc_before}
            self._incident_log(camera_id, {"repair_id": step.repair_id, "type": step.type, "params": _compact(step.params),
                                           "before": before, "verified": None})
            return {"repair_id": step.repair_id, "applied": True, "repair": step.type,
                    "params": _compact(step.params), "before_metrics": before}

    def verify_repair(self, camera_id: str, repair_id: str) -> dict[str, Any]:
        rt = self.rt[camera_id]
        with rt.lock:
            if repair_id not in rt.pending:
                return {"error": f"unknown or already verified repair {repair_id}"}
            step, before, acc_b = rt.pending[repair_id]
            trial = repair.CorrectionProfile(rt.profile.steps + [step])
            raw = self.sim.burst(camera_id, 5)
            base = [rt.profile.apply(f) for f in raw]

            def impact_fn(r: HealthReport, frames: list[np.ndarray]) -> float:
                return float(predict_impact(r, frames, rt.reference)["predicted_accuracy"])

            try:
                res = verify(camera_id, step.type, repair.CorrectionProfile([step]), base, rt.reference, before,
                             impact=impact_fn, acc_before=acc_b)
            except FileNotFoundError:
                res = verify(camera_id, step.type, repair.CorrectionProfile([step]), base, rt.reference, before)
            out = res.to_dict() | {"repair_id": repair_id}
            if res.recovered:
                rt.profile = trial
                self.store.put("profiles", camera_id, {"steps": rt.profile.to_list()})
                del rt.pending[repair_id]
                emit("AutoFixed", 1, "Count")
            else:
                out["note"] = "not recovered: call rollback_repair and escalate"
            self._incident_log(camera_id, {"repair_id": repair_id, "verified": res.recovered, "after": {
                "severity": res.severity_after, "predicted_accuracy": res.acc_after}}, update=True)
            emit("RepairVerifiedRate", 1.0 if res.recovered else 0.0, "None")
            return out

    def rollback_repair(self, camera_id: str, repair_id: str) -> dict[str, Any]:
        rt = self.rt[camera_id]
        with rt.lock:
            rt.pending.pop(repair_id, None)
            rt.profile = rt.profile.without(repair_id)
            self.store.put("profiles", camera_id, {"steps": rt.profile.to_list()})
            self._incident_log(camera_id, {"repair_id": repair_id, "rolled_back": True}, update=True)
        return {"rolled_back": True, "repair_id": repair_id, "active_corrections": [s.type for s in rt.profile.steps]}

    def _incident_log(self, camera_id: str, entry: dict[str, Any], update: bool = False) -> None:
        inc = self.open_incident(camera_id)
        if not inc:
            return
        reps = inc.setdefault("repairs", [])
        if update:
            for r in reps:
                if r.get("repair_id") == entry.get("repair_id"):
                    r.update(entry)
                    break
        else:
            reps.append(entry)
            inc["state"] = "auto_repairing"
        self._save_incident(inc)

    # ---- escalation ------------------------------------------------------------------
    def describe_fault(self, camera_id: str, region_bbox: list[int] | None = None) -> dict[str, Any]:
        rep = self._ensure_report(camera_id)
        rt = self.rt[camera_id]
        faults = rep.faults(self.cfg.incident_min_severity) or rep.faults(1)
        if not faults:
            return {"caption": "No visible fault.", "model": "rule-based"}
        top = faults[0]
        frame = rt.reference.prepare(rt.last_frames[-1])
        safe, _ = blur_faces(frame)
        bbox = region_bbox or (top.evidence.get("bboxes") or [None])[0]
        d = describe(top.name, top.to_dict()["evidence"], safe, bbox)
        inc = self.open_incident(camera_id)
        if inc:
            inc["vlm_description"] = d["caption"]
            if bbox:
                x, y, w, h = bbox
                crop = safe[y : y + h, x : x + w]
                if crop.size:
                    key = self.store.put_blob(f"evidence/{camera_id}/{int(time.time() * 1000)}_crop.jpg", self._jpeg(crop))
                    inc.setdefault("evidence_keys", []).append(key)
            self._save_incident(inc)
        return d | {"fault": top.name, "region_bbox": bbox}

    def request_human_approval(self, incident_id: str, action: str, reason: str, evidence_keys: list[str] | None = None) -> dict[str, Any]:
        inc = self.get_incident(incident_id)
        if inc is None:
            return {"error": "unknown incident"}
        aid = _id("apr")
        doc = {"approval_id": aid, "incident_id": incident_id, "camera_id": inc["camera_id"], "action": action,
               "reason": reason, "evidence_keys": evidence_keys or inc.get("evidence_keys", []), "state": "pending",
               "requested_at": time.time(), "decided_by": None}
        self.store.put("approvals", aid, doc)
        inc["state"] = "awaiting_approval"
        inc["approval_id"] = aid
        self._save_incident(inc)
        self._notify(f"VisionDoctor approval needed: {action} for {inc['camera_id']}", reason)
        emit("Escalated", 1, "Count")
        return {"approval_id": aid, "state": "pending"}

    def decide(self, approval_id: str, approve: bool, user: str) -> dict[str, Any]:
        ap = self.store.get("approvals", approval_id)
        if ap is None:
            return {"error": "unknown approval"}
        if ap["state"] != "pending":
            return {"error": f"already {ap['state']}"}
        ap.update(state="approved" if approve else "rejected", decided_by=user, decided_at=time.time())
        self.store.put("approvals", approval_id, ap)
        inc = self.get_incident(ap["incident_id"])
        if inc is None:
            return ap
        inc["approved_by"] = user
        if not approve:
            inc["state"] = "open"
            self._save_incident(inc)
            self.set_watch(inc["camera_id"], 60)
            return ap
        if ap["action"] == "ptz_rehome":
            self.sim.resolve(inc["camera_id"], {"drift"})
            rt = self.rt[inc["camera_id"]]
            rt.profile = repair.CorrectionProfile([s for s in rt.profile.steps if s.type != "realign"])
            self.store.put("profiles", inc["camera_id"], {"steps": rt.profile.to_list()})
            inc["state"] = "dispatched"
            self._save_incident(inc)
        else:
            t = self.create_maintenance_ticket(inc["incident_id"], ",".join(inc["fault_types"]),
                                               inc.get("vlm_description") or "inspect camera")
            ap["ticket_id"] = t.get("ticket_id")
            self.store.put("approvals", approval_id, ap)
        return ap

    def create_maintenance_ticket(self, incident_id: str, fault_type: str, instructions: str) -> dict[str, Any]:
        inc = self.get_incident(incident_id)
        if inc is None:
            return {"error": "unknown incident"}
        ap = self.store.get("approvals", inc.get("approval_id", "")) if inc.get("approval_id") else None
        if not ap or ap["state"] != "approved":
            return {"error": "approval required before a ticket can be created"}
        tid = _id("tkt")
        self.store.put("tickets", tid, {"ticket_id": tid, "incident_id": incident_id, "camera_id": inc["camera_id"],
                                        "fault_type": fault_type, "instructions": instructions, "created_at": time.time(),
                                        "state": "dispatched"})
        inc["state"] = "dispatched"
        inc["ticket_id"] = tid
        self._save_incident(inc)
        self._notify(f"VisionDoctor ticket {tid}", f"{inc['camera_id']}: {fault_type}. {instructions}")
        # Simulated field visit: the technician fixes the physical fault after a delay.
        cam = inc["camera_id"]
        delay = FIELD_FIX_DELAY_S / max(self.sim.speed, 1e-6)
        threading.Timer(delay, lambda: self.sim.resolve(cam)).start()
        return {"ticket_id": tid}

    def _notify(self, subject: str, message: str) -> None:
        if self.cfg.backend == "aws" and self.cfg.sns_topic_arn:
            import boto3

            boto3.client("sns", region_name=self.cfg.aws_region).publish(
                TopicArn=self.cfg.sns_topic_arn, Subject=subject[:99], Message=message
            )
        log.info("notify", subject=subject, message=message)

    def set_watch(self, camera_id: str, scan_interval_s: int) -> dict[str, Any]:
        cam = self.store.get("cameras", camera_id) or {"camera_id": camera_id}
        cam["watch_interval_s"] = int(scan_interval_s)
        self.store.put("cameras", camera_id, cam)
        return {"ok": True, "camera_id": camera_id, "scan_interval_s": int(scan_interval_s)}

    # ---- incidents ---------------------------------------------------------------------
    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        for d in self.store.query("incidents", incident_id, limit=1):
            return d
        return None

    def _save_incident(self, inc: dict[str, Any]) -> None:
        self.store.put("incidents", inc["incident_id"], inc, sk=f"{inc['opened_at']:.3f}")

    def open_incident(self, camera_id: str) -> dict[str, Any] | None:
        for inc in self.store.query("incidents", limit=500):
            if inc["camera_id"] == camera_id and inc["state"] in OPEN_STATES:
                return inc
        return None

    def close_incident(self, incident_id: str, resolution: str) -> dict[str, Any]:
        inc = self.get_incident(incident_id)
        if inc is None:
            return {"error": "unknown incident"}
        state = {"transient": "false_alarm", "false_alarm": "false_alarm", "auto_fixed": "repaired"}.get(resolution, "closed")
        inc.update(state=state, resolution=resolution, closed_at=time.time())
        self._save_incident(inc)
        if state == "false_alarm":
            emit("FalseAlarm", 1, "Count")
        self.rt[inc["camera_id"]].unhealthy_streak = 0
        return {"ok": True, "incident_id": incident_id, "state": state}

    def list_unhealthy(self, min_severity: int = 2) -> list[dict[str, Any]]:
        out = []
        for cid, rt in self.rt.items():
            r = rt.last_report
            if r is None:
                continue
            f = r.faults(min_severity)
            if f:
                inc = self.open_incident(cid)
                out.append({"camera_id": cid, "status": self._status_for(r), "top_faults": [c.name for c in f[:3]],
                            "priority": inc["priority_score"] if inc else None, "incident_id": inc["incident_id"] if inc else None})
        return sorted(out, key=lambda d: -(d["priority"] or 0))


def _compact(params: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in params.items():
        if k == "H":
            out[k] = [[round(float(x), 4) for x in row] for row in v]
        elif isinstance(v, float):
            out[k] = round(v, 4)
        elif isinstance(v, list) and v and isinstance(v[0], float):
            out[k] = [round(x, 4) for x in v]
        else:
            out[k] = v
    return out
