#!/usr/bin/env python3
"""
Test script for /get_booking_number endpoint

This script tests the booking number extraction functionality with various scenarios:
- Using existing session
- Using credentials (new session)
- Different container IDs
- Debug mode enabled/disabled
- Error handling
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
DEFAULT_SERVER = "http://37.60.243.201:5010"  # Remote server 2
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test container IDs
TEST_CONTAINERS = [
    "TRHU1866154",  # Primary test container
    "TRHU1866154",  # Secondary test container
    "TRHU1866154",  # Another test container
    "TRHU1866154",   # Invalid container for error testing
]

def choose_server():
    """Let user choose server"""
    print("\n🌐 Choose Server:")
    print("1. Local server (http://localhost:5010)")
    print("2. Remote server 1 (http://89.117.63.196:5010)")
    print("3. Remote server 2 (http://37.60.243.201:5010) [DEFAULT]")
    print("4. Custom server")
    
    choice = input("\nEnter choice (1-4) [3]: ").strip()
    
    if choice == "1":
        return "http://localhost:5010"
    elif choice == "2":
        return "http://89.117.63.196:5010"
    elif choice == "3" or choice == "":
        return "http://37.60.243.201:5010"
    elif choice == "4":
        custom = input("Enter custom server URL: ").strip()
        return custom if custom else DEFAULT_SERVER
    else:
        print("Invalid choice, using default server")
        return DEFAULT_SERVER

def test_health(server_url):
    """Test server health"""
    print(f"\n🏥 Testing server health: {server_url}")
    try:
        response = requests.get(f"{server_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy")
            print(f"   📊 Active sessions: {data.get('active_sessions', 0)}/{data.get('max_sessions', 0)}")
            print(f"   🔄 Persistent sessions: {data.get('persistent_sessions', 0)}")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server health check error: {e}")
        return False

def create_session(server_url, username, password, captcha_key):
    """Create a new session"""
    print(f"\n🔐 Creating session for user: {username}")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key
    }
    
    try:
        response = requests.post(f"{server_url}/get_session", json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Session created successfully")
                print(f"   🆔 Session ID: {data.get('session_id')}")
                print(f"   🆕 New session: {data.get('is_new')}")
                print(f"   👤 Username: {data.get('username')}")
                return data.get('session_id')
            else:
                print(f"❌ Session creation failed: {data.get('error')}")
                return None
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Session creation error: {e}")
        return None

def test_get_booking_number_with_session(server_url, session_id, container_id, debug=False):
    """Test get_booking_number using existing session"""
    print(f"\n📋 Testing get_booking_number with session")
    print(f"   🆔 Session: {session_id}")
    print(f"   📦 Container: {container_id}")
    print(f"   🐛 Debug mode: {debug}")
    
    payload = {
        "session_id": session_id,
        "container_id": container_id,
        "debug": debug
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{server_url}/get_booking_number", json=payload, timeout=120)
        end_time = time.time()
        
        print(f"   ⏱️  Response time: {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                booking_number = data.get("booking_number")
                print(f"✅ Booking number extraction successful")
                print(f"   📦 Container ID: {data.get('container_id')}")
                print(f"   🎫 Booking Number: {booking_number if booking_number else 'Not found'}")
                print(f"   🆔 Session ID: {data.get('session_id')}")
                print(f"   🆕 New session: {data.get('is_new_session')}")
                
                if debug and data.get("debug_bundle_url"):
                    print(f"   🐛 Debug bundle: {data.get('debug_bundle_url')}")
                
                return True
            else:
                print(f"❌ Booking number extraction failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

def test_get_booking_number_with_credentials(server_url, username, password, captcha_key, container_id, debug=False):
    """Test get_booking_number using credentials (new session)"""
    print(f"\n📋 Testing get_booking_number with credentials")
    print(f"   👤 Username: {username}")
    print(f"   📦 Container: {container_id}")
    print(f"   🐛 Debug mode: {debug}")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "container_id": container_id,
        "debug": debug
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{server_url}/get_booking_number", json=payload, timeout=120)
        end_time = time.time()
        
        print(f"   ⏱️  Response time: {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                booking_number = data.get("booking_number")
                print(f"✅ Booking number extraction successful")
                print(f"   📦 Container ID: {data.get('container_id')}")
                print(f"   🎫 Booking Number: {booking_number if booking_number else 'Not found'}")
                print(f"   🆔 Session ID: {data.get('session_id')}")
                print(f"   🆕 New session: {data.get('is_new_session')}")
                
                if debug and data.get("debug_bundle_url"):
                    print(f"   🐛 Debug bundle: {data.get('debug_bundle_url')}")
                
                return data.get('session_id')  # Return session for reuse
            else:
                print(f"❌ Booking number extraction failed: {data.get('error')}")
                return None
        else:
            print(f"❌ Request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None

def test_error_cases(server_url, session_id):
    """Test error cases"""
    print(f"\n🚨 Testing error cases")
    
    # Test 1: Missing container_id
    print(f"\n   Test 1: Missing container_id")
    payload = {"session_id": session_id}
    try:
        response = requests.post(f"{server_url}/get_booking_number", json=payload, timeout=30)
        if response.status_code == 400:
            print(f"   ✅ Correctly returned 400 for missing container_id")
        else:
            print(f"   ❌ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Invalid session_id
    print(f"\n   Test 2: Invalid session_id")
    payload = {
        "session_id": "invalid_session_123",
        "container_id": "MSCU5165756"
    }
    try:
        response = requests.post(f"{server_url}/get_booking_number", json=payload, timeout=30)
        if response.status_code == 400:
            print(f"   ✅ Correctly returned 400 for invalid session_id")
        else:
            print(f"   ❌ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Non-JSON request
    print(f"\n   Test 3: Non-JSON request")
    try:
        response = requests.post(f"{server_url}/get_booking_number", data="not json", timeout=30)
        if response.status_code == 400:
            print(f"   ✅ Correctly returned 400 for non-JSON request")
        else:
            print(f"   ❌ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def run_comprehensive_test(server_url, username, password, captcha_key):
    """Run comprehensive test suite"""
    print(f"\n{'='*70}")
    print(f"🧪 COMPREHENSIVE GET_BOOKING_NUMBER TEST SUITE")
    print(f"{'='*70}")
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Server: {server_url}")
    print(f"👤 Username: {username}")
    
    # Test 1: Health check
    if not test_health(server_url):
        print(f"\n❌ Server health check failed, aborting tests")
        return False
    
    # Test 2: Create session
    session_id = create_session(server_url, username, password, captcha_key)
    if not session_id:
        print(f"\n❌ Session creation failed, aborting tests")
        return False
    
    # Test 3: Test with valid containers using session
    print(f"\n{'='*50}")
    print(f"📋 Testing with valid containers (using session)")
    print(f"{'='*50}")
    
    success_count = 0
    for i, container_id in enumerate(TEST_CONTAINERS[:3], 1):  # Test first 3 containers
        print(f"\n--- Test {i}: {container_id} ---")
        if test_get_booking_number_with_session(server_url, session_id, container_id, debug=(i==1)):
            success_count += 1
        time.sleep(2)  # Brief pause between tests
    
    # Test 4: Test with credentials (new session)
    print(f"\n{'='*50}")
    print(f"📋 Testing with credentials (new session)")
    print(f"{'='*50}")
    
    new_session_id = test_get_booking_number_with_credentials(
        server_url, username, password, captcha_key, 
        TEST_CONTAINERS[0], debug=True
    )
    
    if new_session_id:
        success_count += 1
        print(f"✅ New session created: {new_session_id}")
    
    # Test 5: Test error cases
    print(f"\n{'='*50}")
    print(f"🚨 Testing error cases")
    print(f"{'='*50}")
    
    test_error_cases(server_url, session_id)
    
    # Test 6: Test invalid container
    print(f"\n--- Test: Invalid container ---")
    test_get_booking_number_with_session(server_url, session_id, TEST_CONTAINERS[3], debug=True)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Successful tests: {success_count}")
    print(f"📦 Containers tested: {len(TEST_CONTAINERS[:3])}")
    print(f"🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count >= 2:
        print(f"🎉 Overall result: PASSED")
        return True
    else:
        print(f"❌ Overall result: FAILED")
        return False

def run_quick_test(server_url, username, password, captcha_key):
    """Run quick test with one container"""
    print(f"\n🚀 QUICK TEST - Single container")
    
    if not test_health(server_url):
        return False
    
    # Test with credentials (includes session creation)
    session_id = test_get_booking_number_with_credentials(
        server_url, username, password, captcha_key, 
        TEST_CONTAINERS[0], debug=True
    )
    
    return session_id is not None

def main():
    """Main function"""
    print(f"\n🎯 GET_BOOKING_NUMBER ENDPOINT TEST SCRIPT")
    print(f"{'='*50}")
    
    # Choose server
    server_url = choose_server()
    
    # Get credentials
    print(f"\n👤 Enter credentials:")
    username = input(f"Username [{DEFAULT_USERNAME}]: ").strip() or DEFAULT_USERNAME
    password = input(f"Password [{DEFAULT_PASSWORD}]: ").strip() or DEFAULT_PASSWORD
    captcha_key = input(f"Captcha API Key [{DEFAULT_CAPTCHA_KEY}]: ").strip() or DEFAULT_CAPTCHA_KEY
    
    # Choose test mode
    print(f"\n🧪 Choose test mode:")
    print("1. Quick test (single container)")
    print("2. Comprehensive test (all containers + error cases)")
    print("3. Custom container test")
    
    choice = input("\nEnter choice (1-3) [1]: ").strip()
    
    if choice == "2":
        success = run_comprehensive_test(server_url, username, password, captcha_key)
    elif choice == "3":
        container_id = input("Enter container ID: ").strip()
        if not container_id:
            print("❌ No container ID provided")
            return
        
        print(f"\n🔍 Testing custom container: {container_id}")
        if not test_health(server_url):
            return
        
        session_id = test_get_booking_number_with_credentials(
            server_url, username, password, captcha_key, 
            container_id, debug=True
        )
        success = session_id is not None
    else:  # choice == "1" or default
        success = run_quick_test(server_url, username, password, captcha_key)
    
    # Final result
    print(f"\n{'='*50}")
    if success:
        print(f"🎉 TEST COMPLETED SUCCESSFULLY!")
    else:
        print(f"❌ TEST FAILED!")
    print(f"{'='*50}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
