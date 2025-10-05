#!/usr/bin/env python3
"""
Comprehensive Test Script for All E-Modal Business API Endpoints
Tests both session creation and session reuse modes
"""

import requests
import json
import time
from datetime import datetime
from typing import Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default credentials
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test data
TEST_CONTAINER_ID = "MSDU5772413L"  # For timeline test
TEST_TRUCKING_COMPANY = "FENIX MARINE SERVICES LTD"
TEST_TERMINAL = "ITS Long Beach"
TEST_MOVE_TYPE = "DROP EMPTY"
TEST_TRUCK_PLATE = "1234567"
TEST_OWN_CHASSIS = False

# Global session ID
SESSION_ID = None
API_BASE_URL = None

# ============================================================================
# SERVER SELECTION
# ============================================================================

def choose_server():
    """Let user choose which server to test"""
    global API_BASE_URL
    
    print("\n" + "="*70)
    print(" Server Selection")
    print("="*70)
    print("  1. Local server (http://127.0.0.1:5010)")
    print("  2. Remote server 1 (http://89.117.63.196:5010)")
    print("  3. Remote server 2 (http://37.60.243.201:5010)")
    print("  4. Custom URL")
    print("  5. Auto-test mode (Remote server 2 - Port 5010)")
    print("="*70)
    
    choice = input("\nEnter your choice (1-5) [default: 5]: ").strip() or "5"
    
    if choice == "1":
        API_BASE_URL = "http://127.0.0.1:5010"
    elif choice == "2":
        API_BASE_URL = "http://89.117.63.196:5010"
    elif choice == "3":
        API_BASE_URL = "http://37.60.243.201:5010"
    elif choice == "4":
        custom_url = input("Enter custom URL (e.g., http://localhost:5010): ").strip()
        API_BASE_URL = custom_url
    else:  # Auto-test mode
        API_BASE_URL = "http://37.60.243.201:5010"
    
    print(f"\n✅ Using: {API_BASE_URL}\n")
    return API_BASE_URL


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)


def print_result(success: bool, message: str, data: dict = None):
    """Print test result"""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")
    if data:
        print(f"   Data: {json.dumps(data, indent=2)}")


def make_request(endpoint: str, payload: dict, description: str) -> dict:
    """Make API request and handle errors"""
    print(f"\n📤 Testing: {description}")
    print(f"   Endpoint: {endpoint}")
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=300)
        elapsed = time.time() - start_time
        
        print(f"   ⏱️  Response time: {elapsed:.2f}s")
        print(f"   📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success!")
            return {"success": True, "data": result, "time": elapsed}
        else:
            try:
                error_data = response.json()
                print(f"   ❌ Failed: {response.status_code}")
                print(f"   Error: {json.dumps(error_data, indent=2)}")
                return {"success": False, "error": error_data, "status": response.status_code}
            except:
                print(f"   ❌ Failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return {"success": False, "error": response.text, "status": response.status_code}
    
    except requests.exceptions.Timeout:
        print(f"   ⏱️  Request timed out after 300 seconds")
        return {"success": False, "error": "Request timeout"}
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return {"success": False, "error": str(e)}


def health_check():
    """Check API health"""
    print_header("Health Check")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API is healthy")
            print(f"   Status: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            
            sessions_info = data.get('sessions', {})
            if sessions_info:
                print(f"   Active Sessions: {sessions_info.get('active_count', 0)}")
                print(f"   Session Capacity: {sessions_info.get('session_capacity', 'N/A')}")
            
            persistent_count = data.get('persistent_sessions', 0)
            if persistent_count:
                print(f"   Persistent Sessions: {persistent_count}")
            
            print(f"  ⏰ Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_get_session(username: str, password: str, captcha_key: str) -> Optional[str]:
    """Test /get_session endpoint"""
    print_header("Test 1: /get_session - Create Persistent Session")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key
    }
    
    result = make_request("/get_session", payload, "Create new persistent session")
    
    if result["success"]:
        data = result["data"]
        session_id = data.get("session_id")
        is_new = data.get("is_new")
        username_resp = data.get("username")
        
        print(f"\n📋 Session Created:")
        print(f"   Session ID: {session_id}")
        print(f"   Is New: {is_new}")
        print(f"   Username: {username_resp}")
        print(f"   Time: {result['time']:.2f}s")
        
        return session_id
    else:
        print(f"\n❌ Session creation failed!")
        return None


def test_get_containers_with_session(session_id: str, mode: str = "infinite"):
    """Test /get_containers with existing session"""
    print_header(f"Test 2a: /get_containers - Using Existing Session (Mode: {mode})")
    
    payload = {
        "session_id": session_id,
        "return_url": True,
        "debug": False
    }
    
    if mode == "infinite":
        payload["infinite_scrolling"] = True
    elif mode == "count":
        payload["target_count"] = 50
    elif mode == "container":
        payload["target_container_id"] = TEST_CONTAINER_ID
    
    result = make_request("/get_containers", payload, f"Get containers using session (mode: {mode})")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   File URL: {data.get('file_url')}")
        print(f"   Container Count: {data.get('container_count', 'N/A')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Session was reused!")
        else:
            print(f"   ⚠️  WARNING: New session was created (expected reuse)")
    else:
        print(f"\n❌ Test failed!")


def test_get_containers_with_credentials(username: str, password: str, captcha_key: str):
    """Test /get_containers with credentials (should reuse existing session)"""
    print_header("Test 2b: /get_containers - Using Credentials (Should Reuse Session)")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "target_count": 20,
        "return_url": True,
        "debug": False
    }
    
    result = make_request("/get_containers", payload, "Get containers using credentials")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   File URL: {data.get('file_url')}")
        print(f"   Container Count: {data.get('container_count', 'N/A')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Existing session was reused (credential match)!")
        else:
            print(f"   ⚠️  New session created (no matching session found)")
    else:
        print(f"\n❌ Test failed!")


def test_get_timeline_with_session(session_id: str, container_id: str):
    """Test /get_container_timeline with existing session"""
    print_header("Test 3a: /get_container_timeline - Using Existing Session")
    
    payload = {
        "session_id": session_id,
        "container_id": container_id,
        "debug": False
    }
    
    result = make_request("/get_container_timeline", payload, f"Get timeline for {container_id}")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Container ID: {data.get('container_id')}")
        print(f"   Passed Pregate: {data.get('passed_pregate')}")
        print(f"   Detection Method: {data.get('detection_method')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Session was reused!")
        else:
            print(f"   ⚠️  WARNING: New session was created (expected reuse)")
    else:
        print(f"\n❌ Test failed!")


def test_get_timeline_with_credentials(username: str, password: str, captcha_key: str, container_id: str):
    """Test /get_container_timeline with credentials"""
    print_header("Test 3b: /get_container_timeline - Using Credentials")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "container_id": container_id,
        "debug": False
    }
    
    result = make_request("/get_container_timeline", payload, f"Get timeline for {container_id}")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Container ID: {data.get('container_id')}")
        print(f"   Passed Pregate: {data.get('passed_pregate')}")
        print(f"   Detection Method: {data.get('detection_method')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Existing session was reused!")
        else:
            print(f"   ⚠️  New session created")
    else:
        print(f"\n❌ Test failed!")


def test_check_appointments_with_session(session_id: str):
    """Test /check_appointments with existing session"""
    print_header("Test 4a: /check_appointments - Using Existing Session")
    
    payload = {
        "session_id": session_id,
        "trucking_company": TEST_TRUCKING_COMPANY,
        "terminal": TEST_TERMINAL,
        "move_type": TEST_MOVE_TYPE,
        "container_id": TEST_CONTAINER_ID,
        "truck_plate": TEST_TRUCK_PLATE,
        "own_chassis": TEST_OWN_CHASSIS
    }
    
    result = make_request("/check_appointments", payload, "Check appointments using session")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Appointment Session ID: {data.get('appointment_session_id')}")
        print(f"   Available Times: {len(data.get('available_times', []))} slots")
        print(f"   Debug Bundle: {data.get('debug_bundle_url', 'N/A')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if data.get('available_times'):
            print(f"\n   📅 First 5 time slots:")
            for i, time_slot in enumerate(data['available_times'][:5], 1):
                print(f"      {i}. {time_slot}")
        
        if not data.get('is_new_session'):
            print(f"\n   ✅ SUCCESS: Session was reused!")
        else:
            print(f"   ⚠️  WARNING: New session was created (expected reuse)")
    else:
        print(f"\n❌ Test failed!")
        error = result.get('error', {})
        if isinstance(error, dict):
            print(f"   Current Phase: {error.get('current_phase', 'N/A')}")
            print(f"   Error: {error.get('error', 'Unknown')}")


def test_check_appointments_with_credentials(username: str, password: str, captcha_key: str):
    """Test /check_appointments with credentials"""
    print_header("Test 4b: /check_appointments - Using Credentials")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "trucking_company": TEST_TRUCKING_COMPANY,
        "terminal": TEST_TERMINAL,
        "move_type": TEST_MOVE_TYPE,
        "container_id": TEST_CONTAINER_ID,
        "truck_plate": TEST_TRUCK_PLATE,
        "own_chassis": TEST_OWN_CHASSIS
    }
    
    result = make_request("/check_appointments", payload, "Check appointments using credentials")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Appointment Session ID: {data.get('appointment_session_id')}")
        print(f"   Available Times: {len(data.get('available_times', []))} slots")
        print(f"   Debug Bundle: {data.get('debug_bundle_url', 'N/A')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"\n   ✅ SUCCESS: Existing session was reused!")
        else:
            print(f"   ⚠️  New session created")
    else:
        print(f"\n❌ Test failed!")


def test_get_booking_number_with_session(session_id: str, container_id: str):
    """Test /get_booking_number with existing session"""
    print_header(f"Test 5a: /get_booking_number - Using Existing Session")
    
    payload = {
        "session_id": session_id,
        "container_id": container_id,
        "debug": False
    }
    
    result = make_request("/get_booking_number", payload, f"Get booking number for {container_id}")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Container ID: {data.get('container_id')}")
        print(f"   Booking Number: {data.get('booking_number') or 'Not available'}")
        if data.get('message'):
            print(f"   Message: {data.get('message')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Session was reused!")
        else:
            print(f"   ⚠️  WARNING: New session was created (expected reuse)")
    else:
        print(f"\n❌ Test failed!")


def test_get_booking_number_with_credentials(username: str, password: str, captcha_key: str, container_id: str):
    """Test /get_booking_number with credentials"""
    print_header(f"Test 5b: /get_booking_number - Using Credentials")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "container_id": container_id,
        "debug": False
    }
    
    result = make_request("/get_booking_number", payload, f"Get booking number for {container_id}")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Container ID: {data.get('container_id')}")
        print(f"   Booking Number: {data.get('booking_number') or 'Not available'}")
        if data.get('message'):
            print(f"   Message: {data.get('message')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Existing session was reused!")
        else:
            print(f"   ⚠️  New session created")
    else:
        print(f"\n❌ Test failed!")


def test_get_appointments_with_session(session_id: str, mode: str = "count", target: int = 10):
    """Test /get_appointments with existing session"""
    print_header(f"Test 6a: /get_appointments - Using Existing Session (Mode: {mode})")
    
    payload = {
        "session_id": session_id,
        "debug": False
    }
    
    if mode == "infinite":
        payload["infinite_scrolling"] = True
    elif mode == "count":
        payload["target_count"] = target
    
    result = make_request("/get_appointments", payload, f"Get appointments (mode: {mode}, target: {target})")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Selected Count: {data.get('selected_count')}")
        print(f"   File URL: {data.get('file_url')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Session was reused!")
        else:
            print(f"   ⚠️  WARNING: New session was created (expected reuse)")
    else:
        print(f"\n❌ Test failed!")


def test_get_appointments_with_credentials(username: str, password: str, captcha_key: str, target: int = 10):
    """Test /get_appointments with credentials"""
    print_header(f"Test 6b: /get_appointments - Using Credentials")
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_key,
        "target_count": target,
        "debug": False
    }
    
    result = make_request("/get_appointments", payload, f"Get {target} appointments using credentials")
    
    if result["success"]:
        data = result["data"]
        print(f"\n📊 Results:")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Is New Session: {data.get('is_new_session')}")
        print(f"   Selected Count: {data.get('selected_count')}")
        print(f"   File URL: {data.get('file_url')}")
        print(f"   Time: {result['time']:.2f}s")
        
        if not data.get('is_new_session'):
            print(f"   ✅ SUCCESS: Existing session was reused!")
        else:
            print(f"   ⚠️  New session created")
    else:
        print(f"\n❌ Test failed!")


def test_make_appointment_preview():
    """Preview /make_appointment test (without actually running it)"""
    print_header("Test 7: /make_appointment - Preview Only")
    
    print("""
⚠️  WARNING: /make_appointment ACTUALLY SUBMITS appointments!

This test is SKIPPED by default to prevent accidental submissions.

To test /make_appointment, you would use:

📤 With Session ID:
{
    "session_id": "session_XXX",
    "trucking_company": "...",
    "terminal": "...",
    "move_type": "...",
    "container_id": "...",
    "truck_plate": "...",
    "own_chassis": false,
    "appointment_time": "2025-10-10 08:00"
}

📤 With Credentials:
{
    "username": "...",
    "password": "...",
    "captcha_api_key": "...",
    "trucking_company": "...",
    "terminal": "...",
    "move_type": "...",
    "container_id": "...",
    "truck_plate": "...",
    "own_chassis": false,
    "appointment_time": "2025-10-10 08:00"
}

✅ Both modes support session reuse!
    """)


# ============================================================================
# MAIN TEST SUITE
# ============================================================================

def run_mode_create_session():
    """Mode 1: Test with session creation"""
    global SESSION_ID
    
    print("\n" + "🔵"*35)
    print("MODE 1: Create Session + Test All Endpoints")
    print("🔵"*35)
    
    # Step 1: Health check
    if not health_check():
        print("\n❌ Health check failed. Aborting.")
        return False
    
    # Step 2: Create session
    print("\n⏸️  Press Enter to create session...")
    input()
    
    SESSION_ID = test_get_session(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY)
    if not SESSION_ID:
        print("\n❌ Session creation failed. Aborting.")
        return False
    
    # Step 3: Test get_containers with session
    print("\n⏸️  Press Enter to test /get_containers with session...")
    input()
    test_get_containers_with_session(SESSION_ID, mode="count")
    
    # Step 4: Test get_timeline with session
    print("\n⏸️  Press Enter to test /get_container_timeline with session...")
    input()
    test_get_timeline_with_session(SESSION_ID, TEST_CONTAINER_ID)
    
    # Step 5: Test get_booking_number with session
    print("\n⏸️  Press Enter to test /get_booking_number with session...")
    input()
    test_get_booking_number_with_session(SESSION_ID, TEST_CONTAINER_ID)
    
    # Step 6: Test get_appointments with session (OPTIONAL - takes time)
    print("\n⏸️  Test /get_appointments with session? (takes ~30s for 10 appointments) [y/N]:")
    if input().strip().lower() == 'y':
        test_get_appointments_with_session(SESSION_ID, mode="count", target=10)
    else:
        print("   ⏭️  Skipped /get_appointments")
    
    # Step 7: Test check_appointments with session (OPTIONAL - takes time)
    print("\n⏸️  Test /check_appointments with session? (takes ~60s) [y/N]:")
    if input().strip().lower() == 'y':
        test_check_appointments_with_session(SESSION_ID)
    else:
        print("   ⏭️  Skipped /check_appointments")
    
    # Step 8: Preview make_appointment
    test_make_appointment_preview()
    
    # Final health check
    print("\n⏸️  Press Enter for final health check...")
    input()
    health_check()
    
    print(f"\n✅ MODE 1 COMPLETED")
    print(f"📋 Session ID: {SESSION_ID}")
    print(f"   You can use this session in MODE 2 or other requests")
    
    return True


def run_mode_use_credentials():
    """Mode 2: Test with credentials (should reuse existing sessions)"""
    print("\n" + "🟢"*35)
    print("MODE 2: Use Credentials (Auto Session Reuse)")
    print("🟢"*35)
    
    print("""
This mode tests credential-based session reuse.
If you ran MODE 1 first, the system should automatically reuse that session!
    """)
    
    # Step 1: Health check
    if not health_check():
        print("\n❌ Health check failed. Aborting.")
        return False
    
    # Step 2: Test get_containers with credentials
    print("\n⏸️  Press Enter to test /get_containers with credentials...")
    input()
    test_get_containers_with_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY)
    
    # Step 3: Test get_timeline with credentials
    print("\n⏸️  Press Enter to test /get_container_timeline with credentials...")
    input()
    test_get_timeline_with_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY, TEST_CONTAINER_ID)
    
    # Step 4: Test get_booking_number with credentials
    print("\n⏸️  Press Enter to test /get_booking_number with credentials...")
    input()
    test_get_booking_number_with_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY, TEST_CONTAINER_ID)
    
    # Step 5: Test get_appointments with credentials (OPTIONAL - takes time)
    print("\n⏸️  Test /get_appointments with credentials? (takes ~30s for 10 appointments) [y/N]:")
    if input().strip().lower() == 'y':
        test_get_appointments_with_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY, target=10)
    else:
        print("   ⏭️  Skipped /get_appointments")
    
    # Step 6: Test check_appointments with credentials (OPTIONAL - takes time)
    print("\n⏸️  Test /check_appointments with credentials? (takes ~60s) [y/N]:")
    if input().strip().lower() == 'y':
        test_check_appointments_with_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY)
    else:
        print("   ⏭️  Skipped /check_appointments")
    
    # Final health check
    print("\n⏸️  Press Enter for final health check...")
    input()
    health_check()
    
    print(f"\n✅ MODE 2 COMPLETED")
    
    return True


def main():
    """Main test orchestrator"""
    print("\n" + "="*70)
    print(" E-Modal Business API - Comprehensive Endpoint Test")
    print("="*70)
    print("""
This script tests ALL endpoints in two modes:
  MODE 1: Create explicit session, then use session_id
  MODE 2: Use credentials (tests automatic session reuse)

Endpoints tested:
  ✅ /get_session
  ✅ /get_containers
  ✅ /get_container_timeline
  ✅ /get_booking_number (NEW!)
  ✅ /get_appointments (NEW!)
  ✅ /check_appointments
  ℹ️  /make_appointment (preview only - no actual submission)
    """)
    
    # Choose server
    choose_server()
    
    # Choose test mode
    print("\n" + "="*70)
    print(" Test Mode Selection")
    print("="*70)
    print("  1. MODE 1: Create session + test with session_id")
    print("  2. MODE 2: Test with credentials (auto-reuse)")
    print("  3. Both modes sequentially")
    print("  4. Quick test (MODE 1 only, no appointments)")
    print("="*70)
    
    mode_choice = input("\nEnter your choice (1-4) [default: 3]: ").strip() or "3"
    
    if mode_choice == "1":
        run_mode_create_session()
    elif mode_choice == "2":
        run_mode_use_credentials()
    elif mode_choice == "3":
        run_mode_create_session()
        print("\n\n" + "🔄"*35)
        print("Switching to MODE 2...")
        print("🔄"*35)
        time.sleep(2)
        run_mode_use_credentials()
    elif mode_choice == "4":
        print("\n🚀 Quick Test Mode")
        global SESSION_ID
        health_check()
        SESSION_ID = test_get_session(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_CAPTCHA_KEY)
        if SESSION_ID:
            test_get_containers_with_session(SESSION_ID, mode="count")
            test_get_timeline_with_session(SESSION_ID, TEST_CONTAINER_ID)
            test_get_booking_number_with_session(SESSION_ID, TEST_CONTAINER_ID)
            print("\n⏸️  Test /get_appointments (10 appointments)? [y/N]:")
            if input().strip().lower() == 'y':
                test_get_appointments_with_session(SESSION_ID, mode="count", target=10)
        health_check()
    
    print("\n" + "="*70)
    print("✅ All Tests Completed!")
    print("="*70)
    
    if SESSION_ID:
        print(f"\n📋 Session ID: {SESSION_ID}")
        print("   You can use this session_id for manual testing\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

