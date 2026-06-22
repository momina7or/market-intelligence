"""
daily_run.py — runs via GitHub Actions every weekday morning.
Saves results to data/latest_results.json which gets committed back to the repo.
Streamlit reads this file directly — no shared database needed.
"""

import os
import sys
import json
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.news_fetcher import NewsFetcher
from utils.stock_fetcher import StockFetcher
from utils.claude_analyser import ClaudeAnalyser
from utils.hallucination_guard import HallucinationGuard

INDUSTRIES = {
    "Technology":         {"icon":"💻","tickers":["AAPL","MSFT","NVDA","GOOGL","META","AMD","TSM"],"color":"#388bfd"},
    "Petroleum & Energy": {"icon":"⛽","tickers":["XOM","CVX","BP","SHEL","TTE","COP","SLB"],"color":"#d29922"},
    "Healthcare":         {"icon":"💊","tickers":["JNJ","UNH","PFE","MRK","ABBV","LLY","TMO"],"color":"#3fb950"},
    "Finance":            {"icon":"🏦","tickers":["JPM","BAC","GS","MS","BRK-B","V","MA"],"color":"#bc8cff"},
}

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "latest_results.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.json")

def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    today = date.today().isoformat()
    print(f"\n{'='*50}")
    print(f"Daily Market Analysis — {today}")
    print(f"{'='*50}\n")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    news   = NewsFetcher()
    stocks = StockFetcher()
    claude = ClaudeAnalyser()
    guard  = HallucinationGuard()
    claude.set_api_key(api_key)
    guard.set_api_key(api_key)

    all_results = {}

    for industry, cfg in INDUSTRIES.items():
        print(f"\n{cfg['icon']}  {industry}")
        print("-" * 30)

        # 1. News
        print("  Fetching news...")
        articles = news.fetch(industry, limit=6)
        print(f"  {len(articles)} articles")

        # 2. Claude analysis
        print("  Analysing with Claude Haiku...")
        analysis = claude.analyse_industry(industry, articles, cfg["tickers"])
        signals = analysis.get("signals", [])
        print(f"  {len(signals)} signals")

        # 3. Hallucination check
        print("  Hallucination check...")
        analysis = guard.verify_analysis(industry, articles, analysis)
        reliability = analysis.get("verification", {}).get("overall_reliability", "unknown")
        print(f"  Reliability: {reliability}")

        # 4. Stock prices
        prices_snapshot = {}
        for sig in signals:
            ticker = sig["ticker"]
            df = stocks.fetch(ticker, days=2)
            price = float(df["Close"].iloc[-1]) if df is not None and not df.empty else None
            prices_snapshot[ticker] = price
            price_str = f"${price:.2f}" if price else "n/a"
            print(f"    {ticker}: {sig['sentiment']} ({sig['conviction']}%) @ {price_str}")

        # 5. Spot-check article
        spot = guard.pick_spot_check_article(articles, analysis)
        if spot:
            related = spot.get("related_signal") or {}
            spot["haiku_sentiment"] = related.get("sentiment", "neutral")
            spot["haiku_rationale"] = related.get("rationale", "")
            spot["haiku_themes"]    = related.get("key_themes", [])

        all_results[industry] = {
            "articles":        articles,
            "analysis":        analysis,
            "prices_snapshot": prices_snapshot,
            "spot_check":      spot,
            "config":          cfg,
        }
        print(f"  ✅ {industry} done")

    # Build output payload
    payload = {
        "run_date":   today,
        "run_time":   datetime.utcnow().isoformat() + "Z",
        "results":    all_results,
    }

    # Save latest_results.json (Streamlit reads this)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\n✅ Saved to {OUTPUT_FILE}")

    # Append to history.json (keeps last 90 days)
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                history = json.load(f)
        except Exception:
            history = []

    # Store a lightweight summary per day (not full articles)
    summary_entry = {
        "run_date": today,
        "industries": {}
    }
    for industry, r in all_results.items():
        summary_entry["industries"][industry] = {
            "signals": r["analysis"].get("signals", []),
            "prices_snapshot": r["prices_snapshot"],
            "sector_sentiment": r["analysis"].get("sector_sentiment", "neutral"),
            "reliability": r["analysis"].get("verification", {}).get("overall_reliability", "unknown"),
        }

    # Remove existing entry for today if re-running
    history = [h for h in history if h["run_date"] != today]
    history.append(summary_entry)
    # Keep last 90 days
    history = sorted(history, key=lambda x: x["run_date"])[-90:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)
    print(f"✅ History updated ({len(history)} days)")

    print(f"\n{'='*50}")
    print(f"✅ Complete — {today}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run()
