import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="StockSense India", layout="wide", page_icon="📈")

# ===== THEME =====
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

col_t, col_b = st.columns([9, 1])
with col_t:
    st.title("📈 StockSense — Universal Stock Analysis")
with col_b:
    st.write("")
    if st.button("☀️ Light" if st.session_state.dark_mode else "🌙 Dark"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

IS_DARK = st.session_state.dark_mode
THEME   = "plotly_dark" if IS_DARK else "plotly_white"
BG      = "#0e1117"     if IS_DARK else "#f8f9fa"
TEXT    = "#fafafa"     if IS_DARK else "#111111"
CARD    = "#1c1f26"     if IS_DARK else "#ffffff"
BORDER  = "#2e333d"     if IS_DARK else "#dee2e6"

st.markdown(f"""
<style>
  .stApp {{ background-color: {BG} !important; color: {TEXT} !important; }}
  .stApp p, .stApp label, .stApp span,
  .stApp h1, .stApp h2, .stApp h3 {{ color: {TEXT} !important; }}
  div[data-testid="metric-container"] {{
    background: {CARD}; border-radius: 10px; padding: 14px 18px;
  }}
  div[data-testid="metric-container"] label {{ color: {TEXT} !important; opacity:0.65; }}
  div[data-testid="metric-container"] div   {{ color: {TEXT} !important; }}
</style>""", unsafe_allow_html=True)

# ===== SEARCH =====
@st.cache_data(ttl=86400)
def yahoo_search(query):
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        p = {"q": query, "quotesCount": 10, "newsCount": 0}
        h = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=p, headers=h, timeout=5)
        out = []
        for q in r.json().get("quotes", []):
            sym = q.get("symbol", "")
            if sym:
                out.append({"name": q.get("longname") or q.get("shortname") or sym,
                            "ticker": sym, "exchange": q.get("exchange", "")})
        return out
    except:
        return []

def resolve_ticker(query):
    query = query.strip().upper()
    if " " not in query and len(query) <= 12:
        try:
            if not yf.Ticker(query).history(period="1d").empty:
                return query
        except:
            pass
    results = yahoo_search(query)
    if results:
        for r in results:
            if ".NS" in r["ticker"] or ".BO" in r["ticker"]:
                return r["ticker"]
        return results[0]["ticker"]
    nse = query.replace(" ", "") + ".NS"
    try:
        if not yf.download(nse, period="1mo", progress=False).empty:
            return nse
    except:
        pass
    return None

# ===== DATA =====
def _clean(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(c[0]).strip() for c in df.columns]
    elif not isinstance(df.columns[0], str):
        df.columns = [str(c[0]).strip() for c in df.columns]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    want = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
    df = df[want].copy()
    for col in df.columns:
        if isinstance(df[col], pd.DataFrame):
            df[col] = df[col].iloc[:, 0]
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"])

@st.cache_data(ttl=3600)
def get_data(ticker, period):
    try:
        df = yf.download(ticker, period=period, auto_adjust=True,
                         progress=False, multi_level_index=False)
    except TypeError:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    return _clean(df)

@st.cache_data(ttl=3600)
def get_max(ticker):
    try:
        df = yf.download(ticker, period="max", auto_adjust=True,
                         progress=False, multi_level_index=False)
    except TypeError:
        df = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    return _clean(df)

# ===== INDICATORS =====
def add_indicators(df):
    c = df["Close"].astype(float)
    df["SMA20"]    = c.rolling(20).mean()
    df["SMA50"]    = c.rolling(50).mean()
    df["EMA20"]    = c.ewm(span=20, adjust=False).mean()
    mid            = c.rolling(20).mean()
    std            = c.rolling(20).std()
    df["BB_upper"] = mid + 2*std
    df["BB_mid"]   = mid
    df["BB_lower"] = mid - 2*std
    delta          = c.diff()
    gain           = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss           = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"]      = 100 - 100/(1 + gain/loss.replace(0, np.nan))
    e12            = c.ewm(span=12, adjust=False).mean()
    e26            = c.ewm(span=26, adjust=False).mean()
    df["MACD"]     = e12 - e26
    df["MACD_sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_h"]   = df["MACD"] - df["MACD_sig"]
    return df

# ===== SEARCH BAR =====
query = st.text_input("🔍 Search any Stock  (e.g. RELIANCE, HCL Technologies, AAPL, TSLA)")
if not query:
    st.info("Search a stock to begin.")
    st.stop()

with st.spinner("Resolving ticker…"):
    ticker = resolve_ticker(query)
if not ticker:
    st.error("Stock not found.")
    st.stop()

# ===== CONTROLS =====
r1, r2 = st.columns([3,2])
with r1:
    timeframe = st.radio("Timeframe", ["1mo","3mo","6mo","1y","5y","max"], horizontal=True)
with r2:
    chart_type = st.radio("Chart Type", ["Line","Candlestick"], horizontal=True)

with st.spinner("Fetching data…"):
    data = get_data(ticker, timeframe)
if data.empty:
    st.error("No price data returned.")
    st.stop()
data = add_indicators(data)

# ===== META =====
info      = yf.Ticker(ticker).info
mc        = info.get("marketCap")
pe        = info.get("trailingPE")
eps       = info.get("trailingEps")
beta      = info.get("beta")
div_y     = info.get("dividendYield")
pb        = info.get("priceToBook")
de        = info.get("debtToEquity")
roe       = info.get("returnOnEquity")
rev       = info.get("totalRevenue")
pm        = info.get("profitMargins")
sector    = info.get("sector", "N/A")
industry  = info.get("industry", "N/A")
country   = info.get("country", "N/A")
desc      = info.get("longBusinessSummary", "No description available.")
avg_vol   = info.get("averageVolume")
wk52hi    = info.get("fiftyTwoWeekHigh", "N/A")
wk52lo    = info.get("fiftyTwoWeekLow", "N/A")

# ===== HERO =====
price = float(data["Close"].iloc[-1])
prev  = float(data["Close"].iloc[-2]) if len(data) > 1 else price
chg   = price - prev
pct   = (chg / prev * 100) if prev else 0
arrow = "▲" if chg >= 0 else "▼"
clr   = "#00c48c" if chg >= 0 else "#ef5350"

st.markdown(f"""
<div style="margin-bottom:6px">
  <span style="font-size:1.5rem;font-weight:700;color:{TEXT}">{ticker}</span>
  <span style="font-size:0.95rem;color:{TEXT};opacity:0.55;margin-left:12px">{sector} · {industry} · {country}</span>
</div>
<div style="margin-bottom:16px">
  <span style="font-size:2rem;font-weight:700;color:{TEXT}">₹{price:,.2f}</span>
  <span style="font-size:1.2rem;color:{clr};font-weight:600;margin-left:12px">{arrow} ₹{abs(chg):.2f} ({abs(pct):.2f}%)</span>
</div>""", unsafe_allow_html=True)
st.markdown("---")

# ===== CHART =====
left, right = st.columns([3,1])

with right:
    st.markdown("#### 📊 Overlays")
    show_sma  = st.checkbox("SMA 20 & 50")
    show_ema  = st.checkbox("EMA 20")
    show_bb   = st.checkbox("Bollinger Bands")
    st.markdown("#### 📉 Sub-panels")
    show_vol  = st.checkbox("Volume")
    show_rsi  = st.checkbox("RSI (14)")
    show_macd = st.checkbox("MACD")

with left:
    panels = []
    if show_vol:  panels.append("vol")
    if show_rsi:  panels.append("rsi")
    if show_macd: panels.append("macd")
    n  = 1 + len(panels)
    rh = [0.55] + [0.15]*len(panels) if panels else [1.0]
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=rh)

    # Convert to plain Python lists — 100% safe for every Plotly version
    idx = list(data.index)
    op  = [float(x) for x in data["Open"].tolist()]
    hi  = [float(x) for x in data["High"].tolist()]
    lo  = [float(x) for x in data["Low"].tolist()]
    cl  = [float(x) for x in data["Close"].tolist()]
    vol = [float(x) for x in data["Volume"].tolist()]

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=idx, open=op, high=hi, low=lo, close=cl, name="Price",
            increasing=dict(line=dict(color="#26a69a"), fillcolor="#26a69a"),
            decreasing=dict(line=dict(color="#ef5350"), fillcolor="#ef5350")
        ), row=1, col=1)
        fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=idx, y=cl, name="Price",
            line=dict(color="#5c8de8", width=2)), row=1, col=1)

    if show_sma:
        fig.add_trace(go.Scatter(x=idx, y=[float(x) for x in data["SMA20"].tolist()],
            name="SMA 20", line=dict(color="#f59e0b", width=1.5, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=idx, y=[float(x) for x in data["SMA50"].tolist()],
            name="SMA 50", line=dict(color="#a78bfa", width=1.5, dash="dot")), row=1, col=1)

    if show_ema:
        fig.add_trace(go.Scatter(x=idx, y=[float(x) for x in data["EMA20"].tolist()],
            name="EMA 20", line=dict(color="#34d399", width=1.5)), row=1, col=1)

    if show_bb:
        bbu = [float(x) for x in data["BB_upper"].tolist()]
        bbm = [float(x) for x in data["BB_mid"].tolist()]
        bbl = [float(x) for x in data["BB_lower"].tolist()]
        fig.add_trace(go.Scatter(x=idx, y=bbu, name="BB Upper",
            line=dict(color="#94a3b8", width=1, dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=idx, y=bbm, name="BB Mid",
            line=dict(color="#cbd5e1", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=idx, y=bbl, name="BB Lower",
            line=dict(color="#94a3b8", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(148,163,184,0.08)"), row=1, col=1)

    for i, p in enumerate(panels, start=2):
        if p == "vol":
            bc = ["#26a69a" if cl[j] >= cl[j-1] else "#ef5350" for j in range(len(cl))]
            fig.add_trace(go.Bar(x=idx, y=vol, name="Volume",
                marker_color=bc, opacity=0.75), row=i, col=1)
            fig.update_yaxes(title_text="Vol", row=i, col=1)
        elif p == "rsi":
            rsi_v = [float(x) for x in data["RSI"].tolist()]
            fig.add_trace(go.Scatter(x=idx, y=rsi_v, name="RSI",
                line=dict(color="#f97316", width=1.5)), row=i, col=1)
            fig.add_hline(y=70, line=dict(dash="dash", color="red",   width=0.8), row=i, col=1)
            fig.add_hline(y=30, line=dict(dash="dash", color="green", width=0.8), row=i, col=1)
            fig.update_yaxes(title_text="RSI", range=[0,100], row=i, col=1)
        elif p == "macd":
            mh = [float(x) for x in data["MACD_h"].tolist()]
            ml = [float(x) for x in data["MACD"].tolist()]
            ms = [float(x) for x in data["MACD_sig"].tolist()]
            hc = ["#26a69a" if v >= 0 else "#ef5350" for v in mh]
            fig.add_trace(go.Bar(x=idx, y=mh, name="Histogram",
                marker_color=hc, opacity=0.7), row=i, col=1)
            fig.add_trace(go.Scatter(x=idx, y=ml, name="MACD",
                line=dict(color="#60a5fa", width=1.5)), row=i, col=1)
            fig.add_trace(go.Scatter(x=idx, y=ms, name="Signal",
                line=dict(color="#f472b6", width=1.5)), row=i, col=1)
            fig.update_yaxes(title_text="MACD", row=i, col=1)

    fig.update_layout(template=THEME, height=420 + len(panels)*170,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=0,r=0,t=30,b=0), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ===== INVESTMENT SIMULATOR =====
st.subheader("💰 Investment Simulator")
mode = st.radio("Mode", ["Lumpsum","SIP"], horizontal=True)
max_data = get_max(ticker)

if mode == "Lumpsum":
    a1, a2 = st.columns(2)
    invest = a1.number_input("Investment Amount (₹)", 100, 10_000_000, 10_000, step=1000)
    years  = a2.slider("Investment Duration (Years)", 1, 50, 5)
    target = datetime.today() - timedelta(days=int(years*365.25))
    avail  = max_data[max_data.index >= pd.Timestamp(target)]
    if avail.empty:
        sp = float(max_data["Close"].iloc[0])
        st.caption(f"⚠️ Oldest data: {max_data.index[0].date()}")
    else:
        sp = float(avail["Close"].iloc[0])
    fv     = invest * (price / sp)
    profit = fv - invest
    ret    = (profit / invest) * 100
    m1, m2, m3 = st.columns(3)
    m1.metric("Invested",      f"₹{invest:,.0f}")
    m2.metric("Current Value", f"₹{fv:,.0f}", delta=f"₹{profit:+,.0f}")
    m3.metric("Return",        f"{ret:.2f}%")

else:
    b1, b2 = st.columns(2)
    sip   = b1.number_input("Monthly SIP (₹)", 500, 100_000, 2_000, step=500)
    years = b2.slider("SIP Duration (Years)", 1, 50, 10)
    sip_start = pd.Timestamp(datetime.today() - timedelta(days=int(years*365.25)))
    sip_df    = max_data[max_data.index >= sip_start]
    if sip_df.empty:
        st.warning("Not enough data.")
    else:
        monthly = sip_df["Close"].resample("MS").first().dropna()
        n_months = min(years * 12, len(monthly))
        monthly  = monthly.iloc[:n_months]
        total    = sip * n_months
        units    = sum(sip / float(p) for p in monthly if p > 0)
        value    = units * price
        profit   = value - total
        ret      = (profit / total) * 100 if total > 0 else 0
        s1, s2, s3 = st.columns(3)
        s1.metric("Total Invested", f"₹{total:,.0f}")
        s2.metric("Current Value",  f"₹{value:,.0f}", delta=f"₹{profit:+,.0f}")
        s3.metric("Return",         f"{ret:.2f}%")
        st.caption(f"Based on {n_months} monthly instalments of ₹{sip:,}")

st.markdown("---")

# ===== PERFORMANCE =====
st.subheader("📊 Performance")
per_ret = ((price - float(data["Close"].iloc[0])) / float(data["Close"].iloc[0])) * 100
cur_vol = int(data["Volume"].iloc[-1])
pp1,pp2,pp3,pp4,pp5 = st.columns(5)
pp1.metric("Period Return",  f"{per_ret:.2f}%")
pp2.metric("52W High",       f"₹{wk52hi}")
pp3.metric("52W Low",        f"₹{wk52lo}")
pp4.metric("Today Volume",   f"{cur_vol:,}")
pp5.metric("Avg Volume",     f"{avg_vol:,}" if avg_vol else "N/A")

st.markdown("---")

# ===== FUNDAMENTALS =====
st.subheader("📚 Fundamentals")

def fcr(v):  return f"₹{v/1e7:,.0f} Cr" if v else "N/A"
def fpct(v): return f"{v*100:.2f}%" if v else "N/A"
def f2(v):   return f"{v:.2f}" if v else "N/A"

r1 = st.columns(4)
r1[0].metric("Market Cap",     fcr(mc))
r1[1].metric("P/E Ratio",      f2(pe))
r1[2].metric("EPS (TTM)",      f2(eps))
r1[3].metric("Beta",           f2(beta))

r2 = st.columns(4)
r2[0].metric("Dividend Yield", fpct(div_y))
r2[1].metric("Price / Book",   f2(pb))
r2[2].metric("Debt / Equity",  f2(de))
r2[3].metric("ROE",            fpct(roe))

r3 = st.columns(4)
r3[0].metric("Total Revenue",  fcr(rev))
r3[1].metric("Profit Margin",  fpct(pm))
r3[2].metric("Sector",         sector)
r3[3].metric("Industry",       industry)

st.markdown("---")

# ===== ABOUT =====
st.subheader("🏢 About Company")
st.write(desc)
