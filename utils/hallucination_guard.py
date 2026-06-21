"""
Hallucination Guard — cross-checks Claude Haiku's analysis against the source articles.

Two-layer defence:
  1. Automatic: Claude Sonnet re-reads the articles and verifies each signal claim
  2. Human: one article per day is flagged for the user to read and score manually
"""

import json
import re
import anthropic
from typing import Optional


class HallucinationGuard:
    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None

    def set_api_key(self, key: str):
        self._client = anthropic.Anthropic(api_key=key)

    def verify_analysis(self, industry: str, articles: list[dict], analysis: dict) -> dict:
        """
        Use Claude Haiku (cheap) to cross-check each signal against the article text.
        Returns the analysis dict annotated with verification results.
        """
        if not self._client or not analysis.get("signals"):
            return analysis

        article_text = "\n\n".join([
            f"[{i+1}] TITLE: {a['title']}\nSUMMARY: {a['summary']}"
            for i, a in enumerate(articles)
        ])

        signals_json = json.dumps(analysis.get("signals", []), indent=2)

        prompt = f"""You are a fact-checker reviewing an AI analyst's claims about {industry} news.

Below are the SOURCE ARTICLES, followed by the ANALYST'S SIGNALS.
For each signal, check whether the rationale is grounded in the source articles.

SOURCE ARTICLES:
{article_text}

ANALYST SIGNALS TO VERIFY:
{signals_json}

Respond ONLY with valid JSON — no preamble, no markdown fences:
{{
  "verifications": [
    {{
      "ticker": "AAPL",
      "grounded": true,
      "supporting_article_index": 2,
      "issue": null
    }},
    {{
      "ticker": "MSFT",
      "grounded": false,
      "supporting_article_index": null,
      "issue": "Rationale mentions 'Azure outage' but no article covers this"
    }}
  ],
  "overall_reliability": "high",
  "flags": []
}}

Rules:
- grounded = true only if the rationale is clearly supported by at least one article
- overall_reliability is "high" (0 issues), "medium" (1 issue), or "low" (2+ issues)
- flags is a list of strings describing any hallucinated claims"""

        try:
            response = self._client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            verification = json.loads(raw.strip())
        except Exception as e:
            verification = {
                "verifications": [],
                "overall_reliability": "unknown",
                "flags": [f"Verification failed: {e}"],
            }

        # Annotate each signal with its verification result
        ver_map = {v["ticker"]: v for v in verification.get("verifications", [])}
        for sig in analysis.get("signals", []):
            ticker = sig.get("ticker", "")
            ver = ver_map.get(ticker, {})
            sig["verified"] = ver.get("grounded", None)
            sig["verification_issue"] = ver.get("issue")
            sig["supporting_article"] = ver.get("supporting_article_index")

        analysis["verification"] = {
            "overall_reliability": verification.get("overall_reliability", "unknown"),
            "flags": verification.get("flags", []),
            "ungrounded_count": sum(
                1 for v in verification.get("verifications", []) if not v.get("grounded")
            ),
        }

        return analysis

    def pick_spot_check_article(self, articles: list[dict], analysis: dict) -> Optional[dict]:
        """
        Pick one article for the human to read and evaluate today.
        Prefers articles with high-conviction signals attached to them.
        Returns the article dict enriched with the relevant signal.
        """
        if not articles:
            return None

        # Find the article that most relates to the top signal
        top_signal = max(
            analysis.get("signals", [{}]),
            key=lambda s: s.get("conviction", 0),
            default=None,
        )
        if not top_signal:
            return {**articles[0], "related_signal": None}

        ticker = top_signal.get("ticker", "").upper()

        # Score articles by ticker mention
        def score(art):
            text = (art.get("title", "") + " " + art.get("summary", "")).upper()
            return 2 if ticker in text else 1

        best = max(articles, key=score)
        return {**best, "related_signal": top_signal}

    def compute_reliability_score(self, eval_history: list[dict]) -> dict:
        """
        Aggregate human evaluation history into a reliability profile.
        Used to display running hallucination stats in the UI.
        """
        if not eval_history:
            return {
                "total_evals": 0,
                "hallucination_rate": None,
                "avg_accuracy": None,
                "sentiment_match_rate": None,
            }

        total = len(eval_history)
        hallucinations = sum(1 for e in eval_history if e.get("hallucination_flag"))
        accuracy_scores = [e["accuracy_score"] for e in eval_history if e.get("accuracy_score")]
        sentiment_matches = sum(
            1 for e in eval_history
            if e.get("human_sentiment") and e.get("haiku_sentiment")
            and e["human_sentiment"] == e["haiku_sentiment"]
        )

        return {
            "total_evals": total,
            "hallucination_rate": round(hallucinations / total * 100, 1),
            "avg_accuracy": round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else None,
            "sentiment_match_rate": round(sentiment_matches / total * 100, 1),
        }
