""" 
Lambda_function.py
AWS Lambda functio that consumes stock price records from kinesis.

Triggered automatically when new records arrive in the stream.
For each batch of records:
1. Decode the record from kinesis
2. save raw JSON to s3(partitioned by data/ hpur)
3. save latest price to DynamoDB
4. Check for price anomalies and log them
"""

import json
import base64
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal

# AWS Clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Config from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "retailmind-prachi-2026")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "stock_prices")
ANOMALY_THRESHOLD = 1.0 # flag if price moves more than 1%

# DynamoDB table reference
table = dynamodb.Table(DYNAMODB_TABLE)

# Helper: save record to s3
def save_to_s3(record: dict) -> bool:
    try:
        now       = datetime.now(timezone.utc)
        symbol    = record.get("symbol", "UNKNOWN")
        timestamp = record.get("timestamp") or now.isoformat()

        # Clean timestamp for use in S3 key — remove special characters
        clean_ts  = timestamp.replace(":", "-").replace("+", "-").replace(".", "-")

        s3_key = (
            f"stockstream/raw/"
            f"year={now.strftime('%Y')}/"
            f"month={now.strftime('%m')}/"
            f"day={now.strftime('%d')}/"
            f"hour={now.strftime('%H')}/"
            f"{symbol}_{clean_ts}.json"
        )

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(record),
            ContentType="application/json"
        )
        return True

    except Exception as e:
        print(f"S3 save error for {record.get('symbol')}: {e}")
        return False


# Helper: save latest price to DynamoDB
def save_to_dynamodb(record: dict) -> bool:
    """
    Save the latest price for each stock to DynamoDB.
    Uses symbol as partition key and timestamp as sort key.
    DyanamoDB doesn't support float - use Decimal instead.
    """

    try:
        item = {
            "symbol": record["symbol"],
            "timestamp": record["timestamp"],
            "name": record.get("name", ""),
            "price": Decimal(str(record["price"])),
            "price_change": Decimal(str(record["price_change"])),
            "pct_change": Decimal(str(record["pct_change"])),
            "volume": record["volume"],
            "date": record.get("date", ""),
            "hour": record.get("hour", ""),
            "source": record.get("source", "simulator"),
        }
        table.put_item(Item=item)
        return True

    except Exception as e:
        print(f"DynamoDB save error for {record.get('symbol')}: {e}")
        return False

# Helper: check for anomaly
def is_anomaly(record: dict) -> bool:
    """ Flag if price moved more than threshold in one tick."""
    return abs(record.get("pct_change", 0)) > ANOMALY_THRESHOLD

# Main lambda handler 

def lambda_handler(event, context):
    """ 
    Entry point - called by AWS when kinesis has new records.
    event ["Records"] contains a batch of kinesis records. 
    """
    records_processed = 0
    s3_saved = 0
    dynamo_saved = 0
    anomalies = 0
    errors = 0

    print(f"Lambda triggered - processing{len(event['Records'])} records")

    for kinesis_record in event["Records"]:
        try:
            # Kinesis encodes data base64 - decode it first
            raw_data = base64.b64decode(
                kinesis_record["kinesis"]["data"]
            ).decode("utf-8")

            record = json.loads(raw_data)
            symbol = record.get("symbol", "UNKNOWN")

            # save to s3
            if save_to_s3(record):
                s3_saved += 1

            # save to dynamoDB
            if save_to_dynamodb(record):
                dynamo_saved += 1

            # check for anomaly
            if is_anomaly(record):
                anomalies += 1
                print(
                    f"ANOMALY DETECTED: {symbol} "
                    f"moved {record['pct_change']:+.2f}% "
                    f"to ${record['price']:.2f}"
                )

            records_processed += 1
        except Exception as e:
            errors += 1
            print(f" Error processing record: {e}")

    # summary log
    print(
        f" Summary - processed:{records_processed} "
        f"s3:{s3_saved} dynamo: {dynamo_saved} "
        f"anomalies:{anomalies} errors: {errors}"
    )

    return {
    "statusCode":        200,
    "records_processed": records_processed,
    "s3_saved":          s3_saved,
    "dynamo_saved":      dynamo_saved,
    "anomalies":         anomalies,
    "errors":            errors
}