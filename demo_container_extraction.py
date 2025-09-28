#!/usr/bin/env python3
"""
E-Modal Container Extraction Demo
=================================

Quick demo of the container extraction functionality
"""

import requests
import json
import os
import time


def demo_container_extraction():
    """Demo the container extraction endpoint"""
    
    print("🚀 E-Modal Container Extraction Demo")
    print("=" * 50)
    
    # API endpoint
    api_url = "http://localhost:5000/get_containers"
    
    # Test payload
    payload = {
        "username": "jfernandez",
        "password": "taffie",
        "captcha_api_key": "5a0a4a97f8b4c9505d0b719cd92a9dcb",
        "keep_browser_alive": False  # Close browser after operation
    }
    
    print("📋 Configuration:")
    print(f"  👤 Username: {payload['username']}")
    print(f"  🔒 Password: {'*' * len(payload['password'])}")
    print(f"  🤖 2captcha Key: {payload['captcha_api_key'][:8]}...")
    print(f"  🔄 Keep Alive: {payload['keep_browser_alive']}")
    print()
    
    print("⚠️  This demo will:")
    print("  1. 🔐 Authenticate with E-Modal")
    print("  2. 🧩 Solve reCAPTCHA using 2captcha")
    print("  3. 📦 Navigate to containers page")
    print("  4. ☑️  Select all containers")
    print("  5. 📥 Download Excel file")
    print("  6. 🔒 Close browser session")
    print()
    
    input("Press Enter to start the demo...")
    print()
    
    print("🔄 Starting container extraction...")
    print("⏳ This may take 60-120 seconds...")
    
    try:
        start_time = time.time()
        
        # Make request
        response = requests.post(
            api_url,
            json=payload,
            timeout=300,  # 5 minute timeout
            stream=True   # For file download
        )
        
        duration = time.time() - start_time
        print(f"⏱️  Completed in {duration:.1f} seconds")
        
        if response.status_code == 200:
            # Check if it's an Excel file
            content_type = response.headers.get('content-type', '')
            
            if 'excel' in content_type or 'spreadsheet' in content_type:
                # Save the Excel file
                filename = f"emodal_containers_demo_{int(time.time())}.xlsx"
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = os.path.getsize(filename)
                
                print()
                print("🎉 SUCCESS! Container data extracted!")
                print("=" * 50)
                print(f"📄 File: {filename}")
                print(f"📊 Size: {file_size:,} bytes")
                print(f"📍 Location: {os.path.abspath(filename)}")
                print()
                print("✅ The Excel file contains all container data from E-Modal")
                print("✅ You can now open it in Excel or process it programmatically")
                
                return True
            else:
                print("❌ Unexpected response format")
                return False
        else:
            # Error response
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                
                print()
                print("❌ EXTRACTION FAILED")
                print("=" * 50)
                print(f"📝 Error: {error_msg}")
                
                # Provide specific troubleshooting
                if 'authentication' in error_msg.lower():
                    print("\n💡 SOLUTION:")
                    print("  - Verify your E-Modal credentials")
                    print("  - Check 2captcha API key and balance")
                    print("  - Ensure Urban VPN is connected to US server")
                elif 'vpn' in error_msg.lower() or '403' in error_msg:
                    print("\n💡 SOLUTION:")
                    print("  - Install Urban VPN Chrome extension")
                    print("  - Connect to a US server")
                    print("  - Restart Chrome and try again")
                elif 'navigation' in error_msg.lower():
                    print("\n💡 SOLUTION:")
                    print("  - Check if user has container page access")
                    print("  - Verify account permissions")
                elif 'recaptcha' in error_msg.lower():
                    print("\n💡 SOLUTION:")
                    print("  - Verify 2captcha API key")
                    print("  - Check 2captcha account balance")
                    print("  - Try again (reCAPTCHA can be inconsistent)")
                
                return False
                
            except json.JSONDecodeError:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"📝 Raw response: {response.text[:200]}...")
                return False
    
    except requests.exceptions.Timeout:
        print("⏱️ Request timed out after 5 minutes")
        print("💡 This usually indicates browser automation issues")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 Could not connect to API server")
        print("💡 Make sure the server is running: python emodal_business_api.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_api_status():
    """Check if API is running"""
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Status: {data.get('status')}")
            print(f"📊 Active Sessions: {data.get('active_sessions', 0)}")
            return True
        else:
            print("❌ API not responding properly")
            return False
    except:
        print("❌ API server not running")
        print("💡 Start it with: python emodal_business_api.py")
        return False


if __name__ == "__main__":
    print("🔍 Checking API status...")
    if check_api_status():
        print()
        demo_container_extraction()
    else:
        print("Cannot proceed without API server.")

