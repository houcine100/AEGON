from tools.spotify_search.spotify_search_tool import SpotifySearchConnector

c = SpotifySearchConnector()
print("validate (good):", c.validate({"query": "daft punk"}))
print("validate (empty):", c.validate({}))
result = c.execute({"query": "daft punk get lucky"})
print("status:", result["status"])
for r in result["output"][:5]:
    print("-", r["title"], "|", r["body"], "|", r["href"])