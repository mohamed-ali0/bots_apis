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
        response = requests.get("http://localhost:5000/health")
        
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
    
    # Get credentials
    username = input("Enter E-Modal username (or press Enter for 'jfernandez'): ").strip() or "jfernandez"
    password = input("Enter E-Modal password (or press Enter for 'taffie'): ").strip() or "taffie"
    api_key = input("Enter 2captcha API key (or press Enter for demo key): ").strip() or "5a0a4a97f8b4c9505d0b719cd92a9dcb"
    
    keep_alive_input = input("Keep browser alive for more operations? (y/N): ").strip().lower()
    keep_alive = keep_alive_input in ['y', 'yes']
    
    payload = {
        "username": username,
        "password": password,
        "captcha_api_key": api_key,
        "keep_browser_alive": keep_alive
    }
    
    print(f"🚀 Testing container extraction for user: {username}")
    print(f"🔄 Keep browser alive: {keep_alive}")
    print("⏳ This may take 60-120 seconds (login + reCAPTCHA + data extraction)...")
    
    try:
        start_time = time.time()
        response = requests.post(
            "http://localhost:5000/get_containers",
            json=payload,
            timeout=300,  # 5 minute timeout
            stream=True   # For file download
        )
        duration = time.time() - start_time
        
        print(f"⏱️ Request completed in {duration:.1f} seconds")
        print(f"📊 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            # Check if response is a file
            content_type = response.headers.get('content-type', '')
            
            if 'excel' in content_type or 'spreadsheet' in content_type:
                # It's an Excel file
                filename = f"containers_{username}_{int(time.time())}.xlsx"
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = os.path.getsize(filename)
                print("🎉 CONTAINER EXTRACTION SUCCESSFUL!")
                print(f"  📄 File saved: {filename}")
                print(f"  📊 File size: {file_size} bytes")
                
                if keep_alive:
                    print("  🔄 Browser session kept alive for more operations")
                    print("  💡 Use GET /sessions to see active sessions")
                else:
                    print("  🔒 Browser session closed")
                
                return True
                
            else:
                # It's a JSON error response
                try:
                    data = response.json()
                    print("❌ CONTAINER EXTRACTION FAILED")
                    print(f"  📝 Error: {data.get('error', 'Unknown error')}")
                    return False
                except:
                    print("❌ Unexpected response format")
                    print(f"  📝 Content: {response.text[:200]}...")
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


def test_sessions():
    """Test session management"""
    print("\n🔗 Testing session management...")
    
    try:
        response = requests.get("http://localhost:5000/sessions")
        
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
    
    # Test 1: Health check
    if not test_health():
        print("❌ Health check failed. Cannot proceed.")
        return
    
    # Test 2: Session management
    test_sessions()
    
    # Test 3: Container extraction (optional)
    print("\n" + "=" * 50)
    choice = input("🤔 Do you want to test container extraction? (y/N): ").strip().lower()
    
    if choice in ['y', 'yes']:
        print("\n⚠️  CONTAINER EXTRACTION WARNING:")
        print("  - This will open a Chrome browser")
        print("  - Requires Urban VPN connected to US")
        print("  - Uses your 2captcha account balance")
        print("  - May take 1-2 minutes to complete")
        print("  - Will download Excel file with container data")
        
        confirm = input("\n💰 Continue? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            test_get_containers()
            
            # Test session management after
            print("\n📊 Checking sessions after container extraction...")
            test_sessions()
        else:
            print("⏭️  Skipping container extraction test")
    else:
        print("⏭️  Skipping container extraction test")
    
    print("\n🎉 Test suite completed!")
    print("📝 Check the API logs for detailed information")


if __name__ == "__main__":
    main()

