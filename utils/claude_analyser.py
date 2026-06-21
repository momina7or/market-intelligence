"""
Claude Analyser — sends news to Claude, gets back structured investment signals.
"""

import json
import anthropic
from typing import Optional


class ClaudeAnalyser:
    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None

    def set_api_key(self, key: str):
        self._client = anthropic.Anthropic(api_key=key)

    def analyse_industry(self, industry: str, articles: list[dict], tickers: list[str]) -> dict:
        """
        Send articles for an industry to Claude.
        Returns structured dict with: signals, summary, risks.
        """
        if not self._client:
            raise RuntimeError("API key not set. Call set_api_key() first.")

        if not articles:
            return {"signals": [], "summary": "No articles available.", "risks": []}

        # Build the article text block
        article_text = "\n\n".join([
            f"[{i+1}] {a['title']}\nSource: {a['source']} | {a['published']}\n{a['summary']}"
            for i, a in enumerate(articles)
        ])

        tickers_str = ", ".join(tickers)

        prompt = f"""You are an expert financial analyst specialising in the {industry} sector.

Analyse the following {len(articles)} news articles and provide investment signals for these stocks: {tickers_str}

ARTICLES:
{article_text}

Respond ONLY with valid JSON in exactly this structure — no preamble, no markdown fences:

{{
  "signals": [
    {{
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "sentiment": "bullish",
      "conviction": 78,
      "rationale": "One sentence explaining the key driver",
      "key_themes": ["AI investment", "supply chain improvement"],
      "time_horizon": "short-term"
    }}
  ],
  "summary": "2-3 sentence overall sector summary covering the main themes and outlook",
  "risks": ["key risk 1", "key risk 2"],
  "sector_sentiment": "bullish"
}}

Rules:
- Only include tickers from this list that are meaningfully mentioned or impacted by the news: {tickers_str}
- sentiment must be one of: bullish, bearish, neutral
- conviction is 0-100 (100 = extremely high confidence)
- time_horizon is one of: short-term (days-weeks), medium-term (1-3 months), long-term (3+ months)
- sector_sentiment is one of: bullish, bearish, neutral
- If a ticker isn't relevant to these articles, omit it from signals
- Keep rationale concise (max 120 characters)
- Be specific and grounded in the actual articles, not generic commentary"""

        response = self._client.messages.create(
            model="claude-haiku-4-5",   # cheapest model — perfect for bulk analysis
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Graceful fallback
            result = {
                "signals": [],
                "summary": raw[:500] if raw else "Analysis unavailable.",
                "risks": [],
                "sector_sentiment": "neutral",
            }

        # Back-fill sentiment hints onto articles for colour coding in UI
        # (simple keyword check on the summary)
        bull_words = {"surge", "rally", "beat", "growth", "record", "strong", "gain"}
        bear_words = {"fall", "drop", "miss", "decline", "loss", "weak", "cut", "risk"}
        for art in articles:
            text = (art["title"] + " " + art["summary"]).lower()
            if any(w in text for w in bull_words):
                art["sentiment_hint"] = "bullish"
            elif any(w in text for w in bear_words):
                art["sentiment_hint"] = "bearish"

        return result
