"""Quick B2 connection test with timeout"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("Testing B2 credentials...\n")

try:
    import boto3
    from botocore.config import Config
    
    # Add timeout to prevent hanging
    config = Config(
        connect_timeout=5,
        read_timeout=5,
        retries={'max_attempts': 1}
    )
    
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
        config=config
    )
    
    print("Calling list_objects_v2()...")
    response = s3.list_objects_v2(
        Bucket=os.getenv("S3_BUCKET"),
        MaxKeys=1
    )
    
    print("✅ SUCCESS! B2 connection working!")
    print(f"Bucket: {os.getenv('S3_BUCKET')}")
    print(f"Objects in bucket: {response.get('KeyCount', 0)}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
