#!/usr/bin/env python3
"""
Quick 403 Causes Checker

Schnelle Überprüfung der häufigsten 403-Fehler Ursachen.
"""

import os
import re
from dotenv import load_dotenv


def check_403_causes():
    """Überprüft häufigste 403-Ursachen."""
    
    print("⚡ Quick 403 Causes Checker")
    print("-" * 30)
    
    load_dotenv()
    
    issues = []
    
    # Check 1: Placeholder values
    print("1️⃣ Prüfe auf Platzhalter-Werte...")
    endpoint = os.getenv("HCP_ENDPOINT") or os.getenv("S3_ENDPOINT")
    access_key = os.getenv("HCP_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("HCP_SECRET_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("HCP_NAMESPACE") or os.getenv("S3_BUCKET")
    
    placeholders = ["your-", "example", "change-me", "replace", "placeholder"]
    
    for key, value in [("Endpoint", endpoint), ("Access Key", access_key), 
                       ("Secret Key", secret_key), ("Bucket", bucket)]:
        if not value:
            issues.append(f"❌ {key} nicht gesetzt")
        elif any(placeholder in value.lower() for placeholder in placeholders):
            issues.append(f"❌ {key} enthält Platzhalter: {value}")
        else:
            print(f"   ✅ {key} scheint gültig")
    
    # Check 2: Key format
    print("\n2️⃣ Prüfe Key-Format...")
    if access_key:
        if len(access_key) < 10:
            issues.append("❌ Access Key zu kurz (mindestens 10 Zeichen)")
        elif not re.match(r'^[A-Za-z0-9]+$', access_key):
            issues.append("❌ Access Key enthält ungültige Zeichen")
        else:
            print("   ✅ Access Key Format ok")
    
    if secret_key:
        if len(secret_key) < 20:
            issues.append("❌ Secret Key zu kurz (mindestens 20 Zeichen)")
        elif not re.match(r'^[A-Za-z0-9+/]+={0,2}$', secret_key):
            issues.append("❌ Secret Key Format ungültig (sollte Base64 sein)")
        else:
            print("   ✅ Secret Key Format ok")
    
    # Check 3: Endpoint format
    print("\n3️⃣ Prüfe Endpoint-Format...")
    if endpoint:
        if not endpoint.startswith(("http://", "https://")):
            issues.append("❌ Endpoint benötigt http:// oder https://")
        elif not re.match(r'^https?://[a-zA-Z0-9.-]+', endpoint):
            issues.append("❌ Endpoint URL Format ungültig")
        else:
            print("   ✅ Endpoint Format ok")
    
    # Check 4: Bucket/Namespace format
    print("\n4️⃣ Prüfe Bucket/Namespace-Format...")
    if bucket:
        if len(bucket) < 3:
            issues.append("❌ Bucket/Namespace zu kurz (mindestens 3 Zeichen)")
        elif not re.match(r'^[a-z0-9.-]+$', bucket.lower()):
            issues.append("❌ Bucket/Namespace darf nur Kleinbuchstaben, Zahlen, Punkte und Bindestriche enthalten")
        else:
            print("   ✅ Bucket/Namespace Format ok")
    
    # Check 5: Common HCP endpoint patterns
    print("\n5️⃣ Prüfe HCP Endpoint Muster...")
    if endpoint:
        hcp_patterns = [
            r".*hcp-europe\.com",
            r".*hcp\.com", 
            r".*hcp\.ash\.ash\.com",
            r".*hcp\.us\.ash\.com"
        ]
        
        if any(re.search(pattern, endpoint) for pattern in hcp_patterns):
            print("   ✅ Endpoint sieht wie HCP Endpoint aus")
        else:
            print("   ⚠️  Endpoint entspricht nicht typischen HCP Mustern")
    
    # Summary
    print(f"\n📊 Zusammenfassung:")
    if issues:
        print("❌ Gefundene Probleme:")
        for issue in issues:
            print(f"   {issue}")
        
        print(f"\n💡 Empfehlung:")
        print("   1. Korrigieren Sie die oben genannten Probleme")
        print("   2. Führen Sie 'python debug_403.py' für detaillierte Tests aus")
        print("   3. Prüfen Sie Ihre HCP Portal Konfiguration")
        
        return False
    else:
        print("✅ Keine offensichtlichen Konfigurationsfehler gefunden")
        print("   → Das Problem liegt wahrscheinlich bei Berechtigungen oder Netzwerk")
        print("   → Führen Sie 'python debug_403.py' für detaillierte Tests aus")
        return True


if __name__ == "__main__":
    success = check_403_causes()
    sys.exit(0 if success else 1)
