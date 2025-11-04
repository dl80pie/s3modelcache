#!/usr/bin/env python3
"""
Extract Root CA Certificate from S3 Endpoint

This script helps extract the root CA certificate from a self-signed S3 endpoint
for use with SSL verification.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv


def extract_ca_certificate():
    """Extract CA certificate from S3 endpoint."""
    
    print("🔑 Extracting CA Certificate from S3 Endpoint")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Get endpoint
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    
    if not endpoint:
        print("❌ No endpoint found in environment variables")
        print("   Please set HCP_ENDPOINT or S3_ENDPOINT in .env file")
        return False
    
    # Extract hostname from endpoint
    hostname = endpoint.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    port = 443
    
    print(f"📍 Endpoint: {endpoint}")
    print(f"🌐 Hostname: {hostname}")
    print(f"🔌 Port: {port}")
    
    # Extract certificate using OpenSSL
    ca_file = "root-ca.pem"
    
    try:
        print(f"\n🔍 Extracting certificate to {ca_file}...")
        
        cmd = [
            "openssl", "s_client", 
            "-showcerts", 
            "-connect", f"{hostname}:{port}",
            "-servername", hostname
        ]
        
        # Run openssl command
        result = subprocess.run(
            cmd, 
            input="", 
            text=True, 
            capture_output=True, 
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"❌ OpenSSL command failed: {result.stderr}")
            return False
        
        # Extract certificates from output
        cert_data = []
        in_cert = False
        current_cert = []
        
        for line in result.stdout.split('\n'):
            if line.startswith('-----BEGIN CERTIFICATE-----'):
                in_cert = True
                current_cert = [line]
            elif line.startswith('-----END CERTIFICATE-----'):
                current_cert.append(line)
                cert_data.append('\n'.join(current_cert))
                in_cert = False
            elif in_cert:
                current_cert.append(line)
        
        if not cert_data:
            print("❌ No certificates found in output")
            return False
        
        # Write all certificates to file (chain)
        with open(ca_file, 'w') as f:
            for cert in cert_data:
                f.write(cert + '\n\n')
        
        print(f"✅ Extracted {len(cert_data)} certificate(s) to {ca_file}")
        
        # Show certificate info
        print(f"\n📄 Certificate Information:")
        try:
            cert_info_cmd = ["openssl", "x509", "-in", ca_file, "-noout", "-subject", "-issuer", "-dates"]
            cert_result = subprocess.run(cert_info_cmd, capture_output=True, text=True)
            if cert_result.returncode == 0:
                for line in cert_result.stdout.strip().split('\n'):
                    print(f"   {line}")
        except Exception as e:
            print(f"   Could not parse certificate info: {e}")
        
        print(f"\n💡 Usage:")
        print(f"   Add to your .env file:")
        print(f"   ROOT_CA_PATH={os.path.abspath(ca_file)}")
        print(f"   VERIFY_SSL=true")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Connection timeout - endpoint may be unreachable")
        return False
    except FileNotFoundError:
        print("❌ OpenSSL not found - please install OpenSSL")
        return False
    except Exception as e:
        print(f"❌ Error extracting certificate: {e}")
        return False


def test_with_extracted_ca():
    """Test connection using the extracted CA certificate."""
    
    ca_file = "root-ca.pem"
    
    if not Path(ca_file).exists():
        print(f"❌ CA file {ca_file} not found - run extract first")
        return False
    
    print(f"\n🧪 Testing connection with extracted CA...")
    
    # Load environment
    load_dotenv()
    
    # Import and run quick test with CA
    sys.path.insert(0, str(Path(__file__).parent))
    
    # Set environment for test
    os.environ["ROOT_CA_PATH"] = os.path.abspath(ca_file)
    os.environ["VERIFY_SSL"] = "true"
    
    try:
        from quick_s3_test import quick_s3_test
        return quick_s3_test()
    except ImportError:
        print("❌ Could not import quick_s3_test")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test with extracted CA
        success = test_with_extracted_ca()
    else:
        # Extract CA certificate
        success = extract_ca_certificate()
        
        if success:
            print(f"\n🔄 To test with the extracted certificate, run:")
            print(f"   python {__file__} --test")
    
    sys.exit(0 if success else 1)
