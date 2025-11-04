#!/usr/bin/env python3
"""
Simple S3 Connection Test Client

This script tests the connectivity to an S3-compatible storage (HCP, MinIO, etc.)
using the S3ModelCache configuration from .env file.
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Add src to path to import s3modelcache
sys.path.insert(0, str(Path(__file__).parent / "src"))

from s3modelcache import S3ModelCache


def test_s3_connection():
    """Test basic S3 connectivity and bucket access."""
    
    print("🔍 Testing S3 Connection...")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration from environment
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    access_key = os.getenv("HCP_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("HCP_SECRET_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("HCP_NAMESPACE") or os.getenv("S3_BUCKET")
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
    root_ca_path = os.getenv("ROOT_CA_PATH")
    
    if not all([endpoint, access_key, secret_key, bucket]):
        print("❌ Missing required environment variables:")
        print("   Please set HCP_ENDPOINT, HCP_ACCESS_KEY, HCP_SECRET_KEY, HCP_NAMESPACE")
        print("   Or S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET")
        return False
    
    print(f"📍 Endpoint: {endpoint}")
    print(f"🪣 Bucket: {bucket}")
    print(f"🔑 Access Key: {access_key[:10]}..." if len(access_key) > 10 else f"🔑 Access Key: {access_key}")
    print(f"🔒 SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}")
    if root_ca_path:
        print(f"📜 Custom CA Path: {root_ca_path}")
    
    try:
        # Test 1: Create S3ModelCache instance
        print("\n1️⃣ Creating S3ModelCache instance...")
        cache = S3ModelCache(
            bucket_name=bucket,
            s3_endpoint=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            verify_ssl=verify_ssl,
            root_ca_path=root_ca_path
        )
        print("✅ S3ModelCache instance created successfully")
        
        # Test 2: Direct boto3 connection test
        print("\n2️⃣ Testing direct boto3 connection...")
        
        # Configure SSL verification for boto3
        verify_config = verify_ssl
        if root_ca_path and verify_ssl:
            verify_config = root_ca_path
        
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1',
            verify=verify_config
        )
        
        # Test bucket existence
        print("   Checking bucket access...")
        s3_client.head_bucket(Bucket=bucket)
        print("✅ Bucket access confirmed")
        
        # Test 3: List bucket contents (if any)
        print("\n3️⃣ Listing bucket contents...")
        response = s3_client.list_objects_v2(Bucket=bucket, MaxKeys=5)
        
        if 'Contents' in response:
            print(f"✅ Found {len(response['Contents'])} objects in bucket:")
            for obj in response['Contents'][:3]:  # Show first 3 objects
                print(f"   📄 {obj['Key']} ({obj['Size']} bytes)")
            if len(response['Contents']) > 3:
                print(f"   ... and {len(response['Contents']) - 3} more objects")
        else:
            print("✅ Bucket is empty or accessible")
        
        # Test 4: Test upload/download with a small test file
        print("\n4️⃣ Testing upload/download functionality...")
        test_content = b"S3 Connection Test - " + str(os.getpid()).encode()
        test_key = "connection-test.txt"
        
        # Upload test file
        s3_client.put_object(
            Bucket=bucket,
            Key=test_key,
            Body=test_content,
            Metadata={'test': 'connection-test'}
        )
        print("✅ Test file uploaded successfully")
        
        # Download and verify test file
        response = s3_client.get_object(Bucket=bucket, Key=test_key)
        downloaded_content = response['Body'].read()
        
        if downloaded_content == test_content:
            print("✅ Test file downloaded and verified successfully")
            
            # Clean up test file
            s3_client.delete_object(Bucket=bucket, Key=test_key)
            print("✅ Test file cleaned up")
        else:
            print("❌ Downloaded content doesn't match uploaded content")
            return False
        
        print("\n🎉 All S3 connection tests passed!")
        return True
        
    except NoCredentialsError:
        print("❌ No credentials found - check your access keys")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            print(f"❌ Bucket '{bucket}' does not exist")
        elif error_code == 'InvalidAccessKeyId':
            print("❌ Invalid access key ID")
        elif error_code == 'SignatureDoesNotMatch':
            print("❌ Invalid secret access key")
        elif error_code == '403':
            print("❌ Access denied - check permissions")
        else:
            print(f"❌ S3 Client Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_ssl_connection():
    """Test SSL/TLS connection specifically."""
    print("\n🔒 Testing SSL/TLS Connection...")
    print("=" * 30)
    
    load_dotenv()
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    
    try:
        import requests
        response = requests.get(endpoint, timeout=10)
        if response.status_code in [200, 403, 405]:  # 403/405 are OK for S3 endpoints
            print("✅ SSL/TLS connection successful")
            return True
        else:
            print(f"⚠️  Unexpected HTTP status: {response.status_code}")
            return False
    except requests.exceptions.SSLError:
        print("❌ SSL/TLS error - certificate issues")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - endpoint unreachable")
        return False
    except Exception as e:
        print(f"⚠️  SSL test inconclusive: {e}")
        return None


if __name__ == "__main__":
    print("🚀 S3 Connection Test Client")
    print("Testing connectivity to S3-compatible storage")
    print()
    
    # Run main connection test
    success = test_s3_connection()
    
    # Run SSL test
    ssl_result = test_ssl_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("🎯 RESULT: S3 connection is working properly!")
    else:
        print("💥 RESULT: S3 connection test failed!")
        print("   Please check your configuration and network connectivity")
    
    sys.exit(0 if success else 1)
