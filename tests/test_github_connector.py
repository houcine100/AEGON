# Run from project root, in a terminal that has GITHUB_PERSONAL_ACCESS_TOKEN:
#   python tests\test_github_connector.py
from tools.github_search.github_search_tool import GitHubSearchConnector

c = GitHubSearchConnector()
print("validate (good):", c.validate({"query": "langgraph"}))
print("validate (empty):", c.validate({}))
result = c.execute({"query": "langgraph multi-agent language:python"})
print("status:", result["status"])
print("output:\n", result["output"][:1500])