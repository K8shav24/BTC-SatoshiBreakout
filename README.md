# BTC-SatoshiBreakout
A daily BTC/USD trend-following strategy that combines a 20-day Donchian channel breakout with a 20/50 EMA trend filter and an ADX(14) strength filter, exiting through a 3x ATR chandelier trailing stop. Trades are only taken when the breakout, the trend, and the trend strength all agree, and a custom event-driven backtesting engine handles execution, trailing stops, and performance reporting.

Table of Contents


Overview
Strategy Logic
Results
Project Structure
Installation
Usage
How It Works
Limitations
License


Overview

This project backtests a daily BTC/USD trend-following strategy over 2018–2022 (1,826 candles). It was built to answer a specific question: can a Donchian breakout, filtered by trend direction and trend strength, actually avoid the whipsaws a naive breakout system takes in a sideways market — without any lookahead bias?

Every indicator (EMA, ATR, ADX, Donchian channel) is computed so that row i only ever uses data up to and including row i. A sampled re-run of the pipeline on truncated data (main.py) is used as a spot-check to confirm no future information leaks into past signals.

Strategy Logic

Trend filter (EMA 20/50):


Fast EMA above slow EMA → uptrend, only long breakouts are eligible.
Fast EMA below slow EMA → downtrend, only short breakouts are eligible.


Strength filter (ADX 14):


ADX has to be above a threshold (20) before any breakout is taken, so the strategy skips breakouts that happen while the market has no real directional momentum behind it.


Entry trigger (Donchian 20):


The channel is built from the prior 20 candles only (shift(1)), so the breakout level itself can never see the bar that triggers it.
Long: close breaks above the upper channel, EMA trend is up, ADX confirms strength.
Short: close breaks below the lower channel, EMA trend is down, ADX confirms strength.


Exit rule: positions are protected by an ATR(14)-based trailing (chandelier) stop, 3x ATR, tracked bar by bar. The strategy can also reverse directly from long to short (or vice versa) if a strong opposite breakout fires before the trailing stop is hit.

Why ADX 20 and ATR 3x? Both parameters were swept rather than guessed — ADX ∈ {15, 20, 25} × ATR mult ∈ {2, 3, 4}, backtested performance was used to pick the combination (not just intuition):

ATR MultADX Th.SharpeNet ProfitMax DDNotes2.0151.05$6,01229.3%—2.0201.01$5,25229.3%—2.0250.52$88851.0%ADX filter too strict3.0151.08$7,56737.7%—3.0201.15$8,91037.7%Best performing, selected3.0250.42$54659.0%ADX filter too strict4.0151.07$8,37749.2%—4.0201.02$7,03849.2%—4.0250.45$60674.3%ADX filter too strict

Results

Backtested on BTC/USD daily data, 2018–2022 (1,826 candles), $1,000 starting capital, compounding enabled, 0.15% transaction fee per trade.

MetricValueTotal Trades23Win Rate56.5%Long / Short Trades13 / 10Net Profit (on $1,000)$8,909.90Benchmark Return (Buy & Hold)$236.35Sharpe Ratio1.15Maximum Drawdown37.65%Average Win / Average Loss$933.98 / -$323.19Average Holding Time46 days

Capital vs. BTC/USD close price:
<img width="856" height="377" alt="image" src="https://github.com/user-attachments/assets/9f94020d-1a86-491b-b428-b206bbab35c3" />

Trade positioning over the BTC/USD price series (green = long, red = short):
<img width="847" height="373" alt="image" src="https://github.com/user-attachments/assets/6ea87419-278d-4337-9120-d219344716bd" />

Show Image

Project Structure

├── main.py            # Indicator/feature engineering, strategy logic,
│                       #   lookahead-bias check, graphing
├── backtester.py       # Event-driven backtesting engine (positions, trades,
│                       #   TP/SL, statistics, capital curve)
├── btc_18_22_1d.csv    # Raw OHLCV input data (not included — bring your own)
├── final_data.csv       # Generated: processed data + signals
├── capital_vs_close.png # Generated: capital vs. close price over time
├── trade_positioning.png # Generated: price with long/short shading
└── README.md

Installation

git clone <your-repo-url>
cd <your-repo>
pip install -r requirements.txt

Dependencies:

pandas
numpy
matplotlib
plotly

Usage


Place daily OHLC data for BTC/USD as btc_18_22_1d.csv in the project root, with at minimum datetime, open, high, low, close, volume columns.
Run the pipeline:


python main.py

This will:


Compute technical indicators and generate strategy signals
Save signals to final_data.csv
Run the backtest and print performance statistics
Run a sampled lookahead-bias check
Display the trade graph and PnL graph


How It Works

main.py computes indicators (process_data) — EMA(20/50), ATR(14), ADX(14), and the Donchian(20) channel — then walks day-by-day in strat(): for each bar past the 51-bar warmup, it checks the trend filter, strength filter, and breakout trigger, and emits a signal only when all three agree. Once in a position, the chandelier stop is recalculated every bar and can only tighten in the trade's favor, never loosen.

backtester.py consumes the resulting signals CSV and simulates execution: opening/closing/reversing positions, applying transaction fees, tracking highs/lows, and computing performance statistics (win rate, Sharpe ratio, drawdown, holding time, etc.) and the capital curve.

Limitations


Almost all of the profit is concentrated in 2021 (+$5,744.77) and 2022 (+$2,069.92); the strategy lost money in 2018 (-$233.88) and only made modest gains in 2019–2020 (+$731.50, +$597.60). The reported Sharpe ratio may not generalize to a period without a 2021-style trend.
With only 23 total trades over 5 years, the sample size is small — individual trades have an outsized effect on the overall statistics.
The strategy is fundamentally a trend-follower. The ADX filter reduces bad entries in choppy markets, but it doesn't eliminate them, so extended sideways regimes will still hurt performance.
Maximum drawdown (37.65%) is fairly large relative to net profit — position sizing and risk management are areas for future improvement.
