#!/usr/bin/env python3
"""
Test script for appointment endpoints: /check_appointments and /make_appointment
"""

import os
import requests
import json

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None

# Hardcoded Credentials (from test_business_api.py)
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "5a0a4a97f8b4c9505d0b719cd92a9dcb"


def choose_server():
    """Prompt user to choose between local or remote server"""
    global API_HOST, API_PORT, API_BASE_URL
    
    print("\n" + "=" * 70)
    print("🌐 API Server Selection")
    print("=" * 70)
    print("Choose which server to connect to:")
    print("")
    print("  1. Local server    (http://localhost:5010)")
    print("  2. Remote server   (http://89.117.63.196:5010)")
    print("  3. Custom server   (enter IP/hostname)")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3) [default: 1]: ").strip()
        
        # Default to local server
        if not choice:
            choice = "1"
        
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
            print(f"✅ Using remote server: {API_BASE_URL}\n")
            break
        elif choice == "3":
            API_HOST = input("Enter server IP/hostname: ").strip()
            API_PORT = input("Enter server port [default: 5010]: ").strip() or "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Using custom server: {API_BASE_URL}\n")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    return API_BASE_URL

def test_check_appointments():
    """
    Test the /check_appointments endpoint to get available appointment times.
    This goes through all 3 phases but DOES NOT submit.
    """
    print("\n" + "="*70)
    print("🧪 TESTING: /check_appointments")
    print("="*70)
    print("⚠️  This endpoint will NOT submit any appointment")
    print("   It only retrieves available appointment time slots\n")
    
    # Get credentials (hardcoded defaults)
    username = os.getenv('EMODAL_USERNAME', DEFAULT_USERNAME)
    password = os.getenv('EMODAL_PASSWORD', DEFAULT_PASSWORD)
    captcha_api_key = os.getenv('CAPTCHA_API_KEY', DEFAULT_CAPTCHA_KEY)
    
    print(f"✅ Using credentials for user: {username}\n")
    
    # Phase 1 fields
    trucking_company = input("Enter trucking company name [default: TEST TRUCKING]: ").strip() or "TEST TRUCKING"
    terminal = input("Enter terminal [default: ITS Long Beach]: ").strip() or "ITS Long Beach"
    move_type = input("Enter move type [default: DROP EMPTY]: ").strip() or "DROP EMPTY"
    container_id = input("Enter container ID [default: CAIU7181746]: ").strip() or "CAIU7181746"
    
    # Phase 2 fields
    truck_plate = input("Enter truck plate [default: ABC123]: ").strip() or "ABC123"
    pin_code = input("Enter PIN code (optional, press Enter to skip): ").strip() or None
    own_chassis_input = input("Own chassis? (yes/no) [default: no]: ").strip().lower()
    own_chassis = own_chassis_input in ['yes', 'y', 'true', '1']
    
    # Prepare request
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_api_key,
        "trucking_company": trucking_company,
        "terminal": terminal,
        "move_type": move_type,
        "container_id": container_id,
        "truck_plate": truck_plate,
        "own_chassis": own_chassis
    }
    
    if pin_code:
        payload["pin_code"] = pin_code
    
    print("\n📤 Sending request to /check_appointments...")
    print(f"   Trucking: {trucking_company}")
    print(f"   Terminal: {terminal}")
    print(f"   Move Type: {move_type}")
    print(f"   Container: {container_id}")
    print(f"   Truck Plate: {truck_plate}")
    print(f"   PIN Code: {'Yes' if pin_code else 'No'}")
    print(f"   Own Chassis: {'Yes' if own_chassis else 'No'}")
    print("\n⏳ This may take 2-3 minutes...\n")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/check_appointments",
            json=payload,
            timeout=600  # 10 minutes
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS!")
            print(f"   Available Times: {result.get('count', 0)}")
            print("\n📅 Available Appointment Times:")
            for i, time_slot in enumerate(result.get('available_times', []), 1):
                print(f"   {i}. {time_slot}")
            
            if result.get('debug_bundle_url'):
                print(f"\n📦 Debug Bundle: {API_BASE_URL}{result['debug_bundle_url']}")
            
            return result
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")


def test_make_appointment():
    """
    Test the /make_appointment endpoint to actually submit an appointment.
    ⚠️ WARNING: This WILL submit the appointment!
    """
    print("\n" + "="*70)
    print("🧪 TESTING: /make_appointment")
    print("="*70)
    print("⚠️  ⚠️  ⚠️  WARNING  ⚠️  ⚠️  ⚠️")
    print("   This endpoint WILL ACTUALLY SUBMIT the appointment!")
    print("   Only use this if you want to make a real appointment!")
    print("="*70)
    
    confirm = input("\nType 'YES I WANT TO SUBMIT' to continue: ").strip()
    if confirm != "YES I WANT TO SUBMIT":
        print("❌ Test cancelled")
        return
    
    # Get credentials (hardcoded defaults)
    username = os.getenv('EMODAL_USERNAME', DEFAULT_USERNAME)
    password = os.getenv('EMODAL_PASSWORD', DEFAULT_PASSWORD)
    captcha_api_key = os.getenv('CAPTCHA_API_KEY', DEFAULT_CAPTCHA_KEY)
    
    print(f"✅ Using credentials for user: {username}\n")
    
    # Phase 1 fields
    trucking_company = input("Enter trucking company name: ").strip()
    terminal = input("Enter terminal: ").strip()
    move_type = input("Enter move type: ").strip()
    container_id = input("Enter container ID: ").strip()
    
    # Phase 2 fields
    truck_plate = input("Enter truck plate: ").strip()
    pin_code = input("Enter PIN code (optional, press Enter to skip): ").strip() or None
    own_chassis_input = input("Own chassis? (yes/no): ").strip().lower()
    own_chassis = own_chassis_input in ['yes', 'y', 'true', '1']
    
    # Phase 3 field
    appointment_time = input("Enter appointment time (exact text from available times): ").strip()
    
    # Validate all required fields
    if not all([trucking_company, terminal, move_type, container_id, truck_plate, appointment_time]):
        print("❌ Missing required fields!")
        return
    
    # Prepare request
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": captcha_api_key,
        "trucking_company": trucking_company,
        "terminal": terminal,
        "move_type": move_type,
        "container_id": container_id,
        "truck_plate": truck_plate,
        "own_chassis": own_chassis,
        "appointment_time": appointment_time
    }
    
    if pin_code:
        payload["pin_code"] = pin_code
    
    print("\n📤 Sending request to /make_appointment...")
    print(f"   Trucking: {trucking_company}")
    print(f"   Terminal: {terminal}")
    print(f"   Move Type: {move_type}")
    print(f"   Container: {container_id}")
    print(f"   Truck Plate: {truck_plate}")
    print(f"   PIN Code: {'Yes' if pin_code else 'No'}")
    print(f"   Own Chassis: {'Yes' if own_chassis else 'No'}")
    print(f"   Appointment Time: {appointment_time}")
    print("\n⏳ This may take 3-4 minutes...\n")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/make_appointment",
            json=payload,
            timeout=600  # 10 minutes
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ APPOINTMENT SUBMITTED SUCCESSFULLY!")
            print("\n📋 Appointment Details:")
            details = result.get('appointment_details', {})
            for key, value in details.items():
                print(f"   {key}: {value}")
            
            if result.get('debug_bundle_url'):
                print(f"\n📦 Debug Bundle: {API_BASE_URL}{result['debug_bundle_url']}")
            
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
    print("  E-MODAL APPOINTMENT TESTING")
    print("="*70)
    print("\nSelect test to run:")
    print("  1. Check Available Appointments (does NOT submit)")
    print("  2. Make Appointment (WILL SUBMIT)")
    print("  3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        test_check_appointments()
    elif choice == "2":
        test_make_appointment()
    elif choice == "3":
        print("👋 Goodbye!")
        return
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()

