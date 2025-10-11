"""
Test script for the new endpoints: /get_booking_number and /get_appointments
Tests both session creation and session reuse modes
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

# Configuration
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Global session ID
SESSION_ID = None


def choose_server() -> str:
    """Let user choose which server to test against"""
    print("\n" + "="*70)
    print(" Choose Server")
    print("="*70)
    print("1. Local server (http://localhost:5010)")
    print("2. Remote server 1 (http://89.117.63.196:5010)")
    print("3. Remote server 2 (http://37.60.243.201:5010) [Default]")
    print("4. Custom URL")
    
    choice = input("\nEnter your choice (1/2/3/4) [default: 3]: ").strip()
    
    if not choice or choice == "3":
        return "http://37.60.243.201:5010"
    elif choice == "1":
        return "http://localhost:5010"
    elif choice == "2":
        return "http://89.117.63.196:5010"
    elif choice == "4":
        custom_url = input("Enter custom URL (e.g., http://192.168.1.100:5010): ").strip()
        return custom_url if custom_url else "http://37.60.243.201:5010"
    else:
        print("Invalid choice. Using default: Remote server 2")
        return "http://37.60.243.201:5010"


def print_response(response: requests.Response, title: str = "Response"):
    """Pretty print API response"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print("="*70)
    print(f"Status Code: {response.status_code}")
    
    try:
        data = response.json()
        print(f"\n{json.dumps(data, indent=2)}")
        return data
    except json.JSONDecodeError:
        print(f"\nRaw response: {response.text[:500]}")
        return None


def test_health(api_base_url: str):
    """Test the health endpoint"""
    print("\n" + "="*70)
    print(" Health Check")
    print("="*70)
    
    try:
        response = requests.get(f"{api_base_url}/health")
        if response.status_code == 200:
            data = response.json()
            print("✅ API is healthy")
            print(f"   Status: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            print(f"   Session Capacity: {data.get('active_sessions')}/{data.get('max_sessions')}")
            print(f"   Persistent Sessions: {data.get('persistent_sessions')}")
            print(f"  ⏰ Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def create_session(api_base_url: str) -> Optional[str]:
    """Create a new session"""
    global SESSION_ID
    
    print("\n" + "="*70)
    print(" Creating Session")
    print("="*70)
    
    payload = {
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        "captcha_api_key": DEFAULT_CAPTCHA_KEY
    }
    
    print(f"📝 Username: {DEFAULT_USERNAME}")
    print(f"🔐 Password: {'*' * len(DEFAULT_PASSWORD)}")
    print(f"🔑 Captcha Key: {DEFAULT_CAPTCHA_KEY[:10]}...")
    
    try:
        response = requests.post(f"{api_base_url}/get_session", json=payload)
        data = print_response(response, "Session Creation")
        
        if response.status_code == 200 and data and data.get('success'):
            SESSION_ID = data.get('session_id')
            print(f"\n✅ Session created successfully!")
            print(f"   Session ID: {SESSION_ID}")
            print(f"   Username: {data.get('username')}")
            print(f"   Created At: {data.get('created_at')}")
            return SESSION_ID
        else:
            print(f"\n❌ Failed to create session")
            error = data.get('error') if data else response.text
            print(f"   Error: {error}")
            return None
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return None


def test_get_booking_number_with_session(api_base_url: str, container_id: str, debug: bool = False):
    """Test /get_booking_number with existing session"""
    print("\n" + "="*70)
    print(f" Test: Get Booking Number (Session Mode)")
    print("="*70)
    print(f"📦 Container ID: {container_id}")
    print(f"🔍 Session ID: {SESSION_ID}")
    print(f"🐛 Debug Mode: {debug}")
    
    payload = {
        "session_id": SESSION_ID,
        "container_id": container_id,
        "debug": debug
    }
    
    try:
        response = requests.post(f"{api_base_url}/get_booking_number", json=payload)
        data = print_response(response, "Get Booking Number Result")
        
        if response.status_code == 200 and data and data.get('success'):
            print(f"\n✅ Success!")
            print(f"   Booking Number: {data.get('booking_number')}")
            print(f"   Container ID: {data.get('container_id')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Is New Session: {data.get('is_new_session')}")
            
            if debug and data.get('debug_bundle_url'):
                print(f"   📦 Debug Bundle: {data.get('debug_bundle_url')}")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            error = data.get('error') if data else response.text
            print(f"   Error: {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def test_get_booking_number_with_credentials(api_base_url: str, container_id: str, debug: bool = False):
    """Test /get_booking_number with credentials (creates session automatically)"""
    print("\n" + "="*70)
    print(f" Test: Get Booking Number (Credentials Mode)")
    print("="*70)
    print(f"📦 Container ID: {container_id}")
    print(f"👤 Username: {DEFAULT_USERNAME}")
    print(f"🐛 Debug Mode: {debug}")
    
    payload = {
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        "captcha_api_key": DEFAULT_CAPTCHA_KEY,
        "container_id": container_id,
        "debug": debug
    }
    
    try:
        response = requests.post(f"{api_base_url}/get_booking_number", json=payload)
        data = print_response(response, "Get Booking Number Result")
        
        if response.status_code == 200 and data and data.get('success'):
            print(f"\n✅ Success!")
            print(f"   Booking Number: {data.get('booking_number')}")
            print(f"   Container ID: {data.get('container_id')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Is New Session: {data.get('is_new_session')}")
            
            if debug and data.get('debug_bundle_url'):
                print(f"   📦 Debug Bundle: {data.get('debug_bundle_url')}")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            error = data.get('error') if data else response.text
            print(f"   Error: {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def test_get_appointments_with_session(api_base_url: str, mode: str = "infinite", 
                                      target_value: Any = None, debug: bool = False):
    """Test /get_appointments with existing session"""
    print("\n" + "="*70)
    print(f" Test: Get Appointments (Session Mode)")
    print("="*70)
    print(f"🔍 Session ID: {SESSION_ID}")
    print(f"📊 Mode: {mode}")
    if target_value:
        print(f"🎯 Target: {target_value}")
    print(f"🐛 Debug Mode: {debug}")
    
    payload = {
        "session_id": SESSION_ID,
        "debug": debug
    }
    
    # Add mode-specific parameters
    if mode == "infinite":
        payload["infinite_scrolling"] = True
    elif mode == "count":
        payload["infinite_scrolling"] = False
        payload["target_count"] = target_value or 50
    elif mode == "id":
        payload["infinite_scrolling"] = False
        payload["target_appointment_id"] = target_value
    
    try:
        response = requests.post(f"{api_base_url}/get_appointments", json=payload)
        data = print_response(response, "Get Appointments Result")
        
        if response.status_code == 200 and data and data.get('success'):
            print(f"\n✅ Success!")
            print(f"   Selected Count: {data.get('selected_count')}")
            print(f"   File URL: {data.get('file_url')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Is New Session: {data.get('is_new_session')}")
            
            if debug and data.get('debug_bundle_url'):
                print(f"   📦 Debug Bundle: {data.get('debug_bundle_url')}")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            error = data.get('error') if data else response.text
            print(f"   Error: {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def test_get_appointments_with_credentials(api_base_url: str, mode: str = "infinite",
                                          target_value: Any = None, debug: bool = False):
    """Test /get_appointments with credentials (creates session automatically)"""
    print("\n" + "="*70)
    print(f" Test: Get Appointments (Credentials Mode)")
    print("="*70)
    print(f"👤 Username: {DEFAULT_USERNAME}")
    print(f"📊 Mode: {mode}")
    if target_value:
        print(f"🎯 Target: {target_value}")
    print(f"🐛 Debug Mode: {debug}")
    
    payload = {
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        "captcha_api_key": DEFAULT_CAPTCHA_KEY,
        "debug": debug
    }
    
    # Add mode-specific parameters
    if mode == "infinite":
        payload["infinite_scrolling"] = True
    elif mode == "count":
        payload["infinite_scrolling"] = False
        payload["target_count"] = target_value or 50
    elif mode == "id":
        payload["infinite_scrolling"] = False
        payload["target_appointment_id"] = target_value
    
    try:
        response = requests.post(f"{api_base_url}/get_appointments", json=payload)
        data = print_response(response, "Get Appointments Result")
        
        if response.status_code == 200 and data and data.get('success'):
            print(f"\n✅ Success!")
            print(f"   Selected Count: {data.get('selected_count')}")
            print(f"   File URL: {data.get('file_url')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Is New Session: {data.get('is_new_session')}")
            
            if debug and data.get('debug_bundle_url'):
                print(f"   📦 Debug Bundle: {data.get('debug_bundle_url')}")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            error = data.get('error') if data else response.text
            print(f"   Error: {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def run_mode_with_session(api_base_url: str):
    """Run tests using an existing session"""
    print("\n" + "="*70)
    print(" MODE: Using Existing Session")
    print("="*70)
    
    # Create session first
    if not create_session(api_base_url):
        print("\n❌ Failed to create session. Cannot continue.")
        return
    
    input("\n⏸️  Press Enter to start testing...")
    
    # Test 1: Get Booking Number
    print("\n" + "="*70)
    print(" TEST 1: Get Booking Number")
    print("="*70)
    container_id = input("Enter container ID [default: MSDU5772413L]: ").strip()
    if not container_id:
        container_id = "MSDU5772413L"
    
    debug = input("Enable debug mode? (y/n) [default: n]: ").strip().lower() == 'y'
    
    test_get_booking_number_with_session(api_base_url, container_id, debug)
    
    input("\n⏸️  Press Enter to continue to next test...")
    
    # Test 2: Get Appointments - Mode selection
    print("\n" + "="*70)
    print(" TEST 2: Get Appointments")
    print("="*70)
    print("Select scrolling mode:")
    print("1. Infinite scrolling (get all)")
    print("2. Get specific count")
    print("3. Get until appointment ID")
    
    mode_choice = input("\nEnter your choice (1/2/3) [default: 2]: ").strip()
    
    if mode_choice == "1":
        mode = "infinite"
        target = None
    elif mode_choice == "3":
        mode = "id"
        target = input("Enter target appointment ID: ").strip()
    else:
        mode = "count"
        target = input("Enter appointment count [default: 20]: ").strip()
        target = int(target) if target else 20
    
    debug = input("Enable debug mode? (y/n) [default: n]: ").strip().lower() == 'y'
    
    test_get_appointments_with_session(api_base_url, mode, target, debug)


def run_mode_with_credentials(api_base_url: str):
    """Run tests using credentials (auto-create sessions)"""
    print("\n" + "="*70)
    print(" MODE: Using Credentials (Auto-Create Sessions)")
    print("="*70)
    
    input("\n⏸️  Press Enter to start testing...")
    
    # Test 1: Get Booking Number
    print("\n" + "="*70)
    print(" TEST 1: Get Booking Number")
    print("="*70)
    container_id = input("Enter container ID [default: MSDU5772413L]: ").strip()
    if not container_id:
        container_id = "MSDU5772413L"
    
    debug = input("Enable debug mode? (y/n) [default: n]: ").strip().lower() == 'y'
    
    test_get_booking_number_with_credentials(api_base_url, container_id, debug)
    
    input("\n⏸️  Press Enter to continue to next test...")
    
    # Test 2: Get Appointments
    print("\n" + "="*70)
    print(" TEST 2: Get Appointments")
    print("="*70)
    print("Select scrolling mode:")
    print("1. Infinite scrolling (get all)")
    print("2. Get specific count")
    print("3. Get until appointment ID")
    
    mode_choice = input("\nEnter your choice (1/2/3) [default: 2]: ").strip()
    
    if mode_choice == "1":
        mode = "infinite"
        target = None
    elif mode_choice == "3":
        mode = "id"
        target = input("Enter target appointment ID: ").strip()
    else:
        mode = "count"
        target = input("Enter appointment count [default: 20]: ").strip()
        target = int(target) if target else 20
    
    debug = input("Enable debug mode? (y/n) [default: n]: ").strip().lower() == 'y'
    
    test_get_appointments_with_credentials(api_base_url, mode, target, debug)


def run_quick_test(api_base_url: str):
    """Run quick automated tests"""
    print("\n" + "="*70)
    print(" MODE: Quick Test (Automated)")
    print("="*70)
    
    # Create session
    if not create_session(api_base_url):
        print("\n❌ Failed to create session. Cannot continue.")
        return
    
    # Test 1: Get Booking Number (no debug)
    print("\n📋 Test 1/4: Get Booking Number (session, no debug)")
    test_get_booking_number_with_session(api_base_url, "MSDU5772413L", debug=False)
    
    # Test 2: Get Booking Number (with debug)
    print("\n📋 Test 2/4: Get Booking Number (credentials, with debug)")
    test_get_booking_number_with_credentials(api_base_url, "MSDU5772413L", debug=True)
    
    # Test 3: Get Appointments - Count mode
    print("\n📋 Test 3/4: Get Appointments (session, count=10)")
    test_get_appointments_with_session(api_base_url, mode="count", target_value=10, debug=False)
    
    # Test 4: Get Appointments - Infinite mode with debug
    print("\n📋 Test 4/4: Get Appointments (credentials, infinite, debug)")
    test_get_appointments_with_credentials(api_base_url, mode="count", target_value=5, debug=True)


def main():
    """Main function"""
    print("\n" + "="*70)
    print(" E-Modal New Endpoints Test Script")
    print(" Testing: /get_booking_number and /get_appointments")
    print("="*70)
    
    # Choose server
    api_base_url = choose_server()
    print(f"\n🌐 Using API: {api_base_url}")
    
    # Health check
    if not test_health(api_base_url):
        print("\n❌ API is not healthy. Please check the server.")
        sys.exit(1)
    
    # Choose test mode
    print("\n" + "="*70)
    print(" Choose Test Mode")
    print("="*70)
    print("1. Use existing session (create session, then test)")
    print("2. Use credentials (auto-create sessions for each test)")
    print("3. Quick automated test (run all tests)")
    
    mode = input("\nEnter your choice (1/2/3) [default: 1]: ").strip()
    
    if mode == "2":
        run_mode_with_credentials(api_base_url)
    elif mode == "3":
        run_quick_test(api_base_url)
    else:
        run_mode_with_session(api_base_url)
    
    # Final health check
    input("\n⏸️  Press Enter for final health check...")
    test_health(api_base_url)
    
    print("\n" + "="*70)
    print("✅ Test completed!")
    if SESSION_ID:
        print(f" Session ID: {SESSION_ID}")
        print(f" You can use this session_id in subsequent requests")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


