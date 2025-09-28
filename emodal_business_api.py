#!/usr/bin/env python3
"""
E-Modal Business Operations API
==============================

Flask API for E-Modal business operations with persistent browser sessions:
- Container data extraction and Excel download
- Session management for multiple operations
- Professional error handling
- Browser lifecycle management
"""

import os
import time
import tempfile
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from emodal_login_handler import EModalLoginHandler
from recaptcha_handler import RecaptchaHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global session storage
active_sessions = {}
session_timeout = 1800  # 30 minutes


@dataclass
class BrowserSession:
    """Browser session with E-Modal authentication"""
    session_id: str
    driver: webdriver.Chrome
    username: str
    created_at: datetime
    last_used: datetime
    keep_alive: bool = False
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if self.keep_alive:
            return False
        return (datetime.now() - self.last_used).seconds > session_timeout
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.now()


class EModalBusinessOperations:
    """Business operations handler for E-Modal platform"""
    
    def __init__(self, session: BrowserSession):
        self.session = session
        self.driver = session.driver
        self.wait = WebDriverWait(self.driver, 30)
    
    def navigate_to_containers(self) -> Dict[str, Any]:
        """Navigate to containers page"""
        try:
            containers_url = "https://ecp2.emodal.com/containers"
            print(f"📦 Navigating to containers page: {containers_url}")
            
            self.driver.get(containers_url)
            
            # Wait for page to load
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check if we're on the containers page
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            if "containers" in current_url.lower():
                print("✅ Successfully navigated to containers page")
                return {"success": True, "url": current_url, "title": page_title}
            else:
                return {"success": False, "error": f"Not on containers page. Current URL: {current_url}"}
                
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}
    
    def select_all_containers(self) -> Dict[str, Any]:
        """Select all containers using the master checkbox"""
        try:
            print("☑️ Looking for 'Select All' checkbox...")
            
            # Common selectors for "select all" checkbox
            select_all_selectors = [
                "//input[@type='checkbox' and contains(@class, 'select-all')]",
                "//input[@type='checkbox' and @id='selectAll']",
                "//input[@type='checkbox'][1]",  # First checkbox (often master)
                "//th//input[@type='checkbox']",  # Checkbox in table header
                "//thead//input[@type='checkbox']",  # Checkbox in table head
                ".select-all-checkbox",
                "input[data-select-all]"
            ]
            
            # Also look for containers to count them first
            try:
                container_rows = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'container-row') or td[contains(@class, 'container')]]")
                if not container_rows:
                    # Alternative: look for any table rows with data
                    container_rows = self.driver.find_elements(By.XPATH, "//tbody//tr[td]")
                
                container_count = len(container_rows)
                print(f"📊 Found {container_count} container rows on page")
            except Exception as e:
                print(f"⚠️ Could not count containers: {e}")
                container_count = 0
            
            select_all_checkbox = None
            used_selector = None
            
            # Try each selector
            for selector in select_all_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        # CSS selector
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element.is_displayed() and element.is_enabled():
                        select_all_checkbox = element
                        used_selector = selector
                        print(f"✅ Found select-all checkbox with: {selector}")
                        break
                        
                except Exception as e:
                    print(f"❌ Selector '{selector}' failed: {e}")
                    continue
            
            if not select_all_checkbox:
                # Fallback: look for any checkbox that might be the master
                try:
                    all_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                    print(f"🔍 Found {len(all_checkboxes)} total checkboxes on page")
                    
                    for i, checkbox in enumerate(all_checkboxes):
                        try:
                            checkbox_id = checkbox.get_attribute("id")
                            checkbox_class = checkbox.get_attribute("class")
                            checkbox_name = checkbox.get_attribute("name")
                            parent_element = checkbox.find_element(By.XPATH, "./..")
                            parent_tag = parent_element.tag_name
                            
                            print(f"  Checkbox {i+1}: id='{checkbox_id}', class='{checkbox_class}', name='{checkbox_name}', parent='{parent_tag}'")
                            
                            # Check if it's in table header (likely master checkbox)
                            if parent_tag in ['th', 'thead'] or 'select' in (checkbox_class or '').lower():
                                select_all_checkbox = checkbox
                                used_selector = f"checkbox_{i+1}_in_{parent_tag}"
                                print(f"✅ Using checkbox {i+1} as select-all (in {parent_tag})")
                                break
                                
                        except Exception as debug_e:
                            print(f"  Debug error for checkbox {i+1}: {debug_e}")
                            continue
                    
                except Exception as fallback_e:
                    print(f"❌ Fallback checkbox search failed: {fallback_e}")
            
            if not select_all_checkbox:
                return {"success": False, "error": "Could not find select-all checkbox"}
            
            # Click the select-all checkbox
            try:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", select_all_checkbox)
                time.sleep(1)
                
                # Check current state
                is_checked = select_all_checkbox.is_selected()
                print(f"📋 Select-all checkbox current state: {'checked' if is_checked else 'unchecked'}")
                
                # Click to select all
                select_all_checkbox.click()
                time.sleep(2)  # Wait for selection to process
                
                # Verify the click worked
                new_state = select_all_checkbox.is_selected()
                print(f"📋 Select-all checkbox new state: {'checked' if new_state else 'unchecked'}")
                
                # Count selected checkboxes to verify
                try:
                    selected_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' and @checked]")
                    selected_count = len(selected_checkboxes)
                    print(f"✅ {selected_count} checkboxes now selected")
                except:
                    selected_count = "unknown"
                
                return {
                    "success": True,
                    "selector_used": used_selector,
                    "containers_found": container_count,
                    "checkboxes_selected": selected_count,
                    "checkbox_state": "checked" if new_state else "unchecked"
                }
                
            except Exception as click_e:
                return {"success": False, "error": f"Failed to click select-all checkbox: {str(click_e)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Select all containers failed: {str(e)}"}
    
    def download_excel_file(self) -> Dict[str, Any]:
        """Download Excel file with container data"""
        try:
            print("📥 Looking for Excel download button...")
            
            # Common selectors for Excel download
            excel_selectors = [
                "//a[contains(@href, 'excel') or contains(@href, 'xlsx')]",
                "//button[contains(@class, 'excel') or contains(@title, 'excel')]",
                "//i[contains(@class, 'fa-file-excel')]/..",  # FontAwesome Excel icon
                "//i[contains(@class, 'excel-icon')]/..",
                "//a[contains(@title, 'Export') and contains(@title, 'Excel')]",
                "//button[contains(@title, 'Export') and contains(@title, 'Excel')]",
                "//a[@title='Export to Excel']",
                "//button[@title='Export to Excel']",
                ".btn-excel",
                ".export-excel",
                "[data-export='excel']",
                "[data-format='xlsx']"
            ]
            
            excel_button = None
            used_selector = None
            
            # Try each selector
            for selector in excel_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        # CSS selector
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element.is_displayed() and element.is_enabled():
                        excel_button = element
                        used_selector = selector
                        print(f"✅ Found Excel download button with: {selector}")
                        break
                        
                except Exception:
                    continue
            
            if not excel_button:
                # Fallback: look for buttons/links that might be export-related
                try:
                    export_candidates = self.driver.find_elements(By.XPATH, 
                        "//button[contains(text(), 'Export') or contains(text(), 'Download') or contains(text(), 'Excel')] | " +
                        "//a[contains(text(), 'Export') or contains(text(), 'Download') or contains(text(), 'Excel')]"
                    )
                    
                    print(f"🔍 Found {len(export_candidates)} potential export buttons")
                    
                    for i, candidate in enumerate(export_candidates):
                        try:
                            button_text = candidate.text.strip()
                            button_title = candidate.get_attribute("title") or ""
                            button_class = candidate.get_attribute("class") or ""
                            
                            print(f"  Button {i+1}: text='{button_text}', title='{button_title}', class='{button_class}'")
                            
                            if any(keyword in (button_text + button_title + button_class).lower() 
                                   for keyword in ['excel', 'xlsx', 'export', 'download']):
                                excel_button = candidate
                                used_selector = f"export_candidate_{i+1}"
                                print(f"✅ Using button {i+1} as Excel download")
                                break
                                
                        except Exception:
                            continue
                            
                except Exception as fallback_e:
                    print(f"❌ Fallback button search failed: {fallback_e}")
            
            if not excel_button:
                return {"success": False, "error": "Could not find Excel download button"}
            
            # Set up download directory - cross-platform compatible
            download_dir = tempfile.mkdtemp()
            
            # Configure Chrome to download to our temp directory - Linux-compatible
            chrome_options = Options()
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True,
                # Linux-specific download preferences
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Click the Excel download button
            try:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", excel_button)
                time.sleep(1)
                
                button_text = excel_button.text.strip()
                print(f"📥 Clicking Excel download button: '{button_text}'")
                
                excel_button.click()
                
                # Wait for download to complete
                print("⏳ Waiting for file download...")
                download_timeout = 30  # 30 seconds
                start_time = time.time()
                downloaded_file = None
                
                while (time.time() - start_time) < download_timeout:
                    # Check for downloaded files
                    files = [f for f in os.listdir(download_dir) if f.endswith(('.xlsx', '.xls', '.csv'))]
                    if files:
                        # Found a file - check if download is complete (not .crdownload)
                        complete_files = [f for f in files if not f.endswith('.crdownload')]
                        if complete_files:
                            downloaded_file = os.path.join(download_dir, complete_files[0])
                            break
                    
                    time.sleep(1)
                
                if downloaded_file:
                    file_size = os.path.getsize(downloaded_file)
                    print(f"✅ File downloaded: {os.path.basename(downloaded_file)} ({file_size} bytes)")
                    
                    return {
                        "success": True,
                        "file_path": downloaded_file,
                        "file_name": os.path.basename(downloaded_file),
                        "file_size": file_size,
                        "download_dir": download_dir,
                        "selector_used": used_selector
                    }
                else:
                    return {"success": False, "error": "Download timeout - file not found"}
                    
            except Exception as click_e:
                return {"success": False, "error": f"Failed to click download button: {str(click_e)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Excel download failed: {str(e)}"}


def create_browser_session(username: str, password: str, captcha_api_key: str, keep_alive: bool = False) -> BrowserSession:
    """Create a new authenticated browser session"""
    
    # Generate session ID
    session_id = f"session_{int(time.time())}_{hash(username)}"
    
    print(f"🌐 Creating browser session: {session_id}")
    
    # Use the existing login handler
    login_handler = EModalLoginHandler(captcha_api_key, use_vpn_profile=True)
    login_handler._setup_driver()
    
    # Perform login but don't close the browser
    try:
        # Check VPN
        vpn_result = login_handler._check_vpn_status()
        if not vpn_result.success:
            login_handler.driver.quit()
            raise Exception(f"VPN check failed: {vpn_result.error_message}")
        
        # Fill credentials
        cred_result = login_handler._fill_credentials(username, password)
        if not cred_result.success:
            login_handler.driver.quit()
            raise Exception(f"Credential error: {cred_result.error_message}")
        
        # Handle reCAPTCHA
        recaptcha_result = login_handler._handle_recaptcha()
        if not recaptcha_result.success:
            login_handler.driver.quit()
            raise Exception(f"reCAPTCHA error: {recaptcha_result.error_message}")
        
        # Find and click login button
        login_found, login_button = login_handler._locate_login_button()
        if not login_found:
            login_handler.driver.quit()
            raise Exception(f"Login button error: {login_button}")
        
        click_result = login_handler._click_login_button(login_button)
        if not click_result.success:
            login_handler.driver.quit()
            raise Exception(f"Login click error: {click_result.error_message}")
        
        # Handle post-login alerts
        login_handler._handle_post_login_alerts()
        
        # Wait for login to complete
        time.sleep(3)
        
        # Verify we're logged in
        current_url = login_handler.driver.current_url
        if "signin-oidc" in current_url or "ecp2.emodal.com" in current_url:
            print(f"✅ Session {session_id} authenticated successfully")
            
            # Create session object (don't quit the driver!)
            session = BrowserSession(
                session_id=session_id,
                driver=login_handler.driver,
                username=username,
                created_at=datetime.now(),
                last_used=datetime.now(),
                keep_alive=keep_alive
            )
            
            return session
        else:
            login_handler.driver.quit()
            raise Exception(f"Login verification failed. URL: {current_url}")
            
    except Exception as e:
        if login_handler.driver:
            login_handler.driver.quit()
        raise e


def cleanup_expired_sessions():
    """Clean up expired browser sessions"""
    expired_sessions = []
    
    for session_id, session in active_sessions.items():
        if session.is_expired():
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        session = active_sessions[session_id]
        try:
            session.driver.quit()
            print(f"🔒 Cleaned up expired session: {session_id}")
        except:
            pass
        del active_sessions[session_id]


# API Routes

@app.route('/health', methods=['GET'])
def health_check():
    """Health check with session info"""
    cleanup_expired_sessions()
    
    return jsonify({
        "status": "healthy",
        "service": "E-Modal Business Operations API",
        "version": "1.0.0",
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/get_containers', methods=['POST'])
def get_containers():
    """
    Get containers data as Excel download
    
    Expected JSON:
    {
        "username": "your_username",
        "password": "your_password", 
        "captcha_api_key": "your_2captcha_key",
        "keep_browser_alive": true/false
    }
    
    Returns Excel file with container data
    """
    
    request_id = f"containers_{int(time.time())}"
    
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400
        
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        captcha_api_key = data.get('captcha_api_key')
        keep_alive = data.get('keep_browser_alive', False)
        
        if not all([username, password, captcha_api_key]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: username, password, captcha_api_key"
            }), 400
        
        logger.info(f"[{request_id}] Container request for user: {username}")
        logger.info(f"[{request_id}] Keep alive: {keep_alive}")
        
        # Create authenticated session
        try:
            session = create_browser_session(username, password, captcha_api_key, keep_alive)
            
            if keep_alive:
                active_sessions[session.session_id] = session
                logger.info(f"[{request_id}] Session stored for reuse: {session.session_id}")
            
        except Exception as login_error:
            logger.error(f"[{request_id}] Login failed: {str(login_error)}")
            return jsonify({
                "success": False,
                "error": f"Authentication failed: {str(login_error)}"
            }), 401
        
        # Perform business operations
        try:
            operations = EModalBusinessOperations(session)
            
            # Step 1: Navigate to containers
            nav_result = operations.navigate_to_containers()
            if not nav_result["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error']}"
                }), 500
            
            # Step 2: Select all containers
            select_result = operations.select_all_containers()
            if not select_result["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Container selection failed: {select_result['error']}"
                }), 500
            
            # Step 3: Download Excel file
            download_result = operations.download_excel_file()
            if not download_result["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Download failed: {download_result['error']}"
                }), 500
            
            # Success - return file
            file_path = download_result["file_path"]
            file_name = download_result["file_name"]
            
            logger.info(f"[{request_id}] Success! File: {file_name}")
            
            # If not keeping alive, close browser
            if not keep_alive:
                session.driver.quit()
                logger.info(f"[{request_id}] Browser session closed")
            else:
                session.update_last_used()
                logger.info(f"[{request_id}] Browser session kept alive: {session.session_id}")
            
            # Send file as response
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f"containers_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as operation_error:
            logger.error(f"[{request_id}] Operation failed: {str(operation_error)}")
            if not keep_alive:
                try:
                    session.driver.quit()
                except:
                    pass
            return jsonify({
                "success": False,
                "error": f"Operation failed: {str(operation_error)}"
            }), 500
            
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), 500


@app.route('/sessions', methods=['GET'])
def list_sessions():
    """List active browser sessions"""
    cleanup_expired_sessions()
    
    sessions_info = []
    for session_id, session in active_sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "username": session.username,
            "created_at": session.created_at.isoformat(),
            "last_used": session.last_used.isoformat(),
            "keep_alive": session.keep_alive,
            "current_url": session.driver.current_url if session.driver else "unknown"
        })
    
    return jsonify({
        "active_sessions": len(sessions_info),
        "sessions": sessions_info
    })


@app.route('/sessions/<session_id>', methods=['DELETE'])
def close_session(session_id):
    """Close a specific browser session"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        try:
            session.driver.quit()
            del active_sessions[session_id]
            return jsonify({"success": True, "message": f"Session {session_id} closed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    else:
        return jsonify({"success": False, "error": "Session not found"}), 404


if __name__ == '__main__':
    print("🚀 E-Modal Business Operations API")
    print("=" * 50)
    print("✅ Container data extraction")
    print("✅ Excel file downloads")
    print("✅ Browser session management")
    print("✅ Persistent authentication")
    print("=" * 50)
    print("📍 Endpoints:")
    print("  POST /get_containers - Extract and download container data")
    print("  GET /sessions - List active browser sessions")
    print("  DELETE /sessions/<id> - Close specific session")
    print("  GET /health - Health check")
    print("=" * 50)
    print("🔗 Starting server on http://localhost:5000")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )

