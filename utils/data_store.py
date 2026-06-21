"""
Data Store — saves/loads analysis results to JSON, and provides demo data.
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "last_results.json"


class DataStore:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)

    def save(self, results: dict):
        """Save results to disk (prices serialised as records)."""
        serialisable = {}
        for industry, r in results.items():
            prices_json = {}
            for ticker, df in r.get("prices", {}).items():
                if df is not None:
                    prices_json[ticker] = df.reset_index().to_json(date_format="iso")
            serialisable[industry] = {
                "articles": r["articles"],
                "analysis": r["analysis"],
                "prices_json": prices_json,
                "config": {k: v for k, v in r["config"].items()},
                "saved_at": datetime.now().isoformat(),
            }
        with open(CACHE_FILE, "w") as f:
            json.dump(serialisable, f, indent=2)

    def load(self) -> dict | None:
        """Load the most recent saved results from disk."""
        if not CACHE_FILE.exists():
            return None
        try:
            with open(CACHE_FILE) as f:
                raw = json.load(f)
            results = {}
            for industry, r in raw.items():
                prices = {}
                for ticker, json_str in r.get("prices_json", {}).items():
                    df = pd.read_json(json_str)
                    df = df.set_index(df.columns[0])
                    df.index = pd.to_datetime(df.index)
                    prices[ticker] = df
                results[industry] = {
                    "articles": r["articles"],
                    "analysis": r["analysis"],
                    "prices": prices,
                    "config": r["config"],
                }
            return results
        except Exception:
            return None

    def load_demo(self) -> dict:
        """Return realistic-looking demo data (no API calls required)."""
        np.random.seed(42)

        def fake_prices(base: float, days: int = 30, trend: float = 0.0) -> pd.DataFrame:
            dates = pd.bdate_range(end=datetime.today(), periods=days)
            n = len(dates)
            returns = np.random.normal(trend / n, 0.015, n)
            prices = base * np.cumprod(1 + returns)
            return pd.DataFrame({
                "Open": prices * 0.999,
                "High": prices * 1.012,
                "Low": prices * 0.988,
                "Close": prices,
                "Volume": np.random.randint(10_000_000, 80_000_000, n),
            }, index=dates)

        articles_tech = [
            {"title": "NVIDIA posts record quarterly revenue on AI chip demand surge", "source": "Reuters", "published": "21 Jun 2026", "summary": "NVIDIA reported $36bn in quarterly revenue, driven by explosive demand for H100 and Blackwell GPUs from cloud providers.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "Apple's new M4 Ultra chip outperforms rivals by 40% in benchmarks", "source": "TechCrunch", "published": "20 Jun 2026", "summary": "Independent testing shows Apple's latest silicon delivers industry-leading performance per watt, cementing its hardware advantage.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "Microsoft Azure AI revenue grows 65% YoY as enterprise adoption accelerates", "source": "The Verge", "published": "19 Jun 2026", "summary": "Azure cloud segment surged as Fortune 500 companies ramp AI deployments, with OpenAI partnership continuing to differentiate.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "Intel faces further market share losses amid manufacturing delays", "source": "Ars Technica", "published": "18 Jun 2026", "summary": "Intel's 18A node rollout slips another quarter, allowing TSMC-backed rivals to extend their process technology lead.", "url": "#", "sentiment_hint": "bearish"},
            {"title": "AMD announces next-gen MI400 GPU targeting hyperscale AI training", "source": "Wired", "published": "17 Jun 2026", "summary": "AMD's latest data centre GPU claims 2x the memory bandwidth of its predecessor, directly challenging NVIDIA's dominance in AI training.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "Global semiconductor shortage easing as TSMC capacity expands", "source": "NYT Tech", "published": "16 Jun 2026", "summary": "Taiwan Semiconductor Manufacturing expanded production at its Arizona and Japan fabs, easing supply constraints that had hampered device makers.", "url": "#", "sentiment_hint": "neutral"},
        ]

        articles_oil = [
            {"title": "Oil falls to $71 as OPEC+ signals further production increase", "source": "Reuters", "published": "21 Jun 2026", "summary": "Crude prices declined after OPEC+ members agreed to raise output by 400,000 barrels/day, adding to supply overhang concerns.", "url": "#", "sentiment_hint": "bearish"},
            {"title": "ExxonMobil acquires deepwater assets in Gulf of Mexico for $4.2bn", "source": "FT Energy", "published": "20 Jun 2026", "summary": "ExxonMobil expanded its upstream portfolio with a major deepwater acquisition, signalling confidence in long-term oil demand.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "BP accelerates renewables pivot as oil margins compress", "source": "Energy Monitor", "published": "19 Jun 2026", "summary": "BP announced $8bn in additional renewables spending while cutting upstream oil investment, responding to shareholder ESG pressure.", "url": "#", "sentiment_hint": "neutral"},
            {"title": "US crude inventory builds for third consecutive week", "source": "OilPrice.com", "published": "18 Jun 2026", "summary": "EIA data showed US crude stockpiles rose 3.2 million barrels, exceeding analyst forecasts and weighing on WTI futures.", "url": "#", "sentiment_hint": "bearish"},
            {"title": "Chevron's Permian Basin output hits new record of 1.2m boe/day", "source": "Reuters", "published": "17 Jun 2026", "summary": "Chevron's flagship shale operation achieved a production milestone, underpinning strong free cash flow generation for the quarter.", "url": "#", "sentiment_hint": "bullish"},
            {"title": "Shell LNG business benefits from European energy security demand", "source": "FT Energy", "published": "16 Jun 2026", "summary": "Shell's LNG trading arm reported stronger-than-expected margins as European buyers locked in long-term contracts amid geopolitical uncertainty.", "url": "#", "sentiment_hint": "bullish"},
        ]

        return {
            "Technology": {
                "articles": articles_tech,
                "analysis": {
                    "signals": [
                        {"ticker": "NVDA", "company": "NVIDIA Corp.", "sentiment": "bullish", "conviction": 92, "rationale": "Record AI GPU demand with no supply constraint in sight", "key_themes": ["AI infrastructure", "data centre"], "time_horizon": "medium-term"},
                        {"ticker": "AAPL", "company": "Apple Inc.", "sentiment": "bullish", "conviction": 78, "rationale": "M4 Ultra silicon advantage strengthens premium hardware moat", "key_themes": ["silicon leadership", "margin expansion"], "time_horizon": "medium-term"},
                        {"ticker": "MSFT", "company": "Microsoft Corp.", "sentiment": "bullish", "conviction": 85, "rationale": "Azure AI revenue acceleration confirms enterprise monetisation", "key_themes": ["cloud AI", "enterprise SaaS"], "time_horizon": "short-term"},
                        {"ticker": "AMD", "company": "Advanced Micro Devices", "sentiment": "bullish", "conviction": 67, "rationale": "MI400 launch could capture share in price-sensitive AI training", "key_themes": ["AI GPU competition", "data centre"], "time_horizon": "long-term"},
                        {"ticker": "TSM", "company": "Taiwan Semiconductor", "sentiment": "neutral", "conviction": 55, "rationale": "Capacity expansion eases supply but tempers pricing power", "key_themes": ["fab expansion", "supply normalisation"], "time_horizon": "medium-term"},
                    ],
                    "summary": "The technology sector shows strong bullish momentum driven by AI infrastructure spending. NVIDIA and Microsoft are the standout names, with GPU demand and cloud AI monetisation both accelerating. AMD represents a speculative opportunity as it challenges NVIDIA's data centre dominance. Near-term risk centres on valuation — many names trade at significant premiums to historical multiples.",
                    "risks": ["AI spending normalisation if ROI disappoints enterprises", "Geopolitical risk to Taiwan Semiconductor supply chain", "Rising US interest rates compressing growth stock multiples"],
                    "sector_sentiment": "bullish",
                },
                "prices": {
                    "NVDA": fake_prices(875.0, trend=0.18),
                    "AAPL": fake_prices(192.0, trend=0.06),
                    "MSFT": fake_prices(415.0, trend=0.09),
                },
                "config": {"icon": "💻", "tickers": ["AAPL","MSFT","NVDA","GOOGL","META","AMD","TSM"], "color": "#388bfd"},
            },
            "Petroleum & Energy": {
                "articles": articles_oil,
                "analysis": {
                    "signals": [
                        {"ticker": "XOM", "company": "ExxonMobil Corp.", "sentiment": "bullish", "conviction": 71, "rationale": "Deepwater acquisition expands long-life production base at cycle lows", "key_themes": ["M&A", "upstream expansion"], "time_horizon": "long-term"},
                        {"ticker": "CVX", "company": "Chevron Corp.", "sentiment": "bullish", "conviction": 74, "rationale": "Permian record output supports robust FCF and dividend growth", "key_themes": ["shale production", "cash generation"], "time_horizon": "short-term"},
                        {"ticker": "SHEL", "company": "Shell PLC", "sentiment": "bullish", "conviction": 63, "rationale": "LNG margins benefiting from European long-term contract demand", "key_themes": ["LNG", "energy security"], "time_horizon": "medium-term"},
                        {"ticker": "BP", "company": "BP PLC", "sentiment": "neutral", "conviction": 44, "rationale": "Renewables pivot credible long-term but near-term margin dilutive", "key_themes": ["energy transition", "ESG"], "time_horizon": "long-term"},
                        {"ticker": "COP", "company": "ConocoPhillips", "sentiment": "bearish", "conviction": 58, "rationale": "OPEC+ supply increase and inventory build pressure short-term prices", "key_themes": ["oil price", "supply overhang"], "time_horizon": "short-term"},
                    ],
                    "summary": "Energy sector faces short-term headwinds from OPEC+ supply increases and rising US inventories, pressuring WTI toward $70. However, integrated majors with strong LNG and deepwater portfolios (Shell, ExxonMobil) appear more insulated. Chevron's Permian output record is a genuine positive for its FCF story. BP's transition narrative is credible but introduces near-term margin uncertainty.",
                    "risks": ["Further OPEC+ output increases depressing oil price", "Global recession reducing energy demand", "Policy risk from accelerated clean energy transition"],
                    "sector_sentiment": "neutral",
                },
                "prices": {
                    "XOM": fake_prices(108.0, trend=0.04),
                    "CVX": fake_prices(155.0, trend=0.05),
                    "SHEL": fake_prices(68.0, trend=0.03),
                },
                "config": {"icon": "⛽", "tickers": ["XOM","CVX","BP","SHEL","TTE","COP","SLB"], "color": "#d29922"},
            },
        }
