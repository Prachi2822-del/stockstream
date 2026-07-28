"""
test_setup.py
Verifies all AWS services are reachable before we start building
"""

import boto3
import os
from dotenv import load_dotenv 

load_dotenv()

def test_kinesis_connection():
    """Check Kinesis stream exists."""
    client = boto3.client("kinesis", region_name=os.getenv("AWS_DEFAULT_REGION"))
    response = client.describe_stream_summary(
        StreamName=os.getenv("KINESIS_STREAM_NAME")
    )
    status = response["StreamDescriptionSummary"]["StreamStatus"]
    print(f"Kinesis stream status: {status}")
    assert status == "ACTIVE"

def test_dynamodb_connection():
    """Check DynamoDB table exists."""
    client = boto3.client("dynamodb", region_name=os.getenv("AWS_DEFAULT_REGION"))
    response = client.describe_table(
        TableName=os.getenv("DYNAMODB_TABLE_NAME")
    )
    status = response["Table"]["TableStatus"]
    print(f"DynamoDB table status: {status}")
    assert status == "ACTIVE"

def test_s3_connection():
    """Check S3 bucket is reachable."""
    client = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION"))
    response = client.head_bucket(Bucket=os.getenv("S3_BUCKET"))
    print(f"S3 bucket reachable: {os.getenv('S3_BUCKET')}")
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

if __name__ == "__main__":
    print("Testing AWS connections...")
    print()
    test_kinesis_connection()
    test_dynamodb_connection()
    test_s3_connection()
    print()
    print("All connections working!")