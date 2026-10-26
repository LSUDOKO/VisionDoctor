"""MCP tool server exposing VisionDoctor's OpenCV tools (docs/04 §2).

Built on the official MCP Python SDK v2 (``mcp.server.mcpserver.MCPServer``; FastMCP was
renamed in 2.x). Served over stdio (local dev / Claude Code) or streamable HTTP (production,
inside the VPC, shared-secret header). Agents in the same process call the very same tools via
``MCPServer.call_tool`` so traces are identical across transports.
"""

from __future__ import annotations

import argparse
import json
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from visiondoctor.fleet import Fleet

RepairName = Literal["realign", "exposure_fix", "dehaze", "white_balance", "denoise"]
MAX_RESULT_BYTES = 2048

INSTRUCTIONS = (
    "VisionDoctor camera-health tools. OpenCV 5 does the seeing; you decide. Always scan and "
    "diagnose before acting; verify every repair; physical faults need human approval."
)


def _compact(d: dict[str, Any] | list[Any]) -> Any:
    """Keep tool results ≤ 2 KB so the LLM context stays small."""
    s = json.dumps(d, default=str)
    if len(s) <= MAX_RESULT_BYTES:
        return d
    if isinstance(d, dict):
        out = dict(d)
        for k in sorted(out, key=lambda k: -len(json.dumps(out[k], default=str))):
            out[k] = "…truncated"
            if len(json.dumps(out, default=str)) <= MAX_RESULT_BYTES:
                break
        return out
    return d[:10]


def build_server(fleet: Fleet) -> MCPServer:
    mcp = MCPServer("visiondoctor", instructions=INSTRUCTIONS, version="0.1.0")

    @mcp.tool(description="List cameras whose latest scan has a fault at or above min_severity, highest priority first.")
    def list_unhealthy_cameras(min_severity: Annotated[int, Field(ge=1, le=5)] = 2) -> list[dict[str, Any]]:
        return _compact(fleet.list_unhealthy(min_severity))  # type: ignore[no-any-return]

    @mcp.tool(description="Run all 11 OpenCV health checks on a fresh burst of frames from the camera.")
    def scan_camera(
        camera_id: str, frames: Annotated[int, Field(ge=3, le=15)] = 5
    ) -> dict[str, Any]:
        return _compact(fleet.scan_camera(camera_id, frames))  # type: ignore[no-any-return]

    @mcp.tool(description="Fuse the latest checks into faults with regions, which are software-fixable, and a likely cause.")
    def diagnose(camera_id: str) -> dict[str, Any]:
        return _compact(fleet.diagnose(camera_id))  # type: ignore[no-any-return]

    @mcp.tool(description="Predict the downstream detector's accuracy (agreement with clean behaviour) without labels.")
    def predict_ai_impact(camera_id: str) -> dict[str, Any]:
        return _compact(fleet.predict_ai_impact(camera_id))  # type: ignore[no-any-return]

    @mcp.tool(description="URLs of the reference frame, current frame and quality heat map (faces blurred).")
    def get_reference_comparison(camera_id: str) -> dict[str, Any]:
        return fleet.reference_comparison(camera_id)

    @mcp.tool(description="Apply a bounded software repair to the camera's correction profile (pending until verified).")
    def apply_repair(camera_id: str, repair: RepairName, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return _compact(fleet.apply_repair(camera_id, repair, params))  # type: ignore[no-any-return]

    @mcp.tool(description="Re-scan and re-predict impact with the repair applied; commits it only if recovered.")
    def verify_repair(camera_id: str, repair_id: str) -> dict[str, Any]:
        return _compact(fleet.verify_repair(camera_id, repair_id))  # type: ignore[no-any-return]

    @mcp.tool(description="Remove a repair from the camera's correction profile.")
    def rollback_repair(camera_id: str, repair_id: str) -> dict[str, Any]:
        return fleet.rollback_repair(camera_id, repair_id)

    @mcp.tool(description="Describe the fault region for a technician (OpenCV 5 VLM, rule-based fallback). Escalations only.")
    def describe_fault(camera_id: str, region_bbox: list[int] | None = None) -> dict[str, Any]:
        return _compact(fleet.describe_fault(camera_id, region_bbox))  # type: ignore[no-any-return]

    @mcp.tool(description="Ask a human to approve a physical action (technician dispatch or PTZ re-home).")
    def request_human_approval(
        incident_id: str,
        action: Literal["dispatch_technician", "ptz_rehome"],
        reason: Annotated[str, Field(max_length=500)],
        evidence_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        return fleet.request_human_approval(incident_id, action, reason, evidence_keys)

    @mcp.tool(description="Create a maintenance ticket. Only allowed after the incident's approval is granted.")
    def create_maintenance_ticket(
        incident_id: str, fault_type: str, instructions: Annotated[str, Field(max_length=1000)]
    ) -> dict[str, Any]:
        return fleet.create_maintenance_ticket(incident_id, fault_type, instructions)

    @mcp.tool(description="Rescan this camera more often (watchlist).")
    def set_watch(camera_id: str, scan_interval_s: Annotated[int, Field(ge=10, le=3600)] = 60) -> dict[str, Any]:
        return fleet.set_watch(camera_id, scan_interval_s)

    @mcp.tool(description="Close an incident with a resolution: auto_fixed, transient, false_alarm, or watch.")
    def close_incident(
        incident_id: str, resolution: Literal["auto_fixed", "transient", "false_alarm", "watch", "field_fixed"]
    ) -> dict[str, Any]:
        return fleet.close_incident(incident_id, resolution)

    return mcp


def main() -> None:
    from visiondoctor.observability.logging import setup
    from visiondoctor.sim.simulator import FleetSimulator

    ap = argparse.ArgumentParser(description="VisionDoctor MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--cameras", type=int, default=12)
    args = ap.parse_args()
    setup("WARNING" if args.transport == "stdio" else None)
    fleet = Fleet(FleetSimulator(cameras=args.cameras))
    fleet.bootstrap()
    server = build_server(fleet)
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
