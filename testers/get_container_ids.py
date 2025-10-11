#!/usr/bin/env python3
"""
Helper script to get actual container IDs from your E-Modal account
This will help you find real container IDs to use in bulk testing
"""

import requests
import json

# Configuration
API_BASE_URL = "http://37.60.243.201:5010"  # Remote server
# API_BASE_URL = "http://localhost:5010"  # Local server

# Your credentials
USERNAME = "Gustavoa"
PASSWORD = "Julian_1"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

def get_containers():
    """
    Get list of containers from your account using the /get_containers endpoint
    This will help identify real container IDs for testing
    """
    print("="*70)
    print("  Getting Container IDs from E-Modal")
    print("="*70)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"Username: {USERNAME}")
    print("\n⏳ Fetching containers (this may take a minute)...\n")
    
    try:
        # Use get_containers endpoint with "Get Specific Count" mode
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json={
                "username": USERNAME,
                "password": PASSWORD,
                "captcha_api_key": CAPTCHA_API_KEY,
                "mode": "count",  # Get specific count
                "target_count": 20,  # Get first 20 containers
                "return_url": True,  # Get Excel file URL
                "debug": False
            },
            timeout=300  # 5 minutes
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                print("✅ Successfully retrieved containers!")
                print(f"   Session ID: {data.get('session_id')}")
                
                excel_url = data.get('excel_url')
                if excel_url:
                    print(f"   Excel URL: {excel_url}")
                    print("\n📋 Container IDs are in the Excel file")
                    print("   Download the Excel file and copy container IDs from the 'Container #' column")
                    print("\n   Example container IDs to look for:")
                    print("   - Import containers: Check 'Trade Type' = IMPORT")
                    print("   - Export containers: Check 'Trade Type' = EXPORT")
                    print("   - Look for containers with different statuses (GATE IN, GATE OUT, IN YARD, ON VESSEL)")
                    
                    print("\n📝 Update test_bulk_info.py with actual container IDs:")
                    print("   IMPORT_CONTAINERS = ['CONTAINER1', 'CONTAINER2', 'CONTAINER3']")
                    print("   EXPORT_CONTAINERS = ['CONTAINER4', 'CONTAINER5']")
                else:
                    print("⚠️  No Excel URL returned")
                
                return data.get('session_id')
            else:
                print(f"❌ Failed: {data.get('error')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("⏱️  Request timed out")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def get_sample_with_list_sessions():
    """
    Alternative approach: Create session and list it to see container info
    """
    print("\n" + "="*70)
    print("  Alternative: Get Sample Container from Sessions")
    print("="*70)
    
    try:
        # First, get or create a session
        print("\n⏳ Creating session...")
        session_response = requests.post(
            f"{API_BASE_URL}/get_session",
            json={
                "username": USERNAME,
                "password": PASSWORD,
                "captcha_api_key": CAPTCHA_API_KEY
            },
            timeout=120
        )
        
        if session_response.status_code == 200:
            session_data = session_response.json()
            if session_data.get('success'):
                session_id = session_data.get('session_id')
                print(f"✅ Session created: {session_id}")
                
                # List active sessions
                print("\n⏳ Listing active sessions...")
                sessions_response = requests.get(f"{API_BASE_URL}/sessions")
                
                if sessions_response.status_code == 200:
                    sessions_data = sessions_response.json()
                    print(f"\n📊 Active sessions: {sessions_data.get('active_sessions')}")
                    
                    for session in sessions_data.get('sessions', []):
                        print(f"\n   Session ID: {session.get('session_id')}")
                        print(f"   Username: {session.get('username')}")
                        print(f"   URL: {session.get('current_url')}")
                
                print("\n💡 Tip: You can now manually browse to the Containers page")
                print("   and note down container IDs to use in bulk testing")
                
                return session_id
            else:
                print(f"❌ Session creation failed: {session_data.get('error')}")
        else:
            print(f"❌ HTTP Error {session_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None


def main():
    """Main function"""
    print("\n🔍 E-Modal Container ID Helper")
    print("   This script helps you find real container IDs for testing\n")
    
    # Try to get containers via API
    session_id = get_containers()
    
    # If that works, offer to get more info
    if session_id:
        print("\n" + "="*70)
        print("  Next Steps")
        print("="*70)
        print("\n1. Download the Excel file from the URL above")
        print("2. Open it and find container IDs from the 'Container #' column")
        print("3. Look for containers with:")
        print("   - IMPORT trade type (for pregate status testing)")
        print("   - EXPORT trade type (for booking number testing)")
        print("4. Update test_bulk_info.py with actual container IDs")
        print("\n5. Run the bulk test:")
        print("   python test_bulk_info.py")
    else:
        # Fallback approach
        print("\n⚠️  First approach failed, trying alternative method...")
        get_sample_with_list_sessions()
    
    print("\n" + "="*70)
    print("  Manual Method (if API approach doesn't work)")
    print("="*70)
    print("\n1. Login to E-Modal manually: https://truckerportal.emodal.com")
    print("2. Go to Containers page")
    print("3. Look at the container list")
    print("4. Copy 2-3 IMPORT container IDs")
    print("5. Copy 1-2 EXPORT container IDs")
    print("6. Update test_bulk_info.py with these IDs")
    print("\nExample container ID formats:")
    print("  - MSCU5165756 (11 characters: 4 letters + 7 digits)")
    print("  - TRHU1866154 (11 characters)")
    print("  - MSDU4431979 (11 characters)")
    print("\n")


if __name__ == "__main__":
    main()

