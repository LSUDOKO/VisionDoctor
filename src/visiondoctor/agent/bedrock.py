"""LLM agent on Amazon Bedrock (Converse API with tool use), tools generated from MCP list_tools.

docs/04 §3.2. The model id is never hard-coded: VD_BEDROCK_MODEL_ID, else SSM parameter
/visiondoctor/bedrock_model_id, else the newest active Claude Sonnet inference profile.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any

import boto3

from visiondoctor.agent.base import AgentRun
from visiondoctor.agent.prompts import SYSTEM
from visiondoctor.config import get_settings
from visiondoctor.observability.metrics import emit

PREFERENCE = ("sonnet-5-5", "sonnet-5", "sonnet-4-6", "sonnet-4-5")


@lru_cache(maxsize=1)
def resolve_model_id() -> str:
    s = get_settings()
    if s.bedrock_model_id:
        return s.bedrock_model_id
    try:
        p = boto3.client("ssm", region_name=s.aws_region).get_parameter(Name=s.bedrock_model_ssm_param)
        return str(p["Parameter"]["Value"])
    except Exception:  # noqa: BLE001 - parameter is optional in local mode
        pass
    br = boto3.client("bedrock", region_name=s.aws_region)
    ids = [p["inferenceProfileId"] for p in br.list_inference_profiles()["inferenceProfileSummaries"]
           if p.get("status") == "ACTIVE" and "anthropic" in p["inferenceProfileId"]]
    prefix = s.aws_region.split("-")[0] + "."
    for pref in PREFERENCE:
        for i in ids:
            if i.startswith(prefix) and i.endswith(pref):
                return i
    raise RuntimeError("no Claude Sonnet inference profile available; set VD_BEDROCK_MODEL_ID")


def tool_config(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"][:500],
                                     "inputSchema": {"json": t["input_schema"]}}} for t in specs]}


async def run(r: AgentRun, camera_id: str, incident_id: str, criticality: int = 3) -> str:
    s = get_settings()
    model = resolve_model_id()
    r.trace.model = model
    client = boto3.client("bedrock-runtime", region_name=s.aws_region)
    cfg = tool_config(await r.tools.specs())
    system = [{"text": SYSTEM.format(p_dispatch=s.p_dispatch, incident_id=incident_id, camera_id=camera_id,
                                     criticality=criticality)}]
    messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": f"Incident {incident_id} opened on {camera_id}. Handle it."}]}]
    outcome = "unfinished"
    for _ in range(s.max_agent_steps):
        resp = await asyncio.to_thread(
            client.converse, modelId=model, system=system, messages=messages, toolConfig=cfg,
            inferenceConfig={"maxTokens": 1024, "temperature": 0},
        )
        u = resp.get("usage", {})
        r.trace.tokens_in += int(u.get("inputTokens", 0))
        r.trace.tokens_out += int(u.get("outputTokens", 0))
        r.guard.tokens = r.trace.tokens_in + r.trace.tokens_out
        msg = resp["output"]["message"]
        messages.append(msg)
        if resp.get("stopReason") != "tool_use":
            break
        texts = " ".join(c["text"] for c in msg["content"] if "text" in c).strip()
        results = []
        for c in msg["content"]:
            if "toolUse" not in c:
                continue
            tu = c["toolUse"]
            out = await r.act(tu["name"], dict(tu.get("input") or {}), texts[:300] or f"model chose {tu['name']}")
            outcome = _outcome(tu["name"], tu.get("input") or {}, out, outcome)
            results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": out}],
                                           "status": "error" if "error" in out else "success"}})
        messages.append({"role": "user", "content": results})
        if r.guard.tokens > s.max_agent_tokens:
            outcome = outcome if outcome != "unfinished" else "budget_exhausted"
            break
    emit("AgentTokens", r.trace.tokens_in + r.trace.tokens_out, "Count")
    return outcome


def _outcome(tool: str, args: dict[str, Any], out: dict[str, Any], prev: str) -> str:
    if "error" in out:
        return prev
    if tool == "close_incident":
        res = args.get("resolution")
        return {"auto_fixed": "auto_fixed", "transient": "closed_transient", "watch": "watch"}.get(str(res), str(res))
    if tool == "request_human_approval":
        return "approval_requested"
    return prev


def _json(x: Any) -> str:
    return json.dumps(x, default=str)
