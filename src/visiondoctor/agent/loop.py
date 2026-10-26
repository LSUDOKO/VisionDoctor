"""Run an agent on an incident and persist its trace (docs/04 §3)."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any

from visiondoctor.agent import bedrock, policy
from visiondoctor.agent.base import AgentRun
from visiondoctor.agent.guard import Guard
from visiondoctor.agent.tools import InProcessTools, ToolClient
from visiondoctor.agent.trace import Trace
from visiondoctor.config import get_settings
from visiondoctor.fleet import Fleet
from visiondoctor.observability.logging import get as get_log
from visiondoctor.observability.metrics import emit

log = get_log("agent")
RATE_LIMIT_PER_MIN = 10


class AgentRunner:
    def __init__(self, fleet: Fleet, tools: ToolClient | None = None, agent: str | None = None) -> None:
        from visiondoctor.mcp_server.server import build_server

        self.fleet = fleet
        self.tools = tools or InProcessTools(build_server(fleet))
        self.agent = agent or get_settings().agent
        self._recent: deque[float] = deque()
        self._lock = threading.Lock()

    def _rate_ok(self) -> bool:
        now = time.time()
        with self._lock:
            while self._recent and now - self._recent[0] > 60:
                self._recent.popleft()
            if len(self._recent) >= RATE_LIMIT_PER_MIN:
                return False
            self._recent.append(now)
            return True

    async def handle(self, incident_id: str, agent: str | None = None) -> dict[str, Any]:
        inc = self.fleet.get_incident(incident_id)
        if inc is None or inc["state"] != "open":
            return {"skipped": True, "reason": "incident not open"}
        if not self._rate_ok():
            return {"skipped": True, "reason": "fleet rate limit (10 incidents/min)"}
        kind = agent or self.agent
        cam = inc["camera_id"]
        trace = Trace(incident_id, cam, kind)
        guard = Guard(cam, incident_id)
        run = AgentRun(self.tools, guard, trace)
        try:
            if kind == "bedrock":
                try:
                    outcome = await bedrock.run(run, cam, incident_id, int(inc.get("criticality", 3)))
                except Exception as e:  # noqa: BLE001
                    if trace.steps:
                        raise
                    # LLM unavailable (access, quota, network) before acting: the deterministic
                    # policy agent takes over with the same tools, guard and trace format.
                    log.warning("bedrock_unavailable", error=str(e)[:200])
                    trace.agent = "policy (bedrock unavailable)"
                    trace.model = f"{trace.model} unavailable: {type(e).__name__}"
                    outcome = await policy.run(run, cam, incident_id)
            else:
                outcome = await policy.run(run, cam, incident_id)
        except Exception as e:  # noqa: BLE001 - the incident must not be lost on agent failure
            log.error("agent_failed", incident_id=incident_id, error=str(e))
            outcome = f"agent_error: {type(e).__name__}"
        trace.finish(outcome)
        doc = trace.to_dict()
        self.fleet.store.put("traces", trace.trace_id, doc)
        inc = self.fleet.get_incident(incident_id) or inc
        inc["trace_id"] = trace.trace_id
        inc.setdefault("trace_ids", []).append(trace.trace_id)
        self.fleet._save_incident(inc)
        emit("AgentSteps", len(trace.steps), "Count")
        log.info("agent_done", incident_id=incident_id, outcome=outcome, steps=len(trace.steps))
        return doc

    def handle_sync(self, incident_id: str, agent: str | None = None) -> dict[str, Any]:
        return asyncio.run(self.handle(incident_id, agent))
