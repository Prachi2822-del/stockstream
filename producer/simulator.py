"""
simpulator.py
Generates realastic simulated stock prices and streams them to AWS Kineses in real time.

Stocks tracked: AAPL, GOOGLE, MSFT, AMZN, TSLA price movements use random walk algorithm - same technique used by real quantitative finance systems.
"""

import boto3
import json
import time
import random
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Config
STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "stockstream-prices")
REGION        = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2") 
SESSION_MINUTES = 30 # auto-stop afdter 30 min
INTERVAL_SECONDS = 1 # send one priece per second

# Starting prices (realistics as of 2025)

STOCKS = {
    "AAPL": {"price": 227.50, "volatility": 0.002, "name": "Apple Inc."},
    "GOOGLE": {"price": 191.20, "volatility": 0.0025, "name": "Alphabet Inc."},
    "MSFT": {"price": 415.80, "volatility": 0.0018, "name": "Microsoft Corporation"}, 
    "AMZN": {"price": 224.60, "volatility": 0.0022, "name": "Amazon.com Inc."},
    "TSLA": {"price": 352.40, "volatility": 0.004, "name": "Tesla, Inc."}
}

# Price engine

def generate_price_movement(current_price: float, volatility: float) -> float:
    """ Random walk price model.
    Each tick the price moves up or down by a small random amount.
    This is how real quantitative trading systems model price movements.
    """

    # Random return between -volatility and + volatility
    random_return = random.gauss(0, volatility)

    # Apply return to current price
    new_price = current_price * (1+ random_return)

    # Keep price above $1 - stocks don'e go negative
    return max(1.0, round(new_price, 2))

def generate_stock_record(symbol: str, stock_data:dict) -> dict:
    """ Create a single stock price record."""
    now = datetime.now(timezone.utc)

    # Calculate new price
    new_price = generate_price_movement(
        stock_data["price"], stock_data["volatility"]
    )
    price_change = round(new_price - stock_data["price"], 2)
    pct_change = round((price_change / stock_data["price"]) * 100, 4)

    # Update current price for next tick
    stock_data["price"] = new_price

    record = {
        "symbol" : symbol,
        "name": stock_data["name"],
        "price": new_price,
        "price_change": price_change,
        "pct_change": pct_change,
        "volume": random.randint(1000, 50000),
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "hour": now.strftime("%H"),
        "minute": now.strftime("%M"),
        "source": "simulator"
    }
    return record

# Kinesis sender

def send_to_kinesis(client, record: dict) -> bool:
    """ Send one record to Kinesis stream."""
    try: 
        response = client.put_record(
            StreamName = STREAM_NAME, 
            Data=json.dumps(record).encode("utf-8"),
            PartitionKey = record["symbol"] # partition by stock symbol
        )
        return response["ResponseMetadata"]["HTTPStatusCode"] == 200

    except Exception as e:
        print(f" Error sending to Kinesis: {e}")
        return False

# Anomaly Detector

def check_anomaly(record: dict) -> bool:
    """ Flag if price moved more than 1% in one tick.
    In real markets this would trigger an aleert.
    """
    return abs(record["pct_change"]) > 1.0

# Main procedure loop

def run_producer():
    print("=" * 60)
    print(" StockStream Producer")
    print(f" Streaming to: {STREAM_NAME}") 
    print(f" Stocks: {', '.join(STOCKS.keys())}")
    print(f" Session duration: { SESSION_MINUTES} MINUTES")
    print(f" Press Ctrl+C to stop early")
    print("=" * 60)
    print()

    # connect to Kinesis
    client = boto3.client("kinesis", region_name=REGION)

    # Track stats
    records_sent = 0
    errors = 0
    anomalies = 0
    start_time = time.time()
    end_time = start_time + (SESSION_MINUTES * 60)

    try:
        while time.time() < end_time:
            tick_start = time.time()

            # Generate and send one price for each stock
            for symbol, stock_data in STOCKS.items():
                record = generate_stock_record(symbol, stock_data)

                success = send_to_kinesis(client, record)

                if success:
                    records_sent += 1

                    # Check for anomaly
                    if check_anomaly(record):
                        anomalies += 1
                        print(
                            f" ANOMALY: {symbol} moved "
                            f"{record['pct_change']:+.2f}% "
                            f" -> ${record['price']:.2f}"
                        )
                    else:
                        print(
                            f"  {symbol:5s} ${record['price']:8.2f}  "
                            f"{record['pct_change']:+.4f}%  "
                            f"vol:{record['volume']:,}"
                        )
                else:
                    errors += 1

            # print stats every 10 seconds
            elapsed = int(time.time() -start_time) 
            if elapsed % 10 == 0 and elapsed > 0:
                remaining = int(end_time - time.time())
                print(
                    f"\n  Stats: {records_sent} sent | "
                    f"{errors} errors | "
                    f"{anomalies} anomalies | "
                    f"{remaining}s remaining\n"
                )  

            # wait for next tick
            tick_elapsed = time.time() - tick_start
            sleep_time = max(0, INTERVAL_SECONDS - tick_elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    finally:
        elapsed_mins = round((time.time() - start_time) / 60,1)
        print()
        print("=" * 60)
        print(f"  Session complete")
        print(f"  Duration:      {elapsed_mins} minutes")
        print(f"  Records sent:  {records_sent:,}")
        print(f"  Errors:        {errors}")
        print(f"  Anomalies:     {anomalies}")
        print("=" * 60)


if __name__ == "__main__":
    run_producer()   


