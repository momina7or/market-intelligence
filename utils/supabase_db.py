"""
Supabase database layer — replaces SQLite database.py
Both the GitHub Action and Streamlit app connect to the same Supabase instance.
"""

import os
import json
from datetime import datetime
from typing import Optional
import pandas as pd
from supabase import create_client, Client

_client: Optional[Client] = None

def get_client() -> Client:
    global _client
    if _client is None:
        # Try Streamlit secrets first, then env vars, then hardcoded fallback
        try:
            import streamlit as st
            url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "https://beqwpuiqmtbposzlpmlv.supabase.co"))
            key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJlcXdwdWlxbXRicG9zemxwbWx2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIxMTc2NTgsImV4cCI6MjA5NzY5MzY1OH0.0ShxlCWQp3UbVZLTU4J-Lyph_a5rbpVS558DnZzf45A"))
        except Exception:
            url = os.environ.get("SUPABASE_URL", "https://beqwpuiqmtbposzlpmlv.supabase.co")
            key = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJlcXdwdWlxbXRicG9zemxwbWx2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIxMTc2NTgsImV4cCI6MjA5NzY5MzY1OH0.0ShxlCWQp3UbVZLTU4J-Lyph_a5rbpVS558DnZzf45A")
        _client = create_client(url, key)
    return _client


def init_tables():
    """
    Create tables via Supabase SQL editor — run this once manually.
    Paste the SQL below into: Supabase → SQL Editor → New query → Run
    """
    sql = """
    -- Analysis signals log
    CREATE TABLE IF NOT EXISTS analysis_log (
        id            BIGSERIAL PRIMARY KEY,
        run_date      TEXT NOT NULL,
        industry      TEXT NOT NULL,
        ticker        TEXT NOT NULL,
        company       TEXT,
        sentiment     TEXT,
        conviction    INTEGER,
        rationale     TEXT,
        key_themes    TEXT,
        time_horizon  TEXT,
        sector_summary TEXT,
        verified      BOOLEAN,
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );

    -- Article log
    CREATE TABLE IF NOT EXISTS article_log (
        id            BIGSERIAL PRIMARY KEY,
        run_date      TEXT NOT NULL,
        industry      TEXT NOT NULL,
        title         TEXT,
        source        TEXT,
        url           TEXT,
        published     TEXT,
        summary       TEXT,
        sentiment_hint TEXT,
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );

    -- Human spot-check evaluations
    CREATE TABLE IF NOT EXISTS human_eval (
        id              BIGSERIAL PRIMARY KEY,
        eval_date       TEXT NOT NULL UNIQUE,
        article_title   TEXT,
        article_summary TEXT,
        article_source  TEXT,
        haiku_sentiment TEXT,
        haiku_rationale TEXT,
        haiku_themes    TEXT,
        human_sentiment TEXT,
        accuracy_score  INTEGER,
        hallucination_flag BOOLEAN DEFAULT FALSE,
        human_notes     TEXT,
        evaluated_at    TIMESTAMPTZ,
        created_at      TIMESTAMPTZ DEFAULT NOW()
    );

    -- Stock outcomes
    CREATE TABLE IF NOT EXISTS outcomes (
        id                  BIGSERIAL PRIMARY KEY,
        analysis_date       TEXT NOT NULL,
        ticker              TEXT NOT NULL,
        predicted_sentiment TEXT,
        predicted_conviction INTEGER,
        price_at_signal     REAL,
        price_next_day      REAL,
        price_1week         REAL,
        price_1month        REAL,
        actual_move_1d      REAL,
        actual_move_1w      REAL,
        actual_move_1m      REAL,
        signal_correct_1d   INTEGER,
        signal_correct_1w   INTEGER,
        signal_correct_1m   INTEGER,
        updated_at          TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(analysis_date, ticker)
    );

    -- Source ratings
    CREATE TABLE IF NOT EXISTS source_ratings (
        id            BIGSERIAL PRIMARY KEY,
        source_name   TEXT NOT NULL UNIQUE,
        industry      TEXT,
        feed_url      TEXT,
        total_articles INTEGER DEFAULT 0,
        user_rating   INTEGER,
        is_active     BOOLEAN DEFAULT TRUE,
        notes         TEXT,
        updated_at    TIMESTAMPTZ DEFAULT NOW()
    );
    """
    print("Copy the SQL from utils/supabase_db.py init_tables() and run in Supabase SQL editor")
    return sql


# ── Write operations ───────────────────────────────────────────────────────────

def log_analysis(run_date: str, industry: str, articles: list, analysis: dict):
    """Store signals and articles from one analysis run."""
    sb = get_client()
    summary = analysis.get("summary", "")

    # Log signals
    for sig in analysis.get("signals", []):
        sb.table("analysis_log").insert({
            "run_date": run_date,
            "industry": industry,
            "ticker": sig.get("ticker", ""),
            "company": sig.get("company", ""),
            "sentiment": sig.get("sentiment", "neutral"),
            "conviction": sig.get("conviction", 50),
            "rationale": sig.get("rationale", ""),
            "key_themes": json.dumps(sig.get("key_themes", [])),
            "time_horizon": sig.get("time_horizon", ""),
            "sector_summary": summary,
            "verified": sig.get("verified"),
        }).execute()

    # Log articles
    article_ids = []
    for art in articles:
        resp = sb.table("article_log").insert({
            "run_date": run_date,
            "industry": industry,
            "title": art.get("title", ""),
            "source": art.get("source", ""),
            "url": art.get("url", ""),
            "published": art.get("published", ""),
            "summary": art.get("summary", ""),
            "sentiment_hint": art.get("sentiment_hint", "neutral"),
        }).execute()
        if resp.data:
            article_ids.append(resp.data[0]["id"])

    return article_ids


def create_daily_eval(eval_date: str, article: dict,
                      haiku_sentiment: str, haiku_rationale: str, haiku_themes: list):
    sb = get_client()
    # Only one per day
    existing = sb.table("human_eval").select("id").eq("eval_date", eval_date).execute()
    if not existing.data:
        sb.table("human_eval").insert({
            "eval_date": eval_date,
            "article_title": article.get("title", ""),
            "article_summary": article.get("summary", ""),
            "article_source": article.get("source", ""),
            "haiku_sentiment": haiku_sentiment,
            "haiku_rationale": haiku_rationale,
            "haiku_themes": json.dumps(haiku_themes),
        }).execute()


def save_human_eval(eval_date: str, human_sentiment: str, accuracy_score: int,
                    hallucination_flag: bool, notes: str):
    sb = get_client()
    sb.table("human_eval").update({
        "human_sentiment": human_sentiment,
        "accuracy_score": accuracy_score,
        "hallucination_flag": hallucination_flag,
        "human_notes": notes,
        "evaluated_at": datetime.utcnow().isoformat(),
    }).eq("eval_date", eval_date).execute()


def upsert_outcome(analysis_date: str, ticker: str, predicted_sentiment: str,
                   predicted_conviction: int, price_at_signal: Optional[float]):
    sb = get_client()
    sb.table("outcomes").upsert({
        "analysis_date": analysis_date,
        "ticker": ticker,
        "predicted_sentiment": predicted_sentiment,
        "predicted_conviction": predicted_conviction,
        "price_at_signal": price_at_signal,
    }, on_conflict="analysis_date,ticker").execute()


def upsert_source(source_name: str, industry: str, feed_url: str):
    sb = get_client()
    # Try update first, then insert
    existing = sb.table("source_ratings").select("id,total_articles").eq("source_name", source_name).execute()
    if existing.data:
        current = existing.data[0]["total_articles"] or 0
        sb.table("source_ratings").update({
            "total_articles": current + 1,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("source_name", source_name).execute()
    else:
        sb.table("source_ratings").insert({
            "source_name": source_name,
            "industry": industry,
            "feed_url": feed_url,
            "total_articles": 1,
        }).execute()


def update_source_rating(source_name: str, rating: int, notes: str, is_active: bool):
    sb = get_client()
    sb.table("source_ratings").update({
        "user_rating": rating,
        "notes": notes,
        "is_active": is_active,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("source_name", source_name).execute()


# ── Read operations ────────────────────────────────────────────────────────────

def get_recent_analysis(days: int = 30) -> pd.DataFrame:
    sb = get_client()
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    resp = sb.table("analysis_log").select("*").gte("run_date", since).order("run_date", desc=True).execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def get_outcomes_summary() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("outcomes").select("*").not_.is_("price_next_day", "null").execute()
    if not resp.data:
        return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    summary = df.groupby("ticker").agg(
        total_signals=("ticker", "count"),
        avg_conviction=("predicted_conviction", "mean"),
        correct_1d=("signal_correct_1d", "sum"),
        correct_1w=("signal_correct_1w", "sum"),
        avg_move_1d=("actual_move_1d", "mean"),
        avg_move_1w=("actual_move_1w", "mean"),
    ).reset_index()
    return summary


def get_eval_history() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("human_eval").select("*").not_.is_("evaluated_at", "null").order("eval_date", desc=True).execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def get_pending_eval(today: str) -> Optional[dict]:
    sb = get_client()
    resp = sb.table("human_eval").select("*").eq("eval_date", today).execute()
    return resp.data[0] if resp.data else None


def get_all_sources() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("source_ratings").select("*").order("industry").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


def get_hallucination_stats() -> dict:
    sb = get_client()
    resp = sb.table("human_eval").select("*").not_.is_("evaluated_at", "null").execute()
    if not resp.data:
        return {}
    evals = resp.data
    total = len(evals)
    hallucinations = sum(1 for e in evals if e.get("hallucination_flag"))
    accuracy_scores = [e["accuracy_score"] for e in evals if e.get("accuracy_score")]
    sentiment_matches = sum(
        1 for e in evals
        if e.get("human_sentiment") and e.get("haiku_sentiment")
        and e["human_sentiment"] == e["haiku_sentiment"]
    )
    return {
        "total_evals": total,
        "hallucinations": hallucinations,
        "hallucination_rate": round(hallucinations / total * 100, 1),
        "avg_accuracy": round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else None,
        "sentiment_accuracy": round(sentiment_matches / total * 100, 1),
    }


def export_training_data() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("analysis_log").select("*").order("run_date", desc=True).execute()
    if not resp.data:
        return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    # Join with outcomes
    out_resp = sb.table("outcomes").select("*").execute()
    if out_resp.data:
        out_df = pd.DataFrame(out_resp.data)
        df = df.merge(
            out_df[["analysis_date","ticker","price_at_signal","actual_move_1d",
                    "actual_move_1w","signal_correct_1d","signal_correct_1w"]],
            left_on=["run_date","ticker"],
            right_on=["analysis_date","ticker"],
            how="left"
        )
    return df
