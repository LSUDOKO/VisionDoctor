"""FleetSimulator: N virtual cameras streamed from video files with scheduled fault injection.

docs/06 §2. Cameras share decoded frame buffers (sampled at ``fps``) with different time
offsets. A YAML scenario schedules faults; every onset/offset goes to a ground-truth log.
Physical faults clear when a technician ticket completes (``resolve``), mimicking a field fix.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from visiondoctor.sim import sources
from visiondoctor.sim.faults import Fault
from visiondoctor.sim.synthetic import SyntheticScene

SCENARIO_DIR = Path(__file__).parent / "scenarios"
SITES = ["north-gate", "plaza", "depot"]


@dataclass
class ActiveFault:
    fault: Fault
    start: float
    end: float | None
    event_id: str


@dataclass
class SimCamera:
    camera_id: str
    source: str
    offset: float
    flip: bool
    site: str
    criticality: int
    faults: list[ActiveFault] = field(default_factory=list)


class FleetSimulator:
    def __init__(
        self,
        cameras: int = 12,
        fps: float = 2.0,
        width: int = 640,
        seed: int = 7,
        sources_list: list[str] | None = None,
        truth_path: Path | None = None,
        speed: float = 1.0,
        max_frames: int = 90,
    ) -> None:
        self.fps, self.width, self.speed = fps, width, speed
        self.rng = np.random.default_rng(seed)
        # MOT17-02 (dense crowd at dusk) gives too few static keypoints for drift at 640 px;
        # it stays in the offline evaluation as a documented failure case.
        names = sources_list or [n for n in sources.available() if n != "MOT17-02"] or ["synthetic"]
        self.buffers: dict[str, list[np.ndarray]] = {n: self._load(n, max_frames) for n in names}
        self.cameras: dict[str, SimCamera] = {}
        for i in range(cameras):
            src = names[i % len(names)]
            cid = f"cam-{i + 1:02d}"
            self.cameras[cid] = SimCamera(
                cid,
                src,
                offset=float(self.rng.uniform(0, len(self.buffers[src]) / fps)),
                flip=bool((i // len(names)) % 2),
                site=SITES[i % len(SITES)],
                criticality=int(self.rng.integers(1, 6)),
            )
        self.t0 = time.time()
        self.events: list[dict[str, Any]] = []
        self.truth_path = truth_path
        self._lock = threading.Lock()

    # ---- sources ---------------------------------------------------------------------
    def _load(self, name: str, max_frames: int) -> list[np.ndarray]:
        if name == "synthetic" or not sources.video_path(name).exists():
            return SyntheticScene(self.width, int(self.width * 9 / 16), seed=3).frames(max_frames)
        n = sources.frame_count(name)
        native_fps = 30.0 if name.startswith("MOT17") else 10.0
        step = max(1, round(native_fps / self.fps))
        idx = list(range(0, n, step))[:max_frames]
        frames = sources.read_frames(name, idx)
        out = []
        for i in idx:
            f = frames[i]
            h, w = f.shape[:2]
            out.append(cv2.resize(f, (self.width, round(h * self.width / w)), interpolation=cv2.INTER_AREA))
        return out

    # ---- time ------------------------------------------------------------------------
    def now(self) -> float:
        """Simulation seconds since start."""
        return (time.time() - self.t0) * self.speed

    def clean_frame(self, camera_id: str, t: float | None = None) -> np.ndarray:
        cam = self.cameras[camera_id]
        buf = self.buffers[cam.source]
        t = self.now() if t is None else t
        f = buf[int((cam.offset + t) * self.fps) % len(buf)]
        return f[:, ::-1].copy() if cam.flip else f

    def frame(self, camera_id: str, t: float | None = None) -> np.ndarray:
        t = self.now() if t is None else t
        f = self.clean_frame(camera_id, t)
        with self._lock:
            active = [a for a in self.cameras[camera_id].faults if a.start <= t and (a.end is None or t < a.end)]
        for a in active:
            f = a.fault.apply(f)
        return f

    def burst(self, camera_id: str, n: int = 5, dt: float | None = None) -> list[np.ndarray]:
        """``n`` frames ending now, spaced ``dt`` sim-seconds apart (oldest first)."""
        dt = dt or 1.0 / self.fps
        t = self.now()
        return [self.frame(camera_id, t - (n - 1 - k) * dt) for k in range(n)]

    def calibration_frames(self, camera_id: str, n: int = 60) -> list[np.ndarray]:
        """Clean frames spanning the camera's whole loop (stands in for a 10-min window)."""
        loop = len(self.buffers[self.cameras[camera_id].source]) / self.fps
        return [self.clean_frame(camera_id, k * loop / n) for k in range(n)]

    # ---- faults ----------------------------------------------------------------------
    def inject(
        self, camera_id: str, fault: str, severity: int, duration_s: float | None = None, at: float | None = None, **params: float
    ) -> str:
        t = self.now() if at is None else at
        eid = f"ev{len(self.events) + 1:03d}"
        af = ActiveFault(Fault(fault, severity, seed=len(self.events) + 11, params=dict(params)), t,
                         None if duration_s is None else t + duration_s, eid)
        with self._lock:
            self.cameras[camera_id].faults.append(af)
        self._log({"event": "onset", "id": eid, "t": t, "camera": camera_id, "fault": fault, "severity": severity,
                   "duration_s": duration_s})
        return eid

    def resolve(self, camera_id: str, faults: set[str] | None = None) -> list[str]:
        """Field fix: clear (matching) active faults on a camera."""
        t = self.now()
        cleared = []
        with self._lock:
            for a in self.cameras[camera_id].faults:
                if (a.end is None or a.end > t) and (faults is None or a.fault.name in faults):
                    a.end = t
                    cleared.append(a.fault.name)
                    self._log({"event": "resolved", "id": a.event_id, "t": t, "camera": camera_id, "fault": a.fault.name})
        return cleared

    def active_faults(self, camera_id: str) -> list[dict[str, Any]]:
        t = self.now()
        return [
            {"fault": a.fault.name, "severity": a.fault.severity, "since": a.start, "event_id": a.event_id}
            for a in self.cameras[camera_id].faults
            if a.start <= t and (a.end is None or t < a.end)
        ]

    def run_scenario(self, path_or_name: str | Path) -> dict[str, Any]:
        p = Path(path_or_name)
        if not p.exists():
            p = SCENARIO_DIR / f"{path_or_name}.yaml"
        sc = yaml.safe_load(p.read_text())
        base = self.now()
        for ev in sc.get("events", []):
            if ev["camera"] in self.cameras:
                params = {k: v for k, v in ev.items() if k not in ("t", "camera", "fault", "severity", "duration_s")}
                self.inject(ev["camera"], ev["fault"], int(ev["severity"]), ev.get("duration_s"), at=base + ev["t"], **params)
        return {"scenario": p.stem, "events": len(sc.get("events", [])), "starts_at": base}

    def _log(self, rec: dict[str, Any]) -> None:
        self.events.append(rec)
        if self.truth_path:
            self.truth_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.truth_path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
