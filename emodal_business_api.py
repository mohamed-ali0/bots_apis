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
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if self.keep_alive:
            return False
        return (datetime.now() - self.last_used).seconds > session_timeout
    
    def needs_refresh(self) -> bool:
        """Check if session needs to be refreshed"""
        if not self.keep_alive:
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
            if session.keep_alive and not session.is_expired():
                logger.info(f"Found existing persistent session: {session_id} for user: {username}")
                return session
            else:
                # Clean up expired or non-keep-alive session
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
            browser_session.update_last_used()
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
        # Clean up temp profile on failure
        try:
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
            return
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            raw_path = os.path.join(self.screens_dir, f"{ts}_{tag}.png")
            self.driver.save_screenshot(raw_path)
            print(f"📸 Screenshot saved: {os.path.basename(raw_path)}")
            # Annotate top-right with label and URL
            try:
                img = Image.open(raw_path).convert("RGBA")
                draw = ImageDraw.Draw(img)
                url = self.driver.current_url or ""
                text = f"{self.screens_label} | {url}"
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
                # Measure text using textbbox when available
                try:
                    bbox = draw.textbbox((0,0), text, font=font)
                    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                except Exception:
                    tw, th = draw.textlength(text, font=font), 24
                box_w = tw + padding * 2
                box_h = th + padding * 2
                x0 = img.width - box_w - 10
                y0 = img.height - box_h - 10
                draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(0,0,0,180))
                draw.text((x0 + padding, y0 + padding), text, font=font, fill=(255,255,255,255))
                img.save(raw_path)
            except Exception:
                pass
            self.screens.append(raw_path)
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")

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
            
            # Ensure the window is maximized so scrollbar is available
            try:
                self.driver.maximize_window()
                print("🪟 Maximized window for scrolling")
            except Exception as e:
                print(f"  ⚠️ Could not maximize window: {e}")

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
            
            # Track previous content count
            previous_count = 0
            no_new_content_count = 0
            max_no_new_content_cycles = 6  # 30 seconds (5 sec per cycle)
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
                
                # Check if we've found target container ID
                if target_container_id:
                    try:
                        searchres = self.driver.find_element(By.XPATH, "//div[@id='searchres']")
                        page_text = searchres.text
                        # Clean the target ID (remove trailing letter)
                        import re
                        clean_target = re.sub(r'[A-Z]$', '', target_container_id)
                        if clean_target in page_text or target_container_id in page_text:
                            print(f"  🎯 Target container found: {target_container_id}")
                            self._capture_screenshot("after_infinite_scroll")
                            return {
                                "success": True,
                                "total_containers": current_count,
                                "scroll_cycles": scroll_cycle,
                                "found_target_container": target_container_id,
                                "stopped_reason": f"Container {target_container_id} found"
                            }
                    except Exception as e:
                        print(f"  ⚠️ Error checking for target container: {e}")
                
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

                    # Bring target into view and focus
                    if not using_window:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", scroll_target)
                            time.sleep(0.3)
                            actions.move_to_element(scroll_target).perform()
                            try:
                                scroll_target.click()
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
                
                # Wait a bit before next cycle
                print(f"  ⏱️ Waiting 5 seconds before next cycle...")
                time.sleep(5)
            
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
    
    def select_dropdown_by_text(self, dropdown_label: str, option_text: str) -> Dict[str, Any]:
        """
        Select an option from a Material dropdown by exact text match.
        
        Args:
            dropdown_label: Label of the dropdown (e.g., "Terminal", "Move Type")
            option_text: Exact text of the option to select
        
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
            time.sleep(1)
            
            print(f"  ✅ Opened {dropdown_label} dropdown")
            self._capture_screenshot(f"dropdown_{dropdown_label.lower().replace(' ', '_')}_opened")
            
            # Find option by exact text
            options = self.driver.find_elements(By.XPATH, f"//mat-option//span[normalize-space(text())='{option_text}']")
            
            if not options:
                # Close dropdown
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                except:
                    pass
                return {"success": False, "error": f"Option '{option_text}' not found in {dropdown_label}"}
            
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
        Fill the container number field (chip input).
        Clears existing chips first, then adds the new container.
        
        Args:
            container_id: Container number to add
        
        Returns:
            Dict with success status
        """
        try:
            print(f"📦 Filling container number: {container_id}...")
            
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
            
            # Find the input field
            container_input = None
            try:
                container_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='containerNumber']")
            except:
                try:
                    container_input = self.driver.find_element(By.XPATH, "//input[@placeholder='Container number(s)']")
                except:
                    pass
            
            if not container_input:
                return {"success": False, "error": "Container number input field not found"}
            
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
                return {"success": True, "container_id": container_id}
            else:
                print(f"  ⚠️ Container chip may not have been added, but continuing...")
                self._capture_screenshot("container_added_unverified")
                return {"success": True, "container_id": container_id}
            
        except Exception as e:
            print(f"  ❌ Error filling container number: {e}")
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
            print(f"  ⏳ Waiting 15 seconds for stepper to update...")
            time.sleep(15)
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
    
    def fill_pin_code(self, pin_code: str) -> Dict[str, Any]:
        """Fill the PIN code field in Phase 2"""
        try:
            print(f"🔢 Filling PIN code...")
            pin_input = None
            try:
                pin_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='Pin']")
            except:
                try:
                    pin_input = self.driver.find_element(By.XPATH, "//input[@matinput and contains(@placeholder,'PIN')]")
                except:
                    pass
            if not pin_input:
                return {"success": False, "error": "PIN code field not found"}
            pin_input.click()
            time.sleep(0.3)
            pin_input.clear()
            pin_input.send_keys(pin_code)
            time.sleep(0.5)
            print(f"  ✅ PIN code entered")
            self._capture_screenshot("pin_entered")
            return {"success": True, "pin_code": pin_code}
        except Exception as e:
            print(f"  ❌ Error filling PIN: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_truck_plate(self, truck_plate: str, allow_any_if_missing: bool = True) -> Dict[str, Any]:
        """
        Fill the truck plate field in Phase 2.
        If exact match not found, can select any available option.
        
        Args:
            truck_plate: Desired truck plate number
            allow_any_if_missing: If True, select first available option if exact match fails
        """
        try:
            print(f"🚛 Filling truck plate: {truck_plate}...")
            
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
            
            # Click and type
            plate_input.click()
            time.sleep(0.3)
            plate_input.clear()
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
    
    def toggle_own_chassis(self, own_chassis: bool) -> Dict[str, Any]:
        """Toggle the 'Own Chassis' button"""
        try:
            target = "YES" if own_chassis else "NO"
            print(f"🔘 Setting Own Chassis to: {target}...")
            
            # Find all YES/NO toggle spans
            toggle_spans = self.driver.find_elements(By.XPATH, "//span[text()='YES' or text()='NO']")
            if not toggle_spans:
                return {"success": False, "error": "Own chassis toggle not found"}
            
            # Detect current state by checking multiple indicators
            current_state = None
            current_span = None
            
            for span in toggle_spans:
                try:
                    # Check parent button for checked state
                    parent = span.find_element(By.XPATH, "./ancestor::button[contains(@class,'mat-button-toggle')]")
                    classes = parent.get_attribute("class") or ""
                    aria_pressed = parent.get_attribute("aria-pressed") or ""
                    
                    # Check if this button is currently selected
                    if "mat-button-toggle-checked" in classes or aria_pressed == "true":
                        current_state = span.text
                        current_span = span
                        break
                except:
                    pass
            
            # If still no state detected, assume first one (NO) is default
            if current_state is None:
                current_state = "NO"
                print(f"  📊 Could not detect state, assuming default: {current_state}")
            else:
                print(f"  📊 Current state: {current_state}")
            
            # Check if already in desired state
            if current_state == target:
                print(f"  ✅ Already set to {target} - no action needed")
                self._capture_screenshot("own_chassis_already_set")
                return {"success": True, "own_chassis": own_chassis}
            
            # Need to toggle - find and click the target button
            print(f"  🔄 Changing from {current_state} to {target}...")
            for span in toggle_spans:
                if span.text == target:
                    try:
                        # Scroll into view
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", span)
                        time.sleep(0.5)
                        
                        # Click the span (or its parent button)
                        parent = span.find_element(By.XPATH, "./ancestor::button[contains(@class,'mat-button-toggle')]")
                        parent.click()
                        time.sleep(1)
                        
                        print(f"  ✅ Toggled to {target}")
                        self._capture_screenshot("own_chassis_toggled")
                        return {"success": True, "own_chassis": own_chassis}
                    except Exception as click_error:
                        # Try clicking span directly
                        span.click()
                        time.sleep(1)
                        print(f"  ✅ Toggled to {target} (direct click)")
                        self._capture_screenshot("own_chassis_toggled")
                        return {"success": True, "own_chassis": own_chassis}
            
            return {"success": False, "error": f"Could not find {target} option"}
        except Exception as e:
            print(f"  ❌ Error toggling own chassis: {e}")
            return {"success": False, "error": str(e)}
    
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
            return {"success": True, "available_times": available_times, "count": len(available_times)}
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
            time.sleep(5)  # Wait for page load
            self._capture_screenshot("myappointments_page")
            print("✅ Navigated to My Appointments page")
            return {"success": True}
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def scroll_and_select_appointment_checkboxes(self, mode: str, target_value: Any = None) -> Dict[str, Any]:
        """
        Scroll through appointments and select all checkboxes.
        
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
            max_no_new_content = 6  # Stop after 6 cycles with no new content
            
            while True:
                scroll_cycles += 1
                print(f"\n🔄 Scroll cycle {scroll_cycles}")
                
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
                for checkbox in checkboxes:
                    try:
                        # Check if already selected
                        is_checked = checkbox.get_attribute('aria-checked') == 'true'
                        
                        if not is_checked:
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                            time.sleep(0.3)
                            
                            # Click the checkbox (or its parent mat-checkbox element)
                            try:
                                checkbox.click()
                            except:
                                # If direct click fails, try clicking the parent mat-checkbox
                                parent = checkbox.find_element(By.XPATH, "./ancestor::mat-checkbox")
                                parent.click()
                            
                            time.sleep(0.2)
                            newly_selected += 1
                            selected_count += 1
                            
                            print(f"    ✅ Selected checkbox {selected_count}")
                            
                            # Check if we've reached target count
                            if mode == "count" and target_value and selected_count >= target_value:
                                print(f"  🎯 Target count reached: {selected_count} >= {target_value}")
                                return {"success": True, "selected_count": selected_count}
                                
                    except Exception as e:
                        print(f"    ⚠️ Error selecting checkbox: {e}")
                        continue
                
                if newly_selected > 0:
                    print(f"  ✅ Selected {newly_selected} new checkboxes (total: {selected_count})")
                    no_new_content_count = 0
                else:
                    print(f"  ⏳ No new checkboxes selected")
                    no_new_content_count += 1
                
                # Check if we should stop
                if no_new_content_count >= max_no_new_content:
                    print(f"  🛑 No new checkboxes for {max_no_new_content} cycles, stopping")
                    break
                
                # For infinite mode, continue until no new content
                if mode == "infinite":
                    # Scroll down
                    print(f"  📜 Scrolling down...")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)  # Wait for content to load
                    
                # For count mode, scroll and continue
                elif mode == "count":
                    if selected_count >= target_value:
                        break
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)
                
                # For id mode (search for specific appointment)
                elif mode == "id":
                    # TODO: Implement ID-based search if needed
                    # For now, treat similar to infinite
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)
            
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
            
            # Find the Excel download button (mat-icon with svgicon="xls")
            try:
                excel_button = self.driver.find_element(
                    By.XPATH,
                    "//mat-icon[@svgicon='xls' or contains(@class, 'svg-xls-icon')]"
                )
                print("  ✅ Found Excel download button")
            except:
                # Fallback: look for any Excel-related button
                excel_button = self.driver.find_element(
                    By.XPATH,
                    "//mat-icon[contains(@mattooltip, 'Excel') or @svgicon='xls']"
                )
                print("  ✅ Found Excel download button (fallback)")
            
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", excel_button)
            time.sleep(0.5)
            
            # Click the button
            try:
                excel_button.click()
            except:
                # Fallback: JavaScript click
                self.driver.execute_script("arguments[0].click();", excel_button)
            
            print("  ✅ Excel download button clicked")
            self._capture_screenshot("after_excel_click")
            
            # Wait for download to start
            time.sleep(3)
            
            return {"success": True}
            
        except Exception as e:
            print(f"  ❌ Error clicking Excel button: {e}")
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

    def search_container_with_scrolling(self, container_id: str, max_no_new_content_cycles: int = 8) -> Dict[str, Any]:
        """Search for container while progressively scrolling the page to load more rows.
        Returns early when the container is found.
        """
        try:
            print(f"🔎 Progressive search with scrolling for: {container_id}")
            self._capture_screenshot("before_progressive_search")

            # Reuse the robust scrolling setup: maximize, iframe, focus
            try:
                self.driver.maximize_window()
            except Exception:
                pass
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
            
            # Find the expanded row (should already be expanded)
            try:
                expanded_row = self.driver.find_element(
                    By.XPATH,
                    f"//tr[contains(@class, 'expanded')]"
                )
                print("  ✅ Found expanded row")
            except Exception:
                print("  ⚠️ No expanded row found, attempting to find by container ID")
                # Try to find the detail section directly
                try:
                    expanded_row = self.driver.find_element(
                        By.XPATH,
                        f"//tr[.//td[contains(text(), '{container_id}')]]/following-sibling::tr[contains(@class, 'detail')]"
                    )
                    print("  ✅ Found detail row for container")
                except Exception as e:
                    return {"success": False, "error": f"Could not find expanded row: {str(e)}"}
            
            # Look for "Booking #" label and its corresponding value
            try:
                # Method 1: Find by label text "Booking #"
                booking_label = expanded_row.find_element(
                    By.XPATH,
                    ".//div[contains(@class, 'field-label') and contains(text(), 'Booking #')]"
                )
                print("  ✅ Found 'Booking #' label")
                
                # The value should be in a sibling or parent's sibling with class 'field-data'
                try:
                    # Try finding the field-data in the same parent
                    booking_value_elem = booking_label.find_element(
                        By.XPATH,
                        "..//div[contains(@class, 'field-data')]"
                    )
                except:
                    # Try finding as a following sibling
                    booking_value_elem = booking_label.find_element(
                        By.XPATH,
                        "following-sibling::div[contains(@class, 'field-data')]"
                    )
                
                booking_number = booking_value_elem.text.strip()
                
                if booking_number and booking_number != "N/A":
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
                print(f"  ℹ️ Booking # field not found: {str(e)}")
                # Try Method 2: Look for any field-data with btn-link class (clickable booking numbers)
                try:
                    booking_value_elem = expanded_row.find_element(
                        By.XPATH,
                        ".//div[contains(@class, 'field-data') and contains(@class, 'btn-link') and @style='cursor: pointer;']"
                    )
                    booking_number = booking_value_elem.text.strip()
                    
                    if booking_number:
                        print(f"  ✅ Booking number found (method 2): {booking_number}")
                        return {
                            "success": True,
                            "booking_number": booking_number,
                            "container_id": container_id
                        }
                except:
                    pass
                
                # Booking number doesn't exist for this container
                print("  ℹ️ Booking number field does not exist for this container")
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
        if ("ecp2.emodal.com" in current_url) and ("identity" not in current_url):
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
            raise Exception(f"Login verification failed. URL: {current_url}, Title: {current_title}")
            
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
            # Clean up temp profile on failure
            try:
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
    
    Required fields:
        - session_id (optional): Use existing persistent session, skip login
        OR
        - username, password, captcha_api_key (required if no session_id)
    
    Phase 1 fields (required unless continuing from appointment_session_id):
        - trucking_company: Trucking company name
        - terminal: Terminal name (e.g., "ITS Long Beach")
        - move_type: Move type (e.g., "DROP EMPTY")
        - container_id: Container number
    
    Phase 2 fields (required unless continuing from appointment_session_id):
        - pin_code: PIN code (optional, can be missing)
        - truck_plate: Truck plate number
        - own_chassis: Boolean (true/false)
    
    Session continuation (if error occurred):
        - appointment_session_id: To continue from where it left off (different from session_id)
    
    Returns:
        - success: True/False
        - session_id: Browser session ID (persistent)
        - is_new_session: Whether browser session was newly created
        - appointment_session_id: Appointment workflow session ID
        - available_times: List of appointment time slots
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
        
        # PHASE 1: Dropdowns + Container Number
        if appt_session.current_phase == 1:
            print("\n" + "="*70)
            print("📋 PHASE 1: Trucking Company, Terminal, Move Type, Container")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 1 to fully load...")
            time.sleep(5)
            print("✅ Phase 1 ready")
            
            trucking_company = data.get('trucking_company')
            terminal = data.get('terminal')
            move_type = data.get('move_type')
            container_id = data.get('container_id')
            
            # Check for missing fields
            missing_fields = []
            if not trucking_company:
                missing_fields.append("trucking_company")
            if not terminal:
                missing_fields.append("terminal")
            if not move_type:
                missing_fields.append("move_type")
            if not container_id:
                missing_fields.append("container_id")
            
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
            
            result = operations.fill_container_number(container_id)
            if not result["success"]:
                return jsonify({
                    "success": False,
                    "error": f"Phase 1 failed - Container: {result['error']}",
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
                    operations.fill_container_number(container_id)
                    
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
            appt_session.phase_data.update({
                "trucking_company": trucking_company,
                "terminal": terminal,
                "move_type": move_type,
                "container_id": container_id
            })
            print("✅ Phase 1 completed successfully")
        
        # PHASE 2: Checkbox, PIN, Plate, Chassis
        if appt_session.current_phase == 2:
            print("\n" + "="*70)
            print("📋 PHASE 2: Container Selection, PIN, Truck Plate, Chassis")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 2 to fully load...")
            time.sleep(5)
            print("✅ Phase 2 ready")
            
            pin_code = data.get('pin_code')
            truck_plate = data.get('truck_plate')
            own_chassis = data.get('own_chassis', False)
            
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
            
            # PIN code (optional)
            if pin_code:
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
            
            # Own chassis toggle
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
            
            # Click Next
            result = operations.click_next_button(2)
            if not result["success"]:
                # Check if retry is needed
                if result.get("needs_retry"):
                    print("  🔄 Phase did not advance, re-filling Phase 2 fields before retry...")
                    
                    # Re-fill all Phase 2 fields
                    operations.select_container_checkbox()
                    if pin_code:
                        operations.fill_pin_code(pin_code)
                    operations.fill_truck_plate(truck_plate)
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
            appt_session.phase_data.update({
                "pin_code": pin_code,
                "truck_plate": truck_plate,
                "own_chassis": own_chassis
            })
            print("✅ Phase 2 completed successfully")
        
        # PHASE 3: Get Available Times
        if appt_session.current_phase == 3:
            print("\n" + "="*70)
            print("📋 PHASE 3: Retrieving Available Appointment Times")
            print("="*70)
            
            # Wait 5 seconds for phase to fully load
            print("⏳ Waiting 5 seconds for Phase 3 to fully load...")
            time.sleep(5)
            print("✅ Phase 3 ready")
            
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
        
        # Create debug bundle
        bundle_name = None
        bundle_url = None
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
            
            bundle_url = f"/files/{bundle_name}"
            print(f"\n{'='*70}")
            print(f"📦 DEBUG BUNDLE CREATED")
            print(f"{'='*70}")
            print(f" Public URL: http://89.117.63.196:5010{bundle_url}")
            print(f" File: {bundle_name}")
            print(f" Size: {os.path.getsize(bundle_path)} bytes")
            print(f"{'='*70}\n")
            
        except Exception as be:
            print(f"⚠️ Bundle creation failed: {be}")
        
        # Clean up appointment workflow session (keep browser session alive)
        if appt_session.session_id in appointment_sessions:
            del appointment_sessions[appt_session.session_id]
        
        logger.info(f"[{request_id}] Check appointments completed successfully (browser session kept alive: {browser_session_id})")
        
        return jsonify({
            "success": True,
            "session_id": browser_session_id,
            "is_new_session": is_new_browser_session,
            "appointment_session_id": appt_session.session_id,
            "available_times": available_times,
            "count": len(available_times),
            "debug_bundle_url": bundle_url,
            "phase_data": appt_session.phase_data
        }), 200
    
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
        own_chassis = data.get('own_chassis', False)
        
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
        
        if pin_code:
            result = operations.fill_pin_code(pin_code)
            if not result["success"]:
                return jsonify({"success": False, "error": f"Phase 2 - PIN: {result['error']}"}), 500
        
        result = operations.fill_truck_plate(truck_plate)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - Truck plate: {result['error']}"}), 500
        
        result = operations.toggle_own_chassis(own_chassis)
        if not result["success"]:
            return jsonify({"success": False, "error": f"Phase 2 - Own chassis: {result['error']}"}), 500
        
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
            
            bundle_url = f"/files/{bundle_name}"
            print(f"\n{'='*70}")
            print(f"📦 APPOINTMENT SUBMITTED - DEBUG BUNDLE CREATED")
            print(f"{'='*70}")
            print(f" Public URL: http://89.117.63.196:5010{bundle_url}")
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
                    "detection_method": detection_method,
                    "debug_bundle_url": f"/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None
                }
                
                # Add image analysis details if method was image processing
                if detection_method == "image_processing" and pregate_status_result.get("analysis"):
                    response_data["image_analysis"] = pregate_status_result["analysis"]
                
                return jsonify(response_data)
            
            else:
                # Normal mode: Return only Pregate status (fast)
                logger.info(f"[{request_id}] Session kept alive: {session_id}")
                
                return jsonify({
                    "success": True,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                    "container_id": container_id,
                    "passed_pregate": passed_pregate,
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
            
            # Click Excel download button
            download_result = operations.click_excel_download_button()
            if not download_result["success"]:
                return jsonify({"success": False, "error": f"Excel download failed: {download_result['error']}"}), 500
            
            # Wait for file to download
            time.sleep(5)
            
            # Find the downloaded file in the downloads folder
            download_folder = operations.screens_dir.replace("screenshots", "downloads")
            if not os.path.exists(download_folder):
                download_folder = DOWNLOADS_DIR
            
            # Look for most recent Excel file
            excel_files = []
            for root, dirs, files in os.walk(download_folder):
                for file in files:
                    if file.endswith(('.xlsx', '.xls')):
                        full_path = os.path.join(root, file)
                        excel_files.append((full_path, os.path.getmtime(full_path)))
            
            if excel_files:
                # Sort by modification time, newest first
                excel_files.sort(key=lambda x: x[1], reverse=True)
                excel_file = excel_files[0][0]
                excel_filename = os.path.basename(excel_file)
                
                # Move to downloads folder with session ID prefix if not already there
                if not excel_filename.startswith(session_id):
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"{session_id}_{ts}_appointments.xlsx"
                    new_path = os.path.join(DOWNLOADS_DIR, new_filename)
                    
                    try:
                        import shutil
                        shutil.move(excel_file, new_path)
                        excel_file = new_path
                        excel_filename = new_filename
                        print(f"✅ Excel file moved to: {new_filename}")
                    except Exception as e:
                        print(f"⚠️ Could not move Excel file: {e}")
                
                # Create public URL
                excel_url = f"/files/{excel_filename}"
                print(f"✅ Excel file ready: {excel_url}")
            else:
                print("⚠️ Excel file not found in downloads folder")
                excel_url = None
                excel_filename = None
            
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
                    "debug_bundle_url": f"/files/{bundle_name}" if bundle_path and os.path.exists(bundle_path) else None
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


@app.route('/files/<path:filename>', methods=['GET'])
def serve_download(filename):
    """Serve downloaded Excel files from the downloads directory"""
    safe_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.abspath(safe_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
        return jsonify({"success": False, "error": "Invalid path"}), 400
    if not os.path.exists(safe_path):
        return jsonify({"success": False, "error": "File not found"}), 404
    return send_file(safe_path, as_attachment=True)


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

