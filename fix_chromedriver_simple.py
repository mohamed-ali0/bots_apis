#!/usr/bin/env python3
"""
Simple ChromeDriver Fix for Windows
==================================

Downloads the correct win64 ChromeDriver to fix architecture issues.
"""

import os
import sys
import platform
import requests
import zipfile
import shutil

def main():
    """Download correct ChromeDriver for Windows"""
    print("ChromeDriver Architecture Fix")
    print("=" * 40)
    
    if platform.system() != 'Windows':
        print("ERROR: This script is for Windows only")
        return False
    
    # Clear WebDriver Manager cache
    try:
        cache_dir = os.path.expanduser("~/.wdm")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print("Cleared WebDriver Manager cache")
    except Exception as e:
        print(f"Warning: Could not clear cache: {e}")
    
    # Use a known working ChromeDriver version
    driver_version = "141.0.7390.54"
    download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{driver_version}/win64/chromedriver-win64.zip"
    
    try:
        print(f"Downloading ChromeDriver {driver_version}...")
        print(f"URL: {download_url}")
        
        response = requests.get(download_url, timeout=30)
        if response.status_code == 200:
            # Save to temporary file
            temp_zip = "chromedriver_temp.zip"
            with open(temp_zip, 'wb') as f:
                f.write(response.content)
            
            print("Extracting ChromeDriver...")
            
            # Extract zip file
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # Find the chromedriver.exe in the extracted folder
            extracted_dir = "chromedriver-win64"
            chromedriver_path = os.path.join(extracted_dir, "chromedriver.exe")
            
            if os.path.exists(chromedriver_path):
                # Move to current directory
                shutil.move(chromedriver_path, "chromedriver.exe")
                print("ChromeDriver extracted successfully")
                
                # Clean up
                os.remove(temp_zip)
                if os.path.exists(extracted_dir):
                    shutil.rmtree(extracted_dir)
                
                # Verify the file
                if os.path.exists("chromedriver.exe"):
                    file_size = os.path.getsize("chromedriver.exe")
                    print(f"ChromeDriver ready: {file_size} bytes")
                    return True
                else:
                    print("ERROR: ChromeDriver not found after extraction")
                    return False
            else:
                print("ERROR: ChromeDriver executable not found in extracted files")
                return False
        else:
            print(f"ERROR: Download failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: Download error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\nSUCCESS: ChromeDriver fix completed!")
        print("You can now run your automation scripts")
    else:
        print("\nERROR: ChromeDriver fix failed")
        print("Try running as administrator or check your internet connection")
    sys.exit(0 if success else 1)
