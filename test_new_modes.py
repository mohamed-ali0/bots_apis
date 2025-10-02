#!/usr/bin/env python3
"""
Test script for new get_containers work modes
"""

import requests
import json
import time
import sys

# API Configuration
API_BASE_URL = "http://89.117.63.196:5010"  # Remote server

# Credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "5a0a4a97f8b4c9505d0b719cd92a9dcb"


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

