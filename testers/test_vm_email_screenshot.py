"""
Test script for the vm_email field in check_appointments endpoint.
This demonstrates how the vm_email is displayed in screenshots.
"""

import requests
import json

# API endpoint
BASE_URL = "http://localhost:5000"

# Test credentials (replace with your actual credentials)
TEST_DATA = {
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_captcha_api_key",
    "container_type": "import",
    "container_id": "ABCD1234567",
    "trucking_company": "Your Trucking Company",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "pin_code": "1234",
    "truck_plate": "ABC123",
    "own_chassis": False,
    "vm_email": "vm1@example.com",  # NEW FIELD - displayed in screenshots
    "debug": False  # Set to True to see debug bundle
}

def test_check_appointments_with_vm_email():
    """Test check_appointments endpoint with vm_email field"""
    print("="*70)
    print("🧪 Testing check_appointments with vm_email field")
    print("="*70)
    
    # Make request
    print(f"\n📤 Sending request to {BASE_URL}/check_appointments")
    print(f"   VM Email: {TEST_DATA['vm_email']}")
    print(f"   Container: {TEST_DATA['container_id']}")
    print(f"   Container Type: {TEST_DATA['container_type']}")
    
    response = requests.post(
        f"{BASE_URL}/check_appointments",
        json=TEST_DATA,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n📥 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ Success!")
        print(f"\n📊 Response Data:")
        print(json.dumps(data, indent=2))
        
        # Check for screenshots
        if 'screenshots' in data:
            print(f"\n📸 Screenshots captured: {len(data['screenshots'])}")
            for i, screenshot in enumerate(data['screenshots'], 1):
                print(f"   {i}. {screenshot}")
                print(f"      → Should display: username | timestamp | Container: ABCD1234567 | VM: {TEST_DATA['vm_email']} | emodal")
        
        # Check for appointment session
        if 'appointment_session_id' in data:
            print(f"\n🔑 Appointment Session ID: {data['appointment_session_id']}")
        
    else:
        print("\n❌ Error!")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(response.text)

def test_without_vm_email():
    """Test check_appointments endpoint without vm_email field"""
    print("\n" + "="*70)
    print("🧪 Testing check_appointments WITHOUT vm_email field")
    print("="*70)
    
    # Remove vm_email from test data
    test_data_no_email = TEST_DATA.copy()
    del test_data_no_email['vm_email']
    
    print(f"\n📤 Sending request to {BASE_URL}/check_appointments")
    print(f"   VM Email: (not provided)")
    print(f"   Container: {test_data_no_email['container_id']}")
    
    response = requests.post(
        f"{BASE_URL}/check_appointments",
        json=test_data_no_email,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n📥 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ Success!")
        
        # Check for screenshots
        if 'screenshots' in data:
            print(f"\n📸 Screenshots captured: {len(data['screenshots'])}")
            for i, screenshot in enumerate(data['screenshots'], 1):
                print(f"   {i}. {screenshot}")
                print(f"      → Should display: username | timestamp | Container: ABCD1234567 | emodal")
                print(f"      → (VM email should NOT be displayed)")
    else:
        print("\n❌ Error!")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(response.text)

if __name__ == "__main__":
    print("\n" + "🚀 VM Email Screenshot Test")
    print("=" * 70)
    print("\nThis test demonstrates the new vm_email field functionality:")
    print("  1. URL is replaced with platform name 'emodal'")
    print("  2. Date counters are removed from screenshots")
    print("  3. VM email is displayed in screenshots (if provided)")
    print("\nScreenshot Label Format:")
    print("  {username} | {timestamp} | Container: {container_id} | VM: {vm_email} | emodal")
    print("  (If vm_email not provided: {username} | {timestamp} | Container: {container_id} | emodal)")
    print("=" * 70)
    
    # Run tests
    test_check_appointments_with_vm_email()
    print("\n")
    test_without_vm_email()
    
    print("\n" + "="*70)
    print("✅ Test complete!")
    print("="*70)










