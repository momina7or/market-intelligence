"""
Market Intelligence — Test Suite
Run with: python -m pytest tests/ -v
"""

import pytest
import json
import os
import sys
import pandas as pd
from datetime import date, datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.news_fetcher import NewsFetcher, INDUSTRY_FEEDS
from utils.stock_fetcher import StockFetcher
from utils.claude_analyser import ClaudeAnalyser
from utils.hallucination_guard import HallucinationGuard
from utils.data_store import DataStore


# ══════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_articles():
    return [
        {
            "title": "NVIDIA posts record revenue on AI chip demand",
            "summary": "NVIDIA reported $36bn quarterly revenue driven by H100 GPU demand from cloud providers.",
            "source": "Reuters",
            "published": "22 Jun 2026",
            "url": "https://reuters.com/test",
            "sentiment_hint": "bullish",
        },
        {
            "title": "Intel faces manufacturing delays",
            "summary": "Intel's 18A node rollout slips another quarter, ceding ground to TSMC.",
            "source": "Ars Technica",
            "published": "21 Jun 2026",
            "url": "https://arstechnica.com/test",
            "sentiment_hint": "bearish",
        },
        {
            "title": "Apple M4 chip benchmarks impress analysts",
            "summary": "Independent tests show Apple's M4 Ultra delivers 40% better performance per watt.",
            "source": "TechCrunch",
            "published": "20 Jun 2026",
            "url": "https://techcrunch.com/test",
            "sentiment_hint": "bullish",
        },
    ]

@pytest.fixture
def sample_analysis():
    return {
        "signals": [
            {
                "ticker": "NVDA",
                "company": "NVIDIA Corp.",
                "sentiment": "bullish",
                "conviction": 92,
                "rationale": "Record AI GPU demand with strong data centre growth",
                "key_themes": ["AI infrastructure", "data centre"],
                "time_horizon": "medium-term",
                "verified": True,
                "verification_issue": None,
            },
            {
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "sentiment": "bullish",
                "conviction": 78,
                "rationale": "M4 silicon advantage strengthens hardware moat",
                "key_themes": ["silicon", "margin expansion"],
                "time_horizon": "medium-term",
                "verified": True,
                "verification_issue": None,
            },
            {
                "ticker": "INTC",
                "company": "Intel Corp.",
                "sentiment": "bearish",
                "conviction": 65,
                "rationale": "Manufacturing delays cede market share to rivals",
                "key_themes": ["manufacturing", "market share loss"],
                "time_horizon": "short-term",
                "verified": True,
                "verification_issue": None,
            },
        ],
        "summary": "Technology sector shows mixed signals. AI infrastructure names remain strong while legacy chipmakers face headwinds.",
        "risks": ["Valuation compression", "Geopolitical risk to TSMC supply chain"],
        "sector_sentiment": "bullish",
        "verification": {
            "overall_reliability": "high",
            "flags": [],
            "ungrounded_count": 0,
        },
    }


# ══════════════════════════════════════════════════════════════════════
# NEWS FETCHER TESTS
# ══════════════════════════════════════════════════════════════════════

class TestNewsFetcher:

    def test_industry_feeds_defined(self):
        """All four industries have RSS feeds configured."""
        required = ["Technology", "Petroleum & Energy", "Healthcare", "Finance"]
        for ind in required:
            assert ind in INDUSTRY_FEEDS, f"Missing feeds for {ind}"
            assert len(INDUSTRY_FEEDS[ind]) > 0, f"No feeds for {ind}"

    def test_industry_feeds_are_urls(self):
        """All feed URLs start with http."""
        for industry, feeds in INDUSTRY_FEEDS.items():
            for url in feeds:
                assert url.startswith("http"), f"Invalid URL in {industry}: {url}"

    def test_article_normalisation_fields(self, sample_articles):
        """Normalised articles have all required fields."""
        required_fields = ["title", "summary", "source", "published", "url", "sentiment_hint"]
        for art in sample_articles:
            for field in required_fields:
                assert field in art, f"Missing field '{field}' in article"

    def test_article_sentiment_hint_valid(self, sample_articles):
        """Sentiment hints are valid values."""
        valid = {"bullish", "bearish", "neutral"}
        for art in sample_articles:
            assert art["sentiment_hint"] in valid, f"Invalid sentiment: {art['sentiment_hint']}"

    @patch("feedparser.parse")
    def test_fetch_handles_broken_feed(self, mock_parse):
        """Broken feeds are skipped silently."""
        mock_parse.side_effect = Exception("Connection error")
        fetcher = NewsFetcher()
        result = fetcher.fetch("Technology", limit=3)
        assert isinstance(result, list)  # Should return empty list, not crash

    def test_fetch_respects_limit(self):
        """Fetch never returns more than the requested limit."""
        fetcher = NewsFetcher()
        # Mock all feeds to return 10 articles each
        mock_entry = MagicMock()
        mock_entry.title = "Test article"
        mock_entry.summary = "Test summary"
        mock_entry.link = "https://example.com"
        mock_entry.published_parsed = None
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry] * 10

        with patch("feedparser.parse", return_value=mock_feed):
            result = fetcher.fetch("Technology", limit=5)
            assert len(result) <= 5


# ══════════════════════════════════════════════════════════════════════
# STOCK FETCHER TESTS
# ══════════════════════════════════════════════════════════════════════

class TestStockFetcher:

    def test_returns_none_for_invalid_ticker(self):
        """Invalid tickers return None gracefully."""
        fetcher = StockFetcher()
        with patch("yfinance.download") as mock_dl:
            mock_dl.return_value = pd.DataFrame()
            result = fetcher.fetch("INVALID_TICKER_XYZ", days=5)
            assert result is None

    def test_price_change_calculation(self):
        """Price change percentage is calculated correctly."""
        fetcher = StockFetcher()
        import numpy as np
        dates = pd.date_range("2026-01-01", periods=5, freq="B")
        df = pd.DataFrame({
            "Open":   [100.0, 101, 102, 103, 104],
            "High":   [105.0, 106, 107, 108, 109],
            "Low":    [99.0,  100, 101, 102, 103],
            "Close":  [100.0, 102, 104, 106, 110],
            "Volume": [1000000] * 5,
        }, index=dates)

        result = fetcher.get_price_change(df)
        assert result["start_price"] == 100.0
        assert result["end_price"] == 110.0
        assert result["change_pct"] == pytest.approx(10.0, 0.1)

    def test_price_change_empty_df(self):
        """Empty dataframe returns empty dict."""
        fetcher = StockFetcher()
        result = fetcher.get_price_change(pd.DataFrame())
        assert result == {}

    def test_fetch_many_returns_dict(self):
        """fetch_many returns a dict keyed by ticker."""
        fetcher = StockFetcher()
        tickers = ["AAPL", "MSFT"]
        dates = pd.date_range("2026-01-01", periods=3, freq="B")
        mock_df = pd.DataFrame({
            "Open": [100.0]*3, "High": [105.0]*3, "Low": [99.0]*3,
            "Close": [102.0]*3, "Volume": [1000000]*3
        }, index=dates)

        with patch.object(fetcher, "fetch", return_value=mock_df):
            result = fetcher.fetch_many(tickers, days=5)
            assert isinstance(result, dict)
            for ticker in tickers:
                assert ticker in result


# ══════════════════════════════════════════════════════════════════════
# CLAUDE ANALYSER TESTS
# ══════════════════════════════════════════════════════════════════════

class TestClaudeAnalyser:

    def test_requires_api_key(self):
        """Raises error when no API key set."""
        analyser = ClaudeAnalyser()
        with pytest.raises(RuntimeError, match="API key not set"):
            analyser.analyse_industry("Technology", [], ["AAPL"])

    def test_response_structure(self, sample_articles):
        """Claude response is parsed into expected structure."""
        analyser = ClaudeAnalyser()
        analyser.set_api_key("test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "signals": [
                {"ticker": "NVDA", "company": "NVIDIA", "sentiment": "bullish",
                 "conviction": 85, "rationale": "Strong AI demand",
                 "key_themes": ["AI"], "time_horizon": "medium-term"}
            ],
            "summary": "Tech sector bullish on AI.",
            "risks": ["Valuation risk"],
            "sector_sentiment": "bullish"
        }))]

        with patch.object(analyser._client or MagicMock(), "messages") as mock_msg:
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_response
                mock_anthropic.return_value = mock_client
                analyser._client = mock_client

                result = analyser.analyse_industry("Technology", sample_articles, ["NVDA", "AAPL"])

        assert "signals" in result
        assert "summary" in result
        assert "risks" in result

    def test_handles_malformed_json(self, sample_articles):
        """Malformed Claude response returns graceful fallback."""
        analyser = ClaudeAnalyser()
        analyser.set_api_key("test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON at all")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        analyser._client = mock_client

        result = analyser.analyse_industry("Technology", sample_articles, ["NVDA"])
        assert "signals" in result
        assert isinstance(result["signals"], list)

    def test_signal_sentiment_values(self, sample_analysis):
        """All signals have valid sentiment values."""
        valid = {"bullish", "bearish", "neutral"}
        for sig in sample_analysis["signals"]:
            assert sig["sentiment"] in valid

    def test_conviction_range(self, sample_analysis):
        """Conviction scores are between 0 and 100."""
        for sig in sample_analysis["signals"]:
            assert 0 <= sig["conviction"] <= 100

    def test_strips_markdown_fences(self):
        """JSON wrapped in markdown fences is parsed correctly."""
        analyser = ClaudeAnalyser()
        analyser.set_api_key("test-key")

        fenced = '```json\n{"signals":[],"summary":"test","risks":[],"sector_sentiment":"neutral"}\n```'
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=fenced)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        analyser._client = mock_client

        result = analyser.analyse_industry("Technology", [{"title":"test","summary":"test","source":"test","published":"","url":"","sentiment_hint":"neutral"}], ["AAPL"])
        assert result["summary"] == "test"


# ══════════════════════════════════════════════════════════════════════
# HALLUCINATION GUARD TESTS
# ══════════════════════════════════════════════════════════════════════

class TestHallucinationGuard:

    def test_returns_analysis_unchanged_without_client(self, sample_articles, sample_analysis):
        """Guard returns analysis unchanged if no API key set."""
        guard = HallucinationGuard()
        result = guard.verify_analysis("Technology", sample_articles, sample_analysis)
        assert result == sample_analysis

    def test_pick_spot_check_returns_article(self, sample_articles, sample_analysis):
        """Spot check picks an article related to top signal."""
        guard = HallucinationGuard()
        spot = guard.pick_spot_check_article(sample_articles, sample_analysis)
        assert spot is not None
        assert "title" in spot

    def test_pick_spot_check_empty_articles(self):
        """Spot check returns None for empty article list."""
        guard = HallucinationGuard()
        result = guard.pick_spot_check_article([], {})
        assert result is None

    def test_verification_annotates_signals(self, sample_articles, sample_analysis):
        """Verification adds verified field to each signal."""
        guard = HallucinationGuard()
        guard.set_api_key("test-key")

        mock_verification = {
            "verifications": [
                {"ticker": "NVDA", "grounded": True, "supporting_article_index": 0, "issue": None},
                {"ticker": "AAPL", "grounded": True, "supporting_article_index": 2, "issue": None},
                {"ticker": "INTC", "grounded": False, "supporting_article_index": None,
                 "issue": "No article mentions Intel delays"},
            ],
            "overall_reliability": "medium",
            "flags": ["INTC rationale not grounded in articles"],
        }

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(mock_verification))]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        guard._client = mock_client

        result = guard.verify_analysis("Technology", sample_articles, sample_analysis.copy())

        for sig in result["signals"]:
            assert "verified" in sig
        assert "verification" in result
        assert result["verification"]["overall_reliability"] == "medium"

    def test_reliability_score_empty(self):
        """Reliability score handles empty eval history."""
        guard = HallucinationGuard()
        result = guard.compute_reliability_score([])
        assert result["total_evals"] == 0
        assert result["hallucination_rate"] is None

    def test_reliability_score_calculation(self):
        """Reliability score calculates correctly from eval history."""
        guard = HallucinationGuard()
        evals = [
            {"hallucination_flag": False, "accuracy_score": 4, "human_sentiment": "bullish", "haiku_sentiment": "bullish"},
            {"hallucination_flag": False, "accuracy_score": 5, "human_sentiment": "bearish", "haiku_sentiment": "bearish"},
            {"hallucination_flag": True,  "accuracy_score": 2, "human_sentiment": "neutral", "haiku_sentiment": "bullish"},
        ]
        result = guard.compute_reliability_score(evals)
        assert result["total_evals"] == 3
        assert result["hallucination_rate"] == pytest.approx(33.3, 0.1)
        assert result["avg_accuracy"] == pytest.approx(3.67, 0.1)
        assert result["sentiment_match_rate"] == pytest.approx(66.7, 0.1)


# ══════════════════════════════════════════════════════════════════════
# DATA STORE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestDataStore:

    def test_demo_data_structure(self):
        """Demo data has correct structure for all industries."""
        store = DataStore()
        demo = store.load_demo()

        assert isinstance(demo, dict)
        assert len(demo) > 0

        for industry, r in demo.items():
            assert "articles" in r, f"Missing articles in {industry}"
            assert "analysis" in r, f"Missing analysis in {industry}"
            assert "prices" in r, f"Missing prices in {industry}"
            assert "config" in r, f"Missing config in {industry}"

    def test_demo_articles_have_required_fields(self):
        """Demo articles all have required fields."""
        store = DataStore()
        demo = store.load_demo()
        required = ["title", "summary", "source", "published", "url", "sentiment_hint"]

        for industry, r in demo.items():
            for art in r["articles"]:
                for field in required:
                    assert field in art, f"Missing '{field}' in {industry} article"

    def test_demo_signals_have_required_fields(self):
        """Demo signals all have required fields."""
        store = DataStore()
        demo = store.load_demo()
        required = ["ticker", "company", "sentiment", "conviction", "rationale"]

        for industry, r in demo.items():
            for sig in r["analysis"].get("signals", []):
                for field in required:
                    assert field in sig, f"Missing '{field}' in {industry} signal"

    def test_demo_prices_are_dataframes(self):
        """Demo prices are proper DataFrames with OHLCV columns."""
        store = DataStore()
        demo = store.load_demo()

        for industry, r in demo.items():
            for ticker, df in r["prices"].items():
                assert isinstance(df, pd.DataFrame), f"{ticker} prices not a DataFrame"
                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    assert col in df.columns, f"Missing {col} in {ticker} prices"

    def test_demo_conviction_in_range(self):
        """All demo conviction scores are 0-100."""
        store = DataStore()
        demo = store.load_demo()
        for industry, r in demo.items():
            for sig in r["analysis"].get("signals", []):
                assert 0 <= sig["conviction"] <= 100


# ══════════════════════════════════════════════════════════════════════
# APP.PY STRUCTURE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestAppStructure:

    def test_app_py_exists(self):
        """app.py exists at root level."""
        assert os.path.exists("app.py") or os.path.exists(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        )

    def test_app_py_syntax(self):
        """app.py has valid Python syntax."""
        import ast
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        with open(app_path) as f:
            source = f.read()
        # Should not raise
        ast.parse(source)

    def test_all_utils_importable(self):
        """All utils modules import without error."""
        from utils import news_fetcher
        from utils import stock_fetcher
        from utils import claude_analyser
        from utils import hallucination_guard
        from utils import data_store

    def test_css_contains_dark_theme(self):
        """CSS defines dark theme background."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        with open(app_path) as f:
            content = f.read()
        assert "#0d1117" in content, "Dark background colour missing from CSS"
        assert "stSidebar" in content, "Sidebar CSS missing"

    def test_css_covers_form_elements(self):
        """CSS explicitly styles form elements for dark theme."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        with open(app_path) as f:
            content = f.read()
        assert "stRadio" in content, "Radio button CSS missing"
        assert "stCheckbox" in content, "Checkbox CSS missing"
        assert "stSlider" in content, "Slider CSS missing"
        assert "stTextInput" in content, "Text input CSS missing"

    def test_four_pages_defined(self):
        """All four navigation pages are defined."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        with open(app_path) as f:
            content = f.read()
        assert "Dashboard" in content
        assert "Sources" in content
        assert "Spot-Check" in content
        assert "Database" in content

    def test_industries_defined(self):
        """All four industries are configured."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
        with open(app_path) as f:
            content = f.read()
        for industry in ["Technology", "Petroleum & Energy", "Healthcare", "Finance"]:
            assert industry in content, f"Industry '{industry}' missing from app.py"

    def test_requirements_includes_supabase(self):
        """requirements.txt includes supabase."""
        req_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
        with open(req_path) as f:
            content = f.read()
        assert "supabase" in content


# ══════════════════════════════════════════════════════════════════════
# DAILY RUN TESTS
# ══════════════════════════════════════════════════════════════════════

class TestDailyRun:

    def test_daily_run_syntax(self):
        """daily_run.py has valid Python syntax."""
        import ast
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daily_run.py")
        with open(path) as f:
            source = f.read()
        ast.parse(source)

    def test_daily_run_exits_without_api_key(self):
        """daily_run exits with code 1 if ANTHROPIC_API_KEY not set."""
        import subprocess
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daily_run.py")
        result = subprocess.run(
            [sys.executable, path],
            env=env, capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "ANTHROPIC_API_KEY" in result.stdout

    def test_output_files_defined(self):
        """daily_run.py defines OUTPUT_FILE and HISTORY_FILE."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daily_run.py")
        with open(path) as f:
            content = f.read()
        assert "OUTPUT_FILE" in content
        assert "HISTORY_FILE" in content
        assert "latest_results.json" in content
        assert "history.json" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
