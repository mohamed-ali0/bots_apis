#!/usr/bin/env python3
"""
ChromeDriver Fix Script
======================

This script fixes ChromeDriver issues by:
1. Clearing corrupted cache
2. Downloading fresh ChromeDriver
3. Verifying the binary works
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

def clear_chromedriver_cache():
    """Clear any corrupted ChromeDriver cache"""
    print("🧹 Clearing ChromeDriver cache...")
    
    # Clear webdriver-manager cache
    cache_dirs = [
        os.path.expanduser("~/.wdm"),
        os.path.expanduser("~/.cache/selenium"),
        os.path.join(os.getcwd(), ".wdm")
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir, ignore_errors=True)
                print(f"  ✅ Cleared: {cache_dir}")
            except Exception as e:
                print(f"  ⚠️ Could not clear {cache_dir}: {e}")

def download_fresh_chromedriver():
    """Download a fresh ChromeDriver using webdriver-manager"""
    print("📦 Downloading fresh ChromeDriver...")
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        # Force fresh download
        driver_path = ChromeDriverManager().install()
        print(f"  ✅ Downloaded to: {driver_path}")
        
        # Verify the binary
        if os.path.exists(driver_path):
            print(f"  📊 File size: {os.path.getsize(driver_path)} bytes")
            
            # Test if it's executable
            try:
                if platform.system() == "Windows":
                    # On Windows, try to run chromedriver --version
                    result = subprocess.run([driver_path, "--version"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"  ✅ ChromeDriver version: {result.stdout.strip()}")
                        return True
                    else:
                        print(f"  ❌ ChromeDriver test failed: {result.stderr}")
                        return False
                else:
                    # On Linux/Mac, check if file is executable
                    if os.access(driver_path, os.X_OK):
                        print("  ✅ ChromeDriver is executable")
                        return True
                    else:
                        print("  ❌ ChromeDriver is not executable")
                        return False
            except Exception as test_error:
                print(f"  ❌ ChromeDriver test failed: {test_error}")
                return False
        else:
            print("  ❌ ChromeDriver file not found after download")
            return False
            
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False

def download_manual_chromedriver():
    """Download ChromeDriver manually if webdriver-manager fails"""
    print("🔄 Trying manual ChromeDriver download...")
    
    try:
        import requests
        import zipfile
        
        # Get Chrome version
        chrome_version = get_chrome_version()
        if not chrome_version:
            print("  ❌ Could not detect Chrome version")
            return False
            
        print(f"  🔍 Detected Chrome version: {chrome_version}")
        
        # Download appropriate ChromeDriver
        major_version = chrome_version.split('.')[0]
        if platform.system() == "Windows":
            url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
            try:
                response = requests.get(url)
                driver_version = response.text.strip()
                download_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_win32.zip"
            except:
                # Fallback to latest stable
                download_url = "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
                response = requests.get(download_url)
                driver_version = response.text.strip()
                download_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_win32.zip"
        else:
            print("  ❌ Manual download only supported on Windows")
            return False
            
        print(f"  📥 Downloading ChromeDriver {driver_version}...")
        response = requests.get(download_url)
        
        if response.status_code == 200:
            zip_path = "chromedriver.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)
                
            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
                
            # Clean up
            os.remove(zip_path)
            
            # Make executable
            chromedriver_path = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
            if os.path.exists(chromedriver_path):
                print(f"  ✅ Manual download successful: {chromedriver_path}")
                return True
            else:
                print("  ❌ ChromeDriver not found after extraction")
                return False
        else:
            print(f"  ❌ Download failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Manual download failed: {e}")
        return False

def get_chrome_version():
    """Get installed Chrome version"""
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
            version, _ = winreg.QueryValueEx(key, "version")
            return version
        else:
            # Try to get version from command line
            result = subprocess.run(["google-chrome", "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split()[-1]
    except Exception:
        pass
    return None

def main():
    """Main fix process"""
    print("🔧 ChromeDriver Fix Script")
    print("=" * 50)
    
    # Step 1: Clear cache
    clear_chromedriver_cache()
    
    # Step 2: Try webdriver-manager
    print("\n📦 Attempting webdriver-manager download...")
    if download_fresh_chromedriver():
        print("✅ ChromeDriver fixed successfully!")
        return True
    
    # Step 3: Try manual download
    print("\n🔄 Attempting manual download...")
    if download_manual_chromedriver():
        print("✅ ChromeDriver fixed with manual download!")
        return True
    
    print("\n❌ All ChromeDriver download methods failed")
    print("💡 Try running: pip install --upgrade webdriver-manager")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

