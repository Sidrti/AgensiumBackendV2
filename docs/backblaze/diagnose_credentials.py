"""
Quick diagnostic to verify B2 credentials and permissions
"""
import os
from dotenv import load_dotenv
import boto3

load_dotenv()

print("🔍 CREDENTIAL DIAGNOSTIC\n")

# Check credentials
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
endpoint = os.getenv("AWS_ENDPOINT_URL")
region = os.getenv("AWS_REGION")
bucket = os.getenv("S3_BUCKET")

print(f"Access Key ID: {access_key[:20]}..." if access_key else "❌ NOT SET")
print(f"Secret Key: {secret_key[:20]}..." if secret_key else "❌ NOT SET")
print(f"Endpoint: {endpoint}")
print(f"Region: {region}")
print(f"Bucket: {bucket}\n")

if not all([access_key, secret_key, endpoint, region, bucket]):
    print("❌ Missing required environment variables!")
    exit(1)

print("Attempting connection...\n")

try:
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    
    # Try to list objects
    print("Testing: list_objects_v2()...")
    response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
    print("✅ SUCCESS!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print(f"\nError type: {type(e).__name__}")
    
    if hasattr(e, 'response'):
        print(f"Status Code: {e.response['ResponseMetadata']['HTTPStatusCode']}")
        print(f"Error Code: {e.response['Error']['Code']}")
        print(f"Error Message: {e.response['Error']['Message']}")
