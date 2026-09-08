# tools/github_search/github_search_tool.py
# Searches GitHub repositories (read-only) via GitHub's official MCP server binary.
# Modeled on ClockConnector. Read-only, no approval. PAT inherited from the environment.

import json
import os
from tools.mcp_connector import MCPConnector

# Path to the GitHub MCP server binary.
# Set GITHUB_MCP_BINARY in the environment to override (e.g. in .env).
# Defaults to the location where it was originally installed.
_DEFAULT_BINARY = r"C:\Users\houci\Desktop\AI Projects\aegon\tools\bin\github-mcp-server.exe"
GITHUB_BINARY = os.environ.get("GITHUB_MCP_BINARY", _DEFAULT_BINARY)


class GitHubSearchConnector(MCPConnector):
    name = "github_search"
    version = "1.0.0"
    description = "Searches GitHub repositories, read-only, via GitHub's official MCP server."
    permission_level = "read_only"

    mcp_command = GITHUB_BINARY
    mcp_args = ["stdio", "--read-only", "--toolsets", "repos,users"]
    mcp_tool_name = "search_repositories"

    def validate(self, payload: dict) -> bool:
        # search_repositories requires a non-empty query (per the server's schema).
        return isinstance(payload, dict) and bool(payload.get("query"))

    def execute(self, payload: dict) -> dict:
        # Run the MCP call, then reshape GitHub's JSON into the {title, href, body}
        # form the summarize path already understands — so the honesty prompt speaks it cleanly.
        result = super().execute(payload)
        if result.get("status") != "success":
            return result
        try:
            items = json.loads(result["output"]).get("items", [])
        except (json.JSONDecodeError, TypeError, AttributeError):
            return result  # if it isn't the JSON we expect, fall back to the raw output
        if not items:
            return {"status": "no_results", "output": []}
        shaped = []
        for repo in items[:8]:
            desc = repo.get("description") or "No description."
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language") or "unknown language"
            shaped.append({
                "title": repo.get("full_name", ""),
                "href": repo.get("html_url", ""),
                "body": f"{desc} ({stars} stars, {lang})",
            })
        return {"status": "success", "output": shaped}