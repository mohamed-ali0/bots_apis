#!/usr/bin/env python3
"""
Test script for get_container_timeline endpoint with Pregate screenshot
"""

import requests
import json
import time
import os

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None

# Credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"


def choose_server():
    """Prompt user to choose between local or remote servers"""
    global API_HOST, API_PORT, API_BASE_URL
    
    # Check if running in non-interactive mode
    auto_test = os.environ.get('AUTO_TEST', '0') == '1'
    
    if auto_test or os.environ.get('API_HOST'):
        # Use environment variables in non-interactive mode
        API_HOST = os.environ.get('API_HOST', '37.60.243.201')
        API_PORT = os.environ.get('API_PORT', '5010')
        API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
        print(f"🌐 Using API server from environment: {API_BASE_URL}")
        return
    
    # Interactive mode - ask user
    print("\n" + "=" * 70)
    print("🌐 API Server Selection")
    print("=" * 70)
    print("Choose which server to connect to:")
    print("")
    print("  1. Local server     (http://localhost:5010)")
    print("  2. Remote server 1  (http://89.117.63.196:5010)")
    print("  3. Remote server 2  (http://37.60.243.201:5010)")
    print("  4. Custom server    (enter IP/hostname)")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3/4) [default: 1]: ").strip()
        
        # Default to local server
        if not choice:
            choice = "1"
        
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


def test_timeline_debug_mode(container_id: str):
    """
    Test timeline endpoint with debug mode (captures Pregate screenshot)
    
    Args:
        container_id: Container ID to search for
    """
    print("\n" + "="*70)
    print(f"📸 Testing Timeline Endpoint - Debug Mode")
    print(f"🔍 Container: {container_id}")
    print("="*70)
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "container_id": container_id,
        "keep_browser_alive": False,
        "debug": True  # Enable Pregate screenshot capture
    }
    
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_container_timeline",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📦 Container ID: {data.get('container_id')}")
            print(f"  🚦 Passed Pregate: {data.get('passed_pregate')}")
            print(f"  🔍 Detection Method: {data.get('detection_method')}")
            
            if data.get('debug_bundle_url'):
                print(f"  📦 Debug Bundle: {data.get('debug_bundle_url')}")
                full_url = f"{API_BASE_URL}{data['debug_bundle_url']}"
                print(f"\n  🌐 Full download URL:")
                print(f"     {full_url}")
            
            if data.get('image_analysis'):
                analysis = data['image_analysis']
                print(f"\n  📊 Image Analysis:")
                print(f"     Brightness: {analysis.get('average_brightness'):.1f}")
                print(f"     Threshold: {analysis.get('threshold')}")
            
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  Error: {error_data.get('error')}")
            except:
                print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_timeline_normal_mode(container_id: str):
    """
    Test timeline endpoint without debug mode (no screenshot)
    
    Args:
        container_id: Container ID to search for
    """
    print("\n" + "="*70)
    print(f"🔍 Testing Timeline Endpoint - Normal Mode")
    print(f"🔍 Container: {container_id}")
    print("="*70)
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "container_id": container_id,
        "keep_browser_alive": False,
        "debug": False  # No screenshot
    }
    
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_container_timeline",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📦 Container ID: {data.get('container_id')}")
            print(f"  🚦 Passed Pregate: {data.get('passed_pregate')}")
            print(f"  🔍 Detection Method: {data.get('detection_method')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  Error: {error_data.get('error')}")
            except:
                print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def main():
    choose_server()
    print("\n" + "="*70)
    print("🧪 Timeline Endpoint Test Suite")
    print("="*70)
    print(f"🌐 API: {API_BASE_URL}")
    print(f"👤 User: {USERNAME}")
    print("")
    
    # Get container ID from user
    container_id = input("Enter container ID to test (or press Enter for 'HMMU9048448'): ").strip().upper()
    if not container_id:
        container_id = "HMMU9048448"
    
    print("\nChoose test mode:")
    print("  1. Debug mode (captures Pregate screenshot)")
    print("  2. Normal mode (no screenshot)")
    print("  3. Both modes")
    print("")
    
    choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or "1"
    
    if choice == "1":
        test_timeline_debug_mode(container_id)
    elif choice == "2":
        test_timeline_normal_mode(container_id)
    elif choice == "3":
        print("\n🔄 Running both tests...\n")
        test_timeline_debug_mode(container_id)
        time.sleep(2)
        test_timeline_normal_mode(container_id)
    else:
        print("❌ Invalid choice")
        return 1
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("="*70)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

