"""
technical.py
Calculates technical indicators from stock price history.
These indicators are what the AI agent uses to make buy/sell recommendations.

Indicators calculated:
- Moving Averages (MA7, MA20, MA50)
- PSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume Analysis
- Short term signal (1-7 days)
- Long term signal (1-6 months)
"""

import boto3
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
import os

load_dotenv()

dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"))
table    = dynamodb.Table(os.getenv("DYNAMODB_TABLE", "stock_prices"))

# Fetch price history from DynamoDB

def fetch_price_history(symbol: str, limit: int = 100) -> pd.DataFrame:
    """
    Fetch recent price history for a stock from DynamoDB.
    Uses scan with filter — works without GSI.
    """
    try:
        from boto3.dynamodb.conditions import Key, Attr

        response = table.scan(
            FilterExpression=Attr("symbol").eq(symbol),
            Limit=500
        )
        items = response.get("Items", [])

        if not items:
            print(f"  No items found for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(items)
        df["price"]      = df["price"].astype(float)
        df["pct_change"] = df["pct_change"].astype(float)
        df["volume"]     = df["volume"].astype(int)
        df["timestamp"]  = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Keep only latest records up to limit
        df = df.tail(limit).reset_index(drop=True)

        print(f"  {symbol}: {len(df)} records fetched")
        return df

    except Exception as e:
        print(f"Error fetching history for {symbol}: {e}")
        return pd.DataFrame()


# Moving Averages
def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate short, medium and long term moving averages.
    MA7 = 7 period = short term trend
    MA20 = 20 period = medium term trend
    MA50 = 50 period = long term trend
    """

    df = df.copy()
    df["MA7"] = df["price"].rolling(window=7, min_periods=1).mean().round(2)
    df["MA20"] = df["price"].rolling(window=20, min_periods=1).mean().round(2)
    df["MA50"] = df["price"].rolling(window=50, min_periods=1).mean().round(2)
    return df


# RSI (Relative Strength Index)

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    PSI - Relative Strength Index.
    Above 70 = overbought (consider selling)
    Below 30 = oversold (consider buying)
    40-60 = neutral zone
    """

    df = df.copy()
    delta = df["price"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods = 1).mean()
    avg_loss = loss.rolling(window=period, min_periods = 1).mean()

    rs = avg_gain/ avg_loss.replace(0, np.nan)
    df["RSI"] = (100 - (100 / (1 +rs))).round(2)
    df["RSI"] = df["RSI"].fillna(50)
    return df

# MACD( Moving Average Convergence Divergence)
def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """
    MACD - Moving AVerage Convergence Divergence.
    when MACD line crosses above signal line = bullish (buy signal)
    when MACD line crosses below signal line = bearish (sell signal) 
    """

    df = df.copy()
    ema12 = df["price"].ewm(span=12, adjust= False).mean()
    ema26 = df["price"].ewm(span=26, adjust=False).mean()
    df["MACD"] = (ema12 - ema26).round(4)
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean().round(4)
    df["MACD_hist"] = (df["MACD"] - df["Signal"]).round(4)
    return df

# Bollinger Bands

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Bollinger Bands - price volatility indicator.
    Price near upper band = potentially overbought
    Price ear lower band = potentially oversold
    """

    df = df.copy()
    rolling = df["price"].rolling(window=period, min_periods = 1)
    df["BB_mid"] = rolling.mean().round(2)
    df["BB_std"] = rolling.std().round(2).fillna(0)
    df["BB_upper"] =(df["BB_mid"] + 2 * df["BB_std"]).round(2)
    df["BB_lower"] = (df["BB_mid"] - 2 * df["BB_std"]).round(2)
    return df

# Signal generator
def generate_signal(df: pd.DataFrame) -> dict:
    """
    Combines all indidcators to generate a final recommendation.
    Returns signal, confidence, and reasoning for both
    short term(1-7 days) and long term (1-6 months)
    """
    if df.empty or len(df) < 2:
        return{
            "short_term": "INSUFFICIENT DATA",
            "long_term": "INSUFFICIENT DATA",
            "confidence": 0,
            "reasons": ["long enough price history yet - keep streaming dada"]
        }

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    reasons = []
    score = 0 # positive = bullish, negative = bearish

    # RSI signal
    rsi = latest.get("RSI", 50)
    if rsi < 30:
        score += 2
        reasons.append(f"RSI {rsi:.1f} - oversold, potential bounce opportunity")

    elif rsi > 70:
        score -= 2
        reasons.append(f"RSI{rsi:.1f} - overbought, caution advised")

    else:
        reasons.append(f"RSI {rsi:.1f} - neutral Zone")


    # Moving average signal
    price = latest["price"]
    ma7   = latest.get("MA7", price)
    ma20  = latest.get("MA20", price)
    ma50  = latest.get("MA50", price)

    if price > ma7 > ma20:
        score += 2
        reasons.append("Price above MA7 and MA20 - short term bullish trend")

    elif price < ma7 < ma20:
        score -= 2
        reasons.append("price below MA7 and MA20 - short term bearish trend")

    if ma7 > ma50:
        score += 1
        reasons.append("MA7 above MA50 - long term upward trend")

    elif ma7 < ma50:
        score -= 1
        reasons.append("MA7 below MA50 - long term downward pressure")

    # MACD signal
    macd = latest.get("MACD", 0)
    signal = latest.get("Signal", 0)
    prev_macd = prev.get("MACD", 0)
    prev_signal = prev.get("signal", 0)

    if macd > signal and prev_macd <= prev_signal:
        score + 2
        reasons.append("MACD bullish crossover - momentum turning positive")
    elif macd < signal and prev_macd >= prev_signal:
        score -= 2
        reasons.append("MACD bearish crosover - momentum turning negative")
    elif macd > signal: 
        score += 1
        reasons.append("MACD above signal line - positive momentum")
    else:
        score -= 1
        reasons.append("MACD below signal line - negative momentum")

    # Bollinger Band signals
    bb_upper = latest.get("BB_upper", price * 1.02)
    bb_lower = latest.get("BB_lower", price * 0.98)

    if price <= bb_lower:
        score += 1
        reasons.append("price at lower Bollinger band - potential reversal")
    elif price >= bb_upper:
        score -= 1
        reasons.append("price at upper Bollinger Band - potential pullback")

    # Generate final signals
    # Short term is more sensitive to recent movements

    if score >= 3:
        short_term = "STRONG BUY"
    elif score >= 1:
        short_term = "BUY"
    elif score == 0:
        short_term = "HOLD"
    elif score >= -2:
        short_term = "SELL"
    else:
        short_term = "STRING SELL"

    # long term requires stronger conviction
    if score >= 4:
        long_term = "BUY"
    elif score >= 1:
        long_term = "HOLD"
    elif score >= -1:
        long_term = "HOLD"
    else:
        long_term = "SELL"

    confidence = min(100, abs(score) * 20)

    return{
        "short_term": short_term,
        "long_term": long_term,
        "confidence": confidence,
        "score": score,
        "rsi": round(float(rsi), 1),
        "macd": round(float(macd), 4),
        "ma7": round(float(ma7), 2),
        "ma20": round(float(ma20), 2),
        "ma50": round(float(ma50), 2),
        "current_price": round(float(price), 2),
        "reasons": reasons
    }

# Full anaysis for one stock
def analyse_stock(symbol: str) -> dict:
    """
    Run complete techical analyss for a single stock.
    This is what the AI agent calls as a tool.
    """

    df = fetch_price_history(symbol, limit=100)

    if df.empty:
        return{
            "symbol": symbol,
            "error": "No price history found",
            "short_term": "NO DATA",
            "long_term": "NO DATA"
        }

    df = calculate_moving_averages(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)

    signal = generate_signal(df)

    return {
        "symbol":       symbol,
        "data_points":  len(df),
        "latest_price": signal["current_price"],
        "short_term":   signal["short_term"],
        "long_term":    signal["long_term"],
        "confidence":   signal["confidence"],
        "rsi":          signal["rsi"],
        "macd":         signal["macd"],
        "ma7":          signal["ma7"],
        "ma20":         signal["ma20"],
        "ma50":         signal["ma50"],
        "reasons":      signal["reasons"],
        "df":           df
    }

# Comapre all stocks
def compare_all_stocks() -> list:
    symbols = ["AAPL", "GOOGLE", "MSFT", "AMZN", "TSLA"]
    results = []

    for symbol in symbols:
        analysis = analyse_stock(symbol)
        results.append(analysis)    # include even if limited data

    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return results

# Quick test
# ── Quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running technical analysis on all stocks...")
    print()

    stocks = compare_all_stocks()

    print(f"{'Symbol':<8} {'Price':>8} {'Short Term':<14} "
          f"{'Long Term':<12} {'RSI':>6} {'Confidence':>10}")
    print("-" * 65)

    for s in stocks:
        if "error" in s:
            print(f"{s['symbol']:<8} {'NO DATA':<40}")
        else:
            print(
                f"{s['symbol']:<8} "
                f"${s.get('latest_price', 0):>7.2f} "
                f"{s.get('short_term', 'N/A'):<14} "
                f"{s.get('long_term', 'N/A'):<12} "
                f"{s.get('rsi', 0):>6.1f} "
                f"{s.get('confidence', 0):>9}%"
            )

    print()
    valid = [s for s in stocks if "error" not in s]
    if valid:
        print("Top pick short term:", valid[0]["symbol"])
        print("Reasons:")
        for r in valid[0].get("reasons", []):
            print(f"  → {r}")

