import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

# ================= PAGE CONFIG =================
st.set_page_config(page_title="StockSense (India First)", layout="wide")

# ================= UNIVERSAL INDIA-FIRST SEARCH (UNCHANGED) =================
@st.cache_data(ttl=86400)
def yahoo_search(query):
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 10, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers, timeout=5)
        data = res.json()

        results = []
        for q in data.get("quotes", []):
            symbol = q.get("symbol", "")
            name = q.get("longname") or q.get("shortname") or symbol
            exch = q.get("exchange", "")

            if symbol:
                results.append({
                    "name": name,
                    "ticker": symbol,
                    "exchange": exch
                })
        return results
    except:
        return []

def resolve_ticker(query):
    query = query.strip().upper()

    if " " not in query and len(query) <= 12:
        try:
            test = yf.Ticker(query).history(period="1d")
            if not test.empty:
                return query
        except:
            pass

    results = yahoo_search(query)
    if results:
        for r in results:
            if ".NS" in r["ticker"] or ".BO" in r["ticker"]:
                return r["ticker"]
        return results[0]["ticker"]

    nse_try = query.replace(" ", "") + ".NS"
    try:
        test = yf.download(nse_try, period="1mo", progress=False)
        if not test.empty:
            return nse_try
    except:
        pass

    return None

# ================= HEADER =================
st.title("📈 StockSense — Universal Stock Analysis")

# ================= SEARCH BAR =================
query = st.text_input("🔍 Search any Stock (HCL Technologies, RELIANCE, AAPL, TSLA)")

if query == "":
    st.info("Search a stock to begin.")
    st.stop()

ticker = resolve_ticker(query)

if ticker is None:
    st.error("Stock not found. Try full company name or ticker.")
    st.stop()

# ================= DATA FETCH =================
@st.cache_data
def fetch_data(ticker, period):
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# ================= CONTROL ROW (TIMEFRAME + CHART TYPE SAME LINE) =================
c1, c2 = st.columns([2, 2])

with c1:
    timeframe = st.radio(
        "Select Timeframe",
        ["1mo", "3mo", "6mo", "1y", "5y", "max"],
        horizontal=True
    )

with c2:
    chart_type = st.radio(
        "Chart Type",
        ["Line", "Candlestick"],
        horizontal=True
    )

data = fetch_data(ticker, timeframe)

if data.empty:
    st.error("No data available for this stock.")
    st.stop()

# ================= STOCK INFO (UNCHANGED) =================
stock = yf.Ticker(ticker)
info = stock.info

company = info.get("longName", ticker)
market_cap = info.get("marketCap", None)
pe = info.get("trailingPE", None)
eps = info.get("trailingEps", None)
beta = info.get("beta", None)
desc = info.get("longBusinessSummary", "No description available.")

# ================= HERO SECTION (TOP PRIORITY) =================
price = float(data["Close"].iloc[-1])
prev = float(data["Close"].iloc[-2]) if len(data) > 1 else price
change = price - prev
pct = (change / prev) * 100 if prev != 0 else 0

st.markdown(f"## {ticker}")
st.markdown(f"### ₹{price:.2f} ({change:+.2f} | {pct:+.2f}%)")

# ================= INDICATORS CALC (UNCHANGED) =================
data["SMA20"] = data["Close"].rolling(20).mean()
data["SMA50"] = data["Close"].rolling(50).mean()
data["EMA20"] = data["Close"].ewm(span=20).mean()

# ================= CHART LEFT + INDICATORS RIGHT (UI FIX ONLY) =================
left, right = st.columns([3, 1])

with right:
    st.subheader("📊 Indicators")
    show_sma = st.checkbox("SMA 20 & 50", value=False)
    show_ema = st.checkbox("EMA 20")
    show_volume = st.checkbox("Volume (Below Chart)", value=False)

with left:
    rows = 2 if show_volume else 1
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.75, 0.25] if show_volume else [1]
    )

    # Price Chart
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data["Close"],
            name="Price",
            line=dict(width=2)
        ), row=1, col=1)

    # Overlay Indicators (NOT separate graph)
    if show_sma:
        fig.add_trace(go.Scatter(x=data.index, y=data["SMA20"], name="SMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data["SMA50"], name="SMA 50"), row=1, col=1)

    if show_ema:
        fig.add_trace(go.Scatter(x=data.index, y=data["EMA20"], name="EMA 20"), row=1, col=1)

    # Volume BELOW chart (professional layout)
    if show_volume:
        fig.add_trace(go.Bar(
            x=data.index,
            y=data["Volume"],
            name="Volume",
            opacity=0.6
        ), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=700)
    st.plotly_chart(fig, use_container_width=True)

# ================= INVESTMENT SIMULATOR =================
st.subheader("💰 Investment Simulator")
mode = st.radio("Mode", ["Lumpsum", "SIP"], horizontal=True)

if mode == "Lumpsum":
    invest = st.number_input("Investment Amount (₹)", 100, 10000000, 10000)
    years = st.slider("Investment Duration (Years)", 1, 50, 5)

    start_price = float(data["Close"].iloc[0])
    final_value = invest * (price / start_price)
    profit = final_value - invest
    ret = (profit / invest) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Invested", f"₹{invest:,.0f}")
    c2.metric("Current Value", f"₹{final_value:,.0f}")
    c3.metric("Return", f"{ret:.2f}%")

else:
    sip = st.number_input("Monthly SIP (₹)", 500, 100000, 2000)
    years = st.slider("SIP Duration (Years)", 1, 50, 10)

    monthly = data.resample("M").last()
    total_invested = sip * len(monthly)
    units = sum(sip / p for p in monthly["Close"] if p > 0)
    value = units * price
    ret = ((value - total_invested) / total_invested) * 100 if total_invested > 0 else 0

    s1, s2, s3 = st.columns(3)
    s1.metric("Total Invested", f"₹{total_invested:,.0f}")
    s2.metric("Current Value", f"₹{value:,.0f}")
    s3.metric("Return", f"{ret:.2f}%")

# ================= PERFORMANCE =================
st.subheader("📊 Performance")
period_return = ((price - data["Close"].iloc[0]) / data["Close"].iloc[0]) * 100
high = info.get("fiftyTwoWeekHigh", "N/A")
low = info.get("fiftyTwoWeekLow", "N/A")
volume = int(data["Volume"].iloc[-1])

p1, p2, p3, p4 = st.columns(4)
p1.metric("Period Return", f"{period_return:.2f}%")
p2.metric("52W High", f"₹{high}")
p3.metric("52W Low", f"₹{low}")
p4.metric("Latest Volume", f"{volume:,}")

# ================= FUNDAMENTALS =================
st.subheader("📚 Fundamentals")
f1, f2, f3, f4 = st.columns(4)
f1.metric("Market Cap", f"₹{market_cap/1e7:,.0f} Cr" if market_cap else "N/A")
f2.metric("P/E Ratio", f"{pe:.2f}" if pe else "N/A")
f3.metric("EPS (TTM)", f"{eps:.2f}" if eps else "N/A")
f4.metric("Beta", f"{beta:.2f}" if beta else "N/A")

# ================= ABOUT =================
st.subheader("🏢 About Company")
st.write(desc)

