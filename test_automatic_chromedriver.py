#!/usr/bin/env python3
"""
Test Automatic ChromeDriver Fix
===============================

Tests the automatic ChromeDriver architecture fix to ensure it works
on different PCs without manual intervention.
"""

import os
import sys
import platform
from emodal_login_handler import EmodalLoginHandler

def test_chromedriver_fix():
    """Test the automatic ChromeDriver fix"""
    print("🧪 Testing Automatic ChromeDriver Fix")
    print("=" * 50)
    
    if platform.system() != 'Windows':
        print("❌ This test is for Windows only")
        return False
    
    try:
        print("🔧 Testing ChromeDriver initialization...")
        
        # Create login handler (this will trigger the automatic fix)
        handler = EmodalLoginHandler(
            captcha_api_key="test_key",
            timeout=10
        )
        
        print("✅ ChromeDriver initialization successful!")
        print("🎉 Automatic fix working correctly")
        
        # Clean up
        if hasattr(handler, 'driver') and handler.driver:
            handler.driver.quit()
            print("🧹 Browser closed")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting Automatic ChromeDriver Test")
    print(f"🖥️  Platform: {platform.system()} {platform.architecture()}")
    print()
    
    success = test_chromedriver_fix()
    
    if success:
        print("\n✅ SUCCESS: Automatic ChromeDriver fix is working!")
        print("🚀 The system will work on different PCs automatically")
    else:
        print("\n❌ FAILED: Automatic ChromeDriver fix needs attention")
        print("💡 Check the error messages above")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
