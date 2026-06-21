"""
Database — SQLite store for:
  1. Daily analysis snapshots (signals + articles)
  2. Actual stock outcomes (filled next trading day)
  3. Human evaluation scores (hallucination guard)
  4. Source reliability ratings
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "market_intel.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        -- Every time we run an analysis, we store a snapshot per signal
        CREATE TABLE IF NOT EXISTS analysis_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date      TEXT NOT NULL,          -- ISO date: 2026-06-21
            industry      TEXT NOT NULL,
            ticker        TEXT NOT NULL,
            company       TEXT,
            sentiment     TEXT,                   -- bullish / bearish / neutral
            conviction    INTEGER,                -- 0-100
            rationale     TEXT,
            key_themes    TEXT,                   -- JSON list
            time_horizon  TEXT,
            sector_summary TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        -- Article-level log (for hallucination review)
        CREATE TABLE IF NOT EXISTS article_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date      TEXT NOT NULL,
            industry      TEXT NOT NULL,
            title         TEXT,
            source        TEXT,
            url           TEXT,
            published     TEXT,
            summary       TEXT,
            sentiment_hint TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        -- Human spot-check: one article per day to review
        CREATE TABLE IF NOT EXISTS human_eval (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            eval_date       TEXT NOT NULL,         -- the day it was assigned
            article_id      INTEGER,               -- FK → article_log.id
            article_title   TEXT,
            article_summary TEXT,
            article_source  TEXT,
            haiku_sentiment TEXT,                  -- what Haiku said
            haiku_rationale TEXT,
            haiku_themes    TEXT,
            -- Human scores (filled in via UI)
            human_sentiment TEXT,                  -- bullish / bearish / neutral
            accuracy_score  INTEGER,               -- 1-5
            hallucination_flag INTEGER DEFAULT 0,  -- 1 = hallucination detected
            human_notes     TEXT,
            evaluated_at    TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        -- Actual market outcomes (filled next trading day)
        CREATE TABLE IF NOT EXISTS outcomes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_date   TEXT NOT NULL,         -- date of original signal
            ticker          TEXT NOT NULL,
            predicted_sentiment TEXT,
            predicted_conviction INTEGER,
            price_at_signal  REAL,
            price_next_day   REAL,
            price_1week      REAL,
            price_1month     REAL,
            actual_move_1d   REAL,                 -- % change next day
            actual_move_1w   REAL,
            actual_move_1m   REAL,
            signal_correct_1d INTEGER,             -- 1=correct, 0=wrong, NULL=pending
            signal_correct_1w INTEGER,
            signal_correct_1m INTEGER,
            updated_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(analysis_date, ticker)
        );

        -- Source reliability tracker
        CREATE TABLE IF NOT EXISTS source_ratings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name     TEXT NOT NULL UNIQUE,
            industry        TEXT,
            feed_url        TEXT,
            total_articles  INTEGER DEFAULT 0,
            user_rating     INTEGER,               -- 1-5 stars set by user
            avg_accuracy    REAL,                  -- computed from human_eval
            is_active       INTEGER DEFAULT 1,     -- 0 = disabled
            notes           TEXT,
            added_at        TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_date ON analysis_log(run_date);
        CREATE INDEX IF NOT EXISTS idx_outcomes_date ON outcomes(analysis_date);
        CREATE INDEX IF NOT EXISTS idx_eval_date ON human_eval(eval_date);
    """)
    conn.commit()
    conn.close()


# ── Write operations ───────────────────────────────────────────────────────────

def log_analysis(run_date: str, industry: str, articles: list[dict], analysis: dict):
    """Store signals and articles from one analysis run."""
    conn = get_conn()
    summary = analysis.get("summary", "")

    # Log each signal
    for sig in analysis.get("signals", []):
        conn.execute("""
            INSERT INTO analysis_log
              (run_date, industry, ticker, company, sentiment, conviction,
               rationale, key_themes, time_horizon, sector_summary)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            run_date, industry,
            sig.get("ticker", ""), sig.get("company", ""),
            sig.get("sentiment", "neutral"), sig.get("conviction", 50),
            sig.get("rationale", ""),
            json.dumps(sig.get("key_themes", [])),
            sig.get("time_horizon", ""),
            summary,
        ))

    # Log each article and collect IDs
    article_ids = []
    for art in articles:
        cur = conn.execute("""
            INSERT INTO article_log
              (run_date, industry, title, source, url, published, summary, sentiment_hint)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            run_date, industry,
            art.get("title",""), art.get("source",""), art.get("url",""),
            art.get("published",""), art.get("summary",""),
            art.get("sentiment_hint","neutral"),
        ))
        article_ids.append(cur.lastrowid)

    conn.commit()
    conn.close()
    return article_ids


def create_daily_eval(eval_date: str, article_id: int, article: dict,
                      haiku_sentiment: str, haiku_rationale: str, haiku_themes: list):
    """Create a human evaluation record for today's spot-check article."""
    conn = get_conn()
    # Only create one per day
    existing = conn.execute(
        "SELECT id FROM human_eval WHERE eval_date=?", (eval_date,)
    ).fetchone()
    if not existing:
        conn.execute("""
            INSERT INTO human_eval
              (eval_date, article_id, article_title, article_summary, article_source,
               haiku_sentiment, haiku_rationale, haiku_themes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            eval_date, article_id,
            article.get("title",""), article.get("summary",""), article.get("source",""),
            haiku_sentiment, haiku_rationale, json.dumps(haiku_themes),
        ))
        conn.commit()
    conn.close()


def save_human_eval(eval_date: str, human_sentiment: str, accuracy_score: int,
                    hallucination_flag: bool, notes: str):
    """Save the human's evaluation of today's spot-check article."""
    conn = get_conn()
    conn.execute("""
        UPDATE human_eval
        SET human_sentiment=?, accuracy_score=?, hallucination_flag=?,
            human_notes=?, evaluated_at=datetime('now')
        WHERE eval_date=?
    """, (human_sentiment, accuracy_score, int(hallucination_flag), notes, eval_date))
    conn.commit()
    conn.close()


def upsert_outcome(analysis_date: str, ticker: str, predicted_sentiment: str,
                   predicted_conviction: int, price_at_signal: Optional[float]):
    """Insert or update an outcome row (prices filled in later)."""
    conn = get_conn()
    conn.execute("""
        INSERT INTO outcomes (analysis_date, ticker, predicted_sentiment,
                              predicted_conviction, price_at_signal)
        VALUES (?,?,?,?,?)
        ON CONFLICT(analysis_date, ticker) DO UPDATE SET
          predicted_sentiment=excluded.predicted_sentiment,
          predicted_conviction=excluded.predicted_conviction,
          price_at_signal=COALESCE(excluded.price_at_signal, price_at_signal),
          updated_at=datetime('now')
    """, (analysis_date, ticker, predicted_sentiment, predicted_conviction, price_at_signal))
    conn.commit()
    conn.close()


def fill_outcome_prices(analysis_date: str, ticker: str,
                        price_next_day: Optional[float]=None,
                        price_1week: Optional[float]=None,
                        price_1month: Optional[float]=None):
    """Fill in actual prices once they are available."""
    conn = get_conn()
    row = conn.execute(
        "SELECT price_at_signal, predicted_sentiment FROM outcomes WHERE analysis_date=? AND ticker=?",
        (analysis_date, ticker)
    ).fetchone()
    if not row:
        conn.close()
        return

    base = row["price_at_signal"]

    def move(p):
        if base and p:
            return round((p - base) / base * 100, 2)
        return None

    def correct(pct, sentiment):
        if pct is None:
            return None
        if sentiment == "bullish":
            return 1 if pct > 0 else 0
        elif sentiment == "bearish":
            return 1 if pct < 0 else 0
        return None  # neutral — no binary correct/wrong

    sentiment = row["predicted_sentiment"]
    m1d = move(price_next_day)
    m1w = move(price_1week)
    m1m = move(price_1month)

    conn.execute("""
        UPDATE outcomes SET
          price_next_day=?, price_1week=?, price_1month=?,
          actual_move_1d=?, actual_move_1w=?, actual_move_1m=?,
          signal_correct_1d=?, signal_correct_1w=?, signal_correct_1m=?,
          updated_at=datetime('now')
        WHERE analysis_date=? AND ticker=?
    """, (
        price_next_day, price_1week, price_1month,
        m1d, m1w, m1m,
        correct(m1d, sentiment), correct(m1w, sentiment), correct(m1m, sentiment),
        analysis_date, ticker,
    ))
    conn.commit()
    conn.close()


def upsert_source(source_name: str, industry: str, feed_url: str):
    """Register a source if not already known."""
    conn = get_conn()
    conn.execute("""
        INSERT INTO source_ratings (source_name, industry, feed_url)
        VALUES (?,?,?)
        ON CONFLICT(source_name) DO UPDATE SET
          total_articles = total_articles + 1,
          updated_at = datetime('now')
    """, (source_name, industry, feed_url))
    conn.commit()
    conn.close()


def update_source_rating(source_name: str, rating: int, notes: str, is_active: int):
    conn = get_conn()
    conn.execute("""
        UPDATE source_ratings SET user_rating=?, notes=?, is_active=?, updated_at=datetime('now')
        WHERE source_name=?
    """, (rating, notes, is_active, source_name))
    conn.commit()
    conn.close()


# ── Read operations ────────────────────────────────────────────────────────────

def get_recent_analysis(days: int = 30) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(f"""
        SELECT run_date, industry, ticker, company, sentiment, conviction,
               rationale, time_horizon
        FROM analysis_log
        WHERE run_date >= date('now', '-{days} days')
        ORDER BY run_date DESC, conviction DESC
    """, conn)
    conn.close()
    return df


def get_outcomes_summary() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT
            ticker,
            COUNT(*) as total_signals,
            AVG(predicted_conviction) as avg_conviction,
            SUM(signal_correct_1d) as correct_1d,
            SUM(signal_correct_1w) as correct_1w,
            SUM(signal_correct_1m) as correct_1m,
            AVG(actual_move_1d) as avg_move_1d,
            AVG(actual_move_1w) as avg_move_1w
        FROM outcomes
        WHERE price_next_day IS NOT NULL
        GROUP BY ticker
        ORDER BY correct_1w DESC NULLS LAST
    """, conn)
    conn.close()
    return df


def get_eval_history() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT eval_date, article_source, haiku_sentiment, human_sentiment,
               accuracy_score, hallucination_flag, human_notes, evaluated_at
        FROM human_eval
        WHERE evaluated_at IS NOT NULL
        ORDER BY eval_date DESC
    """, conn)
    conn.close()
    return df


def get_pending_eval(today: str) -> Optional[dict]:
    """Return today's pending evaluation, if any."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM human_eval WHERE eval_date=?", (today,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_sources() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT source_name, industry, feed_url, total_articles,
               user_rating, is_active, notes, updated_at
        FROM source_ratings
        ORDER BY industry, source_name
    """, conn)
    conn.close()
    return df


def get_hallucination_stats() -> dict:
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*) as total_evals,
            SUM(hallucination_flag) as hallucinations,
            AVG(accuracy_score) as avg_accuracy,
            COUNT(CASE WHEN human_sentiment=haiku_sentiment THEN 1 END) as sentiment_matches
        FROM human_eval
        WHERE evaluated_at IS NOT NULL
    """).fetchone()
    conn.close()
    if not row or row["total_evals"] == 0:
        return {}
    r = dict(row)
    r["hallucination_rate"] = round(r["hallucinations"] / r["total_evals"] * 100, 1)
    r["sentiment_accuracy"] = round(r["sentiment_matches"] / r["total_evals"] * 100, 1)
    return r


def export_training_data() -> pd.DataFrame:
    """
    Export the combined dataset for future fine-tuning / analysis.
    Joins analysis signals with actual outcomes and human eval scores.
    """
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT
            a.run_date,
            a.industry,
            a.ticker,
            a.company,
            a.sentiment        AS predicted_sentiment,
            a.conviction       AS predicted_conviction,
            a.rationale,
            a.key_themes,
            a.time_horizon,
            a.sector_summary,
            o.price_at_signal,
            o.price_next_day,
            o.price_1week,
            o.price_1month,
            o.actual_move_1d,
            o.actual_move_1w,
            o.actual_move_1m,
            o.signal_correct_1d,
            o.signal_correct_1w,
            o.signal_correct_1m,
            -- Average human eval accuracy for this source/date
            (SELECT AVG(h.accuracy_score)
             FROM human_eval h
             WHERE h.eval_date = a.run_date) AS human_eval_score,
            (SELECT h.hallucination_flag
             FROM human_eval h
             WHERE h.eval_date = a.run_date) AS hallucination_on_date
        FROM analysis_log a
        LEFT JOIN outcomes o
          ON o.analysis_date = a.run_date AND o.ticker = a.ticker
        ORDER BY a.run_date DESC, a.industry, a.ticker
    """, conn)
    conn.close()
    return df


# Initialise DB on import
init_db()
