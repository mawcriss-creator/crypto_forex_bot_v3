"""
Crypto & Forex Bot V3 — Research / Paper Mode with Real Data
SAFE DEFAULT: Uses real market data from Binance but does NOT place real orders.
"""

import streamlit as st
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timezone

st.set_page_config(page_title="Crypto & Forex Bot V3", page_icon="📈", layout="wide")
st.title("📈 Crypto & Forex Bot V3")
st.caption("RESEARCH / PAPER MODE • Real market data • No live orders")
st.info("This version uses real data from Binance. It still does **not** place any real trades.")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Settings")
    pair = st.selectbox("Instrument", ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"])
    timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"], index=0)
    limit = st.slider("Number of candles", 100, 1000, 500)

    st.subheader("Strategy Parameters")
    fast_n = st.slider("Fast EMA", 5, 30, 9)
    slow_n = st.slider("Slow EMA", 15, 80, 21)
    trend_n = st.slider("Trend EMA", 30, 150, 50)
    rsi_filter = st.checkbox("Use RSI confirmation", value=True)
    rsi_buy_max = st.slider("Max RSI for BUY", 55, 80, 70)
    rsi_sell_min = st.slider("Min RSI for SELL", 20, 45, 30)

    st.caption("Still in Paper Mode – no real orders will be sent.")

# ====================== FETCH REAL DATA ======================
@st.cache_data(ttl=300)  # cache for 5 minutes
def fetch_ohlcv(symbol, timeframe, limit):
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["Time", "Open", "High", "Low", "Close", "Volume"])
        df["Time"] = pd.to_datetime(df["Time"], unit="ms", utc=True)
        return df
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return None

df = fetch_ohlcv(pair, timeframe, limit)

if df is None or df.empty:
    st.stop()

# ====================== INDICATORS ======================
df["EMA Fast"] = df["Close"].ewm(span=fast_n, adjust=False).mean()
df["EMA Slow"] = df["Close"].ewm(span=slow_n, adjust=False).mean()
df["EMA Trend"] = df["Close"].ewm(span=trend_n, adjust=False).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)

prev_close = df["Close"].shift(1)
tr = pd.concat([
    (df["High"] - df["Low"]),
    (df["High"] - prev_close).abs(),
    (df["Low"] - prev_close).abs()
], axis=1).max(axis=1)
df["ATR"] = tr.rolling(14).mean().bfill()

# Trend & Signal
df["Trend"] = np.where(
    (df["Close"] > df["EMA Trend"]) & (df["EMA Fast"] > df["EMA Slow"]), "UP",
    np.where(
        (df["Close"] < df["EMA Trend"]) & (df["EMA Fast"] < df["EMA Slow"]), "DOWN", "MIXED"
    )
)

df["Signal"] = "HOLD"
for i in range(1, len(df)):
    up_cross = df["EMA Fast"].iloc[i] > df["EMA Slow"].iloc[i] and df["EMA Fast"].iloc[i-1] <= df["EMA Slow"].iloc[i-1]
    down_cross = df["EMA Fast"].iloc[i] < df["EMA Slow"].iloc[i] and df["EMA Fast"].iloc[i-1] >= df["EMA Slow"].iloc[i-1]

    buy_ok = df["Trend"].iloc[i] == "UP" and (not rsi_filter or 40 <= df["RSI"].iloc[i] <= rsi_buy_max)
    sell_ok = df["Trend"].iloc[i] == "DOWN" and (not rsi_filter or rsi_sell_min <= df["RSI"].iloc[i] <= 60)

    if up_cross and buy_ok:
        df.loc[df.index[i], "Signal"] = "BUY"
    elif down_cross and sell_ok:
        df.loc[df.index[i], "Signal"] = "SELL"

# ====================== DISPLAY ======================
latest = df.iloc[-1]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest Close", f"{latest['Close']:,.2f}")
col2.metric("Trend", latest["Trend"])
col3.metric("Current Signal", latest["Signal"])
col4.metric("RSI", f"{latest['RSI']:.1f}")

st.subheader("Price + EMAs")
st.line_chart(df.set_index("Time")[["Close", "EMA Fast", "EMA Slow", "EMA Trend"]].tail(300), height=350)

st.subheader("Recent Signals")
signals = df[df["Signal"] != "HOLD"][["Time", "Close", "Trend", "RSI", "Signal"]].tail(20)
if not signals.empty:
    st.dataframe(signals, use_container_width=True, hide_index=True)
else:
    st.info("No BUY/SELL signals in the selected period with current filters.")

st.warning("This is still **Paper / Research Mode**. No real orders are being sent.")
