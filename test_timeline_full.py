#!/usr/bin/env python3
"""
Test script for /get_container_timeline endpoint with full timeline extraction
Tests both working mode (timeline data only) and debug mode (timeline + screenshots)
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://37.60.243.201:5010"  # Remote server 2 (default)
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test container IDs
TEST_CONTAINERS = {
    "import_active": "MSCU5165756",    # Known import container with timeline
    "import_other": "TRHU1866154",     # Another import container
}


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_result(data: Dict[str, Any]):
    """Pretty print JSON result"""
    print(json.dumps(data, indent=2))


def print_timeline(timeline: list):
    """Print timeline in a formatted table"""
    print("\n" + "-" * 80)
    print(f"{'#':<4} {'Milestone':<35} {'Date':<20} {'Status':<10}")
    print("-" * 80)
    for idx, milestone in enumerate(timeline, 1):
        status_icon = "✅" if milestone['status'] == 'completed' else "⏳"
        print(f"{idx:<4} {milestone['milestone']:<35} {milestone['date']:<20} {status_icon} {milestone['status']}")
    print("-" * 80)


def test_timeline_working_mode():
    """Test timeline extraction in working mode (no debug)"""
    
    print_section("TEST 1: Timeline Extraction - Working Mode")
    print(f"API: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    print(f"Container: {TEST_CONTAINERS['import_active']}")
    
    # Step 1: Create session
    print_section("Step 1: Creating Session")
    session_response = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    if not session_response.ok:
        print(f"❌ Session creation failed: {session_response.status_code}")
        print_result(session_response.json())
        return False
    
    session_data = session_response.json()
    if not session_data.get("success"):
        print(f"❌ Session creation failed")
        print_result(session_data)
        return False
    
    session_id = session_data.get("session_id")
    print(f"✅ Session created: {session_id}")
    
    # Step 2: Get timeline (working mode)
    print_section("Step 2: Getting Timeline (Working Mode)")
    print(f"Container ID: {TEST_CONTAINERS['import_active']}")
    print("Debug mode: FALSE (working mode)")
    
    print("\n⏳ Fetching timeline... (this may take 30-60 seconds)")
    
    start_time = time.time()
    
    try:
        timeline_response = requests.post(
            f"{API_BASE_URL}/get_container_timeline",
            json={
                "session_id": session_id,
                "container_id": TEST_CONTAINERS['import_active'],
                "debug": False  # Working mode
            },
            timeout=300
        )
        
        elapsed = time.time() - start_time
        
        if not timeline_response.ok:
            print(f"\n❌ Request failed: {timeline_response.status_code}")
            print_result(timeline_response.json())
            return False
        
        timeline_data = timeline_response.json()
        
        print("\n" + "=" * 80)
        if timeline_data.get("success"):
            print("✅ TIMELINE EXTRACTION SUCCESS")
            print("=" * 80)
            
            # Display key results
            print(f"\nContainer ID: {timeline_data.get('container_id', 'N/A')}")
            print(f"Passed Pregate: {timeline_data.get('passed_pregate', False)}")
            print(f"Detection Method: {timeline_data.get('detection_method', 'N/A')}")
            print(f"Milestone Count: {timeline_data.get('milestone_count', 0)}")
            print(f"Execution Time: {elapsed:.2f} seconds")
            
            # Display timeline
            if 'timeline' in timeline_data and timeline_data['timeline']:
                print_timeline(timeline_data['timeline'])
            else:
                print("\n⚠️ No timeline data returned")
            
            # Verify no debug bundle in working mode
            if 'debug_bundle_url' in timeline_data:
                print(f"\n⚠️ WARNING: debug_bundle_url present in working mode!")
                print(f"Debug Bundle: {timeline_data['debug_bundle_url']}")
            else:
                print(f"\n✅ Confirmed: No debug bundle in working mode (as expected)")
            
            return True
        else:
            print("❌ TIMELINE EXTRACTION FAILED")
            print("=" * 80)
            print(f"\nError: {timeline_data.get('error', 'Unknown error')}")
            print("\nFull Response:")
            print_result(timeline_data)
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_timeline_debug_mode():
    """Test timeline extraction in debug mode (with screenshots)"""
    
    print_section("TEST 2: Timeline Extraction - Debug Mode")
    print(f"API: {API_BASE_URL}")
    print(f"Container: {TEST_CONTAINERS['import_other']}")
    
    # Step 1: Create session (reuse from previous test or create new)
    print_section("Step 1: Creating Session")
    session_response = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    if not session_response.ok:
        print(f"❌ Session creation failed: {session_response.status_code}")
        return False
    
    session_data = session_response.json()
    if not session_data.get("success"):
        print(f"❌ Session creation failed")
        return False
    
    session_id = session_data.get("session_id")
    print(f"✅ Session created: {session_id}")
    
    # Step 2: Get timeline (debug mode)
    print_section("Step 2: Getting Timeline (Debug Mode)")
    print(f"Container ID: {TEST_CONTAINERS['import_other']}")
    print("Debug mode: TRUE (debug mode)")
    
    print("\n⏳ Fetching timeline with debug data... (this may take 30-60 seconds)")
    
    start_time = time.time()
    
    try:
        timeline_response = requests.post(
            f"{API_BASE_URL}/get_container_timeline",
            json={
                "session_id": session_id,
                "container_id": TEST_CONTAINERS['import_other'],
                "debug": True  # Debug mode
            },
            timeout=300
        )
        
        elapsed = time.time() - start_time
        
        if not timeline_response.ok:
            print(f"\n❌ Request failed: {timeline_response.status_code}")
            return False
        
        timeline_data = timeline_response.json()
        
        print("\n" + "=" * 80)
        if timeline_data.get("success"):
            print("✅ TIMELINE EXTRACTION SUCCESS (DEBUG MODE)")
            print("=" * 80)
            
            # Display key results
            print(f"\nContainer ID: {timeline_data.get('container_id', 'N/A')}")
            print(f"Passed Pregate: {timeline_data.get('passed_pregate', False)}")
            print(f"Detection Method: {timeline_data.get('detection_method', 'N/A')}")
            print(f"Milestone Count: {timeline_data.get('milestone_count', 0)}")
            print(f"Execution Time: {elapsed:.2f} seconds")
            
            # Display timeline
            if 'timeline' in timeline_data and timeline_data['timeline']:
                print_timeline(timeline_data['timeline'])
            else:
                print("\n⚠️ No timeline data returned")
            
            # Verify debug bundle is present
            if 'debug_bundle_url' in timeline_data:
                print(f"\n✅ Debug Bundle Created")
                print(f"📦 Bundle URL: {timeline_data['debug_bundle_url']}")
            else:
                print(f"\n⚠️ WARNING: debug_bundle_url NOT present in debug mode!")
            
            return True
        else:
            print("❌ TIMELINE EXTRACTION FAILED")
            print("=" * 80)
            print(f"\nError: {timeline_data.get('error', 'Unknown error')}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_timeline_analysis():
    """Test timeline to show specific use cases"""
    
    print_section("TEST 3: Timeline Analysis Examples")
    print("This test demonstrates how to use timeline data")
    
    # Create session
    session_response = requests.post(
        f"{API_BASE_URL}/get_session",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "captcha_api_key": CAPTCHA_API_KEY
        },
        timeout=300
    )
    
    if not session_response.ok:
        print("❌ Session creation failed")
        return False
    
    session_data = session_response.json()
    session_id = session_data.get("session_id")
    print(f"✅ Session: {session_id}")
    
    # Get timeline
    timeline_response = requests.post(
        f"{API_BASE_URL}/get_container_timeline",
        json={
            "session_id": session_id,
            "container_id": TEST_CONTAINERS['import_active'],
            "debug": False
        },
        timeout=300
    )
    
    if not timeline_response.ok:
        print("❌ Timeline request failed")
        return False
    
    timeline_data = timeline_response.json()
    
    if not timeline_data.get("success"):
        print("❌ Timeline extraction failed")
        return False
    
    timeline = timeline_data.get('timeline', [])
    
    # Analysis 1: Count completed vs pending
    print_section("Analysis 1: Milestone Status Summary")
    completed = [m for m in timeline if m['status'] == 'completed']
    pending = [m for m in timeline if m['status'] == 'pending']
    print(f"✅ Completed milestones: {len(completed)}")
    print(f"⏳ Pending milestones: {len(pending)}")
    
    # Analysis 2: Find specific milestones
    print_section("Analysis 2: Key Milestones")
    key_milestones = ['Pregate', 'Discharged', 'Last Free Day', 'Departed Terminal']
    for key in key_milestones:
        milestone = next((m for m in timeline if key.lower() in m['milestone'].lower()), None)
        if milestone:
            status_icon = "✅" if milestone['status'] == 'completed' else "⏳"
            print(f"{status_icon} {milestone['milestone']}: {milestone['date']} ({milestone['status']})")
        else:
            print(f"❓ {key}: Not found in timeline")
    
    # Analysis 3: Check if ready for pickup
    print_section("Analysis 3: Ready for Pickup?")
    pregate_done = timeline_data.get('passed_pregate', False)
    ready_milestone = next((m for m in timeline if 'ready' in m['milestone'].lower() and 'pick' in m['milestone'].lower()), None)
    
    if pregate_done:
        print("✅ Container has passed Pregate")
        if ready_milestone and ready_milestone['status'] == 'completed':
            print("✅ Container is marked as 'Ready for pick up'")
            print("🎉 Container is READY FOR PICKUP!")
        else:
            print("⏳ Waiting for 'Ready for pick up' status")
    else:
        print("⏳ Container has NOT passed Pregate yet")
    
    # Analysis 4: Most recent completed milestone
    print_section("Analysis 4: Most Recent Activity")
    completed_with_dates = [m for m in timeline if m['status'] == 'completed' and m['date'] != 'N/A']
    if completed_with_dates:
        latest = completed_with_dates[0]  # Already in reverse chronological order
        print(f"📅 Latest activity: {latest['milestone']}")
        print(f"   Date: {latest['date']}")
    else:
        print("❓ No dated milestones found")
    
    return True


def main():
    """Run all tests"""
    print_section("FULL TIMELINE EXTRACTION - TEST SUITE")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    print(f"Test Containers: {', '.join(TEST_CONTAINERS.values())}")
    
    results = []
    
    # Test 1: Working Mode
    test1_result = test_timeline_working_mode()
    results.append(("Working Mode", test1_result))
    
    if test1_result:
        time.sleep(2)  # Brief pause between tests
    
    # Test 2: Debug Mode
    test2_result = test_timeline_debug_mode()
    results.append(("Debug Mode", test2_result))
    
    if test2_result:
        time.sleep(2)
    
    # Test 3: Analysis
    test3_result = test_timeline_analysis()
    results.append(("Timeline Analysis", test3_result))
    
    # Summary
    print_section("TEST SUMMARY")
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ SOME TESTS FAILED")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

