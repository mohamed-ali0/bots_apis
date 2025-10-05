#!/usr/bin/env python3
"""
Test script for cleanup endpoint
"""

import requests
import os

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None


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

def test_cleanup():
    """Test manual cleanup endpoint"""
    print("\n🗑️ Testing Manual Cleanup Endpoint")
    print("=" * 60)
    
    try:
        response = requests.post(f"{API_BASE_URL}/cleanup", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Cleanup successful!")
            print(f"  📊 Current storage: {data.get('current_storage_mb')} MB")
            print(f"  📂 Downloads: {data.get('downloads_mb')} MB")
            print(f"  📸 Screenshots: {data.get('screenshots_mb')} MB")
            return True
        else:
            print(f"❌ Cleanup failed: {response.status_code}")
            print(f"  Error: {response.json().get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    choose_server()
    test_cleanup()

