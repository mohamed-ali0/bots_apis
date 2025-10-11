#!/usr/bin/env python3
"""
Simple test script for timeline extraction
Quick test to verify full timeline functionality
"""

import requests
import json

# Configuration
API_BASE_URL = "http://37.60.243.201:5010"
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"
TEST_CONTAINER = "MSDU4431979"


def main():
    print("="*80)
    print(" SIMPLE TIMELINE TEST")
    print("="*80)
    print(f"API: {API_BASE_URL}")
    print(f"Container: {TEST_CONTAINER}\n")
    
    # Step 1: Create session
    print("📝 Step 1: Creating session...")
    session_resp = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    session_data = session_resp.json()
    if not session_data.get("success"):
        print(f"❌ Session failed: {session_data.get('error')}")
        return
    
    session_id = session_data["session_id"]
    print(f"✅ Session: {session_id}\n")
    
    # Step 2: Get timeline
    print("📋 Step 2: Getting timeline...")
    timeline_resp = requests.post(
        f"{API_BASE_URL}/get_container_timeline",
        json={
            "session_id": session_id,
            "container_id": TEST_CONTAINER,
            "debug": False
        },
        timeout=300
    )
    
    data = timeline_resp.json()
    
    if not data.get("success"):
        print(f"❌ Failed: {data.get('error')}")
        return
    
    # Display results
    print("\n" + "="*80)
    print("✅ SUCCESS")
    print("="*80)
    print(f"\nContainer: {data.get('container_id')}")
    print(f"Passed Pregate: {data.get('passed_pregate')}")
    print(f"Total Milestones: {data.get('milestone_count')}")
    
    # Display timeline
    print("\n" + "-"*80)
    print("TIMELINE (newest first):")
    print("-"*80)
    
    for idx, m in enumerate(data.get('timeline', []), 1):
        icon = "✅" if m['status'] == 'completed' else "⏳"
        print(f"{idx:2}. {icon} {m['milestone']:<35} | {m['date']:<20} | {m['status']}")
    
    print("-"*80)
    print("\n🎉 Test completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

