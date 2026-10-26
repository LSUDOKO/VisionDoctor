"""Tool clients: in-process MCP server, or a remote MCP server over streamable HTTP.

Both expose ``specs()`` (name/description/JSON schema from MCP ``list_tools``) and
``call(name, args) -> dict``. Validation errors come back as ``{"error": ...}`` so an agent
can re-plan instead of crashing.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from mcp.server.mcpserver import MCPServer


class ToolClient(Protocol):
    async def specs(self) -> list[dict[str, Any]]: ...

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...


def _result_to_dict(res: Any) -> dict[str, Any]:
    sc = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    if getattr(res, "is_error", False) or getattr(res, "isError", False):
        text = " ".join(getattr(c, "text", "") for c in res.content)
        return {"error": text[:500]}
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} and isinstance(sc["result"], dict) else sc
    for c in res.content:
        t = getattr(c, "text", None)
        if t:
            try:
                v = json.loads(t)
                return v if isinstance(v, dict) else {"result": v}
            except json.JSONDecodeError:
                return {"text": t}
    return {}


class InProcessTools:
    def __init__(self, server: MCPServer) -> None:
        self.server = server

    async def specs(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in await self.server.list_tools()
        ]

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            res = await self.server.call_tool(name, args)
        except Exception as e:  # noqa: BLE001 - surface tool/validation errors to the agent
            return {"error": str(e).split("\n")[0][:400]}
        return _result_to_dict(res)


class HttpTools:
    """Remote MCP server (production: internal ALB, shared-secret header)."""

    def __init__(self, url: str, secret: str | None = None) -> None:
        self.url, self.headers = url, ({"x-vd-secret": secret} if secret else {})

    async def _session_call(self, fn: str, *a: Any) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(self.url, headers=self.headers) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await getattr(s, fn)(*a)

    async def specs(self) -> list[dict[str, Any]]:
        res = await self._session_call("list_tools")
        return [
            {"name": t.name, "description": t.description or "", "input_schema": getattr(t, "input_schema", None) or t.inputSchema}
            for t in res.tools
        ]

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _result_to_dict(await self._session_call("call_tool", name, args))
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:400]}
