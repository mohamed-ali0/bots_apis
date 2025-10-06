#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for /get_appointments endpoint
Uses the same inputs as check_appointments test script
"""

import os
import sys
import requests
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# API Configuration
API_HOST = None
API_PORT = None
API_BASE_URL = None

# Default Credentials (from check_appointments test)
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"


def choose_server():
    """Prompt user to choose between local or remote servers"""
    global API_HOST, API_PORT, API_BASE_URL
    
    # Check if running in non-interactive mode
    auto_test = os.environ.get('AUTO_TEST', '0') == '1'
    
    if auto_test or os.environ.get('API_HOST'):
        # Use environment variables in non-interactive mode
        API_HOST = os.environ.get('API_HOST', '37.60.243.201')
        API_PORT = os.environ.get('API_PORT', '5010')
        API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
        print(f"🌐 Using API server from environment: {API_BASE_URL}")
        return
    
    # Interactive mode - ask user
    print("\n" + "=" * 70)
    print("🌐 API Server Selection")
    print("=" * 70)
    print("Choose which server to connect to:")
    print("")
    print("  1. Local server     (http://localhost:5010)")
    print("  2. Remote server 1  (http://89.117.63.196:5010)")
    print("  3. Remote server 2  (http://37.60.243.201:5010)")
    print("  4. Custom server    (enter IP/hostname)")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3/4) [default: 3]: ").strip()
        
        # Default to remote server 2
        if not choice:
            choice = "3"
        
        if choice == "1":
            API_HOST = "localhost"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Using local server: {API_BASE_URL}\n")
            break
        elif choice == "2":
            API_HOST = "89.117.63.196"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Using remote server 1: {API_BASE_URL}\n")
            break
        elif choice == "3":
            API_HOST = "37.60.243.201"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Using remote server 2: {API_BASE_URL}\n")
            break
        elif choice == "4":
            API_HOST = input("Enter server IP/hostname: ").strip()
            API_PORT = input("Enter server port [default: 5010]: ").strip() or "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Using custom server: {API_BASE_URL}\n")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def test_get_appointments_infinite():
    """Test get_appointments with infinite scrolling mode"""
    print("\n" + "="*70)
    print("🧪 TESTING: /get_appointments (Infinite Scrolling)")
    print("="*70)
    
    username = os.getenv('EMODAL_USERNAME', DEFAULT_USERNAME)
    password = os.getenv('EMODAL_PASSWORD', DEFAULT_PASSWORD)
    captcha_api_key = os.getenv('CAPTCHA_API_KEY', DEFAULT_CAPTCHA_KEY)
    
    print(f"✅ Using credentials for user: {username}")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_api_key,
        "infinite_scrolling": True,
        "debug": True  # Enable debug mode to see screenshots
    }
    
    print("\n📤 Sending request to /get_appointments...")
    print("   Mode: Infinite Scrolling")
    print("   Debug: Enabled")
    print("\n⏳ This may take several minutes...\n")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_appointments",
            json=payload,
            timeout=600  # 10 minutes
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS!")
            print(f"   Selected Appointments: {result.get('selected_count', 0)}")
            print(f"   Excel File URL: {result.get('file_url', 'N/A')}")
            
            if result.get('debug_bundle_url'):
                print(f"\n📦 Debug Bundle: {result['debug_bundle_url']}")
            
            print(f"\n🔑 Session ID: {result.get('session_id', 'N/A')}")
            print(f"   New Session: {result.get('is_new_session', 'N/A')}")
            
            return result
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_get_appointments_count():
    """Test get_appointments with target count mode"""
    print("\n" + "="*70)
    print("🧪 TESTING: /get_appointments (Target Count)")
    print("="*70)
    
    username = os.getenv('EMODAL_USERNAME', DEFAULT_USERNAME)
    password = os.getenv('EMODAL_PASSWORD', DEFAULT_PASSWORD)
    captcha_api_key = os.getenv('CAPTCHA_API_KEY', DEFAULT_CAPTCHA_KEY)
    
    print(f"✅ Using credentials for user: {username}")
    
    target_count = input("\nEnter target count [default: 50]: ").strip()
    target_count = int(target_count) if target_count else 50
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_api_key,
        "target_count": target_count,
        "debug": True
    }
    
    print("\n📤 Sending request to /get_appointments...")
    print(f"   Mode: Target Count ({target_count} appointments)")
    print("   Debug: Enabled")
    print("\n⏳ This may take several minutes...\n")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_appointments",
            json=payload,
            timeout=600
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS!")
            print(f"   Selected Appointments: {result.get('selected_count', 0)}")
            print(f"   Excel File URL: {result.get('file_url', 'N/A')}")
            
            if result.get('debug_bundle_url'):
                print(f"\n📦 Debug Bundle: {result['debug_bundle_url']}")
            
            print(f"\n🔑 Session ID: {result.get('session_id', 'N/A')}")
            print(f"   New Session: {result.get('is_new_session', 'N/A')}")
            
            return result
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_get_appointments_with_session():
    """Test get_appointments using an existing session"""
    print("\n" + "="*70)
    print("🧪 TESTING: /get_appointments (Using Existing Session)")
    print("="*70)
    
    session_id = input("\nEnter session ID: ").strip()
    
    if not session_id:
        print("❌ Session ID is required")
        return
    
    target_count = input("Enter target count [default: 20]: ").strip()
    target_count = int(target_count) if target_count else 20
    
    payload = {
        "session_id": session_id,
        "target_count": target_count,
        "debug": True
    }
    
    print("\n📤 Sending request to /get_appointments...")
    print(f"   Session ID: {session_id}")
    print(f"   Mode: Target Count ({target_count} appointments)")
    print("   Debug: Enabled")
    print("\n⏳ This may take several minutes...\n")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_appointments",
            json=payload,
            timeout=600
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS!")
            print(f"   Selected Appointments: {result.get('selected_count', 0)}")
            print(f"   Excel File URL: {result.get('file_url', 'N/A')}")
            
            if result.get('debug_bundle_url'):
                print(f"\n📦 Debug Bundle: {result['debug_bundle_url']}")
            
            return result
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def main():
    """Main menu"""
    # First, choose server
    choose_server()
    
    print("\n" + "="*70)
    print("  E-MODAL GET APPOINTMENTS TESTING")
    print("="*70)
    print("\nSelect test to run:")
    print("  1. Infinite Scrolling (get all appointments)")
    print("  2. Target Count (get specific number)")
    print("  3. Use Existing Session")
    print("  4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        test_get_appointments_infinite()
    elif choice == "2":
        test_get_appointments_count()
    elif choice == "3":
        test_get_appointments_with_session()
    elif choice == "4":
        print("👋 Goodbye!")
        return
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()

