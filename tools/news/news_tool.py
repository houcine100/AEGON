# tools/news/news_tool.py
# Fetches top world headlines from the last 24 hours via RSS.
# Sources: Reuters, BBC World, AP, Al Jazeera.
# read_only, verbatim — no approval needed.

from datetime import datetime, timezone, timedelta

import feedparser

from tools.base_connector import BaseConnector

# Trusted RSS sources. Add/remove here only.
SOURCES = [
    ("Reuters",     "https://feeds.reuters.com/reuters/topNews"),
    ("BBC",         "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("AP",          "https://feeds.apnews.com/rss/apf-topnews"),
    ("Al Jazeera",  "https://www.aljazeera.com/xml/rss/all.xml"),
]

MAX_PER_SOURCE = 3   # headlines to consider from each feed
MAX_HEADLINES = 5    # final spoken count
WINDOW_HOURS = 24    # only items published within this window


def _parse_pub(entry) -> datetime | None:
    """Extract a UTC-aware published datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def _fetch_headlines() -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    seen: set[str] = set()
    bucket: list[tuple[datetime, str]] = []

    for _name, url in SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        count = 0
        for entry in feed.entries:
            if count >= MAX_PER_SOURCE:
                break

            title = (entry.get("title") or "").strip()
            if not title:
                continue

            pub = _parse_pub(entry)
            if pub and pub < cutoff:
                continue  # too old

            key = title.lower()[:50]
            if key in seen:
                continue
            seen.add(key)

            bucket.append((pub or datetime.now(timezone.utc), title))
            count += 1

    bucket.sort(key=lambda x: x[0], reverse=True)
    return [title for _, title in bucket[:MAX_HEADLINES]]


class NewsConnector(BaseConnector):
    name = "news"
    version = "1.0.0"
    description = "Fetches top world headlines from the last 24 hours via RSS."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict)

    def execute(self, payload: dict) -> dict:
        headlines = _fetch_headlines()
        if not headlines:
            return {"status": "success", "output": "No major headlines in the last 24 hours, Sir."}
        spoken = "Top stories in the last 24 hours: " + ". ".join(headlines) + "."
        return {"status": "success", "output": spoken}
