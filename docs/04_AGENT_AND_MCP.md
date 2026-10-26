# 04 — Agent and MCP Tool Server (Agentic Vision Award)

Competition rule we must satisfy: *image or video results must influence a subsequent plan, tool
call, action, or request for human approval.* Our traces prove it step by step.

## 1. Design principles
- **OpenCV tools do the seeing; the agent decides; the guard enforces.** The LLM never touches
  pixels or AWS directly — only MCP tools with typed, bounded inputs.
- **Two interchangeable agents** with identical tools and trace format:
  `PolicyAgent` (deterministic, reproducible, no LLM) and `BedrockAgent` (LLM reasoning for
  ambiguous multi-fault cases). The report compares them (docs/06 §5).
- **Human control**: anything physical or irreversible requires approval.

## 2. MCP tools (`mcp_server/server.py`)
Built with the official MCP Python SDK (`from mcp.server.fastmcp import FastMCP` — **VERIFY**).
Serve via stdio (local dev, Claude Desktop/Claude Code testing) and streamable HTTP (production,
inside the VPC only, behind a shared-secret header from Secrets Manager).

| Tool | Input (pydantic) | Output | Notes |
|---|---|---|---|
| `list_unhealthy_cameras` | `{min_severity:int=2}` | `[{camera_id, status, top_faults, priority}]` | from storage |
| `scan_camera` | `{camera_id, frames:int=5}` | `HealthReport` summary (scores, severities, key evidence) | runs §3 checks on COOL worker |
| `diagnose` | `{camera_id}` | `{faults:[{type, severity, region_bbox, confidence}], fixable:[...], likely_cause}` | rule-based fusion of checks |
| `predict_ai_impact` | `{camera_id}` | `{predicted_accuracy, predicted_drop, ci90, features_top3}` | docs/03 §6 |
| `get_reference_comparison` | `{camera_id}` | presigned URLs: reference, current, heat map (face-blurred) | for UI + LLM image input |
| `apply_repair` | `{camera_id, repair: enum, params}` | `{repair_id, applied, before_metrics}` | guard-checked bounds |
| `verify_repair` | `{camera_id, repair_id}` | `{recovered:bool, after_metrics, impact_after}` | re-scan + re-predict |
| `rollback_repair` | `{camera_id, repair_id}` | `{rolled_back:true}` | |
| `describe_fault` | `{camera_id, region_bbox}` | `{caption, model:"paligemma2-3b (OpenCV 5 DNN)", latency_ms}` | VLM, escalations only |
| `request_human_approval` | `{incident_id, action:"dispatch_technician"|"ptz_rehome", reason, evidence_keys}` | `{approval_id, state:"pending"}` | SNS + dashboard |
| `create_maintenance_ticket` | `{incident_id, fault_type, instructions}` | `{ticket_id}` | only after approval; stub + SNS (optional Jira/ServiceNow via webhook) |
| `set_watch` | `{camera_id, scan_interval_s}` | `{ok}` | rescan more often |
| `close_incident` | `{incident_id, resolution}` | `{ok}` | |

Every tool: validates input, enforces timeouts (scan 10 s, VLM 60 s), emits metrics, returns
compact JSON (≤ 2 KB) so LLM context stays small.

## 3. Agent loop (`agent/loop.py`)
1. Trigger: worker marks camera unhealthy (2 consecutive scans) → incident opened → agent job.
2. Agent loop, max 12 steps, budget max 20k LLM tokens per incident.
3. On finish: incident state + trace stored; dashboard updates.

### 3.1 PolicyAgent (`agent/policy.py`) — deterministic decision table
```
scan → diagnose → predict_ai_impact
if all faults ∈ {drift, exposure, haze, color_cast, noise} and guard allows:
    apply_repair(best fault) → verify_repair
    if recovered: close_incident("auto_fixed"); else rollback → escalate
escalate:
    describe_fault(region) → priority = predicted_drop × criticality
    if priority ≥ P_dispatch: request_human_approval("dispatch_technician")
    else: set_watch(60)
false alarm: if re-scan shows healthy → close_incident("transient")
```

### 3.2 BedrockAgent (`agent/bedrock.py`) — Bedrock Converse API with tool use
- Client: `boto3.client("bedrock-runtime")`; call `converse(modelId=..., system=[{"text": SYSTEM}],
  messages=[...], toolConfig={"tools": [{"toolSpec": {"name", "description", "inputSchema": {"json": schema}}}]},
  inferenceConfig={"maxTokens": 1024, "temperature": 0})`.
- When `stopReason == "tool_use"`, read `toolUse` blocks (`toolUseId`, `name`, `input`), run the tool
  **through the guard**, reply with a `user` message containing
  `{"toolResult": {"toolUseId": id, "content": [{"json": result}], "status": "success"|"error"}}`.
- Tool specs are generated automatically from the MCP server: an MCP client
  (`mcp.ClientSession` over streamable HTTP — **VERIFY** import path
  `mcp.client.streamable_http`) calls `list_tools()` and maps `name/description/inputSchema`.
- Model: chosen at deploy time via `aws bedrock list-inference-profiles` (prefer a Claude Sonnet
  inference profile in the deployment region); stored in SSM Parameter `/visiondoctor/bedrock_model_id`.
- Optional: pass the face-blurred reference/current/heat-map images as `image` content blocks so the
  model can compare them visually (**VERIFY** image block format in Converse docs).

### 3.3 System prompt (`agent/prompts.py`) — essentials
```
You are VisionDoctor, a camera-fleet reliability agent. You can only act through tools.
Goal: restore trustworthy AI performance on each camera with the least disruption.
Rules:
- Always scan and diagnose before acting. Base every decision on tool outputs; cite the numbers.
- Only software-fixable faults may be repaired: drift, exposure, haze, color_cast, noise.
- After any repair you MUST call verify_repair. If not recovered, rollback and escalate.
- Physical faults (defocus, smudge, occlusion, freeze, hardware) → describe_fault, then decide
  between set_watch and request_human_approval using predicted_drop × criticality.
- Never dispatch or move a camera without request_human_approval.
- Finish with close_incident or a pending approval. Be concise.
```

## 4. Guard (`agent/guard.py`)
Runs on every tool call from either agent; verdicts recorded in the trace.
- Allowlist of tools; schema validation; repair parameter bounds (docs/03 §4).
- `apply_repair` only if the matching fault is present at severity ≥ 2 in the latest scan.
- `create_maintenance_ticket` only if an approval with state `approved` exists for the incident.
- Max 2 repair attempts per incident; max 12 steps; token budget; per-camera lock while a human
  is working on it; rate limit 10 incidents/min per fleet.
- Blocked call → returns `{"error": "blocked_by_guard", "reason": ...}` so the agent can re-plan.

## 5. Trace schema (`agent/trace.py`) — the award evidence
```json
{
  "trace_id": "tr_01H...", "incident_id": "inc_...", "camera_id": "cam-07", "agent": "bedrock|policy",
  "steps": [
    {"i": 1, "tool": "scan_camera", "input": {"camera_id": "cam-07"},
     "output_summary": "drift sev4: rot=4.2°, corner_disp=61px, inliers=0.71",
     "decision_reason": "drift detected; check impact before repair",
     "latency_ms": 412, "guard": "allowed"},
    {"i": 2, "tool": "predict_ai_impact", "output_summary": "pred acc 0.79→0.48 (drop 0.31)"},
    {"i": 3, "tool": "apply_repair", "input": {"repair": "realign"}, "guard": "allowed"},
    {"i": 4, "tool": "verify_repair", "output_summary": "residual 0.3°, pred acc 0.77 — recovered"},
    {"i": 5, "tool": "close_incident", "input": {"resolution": "auto_fixed"}}
  ],
  "outcome": "auto_fixed", "total_ms": 2140, "tokens_in": 3120, "tokens_out": 410
}
```
The dashboard trace viewer (docs/07) renders this as a timeline; the video shows one live.

## 6. Golden-trace tests (`tests/agent/`)
Scripted incidents with expected outcomes: drift→auto_fixed; haze→auto_fixed (or watch at site-wide
fog); smudge→approval requested; occlusion→approval requested; freeze→approval requested;
transient glare→closed as transient; out-of-bounds drift (25°)→guard blocks repair→escalation.
Assert the policy agent's exact tool sequence; assert the Bedrock agent's final outcome (≥ 6/7 runs).
