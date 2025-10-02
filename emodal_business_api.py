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

    def load_all_containers_with_infinite_scroll(self) -> Dict[str, Any]:
        """Scroll through containers page to load all content via infinite scrolling"""
        try:
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

            variants = [
                "https://termops.emodal.com/trucker/web/addvisit",
                "https://termops.emodal.com/trucker/web/#/addvisit"
            ]
            last_error = None
            for ix, url in enumerate(variants, start=1):
                print(f"📅 Navigating to appointment page (variant {ix}/{len(variants)}): {url}")
                try:
                    self.driver.get(url)
                except Exception as nav_e:
                    last_error = f"Navigation error: {nav_e}"
                    continue
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except Exception:
                    pass
                self._wait_for_app_ready(25)
                self._capture_screenshot("appointment_attempt")
                current_url = self.driver.current_url or ""
                page_title = self.driver.title or ""
                print(f"  ➜ Current URL: {current_url}")
                print(f"  ➜ Page title: {page_title}")
                if "addvisit" in current_url.lower() or "add visit" in page_title.lower():
                    print("✅ Appointment page loaded")
                    self._capture_screenshot("appointment")
                    return {"success": True, "url": current_url, "title": page_title}
                last_error = f"After navigating to {url}, ended on {current_url} ({page_title})"
            return {"success": False, "error": last_error or "Unknown navigation failure"}
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}
    
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
            
            # First check if already expanded
            try:
                already_expanded = row.find_element(By.XPATH, ".//mat-icon[normalize-space(text())='keyboard_arrow_down']")
                if already_expanded:
                    print("✅ Row is already expanded")
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
                time.sleep(1)
                self._capture_screenshot("row_expanded")
                
                # Verify expansion worked
                try:
                    # Look for expanded content indicators
                    expanded_indicators = [
                        ".//mat-icon[normalize-space(text())='keyboard_arrow_down']",
                        ".//div[contains(@class,'expanded') or contains(@class,'timeline')]",
                        ".//*[contains(@class,'details') or contains(@class,'content')]"
                    ]
                    
                    for indicator in expanded_indicators:
                        try:
                            row.find_element(By.XPATH, indicator)
                            print("✅ Expansion verified - found expanded indicator")
                            return {"success": True, "expanded": True, "method": "expand_click", "selector_used": used_expand_selector}
                        except Exception:
                            continue
                    
                    print("⚠️ Expansion click completed but no expanded indicators found")
                    return {"success": True, "expanded": True, "method": "expand_click_no_verification", "selector_used": used_expand_selector}
                    
                except Exception as verify_e:
                    print(f"⚠️ Could not verify expansion: {verify_e}")
                    return {"success": True, "expanded": True, "method": "expand_click_no_verification", "selector_used": used_expand_selector}
                
            except Exception as click_e:
                return {"success": False, "error": f"Expand click failed: {str(click_e)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Expand failed: {str(e)}"}

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
        "keep_browser_alive": true/false,
        "infinite_scrolling": true/false  (default: true)
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
        return_url = data.get('return_url', False)
        capture_screens = data.get('capture_screens', True)  # Default: enabled for debugging
        screens_label = data.get('screens_label', username)
        infinite_scrolling = data.get('infinite_scrolling', True)  # Default: enabled
        
        if not all([username, password, captcha_api_key]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: username, password, captcha_api_key"
            }), 400
        
        logger.info(f"[{request_id}] Container request for user: {username}")
        logger.info(f"[{request_id}] Keep alive: {keep_alive}")
        logger.info(f"[{request_id}] Infinite scrolling: {infinite_scrolling}")
        
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
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error']}"
                }), 500
            
            # Step 1.5: Load all containers with infinite scroll (if enabled)
            if infinite_scrolling:
                print("📜 Loading all containers with infinite scroll...")
                scroll_result = operations.load_all_containers_with_infinite_scroll()
                if not scroll_result["success"]:
                    print(f"⚠️ Infinite scroll failed: {scroll_result['error']}")
                    # Continue anyway - maybe all containers are already loaded
                else:
                    print(f"✅ Infinite scroll completed: {scroll_result.get('total_containers', 'unknown')} containers loaded")
            else:
                print("⏭️  Infinite scrolling disabled - using first page only")
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
                    bundle_name = f"{session.session_id}_{ts}_FAILED.zip"
                    bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                    session_root = session.session_id
                    
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
                
                if not keep_alive:
                    session.driver.quit()
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
                session_folder = os.path.join(DOWNLOADS_DIR, session.session_id)
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

            # Close or keep session
            if not keep_alive:
                try:
                    session.driver.quit()
                except Exception:
                    pass
                logger.info(f"[{request_id}] Browser session closed")
            else:
                session.update_last_used()
                logger.info(f"[{request_id}] Browser session kept alive: {session.session_id}")

            # Always build a single combined bundle (downloads + screenshots) zip with top-level session folder
            bundle_name = None
            bundle_path = None
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{session.session_id}_{ts}.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                session_root = session.session_id  # top-level folder inside zip
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Include session downloads folder
                    session_dl_dir = os.path.join(DOWNLOADS_DIR, session.session_id)
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
                
                # Print public download URL immediately
                if bundle_path and os.path.exists(bundle_path):
                    public_url = f"http://{request.host}/files/{bundle_name}"
                    print(f"\n{'='*70}")
                    print(f"📦 BUNDLE READY FOR DOWNLOAD")
                    print(f"{'='*70}")
                    print(f"🌐 Public URL: {public_url}")
                    print(f"📂 File: {bundle_name}")
                    print(f"📊 Size: {os.path.getsize(bundle_path)} bytes")
                    print(f"{'='*70}\n")
                
            except Exception as be:
                print(f"⚠️ Bundle creation failed: {be}")

            if return_url:
                response_data = {
                    "success": True,
                    "bundle_url": (f"/files/{os.path.basename(bundle_path)}" if bundle_path and os.path.exists(bundle_path) else None)
                }
                # Add scroll information if available
                if scroll_result.get("success"):
                    response_data["total_containers"] = scroll_result.get("total_containers")
                    response_data["scroll_cycles"] = scroll_result.get("scroll_cycles")
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
                bundle_name = f"{session.session_id}_{ts}_FAILED.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                session_root = session.session_id
                
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Include any partial downloads
                    session_dl_dir = os.path.join(DOWNLOADS_DIR, session.session_id)
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
            
            if not keep_alive:
                try:
                    session.driver.quit()
                except:
                    pass
            
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


@app.route('/make_appointment', methods=['POST'])
def make_appointment():
    """
    Navigate to the Make Appointment (Add Visit) page and return a session bundle
    Same inputs as /get_containers; later steps will be added.
    """
    request_id = f"appointment_{int(time.time())}"
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        captcha_api_key = data.get('captcha_api_key')
        keep_alive = data.get('keep_browser_alive', False)
        return_url = data.get('return_url', True)
        capture_screens = data.get('capture_screens', True)
        screens_label = data.get('screens_label', username)

        if not all([username, password, captcha_api_key]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: username, password, captcha_api_key"
            }), 400

        logger.info(f"[{request_id}] Appointment request for user: {username}")
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

        # Operations
        try:
            operations = EModalBusinessOperations(session)
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label

            # Ensure app context is loaded
            print("🕒 Ensuring app context is fully loaded after login...")
            ctx = operations.ensure_app_context(30)
            if not ctx.get("success"):
                try:
                    print("⚠️ App readiness not confirmed in 30s — requesting appointment directly...")
                    session.driver.get("https://termops.emodal.com/trucker/web/addvisit")
                    operations._wait_for_app_ready(15)
                except Exception:
                    pass

            # Navigate to appointment page
            nav_result = operations.navigate_to_appointment()
            if not nav_result["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Navigation failed: {nav_result['error'] }"
                }), 500

            # Build a session bundle (even if no download yet) for parity
            bundle_name = None
            bundle_path = None
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{session.session_id}_{ts}.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                session_root = session.session_id
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # include session downloads dir (may be empty)
                    session_dl_dir = os.path.join(DOWNLOADS_DIR, session.session_id)
                    if os.path.isdir(session_dl_dir):
                        for root, _, files in os.walk(session_dl_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_dl_dir)
                                arc = os.path.join(session_root, 'downloads', rel)
                                zf.write(fp, arc)
                    # include screenshots
                    session_sc_dir = operations.screens_dir
                    if os.path.isdir(session_sc_dir):
                        for root, _, files in os.walk(session_sc_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_sc_dir)
                                arc = os.path.join(session_root, 'screenshots', rel)
                                zf.write(fp, arc)
            except Exception as be:
                print(f"⚠️ Bundle creation failed: {be}")

            # Close or keep session
            if not keep_alive:
                try:
                    session.driver.quit()
                except Exception:
                    pass
                logger.info(f"[{request_id}] Browser session closed")
            else:
                session.update_last_used()
                logger.info(f"[{request_id}] Browser session kept alive: {session.session_id}")

            if return_url:
                return jsonify({
                    "success": True,
                    "bundle_url": (f"/files/{os.path.basename(bundle_path)}" if bundle_path and os.path.exists(bundle_path) else None)
                })
            else:
                # Return 204 No Content if not returning URL
                return ('', 204)

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


@app.route('/get_container_timeline', methods=['POST'])
def get_container_timeline():
    """
    Navigate to containers page, search for a container, expand its timeline, and report if status is before/after Pregate.
    Inputs: username, password, captcha_api_key, container_id (string). Optional: keep_browser_alive, return_url, capture_screens, screens_label
    Returns: JSON with status and optional bundle_url (when return_url=true)
    """
    request_id = f"timeline_{int(time.time())}"
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        captcha_api_key = data.get('captcha_api_key')
        container_id = data.get('container_id') or data.get('container')
        keep_alive = data.get('keep_browser_alive', False)
        return_url = data.get('return_url', True)
        capture_screens = data.get('capture_screens', True)
        screens_label = data.get('screens_label', username)

        if not all([username, password, captcha_api_key, container_id]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: username, password, captcha_api_key, container_id"
            }), 400

        logger.info(f"[{request_id}] Timeline request for user: {username}, container: {container_id}")

        # Session/login
        try:
            session = create_browser_session(username, password, captcha_api_key, keep_alive)
            if keep_alive:
                active_sessions[session.session_id] = session
        except Exception as login_error:
            return jsonify({"success": False, "error": f"Authentication failed: {str(login_error)}"}), 401

        try:
            operations = EModalBusinessOperations(session)
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
                if not keep_alive:
                    session.driver.quit()
                return jsonify({"success": False, "error": f"Navigation failed: {nav['error']}"}), 500

            # Progressive search during scrolling (more efficient for infinite lists)
            sr = operations.search_container_with_scrolling(container_id)
            if not sr["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({"success": False, "error": f"Search failed: {sr['error']}"}), 500
            ex = operations.expand_container_row(container_id)
            if not ex["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({"success": False, "error": f"Expand failed: {ex['error']}"}), 500

            # Analyze timeline
            an = operations.analyze_timeline()
            if not an["success"]:
                if not keep_alive:
                    session.driver.quit()
                return jsonify({"success": False, "error": f"Timeline analysis failed: {an['error']}"}), 500

            # Bundle artifacts
            bundle_name = None
            bundle_path = None
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bundle_name = f"{session.session_id}_{ts}.zip"
                bundle_path = os.path.join(DOWNLOADS_DIR, bundle_name)
                session_root = session.session_id
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # downloads
                    session_dl_dir = os.path.join(DOWNLOADS_DIR, session.session_id)
                    if os.path.isdir(session_dl_dir):
                        for root, _, files in os.walk(session_dl_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_dl_dir)
                                arc = os.path.join(session_root, 'downloads', rel)
                                zf.write(fp, arc)
                    # screenshots
                    session_sc_dir = operations.screens_dir
                    if os.path.isdir(session_sc_dir):
                        for root, _, files in os.walk(session_sc_dir):
                            for f in files:
                                fp = os.path.join(root, f)
                                rel = os.path.relpath(fp, session_sc_dir)
                                arc = os.path.join(session_root, 'screenshots', rel)
                                zf.write(fp, arc)
            except Exception as be:
                print(f"⚠️ Bundle creation failed: {be}")

            if not keep_alive:
                try:
                    session.driver.quit()
                except Exception:
                    pass

            return jsonify({
                "success": True,
                "container_id": container_id,
                "status": an.get('status'),
                "signals": an.get('signals'),
                "bundle_url": (f"/files/{os.path.basename(bundle_path)}" if bundle_path and os.path.exists(bundle_path) else None)
            })

        except Exception as op_e:
            if not keep_alive:
                try:
                    session.driver.quit()
                except Exception:
                    pass
            return jsonify({"success": False, "error": f"Operation failed: {op_e}"}), 500

    except Exception as e:
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
    print("=" * 50)
    print("📍 Endpoints:")
    print("  POST /get_containers - Extract and download container data")
    print("  GET /sessions - List active browser sessions")
    print("  DELETE /sessions/<id> - Close specific session")
    print("  GET /health - Health check")
    print("=" * 50)
    print("🔗 Starting server on http://0.0.0.0:5010")
    
    app.run(
        host='0.0.0.0',
        port=5010,
        debug=False,
        threaded=True
    )

