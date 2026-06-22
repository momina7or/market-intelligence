"""
Market Intelligence — Investment Advisor App
Multi-page Streamlit app with: Dashboard, Sources, Spot-Check, Database/Training export
"""

import streamlit as st
import json
import time
from datetime import datetime, date
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import io

from utils.news_fetcher import NewsFetcher, INDUSTRY_FEEDS
from utils.stock_fetcher import StockFetcher
from utils.claude_analyser import ClaudeAnalyser
from utils.data_store import DataStore
from utils.hallucination_guard import HallucinationGuard
from utils import supabase_db as db

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  /* ── Base ── */
  html,body,[class*="css"]{font-family:'Inter',sans-serif;}
  .stApp{background:#0d1117;color:#e6edf3;}
  p,span,label,div{color:#e6edf3;}
  h1,h2,h3,h4{color:#e6edf3 !important;}

  /* ── Sidebar ── */
  section[data-testid="stSidebar"]{background:#161b22;border-right:1px solid #21262d;}
  section[data-testid="stSidebar"] *{color:#e6edf3 !important;}
  section[data-testid="stSidebar"] input{background:#0d1117 !important;color:#e6edf3 !important;border:1px solid #30363d !important;border-radius:6px !important;}
  section[data-testid="stSidebar"] hr{border-color:#21262d !important;opacity:1 !important;}

  /* ── Main content inputs & widgets ── */
  .stTextInput input,.stTextArea textarea{background:#161b22 !important;color:#e6edf3 !important;border:1px solid #30363d !important;border-radius:8px !important;}
  .stTextInput label,.stTextArea label,.stSlider label,.stSelectbox label,.stRadio label,.stCheckbox label,.stToggle label{color:#c9d1d9 !important;}
  .stSelectbox > div > div{background:#161b22 !important;color:#e6edf3 !important;border:1px solid #30363d !important;}
  .stRadio [data-testid="stMarkdownContainer"] p{color:#c9d1d9 !important;}
  .stRadio div[role="radiogroup"] label{color:#c9d1d9 !important;}
  .stCheckbox label p{color:#c9d1d9 !important;}
  .stToggle label p{color:#c9d1d9 !important;}

  /* ── Spot-check eval form specifically ── */
  [data-testid="stForm"] label{color:#e6edf3 !important;}
  [data-testid="stForm"] p{color:#e6edf3 !important;}
  [data-testid="stForm"] .stRadio label{color:#c9d1d9 !important;}
  [data-testid="stForm"] .stSlider label{color:#c9d1d9 !important;}
  [data-testid="stForm"] textarea{background:#161b22 !important;color:#e6edf3 !important;border:1px solid #30363d !important;}

  /* ── Slider ── */
  .stSlider [data-baseweb="slider"] [role="slider"]{background:#388bfd !important;}
  .stSlider p{color:#c9d1d9 !important;}
  [data-testid="stSliderTickBarMin"],[data-testid="stSliderTickBarMax"]{color:#8b949e !important;}

  /* ── Buttons ── */
  div[data-testid="stButton"] button{background:#1f6feb !important;color:white !important;border:none !important;border-radius:8px !important;font-weight:600 !important;}
  div[data-testid="stButton"] button:hover{background:#388bfd !important;}
  button[kind="formSubmit"]{background:#1f6feb !important;color:white !important;border:none !important;border-radius:8px !important;font-weight:600 !important;padding:8px 20px !important;}

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"]{background:#161b22 !important;border-radius:8px !important;padding:4px !important;gap:4px !important;}
  .stTabs [data-baseweb="tab"]{color:#8b949e !important;border-radius:6px !important;font-size:.85rem !important;background:transparent !important;}
  .stTabs [aria-selected="true"]{background:#1f6feb !important;color:white !important;}
  .stTabs [data-baseweb="tab"]:hover{color:#e6edf3 !important;}

  /* ── Dataframes ── */
  .stDataFrame{border-radius:10px !important;overflow:hidden !important;border:1px solid #21262d !important;}
  .stDataFrame thead tr th{background:#161b22 !important;color:#79c0ff !important;font-size:.78rem !important;font-weight:600 !important;text-transform:uppercase !important;letter-spacing:.05em !important;padding:10px 14px !important;border-bottom:1px solid #21262d !important;}
  .stDataFrame tbody tr td{background:#0d1117 !important;color:#e6edf3 !important;font-size:.82rem !important;padding:8px 14px !important;border-bottom:1px solid #161b22 !important;}
  .stDataFrame tbody tr:hover td{background:#161b22 !important;}

  /* ── Alerts ── */
  .stAlert{border-radius:8px !important;}
  [data-testid="stNotification"]{background:#1c2128 !important;border:1px solid #30363d !important;color:#e6edf3 !important;}
  .stAlert p{color:#e6edf3 !important;}

  /* ── Expanders ── */
  [data-testid="stExpander"]{background:#161b22 !important;border:1px solid #21262d !important;border-radius:10px !important;}
  [data-testid="stExpander"] summary{color:#e6edf3 !important;}
  [data-testid="stExpander"] summary:hover{color:#79c0ff !important;}

  /* ── Custom components ── */
  .signal-card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px 20px;margin-bottom:12px;}
  .signal-card:hover{border-color:#388bfd;}
  .signal-card .ticker{font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:600;color:#79c0ff;}
  .signal-card .company{font-size:0.8rem;color:#8b949e;margin-bottom:8px;}
  .score-bar{height:4px;border-radius:2px;margin:8px 0;}
  .badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;}
  .badge-bullish{background:#0d4429;color:#3fb950;border:1px solid #238636;}
  .badge-bearish{background:#4d1f1f;color:#f85149;border:1px solid #da3633;}
  .badge-neutral{background:#1c2128;color:#8b949e;border:1px solid #30363d;}
  .badge-strong{background:#1a2e50;color:#388bfd;border:1px solid #1f6feb;}
  .badge-warn{background:#3d2e00;color:#d29922;border:1px solid #9e6a03;}
  .badge-ok{background:#0d4429;color:#3fb950;border:1px solid #238636;}
  .metric-box{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px 18px;text-align:center;}
  .metric-box .label{font-size:.75rem;color:#8b949e;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em;}
  .metric-box .value{font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;}
  .metric-box .green{color:#3fb950;} .metric-box .red{color:#f85149;} .metric-box .blue{color:#79c0ff;} .metric-box .yellow{color:#d29922;}
  .news-item{border-left:3px solid #21262d;padding:8px 14px;margin-bottom:8px;font-size:.85rem;}
  .news-item.bullish{border-left-color:#238636;} .news-item.bearish{border-left-color:#da3633;}
  .news-item .headline{color:#e6edf3;font-weight:500;}
  .news-item .meta{color:#8b949e;font-size:.75rem;margin-top:2px;}
  .section-title{font-size:.7rem;font-weight:600;color:#8b949e;letter-spacing:.1em;text-transform:uppercase;margin:20px 0 10px;}
  .eval-box{background:#161b22;border:1px solid #388bfd;border-radius:12px;padding:20px;margin:12px 0;}
  .source-row{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px;margin-bottom:8px;}

  /* ── Hide Streamlit chrome ── */
  #MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)


# ── Services ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_services():
    return {
        "news":   NewsFetcher(),
        "stocks": StockFetcher(),
        "claude": ClaudeAnalyser(),
        "store":  DataStore(),
        "guard":  HallucinationGuard(),
    }

svc = get_services()

INDUSTRIES = {
    "Technology":        {"icon":"💻","tickers":["AAPL","MSFT","NVDA","GOOGL","META","AMD","TSM"],"color":"#388bfd"},
    "Petroleum & Energy":{"icon":"⛽","tickers":["XOM","CVX","BP","SHEL","TTE","COP","SLB"],"color":"#d29922"},
    "Healthcare":        {"icon":"💊","tickers":["JNJ","UNH","PFE","MRK","ABBV","LLY","TMO"],"color":"#3fb950"},
    "Finance":           {"icon":"🏦","tickers":["JPM","BAC","GS","MS","BRK-B","V","MA"],"color":"#bc8cff"},
}


def badge(cls, text):
    return f'<span class="badge badge-{cls}">{text}</span>'

def metric_box(col, label, value, cls="blue"):
    col.markdown(f'<div class="metric-box"><div class="label">{label}</div><div class="value {cls}">{value}</div></div>', unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Market Intelligence")
    st.markdown("<div style='color:#8b949e;font-size:0.8rem;margin-bottom:16px'>Powered by Claude AI</div>", unsafe_allow_html=True)

    page = st.radio("", ["📊 Dashboard", "📰 Sources", "🔍 Spot-Check", "🗄️ Database"], label_visibility="collapsed")

    st.markdown("---")
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-…")
    if api_key:
        svc["claude"].set_api_key(api_key)
        svc["guard"].set_api_key(api_key)

    st.markdown("---")
    st.markdown('<div class="section-title">Industries</div>', unsafe_allow_html=True)
    selected_industries = [n for n, cfg in INDUSTRIES.items()
                           if st.checkbox(f"{cfg['icon']} {n}", value=(n in ["Technology","Petroleum & Energy"]))]

    st.markdown("---")
    articles_per_industry = st.slider("Articles per industry", 3, 15, 6)
    lookback_days = st.slider("Price lookback (days)", 7, 90, 30)
    demo_mode = st.toggle("Demo mode", value=True)
    run_btn = st.button("🔍 Run Analysis", disabled=(not api_key and not demo_mode))


# ── Session state defaults ─────────────────────────────────────────────────────
if "results" not in st.session_state: st.session_state.results = None
if "last_run" not in st.session_state: st.session_state.last_run = None
if "spot_check" not in st.session_state: st.session_state.spot_check = None

# ── Load from JSON file (written by GitHub Actions) ───────────────────────────
import os
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "latest_results.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.json")

def load_from_json():
    if not os.path.exists(RESULTS_FILE):
        return None
    try:
        with open(RESULTS_FILE) as f:
            payload = json.load(f)
        raw = payload.get("results", {})
        results = {}
        for industry, r in raw.items():
            cfg = INDUSTRIES.get(industry, r.get("config", {}))
            prices = {}
            for ticker in r.get("prices_snapshot", {}):
                df = svc["stocks"].fetch(ticker, days=30)
                if df is not None:
                    prices[ticker] = df
            results[industry] = {
                "articles": r.get("articles", []),
                "analysis": r.get("analysis", {}),
                "prices":   prices,
                "config":   cfg,
            }
            if not st.session_state.spot_check and r.get("spot_check"):
                st.session_state.spot_check = r["spot_check"]
        return results, payload.get("run_date"), payload.get("run_time")
    except Exception:
        return None

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []


# ── Run analysis ───────────────────────────────────────────────────────────────
def run_analysis():
    today = date.today().isoformat()

    if demo_mode:
        with st.spinner("Loading demo data…"):
            st.session_state.results = svc["store"].load_demo()
            st.session_state.last_run = datetime.now()
        return

    if not api_key:
        st.error("Enter your Anthropic API key to run live analysis.")
        return

    all_results = {}
    progress = st.progress(0, "Starting…")
    step = 1 / (len(selected_industries) * 3 + 1)
    p = 0.0

    for industry in selected_industries:
        cfg = INDUSTRIES[industry]

        progress.progress(p, f"📰 Fetching {industry} news…")
        articles = svc["news"].fetch(industry, limit=articles_per_industry)
        p += step

        progress.progress(p, f"🤖 Analysing with Claude…")
        analysis = svc["claude"].analyse_industry(industry, articles, cfg["tickers"])
        p += step

        # Hallucination auto-check
        analysis = svc["guard"].verify_analysis(industry, articles, analysis)

        # DB: log analysis + articles
        article_ids = db.log_analysis(today, industry, articles, analysis)

        # DB: log signals as pending outcomes
        prices_now = {}
        for sig in analysis.get("signals", []):
            ticker = sig["ticker"]
            df = svc["stocks"].fetch(ticker, days=2)
            price = float(df["Close"].iloc[-1]) if df is not None and not df.empty else None
            prices_now[ticker] = price
            db.upsert_outcome(today, ticker, sig["sentiment"], sig["conviction"], price)

        # Spot-check: pick one article for human review
        spot = svc["guard"].pick_spot_check_article(articles, analysis)
        if spot and article_ids:
            # Find the index of this article in the logged IDs
            art_idx = articles.index({k: v for k, v in spot.items() if k != "related_signal"} if spot.get("related_signal") else spot) if spot else 0
            art_id = article_ids[min(art_idx, len(article_ids)-1)]
            related = spot.get("related_signal") or {}
            db.create_daily_eval(
                today, art_id, spot,
                related.get("sentiment","neutral"),
                related.get("rationale",""),
                related.get("key_themes",[]),
            )

        if not st.session_state.spot_check and spot:
            st.session_state.spot_check = spot

        progress.progress(p, f"📊 Fetching prices…")
        prices = svc["stocks"].fetch_many(cfg["tickers"], days=lookback_days)
        p += step

        # Register sources in DB
        for art in articles:
            if art.get("source"):
                db.upsert_source(art["source"], industry, art.get("url",""))

        all_results[industry] = {"articles": articles, "analysis": analysis, "prices": prices, "config": cfg}

    progress.progress(1.0, "✅ Complete!")
    time.sleep(0.4)
    progress.empty()
    st.session_state.results = all_results
    st.session_state.last_run = datetime.now()
    svc["store"].save(all_results)

if run_btn:
    run_analysis()
elif st.session_state.results is None:
    # First: try loading from the GitHub Actions JSON file
    json_data = load_from_json()
    if json_data:
        st.session_state.results, run_date, run_time = json_data
        try:
            st.session_state.last_run = datetime.fromisoformat(run_time.replace("Z",""))
        except Exception:
            st.session_state.last_run = datetime.now()
        # Override demo_mode since we have real data
        demo_mode = False
    elif demo_mode:
        # Fall back to demo data if no JSON file exists yet
        with st.spinner("Loading demo data…"):
            st.session_state.results = svc["store"].load_demo()
            st.session_state.last_run = datetime.now()


results = st.session_state.results


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown("# Market Intelligence Dashboard")
    st.markdown("<div style='color:#8b949e;margin-bottom:24px'>News sentiment × price correlation</div>", unsafe_allow_html=True)

    m1,m2,m3,m4 = st.columns(4)

    if results:
        all_signals = []
        for ind, r in results.items():
            for sig in r["analysis"].get("signals", []):
                all_signals.append({**sig, "industry": ind})

        total_articles = sum(len(r["articles"]) for r in results.values())
        bullish = sum(1 for s in all_signals if s.get("sentiment")=="bullish")
        bearish = sum(1 for s in all_signals if s.get("sentiment")=="bearish")
        top = max(all_signals, key=lambda s: s.get("conviction",0), default=None)

        # Reliability badge
        reliability_vals = [r["analysis"].get("verification",{}).get("overall_reliability","") for r in results.values()]
        rel_counts = {v: reliability_vals.count(v) for v in ["high","medium","low","unknown"]}
        overall_rel = "high" if rel_counts.get("low",0)==0 and rel_counts.get("medium",0)<=1 else "medium" if rel_counts.get("low",0)==0 else "low"

        metric_box(m1,"Articles Analysed",str(total_articles))
        metric_box(m2,"Bullish Signals",str(bullish),"green")
        metric_box(m3,"Bearish Signals",str(bearish),"red")
        metric_box(m4,"Top Pick",top["ticker"] if top else "—")

        # Reliability strip
        rel_color = {"high":"green","medium":"yellow","low":"red"}.get(overall_rel,"blue")
        flags_all = [f for r in results.values() for f in r["analysis"].get("verification",{}).get("flags",[])]
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:10px 16px;margin:12px 0;display:flex;align-items:center;gap:12px;">
          <span style="font-size:.75rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em">AI Reliability</span>
          {badge(rel_color if rel_color!="yellow" else "warn", f"{'✓' if overall_rel=='high' else '⚠'} {overall_rel.upper()}")}
          <span style="font-size:.8rem;color:#8b949e">{len(flags_all)} flag{'s' if len(flags_all)!=1 else ''} raised · <a href="#" style="color:#388bfd">See Spot-Check tab for details</a></span>
        </div>""", unsafe_allow_html=True)

        if st.session_state.last_run:
            st.markdown(f"<div style='color:#8b949e;font-size:.75rem;text-align:right'>Updated {st.session_state.last_run.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

        # Signals
        st.markdown("---")
        st.markdown("### 🎯 Investment Signals")
        sorted_sigs = sorted(all_signals, key=lambda s: s.get("conviction",0), reverse=True)
        ca, cb = st.columns(2)
        for i, sig in enumerate(sorted_sigs[:8]):
            sentiment = sig.get("sentiment","neutral")
            conviction = sig.get("conviction",50)
            col_bar = "#3fb950" if sentiment=="bullish" else ("#f85149" if sentiment=="bearish" else "#8b949e")
            verified = sig.get("verified")
            ver_badge = badge("ok","✓ verified") if verified is True else (badge("warn","⚠ unverified") if verified is False else "")
            card = f"""<div class="signal-card">
              <div class="ticker">{sig.get('ticker','?')}</div>
              <div class="company">{sig.get('company','')}</div>
              <div>{badge(f'badge-{sentiment}' if sentiment != 'neutral' else 'neutral', sentiment)} &nbsp; {badge('strong',sig.get('industry',''))} &nbsp; {ver_badge}</div>
              <div class="score-bar" style="background:linear-gradient(90deg,{col_bar} {conviction}%,#21262d {conviction}%)"></div>
              <div style="font-size:.78rem;color:#8b949e">Conviction {conviction}% — {sig.get('rationale','')[:120]}</div>
            </div>"""
            (ca if i%2==0 else cb).markdown(card, unsafe_allow_html=True)

        # Per-industry expanders
        st.markdown("---")
        for industry, r in results.items():
            cfg = r["config"]
            with st.expander(f"{cfg['icon']} {industry}", expanded=(industry==list(results.keys())[0])):
                left, right = st.columns([1,2])
                with left:
                    st.markdown('<div class="section-title">Headlines</div>', unsafe_allow_html=True)
                    for art in r["articles"][:6]:
                        sc = art.get("sentiment_hint","neutral")
                        st.markdown(f"""<div class="news-item {sc}">
                          <div class="headline">{art.get('title','')[:90]}…</div>
                          <div class="meta">{art.get('source','')} · {art.get('published','')}</div>
                        </div>""", unsafe_allow_html=True)
                with right:
                    st.markdown('<div class="section-title">Price Charts</div>', unsafe_allow_html=True)
                    prices = r.get("prices",{})
                    ind_sigs = [s for s in all_signals if s.get("industry")==industry]
                    top_tickers = [s["ticker"] for s in sorted(ind_sigs, key=lambda x:x.get("conviction",0), reverse=True)][:3]
                    if not top_tickers: top_tickers = list(prices.keys())[:3]
                    valid = [t for t in top_tickers if t in prices]
                    if valid:
                        fig = make_subplots(rows=len(valid),cols=1,shared_xaxes=True,vertical_spacing=.06,subplot_titles=valid)
                        shades=[cfg["color"],"#e6edf3","#8b949e"]
                        for idx,ticker in enumerate(valid):
                            df=prices[ticker]; row=idx+1
                            c=shades[idx%len(shades)]
                            r2,g2,b2=int(c[1:3],16),int(c[3:5],16),int(c[5:7],16)
                            fig.add_trace(go.Scatter(x=df.index,y=df["Close"],name=ticker,
                                line=dict(color=c,width=2),fill="tozeroy",
                                fillcolor=f"rgba({r2},{g2},{b2},0.05)"),row=row,col=1)
                        fig.update_layout(height=250*len(valid),paper_bgcolor="#161b22",plot_bgcolor="#0d1117",
                            font=dict(color="#8b949e"),showlegend=False,margin=dict(l=10,r=10,t=30,b=10))
                        fig.update_xaxes(gridcolor="#21262d",showline=False,zeroline=False)
                        fig.update_yaxes(gridcolor="#21262d",showline=False,zeroline=False)
                        st.plotly_chart(fig,use_container_width=True)

                ver = r["analysis"].get("verification",{})
                if ver.get("flags"):
                    st.markdown(f"""<div style="background:#3d2e00;border:1px solid #9e6a03;border-radius:8px;padding:10px 14px;margin-top:8px;font-size:.82rem;color:#d29922">
                      ⚠ <strong>Verification flags:</strong> {' · '.join(ver['flags'])}
                    </div>""", unsafe_allow_html=True)

                summary = r["analysis"].get("summary","")
                if summary:
                    st.markdown(f"""<div style="background:#1c2128;border:1px solid #21262d;border-radius:10px;padding:14px 18px;margin-top:8px;font-size:.875rem;line-height:1.6;color:#c9d1d9">
                      🤖 <strong style="color:#79c0ff">Claude's Analysis</strong><br><br>{summary}
                    </div>""", unsafe_allow_html=True)

    else:
        for c in [m1,m2,m3,m4]: metric_box(c,"—","—")
        st.markdown("""<div style="text-align:center;padding:60px;color:#8b949e">
          <div style="font-size:3rem;margin-bottom:16px">📡</div>
          <div style="font-size:1.1rem;color:#e6edf3;margin-bottom:8px">Ready to analyse</div>
          <div>Enable demo mode or enter your API key and click Run Analysis</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SOURCES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📰 Sources":
    st.markdown("# News Sources")
    st.markdown("<div style='color:#8b949e;margin-bottom:24px'>Review, rate, and manage your data sources. Disable unreliable ones.</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 All Sources", "➕ Add Custom Source"])

    with tab1:
        # Build combined source list: configured feeds + anything in DB
        configured = []
        for industry, feeds in INDUSTRY_FEEDS.items():
            for url in feeds:
                name = url.split("/")[2].replace("www.","").replace("feeds.","").split(".")[0].title()
                configured.append({"source_name": name, "industry": industry, "feed_url": url, "configured": True})

        df_config = pd.DataFrame(configured).drop_duplicates("source_name")

        # Merge with DB ratings if available
        try:
            df_db = db.get_all_sources()
            if not df_db.empty:
                df_config = df_config.merge(df_db[["source_name","user_rating","is_active","notes","total_articles"]],
                                             on="source_name", how="left")
        except Exception:
            df_db = pd.DataFrame()

        # Filter controls
        col_f1, col_f2 = st.columns([2,1])
        with col_f1:
            filter_industry = st.selectbox("Filter by industry", ["All"] + list(INDUSTRIES.keys()))
        with col_f2:
            show_disabled = st.toggle("Show disabled", value=True)

        filtered = df_config.copy()
        if filter_industry != "All":
            filtered = filtered[filtered["industry"] == filter_industry]

        # Group by industry
        for industry in filtered["industry"].unique():
            ind_sources = filtered[filtered["industry"] == industry]
            cfg = INDUSTRIES.get(industry, {})
            st.markdown(f"### {cfg.get('icon','')} {industry}")

            for _, row in ind_sources.iterrows():
                is_active = bool(row.get("is_active", 1)) if pd.notna(row.get("is_active")) else True
                if not show_disabled and not is_active:
                    continue

                rating = int(row["user_rating"]) if pd.notna(row.get("user_rating")) else 0
                stars = "★" * rating + "☆" * (5 - rating) if rating else "Not rated"
                total = int(row["total_articles"]) if pd.notna(row.get("total_articles")) else 0
                status_badge = badge("ok","active") if is_active else badge("bearish","disabled")
                notes_text = row.get("notes","") or ""

                with st.expander(f"{row['source_name']} — {status_badge} {stars}", expanded=False):
                    st.markdown(f"**Feed URL:** `{row['feed_url']}`")
                    st.markdown(f"**Articles logged:** {total}")
                    if notes_text:
                        st.markdown(f"**Notes:** {notes_text}")

                    c1, c2, c3 = st.columns([1,1,2])
                    new_rating = c1.slider("Your rating", 1, 5, rating or 3, key=f"rat_{row['source_name']}")
                    new_active = c2.toggle("Active", value=is_active, key=f"act_{row['source_name']}")
                    new_notes = c3.text_input("Notes", value=notes_text, key=f"note_{row['source_name']}")

                    if st.button("💾 Save", key=f"save_{row['source_name']}"):
                        db.upsert_source(row["source_name"], industry, row["feed_url"])
                        db.update_source_rating(row["source_name"], new_rating, new_notes, int(new_active))
                        st.success("Saved!")
                        st.rerun()

            st.markdown("")

    with tab2:
        st.markdown("### Add a custom RSS feed")
        st.markdown("<div style='color:#8b949e;font-size:.875rem'>Any RSS or Atom feed works — paste the URL and we'll start pulling from it.</div>", unsafe_allow_html=True)
        new_url  = st.text_input("Feed URL", placeholder="https://example.com/rss.xml")
        new_name = st.text_input("Source name", placeholder="e.g. Bloomberg Energy")
        new_ind  = st.selectbox("Industry", list(INDUSTRIES.keys()))

        if st.button("Add Source"):
            if new_url and new_name:
                db.upsert_source(new_name, new_ind, new_url)
                st.success(f"Added **{new_name}**. It will be included in the next analysis run.")
            else:
                st.warning("Please fill in both URL and name.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SPOT-CHECK (hallucination guard)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Spot-Check":
    st.markdown("# Daily Spot-Check")
    st.markdown("<div style='color:#8b949e;margin-bottom:24px'>Read today's selected article yourself, then score Claude's interpretation. Builds a reliability track record over time.</div>", unsafe_allow_html=True)

    today_str = date.today().isoformat()

    # Try to get today's eval from DB first
    pending = db.get_pending_eval(today_str)
    spot = st.session_state.spot_check

    # ── Stats strip ────────────────────────────────────────────────────────────
    stats = db.get_hallucination_stats()
    s1, s2, s3, s4 = st.columns(4)
    metric_box(s1,"Total Evaluations", str(stats.get("total_evals",0) or 0))
    metric_box(s2,"Sentiment Match", f"{stats.get('sentiment_accuracy',0) or 0}%","green")
    metric_box(s3,"Avg Accuracy",f"{stats.get('avg_accuracy','—') or '—'}/5","blue")
    metric_box(s4,"Hallucination Rate",f"{stats.get('hallucination_rate',0) or 0}%","red")

    st.markdown("---")

    # ── Today's article ────────────────────────────────────────────────────────
    st.markdown("### 📄 Today's Article to Review")

    if pending and pending.get("evaluated_at"):
        st.success("✅ You've already submitted today's evaluation.")
        with st.expander("View what you submitted"):
            st.markdown(f"**Article:** {pending.get('article_title','')}")
            st.markdown(f"**Claude said:** {pending.get('haiku_sentiment','')} — {pending.get('haiku_rationale','')}")
            st.markdown(f"**You said:** {pending.get('human_sentiment','')} | Accuracy: {pending.get('accuracy_score','')}/5")
            if pending.get("hallucination_flag"):
                st.error("🚨 You flagged a hallucination on this article")
            if pending.get("human_notes"):
                st.markdown(f"**Your notes:** {pending.get('human_notes','')}")

    elif pending or spot:
        # Show the article for review
        article_title   = pending["article_title"]   if pending else spot.get("title","")
        article_summary = pending["article_summary"] if pending else spot.get("summary","")
        article_source  = pending["article_source"]  if pending else spot.get("source","")
        article_url     = spot.get("url","") if spot else ""
        haiku_sentiment = pending["haiku_sentiment"] if pending else (spot.get("related_signal",{}) or {}).get("sentiment","—")
        haiku_rationale = pending["haiku_rationale"] if pending else (spot.get("related_signal",{}) or {}).get("rationale","—")
        haiku_themes    = json.loads(pending["haiku_themes"]) if pending and pending.get("haiku_themes") else (spot.get("related_signal",{}) or {}).get("key_themes",[])

        col_art, col_claude = st.columns([3, 2])

        with col_art:
            st.markdown(f"""<div class="eval-box">
              <div style="font-size:.7rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">📰 {article_source}</div>
              <div style="font-size:1.05rem;font-weight:600;color:#e6edf3;margin-bottom:12px">{article_title}</div>
              <div style="font-size:.875rem;color:#c9d1d9;line-height:1.6">{article_summary}</div>
              {f'<div style="margin-top:12px"><a href="{article_url}" target="_blank" style="color:#388bfd;font-size:.8rem">→ Read full article</a></div>' if article_url else ''}
            </div>""", unsafe_allow_html=True)

        with col_claude:
            themes_html = " ".join([badge("strong", t) for t in haiku_themes]) if haiku_themes else "—"
            sent_color = {"bullish":"#3fb950","bearish":"#f85149","neutral":"#8b949e"}.get(haiku_sentiment,"#8b949e")
            st.markdown(f"""<div class="eval-box" style="border-color:#d29922">
              <div style="font-size:.7rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">🤖 Claude Haiku's Interpretation</div>
              <div style="font-size:.85rem;color:#8b949e;margin-bottom:6px">Sentiment</div>
              <div style="font-size:1.2rem;font-weight:700;color:{sent_color};margin-bottom:12px">{haiku_sentiment.upper()}</div>
              <div style="font-size:.85rem;color:#8b949e;margin-bottom:4px">Rationale</div>
              <div style="font-size:.875rem;color:#c9d1d9;margin-bottom:12px">{haiku_rationale}</div>
              <div style="font-size:.85rem;color:#8b949e;margin-bottom:6px">Key Themes</div>
              <div>{themes_html}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("### ✍️ Your Evaluation")
        st.markdown("<div style='color:#8b949e;font-size:.875rem;margin-bottom:16px'>After reading the article above, how did Claude do?</div>", unsafe_allow_html=True)

        ev1, ev2, ev3 = st.columns([1,1,2])
        human_sent = ev1.radio("Your sentiment read", ["bullish","bearish","neutral"], index=2)
        accuracy   = ev2.slider("Accuracy score", 1, 5, 3, help="1=completely wrong, 5=spot on")
        hall_flag  = ev3.toggle("🚨 Flag as hallucination", help="Claude invented something not in the article")
        notes      = st.text_area("Notes (optional)", placeholder="e.g. Claude missed the nuance that…", height=80)

        if st.button("Submit Evaluation"):
            db.save_human_eval(today_str, human_sent, accuracy, hall_flag, notes)
            st.success("✅ Evaluation saved! Check back tomorrow for a new article.")
            st.rerun()

    else:
        st.info("No spot-check article available yet. Run an analysis first (with a real API key) to generate today's article.")
        st.markdown("""
        <div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:24px;margin-top:16px">
          <div style="font-size:.875rem;color:#c9d1d9;line-height:1.8">
            <strong style="color:#79c0ff">How the spot-check works:</strong><br><br>
            Each time you run a live analysis, the system picks one article related to the highest-conviction signal 
            of the day. You read it here and score Claude's interpretation: did it get the sentiment right? 
            Did it invent facts not in the article?<br><br>
            Over time this builds a hallucination rate and accuracy score — shown in the metrics above — 
            so you know exactly how much to trust the AI's daily output.
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Evaluation history ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Evaluation History")
    hist_df = db.get_eval_history()
    if not hist_df.empty:
        # Colour code accuracy
        fig_hist = px.bar(hist_df, x="eval_date", y="accuracy_score",
                          color="hallucination_flag",
                          color_discrete_map={0:"#3fb950",1:"#f85149"},
                          title="Daily Accuracy Scores (red = hallucination flagged)",
                          labels={"accuracy_score":"Score (1-5)","eval_date":"Date","hallucination_flag":"Hallucination"})
        fig_hist.update_layout(paper_bgcolor="#161b22",plot_bgcolor="#0d1117",
                               font=dict(color="#8b949e"),showlegend=True,
                               margin=dict(t=40,b=10))
        fig_hist.update_xaxes(gridcolor="#21262d")
        fig_hist.update_yaxes(gridcolor="#21262d",range=[0,5])
        st.plotly_chart(fig_hist, use_container_width=True)

        st.dataframe(
            hist_df[["eval_date","article_source","haiku_sentiment","human_sentiment","accuracy_score","hallucination_flag"]].rename(columns={
                "eval_date":"Date","article_source":"Source","haiku_sentiment":"Claude's read",
                "human_sentiment":"Your read","accuracy_score":"Score","hallucination_flag":"Hallucination?"
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Evaluation history will appear here once you start submitting daily spot-checks.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DATABASE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗄️ Database":
    st.markdown("# Analysis Database")
    st.markdown("<div style='color:#8b949e;margin-bottom:24px'>Every signal, its actual stock outcome, and your evaluations — stored for training data.</div>", unsafe_allow_html=True)

    dbtab1, dbtab2, dbtab3 = st.tabs(["📊 Signal Accuracy", "📋 Full Log", "💾 Export Training Data"])

    # ── Signal accuracy ────────────────────────────────────────────────────────
    with dbtab1:
        outcomes_df = db.get_outcomes_summary()
        if outcomes_df.empty:
            st.info("Outcome data builds up as signals age past 1 day, 1 week, and 1 month. Keep running daily analyses — results appear here automatically.")
            st.markdown("""<div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:24px;margin-top:16px">
              <div style="font-size:.875rem;color:#c9d1d9;line-height:1.8">
                <strong style="color:#79c0ff">How outcomes are tracked:</strong><br><br>
                When you run an analysis, the current stock price is captured. The app then needs you to 
                run again the next day, week, and month so it can record the actual price movement and 
                determine if Claude's signal was correct.<br><br>
                After a few months you'll have a dataset showing which industries, tickers, and sentiment 
                patterns Haiku predicts most reliably — perfect for prompt engineering or fine-tuning.
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            # Accuracy chart
            outcomes_df["accuracy_1d"] = outcomes_df["correct_1d"] / outcomes_df["total_signals"] * 100
            outcomes_df["accuracy_1w"] = outcomes_df["correct_1w"] / outcomes_df["total_signals"] * 100
            fig_acc = go.Figure()
            fig_acc.add_trace(go.Bar(name="Next-day accuracy %", x=outcomes_df["ticker"], y=outcomes_df["accuracy_1d"], marker_color="#388bfd"))
            fig_acc.add_trace(go.Bar(name="1-week accuracy %",   x=outcomes_df["ticker"], y=outcomes_df["accuracy_1w"], marker_color="#3fb950"))
            fig_acc.update_layout(barmode="group",paper_bgcolor="#161b22",plot_bgcolor="#0d1117",
                                  font=dict(color="#8b949e"),title="Signal Accuracy by Ticker",
                                  margin=dict(t=40,b=10))
            fig_acc.update_xaxes(gridcolor="#21262d")
            fig_acc.update_yaxes(gridcolor="#21262d",range=[0,100])
            st.plotly_chart(fig_acc, use_container_width=True)

            st.dataframe(outcomes_df.rename(columns={
                "ticker":"Ticker","total_signals":"Signals","avg_conviction":"Avg Conviction",
                "correct_1d":"✓ Next Day","correct_1w":"✓ 1 Week",
                "avg_move_1d":"Avg Move 1D %","avg_move_1w":"Avg Move 1W %"
            }), use_container_width=True, hide_index=True)

    # ── Full analysis log ──────────────────────────────────────────────────────
    with dbtab2:
        days_back = st.slider("Show last N days", 7, 180, 30)
        log_df = db.get_recent_analysis(days=days_back)
        if log_df.empty:
            st.info("Analysis log is empty — run a live analysis to start populating it.")
        else:
            col_f1, col_f2 = st.columns(2)
            ind_filter = col_f1.selectbox("Industry", ["All"] + list(log_df["industry"].unique()))
            sent_filter = col_f2.selectbox("Sentiment", ["All","bullish","bearish","neutral"])
            filtered_log = log_df.copy()
            if ind_filter != "All": filtered_log = filtered_log[filtered_log["industry"]==ind_filter]
            if sent_filter != "All": filtered_log = filtered_log[filtered_log["sentiment"]==sent_filter]

            # Show clean columns only
            display_cols = ["run_date","industry","ticker","company","sentiment","conviction","rationale","time_horizon"]
            display_cols = [c for c in display_cols if c in filtered_log.columns]
            st.dataframe(
                filtered_log[display_cols].rename(columns={
                    "run_date":"Date","industry":"Industry","ticker":"Ticker","company":"Company",
                    "sentiment":"Sentiment","conviction":"Conviction %","rationale":"Rationale","time_horizon":"Horizon"
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date":         st.column_config.TextColumn(width="small"),
                    "Industry":     st.column_config.TextColumn(width="medium"),
                    "Ticker":       st.column_config.TextColumn(width="small"),
                    "Company":      st.column_config.TextColumn(width="medium"),
                    "Sentiment":    st.column_config.TextColumn(width="small"),
                    "Conviction %": st.column_config.NumberColumn(width="small", format="%d%%"),
                    "Rationale":    st.column_config.TextColumn(width="large"),
                    "Horizon":      st.column_config.TextColumn(width="small"),
                }
            )

            st.markdown(f"<div style='color:#8b949e;font-size:.8rem'>{len(filtered_log)} records shown</div>", unsafe_allow_html=True)

    # ── Export ────────────────────────────────────────────────────────────────
    with dbtab3:
        st.markdown("### Export Training Dataset")
        st.markdown("""<div style="font-size:.875rem;color:#c9d1d9;line-height:1.6;margin-bottom:16px">
        This export joins every signal with its actual stock outcome and your human evaluation scores.
        After a few months of daily use, this is the dataset you'd use to analyse Claude's weak spots,
        fine-tune prompts, or eventually fine-tune a model.
        </div>""", unsafe_allow_html=True)

        training_df = db.export_training_data()
        if training_df.empty:
            st.info("No data yet — run live analyses for a few days to start building the dataset.")
        else:
            st.markdown(f"**{len(training_df)} rows** across **{training_df['industry'].nunique()}** industries and **{training_df['ticker'].nunique()}** tickers")
            st.dataframe(training_df.head(20), use_container_width=True, hide_index=True)

            col_e1, col_e2 = st.columns(2)
            # CSV
            csv_buf = io.StringIO()
            training_df.to_csv(csv_buf, index=False)
            col_e1.download_button(
                "⬇️ Download CSV",
                data=csv_buf.getvalue(),
                file_name=f"market_intel_training_{date.today().isoformat()}.csv",
                mime="text/csv",
            )
            # JSON (fine-tuning format)
            def to_finetune_json(row):
                return {
                    "prompt": f"Industry: {row.get('industry','')}. Ticker: {row.get('ticker','')}. Rationale: {row.get('rationale','')}",
                    "completion": {
                        "sentiment": row.get("sentiment", row.get("predicted_sentiment","")),
                        "conviction": row.get("conviction", row.get("predicted_conviction",0)),
                        "correct_1d": row.get("signal_correct_1d"),
                        "correct_1w": row.get("signal_correct_1w"),
                    }
                }
            jsonl = "\n".join(json.dumps(to_finetune_json(row)) for _, row in training_df.iterrows())
            col_e2.download_button(
                "⬇️ Download JSONL (fine-tune format)",
                data=jsonl,
                file_name=f"market_intel_finetune_{date.today().isoformat()}.jsonl",
                mime="application/jsonl",
            )

        st.markdown("---")
        st.markdown("### 💡 What to do with this data")
        st.markdown("""<div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:20px;font-size:.875rem;color:#c9d1d9;line-height:1.8">
          <strong style="color:#79c0ff">After 1–3 months of daily use:</strong><br>
          • Identify which industries Haiku is most/least accurate for — adjust conviction thresholds<br>
          • Find patterns in hallucination flags — often tied to specific source types<br>
          • Use the JSONL export to fine-tune a model via Anthropic's fine-tuning API (when available)<br>
          • Run prompt experiments: edit <code>claude_analyser.py</code>, re-run for a week, compare accuracy<br><br>
          <strong style="color:#79c0ff">The human_eval_score column is gold:</strong> it's the ground truth signal that lets you separate 
          cases where Claude was confidently right vs confidently wrong — the most valuable training signal.
        </div>""", unsafe_allow_html=True)
