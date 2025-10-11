"""
Test script for check_appointments with alternative import form (Line/Equip Size)
Tests the form that doesn't have container number field but has Line and Equip Size dropdowns
"""

import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:5010"  # Change to your server URL
# API_BASE_URL = "http://89.117.63.196:5010"  # Remote server option

# Credentials
USERNAME = "jfernandez"
PASSWORD = "Julian_1"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test data for alternative import form
TEST_DATA = {
    "username": USERNAME,
    "password": PASSWORD,
    "captcha_api_key": CAPTCHA_API_KEY,
    "container_type": "import",
    "container_id": "TCLU8784503",  # For display in screenshot
    "trucking_company": "K & R TRANSPORTATION LLC",
    "terminal": "TraPac LLC - Los Angeles",
    "move_type": "DROP EMPTY",
    "line": "GMSU",
    "equip_size": "40DH",
    "truck_plate": "ABC123",  # For Phase 2
    "own_chassis": True,
    "debug": False  # Set to True to get debug bundle
}

def print_separator(title=""):
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    else:
        print(f"{'='*70}")

def test_alternative_import_form():
    """Test check_appointments with Line/Equip Size form"""
    
    print_separator("CHECK APPOINTMENTS - Alternative Import Form Test")
    print(f"📋 Testing alternative import form (Line/Equip Size)")
    print(f"   Container: {TEST_DATA['container_id']}")
    print(f"   Line: {TEST_DATA['line']}")
    print(f"   Equip Size: {TEST_DATA['equip_size']}")
    print(f"   Terminal: {TEST_DATA['terminal']}")
    print(f"   Move Type: {TEST_DATA['move_type']}")
    print(f"   Trucking: {TEST_DATA['trucking_company']}")
    
    try:
        print(f"\n🚀 Sending request to {API_BASE_URL}/check_appointments...")
        response = requests.post(
            f"{API_BASE_URL}/check_appointments",
            json=TEST_DATA,
            timeout=600  # 10 minutes
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        try:
            result = response.json()
            print(f"\n📄 Response:")
            print(json.dumps(result, indent=2))
            
            if response.status_code == 200 and result.get('success'):
                print_separator("✅ SUCCESS")
                print(f"✅ Alternative form worked successfully!")
                print(f"   Session ID: {result.get('session_id')}")
                print(f"   Is New Session: {result.get('is_new_session')}")
                print(f"   Current Phase: {result.get('current_phase')}")
                
                # Display appointment times if available
                if 'appointment_times' in result:
                    times = result['appointment_times']
                    print(f"\n📅 Available Appointment Times: {len(times)}")
                    for i, time_slot in enumerate(times[:5], 1):  # Show first 5
                        print(f"   {i}. {time_slot}")
                    if len(times) > 5:
                        print(f"   ... and {len(times) - 5} more")
                
                # Display screenshot URL if available
                if 'dropdown_screenshot_url' in result:
                    print(f"\n📸 Dropdown Screenshot: {result['dropdown_screenshot_url']}")
                
                # Display debug bundle if available
                if 'debug_bundle_url' in result:
                    print(f"\n📦 Debug Bundle: {result['debug_bundle_url']}")
                    
            else:
                print_separator("❌ FAILED")
                print(f"❌ Request failed")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                
                if 'message' in result:
                    print(f"   Message: {result['message']}")
                
                if result.get('error') and 'line' in result['error'].lower():
                    print(f"\n💡 TIP: This error suggests the Line field is required")
                    print(f"   Line value provided: {TEST_DATA['line']}")
                
                if result.get('error') and 'equip_size' in result['error'].lower():
                    print(f"\n💡 TIP: This error suggests the Equip Size field is required")
                    print(f"   Equip Size value provided: {TEST_DATA['equip_size']}")
                
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response")
            print(f"Raw response: {response.text[:500]}")
    
    except requests.exceptions.Timeout:
        print(f"⏱️ Request timed out after 10 minutes")
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error - is the server running at {API_BASE_URL}?")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

def test_with_session():
    """Test using an existing session (faster for repeated tests)"""
    
    print_separator("TEST WITH EXISTING SESSION")
    
    # First create a session
    print("📝 Step 1: Creating session...")
    session_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_session",
            json=session_data,
            timeout=600
        )
        
        if response.status_code == 200:
            result = response.json()
            session_id = result.get('session_id')
            print(f"✅ Session created: {session_id}")
            
            # Now test with this session
            print(f"\n📝 Step 2: Testing alternative form with session...")
            test_data_with_session = {
                "session_id": session_id,
                "container_type": "import",
                "container_id": "TCLU8784503",
                "trucking_company": "K & R TRANSPORTATION LLC",
                "terminal": "TraPac LLC - Los Angeles",
                "move_type": "DROP EMPTY",
                "line": "GMSU",
                "equip_size": "40DH",
                "truck_plate": "ABC123",
                "own_chassis": True,
                "debug": False
            }
            
            response = requests.post(
                f"{API_BASE_URL}/check_appointments",
                json=test_data_with_session,
                timeout=600
            )
            
            print(f"📊 Status Code: {response.status_code}")
            result = response.json()
            print(f"\n📄 Response:")
            print(json.dumps(result, indent=2))
            
            if response.status_code == 200 and result.get('success'):
                print_separator("✅ SUCCESS WITH SESSION")
                print(f"✅ Alternative form worked with existing session!")
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run all tests"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║  Alternative Import Form Test (Line/Equip Size)                  ║
║                                                                   ║
║  This tests the import appointment form that has:                ║
║  - Line dropdown (instead of container number field)             ║
║  - Equip Size dropdown                                           ║
║  - Quantity field (auto-filled with 1)                           ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"🔗 API Base URL: {API_BASE_URL}")
    print(f"👤 Username: {USERNAME}")
    print(f"🔑 Captcha Key: {CAPTCHA_API_KEY[:10]}...")
    
    # Choose test mode
    print(f"\n📋 Test Options:")
    print(f"   1. Test with new session (slower, complete flow)")
    print(f"   2. Test with existing session (faster)")
    print(f"   3. Run both tests")
    
    choice = input(f"\nEnter choice (1-3) [default: 1]: ").strip() or "1"
    
    if choice == "1":
        test_alternative_import_form()
    elif choice == "2":
        test_with_session()
    elif choice == "3":
        test_alternative_import_form()
        print(f"\n{'='*70}\n")
        time.sleep(2)
        test_with_session()
    else:
        print(f"Invalid choice. Running default test...")
        test_alternative_import_form()
    
    print_separator("TEST COMPLETE")

if __name__ == "__main__":
    main()

