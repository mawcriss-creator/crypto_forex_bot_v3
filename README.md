# Crypto & Forex Bot V3 — Research Lab

This is a local Streamlit research dashboard with trend filtering, EMA crossover signals, RSI confirmation, ATR-based stop/target examples, risk-based sizing, a daily loss lockout in the synthetic backtest, transaction-cost assumptions, trade log, equity curve, win rate, net P/L, profit factor, and maximum drawdown.

**Important:** It uses generated synthetic OHLC data only. It is not connected to live markets, does not send real orders, and synthetic backtest metrics do not show that a strategy will work in real markets. No strategy can be made perfect or guarantee profits.

## Windows installation
1. Install Python 3.11+ from https://www.python.org/downloads/ and select **Add Python to PATH**.
2. Extract this ZIP.
3. Open the extracted folder, click the address bar, type `cmd`, and press Enter.
4. Run:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Dashboard normally opens at http://localhost:8501. Stop with Ctrl+C.

## Before live trading could even be considered
Use trustworthy real historical candles; model exchange/broker fees, spreads, slippage, funding and contract sizing; avoid look-ahead bias; test on out-of-sample periods and across market regimes; paper trade through the official broker/exchange demo; add monitoring, logging, fail-safe handling and manual shutdown. Do not place secrets in code, and never enable withdrawal permission for trading API keys.
