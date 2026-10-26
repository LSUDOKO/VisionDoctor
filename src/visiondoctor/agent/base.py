"""Shared act() step: guard → MCP tool call → observe → trace."""

from __future__ import annotations

import time
from typing import Any

from visiondoctor.agent.guard import Guard
from visiondoctor.agent.tools import ToolClient
from visiondoctor.agent.trace import Trace
from visiondoctor.observability.metrics import emit


class AgentRun:
    def __init__(self, tools: ToolClient, guard: Guard, trace: Trace) -> None:
        self.tools, self.guard, self.trace = tools, guard, trace

    async def act(self, tool: str, args: dict[str, Any], reason: str, changed_plan: bool = False) -> dict[str, Any]:
        t0 = time.perf_counter()
        v = self.guard.check(tool, args)
        if not v.allowed:
            out = v.block()
            emit("GuardBlocks", 1, "Count")
            self.trace.add(tool, args, out, reason, (time.perf_counter() - t0) * 1000, f"blocked: {v.reason}", changed_plan)
            return out
        out = await self.tools.call(tool, args)
        self.guard.observe(tool, out)
        self.trace.add(tool, args, out, reason, (time.perf_counter() - t0) * 1000, "allowed", changed_plan)
        return out
