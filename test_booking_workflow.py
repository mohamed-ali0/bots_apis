#!/usr/bin/env python3
"""
Workflow test script for /get_booking_number endpoint
Demonstrates session creation, reuse, and multiple container testing
"""

import requests
import json
import time

# Configuration
SERVER_URL = "http://37.60.243.201:5010"
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test containers
CONTAINERS = [
    "MSCU5165756",
    "TRHU1866154", 
    "MSDU5772413"
]

def create_session():
    """Create a new session"""
    print(f"🔐 Creating session...")
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/get_session", json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                session_id = data.get("session_id")
                print(f"✅ Session created: {session_id}")
                return session_id
            else:
                print(f"❌ Session creation failed: {data.get('error')}")
                return None
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Session creation error: {e}")
        return None

def get_booking_number(session_id, container_id, debug=False):
    """Get booking number for a container"""
    print(f"\n📋 Getting booking number for: {container_id}")
    
    payload = {
        "session_id": session_id,
        "container_id": container_id,
        "debug": debug
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{SERVER_URL}/get_booking_number", json=payload, timeout=60)
        end_time = time.time()
        
        print(f"   ⏱️  Response time: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                booking_number = data.get("booking_number")
                print(f"   ✅ Success!")
                print(f"   🎫 Booking Number: {booking_number if booking_number else 'Not found'}")
                
                if debug and data.get("debug_bundle_url"):
                    print(f"   🐛 Debug bundle: {data.get('debug_bundle_url')}")
                
                return True
            else:
                print(f"   ❌ Failed: {data.get('error')}")
                return False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_workflow():
    """Test the complete workflow"""
    print(f"🎯 GET_BOOKING_NUMBER WORKFLOW TEST")
    print(f"{'='*50}")
    print(f"🌐 Server: {SERVER_URL}")
    print(f"👤 Username: {USERNAME}")
    print(f"📦 Containers: {', '.join(CONTAINERS)}")
    
    # Step 1: Create session
    print(f"\n{'='*30}")
    print(f"STEP 1: Create Session")
    print(f"{'='*30}")
    
    session_id = create_session()
    if not session_id:
        print(f"❌ Cannot proceed without session")
        return False
    
    # Step 2: Test multiple containers
    print(f"\n{'='*30}")
    print(f"STEP 2: Test Multiple Containers")
    print(f"{'='*30}")
    
    success_count = 0
    for i, container_id in enumerate(CONTAINERS, 1):
        print(f"\n--- Container {i}/{len(CONTAINERS)}: {container_id} ---")
        debug_mode = (i == 1)  # Enable debug for first container
        if get_booking_number(session_id, container_id, debug=debug_mode):
            success_count += 1
        time.sleep(1)  # Brief pause between requests
    
    # Step 3: Test session reuse
    print(f"\n{'='*30}")
    print(f"STEP 3: Test Session Reuse")
    print(f"{'='*30}")
    
    print(f"🔄 Reusing same session for another container...")
    if get_booking_number(session_id, CONTAINERS[0], debug=False):
        success_count += 1
    
    # Step 4: Test with credentials (new session)
    print(f"\n{'='*30}")
    print(f"STEP 4: Test with Credentials (New Session)")
    print(f"{'='*30}")
    
    print(f"🔐 Testing with credentials (bypasses session)...")
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "container_id": CONTAINERS[0],
        "debug": True
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/get_booking_number", json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Success with credentials!")
                print(f"   🆔 New session: {data.get('session_id')}")
                print(f"   🎫 Booking Number: {data.get('booking_number', 'Not found')}")
                success_count += 1
            else:
                print(f"❌ Failed: {data.get('error')}")
        else:
            print(f"❌ Request failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 WORKFLOW TEST SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Successful operations: {success_count}")
    print(f"📦 Total containers tested: {len(CONTAINERS) + 1}")  # +1 for reuse test
    print(f"🕐 Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count >= 3:
        print(f"🎉 Overall result: PASSED")
        return True
    else:
        print(f"❌ Overall result: FAILED")
        return False

if __name__ == "__main__":
    try:
        success = test_workflow()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        exit(1)
