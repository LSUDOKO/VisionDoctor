"""Fleet monitor: periodic scans of every camera, agent runs on new incidents.

Locally this runs inside the API process (``make demo``); on AWS the same loop runs as the
COOL worker service fed by EventBridge/SQS scan jobs.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from visiondoctor.agent.loop import AgentRunner
from visiondoctor.fleet import Fleet
from visiondoctor.observability.logging import get as get_log
from visiondoctor.observability.metrics import emit

log = get_log("service")


class FleetService:
    def __init__(self, fleet: Fleet, scan_interval_s: float = 15.0, agent: str | None = None) -> None:
        self.fleet = fleet
        self.interval = scan_interval_s
        self.runner = AgentRunner(fleet, agent=agent)
        self.agents = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent")
        self._stop = threading.Event()
        self._next: dict[str, float] = {}
        self._last_cw = 0.0
        self.thread = threading.Thread(target=self._loop, name="fleet-monitor", daemon=True)
        fleet.on_incident.append(self._enqueue)

    def _enqueue(self, incident_id: str) -> None:
        self.agents.submit(self.runner.handle_sync, incident_id)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _due(self, cid: str, now: float) -> bool:
        cam = self.fleet.store.get("cameras", cid) or {}
        interval = min(self.interval, float(cam.get("watch_interval_s") or self.interval))
        if now >= self._next.get(cid, 0):
            self._next[cid] = now + interval
            return True
        return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            for cid in list(self.fleet.rt):
                if self._stop.is_set():
                    return
                if self._due(cid, now):
                    try:
                        self.fleet.scan_camera(cid)
                    except Exception as e:  # noqa: BLE001 - one camera must not stop the fleet
                        log.error("scan_failed", camera_id=cid, error=str(e))
            self._fleet_metrics()
            self._stop.wait(1.0)

    def _fleet_metrics(self) -> None:
        cams = self.fleet.store.query("cameras")
        for st in ("healthy", "watch", "degraded", "failed"):
            emit(f"Cameras{st.capitalize()}", sum(1 for c in cams if c.get("status") == st), "Count")
        accs = [c["predicted_ai_accuracy"] for c in cams if c.get("predicted_ai_accuracy") is not None]
        if accs:
            emit("PredictedFleetAccuracy", sum(accs) / len(accs), "None")
        if self.fleet.cfg.backend == "aws" and time.time() - self._last_cw > 60:
            self._last_cw = time.time()
            self._put_cloudwatch(cams, accs)

    def _put_cloudwatch(self, cams: list[dict], accs: list[float]) -> None:  # type: ignore[type-arg]
        """Direct PutMetricData (lean deploy has no CloudWatch agent to collect EMF)."""
        import boto3

        data = [{"MetricName": f"Cameras{st.capitalize()}", "Value": float(sum(c.get("status") == st for c in cams))}
                for st in ("healthy", "watch", "degraded", "failed")]
        if accs:
            data.append({"MetricName": "PredictedFleetAccuracy", "Value": sum(accs) / len(accs)})
        try:
            boto3.client("cloudwatch", region_name=self.fleet.cfg.aws_region).put_metric_data(
                Namespace="VisionDoctor", MetricData=data)
        except Exception as e:  # noqa: BLE001 - metrics must never stop the monitor
            log.warning("cloudwatch_put_failed", error=str(e)[:200])
