#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify proxy extension creation and loading
"""

import os
import sys
import zipfile
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def test_proxy_extension():
    """Test that proxy extension can be created"""
    
    print("="*70)
    print(" PROXY EXTENSION TEST")
    print("="*70)
    print()
    
    # Import the handler
    try:
        from emodal_login_handler import EModalLoginHandler
        print("✅ EModalLoginHandler imported successfully")
    except Exception as e:
        print(f"❌ Failed to import: {e}")
        return False
    
    # Create a handler instance (no captcha key needed for extension test)
    try:
        handler = EModalLoginHandler(
            captcha_api_key="test_key",
            use_vpn_profile=False,
            auto_close=True
        )
        print("✅ Handler instance created")
    except Exception as e:
        print(f"❌ Failed to create handler: {e}")
        return False
    
    # Test extension creation
    try:
        extension_path = handler._create_proxy_extension()
        
        if not extension_path:
            print("❌ Extension creation returned None")
            return False
        
        print(f"✅ Extension created: {extension_path}")
        
        # Verify file exists
        if not os.path.exists(extension_path):
            print(f"❌ Extension file not found: {extension_path}")
            return False
        
        print(f"✅ Extension file exists")
        print(f"   Size: {os.path.getsize(extension_path)} bytes")
        
        # Verify ZIP contents
        with zipfile.ZipFile(extension_path, 'r') as zf:
            files = zf.namelist()
            print(f"✅ ZIP contains: {files}")
            
            # Check manifest
            if 'manifest.json' not in files:
                print("❌ manifest.json missing from ZIP")
                return False
            
            manifest_data = zf.read('manifest.json')
            manifest = json.loads(manifest_data)
            print(f"✅ manifest.json valid")
            print(f"   Version: {manifest.get('version')}")
            print(f"   Name: {manifest.get('name')}")
            print(f"   Permissions: {len(manifest.get('permissions', []))} items")
            
            # Check background script
            if 'background.js' not in files:
                print("❌ background.js missing from ZIP")
                return False
            
            background_data = zf.read('background.js').decode('utf-8')
            print(f"✅ background.js valid")
            print(f"   Size: {len(background_data)} characters")
            
            # Verify credentials are embedded
            if 'mo3li_moQef' in background_data:
                print(f"✅ Username found in background.js")
            else:
                print(f"⚠️  Username not found in background.js")
            
            if 'dc.oxylabs.io' in background_data:
                print(f"✅ Proxy host found in background.js")
            else:
                print(f"⚠️  Proxy host not found in background.js")
        
        print()
        print("="*70)
        print(" TEST PASSED ✅")
        print("="*70)
        print()
        print("Extension is ready to use!")
        print(f"Path: {extension_path}")
        print()
        print("Next steps:")
        print("1. Restart your API server")
        print("2. Run test_all_endpoints.py")
        print("3. Watch for proxy extension messages in logs")
        print("4. Verify NO authentication popup appears")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Extension creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_proxy_extension()
    sys.exit(0 if success else 1)

