#!/usr/bin/env python3
"""
403 Error Debug Helper

Systematische Analyse von 403 Fehlern bei S3/HCP Verbindungen.
"""

import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


def analyze_403_error():
    """Detaillierte Analyse von 403 Fehlern."""
    
    print("🔍 403 Fehler Analyse")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Get configuration
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    access_key = os.getenv("HCP_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("HCP_SECRET_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("HCP_NAMESPACE") or os.getenv("S3_BUCKET")
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
    root_ca_path = os.getenv("ROOT_CA_PATH")
    
    print("📋 Konfigurations-Check:")
    print(f"   Endpoint: {'✅' if endpoint else '❌'} {endpoint or 'Nicht gesetzt'}")
    print(f"   Access Key: {'✅' if access_key else '❌'} {'***' if access_key else 'Nicht gesetzt'}")
    print(f"   Secret Key: {'✅' if secret_key else '❌'} {'***' if secret_key else 'Nicht gesetzt'}")
    print(f"   Bucket/Namespace: {'✅' if bucket else '❌'} {bucket or 'Nicht gesetzt'}")
    print(f"   SSL Verification: {'✅' if verify_ssl else '❌'} {verify_ssl}")
    if root_ca_path:
        print(f"   Custom CA: {'✅' if Path(root_ca_path).exists() else '❌'} {root_ca_path}")
    
    if not all([endpoint, access_key, secret_key, bucket]):
        print("\n❌ Fehlende Konfiguration - bitte .env Datei prüfen!")
        return False
    
    print(f"\n🧪 Verbindungstests...")
    
    # Configure SSL verification
    verify_config = verify_ssl
    if root_ca_path and verify_ssl:
        verify_config = root_ca_path
    
    # Test 1: Basic connectivity without bucket operations
    print("\n1️⃣ Test: Grundlegende Verbindung (ohne Bucket)")
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1',
            verify=verify_config
        )
        
        # Try to list buckets (this tests authentication)
        response = s3.list_buckets()
        print(f"✅ Authentifizierung erfolgreich")
        print(f"   Gefundene Buckets: {[b['Name'] for b in response.get('Buckets', [])]}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidAccessKeyId':
            print("❌ Ungültiger Access Key ID")
            print("   → Prüfen Sie HCP_ACCESS_KEY / S3_ACCESS_KEY_ID")
        elif error_code == 'SignatureDoesNotMatch':
            print("❌ Ungültiger Secret Key")
            print("   → Prüfen Sie HCP_SECRET_KEY / S3_SECRET_ACCESS_KEY")
        elif error_code == '403':
            print("❌ 403 Fehler beim List Buckets")
            print("   → Mögliche Ursachen:")
            print("     • Access/Secret Key falsch")
            print("     • IP-Adresse nicht erlaubt")
            print("     • Service Account fehlt Berechtigungen")
        else:
            print(f"❌ Authentifizierungsfehler: {error_code} - {e}")
        return False
    except Exception as e:
        print(f"❌ Verbindungsfehler: {e}")
        return False
    
    # Test 2: Check if specific bucket exists
    print(f"\n2️⃣ Test: Bucket '{bucket}' Zugriff")
    try:
        s3.head_bucket(Bucket=bucket)
        print("✅ Bucket existiert und ist zugreifbar")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            print(f"❌ Bucket '{bucket}' existiert nicht")
            print("   → Prüfen Sie HCP_NAMESPACE / S3_BUCKET")
            print("   → Oder erstellen Sie den Bucket im HCP Portal")
        elif error_code == '403':
            print(f"❌ 403 Fehler beim Bucket-Zugriff")
            print("   → Mögliche Ursachen:")
            print("     • Bucket existiert aber Sie haben keine Berechtigung")
            print("     • Falscher Namespace/Bucket Name")
            print("     • Service Account hat keine Bucket-Berechtigungen")
        else:
            print(f"❌ Bucket-Fehler: {error_code} - {e}")
        return False
    
    # Test 3: Try to list objects (tests read permissions)
    print(f"\n3️⃣ Test: Objekte auflisten (Read Berechtigung)")
    try:
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        count = len(response.get('Contents', []))
        print(f"✅ Read Berechtigung vorhanden ({count} Objekte gefunden)")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            print("❌ Keine Read Berechtigung für diesen Bucket")
            print("   → Service Account benötigt 'Read' Berechtigung für den Bucket")
        else:
            print(f"❌ Read Fehler: {error_code} - {e}")
        return False
    
    # Test 4: Try to upload a test file (tests write permissions)
    print(f"\n4️⃣ Test: Test-Datei hochladen (Write Berechtigung)")
    try:
        test_key = "permission-test.txt"
        test_content = b"Permission test - " + str(os.getpid()).encode()
        
        s3.put_object(
            Bucket=bucket,
            Key=test_key,
            Body=test_content,
            Metadata={'test': 'permission-check'}
        )
        print("✅ Write Berechtigung vorhanden")
        
        # Clean up
        s3.delete_object(Bucket=bucket, Key=test_key)
        print("✅ Test-Datei aufgeräumt")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            print("❌ Keine Write Berechtigung für diesen Bucket")
            print("   → Service Account benötigt 'Write' Berechtigung für den Bucket")
        else:
            print(f"❌ Write Fehler: {error_code} - {e}")
        return False
    
    print(f"\n🎉 Alle Berechtigungstests bestanden!")
    print("   → Die 403 Fehler sollten behoben sein")
    return True


def show_troubleshooting_guide():
    """Zeigt Troubleshooting-Guide."""
    
    print("\n" + "=" * 50)
    print("📚 403 Fehler Troubleshooting Guide")
    print("=" * 50)
    
    print("\n🔧 Häufige Ursachen und Lösungen:")
    
    print("\n1️⃣ Falsche Zugangsdaten:")
    print("   • Prüfen Sie Access Key und Secret Key")
    print("   • Stellen Sie sicher, dass keine Leerzeichen oder Sonderzeichen enthalten sind")
    print("   • Erneuern Sie die Keys im HCP Portal falls nötig")
    
    print("\n2️⃣ Bucket/Namespace Probleme:")
    print("   • Prüfen Sie den exakten Bucket/Namespace Namen")
    print("   • Stellen Sie sicher, dass der Bucket existiert")
    print("   • Bei HCP: Namespace muss erstellt und aktiv sein")
    
    print("\n3️⃣ Berechtigungsprobleme:")
    print("   • Service Account benötigt S3 Berechtigungen")
    print("   • Prüfen Sie IAM Policies oder HCP Service Key Berechtigungen")
    print("   • Stellen Sie sicher, dass Read/Write Berechtigungen vorhanden sind")
    
    print("\n4️⃣ Netzwerk/SSL Probleme:")
    print("   • Bei selbstsignierten Zertifikaten: VERIFY_SSL=false oder ROOT_CA_PATH setzen")
    print("   • Prüfen Sie Firewalls und Proxy-Einstellungen")
    print("   • Stellen Sie sicher, dass der Endpoint erreichbar ist")
    
    print("\n5️⃣ HCP Speziell:")
    print("   • Namespace muss aktiv sein")
    print("   • Service Key muss S3 Berechtigungen haben")
    print("   • Endpoint URL muss korrekt sein (z.B. https://*.hcp-europe.com)")
    
    print("\n🧪 Test-Commands:")
    print("   # Mit deaktiviertem SSL testen:")
    print("   VERIFY_SSL=false python debug_403.py")
    print("   ")
    print("   # CA-Zertifikat extrahieren:")
    print("   python extract_ca.py")
    print("   ")
    print("   # Mit CA-Zertifikat testen:")
    print("   ROOT_CA_PATH=/path/to/ca.pem python debug_403.py")


if __name__ == "__main__":
    print("🚀 403 Fehler Debug Helper")
    print("Systematische Analyse von S3/HCP Berechtigungsproblemen")
    print()
    
    success = analyze_403_error()
    
    if not success:
        show_troubleshooting_guide()
    
    print(f"\n📯 Ergebnis: {'ERFOLG' if success else 'FEHLER'}")
    sys.exit(0 if success else 1)
