"""
News Fetcher — pulls articles from RSS feeds (free) and optionally NewsAPI.
"""

import feedparser
import requests
from datetime import datetime
from typing import Optional


# Industry → RSS feed sources (all free, no API key needed)
INDUSTRY_FEEDS = {
    "Technology": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.wired.com/feed/rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://feeds.reuters.com/reuters/technologyNews",
    ],
    "Petroleum & Energy": [
        "https://oilprice.com/rss/main",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.energymonitor.ai/feed/",
        "https://feeds.feedburner.com/platts/oilnews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Energy-Environment.xml",
    ],
    "Healthcare": [
        "https://feeds.reuters.com/reuters/healthNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
        "https://feeds.feedburner.com/statnews/health",
        "https://www.fiercepharma.com/rss/xml",
        "https://www.healio.com/rss/general-medical-education",
    ],
    "Finance": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://feeds.feedburner.com/ftfinance",
        "https://seekingalpha.com/market_currents.xml",
    ],
}


class NewsFetcher:
    def __init__(self, newsapi_key: Optional[str] = None):
        """
        newsapi_key: optional key from newsapi.org (free tier = 100 req/day)
        Without it, RSS feeds are used exclusively.
        """
        self.newsapi_key = newsapi_key

    def fetch(self, industry: str, limit: int = 8) -> list[dict]:
        """Fetch articles for an industry. Returns list of article dicts."""
        articles = []

        # Try RSS feeds first (always free)
        feeds = INDUSTRY_FEEDS.get(industry, [])
        for feed_url in feeds:
            if len(articles) >= limit:
                break
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries[:3]:  # max 3 per feed
                    if len(articles) >= limit:
                        break
                    articles.append(self._normalise_rss(entry, feed_url))
            except Exception:
                continue  # skip broken feeds silently

        # Optionally supplement with NewsAPI
        if self.newsapi_key and len(articles) < limit:
            try:
                newsapi_articles = self._fetch_newsapi(industry, limit - len(articles))
                articles.extend(newsapi_articles)
            except Exception:
                pass

        return articles[:limit]

    def _normalise_rss(self, entry, feed_url: str) -> dict:
        """Normalise a feedparser entry into a standard dict."""
        # Parse publish date
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                dt = datetime(*entry.published_parsed[:6])
                published = dt.strftime("%d %b %Y")
            except Exception:
                pass

        # Extract source name from feed URL
        source = feed_url.split("/")[2].replace("www.", "").replace("feeds.", "").split(".")[0].title()

        # Strip HTML from summary
        summary = getattr(entry, "summary", "") or ""
        summary = summary.replace("<p>", " ").replace("</p>", " ")
        import re
        summary = re.sub(r"<[^>]+>", "", summary).strip()[:500]

        return {
            "title": getattr(entry, "title", "Untitled"),
            "summary": summary,
            "url": getattr(entry, "link", ""),
            "source": source,
            "published": published,
            "sentiment_hint": "neutral",  # will be filled by Claude
        }

    def _fetch_newsapi(self, industry: str, limit: int) -> list[dict]:
        """Fetch from newsapi.org (free tier: 100 requests/day)."""
        query_map = {
            "Technology": "technology stocks OR semiconductor OR AI chips",
            "Petroleum & Energy": "oil price OR petroleum OR energy stocks",
            "Healthcare": "pharmaceutical stocks OR biotech OR FDA approval",
            "Finance": "banking stocks OR interest rates OR Federal Reserve",
        }
        query = query_map.get(industry, industry)

        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": self.newsapi_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for a in data.get("articles", []):
            published = ""
            if a.get("publishedAt"):
                try:
                    dt = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                    published = dt.strftime("%d %b %Y")
                except Exception:
                    pass
            articles.append({
                "title": a.get("title", ""),
                "summary": (a.get("description") or "")[:500],
                "url": a.get("url", ""),
                "source": (a.get("source") or {}).get("name", "NewsAPI"),
                "published": published,
                "sentiment_hint": "neutral",
            })
        return articles
