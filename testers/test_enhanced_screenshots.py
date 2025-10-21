#!/usr/bin/env python3
"""
Test Enhanced Screenshots for check_appointments
================================================

Tests the new screenshot functionality with:
- Full browser window capture (including URL bar)
- VM email in screenshot labels
- Hardcoded "emodal" platform name
- Date counters removed
- Container: KOCU9019106 (IMPORT)
"""

import requests
import json
import time
from datetime import datetime

# Server configuration
SERVER_URL = "http://37.60.243.201:5010"

# Test credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "2captcha_api_key_here"  # Replace with actual 2captcha API key

# Container data from the provided information
CONTAINER_DATA = {
    "container_id": "KOCU9019106",
    "line": "HDMU",
    "equip_size": "45DH",
    "manifested_date": "09/22/2025",
    "departed_date": "10/02/2025",
    "last_free_day_date": "10/03/2025"
}

def test_enhanced_screenshots():
    """Test the enhanced screenshot functionality"""
    
    print("🧪 Testing Enhanced Screenshots for check_appointments")
    print("=" * 60)
    
    # Test data for check_appointments endpoint
    test_data = {
        "container_type": "import",
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY,
        "vm_email": "test@example.com",  # VM email for screenshot labels
        
        # Phase 1 fields
        "trucking_company": "K & R TRANSPORTATION LLC",
        "terminal": "TraPac LLC - Los Angeles",
        "move_type": "DROP EMPTY",
        
        # Container information
        "container_id": CONTAINER_DATA["container_id"],
        "line": CONTAINER_DATA["line"],
        "equip_size": CONTAINER_DATA["equip_size"],
        
        # Date fields for import containers
        "manifested_date": CONTAINER_DATA["manifested_date"],
        "departed_date": CONTAINER_DATA["departed_date"],
        "last_free_day_date": CONTAINER_DATA["last_free_day_date"],
        
        # Screenshot settings
        "capture_screens": True,
        "screens_label": "Enhanced Screenshot Test"
    }
    
    print(f"📦 Testing Container: {CONTAINER_DATA['container_id']}")
    print(f"📧 VM Email: {test_data['vm_email']}")
    print(f"🏢 Terminal: {test_data['terminal']}")
    print(f"🚛 Trucking: {test_data['trucking_company']}")
    print(f"📅 Manifested: {CONTAINER_DATA['manifested_date']}")
    print(f"📅 Departed: {CONTAINER_DATA['departed_date']}")
    print(f"📅 Last Free Day: {CONTAINER_DATA['last_free_day_date']}")
    print()
    
    try:
        print("🚀 Sending request to check_appointments endpoint...")
        start_time = time.time()
        
        response = requests.post(
            f"{SERVER_URL}/check_appointments",
            json=test_data,
            timeout=300  # 5 minutes timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️ Request completed in {duration:.2f} seconds")
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Request successful!")
            print()
            
            # Display response details
            print("📋 Response Details:")
            print(f"  Success: {result.get('success', 'N/A')}")
            print(f"  Current Phase: {result.get('current_phase', 'N/A')}")
            print(f"  Appointment Session ID: {result.get('appointment_session_id', 'N/A')}")
            print(f"  Browser Session ID: {result.get('browser_session_id', 'N/A')}")
            print(f"  Is New Session: {result.get('is_new_session', 'N/A')}")
            print()
            
            # Display screenshots
            screenshots = result.get('screenshots', [])
            if screenshots:
                print("📸 Screenshots Captured:")
                for i, screenshot in enumerate(screenshots, 1):
                    print(f"  {i}. {screenshot}")
            else:
                print("⚠️ No screenshots captured")
            print()
            
            # Display appointment data if available
            appointment_data = result.get('appointment_data', {})
            if appointment_data:
                print("📅 Appointment Data:")
                for key, value in appointment_data.items():
                    print(f"  {key}: {value}")
            else:
                print("ℹ️ No appointment data available")
            print()
            
            # Display any errors
            if 'error' in result:
                print(f"⚠️ Error: {result['error']}")
            
            # Display debug info if available
            if 'debug_info' in result:
                print("🔍 Debug Info:")
                debug_info = result['debug_info']
                for key, value in debug_info.items():
                    print(f"  {key}: {value}")
            
        else:
            print(f"❌ Request failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response: {response.text}")
                
    except requests.exceptions.Timeout:
        print("⏰ Request timed out after 5 minutes")
    except requests.exceptions.ConnectionError:
        print("🔌 Connection error - server may be down")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")

def test_screenshot_labels():
    """Test different VM email formats for screenshot labels"""
    
    print("\n🧪 Testing Different VM Email Formats")
    print("=" * 40)
    
    test_emails = [
        "user@example.com",
        "test.user@domain.org", 
        "vm123@server.net",
        "admin@company.com"
    ]
    
    for email in test_emails:
        print(f"\n📧 Testing with VM Email: {email}")
        
        test_data = {
            "container_type": "import",
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY,
            "vm_email": email,
            "trucking_company": "K & R TRANSPORTATION LLC",
            "terminal": "TraPac LLC - Los Angeles",
            "move_type": "DROP EMPTY",
            "container_id": CONTAINER_DATA["container_id"],
            "line": CONTAINER_DATA["line"],
            "equip_size": CONTAINER_DATA["equip_size"],
            "manifested_date": CONTAINER_DATA["manifested_date"],
            "departed_date": CONTAINER_DATA["departed_date"],
            "last_free_day_date": CONTAINER_DATA["last_free_day_date"],
            "capture_screens": True,
            "screens_label": f"VM Email Test: {email}"
        }
        
        try:
            print("  🚀 Sending request...")
            response = requests.post(
                f"{SERVER_URL}/check_appointments",
                json=test_data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                screenshots = result.get('screenshots', [])
                print(f"  ✅ Success - {len(screenshots)} screenshots captured")
                for screenshot in screenshots:
                    print(f"    📸 {screenshot}")
            else:
                print(f"  ❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"  💥 Error: {e}")

def test_without_vm_email():
    """Test without VM email to see default behavior"""
    
    print("\n🧪 Testing Without VM Email")
    print("=" * 30)
    
    test_data = {
        "container_type": "import",
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY,
        # No vm_email field
        "trucking_company": "K & R TRANSPORTATION LLC",
        "terminal": "TraPac LLC - Los Angeles",
        "move_type": "DROP EMPTY",
        "container_id": CONTAINER_DATA["container_id"],
        "line": CONTAINER_DATA["line"],
        "equip_size": CONTAINER_DATA["equip_size"],
        "manifested_date": CONTAINER_DATA["manifested_date"],
        "departed_date": CONTAINER_DATA["departed_date"],
        "last_free_day_date": CONTAINER_DATA["last_free_day_date"],
        "capture_screens": True,
        "screens_label": "No VM Email Test"
    }
    
    try:
        print("🚀 Sending request without VM email...")
        response = requests.post(
            f"{SERVER_URL}/check_appointments",
            json=test_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            screenshots = result.get('screenshots', [])
            print(f"✅ Success - {len(screenshots)} screenshots captured")
            for screenshot in screenshots:
                print(f"📸 {screenshot}")
        else:
            print(f"❌ Failed with status {response.status_code}")
            
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    print("🧪 Enhanced Screenshots Test Suite")
    print("=" * 50)
    print(f"🌐 Server: {SERVER_URL}")
    print(f"👤 Username: {USERNAME}")
    print(f"📦 Container: {CONTAINER_DATA['container_id']}")
    print()
    
    # Test 1: Main enhanced screenshots test
    test_enhanced_screenshots()
    
    # Test 2: Different VM email formats
    test_screenshot_labels()
    
    # Test 3: Without VM email
    test_without_vm_email()
    
    print("\n🏁 Test suite completed!")
    print("\n📋 Expected Screenshot Label Format:")
    print("  username | timestamp | Container: KOCU9019106 | Email: test@example.com | emodal")
    print("\n📋 Expected Features:")
    print("  ✅ Full browser window (including URL bar)")
    print("  ✅ VM email in labels")
    print("  ✅ Hardcoded 'emodal' platform name")
    print("  ✅ No date counters")
    print("  ✅ Container number in labels")
