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
import shutil
from PIL import Image, ImageDraw, ImageFont
import zipfile

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
session_timeout = 1800  # 30 minutes (not used for keep-alive sessions)
MAX_CONCURRENT_SESSIONS = 10  # Maximum Chrome windows allowed

# Persistent sessions with keep-alive and credential mapping
persistent_sessions = {}  # Maps credentials hash to session_id
session_refresh_interval = 300  # 5 minutes - refresh session to keep it alive

# Appointment sessions with extended timeout for multi-phase operations
appointment_sessions = {}
appointment_session_timeout = 600  # 10 minutes for error recovery

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
SCREENSHOTS_DIR = os.path.join(os.getcwd(), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


@dataclass
class BrowserSession:
    """Browser session with E-Modal authentication"""
    session_id: str
    driver: webdriver.Chrome
    username: str
    created_at: datetime
    last_used: datetime
    keep_alive: bool = False
    credentials_hash: str = None  # Hash of username+password for matching
    last_refresh: datetime = None  # Last time session was refreshed
    in_use: bool = False  # Flag to prevent refresh during active operations
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if self.keep_alive:
            return False
        return (datetime.now() - self.last_used).seconds > session_timeout
    
    def needs_refresh(self) -> bool:
        """Check if session needs to be refreshed"""
        if not self.keep_alive:
            return False
        if self.in_use:  # Don't refresh while operation is running
            return False
        if self.last_refresh is None:
            return True
        return (datetime.now() - self.last_refresh).seconds > session_refresh_interval
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.now()
    
    def update_last_refresh(self):
        """Update last refresh timestamp"""
        self.last_refresh = datetime.now()
    
    def mark_in_use(self):
        """Mark session as in use (operation running)"""
        self.in_use = True
        self.update_last_used()
    
    def mark_not_in_use(self):
        """Mark session as not in use (operation completed)"""
        self.in_use = False


@dataclass
class AppointmentSession:
    """Appointment session with current phase state"""
    session_id: str
    browser_session: BrowserSession
    current_phase: int  # 1, 2, or 3
    created_at: datetime
    last_used: datetime
    phase_data: dict  # Store data from each phase
    
    def is_expired(self) -> bool:
        """Check if appointment session has expired (10 minutes)"""
        return (datetime.now() - self.last_used).seconds > appointment_session_timeout
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.now()


def get_credentials_hash(username: str, password: str) -> str:
    """Generate a hash for credentials to use as a lookup key"""
    import hashlib
    return hashlib.sha256(f"{username}:{password}".encode()).hexdigest()


def find_session_by_credentials(username: str, password: str) -> Optional[BrowserSession]:
    """Find an existing keep-alive session matching the credentials"""
    cred_hash = get_credentials_hash(username, password)
    
    # Check persistent sessions map
    if cred_hash in persistent_sessions:
        session_id = persistent_sessions[cred_hash]
        if session_id in active_sessions:
            session = active_sessions[session_id]
            
            # Check if session is expired
            if session.is_expired():
                logger.info(f"Session {session_id} is expired, cleaning up...")
                del persistent_sessions[cred_hash]
                if session_id in active_sessions:
                    try:
                        active_sessions[session_id].driver.quit()
                    except:
                        pass
                    del active_sessions[session_id]
                return None
            
            # Check if session is still alive
            if not is_session_alive(session):
                logger.warning(f"Session {session_id} is dead (browser crashed), cleaning up...")
                del persistent_sessions[cred_hash]
                if session_id in active_sessions:
                    del active_sessions[session_id]
                return None
            
            # Session is valid and alive
            if session.keep_alive:
                logger.info(f"Found existing persistent session: {session_id} for user: {username}")
                return session
            else:
                # Not a keep-alive session, clean up
                del persistent_sessions[cred_hash]
                if session_id in active_sessions:
                    try:
                        active_sessions[session_id].driver.quit()
                    except:
                        pass
                    del active_sessions[session_id]
    
    return None


def get_lru_session() -> Optional[BrowserSession]:
    """Get the Least Recently Used session for eviction"""
    if not active_sessions:
        return None
    
    # Find session with oldest last_used timestamp
    lru_session = None
    oldest_time = None
    
    for session_id, session in active_sessions.items():
        if oldest_time is None or session.last_used < oldest_time:
            oldest_time = session.last_used
            lru_session = session
    
    return lru_session


def evict_lru_session() -> bool:
    """
    Evict the Least Recently Used session to make room for a new one.
    Returns True if a session was evicted, False otherwise.
    """
    lru_session = get_lru_session()
    
    if not lru_session:
        logger.warning("No LRU session found for eviction")
        return False
    
    try:
        logger.info(f"🗑️ Evicting LRU session: {lru_session.session_id} (user: {lru_session.username}, last_used: {lru_session.last_used})")
        
        # Close the browser
        try:
            lru_session.driver.quit()
            logger.info(f"  ✅ Browser closed for session: {lru_session.session_id}")
        except Exception as e:
            logger.warning(f"  ⚠️ Error closing browser: {e}")
        
        # Remove from persistent_sessions mapping
        if lru_session.credentials_hash and lru_session.credentials_hash in persistent_sessions:
            del persistent_sessions[lru_session.credentials_hash]
            logger.info(f"  ✅ Removed from persistent_sessions")
        
        # Remove from active_sessions
        if lru_session.session_id in active_sessions:
            del active_sessions[lru_session.session_id]
            logger.info(f"  ✅ Removed from active_sessions")
        
        logger.info(f"✅ LRU session evicted successfully. Active sessions: {len(active_sessions)}/{MAX_CONCURRENT_SESSIONS}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error evicting LRU session: {e}")
        return False


def ensure_session_capacity() -> bool:
    """
    Ensure there's capacity for a new session.
    If at limit (10 sessions), evict LRU session.
    Returns True if capacity is available, False otherwise.
    """
    current_count = len(active_sessions)
    
    if current_count < MAX_CONCURRENT_SESSIONS:
        logger.info(f"✅ Session capacity available: {current_count}/{MAX_CONCURRENT_SESSIONS}")
        return True
    
    logger.warning(f"⚠️ Session limit reached: {current_count}/{MAX_CONCURRENT_SESSIONS}. Evicting LRU session...")
    return evict_lru_session()


def kill_orphaned_chrome_processes():
    """
    Kill all Chrome and ChromeDriver processes that are not associated with active sessions.
    This helps clean up zombie processes that may be consuming resources.
    """
    import psutil
    
    try:
        # Get PIDs of active session drivers
        active_pids = set()
        for session_id, session in active_sessions.items():
            try:
                if hasattr(session.driver, 'service') and hasattr(session.driver.service, 'process'):
                    active_pids.add(session.driver.service.process.pid)
                    logger.debug(f"Active session {session_id} ChromeDriver PID: {session.driver.service.process.pid}")
            except Exception as e:
                logger.debug(f"Could not get PID for session {session_id}: {e}")
        
        logger.info(f"Active ChromeDriver PIDs: {active_pids}")
        
        # Find and kill orphaned processes
        killed_count = 0
        
        # Kill orphaned ChromeDriver processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chromedriver' in proc.info['name'].lower():
                    pid = proc.info['pid']
                    if pid not in active_pids:
                        logger.info(f"Killing orphaned ChromeDriver process: PID {pid}")
                        proc.kill()
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Kill orphaned Chrome processes (those without a parent ChromeDriver)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'chrome' in proc.info['name'].lower() and 'chromedriver' not in proc.info['name'].lower():
                    # Check if this Chrome process has --test-type flag (managed by ChromeDriver)
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and '--test-type' in ' '.join(cmdline):
                        # Check if its parent ChromeDriver is in active PIDs
                        try:
                            parent = proc.parent()
                            if parent and 'chromedriver' in parent.name().lower():
                                if parent.pid not in active_pids:
                                    logger.info(f"Killing orphaned Chrome process: PID {proc.info['pid']}")
                                    proc.kill()
                                    killed_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if killed_count > 0:
            logger.info(f"✅ Killed {killed_count} orphaned Chrome/ChromeDriver processes")
        else:
            logger.info("✅ No orphaned processes found")
        
        return killed_count
        
    except Exception as e:
        logger.error(f"Error killing orphaned processes: {e}")
        return 0


def kill_all_chrome_instances():
    """
    Emergency recovery: Kill ALL Chrome and ChromeDriver processes.
    Use this as a last resort when session recovery fails.
    WARNING: This will close all Chrome browsers, not just those managed by this API.
    """
    import psutil
    
    try:
        logger.warning("🚨 EMERGENCY RECOVERY: Killing ALL Chrome instances")
        
        killed_count = 0
        
        # Kill all ChromeDriver processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chromedriver' in proc.info['name'].lower():
                    logger.info(f"Killing ChromeDriver process: PID {proc.info['pid']}")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Kill all Chrome processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    logger.info(f"Killing Chrome process: PID {proc.info['pid']}")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        logger.warning(f"🚨 Emergency recovery killed {killed_count} processes")
        
        # Clear all active sessions
        active_sessions.clear()
        persistent_sessions.clear()
        logger.info("🗑️ Cleared all session data")
        
        return killed_count
        
    except Exception as e:
        logger.error(f"Error in emergency recovery: {e}")
        return 0


def is_session_alive(session: BrowserSession) -> bool:
    """
    Check if a browser session is still alive and responsive.
    
    Args:
        session: BrowserSession to check
    
    Returns:
        True if session is alive, False otherwise
    """
    try:
        # Try to get current URL as a health check
        _ = session.driver.current_url
        return True
    except Exception as e:
        logger.warning(f"Session {session.session_id} appears dead: {e}")
        
        # Check if this is a connection error
        error_str = str(e).lower()
        if 'connection' in error_str or 'winerror 10061' in error_str or 'newconnectionerror' in error_str:
            logger.warning("🔧 Connection error detected - attempting to clean up orphaned processes")
            # Try to kill orphaned processes
            try:
                kill_orphaned_chrome_processes()
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up orphaned processes: {cleanup_error}")
        
        return False


def get_or_create_browser_session(data: dict, request_id: str) -> tuple:
    """
    Get existing session by session_id OR create new persistent session.
    
    Args:
        data: Request JSON data
        request_id: Unique request identifier for logging
    
    Returns:
        Tuple of (driver, username, session_id, is_new_session) or (None, None, None, None) on error
        If error, also returns error response tuple (response, status_code)
    """
    session_id = data.get('session_id', None)
    
    # If session_id provided, try to use existing session
    if session_id:
        logger.info(f"[{request_id}] Using provided session_id: {session_id}")
        
        if session_id in active_sessions:
            browser_session = active_sessions[session_id]
            
            # Check if session is still alive
            if not is_session_alive(browser_session):
                logger.warning(f"[{request_id}] ⚠️ Session {session_id} is dead (browser closed or crashed)")
                logger.info(f"[{request_id}] Removing dead session and creating new one...")
                
                # Clean up dead session
                try:
                    del active_sessions[session_id]
                    # Remove from persistent sessions if present
                    if browser_session.credentials_hash in persistent_sessions:
                        del persistent_sessions[browser_session.credentials_hash]
                except:
                    pass
                
                # Fall through to create new session
            else:
                browser_session.update_last_used()
                browser_session.mark_in_use()  # Mark as in use to prevent refresh during operation
                logger.info(f"[{request_id}] ✅ Found existing session for user: {browser_session.username}")
                return (browser_session.driver, browser_session.username, session_id, False)
        else:
            logger.warning(f"[{request_id}] ⚠️ Session ID not found or expired: {session_id}")
            logger.info(f"[{request_id}] Creating new session instead...")
            # Fall through to create new session
    
    # Create new persistent session
    username = data.get('username')
    password = data.get('password')
    captcha_api_key = data.get('captcha_api_key')
    
    if not all([username, password, captcha_api_key]):
        error_response = jsonify({
            "success": False,
            "error": "Missing required fields: username, password, captcha_api_key (or valid session_id)"
        }), 400
        return (None, None, None, None, error_response)
    
    logger.info(f"[{request_id}] Creating new persistent session for user: {username}")
    
    # Check if session already exists for these credentials
    existing_session = find_session_by_credentials(username, password)
    
    if existing_session:
        existing_session.update_last_used()
        existing_session.mark_in_use()  # Mark as in use to prevent refresh during operation
        logger.info(f"[{request_id}] ✅ Found existing session for credentials: {existing_session.session_id}")
        return (existing_session.driver, existing_session.username, existing_session.session_id, False)
    
    # Ensure capacity (evict LRU if needed)
    if not ensure_session_capacity():
        error_response = jsonify({
            "success": False,
            "error": "Failed to allocate session capacity"
        }), 500
        return (None, None, None, None, error_response)
    
    # Create new session
    new_session_id = f"session_{int(time.time())}_{hash(username)}"
    cred_hash = get_credentials_hash(username, password)
    
    # Create unique temp profile directory for this session
    temp_profile_dir = tempfile.mkdtemp(prefix=f"emodal_session_{new_session_id}_")
    logger.info(f"[{request_id}] Created temp profile: {temp_profile_dir}")
    
    # Authenticate with unique profile
    handler = EModalLoginHandler(
        captcha_api_key=captcha_api_key,
        use_vpn_profile=False,  # Don't use default profile (causes conflicts)
        auto_close=False,  # Keep browser open for persistent session
        user_data_dir=temp_profile_dir
    )
    
    login_result = handler.login(username, password)
    if not login_result.success:
        # Login failed - offer manual intervention before cleanup
        print(f"\n⚠️ Authentication failed: {login_result.error_type if login_result.error_type else 'Unknown error'}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"❓ Do you want to complete login manually?")
        print(f"   Press ENTER within 10 seconds to complete manually...")
        print(f"   (Or wait 10 seconds to abort)")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Wait for user input with timeout
        import sys
        user_wants_manual = False
        try:
            # Windows-compatible timeout input
            if sys.platform == 'win32':
                import msvcrt
                import time as time_module
                start_time = time_module.time()
                while time_module.time() - start_time < 10:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\r':  # Enter key
                            user_wants_manual = True
                            break
                    time_module.sleep(0.1)
            else:
                # Unix-based systems
                import select
                ready, _, _ = select.select([sys.stdin], [], [], 10)
                if ready:
                    sys.stdin.readline()
                    user_wants_manual = True
        except Exception as input_error:
            print(f"⚠️ Input timeout error: {input_error}")
        
        if user_wants_manual and handler.driver:
            print(f"\n✅ Manual login mode activated!")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"📋 Instructions:")
            print(f"   1. Complete the login in the browser window")
            print(f"   2. Solve any reCAPTCHA or other challenges")
            print(f"   3. Wait until you see the eModal dashboard")
            print(f"   4. Press ENTER when done to continue...")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Wait indefinitely for user to press Enter
            try:
                input()  # This will wait until Enter is pressed
                print(f"✅ Continuing with session creation...")
                
                # Verify login after manual intervention
                try:
                    current_url = (handler.driver.current_url or "").lower()
                    current_title = (handler.driver.title or "")
                    
                    # Accept various eModal domains as valid login
                    valid_domains = ["ecp2.emodal.com", "account.emodal.com", "truckerportal.emodal.com"]
                    is_valid_url = any(domain in current_url for domain in valid_domains) and ("identity" not in current_url)
                    
                    if is_valid_url:
                        print(f"✅ Session authenticated successfully (manual recovery)")
                        
                        # Create browser session with keep_alive=True (persistent)
                        browser_session = BrowserSession(
                            session_id=new_session_id,
                            driver=handler.driver,
                            username=username,
                            created_at=datetime.now(),
                            last_used=datetime.now(),
                            keep_alive=True,  # All sessions are persistent by default
                            credentials_hash=cred_hash,
                            last_refresh=datetime.now()
                        )
                        
                        active_sessions[new_session_id] = browser_session
                        persistent_sessions[cred_hash] = new_session_id
                        
                        logger.info(f"[{request_id}] ✅ Session {new_session_id} created successfully (manual)")
                        browser_session.mark_in_use()  # Mark as in use
                        return (browser_session.driver, username, new_session_id, True)
                    else:
                        print(f"❌ Still not logged in after manual intervention")
                        print(f"   URL: {current_url}")
                        print(f"   Title: {current_title}")
                        # Clean up
                        try:
                            handler.driver.quit()
                            shutil.rmtree(temp_profile_dir, ignore_errors=True)
                        except:
                            pass
                        error_response = jsonify({
                            "success": False,
                            "error": "Manual login failed - not on eModal dashboard"
                        }), 401
                        return (None, None, None, None, error_response)
                        
                except Exception as verify_error:
                    print(f"⚠️ Verification error: {verify_error}")
                    # Clean up
                    try:
                        handler.driver.quit()
                        shutil.rmtree(temp_profile_dir, ignore_errors=True)
                    except:
                        pass
                    error_response = jsonify({
                        "success": False,
                        "error": f"Verification failed: {str(verify_error)}"
                    }), 401
                    return (None, None, None, None, error_response)
                    
            except Exception as input_error:
                print(f"⚠️ Input error: {input_error}")
                # Clean up
                try:
                    handler.driver.quit()
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
                except:
                    pass
                error_response = jsonify({
                    "success": False,
                    "error": f"Manual login interrupted: {str(input_error)}"
                }), 401
                return (None, None, None, None, error_response)
        else:
            # No manual intervention or timeout
            print(f"\n❌ No response within 10 seconds - aborting session")
            # Clean up temp profile on failure
            try:
                handler.driver.quit()
                shutil.rmtree(temp_profile_dir, ignore_errors=True)
            except:
                pass
            error_response = jsonify({
                "success": False,
                "error": "Authentication failed",
                "details": str(login_result.error_type) if login_result.error_type else "Unknown error"
            }), 401
            return (None, None, None, None, error_response)
    
    # Create browser session with keep_alive=True (persistent)
    browser_session = BrowserSession(
        session_id=new_session_id,
        driver=handler.driver,
        username=username,
        created_at=datetime.now(),
        last_used=datetime.now(),
        keep_alive=True,  # All sessions are persistent by default
        credentials_hash=cred_hash,
        last_refresh=datetime.now()
    )
    
    active_sessions[new_session_id] = browser_session
    persistent_sessions[cred_hash] = new_session_id
    
    browser_session.mark_in_use()  # Mark as in use to prevent refresh during operation
    
    logger.info(f"[{request_id}] ✅ Created new persistent session: {new_session_id} for user: {username}")
    logger.info(f"[{request_id}] 📊 Active sessions: {len(active_sessions)}/{MAX_CONCURRENT_SESSIONS}")
    
    return (handler.driver, username, new_session_id, True)


def refresh_session(session: BrowserSession) -> bool:
    """Refresh a session to keep it authenticated"""
    try:
        logger.info(f"Refreshing session: {session.session_id}")
        
        # Try to get current URL first
        try:
            current_url = session.driver.current_url
            logger.info(f"  Current URL: {current_url}")
        except:
            logger.warning(f"  Could not get current URL")
        
        # Navigate to containers page to verify session is still valid
        session.driver.get("https://termops.emodal.com/trucker/web/")
        time.sleep(3)  # Give page time to load
        
        # Check if we're still logged in (multiple ways to verify)
        try:
            # Try multiple selectors to verify logged in state
            logged_in = False
            
            # Method 1: Look for user button
            try:
                session.driver.find_element(By.XPATH, "//button[contains(@class,'user')]")
                logged_in = True
                logger.info(f"  ✅ Found user button")
            except:
                pass
            
            # Method 2: Look for mat-toolbar with user info
            if not logged_in:
                try:
                    session.driver.find_element(By.XPATH, "//mat-toolbar")
                    logged_in = True
                    logger.info(f"  ✅ Found mat-toolbar")
                except:
                    pass
            
            # Method 3: Check URL - if redirected to login, we're logged out
            if not logged_in:
                current_url = session.driver.current_url
                if 'login' not in current_url.lower():
                    logged_in = True
                    logger.info(f"  ✅ Not on login page")
            
            if logged_in:
                session.update_last_refresh()
                logger.info(f"✅ Session refreshed: {session.session_id}")
                return True
            else:
                logger.warning(f"Session appears to have been logged out: {session.session_id}")
                return False
        except Exception as check_error:
            logger.warning(f"Error checking login status: {check_error}")
            return False
    except Exception as e:
        logger.error(f"Error refreshing session {session.session_id}: {e}")
        return False


def periodic_session_refresh():
    """Background task to periodically refresh keep-alive sessions"""
    while True:
        try:
            time.sleep(60)  # Check every minute
            
            for session_id, session in list(active_sessions.items()):
                if session.keep_alive and session.needs_refresh():
                    if not refresh_session(session):
                        # Session is dead, clean it up
                        logger.warning(f"Removing dead session: {session_id}")
                        if session.credentials_hash and session.credentials_hash in persistent_sessions:
                            del persistent_sessions[session.credentials_hash]
                        try:
                            session.driver.quit()
                        except:
                            pass
                        del active_sessions[session_id]
        except Exception as e:
            logger.error(f"Error in periodic session refresh: {e}")


def cleanup_expired_appointment_sessions():
    """Clean up expired appointment sessions"""
    expired = []
    for session_id, appt_session in appointment_sessions.items():
        if appt_session.is_expired():
            expired.append(session_id)
    
    for session_id in expired:
        appt_session = appointment_sessions[session_id]
        try:
            appt_session.browser_session.driver.quit()
            print(f"🔒 Cleaned up expired appointment session: {session_id}")
        except:
            pass
        del appointment_sessions[session_id]


class EModalBusinessOperations:
    """Business operations handler for E-Modal platform"""
    
    def __init__(self, session: BrowserSession):
        self.session = session
        self.driver = session.driver
        self.wait = WebDriverWait(self.driver, 30)
        self.screens_enabled = False
        self.screens_label = ""
        self.screens: list[str] = []
        # Per-session screenshots folder
        self.screens_dir = os.path.join(SCREENSHOTS_DIR, self.session.session_id)
        try:
            os.makedirs(self.screens_dir, exist_ok=True)
        except Exception:
            pass
    
    def _wait_for_app_ready(self, timeout_seconds: int = 25) -> None:
        """Wait until SPA main app finishes initial loading."""
        end_time = time.time() + timeout_seconds
        last_err = None
        while time.time() < end_time:
            try:
                # 1) Document ready
                ready = self.driver.execute_script("return document.readyState") == 'complete'
                # 2) Angular/SPA stability (best-effort)
                try:
                    ng_stable = self.driver.execute_script(
                        "return window.getAllAngularTestabilities ? window.getAllAngularTestabilities().every(t => t.isStable()) : true;"
                    )
                except Exception:
                    ng_stable = True
                # 3) Core UI present
                ui_present = False
                try:
                    ui_present = (
                        len(self.driver.find_elements(By.CSS_SELECTOR, "app-root, router-outlet, mat-sidenav-container, main")) > 0
                    )
                except Exception:
                    ui_present = False
                if ready and ng_stable and ui_present:
                    return
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        if last_err:
            print(f"⚠️ App readiness wait ended with last error: {last_err}")

    def _capture_screenshot(self, tag: str):
        if not self.screens_enabled:
            print(f"📸 Screenshot skipped (disabled): {tag}")
            return None
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            raw_path = os.path.join(self.screens_dir, f"{ts}_{tag}.png")
            
            # Ensure browser window is visible, on top, and maximized to capture full browser including URL bar
            try:
                # First, bring window to front and ensure it's not minimized
                self.driver.switch_to.window(self.driver.current_window_handle)
                
                # Force browser window to be on top of all other windows
                try:
                    # Method 1: Use JavaScript to focus the window
                    self.driver.execute_script("window.focus();")
                    
                    # Method 2: Click on the browser window to bring it to front
                    self.driver.execute_script("window.click();")
                    
                    # Method 3: Use JavaScript to bring window to front
                    self.driver.execute_script("""
                        if (window.chrome && window.chrome.runtime) {
                            window.chrome.runtime.sendMessage({action: 'bringToFront'});
                        }
                    """)
                    
                except Exception as e:
                    print(f"⚠️ Could not bring window to front: {e}")
                
                # Try to restore window if it's minimized
                try:
                    self.driver.minimize_window()
                    time.sleep(0.2)
                    self.driver.maximize_window()
                except Exception:
                    # If minimize/maximize fails, just try to maximize
                    self.driver.maximize_window()
                
                time.sleep(0.5)  # Wait for window to maximize
                
                # Additional focus attempts after maximization
                try:
                    self.driver.execute_script("window.focus();")
                    # Click on a safe area of the page to ensure focus
                    self.driver.execute_script("document.body.click();")
                except Exception:
                    pass
                
                # Verify window is actually visible
                window_size = self.driver.get_window_size()
                if window_size['width'] < 800 or window_size['height'] < 600:
                    print(f"⚠️ Window size too small: {window_size}, trying to resize...")
                    self.driver.set_window_size(1920, 1080)
                    time.sleep(0.3)
                    
            except Exception as e:
                print(f"⚠️ Could not maximize window: {e}")
                # Try alternative approach
                try:
                    self.driver.set_window_size(1920, 1080)
                    self.driver.set_window_position(0, 0)
                except Exception as e2:
                    print(f"⚠️ Could not resize window: {e2}")
            
            # Capture full browser window including URL bar and browser chrome
            # Use get_screenshot_as_png() for better full window capture
            try:
                screenshot_png = self.driver.get_screenshot_as_png()
                with open(raw_path, 'wb') as f:
                    f.write(screenshot_png)
                print(f"📸 Full browser screenshot captured: {os.path.basename(raw_path)}")
            except Exception as e:
                print(f"⚠️ get_screenshot_as_png failed: {e}, trying save_screenshot...")
                # Fallback to save_screenshot
                self.driver.save_screenshot(raw_path)
                print(f"📸 Fallback screenshot saved: {os.path.basename(raw_path)}")
            
            print(f"📸 Full browser screenshot saved: {os.path.basename(raw_path)}")
            # Annotate top-right with label, timestamp, container number (if available), and URL
            try:
                img = Image.open(raw_path).convert("RGBA")
                draw = ImageDraw.Draw(img)
                url = self.driver.current_url or ""
                
                # Build annotation text with timestamp and container number if available
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                text_parts = [self.screens_label, timestamp]
                
                # Add container number if available
                if hasattr(self, 'current_container_id') and self.current_container_id:
                    text_parts.append(f"Container: {self.current_container_id}")
                
                # Add vm_email if available
                if hasattr(self, 'vm_email') and self.vm_email:
                    text_parts.append(f"Email: {self.vm_email}")
                
                # Use hardcoded platform name instead of URL
                text_parts.append("emodal")
                main_text = " | ".join(text_parts)
                
                # Background rectangle (bottom-right), label 100% larger
                padding = 12
                # Try a truetype font for better scaling
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", 24)
                except Exception:
                    try:
                        font = ImageFont.truetype("arial.ttf", 24)
                    except Exception:
                        font = ImageFont.load_default()
                
                # Calculate dimensions for single line text
                all_lines = [main_text]
                max_width = 0
                line_height = 30  # Space between lines
                
                for line in all_lines:
                    try:
                        bbox = draw.textbbox((0,0), line, font=font)
                        line_w = bbox[2]-bbox[0]
                    except Exception:
                        line_w = draw.textlength(line, font=font)
                    if line_w > max_width:
                        max_width = line_w
                
                box_w = max_width + padding * 2
                box_h = len(all_lines) * line_height + padding * 2
                x0 = img.width - box_w - 10
                y0 = img.height - box_h - 10
                
                # Draw background
                draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(0,0,0,180))
                
                # Draw each line
                current_y = y0 + padding
                for line in all_lines:
                    draw.text((x0 + padding, current_y), line, font=font, fill=(255,255,255,255))
                    current_y += line_height
                
                img.save(raw_path)
            except Exception:
                pass
            self.screens.append(raw_path)
            return raw_path  # Return the file path
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")
            return None

    def _extract_booking_number_from_image(self, screenshot_path: str) -> str:
        """
        Extract booking number from screenshot using image processing and OCR.
        
        Args:
            screenshot_path: Path to the screenshot image
            
        Returns:
            Booking number string or None if not found
        """
        try:
            print("  🔍 Processing image for booking number extraction...")
            
            # Check if screenshot path is valid
            if not screenshot_path or not os.path.exists(screenshot_path):
                print(f"  ❌ Invalid screenshot path: {screenshot_path}")
                return None
            
            # Check if Tesseract is available
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                print("  ✅ Tesseract OCR is available")
            except Exception as e:
                print(f"  ❌ Tesseract OCR not available: {e}")
                print("  💡 To enable image-based extraction, install Tesseract OCR:")
                print("     Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
                print("     Linux: sudo apt-get install tesseract-ocr")
                return None
            
            # Import required libraries
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np
            import cv2
            import re
            
            # Load the image
            image = Image.open(screenshot_path)
            img_array = np.array(image)
            
            print(f"  📸 Image loaded: {image.size[0]}x{image.size[1]} pixels")
            
            # Convert to OpenCV format (BGR)
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Method 1: Look for "Booking" text using template matching
            booking_number = self._find_booking_number_near_text(img_cv, "Booking")
            if booking_number:
                print(f"  ✅ Found booking number near 'Booking' text: {booking_number}")
                return booking_number
            
            # Method 2: Look for "Booking #" text
            booking_number = self._find_booking_number_near_text(img_cv, "Booking #")
            if booking_number:
                print(f"  ✅ Found booking number near 'Booking #' text: {booking_number}")
                return booking_number
            
            # Method 3: Look for blue text (booking numbers are often blue)
            booking_number = self._find_blue_text_booking_number(img_cv)
            if booking_number:
                print(f"  ✅ Found booking number in blue text: {booking_number}")
                return booking_number
            
            # Method 4: OCR the entire image and look for booking number pattern
            booking_number = self._ocr_booking_number(img_cv)
            if booking_number:
                print(f"  ✅ Found booking number via OCR: {booking_number}")
                return booking_number
            
            print("  ℹ️ No booking number found in image")
            return None
            
        except Exception as e:
            print(f"  ❌ Image processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_booking_number_near_text(self, img_cv, search_text: str) -> str:
        """Find booking number near specific text using template matching"""
        try:
            import cv2
            import pytesseract
            import re
            
            # Use OCR to find text locations
            data = pytesseract.image_to_data(img_cv, output_type=pytesseract.Output.DICT)
            
            # Find the search text
            text_found = False
            search_x, search_y, search_w, search_h = 0, 0, 0, 0
            
            for i, text in enumerate(data['text']):
                if search_text.lower() in text.lower():
                    text_found = True
                    search_x = data['left'][i]
                    search_y = data['top'][i]
                    search_w = data['width'][i]
                    search_h = data['height'][i]
                    print(f"  🔍 Found '{search_text}' at ({search_x}, {search_y})")
                    break
            
            if not text_found:
                return None
            
            # Define search area around the found text (extend to the right and below)
            margin = 50
            search_area_x1 = max(0, search_x - margin)
            search_area_y1 = max(0, search_y - margin)
            search_area_x2 = min(img_cv.shape[1], search_x + search_w + 300)  # Extend right for booking number
            search_area_y2 = min(img_cv.shape[0], search_y + search_h + 100)  # Extend down
            
            # Crop the search area
            search_area = img_cv[search_area_y1:search_area_y2, search_area_x1:search_area_x2]
            
            # Save cropped area for debugging
            cropped_path = os.path.join(self.screens_dir, f"booking_search_area_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            cv2.imwrite(cropped_path, search_area)
            print(f"  📸 Saved search area: {os.path.basename(cropped_path)}")
            
            # OCR the search area
            search_text_result = pytesseract.image_to_string(search_area, config='--psm 6')
            print(f"  📋 OCR text in search area: '{search_text_result.strip()}'")
            
            # Look for booking number pattern (letters and numbers, typically 8-12 characters)
            booking_patterns = [
                r'[A-Z]{2,4}[A-Z0-9]{6,10}',  # Pattern like RICFEM857500
                r'[A-Z0-9]{8,12}',            # General alphanumeric
                r'[A-Z]{3,6}[0-9]{4,8}',      # Letters followed by numbers
            ]
            
            for pattern in booking_patterns:
                matches = re.findall(pattern, search_text_result)
                for match in matches:
                    if len(match) >= 8:  # Booking numbers are usually at least 8 characters
                        print(f"  🎯 Found potential booking number: {match}")
                        return match
            
            return None
            
        except Exception as e:
            print(f"  ❌ Error in _find_booking_number_near_text: {e}")
            return None

    def _find_blue_text_booking_number(self, img_cv) -> str:
        """Find booking number by looking for blue text"""
        try:
            import cv2
            import pytesseract
            import re
            import numpy as np
            
            # Convert to HSV for better color detection
            hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
            
            # Define blue color range
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            
            # Create mask for blue regions
            blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # Apply mask to original image
            blue_regions = cv2.bitwise_and(img_cv, img_cv, mask=blue_mask)
            
            # Save blue regions for debugging
            blue_path = os.path.join(self.screens_dir, f"blue_regions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            cv2.imwrite(blue_path, blue_regions)
            print(f"  📸 Saved blue regions: {os.path.basename(blue_path)}")
            
            # OCR blue regions
            blue_text = pytesseract.image_to_string(blue_regions, config='--psm 6')
            print(f"  📋 Blue text OCR: '{blue_text.strip()}'")
            
            # Look for booking number pattern in blue text
            booking_patterns = [
                r'[A-Z]{2,4}[A-Z0-9]{6,10}',  # Pattern like RICFEM857500
                r'[A-Z0-9]{8,12}',            # General alphanumeric
                r'[A-Z]{3,6}[0-9]{4,8}',      # Letters followed by numbers
            ]
            
            for pattern in booking_patterns:
                matches = re.findall(pattern, blue_text)
                for match in matches:
                    if len(match) >= 8:  # Booking numbers are usually at least 8 characters
                        print(f"  🎯 Found potential blue booking number: {match}")
                        return match
            
            return None
            
        except Exception as e:
            print(f"  ❌ Error in _find_blue_text_booking_number: {e}")
            return None

    def _ocr_booking_number(self, img_cv) -> str:
        """Use OCR to find booking number pattern in the entire image"""
        try:
            import pytesseract
            import re
            
            # OCR the entire image
            full_text = pytesseract.image_to_string(img_cv, config='--psm 6')
            print(f"  📋 Full OCR text: '{full_text[:200]}...'")
            
            # Look for booking number patterns
            booking_patterns = [
                r'[A-Z]{2,4}[A-Z0-9]{6,10}',  # Pattern like RICFEM857500
                r'[A-Z0-9]{8,12}',            # General alphanumeric
                r'[A-Z]{3,6}[0-9]{4,8}',      # Letters followed by numbers
            ]
            
            for pattern in booking_patterns:
                matches = re.findall(pattern, full_text)
                for match in matches:
                    if len(match) >= 8:  # Booking numbers are usually at least 8 characters
                        print(f"  🎯 Found potential OCR booking number: {match}")
                        return match
            
            return None
            
        except Exception as e:
            print(f"  ❌ Error in _ocr_booking_number: {e}")
            return None

    def ensure_app_context(self, max_wait_seconds: int = 45) -> Dict[str, Any]:
        """Ensure we are in authenticated app context (not Identity/forbidden) and app is fully loaded."""
        end_time = time.time() + max_wait_seconds
        while time.time() < end_time:
            try:
                # Always switch to latest window
                try:
                    handles = self.driver.window_handles
                    if handles:
                        self.driver.switch_to.window(handles[-1])
                except Exception:
                    pass

                url = (self.driver.current_url or "").lower()
                title = (self.driver.title or "")

                # If Identity or forbidden, load the app root and wait again
                if ("identity" in url) or ("signin-oidc" in url) or ("forbidden" in url) or ("forbidden" in title.lower()):
                    try:
                        self.driver.get("https://ecp2.emodal.com/")
                        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        self._wait_for_app_ready(30)
                        self._capture_screenshot("app_root")
                        # Loop to re-evaluate
                        time.sleep(0.5)
                        continue
                    except Exception:
                        pass

                # If on app domain and not forbidden/identity, and app ready, we are good
                if ("ecp2.emodal.com" in url) and ("identity" not in url) and ("forbidden" not in url):
                    try:
                        self._wait_for_app_ready(20)
                    except Exception:
                        pass
                    self._capture_screenshot("app_ready")
                    return {"success": True, "url": self.driver.current_url, "title": self.driver.title}
            except Exception as e:
                last = str(e)
            time.sleep(0.5)
        return {"success": False, "error": "App context not ready in time"}
    
    def navigate_to_containers(self) -> Dict[str, Any]:
        """Navigate to containers page"""
        try:
            # Switch to the most recent window (OIDC sometimes opens a new one)
            try:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[-1])
            except Exception:
                pass

            # If we’re on Identity page, first load the app root to refresh session
            try:
                url0 = (self.driver.current_url or "").lower()
                title0 = (self.driver.title or "").lower()
            except Exception:
                url0, title0 = "", ""
            if ("identity" in url0) or ("signin-oidc" in url0) or ("identity" in title0):
                try:
                    self.driver.get("https://ecp2.emodal.com/")
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    # Ensure app readiness before containers route
                    self._wait_for_app_ready(25)
                    self._capture_screenshot("welcome")
                    # Switch to newest again
                    handles = self.driver.window_handles
                    if handles:
                        self.driver.switch_to.window(handles[-1])
                except Exception:
                    pass

            # Handle Welcome page or first-run prompts by clicking a primary action
            try:
                # Common primary action candidates
                primary_xpaths = [
                    "//button[normalize-space()='Continue']",
                    "//button[normalize-space()='Proceed']",
                    "//button[normalize-space()='OK']",
                    "//button[normalize-space()='Got it']",
                    "//button[contains(., 'Continue')]",
                    "//button[contains(., 'Proceed')]",
                    "//button[contains(., 'OK')]",
                    "//button[contains(., 'Got it')]",
                    "//a[normalize-space()='Continue']",
                    "//a[contains(., 'Continue')]",
                    "//span[normalize-space()='Continue']/ancestor::button",
                    "//span[normalize-space()='Proceed']/ancestor::button",
                ]
                for px in primary_xpaths:
                    try:
                        btn = self.driver.find_element(By.XPATH, px)
                        if btn and btn.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                            time.sleep(0.2)
                            try:
                                btn.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", btn)
                            # Wait for app to settle
                            self._wait_for_app_ready(20)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            variants = [
                "https://ecp2.emodal.com/containers",
                "https://ecp2.emodal.com/#/containers",
                "https://ecp2.emodal.com/app/containers"
            ]

            last_error = None
            for ix, url in enumerate(variants, start=1):
                print(f"📦 Navigating to containers page (variant {ix}/{len(variants)}): {url}")
                try:
                    self.driver.get(url)
                except Exception as nav_e:
                    last_error = f"Navigation error: {nav_e}"
                    continue

                # Wait for basic load
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except Exception:
                    pass
                # Ensure SPA finished booting (avoid calling before main loads)
                self._wait_for_app_ready(25)
                self._capture_screenshot("containers_attempt")

                # Switch again to newest window if one popped
                try:
                    handles = self.driver.window_handles
                    if handles:
                        self.driver.switch_to.window(handles[-1])
                except Exception:
                    pass

                current_url = self.driver.current_url or ""
                page_title = self.driver.title or ""
                print(f"  ➜ Current URL: {current_url}")
                print(f"  ➜ Page title: {page_title}")

                if "containers" in current_url.lower():
                    print("✅ Successfully navigated to containers page")
                    self._capture_screenshot("containers")
                    return {"success": True, "url": current_url, "title": page_title}

                # Fallback: click Containers menu/link
                menu_xpaths = [
                    "//a[normalize-space(.)='Containers']",
                    "//a[contains(., 'Containers')]",
                    "//button[normalize-space(.)='Containers']",
                    "//span[normalize-space(.)='Containers']/ancestor::a",
                    "//span[contains(., 'Containers')]/ancestor::button"
                ]
                for mx in menu_xpaths:
                    try:
                        link = self.driver.find_element(By.XPATH, mx)
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                        time.sleep(0.3)
                        try:
                            link.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", link)
                        # Wait and ensure app ready, then reevaluate
                        self._wait_for_app_ready(20)
                        self._capture_screenshot("containers_menu_click")
                        current_url = (self.driver.current_url or "").lower()
                        if "containers" in current_url:
                            print("✅ Reached containers via menu link")
                            self._capture_screenshot("containers")
                            return {"success": True, "url": self.driver.current_url, "title": self.driver.title}
                    except Exception:
                        continue

                last_error = f"After navigating to {url}, ended on {current_url} ({page_title})"

            return {"success": False, "error": last_error or "Unknown navigation failure"}

        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}

    def load_all_containers_with_infinite_scroll(self, target_count: int = None, target_container_id: str = None) -> Dict[str, Any]:
        """
        Scroll through containers page to load content via infinite scrolling
        
        Args:
            target_count: Stop scrolling when this many containers are loaded (None = load all)
            target_container_id: Stop scrolling when this container ID is found (None = load all)
        
        Returns:
            Dict with success, total_containers, scroll_cycles, and optionally found_target_container
        """
        try:
            if target_count:
                print(f"📜 Starting scroll to load {target_count} containers...")
            elif target_container_id:
                print(f"📜 Starting scroll to find container: {target_container_id}...")
            else:
                print("📜 Starting infinite scroll to load all containers...")
            self._capture_screenshot("before_infinite_scroll")
            
            # Note: Removed window maximization to prevent fullscreen mode
            # Scrolling works without maximizing the window

            # If content is inside an iframe, switch into it
            try:
                frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                print(f"🖼️ Found {len(frames)} iframe(s)")
                switched = False
                for i, fr in enumerate(frames):
                    try:
                        self.driver.switch_to.frame(fr)
                        # Heuristics: look for containers table hints
                        hints = self.driver.find_elements(By.XPATH, "//*[contains(@class,'mat-table') or contains(@class,'table') or @role='table' or @role='grid']")
                        if hints:
                            print(f"  ✅ Switched to iframe {i} containing table-like content")
                            switched = True
                            break
                        # Not the right frame, go back and continue
                        self.driver.switch_to.default_content()
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                if not switched:
                    # stay in default content
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
            except Exception as e:
                print(f"  ⚠️ Iframe detection error: {e}")

            # Focus on the page and move mouse to center for better scrolling
            try:
                print("🎯 Focusing on page and positioning mouse...")
                self.driver.execute_script("window.focus();")
                # Move mouse to center of viewport
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                # Get viewport size
                viewport_width = self.driver.execute_script("return window.innerWidth;")
                viewport_height = self.driver.execute_script("return window.innerHeight;")
                center_x = viewport_width // 2
                center_y = viewport_height // 2
                print(f"  📐 Viewport: {viewport_width}x{viewport_height}, Center: ({center_x}, {center_y})")
                try:
                    # Reset pointer to (0,0) by moving to body first when supported
                    body_elem = self.driver.find_element(By.TAG_NAME, 'body')
                    actions.move_to_element_with_offset(body_elem, 1, 1).perform()
                except Exception:
                    pass
                actions.move_by_offset(center_x, center_y).perform()
                time.sleep(1)
            except Exception as e:
                print(f"  ⚠️ Mouse positioning failed: {e}")
            
            # Helper function to quickly find target container (if specified)
            def try_find_target_container():
                """Quick XPath search for target container (like timeline/booking does)"""
                if not target_container_id:
                    return False
                try:
                    el = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{target_container_id}')]")
                    if el and el.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.3)
                        print(f"✅ Target container {target_container_id} found on page!")
                        return True
                except Exception:
                    pass
                return False
            
            # PRE-SCROLL CHECK: Try to find target container before scrolling (FAST!)
            if target_container_id:
                print(f"🔍 Pre-scroll check: Looking for {target_container_id}...")
                if try_find_target_container():
                    print(f"  🎯 Container found BEFORE scrolling (fast path!)")
                    self._capture_screenshot("after_infinite_scroll")
                    # Count containers for return value
                    try:
                        searchres = self.driver.find_element(By.XPATH, "//div[@id='searchres']")
                        page_text = searchres.text
                        import re
                        lines = page_text.split('\n')
                        container_count = sum(1 for line in lines if re.search(r'\b[A-Z]{4}\d{6,7}[A-Z]?\b', line))
                    except:
                        container_count = 0
                    return {
                        "success": True,
                        "total_containers": container_count,
                        "scroll_cycles": 0,
                        "found_target_container": target_container_id,
                        "stopped_reason": f"Container {target_container_id} found (pre-scroll)",
                        "fast_path": True
                    }
            
            # Track previous content count
            previous_count = 0
            no_new_content_count = 0
            max_no_new_content_cycles = 3  # 15 seconds (5 sec per cycle)
            scroll_cycle = 0
            
            print("🔢 Starting container counting...")
            
            while no_new_content_count < max_no_new_content_cycles:
                scroll_cycle += 1
                print(f"🔄 Scroll cycle {scroll_cycle} (no new content: {no_new_content_count}/{max_no_new_content_cycles})")
                
                # Count current visible containers/rows
                try:
                    print("  🔍 Counting containers...")
                    # Look for various container row indicators
                    # Count actual container IDs (same logic as parser for accurate count)
                    try:
                        # Get text from the table
                        searchres = self.driver.find_element(By.XPATH, "//div[@id='searchres']")
                        page_text = searchres.text
                        
                        # Count lines that match container ID pattern (4 letters + 6-7 digits)
                        import re
                        lines = page_text.split('\n')
                        container_count = 0
                        for line in lines:
                            # Match container ID pattern in the line
                            if re.search(r'\b[A-Z]{4}\d{6,7}[A-Z]?\b', line):
                                container_count += 1
                        
                        current_count = container_count
                        print(f"  📊 Found {current_count} actual container IDs in text")
                        
                    except Exception as count_e:
                        print(f"  ⚠️ Error counting containers: {count_e}")
                        # Fallback to DOM counting
                        try:
                            elements = self.driver.find_elements(By.XPATH, "//tbody//tr")
                            current_count = len(elements)
                            print(f"  📊 Fallback DOM count: {current_count} rows")
                        except:
                            current_count = previous_count
                    
                except Exception as e:
                    print(f"  ⚠️ Error counting containers: {e}")
                    current_count = previous_count
                
                # EARLY EXIT: Check if target container is now visible (FAST PATH during scroll)
                if target_container_id and try_find_target_container():
                    print(f"  🎯 Target container found during scroll cycle {scroll_cycle} (early exit!)")
                    self._capture_screenshot("after_infinite_scroll")
                    return {
                        "success": True,
                        "total_containers": current_count,
                        "scroll_cycles": scroll_cycle,
                        "found_target_container": target_container_id,
                        "stopped_reason": f"Container {target_container_id} found (during scroll)",
                        "fast_path": True
                    }
                
                # Check if we got new content
                if current_count > previous_count:
                    print(f"  ✅ New content loaded! {previous_count} → {current_count} containers")
                    previous_count = current_count
                    no_new_content_count = 0
                else:
                    no_new_content_count += 1
                    print(f"  ⏳ No new content ({no_new_content_count}/{max_no_new_content_cycles})")
                
                # Check if we've reached target count
                if target_count and current_count >= target_count:
                    print(f"  🎯 Target count reached: {current_count} >= {target_count}")
                    self._capture_screenshot("after_infinite_scroll")
                    return {
                        "success": True,
                        "total_containers": current_count,
                        "scroll_cycles": scroll_cycle,
                        "stopped_reason": f"Target count {target_count} reached"
                    }
                
                # Scroll down with multiple methods (targeting scrollable container)
                print("  📜 Scrolling down...")
                try:
                    # TARGET THE EXACT SCROLLABLE CONTAINER
                    scroll_target = None
                    using_window = False
                    
                    # Priority 1: The EXACT element with id="searchres" and matinfinitescroll
                    try:
                        scroll_target = self.driver.find_element(By.ID, "searchres")
                        if scroll_target and scroll_target.is_displayed():
                            print(f"  🎯 Found #searchres (matinfinitescroll container)")
                        else:
                            scroll_target = None
                    except Exception:
                        scroll_target = None
                    
                    # Priority 2: Any element with matinfinitescroll attribute
                    if not scroll_target:
                        try:
                            scroll_target = self.driver.find_element(By.XPATH, "//*[@matinfinitescroll]")
                            if scroll_target and scroll_target.is_displayed():
                                print(f"  🎯 Found element with matinfinitescroll attribute")
                            else:
                                scroll_target = None
                        except Exception:
                            scroll_target = None
                    
                    # Priority 3: search-results class
                    if not scroll_target:
                        try:
                            scroll_target = self.driver.find_element(By.CLASS_NAME, "search-results")
                            if scroll_target and scroll_target.is_displayed():
                                print(f"  🎯 Found .search-results container")
                            else:
                                scroll_target = None
                        except Exception:
                            scroll_target = None
                    
                    # Fallback: Find any fixed-height scrollable div
                    if not scroll_target:
                        try:
                            js = """
                                var divs = document.querySelectorAll('div');
                                for (var i=0; i<divs.length; i++) {
                                    var el = divs[i];
                                    var style = window.getComputedStyle(el);
                                    if (el.scrollHeight > el.clientHeight + 10 && 
                                        style.overflowY !== 'hidden' &&
                                        style.height && style.height !== 'auto') {
                                        return el;
                                    }
                                }
                                return null;
                            """
                            el = self.driver.execute_script(js)
                            if el:
                                scroll_target = el
                                print("  🎯 Found fixed-height scrollable div")
                        except Exception as js_e:
                            print(f"  ⚠️ JS scroll detection failed: {js_e}")
                    
                    if not scroll_target:
                        using_window = True
                        print("  ⚠️ No scroll container found, using window (may not work!)")

                    from selenium.webdriver.common.keys import Keys
                    from selenium.webdriver.common.action_chains import ActionChains
                    actions = ActionChains(self.driver)

                    # Bring target into view and focus (without clicking to avoid expanding rows)
                    if not using_window:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", scroll_target)
                            time.sleep(0.3)
                            # Move mouse to scroll target but DON'T click (prevents accidental row expansion)
                            actions.move_to_element(scroll_target).perform()
                            # Focus without clicking - use JavaScript focus
                            try:
                                self.driver.execute_script("arguments[0].focus();", scroll_target)
                            except Exception:
                                pass
                        except Exception as foc_e:
                            print(f"  ⚠️ Could not focus scroll container: {foc_e}")

                    # HEADLESS-COMPATIBLE: Scroll the matinfinitescroll container
                    # This directive triggers on scroll events within its container
                    try:
                        if using_window:
                            print("  ⚠️ Using window scroll (not recommended for matinfinitescroll)")
                            # Window scrolling - multiple small increments
                            for i in range(3):
                                self.driver.execute_script("""
                                    window.scrollBy(0, 400);
                                    window.dispatchEvent(new Event('scroll', {bubbles: true}));
                                    window.dispatchEvent(new WheelEvent('wheel', {deltaY: 400, bubbles: true}));
                                """)
                                time.sleep(0.4)
                            self.driver.execute_script("""
                                window.scrollTo(0, document.body.scrollHeight);
                                window.dispatchEvent(new Event('scroll', {bubbles: true}));
                            """)
                            time.sleep(0.5)
                        else:
                            # Scroll the #searchres matinfinitescroll container
                            print("  ✅ Scrolling matinfinitescroll container")
                            # Multiple incremental scrolls with events
                            for i in range(3):
                                self.driver.execute_script("""
                                    var el = arguments[0];
                                    el.scrollTop = el.scrollTop + 300;
                                    el.dispatchEvent(new Event('scroll', {bubbles: true}));
                                    el.dispatchEvent(new WheelEvent('wheel', {deltaY: 300, bubbles: true}));
                                    void el.offsetHeight;
                                """, scroll_target)
                                time.sleep(0.35)
                            # Final: scroll to bottom of container
                            self.driver.execute_script("""
                                var el = arguments[0];
                                el.scrollTop = el.scrollHeight;
                                el.dispatchEvent(new Event('scroll', {bubbles: true}));
                                void el.offsetHeight;
                            """, scroll_target)
                            time.sleep(0.6)
                        print("  ✅ Scroll cycle completed")
                    except Exception as scroll_e:
                        print(f"  ⚠️ Scroll failed: {scroll_e}")

                    # Report current scroll info
                    try:
                        if using_window:
                            scroll_y = self.driver.execute_script("return window.pageYOffset;")
                            max_scroll = self.driver.execute_script("return document.body.scrollHeight - window.innerHeight;")
                        else:
                            scroll_y = self.driver.execute_script("return arguments[0].scrollTop;", scroll_target)
                            max_scroll = self.driver.execute_script("return arguments[0].scrollHeight - arguments[0].clientHeight;", scroll_target)
                        print(f"  📍 Scroll position: {int(scroll_y)}/{int(max_scroll)} (using {'window' if using_window else 'container'})")
                    except Exception as pos_e:
                        print(f"  ⚠️ Could not read scroll position: {pos_e}")
                    
                except Exception as e:
                    print(f"  ⚠️ Scroll error: {e}")
                
                # Short wait to allow DOM to update (optimized like timeline search)
                time.sleep(0.7)
            
            print(f"🏁 Infinite scroll completed. Total containers loaded: {previous_count}")
            print(f"📊 Final scroll cycles: {scroll_cycle}")
            self._capture_screenshot("after_infinite_scroll")
            
            return {
                "success": True, 
                "total_containers": previous_count,
                "scroll_cycles": scroll_cycle
            }
            
        except Exception as e:
            print(f"❌ Infinite scroll failed: {str(e)}")
            return {"success": False, "error": f"Infinite scroll failed: {str(e)}"}

    def navigate_to_appointment(self) -> Dict[str, Any]:
        """Navigate to the make appointment (add visit) page"""
        try:
            # Ensure latest window
            try:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[-1])
            except Exception:
                pass

            # Ensure app context is ready
            try:
                self._wait_for_app_ready(25)
            except Exception:
                pass

            # Use only the first variant
            url = "https://termops.emodal.com/trucker/web/addvisit"
            print(f"📅 Navigating to appointment page: {url}")
            
            try:
                self.driver.get(url)
            except Exception as nav_e:
                return {"success": False, "error": f"Navigation error: {nav_e}"}
            
            # Wait for body to be present
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception:
                pass
            
            # Screenshot before waiting
            self._capture_screenshot("appointment_before_wait")
            
            # Wait 30 seconds for page to fully load
            print("⏳ Waiting 30 seconds for appointment page to fully load...")
            time.sleep(30)
            print("✅ Page load wait complete")
            
            # Screenshot after waiting
            self._capture_screenshot("appointment_after_wait")
            
            current_url = self.driver.current_url or ""
            page_title = self.driver.title or ""
            print(f"  ➜ Current URL: {current_url}")
            print(f"  ➜ Page title: {page_title}")
            
            # Check if we're on the appointment page
            if "addvisit" in current_url.lower() or "add" in page_title.lower() or "appointment" in page_title.lower():
                print("✅ Appointment page loaded successfully")
                return {"success": True, "url": current_url, "title": page_title}
            else:
                return {"success": False, "error": f"Navigation ended on unexpected page: {current_url} ({page_title})"}
            
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}
    
    # ============================================================================
    # APPOINTMENT BOOKING METHODS (3 PHASES)
    # ============================================================================
    
    def fill_text_field(self, field_label: str, value: str) -> Dict[str, Any]:
        """
        Fill a regular text input field (like Equip Size).
        
        Args:
            field_label: Label of the field (e.g., "Equip Size")
            value: Value to type directly
        
        Returns:
            Dict with success status
        """
        try:
            print(f"📝 Filling '{field_label}' text field with '{value}'...")
            
            # Find the input field by label
            input_field = None
            try:
                # Try to find by label first
                input_field = self.driver.find_element(By.XPATH, f"//mat-label[contains(text(),'{field_label}')]/following-sibling::input[@matinput]")
            except:
                try:
                    # Try alternative: find by placeholder or aria-label
                    input_field = self.driver.find_element(By.XPATH, f"//input[@matinput and contains(@placeholder,'{field_label}')]")
                except:
                    try:
                        # Try to find any mat-input-element
                        inputs = self.driver.find_elements(By.XPATH, "//input[@matinput]")
                        if inputs:
                            input_field = inputs[0]  # Take first one if multiple
                    except:
                        pass
            
            if not input_field:
                return {"success": False, "error": f"Text field '{field_label}' not found"}
            
            # Clear and focus the field
            input_field.clear()
            input_field.click()
            time.sleep(0.5)
            
            print(f"  ✅ Found and focused {field_label} field")
            self._capture_screenshot(f"text_{field_label.lower().replace(' ', '_')}_focused")
            
            # Type the value directly
            input_field.send_keys(value)
            time.sleep(0.5)
            
            print(f"  📝 Typed '{value}' in {field_label} field")
            self._capture_screenshot(f"text_{field_label.lower().replace(' ', '_')}_filled")
            
            # Click blank area to confirm
            try:
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
            except:
                pass
            
            print(f"  ✅ Successfully filled {field_label} with '{value}'")
            return {"success": True, "selected": value, "direct_input": True}
            
        except Exception as e:
            print(f"  ❌ Error filling text field: {e}")
            return {"success": False, "error": str(e)}

    def fill_autocomplete_field(self, field_label: str, value: str, fallback_to_any: bool = False) -> Dict[str, Any]:
        """
        Fill an autocomplete input field (like Line or Equip Size).
        
        Args:
            field_label: Label of the field (e.g., "Line", "Equip Size")
            value: Value to type and search for
            fallback_to_any: If True and exact match fails, select any available option
        
        Returns:
            Dict with success status
        """
        try:
            print(f"🔤 Filling '{field_label}' autocomplete field with '{value}'...")
            
            # Find the input field by label
            input_field = None
            try:
                # Try to find by label first
                input_field = self.driver.find_element(By.XPATH, f"//mat-label[contains(text(),'{field_label}')]/following-sibling::input[@matinput]")
                print(f"  🔍 Found {field_label} field by label")
            except:
                try:
                    # Try alternative: find by placeholder or aria-label
                    input_field = self.driver.find_element(By.XPATH, f"//input[@matinput and contains(@placeholder,'{field_label}')]")
                    print(f"  🔍 Found {field_label} field by placeholder")
                except:
                    try:
                        # Try to find any mat-autocomplete-trigger input
                        inputs = self.driver.find_elements(By.XPATH, "//input[@matinput and contains(@class,'mat-autocomplete-trigger')]")
                        if inputs:
                            # For Equip Size, try to find the second input (after Line)
                            if field_label == "Equip Size" and len(inputs) > 1:
                                input_field = inputs[1]  # Second autocomplete field
                                print(f"  🔍 Found {field_label} field as second autocomplete input")
                            else:
                                input_field = inputs[0]  # First autocomplete field
                                print(f"  🔍 Found {field_label} field as first autocomplete input")
                    except:
                        pass
            
            if not input_field:
                return {"success": False, "error": f"Autocomplete field '{field_label}' not found"}
            
            # Clear and focus the field
            input_field.clear()
            input_field.click()
            time.sleep(1.0)  # Wait for autocomplete to open
            
            print(f"  ✅ Found and focused {field_label} field")
            self._capture_screenshot(f"autocomplete_{field_label.lower().replace(' ', '_')}_focused")
            
            # Get all available options from the expanded list
            print(f"  🔍 Getting available options from {field_label} autocomplete...")
            all_options = self.driver.find_elements(By.XPATH, "//mat-option//span")
            available_options = [opt.text.strip() for opt in all_options if opt.text.strip()]
            
            if available_options:
                print(f"  📋 Available options: {', '.join(available_options[:10])}")  # Show first 10
                if len(available_options) > 10:
                    print(f"  📋 ... and {len(available_options) - 10} more options")
            else:
                print(f"  ⚠️ No options found in autocomplete list")
                return {"success": False, "error": f"No options available in {field_label} autocomplete"}
            
            # Search for our value in the available options (exact match)
            print(f"  🔍 Searching for '{value}' in available options...")
            exact_match = None
            for option in all_options:
                if option.text.strip() == value:
                    exact_match = option
                    break
            
            if exact_match:
                # Found exact match - select it
                exact_match.click()
                time.sleep(0.5)
                print(f"  ✅ Exact match: Selected '{value}' from {field_label}")
                self._capture_screenshot(f"autocomplete_{field_label.lower().replace(' ', '_')}_exact")
                
                # Enter the selected value directly in the field
                input_field.clear()
                input_field.send_keys(value)
                time.sleep(0.5)
                print(f"  📝 Entered '{value}' directly in {field_label} field")
                
                # Click blank space to confirm
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    time.sleep(0.5)
                    print(f"  ✅ Confirmed {field_label} selection")
                except:
                    pass
                
                return {"success": True, "selected": value, "exact_match": True}
            
            # No exact match - try partial match
            print(f"  🔍 No exact match for '{value}', trying partial match...")
            partial_match = None
            for option in all_options:
                if value.lower() in option.text.strip().lower():
                    partial_match = option
                    break
            
            if partial_match:
                # Found partial match - select it
                partial_text = partial_match.text.strip()
                partial_match.click()
                time.sleep(0.5)
                print(f"  ✅ Partial match: Selected '{partial_text}' from {field_label}")
                self._capture_screenshot(f"autocomplete_{field_label.lower().replace(' ', '_')}_partial")
                
                # Enter the selected value directly in the field
                input_field.clear()
                input_field.send_keys(partial_text)
                time.sleep(0.5)
                print(f"  📝 Entered '{partial_text}' directly in {field_label} field")
                
                # Click blank space to confirm
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    time.sleep(0.5)
                    print(f"  ✅ Confirmed {field_label} selection")
                except:
                    pass
                
                return {"success": True, "selected": partial_text, "partial_match": True}
            
            # No match found - use fallback if enabled
            if fallback_to_any:
                print(f"  ⚠️ '{value}' not found, selecting any available option...")
                try:
                    # Select the first available option
                    fallback_option = all_options[0]
                    fallback_text = fallback_option.text.strip()
                    
                    fallback_option.click()
                    time.sleep(0.5)
                    
                    print(f"  ✅ Fallback: Selected '{fallback_text}' from {field_label}")
                    self._capture_screenshot(f"autocomplete_{field_label.lower().replace(' ', '_')}_fallback")
                    
                    # Enter the selected value directly in the field
                    input_field.clear()
                    input_field.send_keys(fallback_text)
                    time.sleep(0.5)
                    print(f"  📝 Entered '{fallback_text}' directly in {field_label} field")
                    
                    # Click blank space to confirm
                    try:
                        self.driver.find_element(By.TAG_NAME, "body").click()
                        time.sleep(0.5)
                        print(f"  ✅ Confirmed {field_label} selection")
                    except:
                        pass
                    
                    return {"success": True, "selected": fallback_text, "fallback": True}
                except Exception as fallback_error:
                    print(f"  ❌ Fallback selection failed: {fallback_error}")
                    return {"success": False, "error": f"Fallback selection failed: {str(fallback_error)}"}
            else:
                # No fallback enabled - but for Equip Size, we might need to handle dependency
                if field_label == "Equip Size":
                    print(f"  ⚠️ Equip Size '{value}' not found - this might be due to Line selection dependency")
                    print(f"  🔄 Trying to select any available option as fallback...")
                    
                    try:
                        # Try to select any available option
                        if all_options:
                            fallback_option = all_options[0]
                            fallback_text = fallback_option.text.strip()
                            
                            fallback_option.click()
                            time.sleep(0.5)
                            
                            print(f"  ✅ Dependency fallback: Selected '{fallback_text}' from {field_label}")
                            self._capture_screenshot(f"autocomplete_{field_label.lower().replace(' ', '_')}_dependency_fallback")
                            
                            return {"success": True, "selected": fallback_text, "dependency_fallback": True}
                        else:
                            print(f"  ❌ No options available after Line selection")
                            return {"success": False, "error": f"No Equip Size options available after Line selection"}
                    except Exception as dep_error:
                        print(f"  ❌ Dependency fallback failed: {dep_error}")
                        return {"success": False, "error": f"Equip Size dependency fallback failed: {str(dep_error)}"}
                else:
                    # No fallback enabled - return error
                    print(f"  ❌ '{value}' not found in available options")
                    return {"success": False, "error": f"'{value}' not found in {field_label} options. Available: {', '.join(available_options[:5])}"}
            
        except Exception as e:
            print(f"  ❌ Error filling autocomplete field: {e}")
            return {"success": False, "error": str(e)}

    def select_dropdown_by_text(self, dropdown_label: str, option_text: str, fallback_to_any: bool = False) -> Dict[str, Any]:
        """
        Select an option from a Material dropdown by exact text match.
        
        Args:
            dropdown_label: Label of the dropdown (e.g., "Terminal", "Move Type")
            option_text: Exact text of the option to select
            fallback_to_any: If True and exact match fails, select any available option (for Line dropdown)
        
        Returns:
            Dict with success status
        """
        try:
            print(f"🔽 Selecting '{option_text}' from '{dropdown_label}' dropdown...")
            
            # Find dropdown by label
            dropdowns = self.driver.find_elements(By.XPATH, f"//mat-label[contains(text(),'{dropdown_label}')]/ancestor::mat-form-field//mat-select")
            
            if not dropdowns:
                # Try alternative: find by placeholder or aria-label
                dropdowns = self.driver.find_elements(By.XPATH, f"//mat-select[contains(@aria-label,'{dropdown_label}')]")
            
            if not dropdowns:
                return {"success": False, "error": f"Dropdown '{dropdown_label}' not found"}
            
            dropdown = dropdowns[0]
            
            # Click to open dropdown
            self.driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
            time.sleep(0.5)
            dropdown.click()
            time.sleep(2)  # Increased wait for dropdown to fully open and load options
            
            print(f"  ✅ Opened {dropdown_label} dropdown")
            self._capture_screenshot(f"dropdown_{dropdown_label.lower().replace(' ', '_')}_opened")
            
            # Normalize the search text (remove extra spaces around dashes, hyphens, etc.)
            normalized_text = option_text.replace(' - ', '-').replace(' -', '-').replace('- ', '-').strip()
            
            if normalized_text != option_text:
                print(f"  📝 Normalized search: '{option_text}' → '{normalized_text}'")
            
            # Wait for options to be visible and find option by exact text
            options = None
            for attempt in range(3):  # Try 3 times with increasing waits
                # Try with normalized text first
                options = self.driver.find_elements(By.XPATH, f"//mat-option//span[normalize-space(text())='{normalized_text}']")
                
                # If not found and normalized is different, try original text
                if not options and normalized_text != option_text:
                    options = self.driver.find_elements(By.XPATH, f"//mat-option//span[normalize-space(text())='{option_text}']")
                
                if options:
                    break
                print(f"  ⏳ Waiting for options to load (attempt {attempt + 1}/3)...")
                time.sleep(1)
            
            if not options:
                # Try partial match as fallback (with both normalized and original)
                print(f"  ⚠️ Exact match failed, trying partial match...")
                options = self.driver.find_elements(By.XPATH, f"//mat-option//span[contains(text(),'{normalized_text}')]")
                
                if not options and normalized_text != option_text:
                    options = self.driver.find_elements(By.XPATH, f"//mat-option//span[contains(text(),'{option_text}')]")
            
            if not options:
                # If fallback is enabled (for Line dropdown), try to select any available option
                if fallback_to_any:
                    print(f"  ⚠️ Option '{option_text}' not found, selecting any available option...")
                    try:
                        all_options = self.driver.find_elements(By.XPATH, "//mat-option//span[@class='mat-option-text']")
                        if all_options:
                            # Select the first available option
                            fallback_option = all_options[0]
                            fallback_text = fallback_option.text.strip()
                            
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", fallback_option)
                            time.sleep(0.3)
                            fallback_option.click()
                            time.sleep(1)
                            
                            print(f"  ✅ Fallback: Selected '{fallback_text}' from {dropdown_label}")
                            self._capture_screenshot(f"dropdown_{dropdown_label.lower().replace(' ', '_')}_fallback_selected")
                            
                            return {"success": True, "selected": fallback_text, "fallback": True}
                        else:
                            print(f"  ❌ No options available in {dropdown_label} dropdown")
                            return {"success": False, "error": f"No options available in {dropdown_label} dropdown"}
                    except Exception as fallback_error:
                        print(f"  ❌ Fallback selection failed: {fallback_error}")
                        return {"success": False, "error": f"Fallback selection failed: {str(fallback_error)}"}
                
                # Close dropdown and report detailed error
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                except:
                    pass
                
                # Try to get all available options for debugging
                try:
                    all_options = self.driver.find_elements(By.XPATH, "//mat-option//span[@class='mat-option-text']")
                    available = [opt.text.strip() for opt in all_options[:10]]  # First 10 options
                    error_msg = f"Option '{option_text}' not found in {dropdown_label}. Available options: {', '.join(available)}"
                except:
                    error_msg = f"Option '{option_text}' not found in {dropdown_label}"
                
                return {"success": False, "error": error_msg}
            
            # Click the option
            option = options[0]
            self.driver.execute_script("arguments[0].scrollIntoView(true);", option)
            time.sleep(0.3)
            option.click()
            time.sleep(1)
            
            print(f"  ✅ Selected '{option_text}' from {dropdown_label}")
            self._capture_screenshot(f"dropdown_{dropdown_label.lower().replace(' ', '_')}_selected")
            
            return {"success": True, "selected": option_text}
            
        except Exception as e:
            print(f"  ❌ Error selecting dropdown: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_container_number(self, container_id: str) -> Dict[str, Any]:
        """
        Fill the container number field (chip input) or booking number field (text input).
        For container fields: Clears existing chips first, then adds the new container.
        For booking fields: Clears and fills the text input directly.
        
        Args:
            container_id: Container number or booking number to add
        
        Returns:
            Dict with success status
        """
        try:
            print(f"📦 Filling container/booking number: {container_id}...")
            
            # Wait 3 seconds before starting to fill (allows UI to stabilize after dropdown selections)
            print("  ⏳ Waiting 3 seconds for UI to stabilize...")
            time.sleep(3)
            print("  ✅ Ready to fill container/booking number")
            
            # First, try to find booking number field (text input)
            booking_input = None
            try:
                booking_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='bookingNumber']")
                print("  📋 Found booking number field (text input)")
            except:
                pass
            
            if booking_input:
                # Handle booking number field (chip input - same as container)
                print(f"  📝 Filling booking number field: {container_id}")
                
                # Clear existing chips first (same as container field)
                remove_buttons = self.driver.find_elements(By.XPATH, "//mat-icon[@matchipremove and contains(text(),'cancel')]")
                if remove_buttons:
                    print(f"  🗑️ Removing {len(remove_buttons)} existing booking number(s)...")
                    for btn in remove_buttons:
                        try:
                            btn.click()
                            time.sleep(0.3)
                        except:
                            pass
                    self._capture_screenshot("booking_numbers_cleared")
                
                # Click and type
                booking_input.click()
                time.sleep(0.3)
                booking_input.send_keys(container_id)
                time.sleep(0.5)
                
                # Press Enter to add as chip (same as container)
                booking_input.send_keys(Keys.ENTER)
                time.sleep(1)
                
                # Click blank area to confirm chip is added
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    time.sleep(0.5)
                    print(f"  ✅ Booking number chip confirmed")
                except:
                    pass
                
                # Verify chip was added
                chips = self.driver.find_elements(By.XPATH, f"//mat-chip//span[contains(text(),'{container_id}')]")
                if chips:
                    print(f"  ✅ Added booking number: {container_id}")
                    self._capture_screenshot("booking_number_added")
                    return {"success": True, "container_id": container_id, "field_type": "booking_number"}
                else:
                    print(f"  ⚠️ Booking number chip may not have been added, but continuing...")
                    self._capture_screenshot("booking_number_added_unverified")
                    return {"success": True, "container_id": container_id, "field_type": "booking_number"}
            
            # If no booking field found, try container number field (chip input)
            print("  📦 No booking field found, trying container number field...")
            
            # Clear existing chips first
            remove_buttons = self.driver.find_elements(By.XPATH, "//mat-icon[@matchipremove and contains(text(),'cancel')]")
            if remove_buttons:
                print(f"  🗑️ Removing {len(remove_buttons)} existing container(s)...")
                for btn in remove_buttons:
                    try:
                        btn.click()
                        time.sleep(0.3)
                    except:
                        pass
                self._capture_screenshot("containers_cleared")
            
            # Find the container input field
            container_input = None
            try:
                container_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='containerNumber']")
            except:
                try:
                    container_input = self.driver.find_element(By.XPATH, "//input[@placeholder='Container number(s)']")
                except:
                    pass
            
            if not container_input:
                return {"success": False, "error": "FIELD_NOT_FOUND: Neither container number nor booking number input field found", "field_not_found": True}
            
            # Click and type
            container_input.click()
            time.sleep(0.3)
            container_input.send_keys(container_id)
            time.sleep(0.5)
            
            # Press Enter to add as chip
            container_input.send_keys(Keys.ENTER)
            time.sleep(1)
            
            # Click blank area to confirm chip is added
            try:
                # Click on the page body to remove focus from input
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
                print(f"  ✅ Container chip confirmed")
            except:
                pass
            
            # Verify chip was added
            chips = self.driver.find_elements(By.XPATH, f"//mat-chip//span[contains(text(),'{container_id}')]")
            if chips:
                print(f"  ✅ Added container: {container_id}")
                self._capture_screenshot("container_added")
                return {"success": True, "container_id": container_id, "field_type": "container_number"}
            else:
                print(f"  ⚠️ Container chip may not have been added, but continuing...")
                self._capture_screenshot("container_added_unverified")
                return {"success": True, "container_id": container_id, "field_type": "container_number"}
            
        except Exception as e:
            print(f"  ❌ Error filling container/booking number: {e}")
            return {"success": False, "error": str(e)}
    
    def get_current_phase_from_stepper(self) -> int:
        """
        Detect current phase from the Material stepper in the top bar.
        Returns phase number (1-4) or 0 if unable to detect.
        """
        try:
            # Find the selected/active step header
            selected_headers = self.driver.find_elements(By.XPATH, 
                "//mat-step-header[contains(@class,'mat-step-icon-selected')]")
            
            if selected_headers:
                # Get aria-posinset which indicates the step number
                aria_pos = selected_headers[0].get_attribute("aria-posinset")
                if aria_pos:
                    return int(aria_pos)
            
            # Fallback: check for aria-selected="true"
            active_headers = self.driver.find_elements(By.XPATH,
                "//mat-step-header[@aria-selected='true']")
            
            if active_headers:
                aria_pos = active_headers[0].get_attribute("aria-posinset")
                if aria_pos:
                    return int(aria_pos)
            
            return 0  # Unable to detect
            
        except Exception as e:
            print(f"  ⚠️ Could not detect phase from stepper: {e}")
            return 0
    
    def click_next_button(self, phase: int) -> Dict[str, Any]:
        """
        Click the Next button to proceed to the next phase.
        Verifies phase transition using the stepper bar.
        
        Args:
            phase: Current phase number (for logging)
        
        Returns:
            Dict with success status and needs_retry flag
        """
        try:
            print(f"➡️ Clicking Next button (Phase {phase} → {phase + 1})...")
            
            # Check current phase from stepper
            stepper_phase_before = self.get_current_phase_from_stepper()
            if stepper_phase_before > 0:
                print(f"  📊 Stepper shows we're in phase: {stepper_phase_before}")
            
            # Find Next button (prioritize visible and enabled ones)
            # IMPORTANT: Explicitly exclude Submit button to avoid accidents
            # Look for button with class 'text-next' which is the active Next button
            next_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(@class,'text-next') and .//span[text()='Next' or contains(text(),'Next')]]")
            
            if not next_buttons:
                # Fallback: find any button with Next text (but NOT Submit)
                next_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[.//span[text()='Next' or contains(text(),'Next')]][not(.//span[text()='Submit'])]")
            
            if not next_buttons:
                return {"success": False, "error": "Next button not found"}
            
            # Filter for visible and enabled buttons
            visible_buttons = []
            for btn in next_buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        visible_buttons.append(btn)
                except:
                    pass
            
            if not visible_buttons:
                # If no visible buttons, just use first one found
                next_button = next_buttons[0]
                print(f"  ⚠️ Using first Next button (may not be visible)")
            else:
                next_button = visible_buttons[0]
                print(f"  ✅ Found visible and enabled Next button")
                if len(visible_buttons) > 1:
                    print(f"  📊 Note: {len(visible_buttons)} Next buttons found, using first visible one")
            
            # Scroll into view (center of viewport)
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_button)
            time.sleep(1)
            
            # Try regular click first
            try:
                next_button.click()
                print(f"  ✅ Clicked Next button (regular click)")
            except Exception as click_error:
                # If regular click fails, use JavaScript click
                print(f"  ⚠️ Regular click failed, using JavaScript click...")
                self.driver.execute_script("arguments[0].click();", next_button)
                print(f"  ✅ Clicked Next button (JavaScript click)")
            
            # Wait for transition and stepper UI to update
            print(f"  ⏳ Waiting 25 seconds for stepper to update...")
            time.sleep(25)
            print(f"  ✅ Wait complete, checking stepper...")
            
            # Verify phase transition using stepper
            stepper_phase_after = self.get_current_phase_from_stepper()
            if stepper_phase_after > 0:
                print(f"  📊 After click, stepper shows phase: {stepper_phase_after}")
                
                if stepper_phase_after == stepper_phase_before:
                    print(f"  ⚠️ Phase did not advance! Still in phase {stepper_phase_after}")
                    self._capture_screenshot(f"phase_{phase}_stuck")
                    return {"success": False, "error": f"Phase did not advance from {stepper_phase_before}", "needs_retry": True}
                elif stepper_phase_after == phase + 1:
                    print(f"  ✅ Successfully advanced to phase {stepper_phase_after}")
                    self._capture_screenshot(f"phase_{phase + 1}_loaded")
                    return {"success": True}
                else:
                    print(f"  ⚠️ Unexpected phase {stepper_phase_after}, expected {phase + 1}")
            
            # If stepper detection failed, just assume success
            self._capture_screenshot(f"phase_{phase + 1}_loaded")
            return {"success": True}
            
        except Exception as e:
            print(f"  ❌ Error clicking Next: {e}")
            return {"success": False, "error": str(e)}
    
    def select_container_checkbox(self) -> Dict[str, Any]:
        """Select the container checkbox in Phase 2"""
        try:
            print("☑️ Selecting container checkbox...")
            checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' and contains(@class,'mat-checkbox-input')]")
            if not checkboxes:
                return {"success": False, "error": "Container checkbox not found"}
            checkbox = checkboxes[0]
            is_checked = checkbox.is_selected()
            if not is_checked:
                try:
                    parent = checkbox.find_element(By.XPATH, "./ancestor::mat-checkbox")
                    parent.click()
                    time.sleep(1)
                    print("  ✅ Checkbox selected")
                except:
                    checkbox.click()
                    time.sleep(1)
                    print("  ✅ Checkbox selected (direct)")
            else:
                print("  ✅ Checkbox already selected")
            self._capture_screenshot("checkbox_selected")
            return {"success": True}
        except Exception as e:
            print(f"  ❌ Error selecting checkbox: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_pin_code(self, pin_code: str = None) -> Dict[str, Any]:
        """
        Fill the PIN code field in Phase 2.
        If pin_code is not provided or empty, auto-fills with '1111'.
        If the PIN field doesn't exist, it's skipped (returns success).
        """
        try:
            # Auto-fill with '1111' if no PIN provided
            if not pin_code:
                pin_code = "1111"
                print(f"🔢 Checking for PIN code field (default: 1111)...")
            else:
                print(f"🔢 Checking for PIN code field: {pin_code}")
            
            # Try to find PIN field
            pin_input = None
            try:
                pin_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='Pin']")
                print(f"  ✅ PIN field found (formcontrolname='Pin')")
            except:
                try:
                    pin_input = self.driver.find_element(By.XPATH, "//input[@matinput and contains(@placeholder,'PIN')]")
                    print(f"  ✅ PIN field found (placeholder contains 'PIN')")
                except:
                    pass
            
            # If PIN field doesn't exist, skip it (not an error)
            if not pin_input:
                print(f"  ⚠️ PIN field not found - skipping (optional field)")
                return {"success": True, "skipped": True, "reason": "PIN field not found"}
            
            # Fill the PIN field
            pin_input.click()
            time.sleep(0.3)
            pin_input.clear()
            pin_input.send_keys(pin_code)
            time.sleep(0.5)
            print(f"  ✅ PIN code entered: {pin_code}")
            self._capture_screenshot("pin_entered")
            return {"success": True, "pin_code": pin_code}
        except Exception as e:
            print(f"  ⚠️ Error filling PIN (ignoring): {e}")
            # Don't fail the entire process if PIN fails
            return {"success": True, "skipped": True, "error": str(e)}
    
    def fill_truck_plate(self, truck_plate: str, allow_any_if_missing: bool = True) -> Dict[str, Any]:
        """
        Fill the truck plate field in Phase 2.
        If exact match not found, can select any available option.
        
        Special case: If truck_plate is "ABC123" or empty, it will select any available plate from the list.
        
        Args:
            truck_plate: Desired truck plate number (use "ABC123" or empty string to select any available plate)
            allow_any_if_missing: If True, select first available option if exact match fails
        """
        try:
            print(f"🚛 Filling truck plate: {truck_plate if truck_plate else '(empty - will select from list)'}...")
            
            # Check if this is a wildcard request (ABC123 or empty string)
            is_wildcard = truck_plate.upper() == "ABC123" or truck_plate.strip() == ""
            if is_wildcard:
                if truck_plate.strip() == "":
                    print(f"  🎲 Empty truck plate detected - will select any available truck plate from list")
                else:
                    print(f"  🎲 Wildcard detected (ABC123) - will select any available truck plate from list")
            
            # Find plate input field
            plate_input = None
            try:
                plate_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='Plate']")
            except:
                try:
                    plate_input = self.driver.find_element(By.XPATH, "//input[@matinput and contains(@class,'mat-autocomplete-trigger')]")
                except:
                    pass
            
            if not plate_input:
                return {"success": False, "error": "Truck plate field not found"}
            
            # Click to open dropdown
            plate_input.click()
            time.sleep(0.3)
            plate_input.clear()
            
            # If wildcard, just trigger the dropdown without typing specific value
            if is_wildcard:
                # Type a space or click to trigger dropdown
                plate_input.send_keys(" ")
                time.sleep(1.5)  # Wait for autocomplete to populate
                
                # Clear the space
                plate_input.clear()
                time.sleep(0.5)
                
                print(f"  🔍 Searching for any available truck plate in list...")
                
                try:
                    # Get all available options
                    all_options = self.driver.find_elements(By.XPATH, "//mat-option")
                    
                    if all_options:
                        # Select first available option
                        first_option = all_options[0]
                        selected_text = first_option.text.strip()
                        first_option.click()
                        time.sleep(0.5)
                        print(f"  ✅ Selected truck plate from list: '{selected_text}'")
                        
                        # Click blank area to confirm selection
                        try:
                            self.driver.find_element(By.TAG_NAME, "body").click()
                            time.sleep(0.5)
                            print(f"  ✅ Truck plate confirmed")
                        except:
                            pass
                        
                        self._capture_screenshot("truck_plate_wildcard_selected")
                        return {"success": True, "truck_plate": selected_text, "exact_match": False, "wildcard": True, "original_request": truck_plate}
                    else:
                        print(f"  ❌ No truck plate options available in list")
                        # Close autocomplete
                        try:
                            self.driver.find_element(By.TAG_NAME, "body").click()
                        except:
                            pass
                        return {"success": False, "error": "No truck plates available in dropdown"}
                except Exception as option_error:
                    print(f"  ❌ Error selecting from list: {option_error}")
                    return {"success": False, "error": f"Failed to select from truck plate list: {str(option_error)}"}
            
            # Normal flow: type the specific truck plate
            plate_input.send_keys(truck_plate)
            time.sleep(1.5)  # Wait for autocomplete to populate
            
            # Try to find exact match
            try:
                options = self.driver.find_elements(By.XPATH, f"//mat-option//span[contains(text(),'{truck_plate}')]")
                if options:
                    options[0].click()
                    time.sleep(0.5)
                    print(f"  ✅ Selected '{truck_plate}' from autocomplete")
                    
                    # Click blank area to confirm selection
                    try:
                        self.driver.find_element(By.TAG_NAME, "body").click()
                        time.sleep(0.5)
                        print(f"  ✅ Truck plate confirmed")
                    except:
                        pass
                    
                    self._capture_screenshot("truck_plate_entered")
                    return {"success": True, "truck_plate": truck_plate, "exact_match": True}
            except:
                pass
            
            # If exact match not found, try to select any available option
            if allow_any_if_missing:
                print(f"  ⚠️ Exact match not found for '{truck_plate}'")
                print(f"  🔄 Looking for any available truck plate option...")
                
                try:
                    # Get all available options
                    all_options = self.driver.find_elements(By.XPATH, "//mat-option")
                    
                    if all_options:
                        # Select first available option
                        first_option = all_options[0]
                        selected_text = first_option.text.strip()
                        first_option.click()
                        time.sleep(0.5)
                        print(f"  ✅ Selected alternative truck plate: '{selected_text}'")
                        
                        # Click blank area to confirm selection
                        try:
                            self.driver.find_element(By.TAG_NAME, "body").click()
                            time.sleep(0.5)
                            print(f"  ✅ Truck plate confirmed")
                        except:
                            pass
                        
                        self._capture_screenshot("truck_plate_alternative_selected")
                        return {"success": True, "truck_plate": selected_text, "exact_match": False, "original_request": truck_plate}
                    else:
                        print(f"  ❌ No truck plate options available")
                        # Close autocomplete
                        try:
                            self.driver.find_element(By.TAG_NAME, "body").click()
                        except:
                            pass
                except Exception as option_error:
                    print(f"  ⚠️ Could not select alternative: {option_error}")
            
            # If we reach here, just accept whatever was typed
            print(f"  ⚠️ Using typed value (no autocomplete selection)")
            
            # Click blank area to confirm
            try:
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
            except:
                pass
            
            self._capture_screenshot("truck_plate_typed")
            return {"success": True, "truck_plate": truck_plate, "exact_match": False}
            
        except Exception as e:
            print(f"  ❌ Error filling truck plate: {e}")
            return {"success": False, "error": str(e)}
    
    def close_popup_if_present(self) -> Dict[str, Any]:
        """Detect and close popup messages (e.g., 'Booking shippingline is required')"""
        try:
            print("🔍 Checking for popup messages...")
            
            # Look for CLOSE button in popup
            close_buttons = self.driver.find_elements(
                By.XPATH,
                "//span[@class='mat-button-wrapper' and text()='CLOSE']"
            )
            
            if close_buttons:
                print(f"  ⚠️ Found {len(close_buttons)} popup(s) - closing...")
                
                for idx, close_btn in enumerate(close_buttons, 1):
                    try:
                        # Check if button is visible
                        if close_btn.is_displayed():
                            print(f"  🖱️  Clicking CLOSE button {idx}...")
                            
                            # Try regular click first
                            try:
                                close_btn.click()
                            except:
                                # Fallback to JavaScript click
                                self.driver.execute_script("arguments[0].click();", close_btn)
                            
                            time.sleep(0.5)
                            print(f"  ✅ Popup {idx} closed")
                    except Exception as btn_error:
                        print(f"  ⚠️ Could not click button {idx}: {btn_error}")
                
                self._capture_screenshot("popup_closed")
                return {"success": True, "popups_closed": len(close_buttons)}
            else:
                print("  ℹ️  No popup messages found")
                return {"success": True, "popups_closed": 0}
                
        except Exception as e:
            print(f"  ⚠️ Error checking for popups: {e}")
            # Don't fail the whole operation if popup check fails
            return {"success": True, "popups_closed": 0, "error": str(e)}
    
    def toggle_own_chassis(self, own_chassis: bool) -> Dict[str, Any]:
        """Toggle the 'Own Chassis' button - Smart toggle that reads current state first"""
        try:
            target = "YES" if own_chassis else "NO"
            print(f"🔘 Setting Own Chassis to: {target}...")
            
            # Take screenshot before reading state
            self._capture_screenshot("own_chassis_before_read")
            
            # Find all YES/NO toggle spans (with or without _ngcontent attributes)
            toggle_spans = self.driver.find_elements(By.XPATH, "//span[text()='YES' or text()='NO']")
            if not toggle_spans:
                print(f"  ❌ No YES/NO toggle buttons found")
                return {"success": False, "error": "Own chassis toggle not found"}
            
            print(f"  🔍 Found {len(toggle_spans)} toggle span(s)")
            
            # Detect current state by checking multiple indicators
            current_state = None
            current_span = None
            
            for span in toggle_spans:
                try:
                    text = span.text.strip()
                    # Try multiple ways to find parent button
                    parent = None
                    try:
                        parent = span.find_element(By.XPATH, "./ancestor::button[contains(@class,'mat-button-toggle')]")
                    except:
                        try:
                            parent = span.find_element(By.XPATH, "..")
                        except:
                            pass
                    
                    if parent:
                        classes = parent.get_attribute("class") or ""
                        aria_pressed = parent.get_attribute("aria-pressed") or ""
                        
                        print(f"    Span '{text}': pressed={aria_pressed}, has-checked-class={('mat-button-toggle-checked' in classes)}")
                        
                        # Check if this button is currently selected
                        if "mat-button-toggle-checked" in classes or aria_pressed == "true":
                            current_state = text
                            current_span = span
                            print(f"  ✅ Detected current state: {current_state}")
                            break
                    else:
                        print(f"    Span '{text}': Could not find parent button")
                except Exception as e:
                    print(f"    ⚠️ Error checking span: {e}")
                    pass
            
            # If still no state detected, assume YES is default for export (most common case)
            if current_state is None:
                current_state = "YES"
                print(f"  ⚠️ Could not detect state, assuming default: {current_state}")
            
            # Check if already in desired state
            if current_state == target:
                print(f"  ✅ Already set to {target} - no action needed")
                self._capture_screenshot("own_chassis_already_set")
                return {"success": True, "own_chassis": own_chassis, "was_toggled": False}
            
            # Need to toggle - find and click the target button
            print(f"  🔄 Changing from {current_state} to {target}...")
            for span in toggle_spans:
                if span.text.strip() == target:
                    try:
                        # Scroll span into view
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", span)
                        time.sleep(0.5)
                        
                        # Try to find parent button and click it
                        parent = None
                        try:
                            parent = span.find_element(By.XPATH, "./ancestor::button[contains(@class,'mat-button-toggle')]")
                        except:
                            try:
                                parent = span.find_element(By.XPATH, "..")
                            except:
                                pass
                        
                        if parent:
                            print(f"  🖱️  Clicking {target} button (parent)...")
                            try:
                                parent.click()
                                time.sleep(1)
                                print(f"  ✅ Toggled to {target}")
                                self._capture_screenshot("own_chassis_toggled")
                                return {"success": True, "own_chassis": own_chassis, "was_toggled": True}
                            except:
                                pass
                        
                        # If parent click failed or parent not found, click span directly
                        print(f"  🖱️  Clicking {target} button (direct span)...")
                        span.click()
                        time.sleep(1)
                        print(f"  ✅ Toggled to {target} (direct click)")
                        self._capture_screenshot("own_chassis_toggled")
                        return {"success": True, "own_chassis": own_chassis, "was_toggled": True}
                        
                    except Exception as click_error:
                        print(f"  ⚠️ Error clicking: {click_error}")
                        pass
            
            return {"success": False, "error": f"Could not find {target} option"}
        except Exception as e:
            print(f"  ❌ Error toggling own chassis: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def fill_quantity_field(self) -> Dict[str, Any]:
        """Fill quantity field with '1' for export appointments"""
        try:
            print(f"🔢 Filling quantity field...")
            
            # Find quantity field by label
            quantity_input = None
            try:
                # Strategy 1: Find by label "Quantity"
                quantity_input = self.driver.find_element(
                    By.XPATH, 
                    "//mat-label[contains(text(),'Quantity')]/ancestor::mat-form-field//input[@type='number']"
                )
            except:
                # Strategy 2: Find by type='number' with min='1'
                try:
                    quantity_input = self.driver.find_element(
                        By.XPATH,
                        "//input[@type='number' and @min='1']"
                    )
                except:
                    pass
            
            if not quantity_input:
                return {"success": False, "error": "Quantity field not found"}
            
            # Get current value
            current_value = quantity_input.get_attribute("value") or "0"
            print(f"  📊 Current quantity: {current_value}")
            
            # Clear and set to 1
            quantity_input.clear()
            time.sleep(0.3)
            quantity_input.click()
            time.sleep(0.3)
            quantity_input.send_keys("1")
            time.sleep(0.5)
            
            print(f"  ✅ Quantity set to 1")
            self._capture_screenshot("quantity_filled")
            
            # Wait 3 seconds as requested
            print(f"  ⏳ Waiting 3 seconds...")
            time.sleep(3)
            
            return {"success": True, "quantity": "1"}
            
        except Exception as e:
            print(f"  ❌ Error filling quantity: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_unit_number(self, unit_number: str = "1") -> Dict[str, Any]:
        """Fill unit number field for export appointments"""
        try:
            print(f"📦 Filling unit number: {unit_number}...")
            
            # Find unit number field by formcontrolname
            unit_input = None
            try:
                unit_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='Unit']")
            except:
                try:
                    # Fallback: Find by uppercase attribute
                    unit_input = self.driver.find_element(
                        By.XPATH,
                        "//input[@matinput and @uppercase and @maxlength='11']"
                    )
                except:
                    pass
            
            if not unit_input:
                return {"success": False, "error": "Unit number field not found"}
            
            # Clear and fill
            unit_input.clear()
            time.sleep(0.3)
            unit_input.click()
            time.sleep(0.3)
            unit_input.send_keys(unit_number)
            time.sleep(0.5)
            
            print(f"  ✅ Unit number filled: {unit_number}")
            self._capture_screenshot("unit_number_filled")
            return {"success": True, "unit_number": unit_number}
            
        except Exception as e:
            print(f"  ❌ Error filling unit number: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_seal_fields(self, seal_value: str = "1") -> Dict[str, Any]:
        """Fill all 4 seal fields for export appointments"""
        try:
            print(f"🔒 Filling seal fields with: {seal_value}...")
            
            filled_count = 0
            
            # Fill all 4 seal fields
            for i in range(1, 5):
                seal_name = f"Seal{i}_Num"
                try:
                    seal_input = self.driver.find_element(
                        By.XPATH,
                        f"//input[@formcontrolname='{seal_name}']"
                    )
                    
                    seal_input.clear()
                    time.sleep(0.2)
                    seal_input.click()
                    time.sleep(0.2)
                    seal_input.send_keys(seal_value)
                    time.sleep(0.3)
                    
                    filled_count += 1
                    print(f"  ✅ Filled Seal {i}")
                    
                except Exception as seal_error:
                    print(f"  ⚠️ Could not fill Seal {i}: {seal_error}")
            
            if filled_count == 0:
                return {"success": False, "error": "No seal fields found"}
            
            print(f"  ✅ Filled {filled_count}/4 seal fields")
            self._capture_screenshot("seals_filled")
            return {"success": True, "seals_filled": filled_count}
            
        except Exception as e:
            print(f"  ❌ Error filling seal fields: {e}")
            return {"success": False, "error": str(e)}
    
    def find_and_click_calendar_icon(self) -> Dict[str, Any]:
        """Find and click calendar icon in Phase 3, then take screenshot"""
        try:
            print(f"📅 Looking for calendar icon...")
            
            # Find calendar icon by text 'calendar_month'
            calendar_icon = None
            try:
                calendar_icon = self.driver.find_element(
                    By.XPATH,
                    "//mat-icon[text()='calendar_month']"
                )
            except:
                # Fallback: Find any mat-icon with calendar in it
                try:
                    calendar_icon = self.driver.find_element(
                        By.XPATH,
                        "//mat-icon[contains(text(),'calendar')]"
                    )
                except:
                    pass
            
            if not calendar_icon:
                print(f"  ❌ Calendar icon not found")
                self._capture_screenshot("calendar_not_found")
                return {"success": False, "calendar_found": False, "error": "Calendar icon not found"}
            
            print(f"  ✅ Calendar icon found")
            
            # Click the calendar icon
            try:
                calendar_icon.click()
            except:
                # Try JavaScript click
                self.driver.execute_script("arguments[0].click();", calendar_icon)
            
            time.sleep(1)
            print(f"  ✅ Calendar clicked")
            
            # Take screenshot to show calendar
            screenshot_path = self._capture_screenshot("calendar_opened")
            
            return {"success": True, "calendar_found": True, "calendar_screenshot": screenshot_path}
            
        except Exception as e:
            print(f"  ❌ Error with calendar icon: {e}")
            self._capture_screenshot("calendar_error")
            return {"success": False, "calendar_found": False, "error": str(e)}
    
    def get_available_appointment_times(self) -> Dict[str, Any]:
        """
        Get all available appointment time slots from Phase 3 dropdown.
        ⚠️ This method DOES NOT click Submit - only retrieves available times.
        Safe for /check_appointments endpoint.
        """
        try:
            print("📅 Getting available appointment times...")
            print("  ℹ️  NOTE: Will NOT click Submit button - only retrieving times")
            
            # Take screenshot before attempting to find dropdown
            self._capture_screenshot("phase_3_before_dropdown")
            
            # Try multiple strategies to find the appointment dropdown
            print("  🔍 Looking for appointment dropdown...")
            
            # Strategy 1: By formcontrolname='slot'
            dropdowns = self.driver.find_elements(By.XPATH, "//mat-select[@formcontrolname='slot']")
            print(f"  📊 Strategy 1 (formcontrolname='slot'): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                # Strategy 2: By mat-label text
                dropdowns = self.driver.find_elements(By.XPATH, "//mat-label[contains(text(),'Appointment') or contains(text(),'Time')]/ancestor::mat-form-field//mat-select")
                print(f"  📊 Strategy 2 (mat-label): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                # Strategy 3: By aria-label
                dropdowns = self.driver.find_elements(By.XPATH, "//mat-select[contains(@aria-label,'appointment') or contains(@aria-label,'time')]")
                print(f"  📊 Strategy 3 (aria-label): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                # Strategy 4: Any mat-select in Phase 3
                dropdowns = self.driver.find_elements(By.XPATH, "//mat-select")
                print(f"  📊 Strategy 4 (any mat-select): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                self._capture_screenshot("appointment_dropdown_not_found")
                return {"success": False, "error": "Appointment time dropdown not found after trying all strategies"}
            
            dropdown = dropdowns[0]
            print(f"  ✅ Found dropdown, using first one")
            
            # Scroll into view and click
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown)
            time.sleep(1)
            
            # Try clicking
            try:
                dropdown.click()
                print("  ✅ Clicked dropdown (regular click)")
            except Exception as click_error:
                print(f"  ⚠️ Regular click failed, using JavaScript click...")
                self.driver.execute_script("arguments[0].click();", dropdown)
                print("  ✅ Clicked dropdown (JavaScript click)")
            
            time.sleep(2)
            print("  ✅ Opened appointment dropdown")
            self._capture_screenshot("appointment_dropdown_opened")
            
            # Get options
            options = self.driver.find_elements(By.XPATH, "//mat-option//span[@class='mat-option-text' or contains(@class,'mat-select-min-line')]")
            print(f"  📊 Found {len(options)} option elements")
            
            available_times = []
            for option in options:
                time_text = option.text.strip()
                if time_text:
                    available_times.append(time_text)
            
            # Close dropdown
            try:
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
            except:
                pass
            
            print(f"  ✅ Found {len(available_times)} available appointment times")
            for i, time_slot in enumerate(available_times[:5], 1):
                print(f"     {i}. {time_slot}")
            if len(available_times) > 5:
                print(f"     ... and {len(available_times) - 5} more")
            
            self._capture_screenshot("appointment_times_retrieved")
            
            # Find the dropdown opened screenshot for return
            dropdown_screenshot = None
            for screenshot_path in self.screens:
                if "appointment_dropdown_opened" in screenshot_path:
                    dropdown_screenshot = screenshot_path
                    break
            
            return {
                "success": True, 
                "available_times": available_times, 
                "count": len(available_times),
                "dropdown_screenshot": dropdown_screenshot
            }
        except Exception as e:
            print(f"  ❌ Error getting appointment times: {e}")
            import traceback
            traceback.print_exc()
            self._capture_screenshot("appointment_error")
            return {"success": False, "error": str(e)}
    
    def select_appointment_time(self, appointment_time: str) -> Dict[str, Any]:
        """Select a specific appointment time in Phase 3"""
        try:
            print(f"📅 Selecting appointment time: {appointment_time}...")
            result = self.select_dropdown_by_text("Appointment", appointment_time)
            if result["success"]:
                print(f"  ✅ Appointment time selected")
                self._capture_screenshot("appointment_time_selected")
            return result
        except Exception as e:
            print(f"  ❌ Error selecting appointment time: {e}")
            return {"success": False, "error": str(e)}
    
    def click_submit_button(self) -> Dict[str, Any]:
        """Click the Submit button in Phase 3 - ACTUALLY SUBMITS THE APPOINTMENT!"""
        try:
            print("✅ Clicking Submit button (FINAL SUBMISSION)...")
            submit_buttons = self.driver.find_elements(By.XPATH, "//button//span[contains(text(),'Submit')]/..")
            if not submit_buttons:
                return {"success": False, "error": "Submit button not found"}
            submit_button = submit_buttons[0]
            self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            time.sleep(3)
            print(f"  ✅ Submit button clicked - Appointment submitted!")
            self._capture_screenshot("appointment_submitted")
            return {"success": True}
        except Exception as e:
            print(f"  ❌ Error clicking Submit: {e}")
            return {"success": False, "error": str(e)}
    
    def select_all_containers(self) -> Dict[str, Any]:
        """Select all containers using the master checkbox"""
        try:
            print("☑️ Looking for 'Select All' checkbox...")
            self._capture_screenshot("before_select_all")
            
            # Common selectors for "select all" checkbox (header-first with fallbacks)
            select_all_selectors = [
                # Native inputs in header
                "//thead//input[@type='checkbox']",
                "//th//input[@type='checkbox']",
                "//table//thead//input[@type='checkbox']",
                # Angular Material (mat-checkbox) input/label/inner container
                "//mat-checkbox//input[contains(@id,'-input')]",
                "//mat-checkbox//label",
                "//mat-checkbox//span[contains(@class,'mat-checkbox-inner-container')]",
                # ARIA role=checkbox in header
                "//thead//*[@role='checkbox']",
                "//th//*[@role='checkbox']",
                # Text-based
                "//*[normalize-space(text())='Select all' or normalize-space(text())='Select All']",
                # Common IDs/classes/data-attrs
                "//input[@type='checkbox' and (@id='selectAll' or contains(@class,'select-all') or contains(@class,'selectAll'))]",
                "//*[@data-select-all='true' or @data-select-all='1']",
                # Fallbacks
                "(//table//th//input[@type='checkbox'])[1]",
                ".select-all-checkbox",
                "input[data-select-all]",
                "//input[@type='checkbox'][1]"
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
                    
                    if element.is_displayed():
                        # If we matched a mat-checkbox label or inner span or role element,
                        # we still need the actual input for state checks.
                        select_all_checkbox = None
                        if element.tag_name.lower() == 'input' and element.get_attribute('type') == 'checkbox':
                            select_all_checkbox = element
                        else:
                            # Try to find the related input within the same mat-checkbox or by label[for]
                            try:
                                # Climb to mat-checkbox ancestor then find input
                                mat = element.find_element(By.XPATH, "ancestor::mat-checkbox")
                                select_all_checkbox = mat.find_element(By.XPATH, ".//input[contains(@id,'-input') and @type='checkbox']")
                            except Exception:
                                # If current is a label, resolve its 'for'
                                try:
                                    control_id = element.get_attribute('for')
                                    if control_id:
                                        select_all_checkbox = self.driver.find_element(By.ID, control_id)
                                except Exception:
                                    pass
                        if select_all_checkbox:
                            used_selector = selector
                            print(f"✅ Found select-all via: {selector}")
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
                
                # Click to select all with robust fallback chain
                # Order: TH parent > Label > Inner container > JS on input
                clicked = False
                
                # Method 1: Click the TH parent (most reliable for Angular Material)
                try:
                    th_parent = select_all_checkbox.find_element(By.XPATH, "ancestor::th[1]")
                    self.driver.execute_script("arguments[0].click();", th_parent)
                    clicked = True
                    print(f"✅ Clicked via TH parent")
                    time.sleep(1)
                except Exception as e1:
                    print(f"⚠️ TH parent click failed: {e1}")
                
                # Method 2: Click the label element
                if not clicked:
                    try:
                        cb_id = select_all_checkbox.get_attribute('id')
                        if cb_id:
                            label = self.driver.find_element(By.XPATH, f"//label[@for='{cb_id}']")
                            self.driver.execute_script("arguments[0].click();", label)
                            clicked = True
                            print(f"✅ Clicked via label[for]")
                            time.sleep(1)
                    except Exception as e2:
                        print(f"⚠️ Label[for] click failed: {e2}")
                
                # Method 3: Click the mat-checkbox inner container
                if not clicked:
                    try:
                        inner = select_all_checkbox.find_element(By.XPATH, "ancestor::mat-checkbox//span[contains(@class,'mat-checkbox-inner-container')]")
                        self.driver.execute_script("arguments[0].click();", inner)
                        clicked = True
                        print(f"✅ Clicked via inner-container")
                        time.sleep(1)
                    except Exception as e3:
                        print(f"⚠️ Inner-container click failed: {e3}")
                
                # Method 4: JS click on input directly (last resort)
                if not clicked:
                    self.driver.execute_script("arguments[0].click();", select_all_checkbox)
                    print(f"✅ Clicked via JS on input")
                    time.sleep(1)
                
                # Wait for selection to process
                time.sleep(3)
                
                # Check if selection worked, if not try alternative methods
                initial_check = select_all_checkbox.is_selected()
                if not initial_check:
                    print(f"⚠️ First click didn't select, trying double-click...")
                    try:
                        th_parent = select_all_checkbox.find_element(By.XPATH, "ancestor::th[1]")
                        # Double click
                        self.driver.execute_script("arguments[0].click();", th_parent)
                        time.sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", th_parent)
                        time.sleep(2)
                        print(f"✅ Double-clicked TH parent")
                        
                        # Check again
                        if not select_all_checkbox.is_selected():
                            print(f"⚠️ Double-click also failed, trying to select individual rows...")
                            # Fallback: Select first 40 rows individually
                            try:
                                row_checkboxes = self.driver.find_elements(By.XPATH, "//tbody//tr//input[@type='checkbox']")
                                print(f"   Found {len(row_checkboxes)} row checkboxes")
                                selected = 0
                                for i, row_cb in enumerate(row_checkboxes[:40]):  # Max 40
                                    try:
                                        if not row_cb.is_selected():
                                            self.driver.execute_script("arguments[0].click();", row_cb)
                                            selected += 1
                                            if i % 10 == 0:
                                                time.sleep(0.5)  # Pause every 10 clicks
                                    except Exception:
                                        pass
                                print(f"✅ Manually selected {selected} row checkboxes")
                                time.sleep(2)
                            except Exception as manual_e:
                                print(f"⚠️ Manual row selection failed: {manual_e}")
                    except Exception as dbl_e:
                        print(f"⚠️ Double-click failed: {dbl_e}")
                
                # Verify the click worked
                new_state = select_all_checkbox.is_selected()
                if not new_state:
                    # Check aria-checked on mat-checkbox
                    try:
                        mat = select_all_checkbox.find_element(By.XPATH, "ancestor::mat-checkbox")
                        aria = (mat.get_attribute('aria-checked') or '').lower()
                        new_state = aria == 'true'
                    except Exception:
                        pass
                print(f"📋 Select-all checkbox new state: {'checked' if new_state else 'unchecked'}")
                self._capture_screenshot("after_select_all")
                
                # Count selected checkboxes to verify
                try:
                    selected_checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' and @checked] | //*[@role='checkbox' and @aria-checked='true']")
                    selected_count = len(selected_checkboxes)
                except:
                    selected_count = "unknown"
                print(f"✅ {selected_count} checkboxes now selected")
                
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
    
    def navigate_to_myappointments(self) -> Dict[str, Any]:
        """Navigate to myappointments page"""
        try:
            print("\n🚗 Navigating to My Appointments page...")
            self.driver.get("https://truckerportal.emodal.com/myappointments")
            print("⏳ Waiting 45 seconds for page to fully load...")
            time.sleep(45)  # Wait for page to fully load before starting operations
            self._capture_screenshot("myappointments_page")
            print("✅ Navigated to My Appointments page")
            return {"success": True}
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def scroll_and_select_appointment_checkboxes(self, mode: str, target_value: Any = None) -> Dict[str, Any]:
        """
        Scroll through appointments and select all checkboxes.
        Optimized flow: only scroll when no new content is found (like timeline search).
        
        Args:
            mode: "infinite", "count", or "id"
            target_value: Number (for count) or appointment ID (for id mode)
        
        Returns:
            Dict with success status and selected_count
        """
        try:
            print(f"\n📜 Starting appointment checkbox selection (mode: {mode})")
            
            selected_count = 0
            scroll_cycles = 0
            no_new_content_count = 0
            max_no_new_content = 3  # Stop after 3 cycles with no new content
            
            while True:
                scroll_cycles += 1
                print(f"\n🔄 Cycle {scroll_cycles} (no new: {no_new_content_count}/{max_no_new_content})")
                
                # Find all checkboxes
                try:
                    checkboxes = self.driver.find_elements(
                        By.XPATH,
                        "//input[@type='checkbox' and contains(@class, 'mat-checkbox-input')]"
                    )
                    print(f"  📊 Found {len(checkboxes)} total checkboxes")
                except Exception as e:
                    print(f"  ⚠️ Error finding checkboxes: {e}")
                    checkboxes = []
                
                # Select unchecked checkboxes
                newly_selected = 0
                for i, checkbox in enumerate(checkboxes):
                    try:
                        # Check if already selected
                        is_checked = checkbox.get_attribute('aria-checked') == 'true'
                        
                        if not is_checked:
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                            time.sleep(0.2)
                            
                            # Try multiple click strategies
                            clicked = False
                            
                            # Strategy 1: Direct click on input
                            try:
                                checkbox.click()
                                clicked = True
                            except:
                                pass
                            
                            # Strategy 2: Click parent mat-checkbox
                            if not clicked:
                                try:
                                    parent = checkbox.find_element(By.XPATH, "./ancestor::mat-checkbox")
                                    parent.click()
                                    clicked = True
                                except:
                                    pass
                            
                            # Strategy 3: JavaScript click on input
                            if not clicked:
                                try:
                                    self.driver.execute_script("arguments[0].click();", checkbox)
                                    clicked = True
                                except:
                                    pass
                            
                            # Strategy 4: JavaScript click on parent
                            if not clicked:
                                try:
                                    parent = checkbox.find_element(By.XPATH, "./ancestor::mat-checkbox")
                                    self.driver.execute_script("arguments[0].click();", parent)
                                    clicked = True
                                except:
                                    pass
                            
                            if clicked:
                                time.sleep(0.2)
                                newly_selected += 1
                                selected_count += 1
                                
                                if selected_count % 10 == 0:  # Print every 10 to reduce log spam
                                    print(f"    ✅ Selected {selected_count} checkboxes so far...")
                                
                                # Check if we've reached target count
                                if mode == "count" and target_value and selected_count >= target_value:
                                    print(f"  🎯 Target count reached: {selected_count} >= {target_value}")
                                    return {"success": True, "selected_count": selected_count}
                                
                    except Exception as e:
                        # Silent fail for individual checkboxes to reduce log spam
                        continue
                
                if newly_selected > 0:
                    print(f"  ✅ Selected {newly_selected} new checkboxes (total: {selected_count})")
                    no_new_content_count = 0
                    # Don't scroll yet - continue checking for more checkboxes first
                else:
                    print(f"  ⏳ No new checkboxes found")
                    no_new_content_count += 1
                    
                    # Only scroll when there's no new content (optimized like timeline)
                    if no_new_content_count < max_no_new_content:
                        print(f"  📜 Scrolling to load more content...")
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.7)  # Short wait like timeline (instead of 3 seconds)
                
                # Check if we should stop
                if no_new_content_count >= max_no_new_content:
                    print(f"  🛑 No new checkboxes for {max_no_new_content} cycles, stopping")
                    break
                
                # For count mode, check if target reached
                if mode == "count" and target_value and selected_count >= target_value:
                    print(f"  🎯 Target count reached: {selected_count}")
                    break
            
            print(f"\n✅ Checkbox selection completed")
            print(f"  Total selected: {selected_count}")
            print(f"  Scroll cycles: {scroll_cycles}")
            
            return {
                "success": True,
                "selected_count": selected_count,
                "scroll_cycles": scroll_cycles
            }
            
        except Exception as e:
            print(f"❌ Checkbox selection failed: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def click_excel_download_button(self) -> Dict[str, Any]:
        """Click the Excel download button and wait for download"""
        try:
            print("\n📥 Clicking Excel download button...")
            self._capture_screenshot("before_excel_click")
            
            # Wait 5 seconds as requested
            print("  ⏳ Waiting 5 seconds before clicking...")
            time.sleep(5)
            
            # Scroll to top to ensure toolbar is visible
            print("  📜 Scrolling to top to reveal toolbar...")
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Try multiple selectors for the Excel download button
            excel_button = None
            selectors = [
                ("//mat-icon[@svgicon='xls']", "svgicon='xls'"),
                ("//mat-icon[contains(@class, 'svg-xls-icon')]", "class contains svg-xls-icon"),
                ("//mat-icon[contains(@class, 'xls')]", "class contains xls"),
                ("//*[name()='svg' and contains(@class, 'xls')]", "svg with xls class"),
                ("//button[contains(@class, 'excel') or contains(@aria-label, 'Excel')]//mat-icon", "button with excel"),
                ("//*[@mattooltip='Excel']", "mattooltip='Excel'"),
                ("//mat-icon[@role='img']/*[name()='svg']", "mat-icon with svg child"),
            ]
            
            for xpath, description in selectors:
                try:
                    print(f"  🔍 Trying selector: {description}")
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed():
                            excel_button = btn
                            print(f"  ✅ Found Excel download button using: {description}")
                            break
                    if excel_button:
                        break
                except Exception as e:
                    print(f"    ⚠️ Selector failed: {e}")
                    continue
            
            if not excel_button:
                # Last resort: look for any visible mat-icon in toolbar area
                print("  🔍 Last resort: Looking for any mat-icon in toolbar...")
                try:
                    toolbar_icons = self.driver.find_elements(By.XPATH, "//mat-toolbar//mat-icon | //div[contains(@class, 'toolbar')]//mat-icon")
                    for icon in toolbar_icons:
                        if icon.is_displayed():
                            # Check if it looks like an Excel icon (has svg child)
                            try:
                                icon.find_element(By.XPATH, ".//*[name()='svg']")
                                excel_button = icon
                                print(f"  ✅ Found potential Excel icon in toolbar")
                                break
                            except:
                                continue
                except:
                    pass
            
            if not excel_button:
                self._capture_screenshot("excel_button_not_found")
                return {"success": False, "error": "Excel download button not found after trying all selectors"}
            
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", excel_button)
            time.sleep(0.5)
            
            # Click the button
            try:
                excel_button.click()
                print("  ✅ Excel download button clicked (regular click)")
            except:
                # Fallback: JavaScript click
                self.driver.execute_script("arguments[0].click();", excel_button)
                print("  ✅ Excel download button clicked (JavaScript click)")
            
            self._capture_screenshot("after_excel_click")
            
            # Wait for download to start
            time.sleep(3)
            
            return {"success": True}
            
        except Exception as e:
            print(f"  ❌ Error clicking Excel button: {e}")
            self._capture_screenshot("excel_click_error")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def scrape_containers_to_excel(self) -> Dict[str, Any]:
        """Extract container data using Ctrl+A Ctrl+C behavior"""
        try:
            import pandas as pd
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            import re
            from selenium.webdriver.common.keys import Keys
            
            print("📊 Extracting container data using select all...")
            self._capture_screenshot("before_scraping")
            
            # Wait for page to be loaded
            time.sleep(2)
            
            # Define expected columns
            columns = [
                'Container #', 'Trade Type', 'Status', 'Holds', 
                'Pregate Ticket#', 'Emodal Pregate Status', 'Gate Status',
                'Origin', 'Destination', 'Current Loc', 'Line', 
                'Vessel Name', 'Vessel Code', 'Voyage', 'Size Type', 
                'Fees', 'LFD/GTD', 'Tags'
            ]
            
            # Extract text using JavaScript selection and copy (same result as Ctrl+A Ctrl+C)
            try:
                # Find searchres div - this contains the table
                searchres = self.driver.find_element(By.XPATH, "//div[@id='searchres']")
                
                # Use JavaScript to select all text in the element and get it
                print("📋 Programmatically selecting all text in table...")
                page_text = self.driver.execute_script("""
                    var element = arguments[0];
                    
                    // Create a range and selection (like Ctrl+A does)
                    var range = document.createRange();
                    range.selectNodeContents(element);
                    
                    var selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                    
                    // Get the selected text (like Ctrl+C would copy)
                    var selectedText = selection.toString();
                    
                    // Clear selection
                    selection.removeAllRanges();
                    
                    return selectedText;
                """, searchres)
                
                print(f"✅ Selected and extracted: {len(page_text)} characters")
                
                # Fallback 1: If selection method didn't work, try innerText
                if not page_text or len(page_text) < 100:
                    print("⚠️ Selection method returned little/no data, trying innerText...")
                    page_text = self.driver.execute_script("return arguments[0].innerText;", searchres)
                    print(f"📄 Extracted {len(page_text)} characters via innerText")
                
                # Fallback 2: Use .text property
                if not page_text or len(page_text) < 100:
                    print("⚠️ innerText failed, trying .text property...")
                    page_text = searchres.text
                    print(f"📄 Extracted {len(page_text)} characters via .text")
                
            except Exception as e:
                print(f"❌ All text extraction methods failed: {e}")
                return {"success": False, "error": f"Could not extract page text: {e}"}
            
            # DEBUG: Save extracted text to file for debugging (RAW TEXT ONLY)
            download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
            os.makedirs(download_dir, exist_ok=True)
            
            debug_text_file = os.path.join(download_dir, "copied_text.txt")
            try:
                with open(debug_text_file, 'w', encoding='utf-8') as f:
                    # Just the raw text - exactly what was copied
                    f.write(page_text)
                print(f"💾 Copied text saved to: {debug_text_file}")
                print(f"   File size: {os.path.getsize(debug_text_file)} bytes")
                print(f"   Characters: {len(page_text)}")
            except Exception as debug_e:
                print(f"⚠️ Could not save copied text file: {debug_e}")
            
            # Parse container data from text
            lines = page_text.split('\n')
            containers_data = []
            
            # Skip header lines - look for "Container #" then "Tags" (last column header)
            start_idx = 0
            found_container_header = False
            for i, line in enumerate(lines):
                if 'Container #' in line:
                    found_container_header = True
                if found_container_header and 'Tags' in line:
                    start_idx = i + 1
                    print(f"✅ Found header section ending at line {i}, data starts at line {start_idx}")
                    break
            
            if start_idx == 0:
                print("⚠️ Header not found, trying to find first container ID")
                # Look for first container ID pattern
                for i, line in enumerate(lines):
                    if re.match(r'^([A-Z]{4}\d{6,7}[A-Z]?)\s*$', line.strip()):
                        start_idx = i
                        print(f"✅ Found first container at line {i}")
                        break
            
            i = start_idx
            while i < len(lines):
                line = lines[i].strip()
                
                # Check if line contains tabs (all data on one line) or just container ID
                if '\t' in line:
                    # Tab-separated format: all fields on one line
                    fields = line.split('\t')
                    fields = [f.strip() for f in fields if f.strip()]  # Remove empty fields
                    
                    # Remove icon text from fields (keyboard_arrow_right, info, more_vert, etc.)
                    icon_texts = ['keyboard_arrow_right', 'info', 'more_vert', 'expand_more', 'expand_less']
                    # Remove standalone icon fields
                    fields = [f for f in fields if f not in icon_texts]
                    # Also remove icon text from within fields (e.g., "info NO" -> "NO")
                    cleaned_fields = []
                    for field in fields:
                        for icon in icon_texts:
                            field = field.replace(icon, '').strip()
                        if field:  # Only add non-empty fields
                            cleaned_fields.append(field)
                    fields = cleaned_fields
                    
                    # First field should be container ID (after removing icons)
                    if fields and re.match(r'^([A-Z]{4}\d{6,7}[A-Z]?)$', fields[0]):
                        container_id_raw = fields[0]
                        container_id_clean = re.sub(r'[A-Z]$', '', container_id_raw)
                        
                        # Build row data from tab-separated fields
                        row_data = {}
                        for idx, field in enumerate(fields):
                            if idx == 0:
                                row_data['Container #'] = container_id_clean
                            elif idx < len(columns):
                                row_data[columns[idx]] = field
                        
                        # Collect Fees, LFD/GTD, Tags from next 3 lines if not in current line
                        if len(row_data) < len(columns):
                            for j in range(i + 1, min(i + 4, len(lines))):
                                next_line = lines[j].strip()
                                if next_line and len(row_data) < len(columns):
                                    row_data[columns[len(row_data)]] = next_line
                        
                        if len(row_data) >= 10:
                            containers_data.append(row_data)
                            if len(containers_data) % 10 == 0:
                                print(f"  Parsed {len(containers_data)} containers...")
                        
                        i += 1
                        continue
                
                # Newline-separated format: each field on its own line
                match = re.match(r'^([A-Z]{4}\d{6,7}[A-Z]?)\s*$', line)
                if match:
                    container_id_raw = match.group(1)
                    container_id_clean = re.sub(r'[A-Z]$', '', container_id_raw)
                    
                    # Collect next 17 fields (18 columns total including container ID)
                    row_data = {'Container #': container_id_clean}
                    
                    # Get the next fields
                    field_idx = 1
                    for j in range(i + 1, min(i + 25, len(lines))):
                        field_line = lines[j].strip()
                        if field_line and field_idx < len(columns):
                            row_data[columns[field_idx]] = field_line
                            field_idx += 1
                            if field_idx >= len(columns):
                                break
                    
                    # Only add if we have all or most fields
                    if len(row_data) >= 10:  # At least 10 fields
                        containers_data.append(row_data)
                        if len(containers_data) % 10 == 0:
                            print(f"  Parsed {len(containers_data)} containers...")
                        i = i + field_idx  # Skip processed lines
                        continue
                
                i += 1
            
            print(f"✅ Parsed {len(containers_data)} containers total")
            
            # DEBUG: Save parsing results to debug file
            try:
                debug_parse_file = os.path.join(download_dir, "parsing_debug.txt")
                with open(debug_parse_file, 'w', encoding='utf-8') as f:
                    f.write("="*70 + "\n")
                    f.write("PARSING DEBUG RESULTS\n")
                    f.write("="*70 + "\n")
                    f.write(f"Total containers parsed: {len(containers_data)}\n")
                    f.write(f"Header start index: {start_idx}\n")
                    f.write(f"Total lines: {len(lines)}\n")
                    f.write("="*70 + "\n\n")
                    
                    if containers_data:
                        f.write("SAMPLE CONTAINERS (first 3):\n\n")
                        for i, container in enumerate(containers_data[:3], 1):
                            f.write(f"{i}. {container.get('Container #', 'N/A')}\n")
                            for key, value in container.items():
                                f.write(f"   {key}: {value}\n")
                            f.write("\n")
                    else:
                        f.write("NO CONTAINERS PARSED!\n\n")
                        f.write("First 50 lines of extracted text:\n")
                        f.write("-"*70 + "\n")
                        for i, line in enumerate(lines[:50], 1):
                            f.write(f"{i:3d}: {repr(line)}\n")
                
                print(f"💾 Parsing debug saved to: {debug_parse_file}")
                print(f"   File size: {os.path.getsize(debug_parse_file)} bytes")
            except Exception as debug_e:
                print(f"⚠️ Could not save parsing debug file: {debug_e}")
            
            # List all files in download directory for verification
            print(f"\n📂 Files in download directory ({download_dir}):")
            try:
                for fname in os.listdir(download_dir):
                    fpath = os.path.join(download_dir, fname)
                    fsize = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                    print(f"   - {fname} ({fsize} bytes)")
            except Exception as list_e:
                print(f"   ⚠️ Could not list files: {list_e}")
            
            if not containers_data:
                return {"success": False, "error": "No container data extracted"}
            
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"containers_scraped_{ts}.xlsx"
            excel_path = os.path.join(download_dir, excel_filename)
            
            # Create DataFrame
            df = pd.DataFrame(containers_data)
            
            # Ensure all columns exist
            for col in columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Reorder columns to match expected format
            df = df[columns]
            
            # Write to Excel with formatting
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Containers', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Containers']
                
                # Format header row
                header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                header_font = Font(color='FFFFFF', bold=True)
                
                for cell in worksheet[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            file_size = os.path.getsize(excel_path)
            print(f"✅ Excel file created: {excel_filename} ({file_size} bytes)")
            self._capture_screenshot("after_scraping")
            
            return {
                "success": True,
                "file_path": excel_path,
                "file_name": excel_filename,
                "file_size": file_size,
                "total_containers": len(containers_data),
                "method": "scraped"
            }
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Scraping failed: {str(e)}"}
    
    def download_excel_file(self) -> Dict[str, Any]:
        """Download Excel file with container data"""
        try:
            print("📥 Looking for Excel download button...")
            self._capture_screenshot("before_export")
            
            # Common selectors for Excel download (expanded)
            excel_selectors = [
                "//a[contains(@href, 'excel') or contains(@href, 'xlsx')]",
                "//button[contains(@class, 'excel') or contains(@title, 'excel') or contains(., 'Excel') or contains(@aria-label,'Excel')]",
                "//*[@aria-label='Export to Excel' or @title='Export to Excel' or contains(., 'Export to Excel')]",
                "//i[contains(@class, 'fa-file-excel')]/..",
                "//i[contains(@class, 'excel-icon')]/..",
                # Angular Material mat-icon with svgicon="xls"
                "//mat-icon[@svgicon='xls']/ancestor::*[self::button or self::a][1]",
                "//mat-icon[contains(@class,'excel-icon')]/ancestor::*[self::button or self::a][1]",
                # SVG group/id for excel icon
                "//g[@id='excel_icon']/ancestor::*[self::button or self::a][1]",
                "//a[contains(@title, 'Export') and contains(@title, 'Excel')]",
                "//button[contains(@title, 'Export') and contains(@title, 'Excel')]",
                "//span[contains(text(), 'Excel') or contains(text(), 'Export')]",
                "(//i[contains(@class,'excel') or contains(@class,'xls') or contains(@class,'download')]/ancestor::button)[1]",
                "(//svg[contains(@class,'excel') or contains(@class,'download')]/ancestor::button)[1]",
                # SVG path provided by user
                "//path[@id='Path_346']/ancestor::*[self::button or self::a][1]",
                "//path[@data-name='Path 346']/ancestor::*[self::button or self::a][1]",
                "//path[contains(@d,'Path 346')]/ancestor::*[self::button or self::a][1]",
                # Generic: green export icon path
                "//path[@fill='#1a8e07']/ancestor::*[self::button or self::a][1]",
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
                    export_candidates = self.driver.find_elements(
                        By.XPATH,
                        "//button[contains(text(), 'Export') or contains(text(), 'Download') or contains(text(), 'Excel')] | "
                        "//a[contains(text(), 'Export') or contains(text(), 'Download') or contains(text(), 'Excel')] | "
                        "//path[@id='Path_346' or @data-name='Path 346' or @fill='#1a8e07']/ancestor::*[self::button or self::a] | "
                        "//mat-icon[@svgicon='xls']/ancestor::*[self::button or self::a] | //g[@id='excel_icon']/ancestor::*[self::button or self::a]"
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
            
            # Set up session-specific download directory under project downloads/
            download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
            try:
                os.makedirs(download_dir, exist_ok=True)
            except Exception as mkdir_e:
                print(f"⚠️ Could not create download directory: {mkdir_e}")
            
            # CRITICAL: Use absolute path for Linux compatibility
            download_dir_abs = os.path.abspath(download_dir)
            print(f"📁 Download directory: {download_dir_abs}")
            
            # Configure active Chrome session to allow downloads into our dir via DevTools
            try:
                self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                    "behavior": "allow",
                    "downloadPath": download_dir_abs  # Must be absolute path
                })
                print(f"✅ Chrome download behavior configured")
            except Exception as cdp_e:
                print(f"⚠️ Could not set download behavior via CDP: {cdp_e}")
            
            # Click the Excel download button
            try:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", excel_button)
                time.sleep(1)
                
                button_text = (excel_button.text or '').strip()
                print(f"📥 Clicking Excel download button: '{button_text}'")
                
                try:
                    excel_button.click()
                except Exception as e_click:
                    print(f"⚠️ Direct click failed: {e_click}. Trying JS click...")
                    try:
                        self.driver.execute_script("arguments[0].click();", excel_button)
                    except Exception:
                        # If excel_button is the path itself, click its clickable ancestor
                        try:
                            ancestor = excel_button.find_element(By.XPATH, "ancestor::*[self::button or self::a][1]")
                            self.driver.execute_script("arguments[0].click();", ancestor)
                        except Exception:
                            raise
                self._capture_screenshot("after_export_click")
                
                # Wait for download to complete
                print("⏳ Waiting for file download...")
                download_timeout = 60  # allow longer for large files
                start_time = time.time()
                downloaded_file = None
                check_count = 0
                
                while (time.time() - start_time) < download_timeout:
                    check_count += 1
                    try:
                        entries = os.listdir(download_dir_abs)
                    except Exception as list_e:
                        print(f"  ⚠️ Could not list directory (attempt {check_count}): {list_e}")
                        entries = []
                    
                    # Any crdownload indicates in-progress
                    in_progress = [f for f in entries if f.endswith('.crdownload')]
                    # Completed known extensions
                    complete_files = [f for f in entries if f.lower().endswith((".xlsx", ".xls", ".csv"))]
                    
                    # Debug output every 10 seconds
                    if check_count % 10 == 0 or complete_files or in_progress:
                        print(f"  📊 Check #{check_count}: {len(entries)} files, {len(in_progress)} in progress, {len(complete_files)} complete")
                        if entries:
                            print(f"     Files: {entries}")
                    
                    if complete_files and not in_progress:
                        # Pick the newest completed file
                        complete_files.sort(key=lambda f: os.path.getmtime(os.path.join(download_dir_abs, f)), reverse=True)
                        downloaded_file = os.path.join(download_dir_abs, complete_files[0])
                        # Additional small grace period to ensure file handlers closed
                        time.sleep(0.5)
                        break
                    
                    time.sleep(1)

                if downloaded_file:
                    file_size = os.path.getsize(downloaded_file)
                    print(f"✅ File downloaded: {os.path.basename(downloaded_file)} ({file_size} bytes)")
                    self._capture_screenshot("after_download")
                    
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

    def search_container(self, container_id: str) -> Dict[str, Any]:
        """Search for a specific container on the containers page"""
        try:
            print(f"🔎 Searching for container: {container_id}")
            self._capture_screenshot("before_search")
            
            # Wait for page to be fully loaded
            self._wait_for_app_ready(15)
            time.sleep(2)
            
            # Try common search input/selectors with more comprehensive options
            search_selectors = [
                # Generic search inputs
                "//input[@placeholder='Search' or contains(@aria-label,'Search')]",
                "//input[contains(@class,'search') or contains(@id,'search')]",
                "//input[contains(@placeholder,'container') or contains(@placeholder,'Container')]",
                "//input[contains(@placeholder,'filter') or contains(@placeholder,'Filter')]",
                # Angular Material form fields
                "//mat-form-field//input",
                "//mat-input//input",
                "//*[@role='search']//input",
                # Generic input fields that might be search
                "//input[@type='text' and not(@readonly)]",
                "//input[not(@type='hidden') and not(@readonly)]",
                # Look for any input that might be a search field
                "//input[contains(@class,'mat-input') or contains(@class,'search') or contains(@class,'filter')]"
            ]
            
            search_input = None
            used_selector = None
            
            for sx in search_selectors:
                try:
                    el = self.driver.find_element(By.XPATH, sx)
                    if el.is_displayed() and el.is_enabled():
                        search_input = el
                        used_selector = sx
                        print(f"✅ Found search input with: {sx}")
                        break
                except Exception as e:
                    print(f"❌ Search selector '{sx}' failed: {e}")
                    continue
            
            if not search_input:
                # Fallback: look for any input field that might be searchable
                try:
                    all_inputs = self.driver.find_elements(By.XPATH, "//input[@type='text' or @type='search']")
                    print(f"🔍 Found {len(all_inputs)} text/search inputs on page")
                    
                    for i, inp in enumerate(all_inputs):
                        try:
                            placeholder = inp.get_attribute("placeholder") or ""
                            aria_label = inp.get_attribute("aria-label") or ""
                            input_id = inp.get_attribute("id") or ""
                            input_class = inp.get_attribute("class") or ""
                            
                            print(f"  Input {i+1}: placeholder='{placeholder}', aria-label='{aria_label}', id='{input_id}', class='{input_class}'")
                            
                            # Check if it looks like a search field
                            if any(keyword in (placeholder + aria_label + input_id + input_class).lower() 
                                   for keyword in ['search', 'filter', 'container', 'find']):
                                search_input = inp
                                used_selector = f"fallback_input_{i+1}"
                                print(f"✅ Using input {i+1} as search field")
                                break
                        except Exception as debug_e:
                            print(f"  Debug error for input {i+1}: {debug_e}")
                            continue
                except Exception as fallback_e:
                    print(f"❌ Fallback input search failed: {fallback_e}")
            
            if not search_input:
                return {"success": False, "error": "Search input not found"}

            # Clear and enter search term
            try:
                search_input.clear()
                time.sleep(0.5)
                search_input.send_keys(container_id)
                time.sleep(0.5)
                
                # Try different ways to trigger search
                try:
                    search_input.send_keys("\n")  # Enter key
                except Exception:
                    pass
                
                # Also try clicking a search button if it exists
                try:
                    search_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@class,'search') or contains(@aria-label,'search') or contains(.,'Search')]")
                    if search_buttons:
                        search_buttons[0].click()
                        print("🔍 Clicked search button")
                except Exception:
                    pass
                
                # Wait for results to load
                print("⏳ Waiting for search results...")
                self._wait_for_app_ready(15)
                time.sleep(2)
                self._capture_screenshot("after_search")
                
                # Verify search worked by checking if container appears on page
                try:
                    container_found = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    if container_found:
                        print(f"✅ Container {container_id} found on page after search")
                        return {"success": True, "selector_used": used_selector}
                except Exception:
                    print(f"⚠️ Container {container_id} not found on page after search")
                    # Don't fail here, let the expand method handle it
                
                return {"success": True, "selector_used": used_selector}
                
            except Exception as e:
                return {"success": False, "error": f"Search input interaction failed: {str(e)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

    def search_container_with_scrolling(self, container_id: str, max_no_new_content_cycles: int = 3) -> Dict[str, Any]:
        """Search for container while progressively scrolling the page to load more rows.
        Returns early when the container is found.
        """
        try:
            print(f"🔎 Progressive search with scrolling for: {container_id}")
            self._capture_screenshot("before_progressive_search")

            # Reuse the robust scrolling setup: iframe, focus
            # Note: Removed window maximization to prevent fullscreen mode
            # Iframe detection (best-effort)
            try:
                frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                switched = False
                for fr in frames:
                    try:
                        self.driver.switch_to.frame(fr)
                        hints = self.driver.find_elements(By.XPATH, "//*[contains(@class,'mat-table') or @role='table' or @role='grid']")
                        if hints:
                            print("  ✅ Switched into iframe containing table content")
                            switched = True
                            break
                        self.driver.switch_to.default_content()
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                if not switched:
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
            except Exception as e:
                print(f"  ⚠️ Iframe detection error: {e}")

            # Focus viewport center
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                self.driver.execute_script("window.focus();")
                vw = self.driver.execute_script("return window.innerWidth;")
                vh = self.driver.execute_script("return window.innerHeight;")
                body_elem = self.driver.find_element(By.TAG_NAME, 'body')
                ActionChains(self.driver).move_to_element_with_offset(body_elem, 1, 1).perform()
                ActionChains(self.driver).move_by_offset(int(vw)//2, int(vh)//2).perform()
            except Exception:
                pass

            # Find the EXACT scrollable container (matinfinitescroll)
            scroll_target = None
            try:
                # Priority 1: id="searchres" with matinfinitescroll
                scroll_target = self.driver.find_element(By.ID, "searchres")
                if scroll_target and scroll_target.is_displayed():
                    print(f"  🎯 Found #searchres (matinfinitescroll)")
                else:
                    scroll_target = None
            except Exception:
                scroll_target = None
            
            # Priority 2: Any element with matinfinitescroll attribute
            if not scroll_target:
                try:
                    scroll_target = self.driver.find_element(By.XPATH, "//*[@matinfinitescroll]")
                    if scroll_target and scroll_target.is_displayed():
                        print(f"  🎯 Found matinfinitescroll element")
                    else:
                        scroll_target = None
                except Exception:
                    scroll_target = None
            
            # Priority 3: search-results class
            if not scroll_target:
                try:
                    scroll_target = self.driver.find_element(By.CLASS_NAME, "search-results")
                    if scroll_target and scroll_target.is_displayed():
                        print(f"  🎯 Found .search-results")
                    else:
                        scroll_target = None
                except Exception:
                    scroll_target = None

            # Helper to attempt to locate the container on the current DOM
            def try_find_container() -> bool:
                try:
                    el = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    if el and el.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.3)
                        print(f"✅ Container {container_id} located on page")
                        self._capture_screenshot("container_found")
                        return True
                except Exception:
                    return False
                return False

            # Initial attempt before any scroll
            if try_find_container():
                return {"success": True, "found": True, "method": "pre_scroll"}

            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
            try:
                if scroll_target:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", scroll_target)
                    ActionChains(self.driver).move_to_element(scroll_target).perform()
            except Exception:
                pass

            previous_seen = 0
            no_new = 0
            cycles = 0
            while no_new < max_no_new_content_cycles:
                cycles += 1
                print(f"🔄 Progressive scroll cycle {cycles} (no-new: {no_new}/{max_no_new_content_cycles})")

                # Try to find container after any new content
                if try_find_container():
                    return {"success": True, "found": True, "method": "during_scroll", "cycles": cycles}

                # Count visible rows to detect growth
                current_seen = previous_seen
                try:
                    rows = self.driver.find_elements(By.XPATH, "//tbody//tr | //mat-row | //div[contains(@class,'row')]")
                    current_seen = len(rows)
                    print(f"  📊 Visible rows: {current_seen}")
                except Exception:
                    pass

                if current_seen > previous_seen:
                    previous_seen = current_seen
                    no_new = 0
                else:
                    no_new += 1

                # HEADLESS-COMPATIBLE: Scroll matinfinitescroll container
                try:
                    print(f"  📜 Scrolling {'matinfinitescroll container' if scroll_target else 'window'}")
                    if scroll_target:
                        # Scroll the specific container with event dispatch
                        for i in range(3):
                            self.driver.execute_script("""
                                var el = arguments[0];
                                el.scrollTop = el.scrollTop + 300;
                                el.dispatchEvent(new Event('scroll', {bubbles: true}));
                                el.dispatchEvent(new WheelEvent('wheel', {deltaY: 300, bubbles: true}));
                                void el.offsetHeight;
                            """, scroll_target)
                            time.sleep(0.35)
                        # Scroll to bottom of container
                        self.driver.execute_script("""
                            var el = arguments[0];
                            el.scrollTop = el.scrollHeight;
                            el.dispatchEvent(new Event('scroll', {bubbles: true}));
                            void el.offsetHeight;
                        """, scroll_target)
                        time.sleep(0.5)
                    else:
                        # Window scrolling fallback
                        for i in range(3):
                            self.driver.execute_script("""
                                window.scrollBy(0, 400);
                                window.dispatchEvent(new Event('scroll', {bubbles: true}));
                                window.dispatchEvent(new WheelEvent('wheel', {deltaY: 400, bubbles: true}));
                            """)
                            time.sleep(0.35)
                        self.driver.execute_script("""
                            window.scrollTo(0, document.body.scrollHeight);
                            window.dispatchEvent(new Event('scroll', {bubbles: true}));
                        """)
                        time.sleep(0.5)
                    print(f"  ✅ Scroll step completed")
                except Exception as e:
                    print(f"  ⚠️ Scroll step failed: {e}")

                # One more attempt after scroll
                if try_find_container():
                    return {"success": True, "found": True, "method": "post_scroll", "cycles": cycles}

                # Short wait to allow DOM to update
                time.sleep(0.7)

            print("⚠️ Container not found after progressive scroll")
            return {"success": False, "error": f"Container '{container_id}' not found after scrolling"}

        except Exception as e:
            return {"success": False, "error": f"Progressive search failed: {str(e)}"}

    def collapse_container_row(self, container_id: str) -> Dict[str, Any]:
        """Collapse the expanded timeline row for the container by clicking the down arrow"""
        try:
            print(f"⤴️ Collapsing row for: {container_id}")
            
            # Wait for page to be ready
            time.sleep(0.5)
            
            # Find the container row
            row = None
            try:
                row = self.driver.find_element(By.XPATH, f"//tr[.//*[contains(text(), '{container_id}')]]")
                print(f"✅ Found container row")
            except Exception:
                try:
                    container_element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    row = container_element.find_element(By.XPATH, "ancestor::tr")
                    print(f"✅ Found container row via element ancestor")
                except Exception as e:
                    print(f"❌ Could not find container row: {e}")
                    return {"success": False, "error": f"Container row not found: {e}"}
            
            # Check if already collapsed (look for right arrow)
            try:
                right_arrow = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_right')]")
                if right_arrow and right_arrow.is_displayed():
                    print("✅ Row is already collapsed (right arrow visible)")
                    return {"success": True, "collapsed": True, "method": "already_collapsed"}
            except Exception:
                pass
            
            # Find the down arrow to click for collapsing
            collapse_element = None
            collapse_selectors = [
                ".//mat-icon[normalize-space(text())='keyboard_arrow_down']",
                ".//mat-icon[normalize-space(text())='expand_less']",
                ".//button[contains(@aria-label,'collapse') or contains(@aria-label,'Collapse')]"
            ]
            
            for selector in collapse_selectors:
                try:
                    collapse_element = row.find_element(By.XPATH, selector)
                    if collapse_element and collapse_element.is_displayed():
                        print(f"✅ Found collapse element via: {selector}")
                        break
                except Exception:
                    continue
            
            if not collapse_element:
                print("⚠️ No collapse arrow found, row might already be collapsed")
                return {"success": True, "collapsed": True, "method": "no_arrow_found"}
            
            # Click to collapse
            try:
                self.driver.execute_script("arguments[0].click();", collapse_element)
                print("✅ JavaScript click executed on collapse element")
                time.sleep(1)
                
                # Verify collapse by checking for right arrow
                try:
                    right_arrow = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_right')]")
                    if right_arrow.is_displayed():
                        print("✅ Collapse verified - arrow changed to right")
                        return {"success": True, "collapsed": True, "method": "collapse_click"}
                except Exception:
                    print("⚠️ Could not verify collapse, but click was executed")
                    return {"success": True, "collapsed": True, "method": "collapse_click_unverified"}
                
            except Exception as e:
                print(f"❌ Failed to click collapse element: {e}")
                return {"success": False, "error": f"Click failed: {e}"}
            
            return {"success": True, "collapsed": True}
            
        except Exception as e:
            print(f"❌ Error collapsing row: {e}")
            return {"success": False, "error": str(e)}
    
    def expand_container_row(self, container_id: str) -> Dict[str, Any]:
        """Expand the timeline row for the container by clicking the arrow if needed"""
        try:
            print(f"⤵️ Expanding row for: {container_id}")
            self._capture_screenshot("before_expand")
            
            # Wait for page to be ready
            self._wait_for_app_ready(10)
            time.sleep(1)
            
            # Try multiple strategies to find the container row
            row = None
            row_found_method = None
            
            # Strategy 1: Look for table row containing the container ID
            try:
                row = self.driver.find_element(By.XPATH, f"//tr[.//*[contains(text(), '{container_id}')]]")
                row_found_method = "table_row_with_text"
                print(f"✅ Found container row via table row search")
            except Exception:
                pass
            
            # Strategy 2: Look for any element with container ID, then find its row
            if not row:
                try:
                    container_element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    row = container_element.find_element(By.XPATH, "ancestor::tr")
                    row_found_method = "element_ancestor_row"
                    print(f"✅ Found container row via element ancestor")
                except Exception:
                    pass
            
            # Strategy 3: Look for div-based rows (not table)
            if not row:
                try:
                    row = self.driver.find_element(By.XPATH, f"//div[contains(@class,'row') and .//*[contains(text(), '{container_id}')]]")
                    row_found_method = "div_row_with_text"
                    print(f"✅ Found container row via div row search")
                except Exception:
                    pass
            
            # Strategy 4: Look for any container with the ID
            if not row:
                try:
                    container_element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    # Try to find a parent that looks like a row
                    row = container_element.find_element(By.XPATH, "ancestor::*[contains(@class,'row') or contains(@class,'item') or contains(@class,'container')]")
                    row_found_method = "element_ancestor_container"
                    print(f"✅ Found container row via element ancestor container")
                except Exception:
                    pass
            
            if not row:
                # Debug: show what we can find
                try:
                    all_elements_with_id = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{container_id}')]")
                    print(f"🔍 Found {len(all_elements_with_id)} elements containing '{container_id}'")
                    
                    for i, el in enumerate(all_elements_with_id[:5]):  # Show first 5
                        try:
                            tag_name = el.tag_name
                            text_content = el.text[:50] if el.text else ""
                            parent_tag = el.find_element(By.XPATH, "./..").tag_name
                            print(f"  Element {i+1}: {tag_name} (parent: {parent_tag}) - '{text_content}...'")
                        except Exception:
                            pass
                except Exception:
                    pass
                
                return {"success": False, "error": f"Container row not found for '{container_id}'"}

            print(f"📋 Container row found via: {row_found_method}")
            self._capture_screenshot("row_found")

            # Look for expand/collapse indicators in the row
            expand_selectors = [
                # Material Design icons
                ".//mat-icon[normalize-space(text())='keyboard_arrow_right']",
                ".//mat-icon[normalize-space(text())='expand_more']",
                ".//mat-icon[normalize-space(text())='add']",
                ".//mat-icon[normalize-space(text())='+']",
                # Generic arrow icons
                ".//i[contains(@class,'arrow-right') or contains(@class,'expand')]",
                ".//span[contains(@class,'arrow-right') or contains(@class,'expand')]",
                # Button elements
                ".//button[contains(@class,'expand') or contains(@class,'toggle')]",
                ".//button[contains(@aria-label,'expand') or contains(@aria-label,'Expand')]",
                # Generic clickable elements that might expand
                ".//*[@role='button' and (contains(@class,'expand') or contains(@class,'toggle'))]",
                # Look for any clickable element in the row
                ".//button | .//a | .//*[@role='button']"
            ]
            
            expand_element = None
            used_expand_selector = None
            
            # First check if already expanded (look for down arrow or expanded content)
            try:
                # Check for down arrow (v icon)
                down_arrow = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_down') or contains(text(),'expand_less')]")
                if down_arrow and down_arrow.is_displayed():
                    print("✅ Row is already expanded (down arrow visible)")
                    self._capture_screenshot("row_already_expanded")
                    return {"success": True, "expanded": True, "method": "already_expanded"}
            except Exception:
                pass
            
            # Also check if timeline content is visible (more reliable)
            try:
                timeline_visible = row.find_element(By.XPATH, "./following-sibling::*[1]//div[contains(@class,'timeline') or contains(@class,'containerflow')]")
                if timeline_visible and timeline_visible.is_displayed():
                    print("✅ Row is already expanded (timeline visible)")
                    self._capture_screenshot("row_already_expanded")
                    return {"success": True, "expanded": True, "method": "already_expanded"}
            except Exception:
                pass
            
            # Look for expand elements
            for selector in expand_selectors:
                try:
                    el = row.find_element(By.XPATH, selector)
                    if el.is_displayed():
                        expand_element = el
                        used_expand_selector = selector
                        print(f"✅ Found expand element with: {selector}")
                        break
                except Exception:
                    continue
            
            if not expand_element:
                # Fallback: try clicking anywhere on the row
                try:
                    print("⚠️ No specific expand element found, trying to click the row itself")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", row)
                    time.sleep(0.5)
                    row.click()
                    self._wait_for_app_ready(5)
                    self._capture_screenshot("row_clicked")
                    return {"success": True, "expanded": True, "method": "row_click"}
                except Exception as e:
                    return {"success": False, "error": f"Could not click row: {str(e)}"}
            
            # Click the expand element
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", expand_element)
                time.sleep(0.5)
                
                # Try different click methods
                clicked = False
                try:
                    expand_element.click()
                    clicked = True
                    print("✅ Direct click succeeded")
                except Exception as e1:
                    print(f"⚠️ Direct click failed: {e1}")
                    try:
                        self.driver.execute_script("arguments[0].click();", expand_element)
                        clicked = True
                        print("✅ JavaScript click succeeded")
                    except Exception as e2:
                        print(f"⚠️ JavaScript click failed: {e2}")
                
                if not clicked:
                    return {"success": False, "error": "Could not click expand element"}
                
                # Wait for expansion to complete
                self._wait_for_app_ready(10)
                time.sleep(2)  # Give more time for animation
                self._capture_screenshot("after_expand_click")
                
                # Verify expansion worked by checking if arrow changed
                expansion_verified = False
                
                try:
                    # Method 1: Check if arrow changed from right (>) to down (v)
                    try:
                        down_arrow = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_down')]")
                        if down_arrow.is_displayed():
                            print("✅ Expansion verified - arrow changed to down")
                            expansion_verified = True
                    except Exception:
                        pass
                    
                    # Method 2: Check if timeline/detail content appeared
                    if not expansion_verified:
                        try:
                            # Look for timeline in next sibling or within row
                            timeline = row.find_element(By.XPATH, "./following-sibling::*[1]//div[contains(@class,'timeline') or contains(@class,'containerflow')]")
                            if timeline and timeline.is_displayed():
                                print("✅ Expansion verified - timeline visible")
                                expansion_verified = True
                        except Exception:
                            pass
                    
                    # Method 3: Check if arrow is still showing "right" (means click didn't work)
                    if not expansion_verified:
                        try:
                            right_arrow_still_there = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_right')]")
                            if right_arrow_still_there.is_displayed():
                                print("⚠️ Arrow still showing 'right' - expansion failed, retrying...")
                                # Retry the click
                                try:
                                    self.driver.execute_script("arguments[0].click();", expand_element)
                                    time.sleep(3)
                                    self._capture_screenshot("after_retry_click")
                                    
                                    # Check again
                                    try:
                                        down_arrow = row.find_element(By.XPATH, ".//mat-icon[contains(text(),'keyboard_arrow_down')]")
                                        if down_arrow.is_displayed():
                                            print("✅ Expansion verified after retry")
                                            expansion_verified = True
                                    except:
                                        pass
                                except Exception as retry_e:
                                    print(f"⚠️ Retry click failed: {retry_e}")
                        except Exception:
                            # Arrow not found at all, might be expanded
                            pass
                    
                    if expansion_verified:
                        return {"success": True, "expanded": True, "method": "expand_click_verified", "selector_used": used_expand_selector}
                    else:
                        print("⚠️ Could not verify expansion - arrow state unclear")
                        return {"success": False, "error": "Expansion verification failed - arrow did not change to down position"}
                    
                except Exception as verify_e:
                    print(f"⚠️ Verification error: {verify_e}")
                    return {"success": False, "error": f"Expansion verification failed: {str(verify_e)}"}
                
            except Exception as click_e:
                return {"success": False, "error": f"Expand click failed: {str(click_e)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Expand failed: {str(e)}"}

    def check_pregate_status(self) -> Dict[str, Any]:
        """
        Determine if container passed Pregate by checking timeline line colors.
        
        Method 1 (Primary): Check DOM classes
            - dividerflowcolor = colored line = passed Pregate
            - horizontalconflow = gray line = not passed yet
        
        Method 2 (Fallback): Image processing on cropped screenshot
            - Analyze line color under Pregate milestone
        
        Returns:
            Dict with success, passed_pregate (bool), method, and optional screenshot
        """
        try:
            print("🔍 Checking Pregate status...")
            
            # Find the timeline container
            timeline_container = None
            try:
                timeline_container = self.driver.find_element(By.XPATH, "//app-containerflow")
                print("  ✅ Found timeline container")
            except Exception:
                try:
                    timeline_container = self.driver.find_element(By.XPATH, "//div[contains(@class,'timeline-container')]")
                except Exception:
                    return {"success": False, "error": "Timeline container not found"}
            
            # Find Pregate element
            pregate_element = None
            pregate_selectors = [
                ".//span[normalize-space(.)='Pregate']",
                ".//span[contains(text(),'Pregate')]",
                ".//*[normalize-space(.)='Pregate']"
            ]
            
            for selector in pregate_selectors:
                try:
                    pregate_element = timeline_container.find_element(By.XPATH, selector)
                    print(f"  ✅ Found Pregate element")
                    break
                except Exception:
                    continue
            
            if not pregate_element:
                return {"success": False, "error": "Pregate milestone not found"}
            
            # METHOD 1: Check DOM classes (fast and reliable)
            try:
                print("  🔍 Method 1: Checking timeline divider classes...")
                
                # Find the parent row containing Pregate
                pregate_row = pregate_element.find_element(By.XPATH, "./ancestor::div[contains(@fxlayout,'row')][1]")
                
                # Look for the timeline divider in this row or adjacent rows
                # The divider can be before or after the milestone
                divider = None
                
                # Try to find divider in the same row
                try:
                    divider = pregate_row.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                except:
                    # Try previous row
                    try:
                        prev_row = pregate_row.find_element(By.XPATH, "./preceding-sibling::div[contains(@fxlayout,'row')][1]")
                        divider = prev_row.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                    except:
                        # Try next row
                        try:
                            next_row = pregate_row.find_element(By.XPATH, "./following-sibling::div[contains(@fxlayout,'row')][1]")
                            divider = next_row.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                        except:
                            pass
                
                if divider:
                    divider_classes = divider.get_attribute("class")
                    print(f"  📋 Divider classes: {divider_classes}")
                    
                    # Check if line is colored (passed) or gray (not passed)
                    if 'dividerflowcolor' in divider_classes and 'horizontalconflow' not in divider_classes:
                        print("  ✅ Line is COLORED - Container passed Pregate")
                        return {
                            "success": True,
                            "passed_pregate": True,
                            "method": "dom_class_check",
                            "divider_classes": divider_classes
                        }
                    elif 'horizontalconflow' in divider_classes:
                        print("  ⏳ Line is GRAY - Container has NOT passed Pregate yet")
                        return {
                            "success": True,
                            "passed_pregate": False,
                            "method": "dom_class_check",
                            "divider_classes": divider_classes
                        }
                    else:
                        print(f"  ⚠️ Unknown divider class pattern: {divider_classes}")
                else:
                    print("  ⚠️ Could not find timeline divider in DOM")
            
            except Exception as dom_e:
                print(f"  ⚠️ DOM check failed: {dom_e}")
            
            # METHOD 2: Fallback to image processing
            print("  🖼️ Method 2: Using image processing fallback...")
            return self._check_pregate_by_image()
            
        except Exception as e:
            print(f"  ❌ Error checking Pregate status: {e}")
            return {"success": False, "error": str(e)}
    
    def extract_full_timeline(self) -> Dict[str, Any]:
        """
        Extract all timeline milestones with their dates and status.
        
        Returns:
            Dict with success and timeline array of {milestone, date, status}
            Timeline is in reverse chronological order (newest first)
        """
        try:
            print("📋 Extracting full timeline...")
            
            # Find the timeline container
            timeline_container = None
            try:
                timeline_container = self.driver.find_element(By.XPATH, "//app-containerflow")
                print("  ✅ Found timeline container")
            except Exception:
                try:
                    timeline_container = self.driver.find_element(By.XPATH, "//div[contains(@class,'timeline-container')]")
                except Exception:
                    return {"success": False, "error": "Timeline container not found"}
            
            # Find all milestone rows
            try:
                milestone_rows = timeline_container.find_elements(By.XPATH, ".//div[@fxlayout='row']")
                print(f"  📊 Found {len(milestone_rows)} timeline rows")
            except Exception as e:
                return {"success": False, "error": f"Could not find timeline rows: {str(e)}"}
            
            timeline_data = []
            
            for idx, row in enumerate(milestone_rows):
                try:
                    # Find milestone label (name)
                    milestone_labels = row.find_elements(By.XPATH, ".//span[contains(@class,'location-details-label')]")
                    
                    if len(milestone_labels) >= 2:
                        # First span is the milestone name, second is the date
                        milestone_name = milestone_labels[0].text.strip()
                        milestone_date = milestone_labels[1].text.strip()
                        
                        # Skip if it's just an arrow icon
                        if not milestone_name or milestone_name in ['arrow_drop_up', 'arrow_drop_down']:
                            continue
                        
                        # Find divider to determine status
                        status = "pending"
                        try:
                            divider = row.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                            divider_classes = divider.get_attribute("class")
                            
                            # Check if line is colored (completed) or gray (pending)
                            if 'dividerflowcolor' in divider_classes and 'horizontalconflow' not in divider_classes:
                                status = "completed"
                            elif 'horizontalconflow' in divider_classes or 'dividerflowcolor2' in divider_classes:
                                status = "pending"
                        except Exception:
                            # If no divider found, assume pending
                            pass
                        
                        timeline_data.append({
                            "milestone": milestone_name,
                            "date": milestone_date,
                            "status": status
                        })
                        
                        print(f"    {idx+1}. {milestone_name} | {milestone_date} | {status}")
                
                except Exception as row_e:
                    # Skip rows that don't have the expected structure
                    continue
            
            if not timeline_data:
                return {"success": False, "error": "No timeline milestones found"}
            
            # Reverse the array to get newest first (timeline is bottom-to-top in HTML)
            timeline_data.reverse()
            
            print(f"  ✅ Extracted {len(timeline_data)} milestones (newest first)")
            
            return {
                "success": True,
                "timeline": timeline_data,
                "milestone_count": len(timeline_data)
            }
            
        except Exception as e:
            print(f"  ❌ Error extracting timeline: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_pregate_by_image(self) -> Dict[str, Any]:
        """
        Fallback method: Capture screenshot of Pregate area and analyze line color.
        
        Returns:
            Dict with success, passed_pregate (bool), method, and screenshot path
        """
        try:
            print("    📸 Capturing Pregate area for image analysis...")
            
            # Find timeline and Pregate element
            timeline_container = self.driver.find_element(By.XPATH, "//app-containerflow | //div[contains(@class,'timeline-container')]")
            pregate_element = timeline_container.find_element(By.XPATH, ".//*[normalize-space(.)='Pregate']")
            
            # Scroll into view
            self.driver.execute_script("""
                arguments[0].scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                    inline: 'center'
                });
            """, pregate_element)
            time.sleep(2)
            
            # Get Pregate container with the line
            try:
                pregate_container = pregate_element.find_element(By.XPATH, "./ancestor::div[contains(@class,'curr-loc-div')]")
            except:
                pregate_container = pregate_element
            
            # Get location
            location = pregate_container.location
            size = pregate_container.size
            
            # Take screenshot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            full_screenshot_path = os.path.join(self.screens_dir, f"{timestamp}_full_page.png")
            self.driver.save_screenshot(full_screenshot_path)
            
            from PIL import Image
            import numpy as np
            
            img = Image.open(full_screenshot_path)
            
            # Crop tightly around Pregate text and line below it
            # Small area: just the text + line underneath
            padding_horizontal = 20
            padding_top = 10
            padding_bottom = 50  # More space below to capture the line
            
            left = max(0, location['x'] - padding_horizontal)
            top = max(0, location['y'] - padding_top)
            right = min(img.width, location['x'] + size['width'] + padding_horizontal)
            bottom = min(img.height, location['y'] + size['height'] + padding_bottom)
            
            cropped_img = img.crop((left, top, right, bottom))
            
            # Save cropped image
            cropped_path = os.path.join(self.screens_dir, f"{timestamp}_pregate_line.png")
            cropped_img.save(cropped_path)
            print(f"    ✅ Cropped Pregate image: {os.path.basename(cropped_path)}")
            
            # Analyze line color in bottom portion of image
            img_array = np.array(cropped_img)
            
            # Focus on bottom 30% of image (where the line should be)
            height = img_array.shape[0]
            line_region = img_array[int(height * 0.7):, :]  # Bottom 30%
            
            # Calculate average color in line region
            avg_color = np.mean(line_region, axis=(0, 1))
            
            # Calculate brightness (grayscale value)
            brightness = np.mean(avg_color)
            
            print(f"    📊 Line region analysis:")
            print(f"       Average color (RGB): {avg_color}")
            print(f"       Brightness: {brightness:.1f}")
            
            # Threshold: Dark/colored line (< 180) = passed, Light/gray (>= 180) = not passed
            threshold = 180
            
            if brightness < threshold:
                print(f"    ✅ Line is DARK (brightness {brightness:.1f} < {threshold}) - Container passed Pregate")
                passed = True
            else:
                print(f"    ⏳ Line is LIGHT (brightness {brightness:.1f} >= {threshold}) - Container has NOT passed Pregate")
                passed = False
            
            # Clean up full screenshot
            try:
                os.remove(full_screenshot_path)
            except:
                pass
            
            return {
                "success": True,
                "passed_pregate": passed,
                "method": "image_processing",
                "screenshot_path": cropped_path,
                "screenshot_name": os.path.basename(cropped_path),
                "analysis": {
                    "average_brightness": float(brightness),
                    "threshold": threshold,
                    "average_color_rgb": [float(c) for c in avg_color]
                }
            }
            
        except Exception as e:
            print(f"    ❌ Image processing failed: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Image processing failed: {str(e)}"}

    def capture_pregate_screenshot(self) -> Dict[str, Any]:
        """
        Locate the Pregate milestone in the horizontal timeline and capture a screenshot.
        The timeline is a horizontal flow that may require scrolling right.
        
        Returns:
            Dict with success, screenshot_path, and element location info
        """
        try:
            print("📸 Locating Pregate milestone in horizontal timeline...")
            
            # Find the timeline container first
            timeline_container = None
            try:
                timeline_container = self.driver.find_element(By.XPATH, "//app-containerflow")
                print("  ✅ Found app-containerflow timeline container")
            except Exception:
                try:
                    timeline_container = self.driver.find_element(By.XPATH, "//div[contains(@class,'timeline-container')]")
                    print("  ✅ Found timeline-container")
                except Exception:
                    return {"success": False, "error": "Timeline container not found"}
            
            # Find Pregate element with multiple possible selectors
            pregate_selectors = [
                ".//span[normalize-space(.)='Pregate']",
                ".//span[contains(text(),'Pregate')]",
                ".//span[normalize-space(.)='pregate']",
                ".//span[contains(text(),'pregate')]",
                ".//*[normalize-space(.)='Pregate']"
            ]
            
            pregate_element = None
            for selector in pregate_selectors:
                try:
                    pregate_element = timeline_container.find_element(By.XPATH, selector)
                    print(f"  ✅ Found Pregate using: {selector}")
                    break
                except Exception:
                    continue
            
            if not pregate_element:
                # Fallback: search all milestone labels in timeline
                all_milestones = timeline_container.find_elements(By.XPATH, ".//span[contains(@class,'location-details-label')]")
                print(f"  🔍 Searching {len(all_milestones)} milestone labels...")
                for milestone in all_milestones:
                    try:
                        text = milestone.text.strip()
                        if 'pregate' in text.lower():
                            pregate_element = milestone
                            print(f"  ✅ Found Pregate in milestone: '{text}'")
                            break
                    except Exception:
                        continue
            
            if not pregate_element:
                return {"success": False, "error": "Pregate milestone not found in timeline"}
            
            # Scroll the Pregate element into view (handles horizontal scrolling)
            print("  🔄 Scrolling Pregate element into view...")
            try:
                # Scroll element to center of viewport (works for horizontal scrolling too)
                self.driver.execute_script("""
                    arguments[0].scrollIntoView({
                        behavior: 'smooth',
                        block: 'center',
                        inline: 'center'
                    });
                """, pregate_element)
                time.sleep(2)  # Wait for smooth scroll to complete
                print("  ✅ Pregate element scrolled into view")
            except Exception as scroll_e:
                print(f"  ⚠️ Scroll warning: {scroll_e}")
            
            # Get the parent milestone container (includes the divider and dates)
            try:
                pregate_container = pregate_element.find_element(By.XPATH, "./ancestor::div[contains(@class,'curr-loc-div')]")
                print("  ✅ Found Pregate milestone container")
            except Exception:
                pregate_container = pregate_element
                print("  ⚠️ Using Pregate text element directly")
            
            # Get element location and size
            location = pregate_container.location
            size = pregate_container.size
            
            print(f"  📐 Pregate location: ({location['x']}, {location['y']}), size: {size['width']}x{size['height']}")
            
            # Expand the crop area to include context (more horizontal padding for timeline)
            vertical_padding = 150  # pixels above/below
            horizontal_padding = 300  # more padding left/right to show timeline flow
            
            # Get full page screenshot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            full_screenshot_path = os.path.join(self.screens_dir, f"{timestamp}_full_timeline.png")
            self.driver.save_screenshot(full_screenshot_path)
            print(f"  📸 Full screenshot saved")
            
            # Crop the image around Pregate element
            from PIL import Image
            img = Image.open(full_screenshot_path)
            
            # Calculate crop box with padding (wider for horizontal timeline)
            left = max(0, location['x'] - horizontal_padding)
            top = max(0, location['y'] - vertical_padding)
            right = min(img.width, location['x'] + size['width'] + horizontal_padding)
            bottom = min(img.height, location['y'] + size['height'] + vertical_padding)
            
            crop_width = right - left
            crop_height = bottom - top
            
            print(f"  📐 Crop area: ({left}, {top}) to ({right}, {bottom}) = {crop_width}x{crop_height}px")
            
            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))
            
            # Save cropped image
            cropped_path = os.path.join(self.screens_dir, f"{timestamp}_pregate_timeline.png")
            cropped_img.save(cropped_path)
            print(f"  ✅ Cropped timeline screenshot saved: {os.path.basename(cropped_path)}")
            print(f"  📊 Final image size: {crop_width}x{crop_height}px")
            
            # Remove full screenshot to save space
            try:
                os.remove(full_screenshot_path)
            except:
                pass
            
            return {
                "success": True,
                "screenshot_path": cropped_path,
                "screenshot_name": os.path.basename(cropped_path),
                "element_location": {
                    "x": location['x'],
                    "y": location['y'],
                    "width": size['width'],
                    "height": size['height']
                },
                "crop_area": {
                    "left": left,
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                    "width": crop_width,
                    "height": crop_height
                }
            }
            
        except Exception as e:
            print(f"  ❌ Error capturing Pregate screenshot: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def get_booking_number(self, container_id: str) -> Dict[str, Any]:
        """
        Extract booking number from expanded container row.
        
        Args:
            container_id: Container ID to search for
            
        Returns:
            Dict with success status and booking_number (or None if not found)
        """
        try:
            print(f"\n📋 Extracting booking number for container: {container_id}")
            self._capture_screenshot("before_booking_extraction")
            
            # Find the expanded row (should already be expanded)
            expanded_row = None
            try:
                expanded_row = self.driver.find_element(
                    By.XPATH,
                    f"//tr[contains(@class, 'expanded')]"
                )
                print("  ✅ Found expanded row with class 'expanded'")
            except Exception:
                print("  ⚠️ No expanded row found, attempting to find by container ID")
                # Try to find the detail section directly
                try:
                    expanded_row = self.driver.find_element(
                        By.XPATH,
                        f"//tr[.//td[contains(text(), '{container_id}')]]/following-sibling::tr[contains(@class, 'detail')]"
                    )
                    print("  ✅ Found detail row for container")
                except Exception:
                    # Try finding the entire expanded section by looking for the container text
                    try:
                        # Look for any element containing the container ID, then find the booking section
                        container_elem = self.driver.find_element(
                            By.XPATH,
                            f"//*[contains(text(), '{container_id}')]"
                        )
                        # Scroll it into view
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container_elem)
                        time.sleep(0.5)
                        # Now try to find the booking section in the visible area
                        expanded_row = self.driver.find_element(
                            By.XPATH,
                            "//body"  # Use body as fallback to search entire page
                        )
                        print("  ✅ Using full page search for booking number")
                    except Exception as e:
                        return {"success": False, "error": f"Could not find expanded row: {str(e)}"}
            
            # Look for "Booking #" label and its corresponding value
            # The structure is: <div class="field-label">Booking #</div> followed by <div class="field-data btn-link">VALUE</div>
            try:
                # Method 1: Find by label text "Booking #" and get the field-data right under it
                print("  🔍 Searching for 'Booking #' label...")
                
                # Try with ng-star-inserted class (from actual HTML)
                booking_label = None
                try:
                    booking_label = expanded_row.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'field-label') and contains(@class, 'ng-star-inserted') and contains(text(), 'Booking #')]"
                    )
                    print("  ✅ Found 'Booking #' label (with ng-star-inserted)")
                except:
                    # Fallback to generic search
                    booking_label = expanded_row.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'field-label') and contains(text(), 'Booking #')]"
                    )
                    print("  ✅ Found 'Booking #' label")
                
                # The value should be right under the label (following-sibling with btn-link class)
                try:
                    # Try following-sibling with btn-link class (from actual HTML)
                    booking_value_elem = booking_label.find_element(
                        By.XPATH,
                        "following-sibling::div[contains(@class, 'field-data') and contains(@class, 'btn-link') and contains(@class, 'ng-star-inserted')]"
                    )
                    print("  ✅ Found field-data as following-sibling (with btn-link)")
                except:
                    try:
                        # Try without ng-star-inserted
                        booking_value_elem = booking_label.find_element(
                            By.XPATH,
                            "following-sibling::div[contains(@class, 'field-data') and contains(@class, 'btn-link')]"
                        )
                        print("  ✅ Found field-data as following-sibling (btn-link, no ng-star)")
                    except:
                        try:
                            # Try any following-sibling field-data
                            booking_value_elem = booking_label.find_element(
                                By.XPATH,
                                "following-sibling::div[contains(@class, 'field-data')]"
                            )
                            print("  ✅ Found field-data as following-sibling")
                        except:
                            try:
                                # Try within same parent container
                                parent = booking_label.find_element(By.XPATH, "..")
                                booking_value_elem = parent.find_element(
                                    By.XPATH,
                                    ".//div[contains(@class, 'field-data')]"
                                )
                                print("  ✅ Found field-data within parent")
                            except:
                                # Try next sibling of parent
                                parent = booking_label.find_element(By.XPATH, "..")
                                booking_value_elem = parent.find_element(
                                    By.XPATH,
                                    "following-sibling::*//div[contains(@class, 'field-data')]"
                                )
                                print("  ✅ Found field-data in following parent sibling")
                
                booking_number = booking_value_elem.text.strip()
                print(f"  📋 Extracted text: '{booking_number}'")
                
                if booking_number and booking_number != "N/A" and booking_number != "":
                    print(f"  ✅ Booking number found: {booking_number}")
                    return {
                        "success": True,
                        "booking_number": booking_number,
                        "container_id": container_id
                    }
                else:
                    print("  ℹ️ Booking number field exists but is empty or N/A")
                    return {
                        "success": True,
                        "booking_number": None,
                        "container_id": container_id,
                        "message": "Booking number not available"
                    }
                    
            except Exception as e:
                print(f"  ℹ️ Method 1 failed: {str(e)}")
                # Try Method 2: Look for any field-data with btn-link class (clickable booking numbers)
                try:
                    print("  🔍 Trying method 2: Looking for clickable field-data...")
                    booking_value_elem = expanded_row.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'field-data') and contains(@class, 'btn-link')]"
                    )
                    booking_number = booking_value_elem.text.strip()
                    print(f"  📋 Extracted text (method 2): '{booking_number}'")
                    
                    if booking_number and booking_number != "N/A" and booking_number != "":
                        print(f"  ✅ Booking number found (method 2): {booking_number}")
                        return {
                            "success": True,
                            "booking_number": booking_number,
                            "container_id": container_id
                        }
                except Exception as e2:
                    print(f"  ℹ️ Method 2 failed: {str(e2)}")
                
                # Try Method 3: Direct text search near "Booking #" label
                try:
                    print("  🔍 Trying method 3: Direct search for Booking # text...")
                    # Find all elements containing "Booking #"
                    booking_labels = expanded_row.find_elements(
                        By.XPATH,
                        ".//*[contains(text(), 'Booking #')]"
                    )
                    
                    for label in booking_labels:
                        print(f"    Found label element: {label.tag_name}")
                        # Get parent and look for any nearby text that looks like a booking number
                        parent = label.find_element(By.XPATH, "..")
                        parent_text = parent.text.strip()
                        print(f"    Parent text: '{parent_text}'")
                        
                        # Try to extract booking number from parent text
                        lines = parent_text.split('\n')
                        for i, line in enumerate(lines):
                            if 'Booking #' in line and i + 1 < len(lines):
                                potential_booking = lines[i + 1].strip()
                                if potential_booking and potential_booking != "N/A" and len(potential_booking) > 3:
                                    print(f"  ✅ Booking number found (method 3): {potential_booking}")
                                    return {
                                        "success": True,
                                        "booking_number": potential_booking,
                                        "container_id": container_id
                                    }
                except Exception as e3:
                    print(f"  ℹ️ Method 3 failed: {str(e3)}")
                
                # Try Method 4: Look for clickable blue text (booking numbers are often styled as links)
                try:
                    print("  🔍 Trying method 4: Looking for blue/clickable text near Booking #...")
                    # Find the booking label first
                    booking_section = expanded_row.find_element(
                        By.XPATH,
                        ".//*[contains(text(), 'Booking #')]/.."
                    )
                    # Look for any clickable or styled text nearby
                    clickable_elements = booking_section.find_elements(
                        By.XPATH,
                        ".//*[@style or contains(@class, 'link') or contains(@class, 'btn')]"
                    )
                    
                    for elem in clickable_elements:
                        text = elem.text.strip()
                        # Booking numbers typically have letters and numbers
                        if text and len(text) > 5 and any(c.isalpha() for c in text) and any(c.isdigit() for c in text):
                            print(f"  ✅ Booking number found (method 4): {text}")
                            return {
                                "success": True,
                                "booking_number": text,
                                "container_id": container_id
                            }
                except Exception as e4:
                    print(f"  ℹ️ Method 4 failed: {str(e4)}")
                
                # Method 5: Full page text extraction (like get_containers)
                try:
                    print("  🔍 Method 5: Full page text extraction...")
                    
                    # Get all text content from the entire page using JavaScript (like get_containers)
                    all_text = self.driver.execute_script("""
                        // Select all text on the page (like Ctrl+A)
                        var range = document.createRange();
                        range.selectNodeContents(document.body);
                        var selection = window.getSelection();
                        selection.removeAllRanges();
                        selection.addRange(range);
                        
                        // Get the selected text
                        var selectedText = selection.toString();
                        
                        // Clear selection
                        selection.removeAllRanges();
                        
                        return selectedText;
                    """)
                    
                    print(f"  📋 Full page text extracted: '{all_text[:300]}...'")
                    
                    # Look for the specific pattern: "Booking #" followed by the booking number
                    import re
                    
                    # Method 5a: Line-by-line search (most reliable)
                    print("  🔍 Method 5a: Line-by-line search...")
                    lines = all_text.split('\n')
                    print(f"  📋 Total lines: {len(lines)}")
                    
                    for i, line in enumerate(lines):
                        if 'Booking #' in line:
                            print(f"  📍 Found 'Booking #' at line {i+1}: '{line.strip()}'")
                            
                            # Look for the pattern: Booking # -> Status -> Booking Number
                            # Check the next few lines for a booking number pattern
                            for j in range(1, 6):  # Check next 5 lines
                                if i + j < len(lines):
                                    potential_line = lines[i + j].strip()
                                    print(f"     Checking line {i+j+1}: '{potential_line}'")
                                    
                                    # Check if this line contains a booking number pattern
                                    if re.match(r'^[A-Z0-9]{8,12}$', potential_line):
                                        print(f"  🎯 Found booking number (method 5a): {potential_line}")
                                        return {
                                            "success": True,
                                            "booking_number": potential_line,
                                            "container_id": container_id
                                        }
                                    
                                    # Also check if the line contains a booking number within it
                                    booking_match = re.search(r'\b([A-Z0-9]{8,12})\b', potential_line)
                                    if booking_match:
                                        booking_number = booking_match.group(1)
                                        print(f"  🎯 Found booking number in line (method 5a): {booking_number}")
                                        return {
                                            "success": True,
                                            "booking_number": booking_number,
                                            "container_id": container_id
                                        }
                    
                    # Method 5b: Regex pattern - "Booking #" followed by status, then booking number
                    print("  🔍 Method 5b: Regex pattern search...")
                    booking_pattern = r'Booking\s*#\s*\n\s*[A-Z\s]+\n\s*([A-Z0-9]{8,12})'
                    match = re.search(booking_pattern, all_text, re.MULTILINE)
                    
                    if match:
                        booking_number = match.group(1).strip()
                        print(f"  🎯 Found booking number (method 5b): {booking_number}")
                        return {
                            "success": True,
                            "booking_number": booking_number,
                            "container_id": container_id
                        }
                    
                    # Method 5c: More flexible regex - "Booking #" followed by any text, then booking number
                    print("  🔍 Method 5c: Flexible regex search...")
                    booking_flexible_pattern = r'Booking\s*#\s*\n\s*.*?\n\s*([A-Z0-9]{8,12})'
                    match = re.search(booking_flexible_pattern, all_text, re.MULTILINE | re.DOTALL)
                    
                    if match:
                        booking_number = match.group(1).strip()
                        print(f"  🎯 Found booking number (method 5c): {booking_number}")
                        return {
                            "success": True,
                            "booking_number": booking_number,
                            "container_id": container_id
                        }
                    
                    # Method 5d: Find "Booking #" and get the next alphanumeric string
                    print("  🔍 Method 5d: Next alphanumeric search...")
                    booking_simple_pattern = r'Booking\s*#\s*[^\w]*([A-Z0-9]{8,12})'
                    match = re.search(booking_simple_pattern, all_text)
                    
                    if match:
                        booking_number = match.group(1).strip()
                        print(f"  🎯 Found booking number (method 5d): {booking_number}")
                        return {
                            "success": True,
                            "booking_number": booking_number,
                            "container_id": container_id
                        }
                    
                    print("  ℹ️ Method 5: No booking number found in full page text")
                    return {
                        "success": True,
                        "booking_number": None,
                        "container_id": container_id,
                        "message": "Booking number not found in full page text"
                    }
                        
                except Exception as e5:
                    print(f"  ℹ️ Method 5 failed: {str(e5)}")
                    
                    # Method 6: Image-based approach (fallback if Tesseract is available)
                    try:
                        print("  🔍 Method 6: Image-based booking number extraction...")
                        
                        # Take a full screenshot first
                        full_screenshot_path = self._capture_screenshot("booking_extraction_full")
                        
                        # Use image processing to find "Booking" text and extract booking number
                        booking_number = self._extract_booking_number_from_image(full_screenshot_path)
                        
                        if booking_number and booking_number != "N/A" and booking_number != "":
                            print(f"  ✅ Booking number found (method 6 - image): {booking_number}")
                            return {
                                "success": True,
                                "booking_number": booking_number,
                                "container_id": container_id
                            }
                        else:
                            print("  ℹ️ Method 6: No booking number found in image")
                            return {
                                "success": True,
                                "booking_number": None,
                                "container_id": container_id,
                                "message": "Booking number not found in image"
                            }
                            
                    except Exception as e6:
                        print(f"  ℹ️ Method 6 failed: {str(e6)}")
                
                # Booking number doesn't exist for this container
                print("  ℹ️ Booking number field does not exist for this container")
                self._capture_screenshot("booking_not_found")
                return {
                    "success": True,
                    "booking_number": None,
                    "container_id": container_id,
                    "message": "Booking number field not found"
                }
                
        except Exception as e:
            print(f"  ❌ Error extracting booking number: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def analyze_timeline(self) -> Dict[str, Any]:
        """Determine if status is before or after Pregate based on timeline DOM structure and progress indicators"""
        try:
            print("🧭 Analyzing timeline...")
            
            # Find timeline container
            timeline_container = None
            try:
                timeline_container = self.driver.find_element(By.XPATH, "//div[contains(@class,'timeline-container')]")
                print("  ✅ Found timeline container")
            except Exception:
                try:
                    timeline_container = self.driver.find_element(By.XPATH, "//app-containerflow")
                    print("  ✅ Found app-containerflow")
                except Exception:
                    return {"success": False, "error": "Timeline container not found"}

            # Get all divider elements in order (top to bottom)
            try:
                dividers = timeline_container.find_elements(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                print(f"  📊 Found {len(dividers)} timeline dividers")
            except Exception as e:
                return {"success": False, "error": f"Could not find timeline dividers: {str(e)}"}

            # Find Pregate milestone row and its divider
            pregate_divider = None
            pregate_index = -1
            pregate_date_na = True
            
            try:
                # Find the Pregate row with multiple possible text variations
                pregate_selectors = [
                    "//span[normalize-space(.)='Pregate']",
                    "//span[contains(text(),'Pregate')]",
                    "//span[normalize-space(.)='pregate']",
                    "//span[contains(text(),'pregate')]",
                    "//*[normalize-space(.)='Pregate']",
                    "//*[contains(text(),'Pregate')]"
                ]
                
                pregate_row = None
                for selector in pregate_selectors:
                    try:
                        pregate_element = self.driver.find_element(By.XPATH, selector)
                        pregate_row = pregate_element.find_element(By.XPATH, "ancestor::div[contains(@class,'fxlayout')][1]")
                        print(f"  ✅ Found Pregate using selector: {selector}")
                        break
                    except Exception:
                        continue
                
                if not pregate_row:
                    # Fallback: look for any milestone that might be Pregate
                    all_milestones = self.driver.find_elements(By.XPATH, "//span[contains(@class,'location-details-label')]")
                    print(f"  🔍 Found {len(all_milestones)} milestone labels, checking for Pregate...")
                    for milestone in all_milestones:
                        try:
                            text = milestone.text.strip()
                            print(f"    - '{text}'")
                            if 'pregate' in text.lower():
                                try:
                                    # Try multiple ancestor patterns
                                    ancestor_patterns = [
                                        "ancestor::div[contains(@class,'fxlayout')][1]",
                                        "ancestor::div[contains(@class,'fxlayout')]",
                                        "ancestor::div[contains(@class,'row')][1]",
                                        "ancestor::div[contains(@class,'row')]",
                                        "ancestor::div[1]",
                                        ".."
                                    ]
                                    
                                    for pattern in ancestor_patterns:
                                        try:
                                            pregate_row = milestone.find_element(By.XPATH, pattern)
                                            print(f"  ✅ Found Pregate in text: '{text}' using pattern: {pattern}")
                                            break
                                        except Exception:
                                            continue
                                    else:
                                        print(f"  ⚠️ Found Pregate text but couldn't find parent row")
                                        continue
                                    break
                                except Exception as e:
                                    print(f"  ⚠️ Error processing Pregate milestone: {e}")
                                    continue
                        except Exception:
                            continue
                
                if not pregate_row:
                    raise Exception("Pregate milestone not found in any form")
                
                # Find the divider within this row - based on the HTML structure you provided
                pregate_divider = None
                try:
                    # Look for the divider in the same row structure as shown in your HTML
                    pregate_divider = pregate_row.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                except Exception:
                    # If not found, look for it in the parent structure
                    try:
                        # The divider might be in a sibling div
                        parent = pregate_row.find_element(By.XPATH, "./..")
                        pregate_divider = parent.find_element(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                    except Exception:
                        # Last resort: look for any divider near this milestone
                        try:
                            # Find all dividers and match by position
                            all_dividers = timeline_container.find_elements(By.XPATH, ".//div[contains(@class,'timeline-divider')]")
                            print(f"  🔍 Found {len(all_dividers)} total dividers, trying to match by position...")
                            
                            # Get the position of the Pregate milestone
                            pregate_rect = self.driver.execute_script("return arguments[0].getBoundingClientRect();", pregate_row)
                            pregate_y = pregate_rect['top']
                            
                            # Find the closest divider
                            closest_divider = None
                            min_distance = float('inf')
                            
                            for i, divider in enumerate(all_dividers):
                                try:
                                    div_rect = self.driver.execute_script("return arguments[0].getBoundingClientRect();", divider)
                                    div_y = div_rect['top']
                                    distance = abs(div_y - pregate_y)
                                    
                                    if distance < min_distance:
                                        min_distance = distance
                                        closest_divider = divider
                                        print(f"    Divider {i}: distance={distance:.1f}px")
                                except Exception:
                                    continue
                            
                            if closest_divider:
                                pregate_divider = closest_divider
                                print(f"  ✅ Found closest divider with distance {min_distance:.1f}px")
                            else:
                                raise Exception("No divider found near Pregate milestone")
                                
                        except Exception as e:
                            print(f"  ⚠️ Could not find divider near Pregate: {e}")
                            raise Exception(f"Could not locate timeline divider for Pregate milestone: {str(e)}")
                
                if not pregate_divider:
                    raise Exception("Could not locate timeline divider for Pregate milestone")
                
                # Get its index in the ordered list
                for i, div in enumerate(dividers):
                    if div == pregate_divider:
                        pregate_index = i
                        break
                
                # Check if Pregate has a real date (not N/A)
                try:
                    pregate_date_span = pregate_row.find_element(By.XPATH, ".//span[contains(@class,'location-details-label') and contains(@class,'p-top-5')]")
                    pregate_date_text = pregate_date_span.text.strip()
                    pregate_date_na = pregate_date_text == "N/A" or pregate_date_text == ""
                    print(f"  📅 Pregate date: '{pregate_date_text}' (N/A: {pregate_date_na})")
                except Exception:
                    print("  ⚠️ Could not read Pregate date")
                
                print(f"  📍 Pregate divider found at index: {pregate_index}")
                
            except Exception as e:
                print(f"  ⚠️ Could not locate Pregate milestone: {e}")
                return {"success": False, "error": f"Pregate milestone not found: {str(e)}"}

            # Analyze divider states (colored = reached/active)
            colored_indices = []
            divider_states = []
            
            for i, divider in enumerate(dividers):
                try:
                    classes = divider.get_attribute("class") or ""
                    is_colored = "dividerflowcolor" in classes and "horizontalconflow" not in classes
                    is_neutral = "horizontalconflow" in classes
                    
                    divider_states.append({
                        "index": i,
                        "classes": classes,
                        "is_colored": is_colored,
                        "is_neutral": is_neutral
                    })
                    
                    if is_colored:
                        colored_indices.append(i)
                        print(f"  🎯 Colored divider at index {i}: {classes}")
                    elif is_neutral:
                        print(f"  ⚪ Neutral divider at index {i}: {classes}")
                    else:
                        print(f"  ❓ Unknown divider at index {i}: {classes}")
                        
                except Exception as e:
                    print(f"  ⚠️ Error analyzing divider {i}: {e}")

            # Determine status based on divider progression
            max_colored_index = max(colored_indices) if colored_indices else -1
            print(f"  📊 Max colored divider index: {max_colored_index}, Pregate index: {pregate_index}")

            # Primary decision: class-based progression
            if max_colored_index >= pregate_index:
                status = "after_pregate"
                method = "class_progression"
                print(f"  ✅ After Pregate: colored divider at {max_colored_index} >= Pregate at {pregate_index}")
            else:
                status = "before_pregate"
                method = "class_progression"
                print(f"  ⏳ Before Pregate: max colored at {max_colored_index} < Pregate at {pregate_index}")

            # Fallback: check milestone dates
            later_milestones_with_dates = []
            if status == "before_pregate":
                try:
                    # Check known later milestones for real dates
                    later_milestones = [
                        "Ready for pick up",
                        "Departed Terminal", 
                        "Arrived at customer",
                        "Discharged"
                    ]
                    
                    for milestone in later_milestones:
                        try:
                            milestone_row = self.driver.find_element(By.XPATH, f"//span[normalize-space(.)='{milestone}']/ancestor::div[contains(@class,'fxlayout')][1]")
                            date_span = milestone_row.find_element(By.XPATH, ".//span[contains(@class,'location-details-label') and contains(@class,'p-top-5')]")
                            date_text = date_span.text.strip()
                            if date_text != "N/A" and date_text != "":
                                later_milestones_with_dates.append(milestone)
                                print(f"  📅 {milestone} has date: {date_text}")
                        except Exception:
                            pass
                    
                    if later_milestones_with_dates:
                        status = "after_pregate"
                        method = "date_fallback"
                        print(f"  ✅ After Pregate (date fallback): {later_milestones_with_dates} have dates")
                        
                except Exception as e:
                    print(f"  ⚠️ Date fallback failed: {e}")

            # Additional check: if Pregate itself has a date, it's definitely after
            if not pregate_date_na:
                status = "after_pregate"
                method = "pregate_date"
                print(f"  ✅ After Pregate: Pregate has real date")

            self._capture_screenshot("timeline_analysis")
            
            return {
                "success": True,
                "status": status,
                "method": method,
                "signals": {
                    "pregate_index": pregate_index,
                    "max_colored_index": max_colored_index,
                    "pregate_date_na": pregate_date_na,
                    "later_milestones_with_dates": later_milestones_with_dates,
                    "total_dividers": len(dividers),
                    "colored_dividers": len(colored_indices),
                    "divider_states": divider_states
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Timeline analysis failed: {str(e)}"}


def create_browser_session(username: str, password: str, captcha_api_key: str, keep_alive: bool = False) -> BrowserSession:
    """Create a new authenticated browser session"""
    
    # Generate session ID
    session_id = f"session_{int(time.time())}_{hash(username)}"
    
    print(f"🌐 Creating browser session: {session_id}")
    
    # Create a unique Chrome user data dir per session to avoid profile-in-use
    temp_profile_dir = tempfile.mkdtemp(prefix="emodal_profile_")
    # Use the existing login handler but with a unique profile dir
    login_handler = EModalLoginHandler(captcha_api_key, use_vpn_profile=False, auto_close=False, user_data_dir=temp_profile_dir)
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
        
        # Handle reCAPTCHA - allow manual override if it takes too long
        print("🔒 Handling reCAPTCHA...")
        print("   💡 TIP: If it takes too long, press CTRL+C to switch to manual mode")
        
        recaptcha_result = None
        manual_override = False
        
        try:
            recaptcha_result = login_handler._handle_recaptcha()
        except KeyboardInterrupt:
            print(f"\n⚠️ reCAPTCHA auto-solve interrupted by user (CTRL+C)")
            manual_override = True
            recaptcha_result = type('obj', (object,), {'success': False, 'error_message': 'User interrupted - manual mode requested'})()
        except Exception as e:
            print(f"⚠️ reCAPTCHA exception: {e}")
            recaptcha_result = type('obj', (object,), {'success': False, 'error_message': str(e)})()
        
        if not recaptcha_result.success:
            print(f"\n⚠️ reCAPTCHA auto-solve failed: {recaptcha_result.error_message}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"❓ Do you want to solve reCAPTCHA manually?")
            print(f"   Press ENTER within 10 seconds to solve manually...")
            print(f"   (Or wait 10 seconds to abort)")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Wait for user input with timeout
            import select
            import sys
            
            user_wants_manual = False
            try:
                # Windows-compatible timeout input
                if sys.platform == 'win32':
                    import msvcrt
                    import time as time_module
                    start_time = time_module.time()
                    while time_module.time() - start_time < 10:
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            if key == b'\r':  # Enter key
                                user_wants_manual = True
                                break
                        time_module.sleep(0.1)
                else:
                    # Unix-based systems
                    ready, _, _ = select.select([sys.stdin], [], [], 10)
                    if ready:
                        sys.stdin.readline()
                        user_wants_manual = True
            except Exception as e:
                print(f"⚠️ Input timeout error: {e}")
            
            if user_wants_manual:
                print(f"\n✅ Manual mode activated!")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"📋 Instructions:")
                print(f"   1. Solve the reCAPTCHA in the browser window")
                print(f"   2. Press ENTER when done to continue...")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Wait indefinitely for user to press Enter
                try:
                    input()  # This will wait until Enter is pressed
                    print(f"✅ Continuing with login process...")
                except Exception as e:
                    print(f"⚠️ Input error: {e}")
                    login_handler.driver.quit()
                    raise Exception(f"Manual reCAPTCHA solve interrupted: {e}")
            else:
                print(f"\n❌ No response within 10 seconds - aborting session")
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
        
        # Wait for login to complete and land on an authenticated app window
        time.sleep(2)
        # Switch to the newest window (OIDC may open a new tab/window)
        try:
            handles = login_handler.driver.window_handles
            if handles:
                login_handler.driver.switch_to.window(handles[-1])
        except Exception:
            pass

        # Prime the app root to establish app context if we’re still on Identity
        try:
            url_check = (login_handler.driver.current_url or "").lower()
            title_check = (login_handler.driver.title or "").lower()
        except Exception:
            url_check, title_check = "", ""

        if ("identity" in url_check) or ("signin-oidc" in url_check) or ("identity" in title_check):
            try:
                login_handler.driver.get("https://ecp2.emodal.com/")
                time.sleep(2)
                # Switch again to latest, just in case
                handles = login_handler.driver.window_handles
                if handles:
                    login_handler.driver.switch_to.window(handles[-1])
                # Wait for app to fully boot
                try:
                    WebDriverWait(login_handler.driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                except Exception:
                    pass
                try:
                    # Best-effort SPA readiness
                    end = time.time() + 20
                    while time.time() < end:
                        try:
                            ready = login_handler.driver.execute_script("return document.readyState") == 'complete'
                            if ready:
                                break
                        except Exception:
                            pass
                        time.sleep(0.3)
                except Exception:
                    pass
            except Exception:
                pass

        # Verify we're logged in (heuristic)
        current_url = (login_handler.driver.current_url or "").lower()
        current_title = (login_handler.driver.title or "")
        # Accept various eModal domains as valid login
        valid_domains = ["ecp2.emodal.com", "account.emodal.com", "truckerportal.emodal.com"]
        is_valid_url = any(domain in current_url for domain in valid_domains) and ("identity" not in current_url)
        
        if is_valid_url:
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
            # Login verification failed - offer manual intervention
            print(f"\n⚠️ Login verification failed!")
            print(f"   Current URL: {current_url}")
            print(f"   Current Title: {current_title}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"❓ Do you want to complete login manually?")
            print(f"   Press ENTER within 10 seconds to complete manually...")
            print(f"   (Or wait 10 seconds to abort)")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Wait for user input with timeout
            import sys
            user_wants_manual = False
            try:
                # Windows-compatible timeout input
                if sys.platform == 'win32':
                    import msvcrt
                    import time as time_module
                    start_time = time_module.time()
                    while time_module.time() - start_time < 10:
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            if key == b'\r':  # Enter key
                                user_wants_manual = True
                                break
                        time_module.sleep(0.1)
                else:
                    # Unix-based systems
                    import select
                    ready, _, _ = select.select([sys.stdin], [], [], 10)
                    if ready:
                        sys.stdin.readline()
                        user_wants_manual = True
            except Exception as e:
                print(f"⚠️ Input timeout error: {e}")
            
            if user_wants_manual:
                print(f"\n✅ Manual login mode activated!")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"📋 Instructions:")
                print(f"   1. Complete the login in the browser window")
                print(f"   2. Wait until you see the eModal dashboard")
                print(f"   3. Press ENTER when done to continue...")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Wait indefinitely for user to press Enter
                try:
                    input()  # This will wait until Enter is pressed
                    print(f"✅ Continuing with session creation...")
                    
                    # Re-verify after manual login
                    current_url = (login_handler.driver.current_url or "").lower()
                    current_title = (login_handler.driver.title or "")
                    
                    # Accept various eModal domains as valid login
                    valid_domains = ["ecp2.emodal.com", "account.emodal.com", "truckerportal.emodal.com"]
                    is_valid_url = any(domain in current_url for domain in valid_domains) and ("identity" not in current_url)
                    
                    if is_valid_url:
                        print(f"✅ Session {session_id} authenticated successfully (manual)")
                        
                        # Create session object
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
                        print(f"❌ Still not logged in after manual intervention")
                        login_handler.driver.quit()
                        raise Exception(f"Manual login failed. URL: {current_url}")
                        
                except Exception as e:
                    print(f"⚠️ Input error: {e}")
                    login_handler.driver.quit()
                    raise Exception(f"Manual login interrupted: {e}")
            else:
                print(f"\n❌ No response within 10 seconds - aborting session")
                login_handler.driver.quit()
                raise Exception(f"Login verification failed. URL: {current_url}, Title: {current_title}")
            
    except Exception as e:
        # Exception occurred during login process - offer manual intervention
        print(f"\n⚠️ Login process failed with exception: {str(e)}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"❓ Do you want to complete login manually?")
        print(f"   Press ENTER within 10 seconds to complete manually...")
        print(f"   (Or wait 10 seconds to abort)")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Wait for user input with timeout
        import sys
        user_wants_manual = False
        try:
            # Windows-compatible timeout input
            if sys.platform == 'win32':
                import msvcrt
                import time as time_module
                start_time = time_module.time()
                while time_module.time() - start_time < 10:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\r':  # Enter key
                            user_wants_manual = True
                            break
                    time_module.sleep(0.1)
            else:
                # Unix-based systems
                import select
                ready, _, _ = select.select([sys.stdin], [], [], 10)
                if ready:
                    sys.stdin.readline()
                    user_wants_manual = True
        except Exception as input_error:
            print(f"⚠️ Input timeout error: {input_error}")
        
        if user_wants_manual and login_handler.driver:
            print(f"\n✅ Manual login mode activated!")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"📋 Instructions:")
            print(f"   1. Complete the login in the browser window")
            print(f"   2. Solve any reCAPTCHA or other challenges")
            print(f"   3. Wait until you see the eModal dashboard")
            print(f"   4. Press ENTER when done to continue...")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Wait indefinitely for user to press Enter
            try:
                input()  # This will wait until Enter is pressed
                print(f"✅ Continuing with session creation...")
                
                # Verify login after manual intervention
                try:
                    current_url = (login_handler.driver.current_url or "").lower()
                    current_title = (login_handler.driver.title or "")
                    
                    # Accept various eModal domains as valid login
                    valid_domains = ["ecp2.emodal.com", "account.emodal.com", "truckerportal.emodal.com"]
                    is_valid_url = any(domain in current_url for domain in valid_domains) and ("identity" not in current_url)
                    
                    if is_valid_url:
                        print(f"✅ Session {session_id} authenticated successfully (manual recovery)")
                        
                        # Create session object
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
                        print(f"❌ Still not logged in after manual intervention")
                        print(f"   URL: {current_url}")
                        print(f"   Title: {current_title}")
                        login_handler.driver.quit()
                        raise Exception(f"Manual login failed. URL: {current_url}")
                        
                except Exception as verify_error:
                    print(f"⚠️ Verification error: {verify_error}")
                    login_handler.driver.quit()
                    raise verify_error
                    
            except Exception as input_error:
                print(f"⚠️ Input error: {input_error}")
                login_handler.driver.quit()
                raise Exception(f"Manual login interrupted: {input_error}")
        else:
            print(f"\n❌ No response within 10 seconds - aborting session")
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


def cleanup_old_files():
    """
    Clean up files older than 24 hours from downloads and screenshots directories.
    This runs periodically to save storage space.
    """
    try:
        now = time.time()
        cutoff_time = now - (24 * 60 * 60)  # 24 hours ago
        
        total_deleted = 0
        total_size_freed = 0
        
        # Clean downloads directory
        if os.path.exists(DOWNLOADS_DIR):
            for root, dirs, files in os.walk(DOWNLOADS_DIR, topdown=False):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        file_mtime = os.path.getmtime(filepath)
                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            total_deleted += 1
                            total_size_freed += file_size
                    except Exception as e:
                        logger.warning(f"Failed to delete {filepath}: {e}")
                
                # Remove empty directories
                for name in dirs:
                    dirpath = os.path.join(root, name)
                    try:
                        if not os.listdir(dirpath):  # if empty
                            os.rmdir(dirpath)
                    except Exception:
                        pass
        
        # Clean screenshots directory
        if os.path.exists(SCREENSHOTS_DIR):
            for root, dirs, files in os.walk(SCREENSHOTS_DIR, topdown=False):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        file_mtime = os.path.getmtime(filepath)
                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            total_deleted += 1
                            total_size_freed += file_size
                    except Exception as e:
                        logger.warning(f"Failed to delete {filepath}: {e}")
                
                # Remove empty directories
                for name in dirs:
                    dirpath = os.path.join(root, name)
                    try:
                        if not os.listdir(dirpath):  # if empty
                            os.rmdir(dirpath)
                    except Exception:
                        pass
        
        if total_deleted > 0:
            size_mb = total_size_freed / (1024 * 1024)
            logger.info(f"🗑️ Cleanup: Deleted {total_deleted} files older than 24h, freed {size_mb:.2f} MB")
        else:
            logger.debug("🗑️ Cleanup: No old files to delete")
            
    except Exception as e:
        logger.error(f"⚠️ Cleanup error: {e}")


def periodic_cleanup_task():
    """Background task that runs cleanup every hour"""
    while True:
        try:
            time.sleep(3600)  # Sleep for 1 hour
            cleanup_old_files()
            cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"⚠️ Periodic cleanup task error: {e}")
            time.sleep(60)  # Wait 1 minute before retrying


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
        "max_sessions": MAX_CONCURRENT_SESSIONS,
        "session_capacity": f"{len(active_sessions)}/{MAX_CONCURRENT_SESSIONS}",
        "persistent_sessions": len(persistent_sessions),
        "timestamp": datetime.now().isoformat()
    })


def release_session_after_operation(session_id: str):
    """Mark session as not in use after operation completes"""
    if session_id and session_id in active_sessions:
        active_sessions[session_id].mark_not_in_use()
        logger.info(f"🔓 Session {session_id} marked as not in use")


@app.route('/get_session', methods=['POST'])
def get_or_create_session():
    """
    Get existing session or create new keep-alive session
    
    Request JSON:
        - username: E-Modal username
        - password: E-Modal password
        - captcha_api_key: 2captcha API key
    
    Response:
        - session_id: Session ID to use in subsequent requests
        - is_new: Whether this is a newly created session
        - username: Associated username
        - created_at: Session creation timestamp
        - expires_at: null (keep-alive sessions don't expire)
    """
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        captcha_api_key = data.get('captcha_api_key')
        
        if not all([username, password, captcha_api_key]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: username, password, captcha_api_key"
            }), 400
        
        logger.info(f"Session request for user: {username}")
        
        # Check if session already exists for these credentials
        existing_session = find_session_by_credentials(username, password)
        
        if existing_session:
            existing_session.update_last_used()
            return jsonify({
                "success": True,
                "session_id": existing_session.session_id,
                "is_new": False,
                "username": existing_session.username,
                "created_at": existing_session.created_at.isoformat(),
                "expires_at": None,  # Keep-alive sessions don't expire
                "message": "Using existing persistent session"
            })
        
        # Create new session
        logger.info(f"Creating new persistent session for user: {username}")
        
        # Ensure we have capacity (evict LRU if at limit)
        if not ensure_session_capacity():
            return jsonify({
                "success": False,
                "error": "Failed to allocate session capacity"
            }), 500
        
        session_id = f"session_{int(time.time())}_{hash(username)}"
        cred_hash = get_credentials_hash(username, password)
        
        # Create unique temp profile directory for this session
        temp_profile_dir = tempfile.mkdtemp(prefix=f"emodal_session_{session_id}_")
        logger.info(f"Created temp profile: {temp_profile_dir}")
        
        # Authenticate with unique profile
        handler = EModalLoginHandler(
            captcha_api_key=captcha_api_key,
            use_vpn_profile=False,  # Don't use default profile (causes conflicts)
            auto_close=False,  # Keep browser open for persistent session
            user_data_dir=temp_profile_dir
        )
        
        login_result = handler.login(username, password)
        if not login_result.success:
            # Login failed - offer manual intervention before cleanup
            print(f"\n⚠️ Authentication failed: {login_result.error_type if login_result.error_type else 'Unknown error'}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"❓ Do you want to complete login manually?")
            print(f"   Press ENTER within 10 seconds to complete manually...")
            print(f"   (Or wait 10 seconds to abort)")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Wait for user input with timeout
            import sys
            user_wants_manual = False
            try:
                # Windows-compatible timeout input
                if sys.platform == 'win32':
                    import msvcrt
                    import time as time_module
                    start_time = time_module.time()
                    while time_module.time() - start_time < 10:
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            if key == b'\r':  # Enter key
                                user_wants_manual = True
                                break
                        time_module.sleep(0.1)
                else:
                    # Unix-based systems
                    import select
                    ready, _, _ = select.select([sys.stdin], [], [], 10)
                    if ready:
                        sys.stdin.readline()
                        user_wants_manual = True
            except Exception as input_error:
                print(f"⚠️ Input timeout error: {input_error}")
            
            if user_wants_manual and handler.driver:
                print(f"\n✅ Manual login mode activated!")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"📋 Instructions:")
                print(f"   1. Complete the login in the browser window")
                print(f"   2. Solve any reCAPTCHA or other challenges")
                print(f"   3. Wait until you see the eModal dashboard")
                print(f"   4. Press ENTER when done to continue...")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Wait indefinitely for user to press Enter
                try:
                    input()  # This will wait until Enter is pressed
                    print(f"✅ Continuing with session creation...")
                    
                    # Verify login after manual intervention
                    try:
                        current_url = (handler.driver.current_url or "").lower()
                        current_title = (handler.driver.title or "")
                        
                        # Accept various eModal domains as valid login
                        valid_domains = ["ecp2.emodal.com", "account.emodal.com", "truckerportal.emodal.com"]
                        is_valid_url = any(domain in current_url for domain in valid_domains) and ("identity" not in current_url)
                        
                        if is_valid_url:
                            print(f"✅ Session authenticated successfully (manual recovery)")
                            
                            # Create browser session with keep_alive=True
                            browser_session = BrowserSession(
                                session_id=session_id,
                                driver=handler.driver,
                                username=username,
                                created_at=datetime.now(),
                                last_used=datetime.now(),
                                keep_alive=True,
                                credentials_hash=cred_hash,
                                last_refresh=datetime.now()
                            )
                            
                            active_sessions[session_id] = browser_session
                            persistent_sessions[cred_hash] = session_id
                            
                            logger.info(f"✅ Created persistent session: {session_id} for user: {username} (manual)")
                            
                            return jsonify({
                                "success": True,
                                "session_id": session_id,
                                "is_new": True,
                                "username": username,
                                "created_at": browser_session.created_at.isoformat(),
                                "expires_at": None,
                                "message": "Session created successfully via manual login"
                            })
                        else:
                            print(f"❌ Still not logged in after manual intervention")
                            print(f"   URL: {current_url}")
                            print(f"   Title: {current_title}")
                            # Clean up
                            try:
                                handler.driver.quit()
                                shutil.rmtree(temp_profile_dir, ignore_errors=True)
                            except:
                                pass
                            return jsonify({
                                "success": False,
                                "error": "Manual login failed - not on eModal dashboard"
                            }), 401
                            
                    except Exception as verify_error:
                        print(f"⚠️ Verification error: {verify_error}")
                        # Clean up
                        try:
                            handler.driver.quit()
                            shutil.rmtree(temp_profile_dir, ignore_errors=True)
                        except:
                            pass
                        return jsonify({
                            "success": False,
                            "error": f"Verification failed: {str(verify_error)}"
                        }), 401
                        
                except Exception as input_error:
                    print(f"⚠️ Input error: {input_error}")
                    # Clean up
                    try:
                        handler.driver.quit()
                        shutil.rmtree(temp_profile_dir, ignore_errors=True)
                    except:
                        pass
                    return jsonify({
                        "success": False,
                        "error": f"Manual login interrupted: {str(input_error)}"
                    }), 401
            else:
                # No manual intervention or timeout
                print(f"\n❌ No response within 10 seconds - aborting session")
                # Clean up temp profile on failure
                try:
                    handler.driver.quit()
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
                except:
                    pass
                return jsonify({
                    "success": False,
                    "error": "Authentication failed",
                    "details": str(login_result.error_type) if login_result.error_type else "Unknown error"
                }), 401
        
        # Create browser session with keep_alive=True
        browser_session = BrowserSession(
            session_id=session_id,
            driver=handler.driver,
            username=username,
            created_at=datetime.now(),
            last_used=datetime.now(),
            keep_alive=True,
            credentials_hash=cred_hash,
            last_refresh=datetime.now()
        )
        
        active_sessions[session_id] = browser_session
        persistent_sessions[cred_hash] = session_id
        
        logger.info(f"✅ Created persistent session: {session_id} for user: {username}")
        logger.info(f"📊 Active sessions: {len(active_sessions)}/{MAX_CONCURRENT_SESSIONS}")
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "is_new": True,
            "username": username,
            "created_at": browser_session.created_at.isoformat(),
            "expires_at": None,  # Keep-alive sessions don't expire
            "message": "New persistent session created"
        })
        
    except Exception as e:
        logger.error(f"Error in get_or_create_session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/get_containers', methods=['POST'])
def get_containers():
    """
    Get containers data as Excel download
    
    Expected JSON:
    {
        "session_id": "session_XXX"  (optional) - Use existing session, skip login
        OR
        "username": "your_username",
        "password": "your_password", 
        "captcha_api_key": "your_2captcha_key",
        
        "infinite_scrolling": true/false  (default: true) - Load all containers
        "target_count": 500  (optional) - Stop when this many containers loaded
        "target_container_id": "MSDU5772413"  (optional) - Stop when this container found
        "debug": true/false  (default: false) - If true, return ZIP with screenshots; if false, Excel only
    }
    
    Note: Only one of infinite_scrolling, target_count, or target_container_id should be used at a time.
    Priority: target_container_id > target_count > infinite_scrolling
    
    Returns Excel file with container data (and session_id in response)
    """
    
    request_id = f"containers_{int(time.time())}"
    
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400
        
        data = request.get_json()
        
        # Work mode selection (priority order)
        target_container_id = data.get('target_container_id', None)
        target_count = data.get('target_count', None)
        infinite_scrolling = data.get('infinite_scrolling', True)  # Default: enabled
        debug_mode = data.get('debug', False)  # Default: no debug (Excel only)
        capture_screens = debug_mode  # Only capture if debug mode is enabled
        return_url = data.get('return_url', False)
        
        # Determine the work mode
        work_mode = "all"  # default
        if target_container_id:
            work_mode = "find_container"
            infinite_scrolling = False
        elif target_count:
            work_mode = "target_count"
            infinite_scrolling = False
        
        logger.info(f"[{request_id}] Work mode: {work_mode}")
        if target_container_id:
            logger.info(f"[{request_id}] Target container: {target_container_id}")
        elif target_count:
            logger.info(f"[{request_id}] Target count: {target_count}")
        else:
            logger.info(f"[{request_id}] Infinite scrolling: {infinite_scrolling}")
        logger.info(f"[{request_id}] Debug mode: {debug_mode}")
        
        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, session_id, is_new_session = result
        
        logger.info(f"[{request_id}] Using session: {session_id} (new={is_new_session})")
        screens_label = data.get('screens_label', username)
        
        # Create session object for EModalBusinessOperations
        class SessionWrapper:
            def __init__(self, driver, session_id):
                self.driver = driver
                self.session_id = session_id
        
        session_wrapper = SessionWrapper(driver, session_id)
        
        # Perform business operations
        try:
            operations = EModalBusinessOperations(session_wrapper)
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label
            print(f"📸 Screenshots enabled: {operations.screens_enabled}")
            print(f"📁 Screenshots directory: {operations.screens_dir}")

            # Ensure app fully ready after login before any navigation
            print("🕒 Ensuring app context is fully loaded after login...")
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                # Fallback: request containers directly per requirement
                try:
                    print("⚠️ App readiness not confirmed in 30s — requesting containers directly...")
                    session.driver.get("https://ecp2.emodal.com/containers")
                    # Small settle + quick readiness wait
                    operations._wait_for_app_ready(15)
                except Exception:
                    pass
 
            
            # Step 1: Navigate to containers
            nav_result = operations.navigate_to_containers()
            if not nav_result["success"]:
                # Session remains active (persistent by default)
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error']}"
                }), 500
            
            # Step 1.5: Load containers based on work mode
            scroll_result = {}
            if target_container_id:
                print(f"🔍 Scrolling to find container: {target_container_id}...")
                scroll_result = operations.load_all_containers_with_infinite_scroll(
                    target_container_id=target_container_id
                )
                if scroll_result.get("success") and scroll_result.get("found_target_container"):
                    print(f"✅ Container found: {target_container_id} after {scroll_result.get('scroll_cycles', 0)} cycles")
                else:
                    print(f"⚠️ Container {target_container_id} not found after scrolling")
            elif target_count:
                print(f"🔢 Scrolling to load {target_count} containers...")
                scroll_result = operations.load_all_containers_with_infinite_scroll(
                    target_count=target_count
                )
                if scroll_result.get("success"):
                    print(f"✅ Loaded {scroll_result.get('total_containers', 0)} containers (target: {target_count})")
            elif infinite_scrolling:
                print("📜 Loading all containers with infinite scroll...")
                scroll_result = operations.load_all_containers_with_infinite_scroll()
                if not scroll_result["success"]:
                    print(f"⚠️ Infinite scroll failed: {scroll_result.get('error', 'Unknown error')}")
                    # Continue anyway - maybe all containers are already loaded
                else:
                    print(f"✅ Infinite scroll completed: {scroll_result.get('total_containers', 'unknown')} containers loaded")
            else:
                print("⏭️  Scrolling disabled - using first page only")
                scroll_result = {
                    "success": True,
                    "total_containers": "first_page_only",
                    "scroll_cycles": 0,
                    "message": "Infinite scrolling disabled by request"
                }
            
            # Step 2: Skip selection, directly scrape table data
            # (No need to select checkboxes if we're scraping)
            print("📊 Skipping checkbox selection - will scrape table directly")
            
            # Step 3: Scrape table and create Excel file
            download_result = operations.scrape_containers_to_excel()
            if not download_result["success"]:
                # Create failure bundle with screenshots
                bundle_path = None
                bundle_name = None
                try:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    bundle_name = f"{session_id}_{ts}_FAILED.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session_id
                    
                    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        # Include screenshots
                        session_sc_dir = operations.screens_dir
                        if os.path.isdir(session_sc_dir):
                            for root, _, files in os.walk(session_sc_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    rel = os.path.relpath(fp, session_sc_dir)
                                    arc = os.path.join(session_root, 'screenshots', rel)
                                    zf.write(fp, arc)
                        # Add error log
                        error_log = f"Error: {download_result['error']}\nTime: {datetime.now().isoformat()}\nRequest ID: {request_id}\nStep: Download Excel"
                        zf.writestr(os.path.join(session_root, 'error.txt'), error_log)
                    
                    # Print download URL
                    if bundle_path and os.path.exists(bundle_path):
                        public_url = f"http://{request.host}/files/{bundle_name}"
                        print(f"\n{'='*70}")
                        print(f"❌ DOWNLOAD FAILED - DEBUG BUNDLE AVAILABLE")
                        print(f"{'='*70}")
                        print(f"🌐 Public URL: {public_url}")
                        print(f"📂 File: {bundle_name}")
                        print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                        print(f"🔍 Error: {download_result['error']}")
                        print(f"{'='*70}\n")
                except Exception as bundle_e:
                    print(f"⚠️ Failed to create error bundle: {bundle_e}")
                
                # Session remains active (persistent by default)
                return jsonify({
                    "success": False,
                    "error": f"Download failed: {download_result['error']}",
                    "debug_bundle_url": (f"/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None)
                }), 500
            
            # Success - ensure file is under project downloads; otherwise move it
            src_path = download_result["file_path"]
            final_name = os.path.basename(src_path)
            # If not already under our DOWNLOADS_DIR, move into a session folder
            if not os.path.abspath(src_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
                session_folder = os.path.join(DOWNLOADS_DIR, session_id)
                try:
                    os.makedirs(session_folder, exist_ok=True)
                except Exception:
                    pass
                dest_path = os.path.join(session_folder, final_name)
                try:
                    shutil.move(src_path, dest_path)
                except Exception:
                    shutil.copyfile(src_path, dest_path)
            else:
                dest_path = src_path
            logger.info(f"[{request_id}] Success! File: {final_name}")

            # Session is automatically kept alive (persistent by default)
            logger.info(f"[{request_id}] Session remains active: {session_id}")

            # Build bundle based on debug mode
            bundle_name = None
            bundle_path = None
            excel_url = None
            
            # Always prepare Excel file URL
            excel_url = f"http://{request.host}/files/{session_id}/{final_name}"
            
            if debug_mode:
                # Debug mode: Build ZIP with screenshots + debug files + Excel
                try:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    bundle_name = f"{session_id}_{ts}_DEBUG.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session_id  # top-level folder inside zip
                    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        # Include session downloads folder (Excel + debug files)
                        session_dl_dir = os.path.join(DOWNLOADS_DIR, session_id)
                        if os.path.isdir(session_dl_dir):
                            for root, _, files in os.walk(session_dl_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    # arc path inside zip: <session_id>/downloads/...
                                    rel = os.path.relpath(fp, session_dl_dir)
                                    arc = os.path.join(session_root, 'downloads', rel)
                                    zf.write(fp, arc)
                        # Include session screenshots folder
                        session_sc_dir = operations.screens_dir
                        if os.path.isdir(session_sc_dir):
                            for root, _, files in os.walk(session_sc_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    # arc path: <session_id>/screenshots/...
                                    rel = os.path.relpath(fp, session_sc_dir)
                                    arc = os.path.join(session_root, 'screenshots', rel)
                                    zf.write(fp, arc)
                    
                    # Print debug bundle URL
                    if bundle_path and os.path.exists(bundle_path):
                        bundle_url = f"http://{request.host}/files/{bundle_name}"
                        print(f"\n{'='*70}")
                        print(f"🐛 DEBUG BUNDLE READY")
                        print(f"{'='*70}")
                        print(f"🌐 Bundle URL: {bundle_url}")
                        print(f"📂 File: {bundle_name}")
                        print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                        print(f"{'='*70}\n")
                    
                except Exception as be:
                    print(f"⚠️ Debug bundle creation failed: {be}")
            else:
                # Normal mode: No bundle, just Excel
                print(f"\n{'='*70}")
                print(f"📄 EXCEL FILE READY")
                print(f"{'='*70}")
                print(f"🌐 Excel URL: {excel_url}")
                print(f"📂 File: {final_name}")
                print(f"📊 Size: {os.path.getsize(dest_path)} bytes")
                print(f"{'='*70}\n")

            # Build response
            response_data = {
                "success": True,
                "session_id": session_id,  # NEW: Return session_id for reuse
                "is_new_session": is_new_session,  # NEW: Indicate if session was created
                "file_url": excel_url,
                "file_name": final_name,
                "file_size": os.path.getsize(dest_path)
            }
            
            # Add scroll information if available
            if scroll_result.get("success"):
                response_data["total_containers"] = scroll_result.get("total_containers")
                response_data["scroll_cycles"] = scroll_result.get("scroll_cycles")
                if scroll_result.get("found_target_container"):
                    response_data["found_target_container"] = scroll_result.get("found_target_container")
                if scroll_result.get("stopped_reason"):
                    response_data["stopped_reason"] = scroll_result.get("stopped_reason")
            
            # Add debug bundle URL if debug mode
            if debug_mode and bundle_path and os.path.exists(bundle_path):
                response_data["debug_bundle_url"] = f"/files/{bundle_name}"
            
            if return_url:
                return jsonify(response_data)
            else:
                return send_file(
                    dest_path,
                    as_attachment=True,
                    download_name=final_name,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            
        except Exception as operation_error:
            logger.error(f"[{request_id}] Operation failed: {str(operation_error)}")
            
            # ALWAYS create a bundle with screenshots for debugging, even on failure
            bundle_path = None
            bundle_name = None
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{session_id}_{ts}_FAILED.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                session_root = session_id
                
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Include any partial downloads
                    session_dl_dir = os.path.join(DOWNLOADS_DIR, session_id)
                    if os.path.isdir(session_dl_dir):
                        for root, _, files in os.walk(session_dl_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_dl_dir)
                                arc = os.path.join(session_root, 'downloads', rel)
                                zf.write(fp, arc)
                    
                    # Include screenshots (most important for debugging)
                    session_sc_dir = operations.screens_dir
                    if os.path.isdir(session_sc_dir):
                        for root, _, files in os.walk(session_sc_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_sc_dir)
                                arc = os.path.join(session_root, 'screenshots', rel)
                                zf.write(fp, arc)
                    
                    # Add error log file
                    error_log = f"Error: {str(operation_error)}\nTime: {datetime.now().isoformat()}\nRequest ID: {request_id}"
                    zf.writestr(os.path.join(session_root, 'error.txt'), error_log)
                
                # Print public download URL for failed operation
                if bundle_path and os.path.exists(bundle_path):
                    public_url = f"http://{request.host}/files/{bundle_name}"
                    print(f"\n{'='*70}")
                    print(f"❌ OPERATION FAILED - DEBUG BUNDLE AVAILABLE")
                    print(f"{'='*70}")
                    print(f"🌐 Public URL: {public_url}")
                    print(f"📂 File: {bundle_name}")
                    print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                    print(f"🔍 Error: {str(operation_error)}")
                    print(f"{'='*70}\n")
            except Exception as bundle_e:
                print(f"⚠️ Failed to create error bundle: {bundle_e}")
            
            # Session remains active (persistent by default)
            
            # Return error with bundle URL if available
            response_data = {
                "success": False,
                "error": f"Operation failed: {str(operation_error)}",
                "debug_bundle_url": (f"/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None)
            }
            return jsonify(response_data), 500
            
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), 500


@app.route('/check_appointments', methods=['POST'])
def check_appointments():
    """
    Check available appointment times by going through all 3 phases.
    Does NOT submit the appointment - only retrieves available time slots.
    
    Supports both IMPORT and EXPORT container workflows.
    
    Required fields:
        - container_type: "import" or "export" (required)
        - session_id (optional): Use existing persistent session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
    
    Phase 1 fields (required unless continuing from appointment_session_id):
        - trucking_company: Trucking company name
        - terminal: Terminal name (e.g., "ITS Long Beach")
        - move_type: Move type (e.g., "DROP EMPTY")
        
        For IMPORT:
            - container_id: Container number
        
        For EXPORT:
            - booking_number: Booking number
    
    Phase 2 fields (required unless continuing from appointment_session_id):
        For IMPORT:
            - pin_code: PIN code (optional, can be missing)
            - truck_plate: Truck plate number
            - own_chassis: Boolean (true/false)
        
        For EXPORT:
            - unit_number: Unit number (default: "1")
            - seal_value: Value for seal fields (default: "1")
            - truck_plate: Truck plate number
            - own_chassis: Boolean (true/false)
    
    Phase 3:
        For IMPORT:
            - Returns available appointment times
        
        For EXPORT:
            - Finds and clicks calendar icon
            - Returns calendar_found: true/false
    
    Session continuation (if error occurred):
        - appointment_session_id: To continue from where it left off (different from session_id)
    
    Returns:
        - success: True/False
        - session_id: Browser session ID (persistent)
        - is_new_session: Whether browser session was newly created
        - appointment_session_id: Appointment workflow session ID
        - available_times: List of appointment time slots (import only)
        - calendar_found: Boolean (export only)
        - debug_bundle_url: ZIP file with screenshots
        - current_phase: Current phase number (1-3)
        - message: Error message if missing fields
    """
    request_id = f"check_appt_{int(time.time())}"
    appt_session = None
    browser_session_id = None
    is_new_browser_session = False
    
    try:
        cleanup_expired_appointment_sessions()
        
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400
        
        data = request.get_json()
        appointment_session_id = data.get('appointment_session_id')
        debug_mode = data.get('debug', False)  # Default: working mode (no bundle)
        vm_email = data.get('vm_email', '')  # VM email for screenshot labels
        
        # Validate container_type
        container_type = data.get('container_type', '').lower()
        if container_type not in ['import', 'export']:
            return jsonify({
                "success": False,
                "error": "container_type must be 'import' or 'export'"
            }), 400
        
        print(f"📦 Container Type: {container_type.upper()}")
        print(f"🔧 Debug Mode: {'ENABLED' if debug_mode else 'DISABLED (working mode)'}")
        
        # Check if continuing from existing appointment workflow session
        if appointment_session_id and appointment_session_id in appointment_sessions:
            print(f"🔄 Continuing from existing appointment session: {appointment_session_id}")
            appt_session = appointment_sessions[appointment_session_id]
            appt_session.update_last_used()
            operations = EModalBusinessOperations(appt_session.browser_session)
            operations.screens_enabled = True
            operations.screens_label = appt_session.browser_session.username
            browser_session_id = appt_session.browser_session.session_id
            is_new_browser_session = False
            username = appt_session.browser_session.username
            
        else:
            # New appointment workflow - get or create browser session
            result = get_or_create_browser_session(data, request_id)
            
            if len(result) == 5:  # Error case
                _, _, _, _, error_response = result
                return error_response
            
            driver, username, browser_session_id, is_new_browser_session = result
            
            logger.info(f"[{request_id}] Check appointments request for user: {username}, session: {browser_session_id}")
            
            # Create wrapper for browser session
            class SessionWrapper:
                def __init__(self, driver, session_id, username):
                    self.driver = driver
                    self.session_id = session_id
                    self.username = username
            
            browser_session = SessionWrapper(driver, browser_session_id, username)
            
            # Create appointment session for workflow tracking
            appt_session = AppointmentSession(
                session_id=f"appt_{browser_session_id}_{int(time.time())}",
                browser_session=browser_session,
                current_phase=1,
                created_at=datetime.now(),
                last_used=datetime.now(),
                phase_data={}
            )
            appointment_sessions[appt_session.session_id] = appt_session
            logger.info(f"[{request_id}] Appointment workflow session created: {appt_session.session_id}")
            
            operations = EModalBusinessOperations(browser_session)
            operations.screens_enabled = True
            operations.screens_label = username
            operations.vm_email = vm_email  # Set VM email for screenshot labels
            
            # Set container ID for screenshot annotations (import or export)
            container_id = data.get('container_id')
            container_number = data.get('container_number')  # For display in screenshots
            
            if container_number:
                operations.current_container_id = container_number
            elif container_id:
                operations.current_container_id = container_id
            
            # Ensure app context
            print("🕒 Ensuring app context is fully loaded...")
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                print("⚠️ App readiness not confirmed - proceeding to appointment page...")
            
            # Navigate to appointment page (includes 30-second wait)
            nav_result = operations.navigate_to_appointment()
            if not nav_result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 1
                }), 500
        
        # Execute phases based on current phase
        operations = EModalBusinessOperations(appt_session.browser_session)
        operations.screens_enabled = True
        operations.screens_label = appt_session.browser_session.username
        operations.vm_email = vm_email  # Set VM email for screenshot labels
        
        # Set container ID for screenshot annotations (import or export)
        container_id = data.get('container_id')
        container_number = data.get('container_number')  # For display in screenshots
        booking_number = data.get('booking_number')  # For export
        
        if container_number:
            operations.current_container_id = container_number
        elif booking_number:
            operations.current_container_id = booking_number
        elif container_id:
            operations.current_container_id = container_id
        
        # Set date counters for import containers (for screenshot annotations)
        if container_type == 'import':
            manifested_date = data.get('manifested_date')
            departed_date = data.get('departed_date')
            last_free_day_date = data.get('last_free_day_date')
            
            # Always show date counters if it's an import container
            operations.show_manifested_counter = True
            operations.show_departed_counter = True
            operations.show_last_free_day_counter = True
            
            if manifested_date:
                operations.manifested_date = manifested_date
                print(f"  📅 Manifested Date: {manifested_date}")
            else:
                operations.manifested_date = None
                print(f"  📅 Manifested Date: N/A")
            
            if departed_date:
                operations.departed_date = departed_date
                print(f"  📅 Departed Date: {departed_date}")
            else:
                operations.departed_date = None
                print(f"  📅 Departed Date: N/A")
            
            if last_free_day_date:
                operations.last_free_day_date = last_free_day_date
                print(f"  📅 Last Free Day Date: {last_free_day_date}")
            else:
                operations.last_free_day_date = None
                print(f"  📅 Last Free Day Date: N/A")
        
        # PHASE 1: Dropdowns + Container/Booking Number + Quantity (for export)
        if appt_session.current_phase == 1:
            if container_type == 'import':
                print("\n" + "="*70)
                print("📋 PHASE 1 (IMPORT): Trucking Company, Terminal, Move Type, Container")
                print("="*70)
            else:
                print("\n" + "="*70)
                print("📋 PHASE 1 (EXPORT): Trucking Company, Terminal, Move Type, Booking, Quantity")
                print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 1 to fully load...")
            time.sleep(5)
            print("✅ Phase 1 ready")
            
            trucking_company = data.get('trucking_company')
            terminal = data.get('terminal')
            move_type = data.get('move_type')
            
            # Check for missing fields based on container type
            missing_fields = []
            if not trucking_company:
                missing_fields.append("trucking_company")
            if not terminal:
                missing_fields.append("terminal")
            if not move_type:
                missing_fields.append("move_type")
            
            if container_type == 'import':
                container_id = data.get('container_id')
                if not container_id:
                    missing_fields.append("container_id")
            else:  # export
                booking_number = data.get('booking_number')
                if not booking_number:
                    missing_fields.append("booking_number")
            
            if missing_fields:
                return jsonify({
                    "success": False,
                    "error": f"Missing required fields for Phase 1: {', '.join(missing_fields)}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 1,
                    "message": f"Please provide {', '.join(missing_fields)} and retry with appointment_session_id"
                }), 400
            
            # Fill Phase 1
            result = operations.select_dropdown_by_text("Trucking", trucking_company)
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 1 failed - Trucking company: {result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 1
                }), 500
            
            result = operations.select_dropdown_by_text("Terminal", terminal)
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 1 failed - Terminal: {result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 1
                }), 500
            
            result = operations.select_dropdown_by_text("Move", move_type)
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 1 failed - Move type: {result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 1
                }), 500
            
            # Fill container or booking number based on type
            if container_type == 'import':
                # Try to fill container number first
                result = operations.fill_container_number(container_id)
                
                # If container/booking field not found, use alternative fields (Line, Equip Size, Quantity)
                if not result["success"] and result.get("field_not_found"):
                    print("  ℹ️ Container field not found - checking for Line/Equip Size fields...")
                    
                    # Check if Line and Equip Size fields exist
                    line_value = data.get('line')
                    equip_size = data.get('equip_size')
                    
                    if line_value and equip_size:
                        print(f"  📋 Using alternative fields: Line={line_value}, Equip Size={equip_size}")
                        
                        # Fill Line autocomplete field with fallback to any option if not found
                        result = operations.fill_autocomplete_field("Line", line_value, fallback_to_any=True)
                        if not result["success"]:
                            return jsonify({
                                "success": False,
                                "error": f"Phase 1 failed - Line: {result['error']}",
                                "session_id": browser_session_id,
                                "is_new_session": is_new_browser_session,
                                "appointment_session_id": appt_session.session_id,
                                "current_phase": 1
                            }), 500
                        
                        # Log if fallback was used
                        if result.get("fallback"):
                            print(f"  ⚠️ Line '{line_value}' not found, used fallback: '{result.get('selected')}'")
                        
                        # Wait a moment for Line selection to be processed
                        print(f"  ⏳ Waiting 2 seconds for Line selection to be processed...")
                        time.sleep(2)
                        
                        # Fill Equip Size autocomplete field (same as Line - it's also an autocomplete field)
                        print(f"  🔄 Proceeding to fill Equip Size field...")
                        result = operations.fill_autocomplete_field("Equip Size", equip_size, fallback_to_any=True)
                        if not result["success"]:
                            print(f"  ❌ Equip Size field failed: {result['error']}")
                            return jsonify({
                                "success": False,
                                "error": f"Phase 1 failed - Equip Size: {result['error']}",
                                "session_id": browser_session_id,
                                "is_new_session": is_new_browser_session,
                                "appointment_session_id": appt_session.session_id,
                                "current_phase": 1
                            }), 500
                        
                        # Log if fallback was used for Equip Size
                        if result.get("fallback"):
                            print(f"  ⚠️ Equip Size '{equip_size}' not found, used fallback: '{result.get('selected')}'")
                        elif result.get("exact_match"):
                            print(f"  ✅ Equip Size '{equip_size}' found and selected exactly")
                        elif result.get("partial_match"):
                            print(f"  ✅ Equip Size '{equip_size}' found as partial match: '{result.get('selected')}'")
                        
                        print(f"  ✅ Equip Size field filled successfully with '{result.get('selected')}'")
                        
                        # Fill Quantity (always 1)
                        result = operations.fill_quantity_field()
                        if not result["success"]:
                            return jsonify({
                                "success": False,
                                "error": f"Phase 1 failed - Quantity: {result['error']}",
                                "session_id": browser_session_id,
                                "is_new_session": is_new_browser_session,
                                "appointment_session_id": appt_session.session_id,
                                "current_phase": 1
                            }), 500
                    else:
                        # Neither container field nor alternative fields available
                        return jsonify({
                            "success": False,
                            "error": "Phase 1 failed - Container field not found. Please provide 'line' and 'equip_size' fields for this form type.",
                            "session_id": browser_session_id,
                            "is_new_session": is_new_browser_session,
                            "appointment_session_id": appt_session.session_id,
                            "current_phase": 1,
                            "message": "This form requires 'line' and 'equip_size' instead of 'container_id'"
                        }), 400
                elif not result["success"]:
                    # Other error (not "not found")
                    return jsonify({
                        "success": False,
                        "error": f"Phase 1 failed - Container: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 1
                    }), 500
            else:  # export
                result = operations.fill_container_number(booking_number)  # Works for both container and booking
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 1 failed - Booking number: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 1
                    }), 500
                
                # Click blank space and check for popup after booking number
                print("  🖱️  Clicking blank space after booking number...")
                try:
                    operations.driver.find_element(By.TAG_NAME, "body").click()
                    time.sleep(0.5)
                except:
                    pass
                
                # Check for specific error: "No open transactions for this booking number"
                try:
                    error_dialog = operations.driver.find_element(
                        By.XPATH,
                        "//div[contains(@class, 'dialog-content')]//span[contains(text(), 'No open transactions for this booking number')]"
                    )
                    if error_dialog:
                        error_message = error_dialog.text.strip()
                        print(f"  ⚠️ Booking number error detected: {error_message}")
                        operations._capture_screenshot("booking_number_error")
                        
                        # Close the error dialog
                        operations.close_popup_if_present()
                        
                        # Release session
                        release_session_after_operation(browser_session_id)
                        
                        return jsonify({
                            "success": False,
                            "error": "Booking number validation failed",
                            "error_message": error_message,
                            "session_id": browser_session_id,
                            "is_new_session": is_new_browser_session,
                            "appointment_session_id": appt_session.session_id,
                            "current_phase": 1,
                            "screenshot_url": f"http://{request.host}/files/{operations.screens_dir.split('/')[-1]}/booking_number_error.png"
                        }), 400
                except:
                    pass  # No error dialog found, continue
                
                # Check for and close any other popup messages (e.g., "Booking shippingline is required")
                operations.close_popup_if_present()
                
                print("  ⏳ Waiting 5 seconds before filling quantity...")
                time.sleep(5)
                print("  ✅ Ready to fill quantity")
                
                # Fill quantity field (export only)
                result = operations.fill_quantity_field()
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 1 failed - Quantity: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 1
                    }), 500
            
            # Click Next
            result = operations.click_next_button(1)
            if not result["success"]:
                # Check if retry is needed
                if result.get("needs_retry"):
                    print("  🔄 Phase did not advance, re-filling Phase 1 fields before retry...")
                    
                    # Re-fill all Phase 1 fields
                    operations.select_dropdown_by_text("Trucking", trucking_company)
                    operations.select_dropdown_by_text("Terminal", terminal)
                    operations.select_dropdown_by_text("Move", move_type)
                    
                    if container_type == 'import':
                        operations.fill_container_number(container_id)
                    else:  # export
                        operations.fill_container_number(booking_number)
                        # Click blank and check for popup
                        try:
                            operations.driver.find_element(By.TAG_NAME, "body").click()
                            time.sleep(0.5)
                        except:
                            pass
                        operations.close_popup_if_present()
                        time.sleep(5)
                        operations.fill_quantity_field()
                    
                    # Retry Next button
                    print("  🔄 Retrying Next button after re-filling...")
                    result = operations.click_next_button(1)
                    if not result["success"]:
                        return jsonify({
                            "success": False,
                            "error": f"Phase 1 failed - Next button (after retry): {result['error']}",
                            "session_id": browser_session_id,
                            "is_new_session": is_new_browser_session,
                            "appointment_session_id": appt_session.session_id,
                            "current_phase": 1
                        }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 1 failed - Next button: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 1
                    }), 500
            
            # Update session
            appt_session.current_phase = 2
            phase_data = {
                "container_type": container_type,
                "trucking_company": trucking_company,
                "terminal": terminal,
                "move_type": move_type
            }
            
            if container_type == 'import':
                phase_data["container_id"] = container_id
            else:  # export
                phase_data["booking_number"] = booking_number
            
            appt_session.phase_data.update(phase_data)
            print("✅ Phase 1 completed successfully")
        
        # PHASE 2: Container Selection + Type-Specific Fields
        if appt_session.current_phase == 2:
            if container_type == 'import':
                print("\n" + "="*70)
                print("📋 PHASE 2 (IMPORT): Checkbox, PIN, Truck Plate, Chassis")
                print("="*70)
            else:
                print("\n" + "="*70)
                print("📋 PHASE 2 (EXPORT): Checkbox, Unit, Seals, Truck Plate, Chassis")
                print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 2 to fully load...")
            time.sleep(5)
            print("✅ Phase 2 ready")
            
            truck_plate = data.get('truck_plate')
            own_chassis = data.get('own_chassis')
            
            # Debug: Show what we received
            print(f"  📋 Received own_chassis value: {own_chassis} (type: {type(own_chassis).__name__})")
            
            # Check if own_chassis should be ignored
            ignore_own_chassis = (
                own_chassis is None or 
                (isinstance(own_chassis, str) and own_chassis.lower() == 'ignore')
            )
            
            if ignore_own_chassis:
                print("  ℹ️ Own Chassis: IGNORED (not provided or set to 'ignore')")
            
            # Select checkbox (always required)
            result = operations.select_container_checkbox()
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 2 failed - Checkbox: {result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 2
                }), 500
            
            # Type-specific fields
            if container_type == 'import':
                # Import: PIN code (auto-fills with '1111' if not provided)
                pin_code = data.get('pin_code')
                result = operations.fill_pin_code(pin_code)
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 2 failed - PIN: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 2
                    }), 500
            else:  # export
                # Export: Unit number (default "1")
                unit_number = data.get('unit_number', '1')
                result = operations.fill_unit_number(unit_number)
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 2 failed - Unit number: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 2
                    }), 500
                
                # Export: Seal fields (default "1")
                seal_value = data.get('seal_value', '1')
                result = operations.fill_seal_fields(seal_value)
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 2 failed - Seal fields: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 2
                    }), 500
            
            # Truck plate (required)
            if not truck_plate:
                return jsonify({
                    "success": False,
                    "error": "Missing required field for Phase 2: truck_plate",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 2,
                    "message": "Please provide truck_plate and retry with appointment_session_id"
                }), 400
            
            result = operations.fill_truck_plate(truck_plate)
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 2 failed - Truck plate: {result['error']}",
                    "session_id": browser_session_id,
                    "is_new_session": is_new_browser_session,
                    "appointment_session_id": appt_session.session_id,
                    "current_phase": 2
                }), 500
            
            # Own chassis toggle (only if not ignored)
            if not ignore_own_chassis:
                result = operations.toggle_own_chassis(own_chassis)
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 2 failed - Own chassis: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 2
                    }), 500
            else:
                print("  ⏭️ Skipping Own Chassis toggle (ignored)")
            
            # Click Next
            result = operations.click_next_button(2)
            if not result["success"]:
                # Check if retry is needed
                if result.get("needs_retry"):
                    print("  🔄 Phase did not advance, re-filling Phase 2 fields before retry...")
                    
                    # Re-fill all Phase 2 fields
                    operations.select_container_checkbox()
                    
                    if container_type == 'import':
                        pin_code = data.get('pin_code')
                        operations.fill_pin_code(pin_code)
                    else:  # export
                        unit_number = data.get('unit_number', '1')
                        seal_value = data.get('seal_value', '1')
                        operations.fill_unit_number(unit_number)
                        operations.fill_seal_fields(seal_value)
                    
                    operations.fill_truck_plate(truck_plate)
                    
                    # Toggle own chassis only if not ignored
                    if not ignore_own_chassis:
                        operations.toggle_own_chassis(own_chassis)
                    
                    # Retry Next button
                    print("  🔄 Retrying Next button after re-filling...")
                    result = operations.click_next_button(2)
                    if not result["success"]:
                        return jsonify({
                            "success": False,
                            "error": f"Phase 2 failed - Next button (after retry): {result['error']}",
                            "session_id": browser_session_id,
                            "is_new_session": is_new_browser_session,
                            "appointment_session_id": appt_session.session_id,
                            "current_phase": 2
                        }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 2 failed - Next button: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 2
                    }), 500
            
            # Update session
            appt_session.current_phase = 3
            phase_data = {
                "truck_plate": truck_plate,
                "own_chassis": own_chassis
            }
            
            if container_type == 'import':
                pin_code = data.get('pin_code')
                if pin_code:
                    phase_data["pin_code"] = pin_code
            else:  # export
                phase_data["unit_number"] = data.get('unit_number', '1')
                phase_data["seal_value"] = data.get('seal_value', '1')
            
            appt_session.phase_data.update(phase_data)
            print("✅ Phase 2 completed successfully")
        
        # PHASE 3: Get Available Times (import) or Find Calendar (export)
        if appt_session.current_phase == 3:
            if container_type == 'import':
                print("\n" + "="*70)
                print("📋 PHASE 3 (IMPORT): Retrieving Available Appointment Times")
                print("="*70)
            else:
                print("\n" + "="*70)
                print("📋 PHASE 3 (EXPORT): Finding Calendar Icon")
                print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 3 to fully load...")
            time.sleep(5)
            print("✅ Phase 3 ready")
            
            # Execute phase based on container type
            available_times = []
            calendar_found = False
            
            if container_type == 'import':
                result = operations.get_available_appointment_times()
                if not result["success"]:
                    return jsonify({
                        "success": False,
                        "error": f"Phase 3 failed: {result['error']}",
                        "session_id": browser_session_id,
                        "is_new_session": is_new_browser_session,
                        "appointment_session_id": appt_session.session_id,
                        "current_phase": 3
                    }), 500
                
                available_times = result["available_times"]
                print("✅ Phase 3 completed successfully")
                print(f"✅ Found {len(available_times)} available appointment times")
            else:  # export
                result = operations.find_and_click_calendar_icon()
                calendar_found = result.get("calendar_found", False)
                
                if calendar_found:
                    print("✅ Phase 3 completed successfully")
                    print(f"✅ Calendar icon found and clicked")
                else:
                    print("⚠️ Phase 3 completed but calendar not found")
                    print(f"⚠️ Calendar icon was not found on the page")
        
        # Create debug bundle (only if debug mode is enabled)
        bundle_name = None
        bundle_url = None
        if debug_mode:
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{appt_session.session_id}_{ts}_check_appointments.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Include screenshots
                    session_sc_dir = operations.screens_dir
                    if os.path.isdir(session_sc_dir):
                        for root, _, files in os.walk(session_sc_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_sc_dir)
                                arc = os.path.join('screenshots', rel)
                                zf.write(fp, arc)
                
                bundle_url = f"http://{request.host}/files/{bundle_name}"
                print(f"\n{'='*70}")
                print(f"📦 DEBUG BUNDLE CREATED")
                print(f"{'='*70}")
                print(f" Public URL: {bundle_url}")
                print(f" File: {bundle_name}")
                print(f" Size: {os.path.getsize(bundle_path)} bytes")
                print(f"{'='*70}\n")
                
            except Exception as be:
                print(f"⚠️ Bundle creation failed: {be}")
        else:
            print(f"\n✅ Working mode: No debug bundle created (screenshots available via direct URLs)")
        
        # Clean up appointment workflow session (keep browser session alive)
        if appt_session.session_id in appointment_sessions:
            del appointment_sessions[appt_session.session_id]
        
        logger.info(f"[{request_id}] Check appointments completed successfully (browser session kept alive: {browser_session_id})")
        
        # Prepare dropdown screenshot URL if available (import)
        dropdown_screenshot_url = None
        if result.get("dropdown_screenshot"):
            screenshot_path = result.get("dropdown_screenshot")
            screenshot_filename = os.path.basename(screenshot_path)
            # Copy to downloads folder for public access
            try:
                import shutil
                public_screenshot_path = os.path.join(DOWNLOADS_DIR, screenshot_filename)
                shutil.copy2(screenshot_path, public_screenshot_path)
                dropdown_screenshot_url = f"http://{request.host}/files/{screenshot_filename}"
                print(f"📸 Dropdown screenshot available: {dropdown_screenshot_url}")
            except Exception as copy_error:
                print(f"⚠️ Could not copy screenshot: {copy_error}")
        
        # Prepare calendar screenshot URL if available (export)
        calendar_screenshot_url = None
        if result.get("calendar_screenshot"):
            screenshot_path = result.get("calendar_screenshot")
            screenshot_filename = os.path.basename(screenshot_path)
            # Copy to downloads folder for public access
            try:
                import shutil
                public_screenshot_path = os.path.join(DOWNLOADS_DIR, screenshot_filename)
                shutil.copy2(screenshot_path, public_screenshot_path)
                calendar_screenshot_url = f"http://{request.host}/files/{screenshot_filename}"
                print(f"📸 Calendar screenshot available: {calendar_screenshot_url}")
            except Exception as copy_error:
                print(f"⚠️ Could not copy screenshot: {copy_error}")
        
        # Build response based on container type
        response = {
            "success": True,
            "container_type": container_type,
            "session_id": browser_session_id,
            "is_new_session": is_new_browser_session,
            "appointment_session_id": appt_session.session_id,
            "phase_data": appt_session.phase_data
        }
        
        # Only include debug bundle URL if debug mode is enabled
        if debug_mode and bundle_url:
            response["debug_bundle_url"] = bundle_url
        
        if container_type == 'import':
            response["available_times"] = available_times
            response["count"] = len(available_times)
            response["dropdown_screenshot_url"] = dropdown_screenshot_url
        else:  # export
            response["calendar_found"] = calendar_found
            response["calendar_screenshot_url"] = calendar_screenshot_url
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        response = {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "current_phase": appt_session.current_phase if appt_session else 0
        }
        if appt_session:
            response["appointment_session_id"] = appt_session.session_id
            try:
                response["session_id"] = appt_session.browser_session.session_id
            except:
                pass
        return jsonify(response), 500


@app.route('/make_appointment', methods=['POST'])
def make_appointment():
    """
    Make an appointment by going through all 3 phases and SUBMITTING.
    ⚠️ WARNING: This ACTUALLY SUBMITS the appointment!
    
    Required fields:
        - session_id (optional): Use existing persistent session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
        - trucking_company, terminal, move_type, container_id
        - truck_plate, own_chassis
        - appointment_time: The specific time slot to select
        - pin_code: Optional PIN code
    
    Returns:
        - success: True/False
        - session_id: Browser session ID (persistent)
        - is_new_session: Whether browser session was newly created
        - appointment_confirmed: True if submitted successfully
        - debug_bundle_url: ZIP file with screenshots
    """
    request_id = f"make_appt_{int(time.time())}"
    appt_session = None
    browser_session_id = None
    is_new_browser_session = False
    
    try:
        cleanup_expired_appointment_sessions()
        
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400
        
        data = request.get_json()
        
        # Phase 1
        trucking_company = data.get('trucking_company')
        terminal = data.get('terminal')
        move_type = data.get('move_type')
        container_id = data.get('container_id')
        
        # Phase 2
        pin_code = data.get('pin_code')
        truck_plate = data.get('truck_plate')
        own_chassis = data.get('own_chassis')
        
        # Check if own_chassis should be ignored
        ignore_own_chassis = (
            own_chassis is None or 
            (isinstance(own_chassis, str) and own_chassis.lower() == 'ignore')
        )
        
        # Phase 3
        appointment_time = data.get('appointment_time')
        
        # Validate all required fields
        missing = []
        if not trucking_company: missing.append("trucking_company")
        if not terminal: missing.append("terminal")
        if not move_type: missing.append("move_type")
        if not container_id: missing.append("container_id")
        if not truck_plate: missing.append("truck_plate")
        if not appointment_time: missing.append("appointment_time")
        
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, browser_session_id, is_new_browser_session = result
        
        logger.info(f"[{request_id}] Make appointment request for user: {username}, session: {browser_session_id}")
        print("\n" + "="*70)
        print("⚠️  MAKE APPOINTMENT - WILL SUBMIT THE APPOINTMENT!")
        print("="*70)
        
        # Create wrapper for browser session
        class SessionWrapper:
            def __init__(self, driver, session_id, username):
                self.driver = driver
                self.session_id = session_id
                self.username = username
        
        browser_session = SessionWrapper(driver, browser_session_id, username)
        
        # Create appointment session for workflow tracking
        try:
            appt_session = AppointmentSession(
                session_id=f"appt_{browser_session_id}_{int(time.time())}",
                browser_session=browser_session,
                current_phase=1,
                created_at=datetime.now(),
                last_used=datetime.now(),
                phase_data={}
            )
            
            operations = EModalBusinessOperations(browser_session)
            operations.screens_enabled = True
            operations.screens_label = username
            
            # Ensure app context
            print("🕒 Ensuring app context is fully loaded...")
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                print("⚠️ App readiness not confirmed - proceeding to appointment page...")
            
            # Navigate to appointment page (includes 30-second wait)
            nav_result = operations.navigate_to_appointment()
            if not nav_result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error']}"
                }), 500
            
        except Exception as login_error:
            logger.error(f"[{request_id}] Authentication failed: {str(login_error)}")
            return jsonify({
                "success": False,
                "error": f"Authentication failed: {str(login_error)}"
            }), 401
        
        # PHASE 1
        print("\n" + "="*70)
        print("📋 PHASE 1: Trucking Company, Terminal, Move Type, Container")
        print("="*70)
        
        # Wait 5 seconds for phase to fully load
        print("⏳ Waiting 5 seconds for Phase 1 to fully load...")
        time.sleep(5)
        print("✅ Phase 1 ready")
        
        result = operations.select_dropdown_by_text("Trucking", trucking_company)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 1 - Trucking: {result['error']}"}), 500
        
        result = operations.select_dropdown_by_text("Terminal", terminal)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 1 - Terminal: {result['error']}"}), 500
        
        result = operations.select_dropdown_by_text("Move", move_type)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 1 - Move type: {result['error']}"}), 500
        
        result = operations.fill_container_number(container_id)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 1 - Container: {result['error']}"}), 500
        
        result = operations.click_next_button(1)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 1 - Next: {result['error']}"}), 500
        
        print("✅ Phase 1 completed")
        
        # PHASE 2
        print("\n" + "="*70)
        print("📋 PHASE 2: Container Selection, PIN, Truck Plate, Chassis")
        print("="*70)
        
        # Wait 5 seconds for phase to fully load
        print("⏳ Waiting 5 seconds for Phase 2 to fully load...")
        time.sleep(5)
        print("✅ Phase 2 ready")
        
        result = operations.select_container_checkbox()
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - Checkbox: {result['error']}"}), 500
        
        result = operations.fill_pin_code(pin_code)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - PIN: {result['error']}"}), 500
        
        result = operations.fill_truck_plate(truck_plate)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - Truck plate: {result['error']}"}), 500
        
        # Toggle own chassis only if not ignored
        if not ignore_own_chassis:
            result = operations.toggle_own_chassis(own_chassis)
            if not result["success"]:
                return jsonify({"success": False, "error": f"Phase 2 - Own chassis: {result['error']}"}), 500
        else:
            print("  ⏭️ Skipping Own Chassis toggle (ignored)")
        
        result = operations.click_next_button(2)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - Next: {result['error']}"}), 500
        
        print("✅ Phase 2 completed")
        
        # PHASE 3
        print("\n" + "="*70)
        print("📋 PHASE 3: Selecting Appointment Time and SUBMITTING")
        print("="*70)
        
        # Wait 5 seconds for phase to fully load
        print("⏳ Waiting 5 seconds for Phase 3 to fully load...")
        time.sleep(5)
        print("✅ Phase 3 ready")
        
        result = operations.select_appointment_time(appointment_time)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 3 - Appointment time: {result['error']}"}), 500
        
        # ⚠️ SUBMIT THE APPOINTMENT
        result = operations.click_submit_button()
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 3 - Submit: {result['error']}"}), 500
        
        print("✅ Phase 3 completed - APPOINTMENT SUBMITTED!")
        
        # Create debug bundle
        bundle_name = None
        bundle_url = None
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            bundle_name = f"{appt_session.session_id}_{ts}_appointment_submitted.zip"
            bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
            
            with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                session_sc_dir = operations.screens_dir
                if os.path.isdir(session_sc_dir):
                    for root, _, files in os.walk(session_sc_dir):
                        for f in files:
                            fp = os.path.join(root, f)
                            rel = os.path.relpath(fp, session_sc_dir)
                            arc = os.path.join('screenshots', rel)
                            zf.write(fp, arc)
            
            bundle_url = f"http://{request.host}/files/{bundle_name}"
            print(f"\n{'='*70}")
            print(f"📦 APPOINTMENT SUBMITTED - DEBUG BUNDLE CREATED")
            print(f"{'='*70}")
            print(f" Public URL: {bundle_url}")
            print(f" File: {bundle_name}")
            print(f" Size: {os.path.getsize(bundle_path)} bytes")
            print(f"{'='*70}\n")
            
        except Exception as be:
            print(f"⚠️ Bundle creation failed: {be}")
        
        logger.info(f"[{request_id}] Appointment submitted successfully (browser session kept alive: {browser_session_id})")
        
        return jsonify({
            "success": True,
            "session_id": browser_session_id,
            "is_new_session": is_new_browser_session,
            "appointment_confirmed": True,
            "debug_bundle_url": bundle_url,
            "appointment_details": {
                "trucking_company": trucking_company,
                "terminal": terminal,
                "move_type": move_type,
                "container_id": container_id,
                "truck_plate": truck_plate,
                "own_chassis": own_chassis,
                "appointment_time": appointment_time
            }
        }), 200
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        response = {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
        if browser_session_id:
            response["session_id"] = browser_session_id
            response["is_new_session"] = is_new_browser_session
        
        return jsonify(response), 500


@app.route('/get_container_timeline', methods=['POST'])
def get_container_timeline():
    """
    Navigate to containers page, search for a container, expand its timeline, and capture Pregate milestone screenshot.
    
    Inputs:
        - session_id (optional): Use existing session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
        - container_id (required): Container ID to search for
        - debug (optional, default: false): If true, captures cropped screenshot of Pregate milestone
    
    Returns: JSON with container_id, session_id, and optional pregate_screenshot_url (when debug=true)
    """
    request_id = f"timeline_{int(time.time())}"
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        container_id = data.get('container_id') or data.get('container')
        debug_mode = data.get('debug', False)
        
        # Only capture screenshots in debug mode
        capture_screens = debug_mode

        if not container_id:
            return jsonify({
                "success": False,
                "error": "Missing required field: container_id"
            }), 400

        logger.info(f"[{request_id}] Timeline request for container: {container_id}")

        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, session_id, is_new_session = result
        
        logger.info(f"[{request_id}] Using session: {session_id} (new={is_new_session})")
        screens_label = data.get('screens_label', username)
        
        # Create session wrapper for EModalBusinessOperations
        class SessionWrapper:
            def __init__(self, driver, session_id):
                self.driver = driver
                self.session_id = session_id
        
        session_wrapper = SessionWrapper(driver, session_id)

        try:
            operations = EModalBusinessOperations(session_wrapper)
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label

            # Ensure app context
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                try:
                    session.driver.get("https://ecp2.emodal.com/containers")
                    operations._wait_for_app_ready(15)
                except Exception:
                    pass

            # Navigate to containers
            nav = operations.navigate_to_containers()
            if not nav["success"]:
                return jsonify({"success": False, "error": f"Navigation failed: {nav['error']}"}), 500

            # Progressive search during scrolling (more efficient for infinite lists)
            sr = operations.search_container_with_scrolling(container_id)
            if not sr["success"]:
                return jsonify({"success": False, "error": f"Search failed: {sr['error']}"}), 500
            ex = operations.expand_container_row(container_id)
            if not ex["success"]:
                return jsonify({"success": False, "error": f"Expand failed: {ex['error']}"}), 500

            # Extract full timeline
            timeline_result = operations.extract_full_timeline()
            
            if not timeline_result.get("success"):
                return jsonify({
                    "success": False,
                    "error": f"Timeline extraction failed: {timeline_result.get('error')}"
                }), 500
            
            timeline_data = timeline_result.get("timeline", [])
            milestone_count = timeline_result.get("milestone_count", 0)
            
            print(f"✅ Extracted {milestone_count} milestones")
            
            # Check Pregate status (DOM check + optional image processing)
            pregate_status_result = operations.check_pregate_status()
            
            if not pregate_status_result.get("success"):
                return jsonify({
                    "success": False,
                    "error": f"Pregate status check failed: {pregate_status_result.get('error')}"
                }), 500
            
            passed_pregate = pregate_status_result.get("passed_pregate")
            detection_method = pregate_status_result.get("method")
            
            print(f"✅ Pregate status: {'PASSED' if passed_pregate else 'NOT PASSED'} (method: {detection_method})")
            
            # Build response based on debug mode
            if debug_mode:
                # Debug mode: Create ZIP with screenshots/images if available
                bundle_name = None
                bundle_path = None
                try:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    bundle_name = f"{session_id}_{ts}_PREGATE.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session_id
                    
                    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        # Add all screenshots from session (includes Pregate image if captured)
                        session_sc_dir = operations.screens_dir
                        if os.path.isdir(session_sc_dir):
                            for root, _, files in os.walk(session_sc_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    rel = os.path.relpath(fp, session_sc_dir)
                                    arc = os.path.join(session_root, 'screenshots', rel)
                                    zf.write(fp, arc)
                    
                    # Print public download URL
                    if bundle_path and os.path.exists(bundle_path):
                        public_url = f"http://{request.host}/files/{bundle_name}"
                        print(f"\n{'='*70}")
                        print(f"🐛 DEBUG BUNDLE READY")
                        print(f"{'='*70}")
                        print(f"🌐 Bundle URL: {public_url}")
                        print(f"📂 File: {bundle_name}")
                        print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                        print(f"{'='*70}\n")
                    
                except Exception as be:
                    print(f"⚠️ Bundle creation failed: {be}")
                
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                # Return debug response with screenshot
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "container_id": container_id,
                    "passed_pregate": passed_pregate,
                    "timeline": timeline_data,
                    "milestone_count": milestone_count,
                    "detection_method": detection_method,
                    "debug_bundle_url": f"http://{request.host}/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None
                }
                
                # Add image analysis details if method was image processing
                if detection_method == "image_processing" and pregate_status_result.get("analysis"):
                    response_data["image_analysis"] = pregate_status_result["analysis"]
                
                return jsonify(response_data)
            
            else:
                # Working mode: Return Pregate status + full timeline (fast)
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                return jsonify({
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "container_id": container_id,
                    "passed_pregate": passed_pregate,
                    "timeline": timeline_data,
                    "milestone_count": milestone_count,
                    "detection_method": detection_method
                })

        except Exception as op_e:
            return jsonify({"success": False, "error": f"Operation failed: {op_e}"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


@app.route('/get_booking_number', methods=['POST'])
def get_booking_number():
    """
    Navigate to containers page, search for a container, expand its row, and extract booking number.
    
    Inputs:
        - session_id (optional): Use existing session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
        - container_id (required): Container ID to search for
        - debug (optional, default: false): If true, returns debug bundle with screenshots
    
    Returns: JSON with container_id, booking_number (or null), session_id, and optional debug_bundle_url
    """
    request_id = f"booking_{int(time.time())}"
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        container_id = data.get('container_id') or data.get('container')
        debug_mode = data.get('debug', False)
        
        # Only capture screenshots in debug mode
        capture_screens = debug_mode

        if not container_id:
            return jsonify({
                "success": False,
                "error": "Missing required field: container_id"
            }), 400

        logger.info(f"[{request_id}] Booking number request for container: {container_id}")

        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, session_id, is_new_session = result
        
        logger.info(f"[{request_id}] Using session: {session_id} (new={is_new_session})")
        screens_label = data.get('screens_label', username)
        
        # Create session wrapper for EModalBusinessOperations
        class SessionWrapper:
            def __init__(self, driver, session_id):
                self.driver = driver
                self.session_id = session_id
        
        session_wrapper = SessionWrapper(driver, session_id)

        try:
            operations = EModalBusinessOperations(session_wrapper)
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label

            # Ensure app context
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                try:
                    driver.get("https://ecp2.emodal.com/containers")
                    operations._wait_for_app_ready(15)
                except Exception:
                    pass

            # Navigate to containers
            nav = operations.navigate_to_containers()
            if not nav["success"]:
                return jsonify({"success": False, "error": f"Navigation failed: {nav['error']}"}), 500

            # Progressive search during scrolling
            sr = operations.search_container_with_scrolling(container_id)
            if not sr["success"]:
                return jsonify({"success": False, "error": f"Search failed: {sr['error']}"}), 500
            
            # Expand container row
            ex = operations.expand_container_row(container_id)
            if not ex["success"]:
                return jsonify({"success": False, "error": f"Expand failed: {ex['error']}"}), 500

            # Extract booking number
            booking_result = operations.get_booking_number(container_id)
            
            if not booking_result.get("success"):
                return jsonify({
                    "success": False,
                    "error": f"Booking number extraction failed: {booking_result.get('error')}"
                }), 500
            
            booking_number = booking_result.get("booking_number")
            message = booking_result.get("message", "")
            
            print(f"✅ Booking number: {booking_number if booking_number else 'Not available'}")
            
            # Build response based on debug mode
            if debug_mode:
                # Debug mode: Create ZIP with screenshots
                bundle_name = None
                bundle_path = None
                try:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    bundle_name = f"{session_id}_{ts}_BOOKING.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session_id
                    
                    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        # Add all screenshots from session
                        session_sc_dir = operations.screens_dir
                        if os.path.isdir(session_sc_dir):
                            for root, _, files in os.walk(session_sc_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    rel = os.path.relpath(fp, session_sc_dir)
                                    arc = os.path.join(session_root, 'screenshots', rel)
                                    zf.write(fp, arc)
                    
                    # Print public download URL
                    if bundle_path and os.path.exists(bundle_path):
                        public_url = f"http://{request.host}/files/{bundle_name}"
                        print(f"\n{'='*70}")
                        print(f"🐛 DEBUG BUNDLE READY")
                        print(f"{'='*70}")
                        print(f"🌐 Bundle URL: {public_url}")
                        print(f"📂 File: {bundle_name}")
                        print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                        print(f"{'='*70}\n")
                    
                except Exception as be:
                    print(f"⚠️ Bundle creation failed: {be}")
                
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                # Return debug response
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "container_id": container_id,
                    "booking_number": booking_number,
                    "debug_bundle_url": f"/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None
                }
                
                if message:
                    response_data["message"] = message
                
                return jsonify(response_data)
            
            else:
                # Normal mode: Return only booking number (fast)
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "container_id": container_id,
                    "booking_number": booking_number
                }
                
                if message:
                    response_data["message"] = message
                
                return jsonify(response_data)

        except Exception as op_e:
            return jsonify({"success": False, "error": f"Operation failed: {op_e}"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


@app.route('/get_appointments', methods=['POST'])
def get_appointments():
    """
    Navigate to myappointments page, scroll through appointments, select all checkboxes, and download Excel.
    
    Inputs:
        - session_id (optional): Use existing session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
        - infinite_scrolling (optional): If true, scroll until no new content
        - target_count (optional): Number of appointments to select
        - target_appointment_id (optional): Scroll until specific appointment found
        - debug (optional, default: false): If true, returns debug bundle with screenshots
    
    Returns: JSON with session_id, selected_count, file_url (Excel download link), and optional debug_bundle_url
    """
    request_id = f"appointments_{int(time.time())}"
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        debug_mode = data.get('debug', False)
        
        # Determine scrolling mode
        infinite_scrolling = data.get('infinite_scrolling', False)
        target_count = data.get('target_count')
        target_appointment_id = data.get('target_appointment_id')
        
        mode = "infinite"
        target_value = None
        
        if target_count:
            mode = "count"
            target_value = target_count
        elif target_appointment_id:
            mode = "id"
            target_value = target_appointment_id
        
        # Only capture screenshots in debug mode
        capture_screens = debug_mode

        logger.info(f"[{request_id}] Get appointments request (mode: {mode})")

        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, session_id, is_new_session = result
        
        logger.info(f"[{request_id}] Using session: {session_id} (new={is_new_session})")
        screens_label = data.get('screens_label', username)
        
        # Create session wrapper for EModalBusinessOperations
        class SessionWrapper:
            def __init__(self, driver, session_id):
                self.driver = driver
                self.session_id = session_id
        
        session_wrapper = SessionWrapper(driver, session_id)

        try:
            operations = EModalBusinessOperations(session_wrapper)
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label

            # Navigate to myappointments page
            nav = operations.navigate_to_myappointments()
            if not nav["success"]:
                return jsonify({"success": False, "error": f"Navigation failed: {nav['error']}"}), 500

            # Scroll and select checkboxes
            select_result = operations.scroll_and_select_appointment_checkboxes(mode, target_value)
            if not select_result["success"]:
                return jsonify({"success": False, "error": f"Checkbox selection failed: {select_result['error']}"}), 500
            
            selected_count = select_result.get("selected_count", 0)
            print(f"✅ Selected {selected_count} appointments")
            
            # Set up session-specific download directory
            download_dir = os.path.join(DOWNLOADS_DIR, session_id)
            try:
                os.makedirs(download_dir, exist_ok=True)
            except Exception as mkdir_e:
                print(f"⚠️ Could not create download directory: {mkdir_e}")
            
            # CRITICAL: Use absolute path for Linux compatibility
            download_dir_abs = os.path.abspath(download_dir)
            print(f"📁 Download directory: {download_dir_abs}")
            
            # Configure active Chrome session to allow downloads into our dir via DevTools
            try:
                operations.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                    "behavior": "allow",
                    "downloadPath": download_dir_abs
                })
                print("✅ Download behavior configured for session directory")
            except Exception as cdp_e:
                print(f"⚠️ Could not configure download behavior: {cdp_e}")
            
            # Click Excel download button
            download_result = operations.click_excel_download_button()
            if not download_result["success"]:
                return jsonify({"success": False, "error": f"Excel download failed: {download_result['error']}"}), 500
            
            # Wait for file to download
            time.sleep(5)
            
            # Find the downloaded file in the session-specific downloads folder
            download_folder = download_dir
            
            # Look for the most recent Excel file downloaded after clicking the button
            # We'll look for files created in the last 30 seconds to ensure it's the appointments file
            current_time = time.time()
            excel_files = []
            
            for root, dirs, files in os.walk(download_folder):
                for file in files:
                    if file.endswith(('.xlsx', '.xls')):
                        full_path = os.path.join(root, file)
                        file_mtime = os.path.getmtime(full_path)
                        
                        # Only consider files created in the last 30 seconds
                        if current_time - file_mtime <= 30:
                            excel_files.append((full_path, file_mtime))
            
            if excel_files:
                # Sort by modification time, newest first
                excel_files.sort(key=lambda x: x[1], reverse=True)
                excel_file = excel_files[0][0]
                excel_filename = os.path.basename(excel_file)
                
                # Create a unique filename for appointments (already in session directory)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_filename = f"{session_id}_{ts}_appointments.xlsx"
                new_path = os.path.join(download_dir, new_filename)
                
                try:
                    import shutil
                    shutil.move(excel_file, new_path)
                    excel_file = new_path
                    excel_filename = new_filename
                    print(f"✅ Appointments Excel file saved as: {new_filename}")
                except Exception as e:
                    print(f"⚠️ Could not rename Excel file: {e}")
                    # File is already in the right directory, just use current name
                    excel_filename = os.path.basename(excel_file)
                
                # Create full public URL
                excel_url = f"http://{request.host}/files/{excel_filename}"
                print(f"✅ Appointments Excel file ready: {excel_url}")
            else:
                print("⚠️ Appointments Excel file not found in downloads folder")
                # Create debug bundle if requested
                if debug_mode:
                    debug_zip_filename = create_debug_bundle(operations, session_id, request_id)
                    debug_bundle_url = f"http://{request.host}/files/{debug_zip_filename}"
                    
                    return jsonify({
                        "success": False,
                        "error": "Excel file not found after download",
                        "session_id": session_id,
                        "is_new_session": is_new_session,
                        "debug_bundle_url": debug_bundle_url
                    }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": "Excel file not found after download",
                        "session_id": session_id,
                        "is_new_session": is_new_session
                    }), 500
            
            # Build response based on debug mode
            if debug_mode:
                # Debug mode: Create ZIP with screenshots and Excel file
                bundle_name = None
                bundle_path = None
                try:
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    bundle_name = f"{session_id}_{ts}_APPOINTMENTS.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session_id
                    
                    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        # Add all screenshots from session
                        session_sc_dir = operations.screens_dir
                        if os.path.isdir(session_sc_dir):
                            for root, _, files in os.walk(session_sc_dir):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    rel = os.path.relpath(fp, session_sc_dir)
                                    arc = os.path.join(session_root, 'screenshots', rel)
                                    zf.write(fp, arc)
                        
                        # Add Excel file if found
                        if excel_file and os.path.exists(excel_file):
                            zf.write(excel_file, os.path.join(session_root, excel_filename))
                    
                    # Print public download URL
                    if bundle_path and os.path.exists(bundle_path):
                        public_url = f"http://{request.host}/files/{bundle_name}"
                        print(f"\n{'='*70}")
                        print(f"🐛 DEBUG BUNDLE READY")
                        print(f"{'='*70}")
                        print(f"🌐 Bundle URL: {public_url}")
                        print(f"📂 File: {bundle_name}")
                        print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                        print(f"{'='*70}\n")
                    
                except Exception as be:
                    print(f"⚠️ Bundle creation failed: {be}")
                
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                # Return debug response
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "selected_count": selected_count,
                    "file_url": excel_url,
                    "debug_bundle_url": f"http://{request.host}/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None
                }
                
                return jsonify(response_data)
            
            else:
                # Normal mode: Return only Excel URL
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "selected_count": selected_count,
                    "file_url": excel_url
                }
                
                return jsonify(response_data)

        except Exception as op_e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": f"Operation failed: {op_e}"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


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


@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Manually trigger cleanup of old files (24h+)"""
    try:
        logger.info("🗑️ Manual cleanup triggered")
        cleanup_old_files()
        
        # Get current disk usage
        downloads_size = 0
        screenshots_size = 0
        
        if os.path.exists(DOWNLOADS_DIR):
            for root, dirs, files in os.walk(DOWNLOADS_DIR):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        downloads_size += os.path.getsize(fp)
                    except:
                        pass
        
        if os.path.exists(SCREENSHOTS_DIR):
            for root, dirs, files in os.walk(SCREENSHOTS_DIR):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        screenshots_size += os.path.getsize(fp)
                    except:
                        pass
        
        total_size_mb = (downloads_size + screenshots_size) / (1024 * 1024)
        
        return jsonify({
            "success": True,
            "message": "Cleanup completed",
            "current_storage_mb": round(total_size_mb, 2),
            "downloads_mb": round(downloads_size / (1024 * 1024), 2),
            "screenshots_mb": round(screenshots_size / (1024 * 1024), 2)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/cleanup_orphaned_processes', methods=['POST'])
def cleanup_orphaned_processes():
    """
    Clean up orphaned Chrome/ChromeDriver processes.
    Kills processes that are not associated with active sessions.
    """
    try:
        logger.info("🔧 Orphaned process cleanup triggered")
        killed_count = kill_orphaned_chrome_processes()
        
        return jsonify({
            "success": True,
            "message": f"Cleaned up {killed_count} orphaned processes",
            "killed_count": killed_count,
            "active_sessions": len(active_sessions)
        })
    except Exception as e:
        logger.error(f"Error in orphaned process cleanup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/emergency_recovery', methods=['POST'])
def emergency_recovery():
    """
    Emergency recovery: Kill ALL Chrome instances and clear all sessions.
    Use this as a last resort when normal recovery fails.
    WARNING: This will close ALL Chrome browsers on the system.
    """
    try:
        logger.warning("🚨 Emergency recovery triggered")
        killed_count = kill_all_chrome_instances()
        
        return jsonify({
            "success": True,
            "message": f"Emergency recovery completed - killed {killed_count} processes and cleared all sessions",
            "killed_count": killed_count,
            "warning": "All Chrome browsers have been closed",
            "active_sessions": 0
        })
    except Exception as e:
        logger.error(f"Error in emergency recovery: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/get_info_bulk', methods=['POST'])
def get_info_bulk():
    """
    Bulk process multiple containers to extract information efficiently.
    
    For IMPORT containers: Get Pregate status
    For EXPORT containers: Get Booking number
    
    Request JSON:
        - session_id (optional): Use existing session
        OR
        - username, password, captcha_api_key: Create new session
        - import_containers: List of import container IDs (optional)
        - export_containers: List of export container IDs (optional)
        - debug: Boolean for debug mode (default: false)
    
    Returns:
        - Results for each container with status/booking number
        - Session info for reuse
    """
    request_id = f"bulk_{int(time.time())}"
    
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400
        
        data = request.get_json()
        
        # Get container lists
        import_containers = data.get('import_containers', [])
        export_containers = data.get('export_containers', [])
        debug_mode = data.get('debug', False)
        
        if not import_containers and not export_containers:
            return jsonify({
                "success": False,
                "error": "At least one of 'import_containers' or 'export_containers' must be provided"
            }), 400
        
        # Get or create browser session
        result = get_or_create_browser_session(data, request_id)
        
        if len(result) == 5:  # Error case
            _, _, _, _, error_response = result
            return error_response
        
        driver, username, browser_session_id, is_new_browser_session = result
        
        logger.info(f"[{request_id}] Bulk processing for user: {username}")
        logger.info(f"[{request_id}] Import containers: {len(import_containers)}, Export containers: {len(export_containers)}")
        
        # Create wrapper for browser session
        class SessionWrapper:
            def __init__(self, driver, session_id, username):
                self.driver = driver
                self.session_id = session_id
                self.username = username
        
        browser_session = SessionWrapper(driver, browser_session_id, username)
        
        operations = EModalBusinessOperations(browser_session)
        operations.screens_enabled = debug_mode
        operations.screens_label = username
        
        # Ensure we're on containers page
        print("🕒 Ensuring app context is fully loaded...")
        ctx = operations.ensure_app_context(30)
        if not ctx.get("success"):
            print("⚠️ App readiness not confirmed - proceeding anyway...")
        
        # Navigate to containers page
        print("📍 Navigating to containers page...")
        nav_result = operations.navigate_to_containers()
        if not nav_result.get("success"):
            logger.warning(f"Navigation to containers page failed: {nav_result.get('error')}")
            return jsonify({
                "success": False,
                "error": f"Failed to navigate to containers page: {nav_result.get('error')}",
                "session_id": browser_session_id,
                "is_new_session": is_new_browser_session
            }), 500
        
        # Results storage
        results = {
            "import_results": [],
            "export_results": [],
            "summary": {
                "total_import": len(import_containers),
                "total_export": len(export_containers),
                "import_success": 0,
                "import_failed": 0,
                "export_success": 0,
                "export_failed": 0
            }
        }
        
        # Process IMPORT containers (get Pregate status)
        if import_containers:
            print(f"\n📦 Processing {len(import_containers)} IMPORT containers for Pregate status...")
            
            for idx, container_id in enumerate(import_containers, 1):
                print(f"\n[{idx}/{len(import_containers)}] Processing IMPORT: {container_id}")
                
                try:
                    # Set current container for screenshots
                    operations.current_container_id = container_id
                    
                    # Search and expand
                    search_result = operations.search_container_with_scrolling(container_id)
                    if not search_result.get("success"):
                        results["import_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": f"Container not found: {search_result.get('error')}",
                            "pregate_status": None
                        })
                        results["summary"]["import_failed"] += 1
                        continue
                    
                    expand_result = operations.expand_container_row(container_id)
                    if not expand_result.get("success"):
                        results["import_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": f"Failed to expand: {expand_result.get('error')}",
                            "pregate_status": None,
                            "timeline": [],
                            "milestone_count": 0
                        })
                        results["summary"]["import_failed"] += 1
                        continue
                    
                    # Extract full timeline
                    timeline_result = operations.extract_full_timeline()
                    timeline_data = []
                    milestone_count = 0
                    
                    if timeline_result.get("success"):
                        timeline_data = timeline_result.get("timeline", [])
                        milestone_count = timeline_result.get("milestone_count", 0)
                        print(f"  ✅ Extracted {milestone_count} milestones")
                    else:
                        print(f"  ⚠️ Timeline extraction failed: {timeline_result.get('error')}")
                    
                    # Get Pregate status
                    pregate_result = operations.check_pregate_status()
                    
                    if pregate_result.get("success"):
                        results["import_results"].append({
                            "container_id": container_id,
                            "success": True,
                            "pregate_status": pregate_result.get("passed_pregate"),
                            "pregate_details": pregate_result.get("message"),
                            "timeline": timeline_data,
                            "milestone_count": milestone_count
                        })
                        results["summary"]["import_success"] += 1
                        print(f"  ✅ Pregate: {pregate_result.get('passed_pregate')}")
                    else:
                        results["import_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": pregate_result.get("error"),
                            "pregate_status": None,
                            "timeline": timeline_data,
                            "milestone_count": milestone_count
                        })
                        results["summary"]["import_failed"] += 1
                        print(f"  ❌ Failed: {pregate_result.get('error')}")
                    
                    # Collapse the container row before moving to next
                    print(f"  🔽 Collapsing container row...")
                    collapse_result = operations.collapse_container_row(container_id)
                    if collapse_result.get("success"):
                        print(f"  ✅ Container collapsed")
                    else:
                        print(f"  ⚠️ Collapse warning: {collapse_result.get('error')}")
                    
                except Exception as e:
                    logger.error(f"Error processing import container {container_id}: {e}")
                    results["import_results"].append({
                        "container_id": container_id,
                        "success": False,
                        "error": str(e),
                        "pregate_status": None,
                        "timeline": [],
                        "milestone_count": 0
                    })
                    results["summary"]["import_failed"] += 1
                    
                # Small delay between containers to avoid overwhelming the system
                if idx < len(import_containers):
                    time.sleep(0.5)
        
        # Process EXPORT containers (get Booking number)
        if export_containers:
            print(f"\n📦 Processing {len(export_containers)} EXPORT containers for Booking numbers...")
            
            for idx, container_id in enumerate(export_containers, 1):
                print(f"\n[{idx}/{len(export_containers)}] Processing EXPORT: {container_id}")
                
                try:
                    # Set current container for screenshots
                    operations.current_container_id = container_id
                    
                    # Search and expand
                    search_result = operations.search_container_with_scrolling(container_id)
                    if not search_result.get("success"):
                        results["export_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": f"Container not found: {search_result.get('error')}",
                            "booking_number": None
                        })
                        results["summary"]["export_failed"] += 1
                        continue
                    
                    expand_result = operations.expand_container_row(container_id)
                    if not expand_result.get("success"):
                        results["export_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": f"Failed to expand: {expand_result.get('error')}",
                            "booking_number": None
                        })
                        results["summary"]["export_failed"] += 1
                        continue
                    
                    # Get Booking number
                    booking_result = operations.get_booking_number(container_id)
                    
                    if booking_result.get("success"):
                        booking_number = booking_result.get("booking_number")
                        results["export_results"].append({
                            "container_id": container_id,
                            "success": True,
                            "booking_number": booking_number
                        })
                        if booking_number:
                            results["summary"]["export_success"] += 1
                            print(f"  ✅ Booking: {booking_number}")
                        else:
                            results["summary"]["export_success"] += 1
                            print(f"  ⚠️ Booking: Not available")
                    else:
                        results["export_results"].append({
                            "container_id": container_id,
                            "success": False,
                            "error": booking_result.get("error"),
                            "booking_number": None
                        })
                        results["summary"]["export_failed"] += 1
                        print(f"  ❌ Failed: {booking_result.get('error')}")
                    
                    # Collapse the container row before moving to next
                    print(f"  🔽 Collapsing container row...")
                    collapse_result = operations.collapse_container_row(container_id)
                    if collapse_result.get("success"):
                        print(f"  ✅ Container collapsed")
                    else:
                        print(f"  ⚠️ Collapse warning: {collapse_result.get('error')}")
                    
                except Exception as e:
                    logger.error(f"Error processing export container {container_id}: {e}")
                    results["export_results"].append({
                        "container_id": container_id,
                        "success": False,
                        "error": str(e),
                        "booking_number": None
                    })
                    results["summary"]["export_failed"] += 1
                    
                # Small delay between containers to avoid overwhelming the system
                if idx < len(export_containers):
                    time.sleep(0.5)
        
        print(f"\n✅ Bulk processing completed!")
        print(f"   Import: {results['summary']['import_success']}/{results['summary']['total_import']} successful")
        print(f"   Export: {results['summary']['export_success']}/{results['summary']['total_export']} successful")
        
        # Prepare final response
        response_data = {
            "success": True,
            "session_id": browser_session_id,
            "is_new_session": is_new_browser_session,
            "results": results,
            "message": f"Bulk processing completed: {results['summary']['import_success'] + results['summary']['export_success']} successful, {results['summary']['import_failed'] + results['summary']['export_failed']} failed"
        }
        
        # Add debug bundle if requested
        if debug_mode:
            try:
                debug_bundle_path = operations.create_debug_bundle()
                if debug_bundle_path:
                    bundle_filename = os.path.basename(debug_bundle_path)
                    debug_url = f"{request.host_url}debug_bundles/{bundle_filename}"
                    response_data["debug_bundle_url"] = debug_url
            except Exception as debug_error:
                logger.warning(f"Failed to create debug bundle: {debug_error}")
        
        # Release session after operation (in finally-like pattern)
        try:
            release_session_after_operation(browser_session_id)
        except Exception as release_error:
            logger.warning(f"Failed to release session: {release_error}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[{request_id}] Error in bulk processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/files/<path:filename>', methods=['GET'])
def serve_download(filename):
    """Serve downloaded Excel files from the downloads directory"""
    # First try the main downloads directory
    safe_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.abspath(safe_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
        return jsonify({"success": False, "error": "Invalid path"}), 400
    
    if os.path.exists(safe_path):
        return send_file(safe_path, as_attachment=True)
    
    # If not found in main directory, search in session subdirectories
    # Look for files that match the pattern: session_id_timestamp_appointments.xlsx
    if filename.endswith('_appointments.xlsx') and '_' in filename:
        # Extract session_id from filename (everything before the last two underscores)
        parts = filename.split('_')
        if len(parts) >= 3:
            session_id = '_'.join(parts[:-2])  # Everything except last two parts (timestamp and appointments.xlsx)
            session_dir = os.path.join(DOWNLOADS_DIR, session_id)
            
            if os.path.exists(session_dir):
                session_file_path = os.path.join(session_dir, filename)
                if os.path.exists(session_file_path):
                    return send_file(session_file_path, as_attachment=True)
    
    # If still not found, search all subdirectories for the file
    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        if filename in files:
            file_path = os.path.join(root, filename)
            if os.path.abspath(file_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
                return send_file(file_path, as_attachment=True)
    
    return jsonify({"success": False, "error": "File not found"}), 404


if __name__ == '__main__':
    print("🚀 E-Modal Business Operations API")
    print("=" * 50)
    print("✅ Container data extraction")
    print("✅ Excel file downloads")
    print("✅ Browser session management")
    print("✅ Persistent authentication")
    print("✅ Automatic cleanup (24h retention)")
    print("=" * 50)
    print("📍 Endpoints:")
    print("  POST /get_containers - Extract and download container data")
    print("  GET /sessions - List active browser sessions")
    print("  DELETE /sessions/<id> - Close specific session")
    print("  POST /cleanup - Manually trigger file cleanup (24h+)")
    print("  GET /health - Health check")
    print("=" * 50)
    print("🔗 Starting server on http://0.0.0.0:5010")
    print("🗑️ Starting background cleanup task (runs every hour)")
    print("🔄 Starting session refresh task (checks every minute)")
    
    # Start background cleanup thread
    cleanup_thread = threading.Thread(target=periodic_cleanup_task, daemon=True)
    cleanup_thread.start()
    
    # Start background session refresh thread
    refresh_thread = threading.Thread(target=periodic_session_refresh, daemon=True)
    refresh_thread.start()
    
    # Run initial cleanup on startup
    print("🗑️ Running initial cleanup...")
    cleanup_old_files()
    
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=5010,
        debug=False,
        threaded=True
    )

