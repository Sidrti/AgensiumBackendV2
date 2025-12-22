"""
Script to update Backblaze B2 bucket CORS rules using boto3
"""
import boto3
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment
ENDPOINT_URL = os.getenv('AWS_ENDPOINT_URL')
ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
BUCKET_NAME = os.getenv('S3_BUCKET', 'agensium-files')
REGION = os.getenv('AWS_REGION', 'us-east-005')

# CORS configuration for S3-compatible API
cors_configuration = {
    'CORSRules': [
        {
            'AllowedOrigins': [
                'http://localhost:5173',
                'http://localhost:3000',
                'https://agensium2.netlify.app'
            ],
            'AllowedMethods': ['PUT', 'GET', 'HEAD', 'POST', 'DELETE'],
            'AllowedHeaders': ['*'],
            'ExposeHeaders': ['ETag', 'Content-Length', 'x-amz-request-id'],
            'MaxAgeSeconds': 3600
        }
    ]
}

def update_bucket_cors():
    """Update B2 bucket CORS rules using S3-compatible API"""
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id=ACCESS_KEY_ID,
            aws_secret_access_key=SECRET_ACCESS_KEY,
            region_name=REGION
        )
        print(f"✓ S3 client initialized")
        
        # Update CORS configuration
        s3_client.put_bucket_cors(
            Bucket=BUCKET_NAME,
            CORSConfiguration=cors_configuration
        )
        print(f"✓ CORS rules updated successfully for bucket: {BUCKET_NAME}")
        
        # Verify by getting current CORS configuration
        response = s3_client.get_bucket_cors(Bucket=BUCKET_NAME)
        print(f"\n✓ Current CORS configuration:")
        print(json.dumps(response['CORSRules'], indent=2))
        
    except Exception as e:
        print(f"✗ Error updating CORS rules: {str(e)}")
        print(f"\nMake sure your credentials have permission to update bucket CORS settings.")
        raise

if __name__ == "__main__":
    print("Updating B2 bucket CORS rules...\n")
    update_bucket_cors()
