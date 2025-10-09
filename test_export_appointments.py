#!/usr/bin/env python3
"""
Test script for Export Container Appointment Flow
Tests the /check_appointments endpoint with container_type='export'
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://37.60.243.201:5010"  # Change to remote server if needed
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Export container test data
TEST_EXPORT_DATA = {
    "trucking_company": "K & R TRANSPORTATION LLC",
    "terminal": "Everport Terminal Services - Los Angeles",
    "move_type": "DROP FULL",
    "booking_number": "510476551",  # Booking number instead of container ID
    "truck_plate": "ABC123",  # Wildcard to select any available plate
    "own_chassis": True,
    "unit_number": "1",  # Will be filled automatically
    "seal_value": "1"    # Will be filled automatically
}


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_result(data: Dict[str, Any]):
    """Pretty print JSON result"""
    print(json.dumps(data, indent=2))


def test_export_appointment():
    """Test export container appointment flow"""
    
    print_section("EXPORT CONTAINER APPOINTMENT TEST")
    print(f"API: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    print(f"Booking Number: {TEST_EXPORT_DATA['booking_number']}")
    
    # Step 1: Create session
    print_section("Step 1: Creating Session")
    session_response = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    if not session_response.ok:
        print(f"❌ Session creation failed: {session_response.status_code}")
        print_result(session_response.json())
        return False
    
    session_data = session_response.json()
    if not session_data.get("success"):
        print(f"❌ Session creation failed")
        print_result(session_data)
        return False
    
    session_id = session_data.get("session_id")
    print(f"✅ Session created: {session_id}")
    
    # Step 2: Check export appointments
    print_section("Step 2: Checking Export Appointments")
    print("This will go through all 3 phases:")
    print("  Phase 1: Company, Terminal, Move Type, Booking Number, Quantity")
    print("  Phase 2: Checkbox, Unit Number, Seal Fields, Truck Plate, Chassis")
    print("  Phase 3: Find Calendar Icon")
    
    request_data = {
        "container_type": "export",  # IMPORTANT: Set to 'export'
        "session_id": session_id,
        **TEST_EXPORT_DATA
    }
    
    print("\nRequest:")
    print_result(request_data)
    
    print("\n⏳ Processing... (this may take 1-2 minutes)")
    
    try:
        appt_response = requests.post(
            f"{API_BASE_URL}/check_appointments",
            json=request_data,
            timeout=600  # 10 minutes
        )
        
        if not appt_response.ok:
            print(f"\n❌ Request failed: {appt_response.status_code}")
            print_result(appt_response.json())
            return False
        
        appt_data = appt_response.json()
        
        print("\n" + "=" * 80)
        if appt_data.get("success"):
            print("✅ EXPORT APPOINTMENT CHECK SUCCESS")
            print("=" * 80)
            
            # Display key results
            print(f"\nContainer Type: {appt_data.get('container_type', 'N/A')}")
            print(f"Calendar Found: {appt_data.get('calendar_found', False)}")
            print(f"Session ID: {appt_data.get('session_id', 'N/A')}")
            print(f"Is New Session: {appt_data.get('is_new_session', False)}")
            
            # Phase data
            if 'phase_data' in appt_data:
                print("\nPhase Data:")
                print_result(appt_data['phase_data'])
            
            # Debug bundle
            if 'debug_bundle_url' in appt_data:
                print(f"\n📦 Debug Bundle: {appt_data['debug_bundle_url']}")
            
            return True
        else:
            print("❌ EXPORT APPOINTMENT CHECK FAILED")
            print("=" * 80)
            print(f"\nError: {appt_data.get('error', 'Unknown error')}")
            print(f"Current Phase: {appt_data.get('current_phase', 'Unknown')}")
            
            if 'message' in appt_data:
                print(f"Message: {appt_data['message']}")
            
            print("\nFull Response:")
            print_result(appt_data)
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out (10 minutes)")
        return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_import_for_comparison():
    """Test import container for comparison (optional)"""
    
    print_section("IMPORT CONTAINER APPOINTMENT TEST (For Comparison)")
    print(f"API: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    print(f"Container ID: MSCU5165756")
    
    # Create session
    print("\n⏳ Creating session...")
    session_response = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    if not session_response.ok:
        print(f"❌ Session creation failed")
        return False
    
    session_data = session_response.json()
    session_id = session_data.get("session_id")
    print(f"✅ Session created: {session_id}")
    
    # Check import appointments
    print("\n⏳ Checking import appointments...")
    request_data = {
        "container_type": "import",  # Set to 'import'
        "session_id": session_id,
        "trucking_company": "LONGSHIP FREIGHT LLC",
        "terminal": "ITS Long Beach",
        "move_type": "DROP EMPTY",
        "container_id": "MSCU5165756",
        "truck_plate": "ABC123",
        "own_chassis": True
    }
    
    try:
        appt_response = requests.post(
            f"{API_BASE_URL}/check_appointments",
            json=request_data,
            timeout=600
        )
        
        appt_data = appt_response.json()
        
        if appt_data.get("success"):
            print("\n✅ IMPORT APPOINTMENT CHECK SUCCESS")
            print(f"Available Times: {appt_data.get('count', 0)}")
            if appt_data.get('available_times'):
                print("First 5 times:")
                for time_slot in appt_data['available_times'][:5]:
                    print(f"  - {time_slot}")
            return True
        else:
            print(f"\n❌ IMPORT APPOINTMENT CHECK FAILED: {appt_data.get('error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def main():
    """Main test runner"""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║           E-MODAL EXPORT APPOINTMENT FLOW TEST                           ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("This test will:")
    print("  1. Create a persistent browser session")
    print("  2. Test export container appointment flow")
    print("  3. Optionally test import container for comparison")
    print()
    
    # Test export flow
    export_success = test_export_appointment()
    
    # Ask if user wants to test import for comparison
    if export_success:
        print("\n" + "=" * 80)
        response = input("Test import flow for comparison? (y/n): ").strip().lower()
        if response == 'y':
            test_import_for_comparison()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()

