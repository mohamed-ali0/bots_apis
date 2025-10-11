#!/usr/bin/env python3
"""
Test script for /get_info_bulk endpoint
Tests bulk processing of import and export containers
"""

import requests
import json
import time

# Configuration
# API_BASE_URL = "http://localhost:5010"  # Local server
API_BASE_URL = "http://37.60.243.201:5010"  # Remote server (default)

# Test credentials
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test containers - Real container IDs from your E-Modal account
IMPORT_CONTAINERS = [
    "MSDU8716455",  # IMPORT container
    "TCLU8784503",  # IMPORT container
    "MEDU7724823",  # IMPORT container
]

EXPORT_CONTAINERS = [
    "TRHU1866154",  # EXPORT container
    "YMMU1089936",  # EXPORT container
    "EISU1654618",  # EXPORT container
]

def print_separator(title=""):
    """Print a formatted separator"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    else:
        print(f"{'='*70}\n")


def test_bulk_with_session_creation():
    """Test bulk processing with new session creation"""
    print_separator("TEST 1: Bulk Processing with New Session")
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY,
        "import_containers": IMPORT_CONTAINERS,
        "export_containers": EXPORT_CONTAINERS,
        "debug": False
    }
    
    print(f"📦 Sending request to {API_BASE_URL}/get_info_bulk")
    print(f"   Import containers: {len(IMPORT_CONTAINERS)}")
    print(f"   Export containers: {len(EXPORT_CONTAINERS)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_info_bulk",
            json=payload,
            timeout=600  # 10 minutes timeout for bulk processing
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n⏱️  Response time: {elapsed_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   New session: {data.get('is_new_session')}")
            print(f"   Message: {data.get('message')}")
            
            # Print summary
            summary = data.get('results', {}).get('summary', {})
            print(f"\n📊 SUMMARY:")
            print(f"   Import: {summary.get('import_success')}/{summary.get('total_import')} successful")
            print(f"   Export: {summary.get('export_success')}/{summary.get('total_export')} successful")
            print(f"   Total Failed: {summary.get('import_failed') + summary.get('export_failed')}")
            
            # Print import results
            import_results = data.get('results', {}).get('import_results', [])
            if import_results:
                print(f"\n📥 IMPORT RESULTS:")
                for result in import_results:
                    container = result.get('container_id')
                    if result.get('success'):
                        pregate = result.get('pregate_status')
                        status = "✅ PASSED" if pregate else "❌ NOT PASSED"
                        milestone_count = result.get('milestone_count', 0)
                        print(f"   {container}: {status} | {milestone_count} milestones")
                        
                        # Show timeline preview (first 3 milestones)
                        timeline = result.get('timeline', [])
                        if timeline:
                            print(f"      Timeline preview:")
                            for idx, m in enumerate(timeline[:3], 1):
                                icon = "✅" if m['status'] == 'completed' else "⏳"
                                print(f"         {idx}. {icon} {m['milestone']} - {m['date']}")
                            if len(timeline) > 3:
                                print(f"         ... and {len(timeline) - 3} more")
                    else:
                        print(f"   {container}: ❌ FAILED - {result.get('error')}")
            
            # Print export results
            export_results = data.get('results', {}).get('export_results', [])
            if export_results:
                print(f"\n📤 EXPORT RESULTS:")
                for result in export_results:
                    container = result.get('container_id')
                    if result.get('success'):
                        booking = result.get('booking_number')
                        if booking:
                            print(f"   {container}: ✅ Booking: {booking}")
                        else:
                            print(f"   {container}: ⚠️  Booking: Not available")
                    else:
                        print(f"   {container}: ❌ FAILED - {result.get('error')}")
            
            # Print full JSON for reference
            print(f"\n📄 Full Response:")
            print(json.dumps(data, indent=2))
            
            return data.get('session_id')
            
        else:
            print(f"\n❌ FAILED")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"\n⏱️  TIMEOUT after {time.time() - start_time:.2f} seconds")
        return None
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return None


def test_bulk_with_existing_session(session_id):
    """Test bulk processing with existing session"""
    print_separator("TEST 2: Bulk Processing with Existing Session")
    
    # Use subset of containers for reuse test
    import_test = [IMPORT_CONTAINERS[0]] if IMPORT_CONTAINERS else []
    export_test = [EXPORT_CONTAINERS[0]] if EXPORT_CONTAINERS else []
    
    payload = {
        "session_id": session_id,
        "import_containers": import_test,
        "export_containers": export_test,
        "debug": False
    }
    
    print(f"📦 Reusing session: {session_id}")
    print(f"   Import containers: {len(import_test)}")
    print(f"   Export containers: {len(export_test)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_info_bulk",
            json=payload,
            timeout=600
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n⏱️  Response time: {elapsed_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS")
            print(f"   Message: {data.get('message')}")
            
            # Print results
            summary = data.get('results', {}).get('summary', {})
            print(f"\n📊 Results: {summary.get('import_success') + summary.get('export_success')} successful")
            
            return True
        else:
            print(f"\n❌ FAILED")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_import_only():
    """Test bulk processing with only import containers"""
    print_separator("TEST 3: Import Containers Only")
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY,
        "import_containers": IMPORT_CONTAINERS,
        "debug": False
    }
    
    print(f"📦 Testing import containers only")
    print(f"   Containers: {', '.join(IMPORT_CONTAINERS)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_info_bulk",
            json=payload,
            timeout=600
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n⏱️  Response time: {elapsed_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            summary = data.get('results', {}).get('summary', {})
            print(f"\n✅ SUCCESS: {summary.get('import_success')}/{summary.get('total_import')} successful")
            
            # Print pregate statuses with timeline info
            for result in data.get('results', {}).get('import_results', []):
                container = result.get('container_id')
                pregate = result.get('pregate_status')
                milestone_count = result.get('milestone_count', 0)
                if pregate is not None:
                    status = "PASSED" if pregate else "NOT PASSED"
                    print(f"   {container}: {status} ({milestone_count} milestones)")
            
            return True
        else:
            print(f"\n❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_export_only():
    """Test bulk processing with only export containers"""
    print_separator("TEST 4: Export Containers Only")
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha_api_key": CAPTCHA_API_KEY,
        "export_containers": EXPORT_CONTAINERS,
        "debug": False
    }
    
    print(f"📦 Testing export containers only")
    print(f"   Containers: {', '.join(EXPORT_CONTAINERS)}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_info_bulk",
            json=payload,
            timeout=600
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n⏱️  Response time: {elapsed_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            summary = data.get('results', {}).get('summary', {})
            print(f"\n✅ SUCCESS: {summary.get('export_success')}/{summary.get('total_export')} successful")
            
            # Print booking numbers
            for result in data.get('results', {}).get('export_results', []):
                container = result.get('container_id')
                booking = result.get('booking_number')
                if booking:
                    print(f"   {container}: {booking}")
                else:
                    print(f"   {container}: Not available")
            
            return True
        else:
            print(f"\n❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    """Run all tests"""
    print_separator("🧪 E-Modal Bulk Info Testing Suite")
    print(f"API URL: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    
    results = []
    
    # Test 1: Full bulk processing with new session
    print("\nStarting Test 1...")
    session_id = test_bulk_with_session_creation()
    results.append(("Bulk with new session", session_id is not None))
    
    # Test 2: Bulk processing with existing session
    if session_id:
        print("\nStarting Test 2...")
        time.sleep(2)  # Brief pause
        result = test_bulk_with_existing_session(session_id)
        results.append(("Bulk with existing session", result))
    else:
        results.append(("Bulk with existing session", False))
        print("\n⚠️  Skipping Test 2 (no session from Test 1)")
    
    # Test 3: Import only
    print("\nStarting Test 3...")
    time.sleep(2)
    result = test_import_only()
    results.append(("Import only", result))
    
    # Test 4: Export only
    print("\nStarting Test 4...")
    time.sleep(2)
    result = test_export_only()
    results.append(("Export only", result))
    
    # Print final summary
    print_separator("📊 TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()

