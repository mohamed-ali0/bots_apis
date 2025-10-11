#!/usr/bin/env python3
"""
Simple test script for /get_booking_number endpoint
Quick and easy testing with minimal setup
"""

import requests
import json

# Configuration
SERVER_URL = "http://37.60.243.201:5010"  # Remote server 2
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"
CONTAINER_ID = "MSCU5165756"  # Test container

def test_booking_number():
    """Test get_booking_number endpoint"""
    print(f"🎯 Testing /get_booking_number endpoint")
    print(f"🌐 Server: {SERVER_URL}")
    print(f"📦 Container: {CONTAINER_ID}")
    
    # Test with credentials
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "container_id": CONTAINER_ID,
        "debug": True
    }
    
    print(f"\n📤 Sending request...")
    try:
        response = requests.post(f"{SERVER_URL}/get_booking_number", json=payload, timeout=120)
        
        print(f"📥 Response received:")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"   📦 Container ID: {data.get('container_id')}")
            print(f"   🎫 Booking Number: {data.get('booking_number', 'Not found')}")
            print(f"   🆔 Session ID: {data.get('session_id')}")
            print(f"   🆕 New session: {data.get('is_new_session')}")
            
            if data.get('debug_bundle_url'):
                print(f"   🐛 Debug bundle: {data.get('debug_bundle_url')}")
            
            return True
        else:
            print(f"\n❌ FAILED!")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_with_session(session_id):
    """Test with existing session"""
    print(f"\n🔄 Testing with existing session: {session_id}")
    
    payload = {
        "session_id": session_id,
        "container_id": CONTAINER_ID,
        "debug": False
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/get_booking_number", json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ SUCCESS with session!")
                print(f"   🎫 Booking Number: {data.get('booking_number', 'Not found')}")
                return True
            else:
                print(f"❌ Failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 GET_BOOKING_NUMBER SIMPLE TEST")
    print(f"{'='*40}")
    
    # Test 1: With credentials
    success = test_booking_number()
    
    if success:
        print(f"\n🎉 Test completed successfully!")
    else:
        print(f"\n❌ Test failed!")
