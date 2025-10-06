#!/usr/bin/env python3
"""
E-Modal Login Handler
====================

Professional login automation for E-Modal platform with:
- VPN integration support
- Comprehensive error detection
- reCAPTCHA handling with fallbacks
- Robust credential validation
- Detailed error reporting
- API-ready design
- Linux Xvfb support for non-GUI servers
"""

import time
import os
import sys
import platform
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Undetected ChromeDriver for anti-bot detection
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    uc = None

from recaptcha_handler import RecaptchaHandler, RecaptchaError

# Linux Xvfb support for non-GUI servers
try:
    from pyvirtualdisplay import Display
    XVFB_AVAILABLE = True
except ImportError:
    XVFB_AVAILABLE = False
    Display = None


class LoginError(Exception):
    """Base exception for login-related errors"""
    pass


class LoginErrorType(Enum):
    """Types of login errors for detailed error handling"""
    VPN_REQUIRED = "vpn_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    RECAPTCHA_FAILED = "recaptcha_failed"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"
    LOGIN_BUTTON_NOT_FOUND = "login_button_not_found"
    PAGE_LOAD_ERROR = "page_load_error"


@dataclass
class LoginResult:
    """Structured login result with detailed information"""
    success: bool
    error_type: Optional[LoginErrorType] = None
    error_message: Optional[str] = None
    final_url: Optional[str] = None
    page_title: Optional[str] = None
    cookies: Optional[List[Dict]] = None
    session_tokens: Optional[Dict] = None
    recaptcha_method: Optional[str] = None


class EModalLoginHandler:
    """
    Professional E-Modal login handler with comprehensive error detection
    """
    
    def __init__(self, captcha_api_key: str, use_vpn_profile: bool = True, timeout: int = 30, auto_close: bool = True, user_data_dir: Optional[str] = None):
        """
        Initialize E-Modal login handler
        
        Args:
            captcha_api_key (str): 2captcha API key for reCAPTCHA solving
            use_vpn_profile (bool): Whether to use Chrome profile with VPN
            timeout (int): Timeout for operations in seconds
        """
        self.captcha_api_key = captcha_api_key
        self.use_vpn_profile = use_vpn_profile
        self.timeout = timeout
        self.auto_close = auto_close
        self.custom_user_data_dir = user_data_dir
        
        self.driver = None
        self.wait = None
        self.recaptcha_handler = None
        self.display = None  # Xvfb display for Linux
        
        # URLs and selectors
        self.login_url = "https://ecp2.emodal.com/login"
        self.success_indicators = [
            "ecp2.emodal.com",
            "dashboard",
            "portal",
            "signin-oidc",
            "CargoSprint"
        ]
        self.failure_indicators = [
            "Account/Login",
            "403",
            "Forbidden",
            "error"
        ]
    
    def _setup_driver(self) -> None:
        """Setup Chrome WebDriver with optimal configuration and Xvfb support for Linux"""
        
        # Start Xvfb virtual display on Linux non-GUI servers
        if platform.system() == 'Linux' and XVFB_AVAILABLE:
            try:
                # Check if DISPLAY is set (GUI available)
                if not os.environ.get('DISPLAY'):
                    print("🖥️  Starting Xvfb virtual display for Linux non-GUI server...")
                    self.display = Display(visible=0, size=(1920, 1080))
                    self.display.start()
                    print(f"✅ Xvfb started on display: {os.environ.get('DISPLAY')}")
                else:
                    print(f"🖥️  Using existing display: {os.environ.get('DISPLAY')}")
            except Exception as e:
                print(f"⚠️  Xvfb setup failed (will try without): {e}")
                self.display = None
        elif platform.system() == 'Linux' and not XVFB_AVAILABLE:
            print("⚠️  pyvirtualdisplay not installed. Install with: pip install pyvirtualdisplay")
            print("⚠️  Continuing without Xvfb - may fail on non-GUI servers")
        
        chrome_options = Options()
        
        if self.custom_user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={self.custom_user_data_dir}")
            chrome_options.add_argument("--profile-directory=Default")
        elif self.use_vpn_profile:
            # Use existing Chrome profile with VPN - cross-platform paths
            if os.name == 'nt':  # Windows
                user_data_dir = os.path.join(
                    os.environ.get('LOCALAPPDATA', ''), 
                    'Google', 'Chrome', 'User Data'
                )
            else:  # Linux/Unix
                home_dir = os.path.expanduser('~')
                user_data_dir = os.path.join(home_dir, '.config', 'google-chrome')
                if not os.path.exists(user_data_dir):
                    user_data_dir = os.path.join(home_dir, '.config', 'chromium')
            if os.path.exists(user_data_dir):
                chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
                chrome_options.add_argument("--profile-directory=Default")
        
        # Critical options for Linux servers
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configure download behavior (important for Linux)
        prefs = {
            "download.default_directory": "/tmp",  # Will be overridden per-session
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "profile.default_content_settings.popups": 0,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Linux-specific optimizations for server environments
        if platform.system() == 'Linux':
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--disable-hang-monitor")
            chrome_options.add_argument("--disable-prompt-on-repost")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--force-color-profile=srgb")
            chrome_options.add_argument("--metrics-recording-only")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--enable-automation")
            chrome_options.add_argument("--password-store=basic")
            chrome_options.add_argument("--use-mock-keychain")
            # Set window size for consistent rendering
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--start-maximized")
        
        # Initialize driver with automatic ChromeDriver management
        print("🚀 Initializing Chrome WebDriver...")
        
        # Try undetected-chromedriver first for better bot detection avoidance
        if UC_AVAILABLE:
            try:
                print("🔒 Using undetected-chromedriver for anti-bot detection...")
                
                # Convert Options to uc.ChromeOptions
                uc_options = uc.ChromeOptions()
                
                # Copy all arguments from chrome_options
                for arg in chrome_options.arguments:
                    uc_options.add_argument(arg)
                
                # Copy experimental options
                for key, value in chrome_options.experimental_options.items():
                    uc_options.add_experimental_option(key, value)
                
                # Initialize undetected Chrome
                self.driver = uc.Chrome(
                    options=uc_options,
                    use_subprocess=True,
                    version_main=None,  # Auto-detect Chrome version
                )
                print("✅ Undetected ChromeDriver initialized successfully")
                
            except Exception as uc_error:
                print(f"⚠️ Undetected ChromeDriver failed: {uc_error}")
                print("🔄 Falling back to standard ChromeDriver...")
                UC_AVAILABLE_FALLBACK = False
            else:
                UC_AVAILABLE_FALLBACK = True
        else:
            print("ℹ️ Undetected-chromedriver not available, using standard ChromeDriver")
            UC_AVAILABLE_FALLBACK = False
        
        # Fallback to standard ChromeDriver if undetected failed or not available
        if not UC_AVAILABLE or not UC_AVAILABLE_FALLBACK:
            print("📦 Auto-downloading matching ChromeDriver version...")
            try:
                # Clear any corrupted ChromeDriver cache
                try:
                    import shutil
                    cache_dir = os.path.expanduser("~/.wdm")
                    if os.path.exists(cache_dir):
                        print("🧹 Clearing ChromeDriver cache...")
                        shutil.rmtree(cache_dir, ignore_errors=True)
                except Exception:
                    pass
                
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                print("✅ ChromeDriver initialized successfully with webdriver-manager")
            except Exception as wdm_error:
                print(f"⚠️ WebDriver Manager failed: {wdm_error}")
                print("🔄 Trying local chromedriver.exe...")
                
                # Fallback to local chromedriver.exe
                local_chromedriver = os.path.join(os.getcwd(), "chromedriver.exe")
                if os.path.exists(local_chromedriver):
                    try:
                        service = Service(local_chromedriver)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        print("✅ ChromeDriver initialized successfully with local chromedriver.exe")
                    except Exception as local_error:
                        print(f"❌ Local chromedriver.exe also failed: {local_error}")
                        raise Exception(f"Both webdriver-manager and local chromedriver failed. WDM error: {wdm_error}, Local error: {local_error}")
                else:
                    print("❌ No local chromedriver.exe found")
                    raise Exception(f"WebDriver Manager failed and no local chromedriver.exe found. WDM error: {wdm_error}")
            
            # Additional anti-detection for standard ChromeDriver
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except:
                pass
        
        self.wait = WebDriverWait(self.driver, self.timeout)
        
        # Initialize reCAPTCHA handler
        self.recaptcha_handler = RecaptchaHandler(self.captcha_api_key, self.timeout)
        self.recaptcha_handler.set_driver(self.driver)
    
    def _check_vpn_status(self) -> LoginResult:
        """Check if VPN is working (no 403 errors)"""
        try:
            self.driver.get(self.login_url)
            time.sleep(3)
            
            page_title = self.driver.title
            current_url = self.driver.current_url
            
            # Check for 403 errors
            if any(indicator in page_title for indicator in ["403", "Forbidden"]) or \
               any(indicator in current_url for indicator in ["403", "error"]):
                return LoginResult(
                    success=False,
                    error_type=LoginErrorType.VPN_REQUIRED,
                    error_message="Geographic restriction detected. VPN to US required.",
                    final_url=current_url,
                    page_title=page_title
                )
            
            return LoginResult(success=True)
            
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.NETWORK_ERROR,
                error_message=f"Network error during page load: {str(e)}"
            )
    
    def _fill_credentials(self, username: str, password: str) -> LoginResult:
        """Fill username and password fields"""
        try:
            # Find and fill username
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "Username"))
            )
            username_field.clear()
            username_field.send_keys(username)
            
            # Find and fill password
            password_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "Password"))
            )
            password_field.clear()
            password_field.send_keys(password)
            
            return LoginResult(success=True)
            
        except TimeoutException:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.PAGE_LOAD_ERROR,
                error_message="Login form fields not found. Page may have changed."
            )
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.UNKNOWN_ERROR,
                error_message=f"Error filling credentials: {str(e)}"
            )
    
    def _locate_login_button(self) -> tuple:
        """
        Locate LOGIN button before starting reCAPTCHA to prevent timeouts
        
        Returns:
            tuple: (success, login_button_element or error_message)
        """
        try:
            # Wait for page to fully load
            time.sleep(2)
            
            # We know from debug that LOGIN button exists as: button[@type='submit']
            # We just need to wait for it to be enabled after reCAPTCHA
            login_selectors = [
                "//button[@type='submit']",  # Primary - we know this works
                "//button[contains(@class, 'btn') and @type='submit']",  # Backup
                "//*[@type='submit']"  # Fallback
            ]
            
            # Wait up to 10 seconds for button to become enabled after reCAPTCHA
            for attempt in range(10):
                for selector in login_selectors:
                    try:
                        login_button = self.driver.find_element(By.XPATH, selector)
                        
                        is_displayed = login_button.is_displayed()
                        is_enabled = login_button.is_enabled()
                        
                        if is_displayed and is_enabled:
                            # Scroll to button to ensure visibility
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
                            print(f"  ✅ LOGIN button enabled after {attempt+1} attempts")
                            return True, login_button
                        elif is_displayed and not is_enabled:
                            # Button exists but still disabled - keep waiting
                            if attempt == 0:
                                print(f"  ⏳ LOGIN button found but disabled - waiting for reCAPTCHA validation...")
                            break  # Try again after wait
                            
                    except:
                        continue
                
                # Wait 1 second before retry
                time.sleep(1)
            
            # Final attempt with detailed info
            try:
                login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                is_enabled = login_button.is_enabled()
                button_text = login_button.text.strip()
                print(f"❌ LOGIN button still disabled after 10 seconds")
                print(f"   Text: '{button_text}', Enabled: {is_enabled}")
                return False, f"LOGIN button remains disabled - reCAPTCHA may not be properly solved"
            except:
                return False, "LOGIN button not found at all"
            
        except Exception as e:
            print(f"❌ LOGIN button search failed with exception: {str(e)}")
            return False, f"LOGIN button search error: {str(e)}"
    
    def _handle_recaptcha(self) -> LoginResult:
        """Handle reCAPTCHA challenge with comprehensive error handling"""
        try:
            if not self.recaptcha_handler.is_recaptcha_present():
                return LoginResult(
                    success=True,
                    recaptcha_method="not_present"
                )
            
            result = self.recaptcha_handler.handle_recaptcha_challenge()
            
            return LoginResult(
                success=result["success"],
                recaptcha_method=result.get("method"),
                error_message=result.get("message") if not result["success"] else None,
                error_type=LoginErrorType.RECAPTCHA_FAILED if not result["success"] else None
            )
            
        except RecaptchaError as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.RECAPTCHA_FAILED,
                error_message=f"reCAPTCHA error: {str(e)}"
            )
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.UNKNOWN_ERROR,
                error_message=f"Unexpected reCAPTCHA error: {str(e)}"
            )
    
    def _click_login_button(self, login_button) -> LoginResult:
        """Click the pre-located LOGIN button"""
        try:
            # Ensure page focus
            self.driver.execute_script("window.focus();")
            self.driver.execute_script("document.body.focus();")
            
            # Final scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
            time.sleep(0.5)
            
            # Click button
            login_button.click()
            
            return LoginResult(success=True)
            
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.LOGIN_BUTTON_NOT_FOUND,
                error_message=f"Failed to click LOGIN button: {str(e)}"
            )
    
    def _handle_post_login_alerts(self) -> None:
        """Handle any JavaScript alerts after login"""
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            print(f"📢 Alert detected: '{alert_text}'")
            alert.accept()
            print("✅ Alert dismissed")
            time.sleep(1)
        except:
            # No alert present
            pass
    
    def _analyze_final_result(self) -> LoginResult:
        """Analyze final page to determine login success/failure"""
        try:
            # Wait for page to load
            time.sleep(5)
            
            # Handle any alerts
            self._handle_post_login_alerts()
            
            final_url = self.driver.current_url
            final_title = self.driver.title
            
            # Get cookies
            cookies = self.driver.get_cookies()
            
            # Extract session tokens
            session_tokens = {}
            for cookie in cookies:
                if any(term in cookie['name'].lower() for term in ['auth', 'token', 'session']):
                    session_tokens[cookie['name']] = cookie['value']
            
            # Determine success based on URL and page content
            is_success = False
            error_message = None
            error_type = None
            
            # Check for success indicators
            if any(indicator.lower() in final_url.lower() or indicator.lower() in final_title.lower() 
                   for indicator in self.success_indicators):
                is_success = True
            
            # Check for failure indicators
            elif any(indicator.lower() in final_url.lower() or indicator.lower() in final_title.lower()
                    for indicator in self.failure_indicators):
                is_success = False
                
                # Determine specific error type
                if "login" in final_url.lower() or "Account/Login" in final_url:
                    # Still on login page - likely credential error
                    error_type = LoginErrorType.INVALID_CREDENTIALS
                    error_message = "Login failed - likely invalid credentials"
                elif "403" in final_title or "Forbidden" in final_title:
                    error_type = LoginErrorType.VPN_REQUIRED
                    error_message = "Access forbidden - VPN required"
                else:
                    error_type = LoginErrorType.UNKNOWN_ERROR
                    error_message = "Login failed for unknown reason"
            
            # Check for welcome/success page indicators
            elif "CargoSprint" in final_title or "signin-oidc" in final_url:
                is_success = True
            
            else:
                # Ambiguous result - check for specific error indicators on page
                try:
                    page_source = self.driver.page_source.lower()
                    
                    if any(term in page_source for term in ["invalid", "incorrect", "failed"]):
                        error_type = LoginErrorType.INVALID_CREDENTIALS
                        error_message = "Invalid credentials detected"
                        is_success = False
                    elif "welcome" in page_source or "dashboard" in page_source:
                        is_success = True
                    else:
                        error_type = LoginErrorType.UNKNOWN_ERROR
                        error_message = f"Uncertain login result. URL: {final_url}, Title: {final_title}"
                        is_success = False
                        
                except:
                    error_type = LoginErrorType.UNKNOWN_ERROR
                    error_message = "Could not determine login result"
                    is_success = False
            
            return LoginResult(
                success=is_success,
                error_type=error_type,
                error_message=error_message,
                final_url=final_url,
                page_title=final_title,
                cookies=cookies,
                session_tokens=session_tokens
            )
            
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.UNKNOWN_ERROR,
                error_message=f"Error analyzing result: {str(e)}"
            )
    
    def login(self, username: str, password: str) -> LoginResult:
        """
        Main login function - API entry point
        
        Args:
            username (str): E-Modal username
            password (str): E-Modal password
            
        Returns:
            LoginResult: Detailed login result with success status and error information
        """
        try:
            print(f"🚀 Starting E-Modal login for user: {username}")
            
            # Step 1: Setup WebDriver
            print("🌐 Initializing browser...")
            self._setup_driver()
            
            # Step 2: Check VPN/Access
            print("🔍 Checking VPN status...")
            vpn_result = self._check_vpn_status()
            if not vpn_result.success:
                return vpn_result
            print("✅ VPN/Access OK")
            
            # Step 3: Fill credentials
            print("📝 Filling credentials...")
            cred_result = self._fill_credentials(username, password)
            if not cred_result.success:
                return cred_result
            print("✅ Credentials filled")
            
            # Step 4: Handle reCAPTCHA FIRST (LOGIN button is disabled until reCAPTCHA solved)
            print("🔒 Handling reCAPTCHA...")
            recaptcha_result = self._handle_recaptcha()
            if not recaptcha_result.success:
                return recaptcha_result
            print(f"✅ reCAPTCHA handled: {recaptcha_result.recaptcha_method}")
            
            # Step 5: Now locate enabled LOGIN button (should be enabled after reCAPTCHA)
            print("🔍 Locating now-enabled LOGIN button...")
            login_found, login_button = self._locate_login_button()
            if not login_found:
                return LoginResult(
                    success=False,
                    error_type=LoginErrorType.LOGIN_BUTTON_NOT_FOUND,
                    error_message=f"LOGIN button still disabled after reCAPTCHA: {login_button}"
                )
            print("✅ LOGIN button located and enabled")
            
            # Step 6: Click LOGIN button immediately
            print("🔘 Clicking LOGIN...")
            click_result = self._click_login_button(login_button)
            if not click_result.success:
                return click_result
            print("✅ LOGIN clicked")
            
            # Step 7: Analyze final result
            print("📊 Analyzing result...")
            final_result = self._analyze_final_result()
            
            if final_result.success:
                print("🎉 LOGIN SUCCESSFUL!")
                print(f"📍 Final URL: {final_result.final_url}")
                print(f"🍪 Cookies: {len(final_result.cookies)} received")
                print(f"🔑 Session tokens: {len(final_result.session_tokens)} extracted")
            else:
                print("❌ LOGIN FAILED")
                print(f"🔍 Error type: {final_result.error_type.value}")
                print(f"📝 Error message: {final_result.error_message}")
            
            return final_result
            
        except Exception as e:
            return LoginResult(
                success=False,
                error_type=LoginErrorType.UNKNOWN_ERROR,
                error_message=f"Unexpected error during login: {str(e)}"
            )
        
        finally:
            # Cleanup
            if self.driver and self.auto_close:
                try:
                    self.driver.quit()
                    print("🔒 Browser closed")
                except:
                    pass
            
            # Stop Xvfb display if we started it
            if self.display:
                try:
                    self.display.stop()
                    print("🖥️  Xvfb display stopped")
                except:
                    pass


def emodal_login(username: str, password: str, captcha_api_key: str, use_vpn: bool = True) -> Dict[str, Any]:
    """
    Simplified API function for E-Modal login
    
    Args:
        username (str): E-Modal username
        password (str): E-Modal password
        captcha_api_key (str): 2captcha API key
        use_vpn (bool): Whether to use VPN profile
        
    Returns:
        dict: Login result with success status and details
    """
    handler = EModalLoginHandler(captcha_api_key, use_vpn)
    result = handler.login(username, password)
    
    # Convert to dictionary for API compatibility
    return {
        "success": result.success,
        "error_type": result.error_type.value if result.error_type else None,
        "error_message": result.error_message,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "cookies": result.cookies,
        "session_tokens": result.session_tokens,
        "recaptcha_method": result.recaptcha_method
    }
