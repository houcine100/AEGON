# tools/web_search/web_search_tool.py
# Web search connector. READ ONLY — no approval needed.
# Does ONE thing: take a query, return raw results. No LLM, no summarizing.
# tool_node turns these raw results into Aegon's answer later (Step 3c).

from ddgs import DDGS
from tools.base_connector import BaseConnector


class WebSearchConnector(BaseConnector):
    name = "web_search"
    version = "1.0.0"
    description = "Searches the web with DuckDuckGo and returns raw results."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        """Input must have a non-empty 'query' string."""
        query = payload.get("query")
        return isinstance(query, str) and len(query.strip()) > 0

    def execute(self, payload: dict) -> dict:
        """
        Run the search. Return clean results.
        On success: {"status": "success", "output": [ {title, href, body}, ... ]}
        On failure: {"status": "error", "output": <message>}
        """
        query = (payload.get("query") or "").strip()
        max_results = payload.get("max_results", 5)

        if not self.validate(payload):
            return {"status": "error", "output": "Empty or invalid query."}

        try:
            raw = list(DDGS().text(query, max_results=max_results))
        except Exception as e:
            return {"status": "error", "output": f"Search failed: {e}"}

        if not raw:
            return {"status": "no_results", "output": []}

        # Keep only the three fields we confirmed exist. Defensive: skip malformed.
        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "href": item.get("href", ""),
                "body": item.get("body", ""),
            })

        return {"status": "success", "output": results}