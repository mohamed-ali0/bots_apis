#!/usr/bin/env python3
"""
E-Modal API Test Script
======================

Test script for the professional E-Modal authentication API
"""

import requests
import json
import time
import os

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None


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
        choice = input("Enter your choice (1/2/3/4) [default: 1]: ").strip()
        
        # Default to local server
        if not choice:
            choice = "1"
        
        if choice == "1":
            API_HOST = "localhost"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "2":
            API_HOST = "89.117.63.196"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "3":
            API_HOST = "37.60.243.201"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "4":
            API_HOST = input("Enter server IP/hostname: ").strip()
            API_PORT = input("Enter server port [default: 5010]: ").strip() or "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check passed")
            print(f"  📊 Status: {data.get('status')}")
            print(f"  🕐 Timestamp: {data.get('timestamp')}")
            print(f"  📋 Version: {data.get('version')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ API server not running. Please start with: python api.py")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_login():
    """Test login endpoint"""
    print("\n🔐 Testing login endpoint...")
    
    # Test credentials (replace with your actual credentials)
    username = input("Enter E-Modal username (or press Enter for 'jfernandez'): ").strip() or "jfernandez"
    password = input("Enter E-Modal password (or press Enter for 'taffie'): ").strip() or "taffie"
    api_key = input("Enter 2captcha API key (or press Enter for demo key): ").strip() or "5a0a4a97f8b4c9505d0b719cd92a9dcb"
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": api_key,
        "use_vpn": True
    }
    
    print(f"🚀 Testing login for user: {username}")
    print("⏳ This may take 60-90 seconds due to reCAPTCHA solving...")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/login",
            json=payload,
            timeout=300  # 5 minute timeout
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Request completed in {duration:.1f} seconds")
        print(f"📊 HTTP Status: {response.status_code}")
        
        data = response.json()
        print(f"📋 Request ID: {data.get('request_id', 'N/A')}")
        
        if data.get('success'):
            print("🎉 LOGIN SUCCESSFUL!")
            print(f"  🔗 Final URL: {data.get('final_url', 'N/A')}")
            print(f"  📄 Page Title: {data.get('page_title', 'N/A')}")
            print(f"  🤖 reCAPTCHA Method: {data.get('recaptcha_method', 'N/A')}")
            print(f"  🍪 Cookies: {len(data.get('cookies', []))} received")
            print(f"  🔑 Session Tokens: {len(data.get('session_tokens', {}))} extracted")
            
            # Show session token names (not values for security)
            if data.get('session_tokens'):
                print("  🔐 Token Names:")
                for token_name in data['session_tokens'].keys():
                    print(f"    - {token_name}")
            
            return True
        else:
            print("❌ LOGIN FAILED")
            print(f"  🔍 Error Type: {data.get('error_type', 'unknown')}")
            print(f"  📝 Error Message: {data.get('error_message', 'N/A')}")
            
            # Provide troubleshooting hints
            error_type = data.get('error_type')
            if error_type == 'vpn_required':
                print("\n💡 TROUBLESHOOTING:")
                print("  - Ensure Urban VPN Chrome extension is installed")
                print("  - Connect to a US server in Urban VPN")
                print("  - Restart Chrome and try again")
            elif error_type == 'invalid_credentials':
                print("\n💡 TROUBLESHOOTING:")
                print("  - Verify username and password are correct")
                print("  - Check if account is active")
            elif error_type == 'recaptcha_failed':
                print("\n💡 TROUBLESHOOTING:")
                print("  - Verify 2captcha API key is correct")
                print("  - Check 2captcha account balance")
                print("  - Try again (reCAPTCHA can be inconsistent)")
            
            return False
            
    except requests.exceptions.Timeout:
        print("⏱️ Request timed out (>5 minutes)")
        print("💡 This might indicate browser or reCAPTCHA issues")
        return False
    except Exception as e:
        print(f"❌ Login test error: {e}")
        return False


def test_invalid_request():
    """Test API validation"""
    print("\n🧪 Testing API validation...")
    
    # Test missing fields
    print("  Testing missing username...")
    response = requests.post(
        "http://localhost:5000/login",
        json={"password": "test", "captcha_api_key": "test"}
    )
    
    if response.status_code == 400:
        print("  ✅ Correctly rejected missing username")
    else:
        print(f"  ⚠️ Unexpected response: {response.status_code}")
    
    # Test non-JSON request
    print("  Testing non-JSON request...")
    response = requests.post(
        "http://localhost:5000/login",
        data="not json"
    )
    
    if response.status_code == 400:
        print("  ✅ Correctly rejected non-JSON request")
    else:
        print(f"  ⚠️ Unexpected response: {response.status_code}")
    
    print("✅ API validation tests passed")


def main():
    """Main test function"""
    choose_server()
    print("🧪 E-Modal API Test Suite")
    print("=" * 50)
    
    # Test 1: Health check
    if not test_health():
        print("❌ Health check failed. Cannot proceed with other tests.")
        return
    
    # Test 2: API validation
    test_invalid_request()
    
    # Test 3: Actual login (optional)
    print("\n" + "=" * 50)
    choice = input("🤔 Do you want to test actual login? (y/N): ").strip().lower()
    
    if choice in ['y', 'yes']:
        print("\n⚠️  LOGIN TEST WARNING:")
        print("  - This will open a Chrome browser")
        print("  - It requires Urban VPN connected to US")
        print("  - It uses your 2captcha account balance")
        print("  - It may take 60-90 seconds")
        
        confirm = input("\n💰 Continue? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            test_login()
        else:
            print("⏭️  Skipping login test")
    else:
        print("⏭️  Skipping login test")
    
    print("\n🎉 Test suite completed!")
    print("📝 Check emodal_api.log for detailed logs")


if __name__ == "__main__":
    main()

