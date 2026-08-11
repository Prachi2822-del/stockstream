"""
test_producer.py
Unit tests for the stock price simulator.
Tests price generation logic without hitting AWS
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from producer.simulator import (
    generate_price_movement,
    generate_stock_record,
    check_anomaly,
    STOCKS
)

def test_price_never_goes_negative():
    """ Price must always stay above $1."""
    for _ in range(1000):
        price = generate_price_movement(10.0, 0.5)
        assert price >= 1.0

def test_price_movement_is_realistic():
    """ Price should not jump more than 10% in one tick at normal volatility. """
    current = 100.0
    for _ in range(100):
        new_price = generate_price_movement(current, 0.02)
        change_pct = abs(new_price - current) / current * 100
        assert change_pct < 10.0

def test_record_has_required_fields():
    """ Every record must have all required fields."""
    symbol = "AAPl"
    stock = {"price": 227.50, "volatility": 0.002, "name": "Apple Inc"}
    record = generate_stock_record(symbol, stock)

    required =["symbol", "name", "price_change","pct_change", "volume", "timestamp", "date", "source"]
    for field in required:
        assert field in record, f"Missing field: {field}"

def test_record_symbol_matches():
    """Record symbol must input symbol."""
    stock = {"price": 100.0, "volatility": 0.002, "name": "Test Crop"}
    record = generate_stock_record("MSFT", stock)
    assert record["symbol"] == "MSFT"

def test_anomaly_detection_high_change():
    """ Record with > 1% change should be flagged as anomaly."""
    record = {"pct_change": 1.5}
    assert check_anomaly(record) is True

def test_anomaly_detection_normal_change():
    """ Record with < 1% change should not be flagged keys. """
    record = {"pct_change": 0.3}
    assert check_anomaly(record) is False

def test_all_stocks_defined():
    """ All 5 stocks must be defined with required keys."""
    required_stocks = ["AAPL", "GOOGLE", "MSFT", "AMZN", "TSLA"]
    for symbol in required_stocks:
        assert symbol in STOCKS
        assert "price" in STOCKS[symbol]
        assert "volatility" in STOCKS[symbol]
        assert "name" in STOCKS[symbol]

if __name__ == "__main__":
    print("Running producer tests...")
    test_price_never_goes_negative()
    print("  PASS  price never goes negative")
    test_price_movement_is_realistic()
    print("  PASS  price movement is realistic")
    test_record_has_required_fields()
    print("  PASS  record has required fields")
    test_record_symbol_matches()
    print("  PASS  record symbol matches")
    test_anomaly_detection_high_change()
    print("  PASS  anomaly detection high change")
    test_anomaly_detection_normal_change()
    print("  PASS  anomaly detection normal change")
    test_all_stocks_defined()
    print("  PASS  all stocks defined")
    print()
    print("All tests passed!")
