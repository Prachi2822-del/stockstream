"""
real_producer.py
Fetches REAL live stock prices from Yahoo Finance
and saves directly to DynamoDB + Kinesis.
"""

import boto3
import json
import time
import os
import yfinance as yf
from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

STREAM_NAME      = os.getenv("KINESIS_STREAM_NAME", "stockstream-prices")
REGION           = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
DYNAMODB_TABLE   = os.getenv("DYNAMODB_TABLE", "stock_prices")
INTERVAL_SECONDS = 120
SESSION_MINUTES  = 60

STOCKS = {
    "AAPL":   ("AAPL",  "Apple Inc"),
    "GOOGLE": ("GOOGL", "Alphabet Inc"),
    "MSFT":   ("MSFT",  "Microsoft Corp"),
    "AMZN":   ("AMZN",  "Amazon.com Inc"),
    "TSLA":   ("TSLA",  "Tesla Inc"),
}

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table    = dynamodb.Table(DYNAMODB_TABLE)
kinesis  = boto3.client("kinesis", region_name=REGION)


def fetch_price(symbol: str) -> dict | None:
    yahoo_sym, name = STOCKS[symbol]
    for attempt in range(3):
        try:
            info  = yf.Ticker(yahoo_sym).fast_info
            price = round(float(info.last_price), 2)
            prev  = round(float(info.previous_close), 2)
            chg   = round(price - prev, 2)
            pct   = round((chg / prev) * 100, 4) if prev else 0
            vol   = int(info.last_volume or 0)
            now   = datetime.now(timezone.utc)
            return {
                "symbol":       symbol,
                "name":         name,
                "price":        price,
                "price_change": chg,
                "pct_change":   pct,
                "volume":       vol,
                "timestamp":    now.isoformat(),
                "date":         now.strftime("%Y-%m-%d"),
                "hour":         now.strftime("%H"),
                "source":       "yahoo_finance"
            }
        except Exception as e:
            print(f"  {symbol}: attempt {attempt+1} failed — {e}")
            time.sleep(5 * (attempt + 1))
    return None


def save_to_dynamodb(record: dict) -> bool:
    try:
        table.put_item(Item={
            "symbol":       record["symbol"],
            "timestamp":    record["timestamp"],
            "name":         record["name"],
            "price":        Decimal(str(record["price"])),
            "price_change": Decimal(str(record["price_change"])),
            "pct_change":   Decimal(str(record["pct_change"])),
            "volume":       record["volume"],
            "date":         record["date"],
            "hour":         record["hour"],
            "source":       record["source"],
        })
        return True
    except Exception as e:
        print(f"  DynamoDB error: {e}")
        return False


def send_to_kinesis(record: dict) -> bool:
    try:
        response = kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(record).encode("utf-8"),
            PartitionKey=record["symbol"]
        )
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return status == 200
    except Exception as e:
        return False


def run():
    print("=" * 60)
    print("  StockStream REAL DATA Producer")
    print(f"  Stocks: {', '.join(STOCKS.keys())}")
    print(f"  Interval: every {INTERVAL_SECONDS}s")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    sent     = 0
    errors   = 0
    end_time = time.time() + SESSION_MINUTES * 60

    try:
        while time.time() < end_time:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching real prices...")

            for symbol in STOCKS:
                record = fetch_price(symbol)
                if record is None:
                    errors += 1
                    continue

                # Save to DynamoDB directly
                db_ok = save_to_dynamodb(record)

                # Also send to Kinesis
                send_to_kinesis(record)

                if db_ok:
                    sent += 1
                    arrow = "▲" if record["pct_change"] >= 0 else "▼"
                    if abs(record["pct_change"]) > 1.0:
                        print(f"  ⚠ ANOMALY: {symbol} {record['pct_change']:+.2f}% → ${record['price']:.2f}")
                    else:
                        print(f"  {symbol:6s} ${record['price']:8.2f}  {arrow} {abs(record['pct_change']):.4f}%  vol:{record['volume']:,}  [REAL]")
                else:
                    errors += 1

                time.sleep(3)  # avoid rate limiting

            remaining = int(end_time - time.time())
            print(f"\n  Sent:{sent} | Errors:{errors} | Next in {INTERVAL_SECONDS}s | {remaining//60}m remaining")
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopped by user")

    print(f"\nDone — {sent} records saved to DynamoDB")


if __name__ == "__main__":
    run()
