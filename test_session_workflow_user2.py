#!/usr/bin/env python3
"""
Session-Based Workflow Test Script - User 2 (Gustavoa)
======================================================

Tests the new persistent session management with second user:
1. Create/Get persistent session for Gustavoa
2. Use session for multiple operations
3. Test different get_containers modes
4. Test concurrency with first user
"""

import requests
import json
import time
import os
import sys

# API Configuration
API_HOST = None
API_PORT = None
API_BASE_URL = None

# Credentials - USER 2
USERNAME = "Gustavoa"
PASSWORD = "Julian_1"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Global session ID
SESSION_ID = None


def choose_server():
    """Prompt user to choose between local or remote server"""
    global API_HOST, API_PORT, API_BASE_URL
    
    # Check if running in non-interactive mode
    auto_test = os.environ.get('AUTO_TEST', '0') == '1'
    
    if auto_test or os.environ.get('API_HOST'):
        API_HOST = os.environ.get('API_HOST', '37.60.243.201')
        API_PORT = os.environ.get('API_PORT', '5010')
        API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
        print(f"🌐 Using API server: {API_BASE_URL}")
        return
    
    print("\n" + "=" * 70)
    print("🌐 API Server Selection - User 2 (Gustavoa)")
    print("=" * 70)
    print("Choose which server to connect to:")
    print("")
    print("  1. Local server     (http://localhost:5010)")
    print("  2. Remote server 1  (http://89.117.63.196:5010)")
    print("  3. Remote server 2  (http://37.60.243.201:5010)")
    print("  4. Custom server    (enter IP/hostname)")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3/4) [default: 3]: ").strip()
        
        if not choice:
            choice = "3"
        
        if choice == "1":
            API_HOST = "localhost"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "2":
            API_HOST = "89.117.63.196"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "3":
            API_HOST = "37.60.243.201"
            API_PORT = "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        elif choice == "4":
            API_HOST = input("Enter server IP/hostname: ").strip()
            API_PORT = input("Enter server port [default: 5010]: ").strip() or "5010"
            API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
            print(f"✅ Selected: {API_BASE_URL}")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def test_health():
    """Test health endpoint and show session capacity"""
    print("\n" + "="*70)
    print("💚 Health Check - User 2")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API is healthy")
            print(f"  📊 Status: {data.get('status')}")
            print(f"  🔗 Service: {data.get('service')}")
            print(f"  📈 Session Capacity: {data.get('session_capacity')}")
            print(f"  🔄 Persistent Sessions: {data.get('persistent_sessions')}")
            print(f"  ⏰ Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def create_session():
    """Step 1: Create or get persistent session for User 2"""
    global SESSION_ID
    
    print("\n" + "="*70)
    print("📌 Step 1: Creating/Getting Persistent Session - User 2")
    print("="*70)
    print(f"👤 Username: {USERNAME}")
    print(f"🔑 Password: {'*' * len(PASSWORD)}")
    print(f"🤖 Captcha Key: {CAPTCHA_KEY[:20]}...")
    print("")
    
    try:
        print("🔄 Calling /get_session endpoint...")
        response = requests.post(f"{API_BASE_URL}/get_session", json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_KEY
        })
        
        if response.status_code == 200:
            data = response.json()
            SESSION_ID = data['session_id']
            is_new = data['is_new']
            
            print("\n✅ Session Ready!")
            print(f"  📋 Session ID: {SESSION_ID}")
            print(f"  🆕 Is New: {is_new}")
            print(f"  👤 Username: {data['username']}")
            print(f"  📅 Created At: {data['created_at']}")
            print(f"  ⏰ Expires At: {data['expires_at']} (never - persistent)")
            print(f"  💬 Message: {data['message']}")
            
            if is_new:
                print("\n🎉 New session created successfully!")
            else:
                print("\n🔄 Existing session reused!")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"  Error: {response.json()}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def choose_mode():
    """Step 2: Choose which get_containers mode to test"""
    print("\n" + "="*70)
    print("📦 Step 2: Choose Get Containers Mode - User 2")
    print("="*70)
    print("")
    print("  1. Get ALL containers (infinite scroll)")
    print("  2. Get specific COUNT (e.g., 50, 100, 500)")
    print("  3. Get until CONTAINER ID found")
    print("  4. Run all modes sequentially")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3/4): ").strip()
        
        if choice in ['1', '2', '3', '4']:
            return choice
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def test_mode_all():
    """Mode 1: Get ALL containers with infinite scroll"""
    print("\n" + "="*70)
    print("🔄 Mode 1: Get ALL Containers (Infinite Scroll) - User 2")
    print("="*70)
    print(f"📋 Using Session ID: {SESSION_ID}")
    print("")
    
    payload = {
        "session_id": SESSION_ID,
        "infinite_scrolling": True,
        "debug": False,
        "return_url": True
    }
    
    try:
        print("🔄 Calling /get_containers with session_id...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! (took {elapsed:.1f}s)")
            print(f"  📋 Session ID: {data.get('session_id')}")
            print(f"  🆕 Is New Session: {data.get('is_new_session')}")
            print(f"  📄 File: {data.get('file_name')}")
            print(f"  📊 Total Containers: {data.get('total_containers')}")
            print(f"  🔄 Scroll Cycles: {data.get('scroll_cycles')}")
            print(f"  🔗 Download URL: {data.get('file_url')}")
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"  Error: {response.json()}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def test_mode_count():
    """Mode 2: Get specific COUNT of containers"""
    print("\n" + "="*70)
    print("🔢 Mode 2: Get Specific COUNT - User 2")
    print("="*70)
    print(f"📋 Using Session ID: {SESSION_ID}")
    print("")
    
    count = input("Enter container count (e.g., 50, 100, 500) [default: 100]: ").strip()
    if not count:
        count = "100"
    
    try:
        count = int(count)
    except:
        print("❌ Invalid number, using 100")
        count = 100
    
    payload = {
        "session_id": SESSION_ID,
        "target_count": count,
        "debug": False,
        "return_url": True
    }
    
    try:
        print(f"\n🔄 Getting {count} containers...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! (took {elapsed:.1f}s)")
            print(f"  📋 Session ID: {data.get('session_id')}")
            print(f"  🆕 Is New Session: {data.get('is_new_session')}")
            print(f"  📄 File: {data.get('file_name')}")
            print(f"  📊 Total Containers: {data.get('total_containers')}")
            print(f"  🔗 Download URL: {data.get('file_url')}")
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"  Error: {response.json()}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def test_mode_find():
    """Mode 3: Get until specific CONTAINER ID found"""
    print("\n" + "="*70)
    print("🔍 Mode 3: Get Until Container ID Found - User 2")
    print("="*70)
    print(f"📋 Using Session ID: {SESSION_ID}")
    print("")
    
    container_id = input("Enter container ID (e.g., MSDU5772413): ").strip().upper()
    if not container_id:
        print("❌ Container ID required")
        return False
    
    payload = {
        "session_id": SESSION_ID,
        "target_container_id": container_id,
        "debug": False,
        "return_url": True
    }
    
    try:
        print(f"\n🔄 Searching for container: {container_id}...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! (took {elapsed:.1f}s)")
            print(f"  📋 Session ID: {data.get('session_id')}")
            print(f"  🆕 Is New Session: {data.get('is_new_session')}")
            print(f"  📄 File: {data.get('file_name')}")
            print(f"  📊 Total Containers: {data.get('total_containers')}")
            print(f"  🎯 Found Target: {data.get('found_target_container', False)}")
            print(f"  🔗 Download URL: {data.get('file_url')}")
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            print(f"  Error: {response.json()}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def main():
    """Main test flow for User 2"""
    choose_server()
    
    print("\n" + "="*70)
    print("🧪 Session-Based Workflow Test - User 2 (Gustavoa)")
    print("="*70)
    print("")
    
    # Health check
    if not test_health():
        print("\n❌ Health check failed. Exiting.")
        return 1
    
    # Step 1: Create/Get session
    print("\n⏸️  Press Enter to create/get session for User 2...")
    input()
    
    if not create_session():
        print("\n❌ Session creation failed. Exiting.")
        return 1
    
    # Step 2: Choose mode and test
    print("\n⏸️  Press Enter to choose mode...")
    input()
    
    mode = choose_mode()
    
    if mode == '1':
        test_mode_all()
    elif mode == '2':
        test_mode_count()
    elif mode == '3':
        test_mode_find()
    elif mode == '4':
        print("\n🔄 Running all modes sequentially...\n")
        test_mode_count()  # Start with count (fastest)
        time.sleep(2)
        test_mode_find()
        time.sleep(2)
    
    # Show final health check
    print("\n⏸️  Press Enter for final health check...")
    input()
    test_health()
    
    print("\n" + "="*70)
    print("✅ Test completed for User 2!")
    print(f"📋 Session ID: {SESSION_ID}")
    print(f"👤 Username: {USERNAME}")
    print("💡 You can use this session_id in subsequent requests")
    print("="*70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


