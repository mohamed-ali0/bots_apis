#!/usr/bin/env python3
"""
Test script for new get_containers work modes
"""

import requests
import json
import time
import sys
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


def test_mode_1_all_containers():
    """Mode 1: Get ALL containers with infinite scroll"""
    print("\n" + "="*70)
    print("🔄 Mode 1: Get ALL Containers (Infinite Scroll)")
    print("="*70)
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "keep_browser_alive": False,
        "infinite_scrolling": True,
        "debug": False,  # No screenshots, just Excel
        "return_url": True
    }
    
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📄 Excel URL: {data.get('file_url')}")
            print(f"  📊 Total containers: {data.get('total_containers')}")
            print(f"  🔄 Scroll cycles: {data.get('scroll_cycles')}")
            print(f"  📦 File: {data.get('file_name')}")
            print(f"  💾 Size: {data.get('file_size')} bytes")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"  Error: {response.json().get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_mode_2_target_count():
    """Mode 2: Get specific COUNT of containers"""
    print("\n" + "="*70)
    print("🔢 Mode 2: Get Specific Count")
    print("="*70)
    
    target = 100  # Stop after loading 100 containers
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "keep_browser_alive": False,
        "target_count": target,
        "debug": False,
        "return_url": True
    }
    
    print(f"🎯 Target count: {target}")
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📄 Excel URL: {data.get('file_url')}")
            print(f"  📊 Loaded: {data.get('total_containers')} containers (target: {target})")
            print(f"  🔄 Scroll cycles: {data.get('scroll_cycles')}")
            print(f"  🛑 Stopped: {data.get('stopped_reason')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"  Error: {response.json().get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_mode_3_find_container():
    """Mode 3: Find specific CONTAINER ID"""
    print("\n" + "="*70)
    print("🔍 Mode 3: Find Specific Container")
    print("="*70)
    
    target_id = "MSDU5772413"  # Example container ID
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "keep_browser_alive": False,
        "target_container_id": target_id,
        "debug": False,
        "return_url": True
    }
    
    print(f"🎯 Target container: {target_id}")
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📄 Excel URL: {data.get('file_url')}")
            print(f"  🎯 Found: {data.get('found_target_container', 'Not found')}")
            print(f"  📊 Total containers: {data.get('total_containers')}")
            print(f"  🔄 Scroll cycles: {data.get('scroll_cycles')}")
            print(f"  🛑 Stopped: {data.get('stopped_reason')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"  Error: {response.json().get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_debug_mode():
    """Test with debug mode enabled (includes screenshots)"""
    print("\n" + "="*70)
    print("🐛 Debug Mode: First Page with Screenshots")
    print("="*70)
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_KEY,
        "keep_browser_alive": False,
        "infinite_scrolling": False,
        "debug": True,  # Enable debug mode
        "return_url": True
    }
    
    print("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS in {duration:.1f} seconds")
            print(f"  📄 Excel URL: {data.get('file_url')}")
            print(f"  📦 Debug Bundle: {data.get('debug_bundle_url')}")
            print(f"  📊 Total containers: {data.get('total_containers')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"  Error: {response.json().get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def main():
    choose_server()
    print("\n" + "="*70)
    print("🧪 Testing New get_containers Work Modes")
    print("="*70)
    print(f"🌐 API: {API_BASE_URL}")
    print(f"👤 User: {USERNAME}")
    print("")
    
    print("Choose test to run:")
    print("  1. Mode 1: Get ALL containers (infinite scroll)")
    print("  2. Mode 2: Get specific COUNT (e.g., 100 containers)")
    print("  3. Mode 3: Find specific CONTAINER ID")
    print("  4. Debug mode test (with screenshots)")
    print("  5. Run all tests")
    print("")
    
    choice = input("Enter choice (1-5) [default: 1]: ").strip() or "1"
    
    if choice == "1":
        test_mode_1_all_containers()
    elif choice == "2":
        test_mode_2_target_count()
    elif choice == "3":
        test_mode_3_find_container()
    elif choice == "4":
        test_debug_mode()
    elif choice == "5":
        print("\n🔄 Running all tests...\n")
        test_mode_1_all_containers()
        time.sleep(2)
        test_mode_2_target_count()
        time.sleep(2)
        test_mode_3_find_container()
        time.sleep(2)
        test_debug_mode()
    else:
        print("❌ Invalid choice")
        return 1
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("="*70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

