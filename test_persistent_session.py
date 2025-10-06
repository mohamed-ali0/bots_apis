#!/usr/bin/env python3
"""
Test script for persistent session management
"""

import requests
import json
import time
import os

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None

# Credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"


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


def test_create_session():
    """Test creating a new persistent session"""
    print("\n" + "="*70)
    print("📌 Test 1: Creating Persistent Session")
    print("="*70)
    
    try:
        response = requests.post(f"{API_BASE_URL}/get_session", json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_KEY
        })
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Session created successfully!")
            print(f"  📋 Session ID: {data['session_id']}")
            print(f"  🆕 Is New: {data['is_new']}")
            print(f"  👤 Username: {data['username']}")
            print(f"  📅 Created At: {data['created_at']}")
            print(f"  ⏰ Expires At: {data['expires_at']}")
            print(f"  💬 Message: {data['message']}")
            return data['session_id']
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"  Error: {response.json()}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def test_reuse_session():
    """Test that calling get_session again returns the same session"""
    print("\n" + "="*70)
    print("🔄 Test 2: Reusing Existing Session")
    print("="*70)
    
    try:
        # First call
        print("📌 First call to /get_session...")
        response1 = requests.post(f"{API_BASE_URL}/get_session", json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_KEY
        })
        
        if response1.status_code != 200:
            print(f"❌ First call failed: {response1.status_code}")
            return False
        
        data1 = response1.json()
        session_id1 = data1['session_id']
        is_new1 = data1['is_new']
        
        print(f"  ✅ Got session: {session_id1} (is_new={is_new1})")
        
        # Second call (should return same session)
        print("\n📌 Second call to /get_session...")
        time.sleep(2)
        
        response2 = requests.post(f"{API_BASE_URL}/get_session", json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_KEY
        })
        
        if response2.status_code != 200:
            print(f"❌ Second call failed: {response2.status_code}")
            return False
        
        data2 = response2.json()
        session_id2 = data2['session_id']
        is_new2 = data2['is_new']
        
        print(f"  ✅ Got session: {session_id2} (is_new={is_new2})")
        
        # Verify they're the same
        if session_id1 == session_id2:
            print("\n✅ SUCCESS: Same session returned!")
            print(f"  📋 Session ID: {session_id1}")
            print(f"  🔄 Second call: is_new={is_new2} (should be False)")
            return True
        else:
            print("\n❌ FAILED: Different sessions returned!")
            print(f"  📋 First: {session_id1}")
            print(f"  📋 Second: {session_id2}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_health_check():
    """Test health check endpoint"""
    print("\n" + "="*70)
    print("💚 Test 3: Health Check with Session Counts")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check passed!")
            print(f"  📊 Status: {data['status']}")
            print(f"  🔌 Active Sessions: {data['active_sessions']}")
            print(f"  🔄 Persistent Sessions: {data['persistent_sessions']}")
            print(f"  🕐 Timestamp: {data['timestamp']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_session_usage():
    """Test using a session with another endpoint"""
    print("\n" + "="*70)
    print("🎯 Test 4: Using Session with /get_containers")
    print("="*70)
    print("⚠️  Note: This test requires session_id support in /get_containers endpoint")
    print("⚠️  TODO: Implement session_id parameter in /get_containers")
    
    # TODO: Implement this test once session_id is added to endpoints
    print("\n⏭️  Skipping for now (not yet implemented)")
    return None


def main():
    choose_server()
    
    print("\n" + "="*70)
    print("🧪 Persistent Session Management Test Suite")
    print("="*70)
    print(f"🌐 API: {API_BASE_URL}")
    print(f"👤 User: {USERNAME}")
    print("")
    
    results = []
    
    # Test 1: Create session
    session_id = test_create_session()
    results.append(("Create Session", session_id is not None))
    
    # Wait a bit
    time.sleep(3)
    
    # Test 2: Reuse session
    reuse_result = test_reuse_session()
    results.append(("Reuse Session", reuse_result))
    
    # Test 3: Health check
    health_result = test_health_check()
    results.append(("Health Check", health_result))
    
    # Test 4: Use session (TODO)
    # usage_result = test_session_usage()
    # results.append(("Session Usage", usage_result))
    
    # Summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status} - {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())


