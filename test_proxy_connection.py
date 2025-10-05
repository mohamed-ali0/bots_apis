#!/usr/bin/env python3
"""
Proxy/VPN Connection Test Script
================================

Test script to verify proxy/VPN configuration before using in automation
"""

import requests
import os
import time
from anti_detection_config import get_proxy_config_from_env, get_vpn_config_from_env


def test_proxy_connection():
    """Test proxy/VPN connection"""
    print("🔍 Testing Proxy/VPN Connection")
    print("=" * 50)
    
    # Get proxy/VPN configuration
    proxy_config = get_proxy_config_from_env()
    vpn_config = get_vpn_config_from_env()
    
    if not proxy_config and not vpn_config:
        print("❌ No proxy/VPN configuration found")
        print("💡 Set environment variables or use proxy_vpn_config.env")
        return False
    
    # Use proxy or VPN config
    config = proxy_config or vpn_config
    config_type = "Proxy" if proxy_config else "VPN"
    
    print(f"🌐 Testing {config_type} configuration:")
    print(f"  Type: {config.get('type', 'http')}")
    print(f"  Host: {config.get('host')}")
    print(f"  Port: {config.get('port')}")
    print(f"  Username: {'***' if config.get('username') else 'None'}")
    print(f"  Password: {'***' if config.get('password') else 'None'}")
    
    # Build proxy URL
    proxy_type = config.get('type', 'http')
    host = config.get('host')
    port = config.get('port')
    username = config.get('username')
    password = config.get('password')
    
    if username and password:
        proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
    else:
        proxy_url = f"{proxy_type}://{host}:{port}"
    
    # Test proxy with requests
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    print(f"\n🧪 Testing connection...")
    
    try:
        # Test with a simple request
        response = requests.get(
            "http://httpbin.org/ip",
            proxies=proxies,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Connection successful!")
            print(f"  Your IP: {data.get('origin')}")
            return True
        else:
            print(f"❌ Connection failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ProxyError as e:
        print(f"❌ Proxy error: {e}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_stealth_features():
    """Test stealth features with Chrome"""
    print("\n🥷 Testing Stealth Features")
    print("=" * 50)
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        from anti_detection_config import AntiDetectionConfig
        
        # Get proxy/VPN configuration
        proxy_config = get_proxy_config_from_env() or get_vpn_config_from_env()
        use_proxy = proxy_config is not None
        
        print("🚀 Starting Chrome with stealth configuration...")
        
        # Initialize anti-detection
        anti_detection = AntiDetectionConfig(use_proxy=use_proxy, proxy_config=proxy_config)
        chrome_options = anti_detection.get_stealth_chrome_options()
        
        # Start Chrome
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Apply stealth JavaScript
        stealth_scripts = anti_detection.get_stealth_js_scripts()
        for script in stealth_scripts:
            try:
                driver.execute_script(script)
            except Exception as e:
                print(f"⚠️ Stealth script warning: {e}")
        
        print("✅ Chrome started with stealth configuration")
        
        # Test IP detection
        print("🔍 Testing IP detection...")
        driver.get("http://httpbin.org/ip")
        time.sleep(3)
        
        # Get page source to check IP
        page_source = driver.page_source
        if "origin" in page_source:
            print("✅ IP detection working")
        else:
            print("⚠️ IP detection may not be working")
        
        # Test user agent
        print("🔍 Testing user agent...")
        user_agent = driver.execute_script("return navigator.userAgent")
        print(f"  User Agent: {user_agent}")
        
        # Test webdriver property
        webdriver_prop = driver.execute_script("return navigator.webdriver")
        print(f"  WebDriver property: {webdriver_prop}")
        
        # Test automation detection
        automation_detected = driver.execute_script("""
            return window.navigator.webdriver !== undefined || 
                   window.chrome && window.chrome.runtime && window.chrome.runtime.onConnect
        """)
        print(f"  Automation detected: {automation_detected}")
        
        driver.quit()
        print("✅ Stealth test completed")
        return True
        
    except Exception as e:
        print(f"❌ Stealth test failed: {e}")
        return False


def main():
    """Main test function"""
    print("🧪 Proxy/VPN Connection Test Suite")
    print("=" * 60)
    
    # Test 1: Basic connection
    connection_ok = test_proxy_connection()
    
    # Test 2: Stealth features (if connection works)
    if connection_ok:
        stealth_ok = test_stealth_features()
    else:
        print("\n⚠️ Skipping stealth test due to connection failure")
        stealth_ok = False
    
    # Summary
    print("\n📊 Test Results")
    print("=" * 30)
    print(f"Proxy/VPN Connection: {'✅ PASS' if connection_ok else '❌ FAIL'}")
    print(f"Stealth Features: {'✅ PASS' if stealth_ok else '❌ FAIL'}")
    
    if connection_ok and stealth_ok:
        print("\n🎉 All tests passed! Your proxy/VPN is ready for automation.")
    else:
        print("\n⚠️ Some tests failed. Check your configuration.")
        print("💡 See proxy_vpn_config.env for configuration examples")


if __name__ == "__main__":
    main()
