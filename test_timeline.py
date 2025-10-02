#!/usr/bin/env python3
"""
Test script for get_container_timeline endpoint with Pregate screenshot
"""

import requests
import json
import time

# API Configuration
API_BASE_URL = "http://89.117.63.196:5010"

# Credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "5a0a4a97f8b4c9505d0b719cd92a9dcb"


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

