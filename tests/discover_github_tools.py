# tests/discover_github_tools.py
# Lists the GitHub MCP server's tools over stdio — read-only, scoped small.
# Run from the project root with the venv active:
#   python tests\discover_github_tools.py
# Needs GITHUB_PERSONAL_ACCESS_TOKEN visible (open a NEW terminal after setx).

import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BINARY = r"C:\Users\houci\Desktop\AI Projects\aegon\tools\bin\github-mcp-server.exe"

server_params = StdioServerParameters(
    command=BINARY,
    args=["stdio", "--read-only", "--toolsets", "repos,users"],
    env=dict(os.environ),   # pass full env so the server sees the PAT + Windows essentials
)

async def main():
    if not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        print("WARNING: GITHUB_PERSONAL_ACCESS_TOKEN not visible in this terminal.")
        print("Open a NEW terminal after running setx, then re-run.\n")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            print(f"{len(result.tools)} read-only tools (toolsets: repos, users):\n")
            print("\n--- input schemas for first-tool candidates ---")
            for t in result.tools:
                if t.name in ("search_repositories", "search_users"):
                    print(f"\n{t.name}:")
                    print(t.inputSchema)

if __name__ == "__main__":
    asyncio.run(main())