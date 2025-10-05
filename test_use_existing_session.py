#!/usr/bin/env python3
"""
Test Using Existing Session
============================

Quick test to verify you can reuse an existing session_id
without creating a new one.

Usage:
    python test_use_existing_session.py
"""

import requests
import json
import time
import sys

# API Configuration
API_BASE_URL = "http://37.60.243.201:5010"


def test_health():
    """Check API health and show current sessions"""
    print("\n" + "="*70)
    print("💚 Health Check")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API is healthy")
            print(f"  📈 Session Capacity: {data.get('session_capacity')}")
            print(f"  🔄 Persistent Sessions: {data.get('persistent_sessions')}")
            print(f"  📊 Active Sessions: {data.get('active_sessions')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def list_sessions():
    """List all active sessions"""
    print("\n" + "="*70)
    print("📋 Active Sessions")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/sessions")
        
        if response.status_code == 200:
            data = response.json()
            sessions = data.get('sessions', [])
            
            if sessions:
                print(f"Found {len(sessions)} active session(s):\n")
                for i, session in enumerate(sessions, 1):
                    print(f"  {i}. Session ID: {session['session_id']}")
                    print(f"     👤 Username: {session['username']}")
                    print(f"     📅 Created: {session['created_at']}")
                    print(f"     🔄 Last Used: {session['last_used']}")
                    print(f"     💾 Keep Alive: {session['keep_alive']}")
                    print("")
                return sessions
            else:
                print("  ⚠️ No active sessions found")
                print("  💡 Create a session first using test_session_workflow.py")
                return []
        else:
            print(f"❌ Failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Exception: {e}")
        return []


def test_with_session(session_id):
    """Test using an existing session_id"""
    print("\n" + "="*70)
    print("🧪 Testing with Existing Session")
    print("="*70)
    print(f"📋 Session ID: {session_id}")
    print("")
    
    # Ask for count
    count = input("Enter container count to fetch (e.g., 20, 50, 100) [default: 20]: ").strip()
    if not count:
        count = "20"
    
    try:
        count = int(count)
    except:
        print("❌ Invalid number, using 20")
        count = 20
    
    payload = {
        "session_id": session_id,  # Use provided session_id
        "target_count": count,
        "debug": False,
        "return_url": True
    }
    
    try:
        print(f"\n🔄 Getting {count} containers using existing session...")
        print("⏱️ Starting timer...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/get_containers",
            json=payload,
            timeout=600
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success! (took {elapsed:.1f}s)")
            print("")
            print("📊 Response Details:")
            print(f"  📋 Session ID: {data.get('session_id')}")
            print(f"  🆕 Is New Session: {data.get('is_new_session')}")
            print(f"  👤 Username: {data.get('username', 'N/A')}")
            print(f"  📄 File: {data.get('file_name')}")
            print(f"  📊 Total Containers: {data.get('total_containers')}")
            print(f"  💾 File Size: {data.get('file_size')} bytes")
            print(f"  🔗 Download URL: {data.get('file_url')}")
            print("")
            
            if data.get('is_new_session'):
                print("⚠️  WARNING: A new session was created!")
                print("   This means the provided session_id was invalid or expired.")
            else:
                print("✅ SUCCESS: Existing session was reused!")
                print(f"   ⚡ Fast operation (no login required)")
                print(f"   ⏱️  Time: {elapsed:.1f}s (vs ~20s with login)")
            
            return True
        else:
            print(f"\n❌ Failed: {response.status_code}")
            error = response.json()
            print(f"  Error: {error.get('error')}")
            
            if response.status_code == 400:
                print("\n💡 Tip: The session_id might be invalid or expired.")
                print("   Try creating a new session with test_session_workflow.py")
            
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


def main():
    """Main test flow"""
    print("\n" + "="*70)
    print("🧪 Test Using Existing Session")
    print("="*70)
    print("")
    
    # Health check
    if not test_health():
        print("\n❌ Health check failed. Is the API running?")
        return 1
    
    # List active sessions
    sessions = list_sessions()
    
    # Get session_id from user
    print("\n" + "="*70)
    print("📝 Enter Session ID")
    print("="*70)
    
    if sessions:
        print("\n💡 You can copy a session_id from above, or enter a different one.")
    
    session_id = input("\nEnter session_id to use: ").strip()
    
    if not session_id:
        print("\n❌ Session ID is required!")
        print("💡 Run test_session_workflow.py to create a session first.")
        return 1
    
    # Test with the session
    success = test_with_session(session_id)
    
    # Final health check
    print("\n⏸️  Press Enter for final health check...")
    input()
    test_health()
    
    print("\n" + "="*70)
    if success:
        print("✅ Test Completed Successfully!")
        print("💡 The session is still active and can be reused again.")
    else:
        print("❌ Test Failed")
        print("💡 Check the error message above for details.")
    print("="*70)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

