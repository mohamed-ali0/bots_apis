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
import zipfile
import pandas as pd
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
            return None
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            raw_path = os.path.join(self.screens_dir, f"{ts}_{tag}.png")
            self.driver.save_screenshot(raw_path)
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
            return raw_path
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")
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

            # If we're on Identity page, first load the app root to refresh session
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
                    container_selectors = [
                        "//tr[contains(@class, 'container') or contains(@class, 'row')]",
                        "//div[contains(@class, 'container') or contains(@class, 'row')]",
                        "//mat-row",
                        "//tbody//tr",
                        "//*[contains(@class, 'mat-table')]//tr",
                        "//*[contains(@class, 'data-row')]",
                        "//*[contains(@class, 'item-row')]"
                    ]
                    
                    current_count = 0
                    for selector in container_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            if elements:
                                current_count = len(elements)
                                print(f"  📊 Found {current_count} containers using selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if current_count == 0:
                        # Fallback: count any clickable rows or items
                        try:
                            all_rows = self.driver.find_elements(By.XPATH, "//tr | //div[contains(@class, 'row')] | //mat-row")
                            current_count = len(all_rows)
                            print(f"  📊 Fallback count: {current_count} total rows/divs")
                        except Exception:
                            pass
                    
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
        """Click checkbox, wait 10 seconds, then proceed regardless of state."""
        try:
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
            from selenium.webdriver.support import expected_conditions as EC
            print("☑️ Looking for 'Select All' checkbox...")
            self._capture_screenshot("before_select_all")

            # 1. Find and click the checkbox
            try:
                checkbox_container = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//thead//mat-checkbox"))
                )
                clickable_target = checkbox_container.find_element(By.TAG_NAME, "label")
                self.driver.execute_script("arguments[0].click();", clickable_target)
                print("   ✅ Clicked checkbox")
            except Exception as click_e:
                print(f"   ⚠️ Could not click checkbox: {click_e}")

            # 2. Wait 10 seconds regardless of checkbox state
            print("   ⏳ Waiting 10 seconds...")
            time.sleep(10)
            
            # 3. Always return success
            print("✅ Proceeding with export after 10-second wait")
            self._capture_screenshot("after_select_all")
            
            return {"success": True, "checkboxes_selected": 0}

        except Exception as e:
            print(f"⚠️ Error in select_all_containers: {e}")
            return {"success": True, "checkboxes_selected": 0}
    
    def download_excel_file(self) -> Dict[str, Any]:
        """Extract container data, create Excel file, and prepare for zip download."""
        try:
            print("📊 Starting data extraction and Excel creation...")
            self._capture_screenshot("before_data_extraction")
            
            # Set up session-specific download directory
            download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
            try:
                os.makedirs(download_dir, exist_ok=True)
            except Exception:
                pass
            
            # Extract container data from the page
            extraction_result = self._extract_container_data()
            containers_data = extraction_result.get("containers", [])
            
            # Create our own Excel file with the extracted data
            excel_filename = f"containers_data_{self.session.session_id}.xlsx"
            excel_path = os.path.join(download_dir, excel_filename)
            excel_created = self._create_excel_file(containers_data, excel_path)
            
            if excel_created:
                print(f"✅ Excel file created successfully: {excel_path}")
            else:
                print("⚠️ Excel file creation failed, but continuing...")
            
            # Take 5 screenshots for documentation
            print("📸 Taking 5 screenshots for documentation...")
            for i in range(5):
                screenshot_name = f"data_extraction_{i+1}"
                self._capture_screenshot(screenshot_name)
                print(f"   📸 Screenshot {i+1}/5: {screenshot_name}")
                time.sleep(2)  # Wait 2 seconds between screenshots
            
            # Create zip file of session folder (includes Excel + screenshots)
            print(f"📦 Creating zip of session folder: {download_dir}")
            zip_path = self._create_session_zip(download_dir)
            self._capture_screenshot("after_zip_creation")
            
            if zip_path and os.path.exists(zip_path):
                file_size = os.path.getsize(zip_path)
                return {
                    "success": True,
                    "download_dir": download_dir,
                    "file_path": zip_path,
                    "file_name": os.path.basename(zip_path),
                    "file_size": file_size,
                    "zip_created": True,
                    "excel_created": excel_created is not None,
                    "containers_extracted": len(containers_data),
                    "extraction_result": extraction_result
                }
            else:
                return {
                    "success": True,
                    "download_dir": download_dir,
                    "file_path": None,
                    "file_name": "zip_creation_failed",
                    "zip_created": False,
                    "excel_created": excel_created is not None,
                    "containers_extracted": len(containers_data)
                }
                
        except Exception as e:
            print(f"⚠️ Error in download_excel_file: {e}")
            return {
                "success": True,
                "download_dir": os.path.join(DOWNLOADS_DIR, self.session.session_id),
                "file_path": None,
                "file_name": "error_occurred",
                "excel_created": False,
                "containers_extracted": 0
            }

    def _extract_container_data(self) -> Dict[str, Any]:
        """Extract container data from the page and return as structured data"""
        try:
            print("📊 Extracting container data from page...")
            
            # Find all container rows
            container_rows = self.driver.find_elements(By.XPATH, "//tbody//tr[contains(@class, 'container') or contains(@class, 'row')]")
            print(f"   Found {len(container_rows)} container rows")
            
            containers_data = []
            
            for i, row in enumerate(container_rows):
                try:
                    # Extract text from all cells in the row
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells:
                        # Try mat-cell for Angular Material tables
                        cells = row.find_elements(By.TAG_NAME, "mat-cell")
                    
                    row_data = {}
                    for j, cell in enumerate(cells):
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_data[f"column_{j+1}"] = cell_text
                    
                    # Try to identify specific columns by common patterns
                    row_text = row.text
                    if "container" in row_text.lower() or "booking" in row_text.lower():
                        # This looks like a container row
                        containers_data.append({
                            "row_number": i + 1,
                            "raw_text": row_text,
                            "columns": row_data,
                            "extracted_at": datetime.now().isoformat()
                        })
                        
                except Exception as cell_e:
                    print(f"   ⚠️ Error extracting row {i+1}: {cell_e}")
                    continue
            
            print(f"✅ Extracted {len(containers_data)} containers")
            return {
                "success": True,
                "containers": containers_data,
                "total_count": len(containers_data),
                "extraction_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error extracting container data: {e}")
            return {
                "success": False,
                "error": str(e),
                "containers": [],
                "total_count": 0
            }

    def _create_excel_file(self, containers_data: list, output_path: str) -> str:
        """Create Excel file with container data"""
        try:
            print(f"📊 Creating Excel file: {output_path}")
            
            # Convert to DataFrame
            df_data = []
            for container in containers_data:
                row_data = {
                    "Row Number": container.get("row_number", ""),
                    "Raw Text": container.get("raw_text", ""),
                    "Extracted At": container.get("extracted_at", "")
                }
                
                # Add individual columns
                columns = container.get("columns", {})
                for col_name, col_value in columns.items():
                    row_data[col_name] = col_value
                
                df_data.append(row_data)
            
            if not df_data:
                # Create empty Excel with headers
                df_data = [{
                    "Row Number": "No data found",
                    "Raw Text": "No containers were extracted",
                    "Extracted At": datetime.now().isoformat()
                }]
            
            df = pd.DataFrame(df_data)
            
            # Create Excel file
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Containers', index=False)
                
                # Add summary sheet
                summary_data = {
                    "Metric": ["Total Containers", "Extraction Time", "API Version"],
                    "Value": [len(containers_data), datetime.now().isoformat(), "1.0"]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            file_size = os.path.getsize(output_path)
            print(f"✅ Excel file created: {output_path} ({file_size} bytes)")
            return output_path
            
        except Exception as e:
            print(f"❌ Error creating Excel file: {e}")
            return None

    def _create_session_zip(self, session_dir: str) -> str:
        """Create a zip file of the session directory and return the zip path"""
        try:
            # Create zip in the public downloads directory
            zip_filename = f"{os.path.basename(session_dir)}.zip"
            zip_path = os.path.join(DOWNLOADS_DIR, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists(session_dir):
                    for root, dirs, files in os.walk(session_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, session_dir)
                            zipf.write(file_path, arcname)
                else:
                    # Create empty zip if directory doesn't exist
                    zipf.writestr("empty_folder.txt", "Session folder was empty or not found")
            
            print(f"📦 Created zip file: {zip_path}")
            return zip_path
        except Exception as e:
            print(f"⚠️ Failed to create zip: {e}")
            return None

    def _try_fallback_download_links(self, download_dir: str) -> Dict[str, Any]:
        """Try fallback download links when main export button fails"""
        try:
            print("🔍 Searching for fallback download links...")
            
            # Look for any download links on the page
            download_link_selectors = [
                "//a[contains(@href, '.xlsx') or contains(@href, '.xls') or contains(@href, 'download')]",
                "//a[contains(@href, 'export') or contains(@href, 'excel')]",
                "//a[contains(text(), 'Download') or contains(text(), 'Export')]",
                "//a[@download]",
                "//a[contains(@class, 'download') or contains(@class, 'export')]",
                "//button[contains(text(), 'Download') or contains(text(), 'Export')]"
            ]
            
            for selector in download_link_selectors:
                try:
                    links = self.driver.find_elements(By.XPATH, selector)
                    for i, link in enumerate(links):
                        if link.is_displayed():
                            print(f"   📎 Found fallback link {i+1}: {selector}")
                            try:
                                self.driver.execute_script("arguments[0].click();", link)
                                print(f"   ✅ Clicked fallback link {i+1}")
                                time.sleep(5)  # Wait for download
                                
                                # Check if file appeared
                                try:
                                    entries = os.listdir(download_dir)
                                    complete_files = [f for f in entries if f.lower().endswith((".xlsx", ".xls", ".csv"))]
                                    if complete_files:
                                        complete_files.sort(key=lambda f: os.path.getmtime(os.path.join(download_dir, f)), reverse=True)
                                        downloaded_file = os.path.join(download_dir, complete_files[0])
                                        file_size = os.path.getsize(downloaded_file)
                                        print(f"✅ Fallback download successful: {os.path.basename(downloaded_file)} ({file_size} bytes)")
                                        return {
                                            "success": True,
                                            "file_path": downloaded_file,
                                            "file_name": os.path.basename(downloaded_file),
                                            "file_size": file_size,
                                            "download_dir": download_dir,
                                            "method": "fallback_link"
                                        }
                                except Exception:
                                    pass
                            except Exception as click_e:
                                print(f"   ❌ Failed to click fallback link {i+1}: {click_e}")
                                continue
                except Exception:
                    continue
            
            # If no fallback links worked, return success with empty file info
            print("⚠️ No fallback links worked, but continuing without error")
            return {
                "success": True,
                "file_path": None,
                "file_name": "no_file_downloaded",
                "file_size": 0,
                "download_dir": download_dir,
                "method": "no_download_available"
            }
            
        except Exception as e:
            print(f"⚠️ Fallback download failed: {e}")
            return {
                "success": True,
                "file_path": None,
                "file_name": "fallback_failed",
                "file_size": 0,
                "download_dir": download_dir,
                "method": "fallback_failed"
            }

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

        # Prime the app root to establish app context if we're still on Identity
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
        return_url = data.get('return_url', False)
        capture_screens = data.get('capture_screens', False)
        screens_label = data.get('screens_label', username)
        
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
            operations.screens_enabled = bool(capture_screens)
            operations.screens_label = screens_label

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
            
            # Step 1.5: Load all containers with infinite scroll (TEMPORARILY DISABLED FOR SPEED)
            print("📜 Infinite scrolling DISABLED - using first page only for speed...")
            # scroll_result = operations.load_all_containers_with_infinite_scroll()
            # if not scroll_result["success"]:
            #     print(f"⚠️ Infinite scroll failed: {scroll_result['error']}")
            #     # Continue anyway - maybe all containers are already loaded
            # else:
            #     print(f"✅ Infinite scroll completed: {scroll_result.get('total_containers', 'unknown')} containers loaded")
            
            # Mock scroll result for compatibility
            scroll_result = {
                "success": True,
                "total_containers": "first_page_only",
                "scroll_cycles": 0,
                "message": "Infinite scroll disabled - first page only"
            }
            
            # Step 2: Select all containers
            print("🔘 Calling select_all_containers...")
            select_result = operations.select_all_containers()
            print(f"🔘 select_all_containers returned: {select_result}")
            if not select_result["success"]:
                print(f"❌ Select all failed: {select_result['error']}")
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Container selection failed: {select_result['error']}"
                }), 500
            
            # Step 3: Download Excel file
            print("📥 Calling download_excel_file...")
            download_result = operations.download_excel_file()
            print(f"📥 download_excel_file returned: {download_result}")
            if not download_result["success"]:
                print(f"❌ Download failed: {download_result['error']}")
                if not keep_alive:
                    session.driver.quit()
                return jsonify({
                    "success": False,
                    "error": f"Download failed: {download_result['error']}"
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
            except Exception as be:
                print(f"⚠️ Bundle creation failed: {be}")

            # Check if we have a zip file from download_result
            if download_result.get("success") and download_result.get("file_path"):
                zip_path = download_result["file_path"]
                if os.path.exists(zip_path):
                    # Move zip file to downloads directory for public access
                    zip_filename = os.path.basename(zip_path)
                    public_zip_path = os.path.join(DOWNLOADS_DIR, zip_filename)
                    try:
                        import shutil
                        shutil.move(zip_path, public_zip_path)
                        print(f"📦 Moved zip file to public directory: {public_zip_path}")
                    except Exception as move_e:
                        print(f"⚠️ Could not move zip file: {move_e}")
                        public_zip_path = zip_path
                    
                    # Return public download URL
                    public_url = f"http://89.117.63.196:5010/files/{zip_filename}"
                    print(f"🌐 Public download URL: {public_url}")
                    return jsonify({
                        "success": True,
                        "download_url": public_url,
                        "file_name": zip_filename,
                        "file_size": download_result.get("file_size", 0),
                        "message": "Zip file ready for download"
                    })
            
            # Fallback to original logic
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
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"[{request_id}] Operation failed: {str(operation_error)}")
            logger.error(f"[{request_id}] Full traceback: {error_details}")
            print(f"❌ Operation failed: {str(operation_error)}")
            print(f"❌ Full traceback: {error_details}")
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
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[{request_id}] Unexpected error: {str(e)}")
        logger.error(f"[{request_id}] Full traceback: {error_details}")
        print(f"❌ Unexpected error: {str(e)}")
        print(f"❌ Full traceback: {error_details}")
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

