#!/usr/bin/env python3
"""
E-Modal Business API Test Script
===============================

Test script for the E-Modal business operations API
"""

import requests
import json
import time
import os


def test_health():
    """Test health endpoint"""
    print("🔍 Testing business API health...")
    
    try:
        response = requests.get("http://89.117.63.196:5010/health")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check passed")
            print(f"  📊 Status: {data.get('status')}")
            print(f"  🔗 Service: {data.get('service')}")
            print(f"  📈 Active sessions: {data.get('active_sessions')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ API server not running. Please start with: python emodal_business_api.py")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_get_containers():
    """Test get_containers endpoint"""
    print("\n📦 Testing get_containers endpoint...")
    
    # Non-interactive mode via environment variables
    auto_test = os.environ.get('AUTO_TEST', '1') == '1'
    if auto_test:
        username = os.environ.get('EMODAL_USERNAME', 'jfernandez')
        password = os.environ.get('EMODAL_PASSWORD', 'taffie')
        api_key = os.environ.get('CAPTCHA_API_KEY', '5a0a4a97f8b4c9505d0b719cd92a9dcb')
        keep_alive = os.environ.get('KEEP_BROWSER_ALIVE', 'true').lower() in ['1', 'true', 'yes', 'y']
    else:
        # Interactive fallback
        username = input("Enter E-Modal username (or press Enter for 'jfernandez'): ").strip() or "jfernandez"
        password = input("Enter E-Modal password (or press Enter for 'taffie'): ").strip() or "taffie"
        api_key = input("Enter 2captcha API key (or press Enter for demo key): ").strip() or "5a0a4a97f8b4c9505d0b719cd92a9dcb"
        keep_alive_input = input("Keep browser alive for more operations? (y/N): ").strip().lower()
        keep_alive = keep_alive_input in ['y', 'yes']
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": api_key,
        "keep_browser_alive": keep_alive,
        "capture_screens": True,
        "screens_label": username
    }
    
    print(f"🚀 Testing container extraction for user: {username}")
    print(f"🔄 Keep browser alive: {keep_alive}")
    print("⏳ This may take 60-120 seconds (login + reCAPTCHA + data extraction)...")
    
    try:
        start_time = time.time()
        response = requests.post(
            "http://89.117.63.196:5010/get_containers",
            json={**payload, "return_url": True},
            timeout=300
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Request completed in {duration:.1f} seconds")
        print(f"📊 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            # Expect JSON with download_url
            data = response.json()
            bundle_url = data.get('bundle_url')
            if bundle_url:
                print("🎉 CONTAINER EXTRACTION SUCCESSFUL!")
                print(f"  📦 Bundle URL: {bundle_url}")
                
                # Always close any sessions for this user after the test finishes
                if keep_alive:
                    print("  🔄 Browser session kept alive for more operations")
                    print("  💡 Use GET /sessions to see active sessions")
                else:
                    # Close sessions for this user after test completes
                    try:
                        sessions = requests.get("http://89.117.63.196:5010/sessions").json().get('sessions', [])
                        closed_any = False
                        for s in sessions:
                            if s.get('username') == username:
                                sid = s.get('session_id')
                                if sid:
                                    requests.delete(f"http://89.117.63.196:5010/sessions/{sid}")
                                    print(f"  🔒 Closed session: {sid}")
                                    closed_any = True
                        if not closed_any:
                            print("  🔒 No sessions to close for user")
                    except Exception as ce:
                        print(f"  ⚠️ Could not auto-close session(s): {ce}")
                
                return True
            else:
                print("❌ Unexpected response (no download_url)")
                print(f"  📝 Payload: {data}")
                return False
        else:
            # Error response
            try:
                data = response.json()
                print("❌ CONTAINER EXTRACTION FAILED")
                print(f"  📝 Error: {data.get('error', 'Unknown error')}")
                
                # Provide troubleshooting hints
                error_msg = data.get('error', '').lower()
                if 'authentication' in error_msg or 'login' in error_msg:
                    print("\n💡 TROUBLESHOOTING:")
                    print("  - Verify username and password")
                    print("  - Check 2captcha API key and balance")
                    print("  - Ensure Urban VPN is connected to US")
                elif 'navigation' in error_msg:
                    print("\n💡 TROUBLESHOOTING:")
                    print("  - Container page may have changed")
                    print("  - Check if user has container access permissions")
                elif 'selection' in error_msg or 'checkbox' in error_msg:
                    print("\n💡 TROUBLESHOOTING:")
                    print("  - Container page layout may have changed")
                    print("  - Try with keep_browser_alive=true to debug manually")
                elif 'download' in error_msg:
                    print("\n💡 TROUBLESHOOTING:")
                    print("  - Excel export button may have moved")
                    print("  - Check if containers are selected properly")
                
                return False
            except:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"  📝 Response: {response.text[:200]}...")
                return False
            
    except requests.exceptions.Timeout:
        print("⏱️ Request timed out (>5 minutes)")
        print("💡 This might indicate browser automation issues")
        return False
    except Exception as e:
        print(f"❌ Container extraction test error: {e}")
        return False


def test_make_appointment():
    """Test make_appointment endpoint"""
    print("\n📅 Testing make_appointment endpoint...")
    
    # Non-interactive mode via environment variables
    auto_test = os.environ.get('AUTO_TEST', '1') == '1'
    if auto_test:
        username = os.environ.get('EMODAL_USERNAME', 'jfernandez')
        password = os.environ.get('EMODAL_PASSWORD', 'taffie')
        api_key = os.environ.get('CAPTCHA_API_KEY', '5a0a4a97f8b4c9505d0b719cd92a9dcb')
        keep_alive = os.environ.get('KEEP_BROWSER_ALIVE', 'true').lower() in ['1', 'true', 'yes', 'y']
    else:
        username = input("Enter E-Modal username (or press Enter for 'jfernandez'): ").strip() or "jfernandez"
        password = input("Enter E-Modal password (or press Enter for 'taffie'): ").strip() or "taffie"
        api_key = input("Enter 2captcha API key (or press Enter for demo key): ").strip() or "5a0a4a97f8b4c9505d0b719cd92a9dcb"
        keep_alive_input = input("Keep browser alive for more operations? (y/N): ").strip().lower()
        keep_alive = keep_alive_input in ['y', 'yes']
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": api_key,
        "keep_browser_alive": keep_alive,
        "capture_screens": True,
        "screens_label": username,
        "return_url": True
    }
    
    print(f"🚀 Navigating to Make Appointment for user: {username}")
    try:
        start_time = time.time()
        response = requests.post(
            "http://89.117.63.196:5010/make_appointment",
            json=payload,
            timeout=300
        )
        duration = time.time() - start_time
        print(f"⏱️ Request completed in {duration:.1f} seconds")
        print(f"📊 HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            bundle_url = data.get('bundle_url')
            if bundle_url:
                print("🎉 MAKE APPOINTMENT READY!")
                print(f"  📦 Bundle URL: {bundle_url}")
                if not keep_alive:
                    try:
                        sessions = requests.get("http://89.117.63.196:5010/sessions").json().get('sessions', [])
                        for s in sessions:
                            if s.get('username') == username:
                                sid = s.get('session_id')
                                if sid:
                                    requests.delete(f"http://89.117.63.196:5010/sessions/{sid}")
                                    print(f"  🔒 Closed session: {sid}")
                    except Exception as ce:
                        print(f"  ⚠️ Could not auto-close session(s): {ce}")
                return True
        else:
            try:
                data = response.json()
                print("❌ MAKE APPOINTMENT FAILED")
                print(f"  📝 Error: {data.get('error', 'Unknown error')}")
            except Exception:
                print("❌ Unexpected response format")
                print(f"  📝 Content: {response.text[:200]}...")
        return False
    except Exception as e:
        print(f"❌ Make appointment test error: {e}")
        return False


def test_sessions():
    """Test session management"""
    print("\n🔗 Testing session management...")
    
    try:
        response = requests.get("http://89.117.63.196:5010/sessions")
        
        if response.status_code == 200:
            data = response.json()
            active_count = data.get('active_sessions', 0)
            sessions = data.get('sessions', [])
            
            print(f"✅ Sessions endpoint working")
            print(f"  📈 Active sessions: {active_count}")
            
            if sessions:
                print("  📋 Session details:")
                for i, session in enumerate(sessions):
                    print(f"    {i+1}. ID: {session.get('session_id', 'N/A')}")
                    print(f"       User: {session.get('username', 'N/A')}")
                    print(f"       Keep alive: {session.get('keep_alive', False)}")
                    print(f"       Current URL: {session.get('current_url', 'N/A')}")
            else:
                print("  📭 No active sessions")
            
            return True
        else:
            print(f"❌ Sessions check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Sessions test error: {e}")
        return False


def main():
    """Main test function"""
    print("🧪 E-Modal Business API Test Suite")
    print("=" * 50)
    
    # Test get_containers with infinite scroll
    if not test_health():
        print("❌ Health check failed. Cannot proceed.")
        return
    test_sessions()
    print("\n" + "=" * 50)
    print("🚀 Running get_containers test...")
    ok = test_get_containers()
    if not ok:
        print("❌ get_containers test failed")
    return


if __name__ == "__main__":
    main()

