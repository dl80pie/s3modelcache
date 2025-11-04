#!/usr/bin/env python3
"""
Quick S3 Connection Health Check

Minimal script to test S3 connectivity without dependencies on the full S3ModelCache.
"""

import os
import sys
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError


def quick_s3_test():
    """Quick S3 connectivity test."""
    
    print("🔍 Quick S3 Health Check")
    print("-" * 30)
    
    # Load environment
    load_dotenv()
    
    # Get config
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    access_key = os.getenv("HCP_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("HCP_SECRET_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("HCP_NAMESPACE") or os.getenv("S3_BUCKET")
    
    if not all([endpoint, access_key, secret_key, bucket]):
        print("❌ Missing configuration in .env file")
        return False
    
    try:
        # Create S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1'
        )
        
        # Test bucket access
        s3.head_bucket(Bucket=bucket)
        
        # List objects (max 3)
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=3)
        count = len(response.get('Contents', []))
        
        print(f"✅ Connection successful!")
        print(f"📍 Endpoint: {endpoint}")
        print(f"🪣 Bucket: {bucket}")
        print(f"📊 Objects found: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = quick_s3_test()
    sys.exit(0 if success else 1)
