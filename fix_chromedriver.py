#!/usr/bin/env python3
"""
ChromeDriver Architecture Fix
============================

Fixes the ChromeDriver architecture issue on Windows by downloading
the correct win64 version instead of win32.
"""

import os
import sys
import platform
import requests
import zipfile
import shutil
from pathlib import Path

def get_chrome_version():
    """Get installed Chrome version"""
    try:
        if platform.system() == 'Windows':
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
            version, _ = winreg.QueryValueEx(key, "version")
            return version
        else:
            # Linux/Mac - try to get version from chrome binary
            import subprocess
            result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split()[-1]
    except Exception as e:
        print(f"⚠️ Could not detect Chrome version: {e}")
        return None

def download_chromedriver(version=None):
    """Download correct ChromeDriver for Windows"""
    if platform.system() != 'Windows':
        print("❌ This script is for Windows only")
        return False
    
    if not version:
        version = get_chrome_version()
        if not version:
            print("❌ Could not detect Chrome version")
            return False
    
    print(f"🔍 Chrome version detected: {version}")
    
    # Extract major version
    major_version = version.split('.')[0]
    print(f"📦 Major version: {major_version}")
    
    # Chrome for Testing API endpoint
    api_url = f"https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_{major_version}"
    
    try:
        print("🌐 Fetching latest ChromeDriver version...")
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            driver_version = response.text.strip()
            print(f"✅ Latest ChromeDriver version: {driver_version}")
        else:
            print(f"❌ API request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to fetch version: {e}")
        return False
    
    # Download URL for win64
    download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{driver_version}/win64/chromedriver-win64.zip"
    
    try:
        print("📥 Downloading ChromeDriver...")
        print(f"🔗 URL: {download_url}")
        
        response = requests.get(download_url, timeout=30)
        if response.status_code == 200:
            # Save to temporary file
            temp_zip = "chromedriver_temp.zip"
            with open(temp_zip, 'wb') as f:
                f.write(response.content)
            
            print("📦 Extracting ChromeDriver...")
            
            # Extract zip file
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # Find the chromedriver.exe in the extracted folder
            extracted_dir = f"chromedriver-win64"
            chromedriver_path = os.path.join(extracted_dir, "chromedriver.exe")
            
            if os.path.exists(chromedriver_path):
                # Move to current directory
                shutil.move(chromedriver_path, "chromedriver.exe")
                print("✅ ChromeDriver extracted successfully")
                
                # Clean up
                os.remove(temp_zip)
                if os.path.exists(extracted_dir):
                    shutil.rmtree(extracted_dir)
                
                # Verify the file
                if os.path.exists("chromedriver.exe"):
                    file_size = os.path.getsize("chromedriver.exe")
                    print(f"✅ ChromeDriver ready: {file_size} bytes")
                    return True
                else:
                    print("❌ ChromeDriver not found after extraction")
                    return False
            else:
                print("❌ ChromeDriver executable not found in extracted files")
                return False
        else:
            print(f"❌ Download failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def clear_webdriver_cache():
    """Clear WebDriver Manager cache"""
    try:
        cache_dir = os.path.expanduser("~/.wdm")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print("🗑️ Cleared WebDriver Manager cache")
            return True
    except Exception as e:
        print(f"⚠️ Could not clear cache: {e}")
    return False

def main():
    """Main function"""
    print("ChromeDriver Architecture Fix")
    print("=" * 40)
    
    if platform.system() != 'Windows':
        print("❌ This script is for Windows only")
        return False
    
    # Clear WebDriver Manager cache
    print("🧹 Clearing WebDriver Manager cache...")
    clear_webdriver_cache()
    
    # Download correct ChromeDriver
    print("📥 Downloading correct ChromeDriver...")
    success = download_chromedriver()
    
    if success:
        print("\n✅ ChromeDriver fix completed successfully!")
        print("🚀 You can now run your automation scripts")
        return True
    else:
        print("\n❌ ChromeDriver fix failed")
        print("💡 Try running as administrator or check your internet connection")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
