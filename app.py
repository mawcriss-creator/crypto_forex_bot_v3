"""
Crypto & Forex Bot V3 — research / paper-trading lab.
SAFE DEFAULT: generated sample data, no live broker/exchange connection, no real orders.

Features:
- Trend regime filter (fast/slow/long EMA)
- RSI confirmation
- ATR-based stop and target illustration
- Position sizing by risk budget
- Daily loss lockout
- Synthetic backtest with fees/slippage assumptions
- Equity curve, trade log, basic performance metrics
- Paper trade controls
Run: streamlit run app.py
"""
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Crypto & Forex Bot V3", page_icon="📈", layout="wide")
st.title("📈 Crypto & Forex Bot V3")
st.caption("RESEARCH / PAPER MODE • Sample data only • No live orders")
st.info("This is a research prototype, not a perfect or proven profitable system. The market series below is synthetic and must not be mistaken for live prices.")

with st.sidebar:
    st.header("Strategy")
    pair = st.selectbox("Instrument", ["BTC/USDT", "ETH/USDT", "EUR/USD", "GBP/USD", "USD/JPY"])
    seed = st.number_input("Synthetic data seed", min_value=1, max_value=99999, value=2026, step=1)
    starting_balance = st.number_input("Starting virtual balance ($)", min_value=100.0, max_value=1000000.0, value=1000.0, step=100.0)
    risk_pct = st.slider("Risk budget per trade (%)", 0.25, 1.5, 0.5, 0.25)
    daily_loss_pct = st.slider("Daily loss lockout (%)", 1.0, 5.0, 2.0, 0.5)
    fast_n = st.slider("Fast EMA", 5, 30, 9)
    slow_n = st.slider("Slow EMA", 15, 80, 21)
    trend_n = st.slider("Trend EMA", 30, 150, 50)
    rsi_filter = st.checkbox("Use RSI confirmation", value=True)
    rsi_buy_max = st.slider("Maximum RSI for BUY", 55, 80, 70)
    rsi_sell_min = st.slider("Minimum RSI for SELL", 20, 45, 30)
    atr_stop_mult = st.slider("Stop distance (ATR multiple)", 1.0, 4.0, 2.0, 0.5)
    reward_risk = st.slider("Target / risk ratio", 1.0, 3.0, 2.0, 0.5)
    fee_bps = st.slider("Assumed fee per side (basis points)", 0, 20, 5)
    slippage_bps = st.slider("Assumed slippage per side (basis points)", 0, 20, 5)
    st.caption("Settings are for testing only. Synthetic data is not a substitute for real historical candles.")

if fast_n >= slow_n:
    st.error("Fast EMA should be lower than slow EMA for this crossover strategy.")
    st.stop()

# Build a reproducible synthetic OHLC series with changing regimes; never represented as real market data.
rng = np.random.default_rng(int(seed) + sum(ord(c) for c in pair))
n = 1500
regimes = np.zeros(n)
for start, end, drift in [(0, 250, 0.00025), (250, 450, -0.00035),
                          (450, 800, 0.00012), (800, 1050, -0.0002),
                          (1050, 1500, 0.0003)]:
    regimes[start:end] = drift
vol = 0.009 if "USDT" in pair else 0.0025
returns = regimes + rng.normal(0, vol, n)
close = 100 * np.exp(np.cumsum(returns))
if pair == "BTC/USDT": close *= 650
elif pair == "ETH/USDT": close *= 35
elif pair == "EUR/USD": close *= 0.0108
elif pair == "GBP/USD": close *= 0.0127
else: close *= 1.5
intraday = np.abs(rng.normal(vol * 0.8, vol * 0.35, n))
high = close * (1 + intraday)
low = close * (1 - intraday)
df = pd.DataFrame({
    "Time": pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n, freq="h"),
    "Open": np.r_[close[0], close[:-1]], "High": high, "Low": low, "Close": close
})
df["EMA Fast"] = df.Close.ewm(span=fast_n, adjust=False).mean()
df["EMA Slow"] = df.Close.ewm(span=slow_n, adjust=False).mean()
df["EMA Trend"] = df.Close.ewm(span=trend_n, adjust=False).mean()
delta = df.Close.diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)
prev_close = df.Close.shift(1)
tr = pd.concat([(df.High - df.Low), (df.High - prev_close).abs(), (df.Low - prev_close).abs()], axis=1).max(axis=1)
df["ATR"] = tr.rolling(14).mean().bfill()
df["Trend"] = np.where((df.Close > df["EMA Trend"]) & (df["EMA Fast"] > df["EMA Slow"]), "UP",
                       np.where((df.Close < df["EMA Trend"]) & (df["EMA Fast"] < df["EMA Slow"]), "DOWN", "MIXED"))
df["Signal"] = "HOLD"
for i in range(1, len(df)):
    up_cross = df["EMA Fast"].iloc[i] > df["EMA Slow"].iloc[i] and df["EMA Fast"].iloc[i-1] <= df["EMA Slow"].iloc[i-1]
    down_cross = df["EMA Fast"].iloc[i] < df["EMA Slow"].iloc[i] and df["EMA Fast"].iloc[i-1] >= df["EMA Slow"].iloc[i-1]
    buy_ok = df.Trend.iloc[i] == "UP" and (not rsi_filter or 40 <= df.RSI.iloc[i] <= rsi_buy_max)
    sell_ok = df.Trend.iloc[i] == "DOWN" and (not rsi_filter or rsi_sell_min <= df.RSI.iloc[i] <= 60)
    if up_cross and buy_ok: df.loc[df.index[i], "Signal"] = "BUY"
    elif down_cross and sell_ok: df.loc[df.index[i], "Signal"] = "SELL"

# Conservative, close-to-close educational backtest. Stops are checked with synthetic high/low bars.
fee_rate = (fee_bps + slippage_bps) / 10000
equity = float(starting_balance)
peak = equity
max_dd = 0.0
trades = []
position = None
daily_anchor = equity
current_day = None
daily_locked = False
equity_rows = []
for i in range(max(trend_n, 20), len(df)):
    row = df.iloc[i]
    day = row.Time.date()
    if day != current_day:
        current_day = day
        daily_anchor = equity
        daily_locked = False
    if equity - daily_anchor <= -daily_anchor * daily_loss_pct / 100:
        daily_locked = True

    # Existing position exits: gap-aware approximations, conservative if stop and target touched in same bar.
    if position:
        exit_price, exit_reason = None, None
        if position["side"] == "BUY":
            if row.Low <= position["stop"]:
                exit_price, exit_reason = min(position["stop"], row.Open), "Stop-loss"
            elif row.High >= position["target"]:
                exit_price, exit_reason = position["target"], "Take-profit"
        else:
            if row.High >= position["stop"]:
                exit_price, exit_reason = max(position["stop"], row.Open), "Stop-loss"
            elif row.Low <= position["target"]:
                exit_price, exit_reason = position["target"], "Take-profit"
        if exit_price is not None:
            gross = (exit_price-position["entry"])*position["units"] if position["side"]=="BUY" else (position["entry"]-exit_price)*position["units"]
            costs = (position["entry"] + exit_price) * position["units"] * fee_rate
            pnl = gross - costs
            equity += pnl
            trades.append({"Entry time": position["time"], "Exit time": str(row.Time),
                           "Side": position["side"], "Entry": position["entry"], "Exit": exit_price,
                           "P/L ($)": pnl, "Exit reason": exit_reason})
            position = None

    # New positions only if flat, signal occurs, and daily loss limit has not locked entries.
    if position is None and not daily_locked and row.Signal in ("BUY", "SELL") and equity > 0:
        entry = float(row.Close)
        stop_dist = max(float(row.ATR) * atr_stop_mult, entry * 0.001)
        risk_cash = equity * risk_pct / 100
        units = risk_cash / stop_dist
        # Bound notional exposure to 100% of equity; this prototype uses no leverage.
        units = min(units, equity / entry)
        if units > 0:
            if row.Signal == "BUY":
                stop, target = entry-stop_dist, entry+stop_dist*reward_risk
            else:
                stop, target = entry+stop_dist, entry-stop_dist*reward_risk
            position = {"side": row.Signal, "entry": entry, "stop": stop, "target": target,
                        "units": units, "time": str(row.Time)}
    peak = max(peak, equity)
    max_dd = max(max_dd, (peak-equity)/peak if peak else 0)
    equity_rows.append({"Time": row.Time, "Equity": equity})

# Mark any remaining position to market for transparency, not as a closed trade.
equity_df = pd.DataFrame(equity_rows)
trade_df = pd.DataFrame(trades)
wins = int((trade_df["P/L ($)"] > 0).sum()) if not trade_df.empty else 0
ntrades = len(trade_df)
net_pnl = float(trade_df["P/L ($)"].sum()) if ntrades else 0.0
win_rate = wins / ntrades * 100 if ntrades else 0.0
profit_factor = (trade_df.loc[trade_df["P/L ($)"] > 0, "P/L ($)"].sum() / abs(trade_df.loc[trade_df["P/L ($)"] < 0, "P/L ($)"].sum())) if ntrades and (trade_df["P/L ($)"] < 0).any() else None

latest = df.iloc[-1]
m = st.columns(4)
m[0].metric("Latest sample close", f"{latest.Close:,.5f}")
m[1].metric("Trend", latest.Trend)
m[2].metric("Current signal", latest.Signal)
m[3].metric("Synthetic backtest trades", f"{ntrades}")
st.subheader("Trend and signals")
st.line_chart(df.set_index("Time")[["Close", "EMA Fast", "EMA Slow", "EMA Trend"]].tail(500), height=320)
st.caption("Synthetic prices only. Do not interpret this chart as current BTC, ETH, or forex prices.")

st.subheader("Backtest results on synthetic data")
a,b,c,d,e = st.columns(5)
a.metric("Closed trades", ntrades)
b.metric("Win rate", f"{win_rate:.1f}%")
c.metric("Net P/L", f"${net_pnl:,.2f}")
d.metric("Max drawdown", f"{max_dd*100:.1f}%")
e.metric("Profit factor", f"{profit_factor:.2f}" if profit_factor is not None else "N/A")
if not equity_df.empty:
    st.line_chart(equity_df.set_index("Time")[["Equity"]], height=220)
if not trade_df.empty:
    st.dataframe(trade_df.tail(100), use_container_width=True, hide_index=True)
else:
    st.info("No trades triggered in this synthetic run with the selected filters.")

st.subheader("What this version does not do")
st.markdown("""
- Does not fetch live prices or connect to a broker/exchange.
- Does not place real orders.
- Does not guarantee profits or prevent all losses.
- Uses synthetic OHLC candles and simplified fee/slippage assumptions.
- Needs real historical data, out-of-sample testing, walk-forward testing, and broker-specific demo testing before any real-world use.
""")
st.warning("Backtest results here are only a code/logic demonstration. Synthetic results are not evidence of a real trading edge.")
