#!/usr/bin/env python3
"""
Test script for cleanup endpoint
"""

import requests

API_BASE_URL = "http://89.117.63.196:5010"

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
    test_cleanup()

