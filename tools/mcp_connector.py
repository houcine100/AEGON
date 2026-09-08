# tools/mcp_connector.py
# Bridges Aegon to any MCP server over stdio. Written ONCE, language-agnostic.
# Each MCP-backed tool registers with: command, args, and which server tool to call.
# Flows through the SAME registry/governance/approval as every other connector.

import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools.base_connector import BaseConnector


class MCPConnector(BaseConnector):
    # Subclasses set these (from connector.json, loaded by the registry).
    name = "mcp_unnamed"
    version = "1.0.0"
    description = "An MCP-backed tool."
    permission_level = "read_only"

    # MCP launch details — set by the subclass.
    mcp_command = ""          # e.g. "python"
    mcp_args: list = []       # e.g. ["-m", "mcp_server_time"]
    mcp_tool_name = ""        # the tool to call on the server, e.g. "get_current_time"
    mcp_env: dict = {}        # extra env vars for the server, merged over the inherited environment

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict)

    def execute(self, payload: dict) -> dict:
        try:
            return asyncio.run(self._call(payload))
        except Exception as e:
            return {"status": "error", "output": f"MCP call failed: {e}"}

    async def _call(self, payload: dict) -> dict:
        # The server inherits Aegon's environment (so tokens set as env vars reach it),
        # plus any extra vars the subclass declares in mcp_env.
        server_env = {**os.environ, **self.mcp_env}
        # "python" must mean the SAME interpreter running Aegon (the venv), not whatever
        # bare "python" resolves to on PATH (often a different system Python that lacks the
        # MCP server packages). Resolve it to sys.executable so stdio servers launch in the
        # correct environment.
        command = self.mcp_command
        if command in ("python", "python3"):
            command = sys.executable
        params = StdioServerParameters(command=command, args=self.mcp_args, env=server_env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self.mcp_tool_name, payload)
                # Flatten the MCP content blocks into plain text.
                parts = []
                for block in (result.content or []):
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)
                output = "\n".join(parts) if parts else "(no output)"
                if getattr(result, "isError", False):
                    return {"status": "error", "output": output}
                return {"status": "success", "output": output}