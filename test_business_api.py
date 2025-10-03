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
import sys

# API Configuration - will be set after user chooses server
API_HOST = None
API_PORT = None
API_BASE_URL = None


def choose_server():
    """Prompt user to choose between local or remote server"""
    global API_HOST, API_PORT, API_BASE_URL
    
    # Check if running in non-interactive mode
    auto_test = os.environ.get('AUTO_TEST', '0') == '1'
    
    if auto_test or os.environ.get('API_HOST'):
        # Use environment variables in non-interactive mode
        API_HOST = os.environ.get('API_HOST', '89.117.63.196')
        API_PORT = os.environ.get('API_PORT', '5010')
        API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
        print(f"🌐 Using API server from environment: {API_BASE_URL}")
        return
    
    # Interactive mode - ask user
    print("\n" + "=" * 60)
    print("🌐 API Server Selection")
    print("=" * 60)
    print("Choose which server to connect to:")
    print("")
    print("  1. Local server     (http://localhost:5010)")
    print("  2. Remote server 1  (http://89.117.63.196:5010)")
    print("  3. Remote server 2  (http://37.60.243.201:5010)")
    print("  4. Custom server    (enter IP/hostname)")
    print("")
    
    while True:
        choice = input("Enter your choice (1/2/3/4) [default: 2]: ").strip()
        
        # Default to remote server 1
        if not choice:
            choice = "2"
        
        if choice == "1":
            API_HOST = "localhost"
            API_PORT = "5010"
            print(f"✅ Selected: Local server")
            break
        elif choice == "2":
            API_HOST = "89.117.63.196"
            API_PORT = "5010"
            print(f"✅ Selected: Remote server 1 (89.117.63.196)")
            break
        elif choice == "3":
            API_HOST = "37.60.243.201"
            API_PORT = "5010"
            print(f"✅ Selected: Remote server 2 (37.60.243.201)")
            break
        elif choice == "4":
            API_HOST = input("Enter server IP/hostname: ").strip()
            API_PORT = input("Enter port [5010]: ").strip() or "5010"
            print(f"✅ Selected: Custom server ({API_HOST}:{API_PORT})")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
    
    API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
    print(f"🔗 API URL: {API_BASE_URL}")
    print("=" * 60 + "\n")


def test_health():
    """Test health endpoint"""
    print("🔍 Testing business API health...")
    print(f"  🌐 API URL: {API_BASE_URL}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
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
        print(f"❌ API server not running at {API_BASE_URL}")
        print("   Please start with: python emodal_business_api.py")
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
    
    # Get infinite_scrolling parameter
    # In interactive mode, ask user; in auto mode, use environment variable
    if not auto_test:
        print("\n📜 Infinite Scrolling Options:")
        print("  1. Enable (loads ALL containers - may take 2-5 minutes)")
        print("  2. Disable (first page only - ~40 containers)")
        scroll_choice = input("\nEnable infinite scrolling? (1/2) [default: 2]: ").strip()
        infinite_scrolling = scroll_choice == '1'
    else:
        infinite_scrolling = os.environ.get('INFINITE_SCROLLING', 'false').lower() in ['1', 'true', 'yes', 'y']
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": api_key,
        "keep_browser_alive": keep_alive,
        "capture_screens": True,
        "screens_label": username,
        "infinite_scrolling": infinite_scrolling
    }
    
    print(f"🚀 Testing container extraction for user: {username}")
    print(f"🔄 Keep browser alive: {keep_alive}")
    print(f"📜 Infinite scrolling: {infinite_scrolling}")
    print("⏳ This may take 60-120 seconds (login + reCAPTCHA + data extraction)...")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
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
            total_containers = data.get('total_containers', 'unknown')
            scroll_cycles = data.get('scroll_cycles', 0)
            if bundle_url:
                print("🎉 CONTAINER EXTRACTION SUCCESSFUL!")
                print(f"  📦 Bundle URL: {bundle_url}")
                print(f"  📊 Total containers: {total_containers}")
                print(f"  🔄 Scroll cycles: {scroll_cycles}")
                
                # Always close any sessions for this user after the test finishes
                if keep_alive:
                    print("  🔄 Browser session kept alive for more operations")
                    print("  💡 Use GET /sessions to see active sessions")
                else:
                    # Close sessions for this user after test completes
                    try:
                        sessions = requests.get(f"{API_BASE_URL}/sessions").json().get('sessions', [])
                        closed_any = False
                        for s in sessions:
                            if s.get('username') == username:
                                sid = s.get('session_id')
                                if sid:
                                    requests.delete(f"{API_BASE_URL}/sessions/{sid}")
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
            f"{API_BASE_URL}/make_appointment",
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
                        sessions = requests.get(f"{API_BASE_URL}/sessions").json().get('sessions', [])
                        for s in sessions:
                            if s.get('username') == username:
                                sid = s.get('session_id')
                                if sid:
                                    requests.delete(f"{API_BASE_URL}/sessions/{sid}")
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
        response = requests.get(f"{API_BASE_URL}/sessions")
        
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
    print("\n" + "="*70)
    print("E-MODAL BUSINESS API TEST - INFINITE SCROLLING")
    print("="*70)
    
    # Choose server first
    choose_server()
    
    # Test health
    if not test_health():
        print("\n❌ Health check failed! API might not be running.")
        return
    
    # Test active sessions
    test_sessions()
    
    # Run the main test - Get containers WITH infinite scrolling
    print("\n" + "="*70)
    print("TESTING: Get Containers with Infinite Scrolling")
    print("="*70)
    print("\n⚠️  This test will take several minutes to complete!")
    print("   The system will scroll through all containers until no new content appears.")
    print("   Estimated time: 2-5 minutes depending on the number of containers.\n")
    
    input("Press Enter to start the test...")
    
    # Get configuration for infinite scrolling
    print("\nChoose test mode:")
    print("  1. With infinite scrolling (loads ALL containers)")
    print("  2. Without infinite scrolling (first page only - ~40 containers)")
    
    choice = input("\nEnter your choice (1/2) [default: 1]: ").strip()
    
    # Set environment variable for infinite scrolling
    if choice != '2':
        os.environ['INFINITE_SCROLLING'] = 'true'
    else:
        os.environ['INFINITE_SCROLLING'] = 'false'
    
    # Test with chosen mode
    result = test_get_containers()
    
    if result:
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"\n📊 Results:")
        print(f"   Total containers retrieved: {result.get('total_containers', 'N/A')}")
        if 'scroll_cycles' in result:
            print(f"   Scroll cycles performed: {result.get('scroll_cycles', 'N/A')}")
        print(f"   Excel file: {result.get('file_name', 'N/A')}")
        print(f"   File size: {result.get('file_size', 'N/A')} bytes")
        
        if 'download_url' in result:
            print(f"\n📥 Download your file:")
            print(f"   {result['download_url']}")
    else:
        print("\n" + "="*70)
        print("❌ TEST FAILED")
        print("="*70)
    
    return


if __name__ == "__main__":
    main()

