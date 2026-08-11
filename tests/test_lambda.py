"""
test_lambda.py
Tests for the lambda consumer without needing AWS.
We mock S3 and dynamoDB so tests run locally.
"""

import sys
import os
import json
import base64
from unittest.mock import patch, MagicMock
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def make_kinesis_event(records: list) -> dict:
    """ Create a fake kinesis event for testing. """

    kinesis_records = []
    for record in records:
        encoded = base64.b64encode(
            json.dumps(record).encode("utf-8")
        ).decode("utf-8")
        kinesis_records.append({
            "kinesis": {
                "data": encoded,
                "partitionkey": record.get("symbol", "TEST")
            }
        })
    return {"Records": kinesis_records}

def make_stock_record(symbol="AAPL", price= 227.50, pct_change = 0.05):
    return{
        "symbol":       symbol,
        "name":         "Apple Inc",
        "price":        price,
        "price_change": price * pct_change / 100,
        "pct_change":   pct_change,
        "volume":       10000,
        "timestamp":    "2026-07-28T10:00:00+00:00",
        "date":         "2026-07-28",
        "hour":         "10",
        "source":       "simulator"
    }

@patch("consumer.lambda_function.table")
@patch("consumer.lambda_function.s3")

def test_lambda_processes_single_record(mock_s3, mock_table):
    """ Lambda should process one record and save to s3 and DynamoDB."""
    mock_s3.put_object.return_value = {}
    mock_table.put_item.return_value ={}

    from consumer.lambda_function import lambda_handler

    record = make_stock_record("AAPL", 227.50, 0.05)
    event = make_kinesis_event([record])

    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert result["records_processed"] == 1
    assert result["s3_saved"] == 1
    assert result["dynamo_saved"] == 1
    print(" PASS processes single record")

@patch("consumer.lambda_function.table")
@patch("consumer.lambda_function.s3")

def test_lambda_detects_anomaly(mock_s3, mock_table):
    """Lambda should flag records with pct_change > 1%."""
    mock_s3.put_object.return_value = {}
    mock_table.put_item.return_value = {}

    from consumer.lambda_function import lambda_handler

    record = make_stock_record("TSLA", 352.0, 1.5)
    event  = make_kinesis_event([record])

    result = lambda_handler(event, None)

    print(f"  Debug result keys: {list(result.keys())}")
    assert "anomalies" in result, f"Missing 'anomalies' key in result: {result}"
    assert result["anomalies"] == 1
    print("  PASS  detects anomaly")

@patch("consumer.lambda_function.table")
@patch("consumer.lambda_function.s3")

def test_lambda_processes_multiple_records(mock_s3, mock_table):
    """ lambda should handle a batch of records. """
    mock_s3.put_object.return_value = {}
    mock_table.put_item.return_value = {}

    from consumer.lambda_function import lambda_handler

    records =[
        make_stock_record("AAPL",  227.50, 0.05),
        make_stock_record("GOOGL", 191.20, 0.10),
        make_stock_record("MSFT",  415.80, 0.08),
        make_stock_record("AMZN",  224.60, 0.03),
        make_stock_record("TSLA",  352.40, 0.20),
    ]
    event = make_kinesis_event(records)
    result = lambda_handler(event, None)

    assert result["records_processed"] == 5
    assert result["s3_saved"] == 5
    print(" PASS processes multiple records")

@patch("consumer.lambda_function.table")
@patch("consumer.lambda_function.s3")

def test_lambda_normal_change_not_anomaly(mock_s3, mock_table):
    """Records with small price change should not be flagged."""
    mock_s3.put_object.return_value = {}
    mock_table.put_item.return_value = {}

    from consumer.lambda_function import lambda_handler

    record = make_stock_record("MSFT", 415.80, 0.3)
    event  = make_kinesis_event([record])
    result = lambda_handler(event, None)

    assert result["anomalies"] == 0
    print("  PASS  normal change not flagged as anomaly")


if __name__ == "__main__":
    print("Running Lambda tests...")
    print()
    test_lambda_processes_single_record()
    test_lambda_processes_multiple_records()
    test_lambda_detects_anomaly()
    test_lambda_normal_change_not_anomaly()
    print()
    print("All Lambda tests passed!")


