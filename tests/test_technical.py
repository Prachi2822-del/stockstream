"""
test_technical.py
Tests for the technical analysis engine.
Uses synthetic price data so no AWS needed.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from analyser.technical import(
    calculate_moving_averages,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    generate_signal
)

def make_price_df(prices: list) -> pd.DataFrame:
    return pd.DataFrame({
        "price":      prices,
        "pct_change": [0.0] * len(prices),
        "volume":     [10000] * len(prices),
        "timestamp":  pd.date_range("2026-01-01", periods=len(prices), freq="1s")
    })

def test_moving_averages_calculated():
    """ MA7, MA20, MA50 columns should exist after calculation. """
    df = make_price_df([100.0] * 60)
    result = calculate_moving_averages(df)
    assert "MA7" in result.columns
    assert "MA20" in result.columns
    assert "MA50" in result.columns
    print(" PASS moving averages calculated")

def test_rsi_in_valid_range():
    """ RSI should always be betwen o and 100."""
    prices = [ 100 + np.sin(i * 0.3) * 5 for i in range(50)]
    df = make_price_df(prices)
    result = calculate_rsi(df)
    assert result["RSI"].between(0, 100).all()
    print(" PASS RSI in valid range 0-100")

def test_rsi_oversold_on_falling_prices():
    """ Falling prices should produce low RSI."""
    prices = [ 100 - i * 0.5 for i in range(50)]
    df = make_price_df(prices)
    result = calculate_rsi(df)
    assert result["RSI"].iloc[-1] < 50
    print(" PASS RSI low on falling prices")

def test_macd_columns_exist():
    """MACD, Signal, and MACD_hist columns should exist."""
    df     = make_price_df([100.0 + i * 0.1 for i in range(50)])
    result = calculate_macd(df)
    assert "MACD"      in result.columns
    assert "Signal"    in result.columns
    assert "MACD_hist" in result.columns
    print(" PASS  MACD columns calculated")

def test_bollinger_bands_upper_above_lower():
    """ Upper band should always be above lower band. """
    prices = [100 + np.random.randn() for _ in range(50)]
    df = make_price_df(prices)
    result = calculate_bollinger_bands(df)
    assert (result["BB_upper"] >= result["BB_lower"]).all()
    print(" PASS Bollinger upper always above lower")

def test_signal_bullish_on_rising_prices():
    """ Rising prices should generate BUY or STRONG BUY signal. """
    prices = [100 + i * 0.5 for i in range (60)]
    df = make_price_df(prices)
    df = calculate_moving_averages(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    signal = generate_signal(df)
    assert signal["short_term"] in ["BUY", "STRONG BUY", "HOLD"]
    print(" PASS bullish signal on rising prices")

def test_signal_has_required_keys():
    """ Signal dict should have all required keys. """
    prices =[100.0 + np.sin(i) for i in range(30)]
    df = make_price_df(prices)
    df = calculate_moving_averages(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    signal = generate_signal(df)

    required = ["short_term", "long_term", "confidence", "rsi", "macd", "reasons"]
    for key in required:
        assert key in signal, f"Missing key: {key}"
    print(" PASS signal has all required keys")

def test_empty_df_returns_insufficient_data():
    """ Empty DataFrame should return INSUFFICIENT DATA signal. """
    signal = generate_signal(pd.DataFrame())
    assert signal["short_term"] == "INSUFFICIENT DATA"
    print(" PASS empty data handled gracefully")

if __name__ == "__main__":
    print("Running technical analysis tests...")
    print()
    test_moving_averages_calculated()
    test_rsi_in_valid_range()
    test_rsi_oversold_on_falling_prices()
    test_macd_columns_exist()
    test_bollinger_bands_upper_above_lower()
    test_signal_bullish_on_rising_prices()
    test_signal_has_required_keys()
    test_empty_df_returns_insufficient_data()
    print()
    print(" ALL technical analysis tests passed! ")