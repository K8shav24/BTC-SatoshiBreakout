import pandas as pd
import numpy as np
from backtester import BackTester


def calculate_ema(series, length):
    """Exponential moving average, computed manually (Wilder-style recursive EMA)."""
    alpha = 2 / (length + 1)
    return series.ewm(alpha=alpha, adjust=False).mean()


def calculate_atr(high, low, close, length=14):
    """Average True Range using Wilder's smoothing, built from raw OHLC."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / length, adjust=False).mean()
    return atr


def calculate_adx(high, low, close, length=14):
    """
    ADX computed manually using Wilder's original method:
    directional movement -> smoothed DI+/DI- -> DX -> smoothed ADX.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    smoothed_tr = tr.ewm(alpha=1 / length, adjust=False).mean()
    smoothed_plus_dm = pd.Series(plus_dm, index=high.index).ewm(alpha=1 / length, adjust=False).mean()
    smoothed_minus_dm = pd.Series(minus_dm, index=high.index).ewm(alpha=1 / length, adjust=False).mean()

    plus_di = 100 * (smoothed_plus_dm / smoothed_tr)
    minus_di = 100 * (smoothed_minus_dm / smoothed_tr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / length, adjust=False).mean()

    return adx


def calculate_donchian(high, low, length=20):
    """
    Donchian channel built from the PRIOR `length` candles only
    (shift(1) excludes the current bar), so a breakout can never be
    triggered by information from the bar generating the signal.
    """
    upper = high.rolling(length).max().shift(1)
    lower = low.rolling(length).min().shift(1)
    return upper, lower


def process_data(data):
    """
    Compute all technical indicators needed by the strategy, all built
    from scratch on raw OHLCV data. Every indicator uses only data up to
    and including the current row, so no future information leaks into row i.
    """
    data['EMA_fast'] = calculate_ema(data['close'], 20)
    data['EMA_slow'] = calculate_ema(data['close'], 50)
    data['ATR'] = calculate_atr(data['high'], data['low'], data['close'], 14)
    data['ADX'] = calculate_adx(data['high'], data['low'], data['close'], 14)
    data['DC_upper'], data['DC_lower'] = calculate_donchian(data['high'], data['low'], 20)

    return data


def strat(data):
    """
    Trend-following strategy: Donchian-channel breakout, filtered by an
    EMA(20/50) trend direction and an ADX(14) strength filter, with an
    ATR-based chandelier trailing stop for risk management.

    Hypothesis: BTC/USD spends long stretches in strong directional trends
    punctuated by choppy ranges. Waiting for a 20-day breakout that agrees
    with the EMA trend direction, and only when ADX confirms the market is
    actually trending, should filter out a lot of the false signals a naive
    breakout system would take in a sideways market. The ATR trailing stop
    lets winners run while cutting losers before they give back too much.
    """
    data['trade_type'] = "HOLD"
    data['signals'] = 0
    position = 0
    trailing_stop = 0.0
    atr_mult = 3.0
    adx_threshold = 20

    warmup = 51  # first index where EMA_slow/ADX/DC are all valid

    for i in range(warmup, len(data)):
        row = data.loc[i]

        if pd.isna(row['EMA_slow']) or pd.isna(row['ADX']) or pd.isna(row['DC_upper']) or pd.isna(row['ATR']):
            continue

        trend_up = row['EMA_fast'] > row['EMA_slow']
        trend_down = row['EMA_fast'] < row['EMA_slow']
        strong_trend = row['ADX'] > adx_threshold

        if position == 0:
            if row['close'] > row['DC_upper'] and trend_up and strong_trend:
                data.loc[i, 'signals'] = 1
                position = 1
                data.loc[i, 'trade_type'] = "LONG"
                trailing_stop = row['close'] - atr_mult * row['ATR']

            elif row['close'] < row['DC_lower'] and trend_down and strong_trend:
                data.loc[i, 'signals'] = -1
                position = -1
                data.loc[i, 'trade_type'] = "SHORT"
                trailing_stop = row['close'] + atr_mult * row['ATR']

        elif position == 1:
            new_stop = row['close'] - atr_mult * row['ATR']
            trailing_stop = max(trailing_stop, new_stop)

            if row['close'] < trailing_stop:
                data.loc[i, 'signals'] = -1
                position = 0
                data.loc[i, 'trade_type'] = "CLOSE"

            elif row['close'] < row['DC_lower'] and trend_down and strong_trend:
                data.loc[i, 'signals'] = -2
                position = -1
                trailing_stop = row['close'] + atr_mult * row['ATR']
                data.loc[i, 'trade_type'] = "REVERSE_LONG_TO_SHORT"

        elif position == -1:
            new_stop = row['close'] + atr_mult * row['ATR']
            trailing_stop = min(trailing_stop, new_stop)

            if row['close'] > trailing_stop:
                data.loc[i, 'signals'] = 1
                position = 0
                data.loc[i, 'trade_type'] = "CLOSE"

            elif row['close'] > row['DC_upper'] and trend_up and strong_trend:
                data.loc[i, 'signals'] = 2
                position = 1
                trailing_stop = row['close'] - atr_mult * row['ATR']
                data.loc[i, 'trade_type'] = "REVERSE_SHORT_TO_LONG"

    return data


def main():
    data = pd.read_csv("BTC_2019_2023_1d.csv")
    processed_data = process_data(data)
    result_data = strat(processed_data)
    csv_file_path = "final_data.csv"
    result_data.to_csv(csv_file_path, index=False)

    bt = BackTester("BTC", signal_data_path="final_data.csv", master_file_path="final_data.csv", compound_flag=1)
    bt.get_trades(1000)

    for trade in bt.trades:
        print(trade)
        print(trade.pnl())

    stats = bt.get_statistics()
    for key, val in stats.items():
        print(key, ":", val)

    print("Checking for lookahead bias...")
    lookahead_bias = False
    for i in range(len(result_data)):
        if result_data.loc[i, 'signals'] != 0:
            temp_data = data.iloc[:i + 1].copy()
            temp_data = process_data(temp_data)
            temp_data = strat(temp_data)
            if temp_data.loc[i, 'signals'] != result_data.loc[i, 'signals']:
                print(f"Lookahead bias detected at index {i}")
                lookahead_bias = True

    if not lookahead_bias:
        print("No lookahead bias detected.")

    import matplotlib.pyplot as plt

    print("Generating graphs...")

    # 1. PnL Graph (The specific image you requested)
    bt.calc_capital()
    fig1, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()
    
    ax1.plot(bt.data.index, bt.data['capital'], label='Capital ($)', color='blue', linewidth=2)
    ax2.plot(bt.data.index, bt.data['close'], label='BTC Price', color='gray', alpha=0.5, linewidth=1)
    
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Capital ($)', color='blue')
    ax2.set_ylabel('BTC Price', color='gray')
    ax1.set_title("Capital (PnL) over Time")
    
    fig1.tight_layout()
    plt.savefig('pnl_graph.png')
    print("Success: Saved 'pnl_graph.png'.")

    # 2. Trade Entries and Exits Graph
    fig2, ax3 = plt.subplots(figsize=(14, 7))
    ax3.plot(bt.data.index, bt.data['close'], label='Close Price', color='black', linewidth=1)
    
    for trade in bt.trades:
        color = 'green' if trade.qty > 0 else 'red'
        ax3.axvspan(trade.init_timestamp, trade.final_timestamp, color=color, alpha=0.2)
        
    ax3.set_title("Trade Entries and Exits")
    ax3.set_ylabel("Price")
    fig2.tight_layout()
    plt.savefig('trade_graph.png')
    print("Success: Saved 'trade_graph.png'.")


if __name__ == "__main__":
    main()
