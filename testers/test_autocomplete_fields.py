"""
Test script for check_appointments with autocomplete fields (Line/Equip Size)
Tests the new autocomplete field handling with real container data
"""

import requests
import json
import time

# Configuration
API_BASE_URL = "http://37.60.243.201:5010"  # Change to your server URL
# API_BASE_URL = "http://89.117.63.196:5010"  # Remote server option

# Credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test data based on real container data
TEST_DATA = {
    "username": USERNAME,
    "password": PASSWORD,
    "captcha_api_key": CAPTCHA_API_KEY,
    "container_type": "import",
    "container_id": "TCLU8784503",
    "container_number": "TCLU8784503",  # For display in screenshots
    "trucking_company": "K & R TRANSPORTATION LLC",
    "terminal": "TraPac LLC - Los Angeles",
    "move_type": "DROP EMPTY",
    "line": "GMSU",  # From Excel column K
    "equip_size": "40DH",  # From Excel column O (Size Type)
    "truck_plate": "ABC123",  # For Phase 2
    "own_chassis": True,
    "manifested_date": "2025-09-08",  # From Excel data
    "last_free_day_date": "2025-09-21",  # From Excel data
    "debug": False  # Set to True to get debug bundle
}

# Test scenarios for different line values
TEST_SCENARIOS = [
    {
        "name": "Exact Line Match",
        "line": "GMSU",
        "equip_size": "40DH",
        "description": "Tests exact match in autocomplete"
    },
    {
        "name": "Line Not Found - Fallback",
        "line": "UNKNOWN_LINE",
        "equip_size": "40DH", 
        "description": "Tests fallback when line not found"
    },
    {
        "name": "Different Line",
        "line": "MSC",
        "equip_size": "40DH",
        "description": "Tests with different line name"
    },
    {
        "name": "Partial Line Match",
        "line": "GMS",  # Partial match of GMSU
        "equip_size": "40DH",
        "description": "Tests partial match in autocomplete"
    }
]

def print_separator(title=""):
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    else:
        print(f"{'='*70}")

def test_autocomplete_scenario(scenario):
    """Test a specific autocomplete scenario"""
    
    print_separator(f"TESTING: {scenario['name']}")
    print(f"📋 {scenario['description']}")
    print(f"   Line: {scenario['line']}")
    print(f"   Equip Size: {scenario['equip_size']}")
    print(f"   Container: {TEST_DATA['container_id']}")
    
    # Create test data with scenario values
    test_data = TEST_DATA.copy()
    test_data["line"] = scenario["line"]
    test_data["equip_size"] = scenario["equip_size"]
    
    try:
        print(f"\n🚀 Sending request to {API_BASE_URL}/check_appointments...")
        response = requests.post(
            f"{API_BASE_URL}/check_appointments",
            json=test_data,
            timeout=600  # 10 minutes
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        try:
            result = response.json()
            print(f"\n📄 Response:")
            print(json.dumps(result, indent=2))
            
            if response.status_code == 200 and result.get('success'):
                print_separator("✅ SUCCESS")
                print(f"✅ {scenario['name']} worked successfully!")
                print(f"   Session ID: {result.get('session_id')}")
                print(f"   Current Phase: {result.get('current_phase')}")
                
                # Check if fallback was used (would be in logs)
                if scenario['line'] == "UNKNOWN_LINE":
                    print(f"   🔄 Expected: Line fallback should have been used")
                
                # Display appointment times if available
                if 'available_times' in result:
                    times = result['available_times']
                    print(f"\n📅 Available Appointment Times: {len(times)}")
                    for i, time_slot in enumerate(times[:5], 1):  # Show first 5
                        print(f"   {i}. {time_slot}")
                    if len(times) > 5:
                        print(f"   ... and {len(times) - 5} more")
                
                # Display screenshot URLs if available
                if 'dropdown_screenshot_url' in result:
                    print(f"\n📸 Dropdown Screenshot: {result['dropdown_screenshot_url']}")
                
                # Display debug bundle if available
                if 'debug_bundle_url' in result:
                    print(f"\n📦 Debug Bundle: {result['debug_bundle_url']}")
                    
                return True
            else:
                print_separator("❌ FAILED")
                print(f"❌ {scenario['name']} failed")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                
                if 'message' in result:
                    print(f"   Message: {result['message']}")
                
                # Provide specific guidance based on error
                if result.get('error') and 'line' in result['error'].lower():
                    print(f"\n💡 TIP: Line autocomplete field issue")
                    print(f"   Line value: {scenario['line']}")
                    print(f"   This might be a field detection issue")
                
                if result.get('error') and 'equip_size' in result['error'].lower():
                    print(f"\n💡 TIP: Equip Size autocomplete field issue")
                    print(f"   Equip Size value: {scenario['equip_size']}")
                    print(f"   This might be a field detection issue")
                
                return False
                
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response")
            print(f"Raw response: {response.text[:500]}")
            return False
    
    except requests.exceptions.Timeout:
        print(f"⏱️ Request timed out after 10 minutes")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error - is the server running at {API_BASE_URL}?")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

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
            
            # Test scenarios with session
            print(f"\n📝 Step 2: Testing autocomplete scenarios with session...")
            
            for i, scenario in enumerate(TEST_SCENARIOS, 1):
                print(f"\n--- Scenario {i}/{len(TEST_SCENARIOS)} ---")
                
                # Create test data with session
                test_data = {
                    "session_id": session_id,
                    "container_type": "import",
                    "container_id": "TCLU8784503",
                    "container_number": "TCLU8784503",
                    "trucking_company": "K & R TRANSPORTATION LLC",
                    "terminal": "TraPac LLC - Los Angeles",
                    "move_type": "DROP EMPTY",
                    "line": scenario["line"],
                    "equip_size": scenario["equip_size"],
                    "truck_plate": "ABC123",
                    "own_chassis": True,
                    "manifested_date": "2025-09-08",
                    "last_free_day_date": "2025-09-21",
                    "debug": False
                }
                
                response = requests.post(
                    f"{API_BASE_URL}/check_appointments",
                    json=test_data,
                    timeout=600
                )
                
                print(f"📊 Status Code: {response.status_code}")
                result = response.json()
                
                if response.status_code == 200 and result.get('success'):
                    print(f"✅ {scenario['name']} - SUCCESS")
                else:
                    print(f"❌ {scenario['name']} - FAILED: {result.get('error', 'Unknown error')}")
                
                # Small delay between tests
                time.sleep(2)
            
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run all tests"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║  Autocomplete Fields Test (Line/Equip Size)                     ║
║                                                                   ║
║  This tests the new autocomplete field handling:                ║
║  - Line field: Autocomplete with fallback to any option         ║
║  - Equip Size field: Direct input (no selection needed)         ║
║  - Real container data: TCLU8784503                              ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"🔗 API Base URL: {API_BASE_URL}")
    print(f"👤 Username: {USERNAME}")
    print(f"🔑 Captcha Key: {CAPTCHA_API_KEY[:10]}...")
    print(f"📦 Container: {TEST_DATA['container_id']}")
    print(f"🏢 Terminal: {TEST_DATA['terminal']}")
    print(f"🚛 Trucking: {TEST_DATA['trucking_company']}")
    
    # Choose test mode
    print(f"\n📋 Test Options:")
    print(f"   1. Test individual scenarios (slower, complete flow)")
    print(f"   2. Test all scenarios with existing session (faster)")
    print(f"   3. Test specific scenario")
    
    choice = input(f"\nEnter choice (1-3) [default: 2]: ").strip() or "2"
    
    if choice == "1":
        # Test individual scenarios
        for i, scenario in enumerate(TEST_SCENARIOS, 1):
            print(f"\n{'='*70}")
            print(f"SCENARIO {i}/{len(TEST_SCENARIOS)}")
            print(f"{'='*70}")
            test_autocomplete_scenario(scenario)
            if i < len(TEST_SCENARIOS):
                input(f"\nPress Enter to continue to next scenario...")
                
    elif choice == "2":
        test_with_session()
        
    elif choice == "3":
        # Test specific scenario
        print(f"\nAvailable scenarios:")
        for i, scenario in enumerate(TEST_SCENARIOS, 1):
            print(f"   {i}. {scenario['name']} - {scenario['description']}")
        
        try:
            scenario_choice = int(input(f"\nEnter scenario number (1-{len(TEST_SCENARIOS)}): "))
            if 1 <= scenario_choice <= len(TEST_SCENARIOS):
                test_autocomplete_scenario(TEST_SCENARIOS[scenario_choice - 1])
            else:
                print(f"Invalid choice. Running default test...")
                test_with_session()
        except ValueError:
            print(f"Invalid input. Running default test...")
            test_with_session()
    else:
        print(f"Invalid choice. Running default test...")
        test_with_session()
    
    print_separator("TEST COMPLETE")

if __name__ == "__main__":
    main()
