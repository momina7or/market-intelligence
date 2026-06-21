"""
daily_run.py — runs automatically via GitHub Actions every weekday morning.
Fetches news, analyses with Claude, stores results in Supabase.
Completely independent of the Streamlit UI.
"""

import os
import sys
import json
from datetime import date, datetime

# Add parent to path so we can import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.news_fetcher import NewsFetcher
from utils.stock_fetcher import StockFetcher
from utils.claude_analyser import ClaudeAnalyser
from utils.hallucination_guard import HallucinationGuard
from utils import database as db

INDUSTRIES = {
    "Technology": {
        "icon": "💻",
        "tickers": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD", "TSM"],
        "color": "#388bfd",
    },
    "Petroleum & Energy": {
        "icon": "⛽",
        "tickers": ["XOM", "CVX", "BP", "SHEL", "TTE", "COP", "SLB"],
        "color": "#d29922",
    },
    "Healthcare": {
        "icon": "💊",
        "tickers": ["JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "TMO"],
        "color": "#3fb950",
    },
    "Finance": {
        "icon": "🏦",
        "tickers": ["JPM", "BAC", "GS", "MS", "BRK-B", "V", "MA"],
        "color": "#bc8cff",
    },
}

def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    today = date.today().isoformat()
    print(f"\n{'='*50}")
    print(f"Daily Market Analysis — {today}")
    print(f"{'='*50}\n")

    news    = NewsFetcher()
    stocks  = StockFetcher()
    claude  = ClaudeAnalyser()
    guard   = HallucinationGuard()

    claude.set_api_key(api_key)
    guard.set_api_key(api_key)

    for industry, cfg in INDUSTRIES.items():
        print(f"\n{cfg['icon']}  {industry}")
        print("-" * 30)

        # 1. Fetch news
        print("  Fetching news...")
        articles = news.fetch(industry, limit=6)
        print(f"  Got {len(articles)} articles")

        # 2. Analyse with Claude
        print("  Analysing with Claude Haiku...")
        analysis = claude.analyse_industry(industry, articles, cfg["tickers"])
        signals = analysis.get("signals", [])
        print(f"  {len(signals)} signals generated")

        # 3. Hallucination check
        print("  Running hallucination check...")
        analysis = guard.verify_analysis(industry, articles, analysis)
        reliability = analysis.get("verification", {}).get("overall_reliability", "unknown")
        print(f"  Reliability: {reliability}")

        # 4. Store in database
        print("  Storing in database...")
        article_ids = db.log_analysis(today, industry, articles, analysis)

        # 5. Capture current stock prices for each signal
        for sig in signals:
            ticker = sig["ticker"]
            df = stocks.fetch(ticker, days=2)
            price = float(df["Close"].iloc[-1]) if df is not None and not df.empty else None
            db.upsert_outcome(today, ticker, sig["sentiment"], sig["conviction"], price)
            price_str = f"${price:.2f}" if price else "unavailable"
            print(f"    {ticker}: {sig['sentiment']} (conviction {sig['conviction']}%) @ {price_str}")

        # 6. Create spot-check eval for today
        spot = guard.pick_spot_check_article(articles, analysis)
        if spot and article_ids:
            related = spot.get("related_signal") or {}
            db.create_daily_eval(
                today, article_ids[0], spot,
                related.get("sentiment", "neutral"),
                related.get("rationale", ""),
                related.get("key_themes", []),
            )
            print(f"  Spot-check article set: '{spot.get('title','')[:60]}...'")

        # Register sources
        for art in articles:
            if art.get("source"):
                db.upsert_source(art["source"], industry, art.get("url", ""))

        print(f"  ✅ {industry} complete")

    print(f"\n{'='*50}")
    print(f"✅ Daily analysis complete — {today}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run()
