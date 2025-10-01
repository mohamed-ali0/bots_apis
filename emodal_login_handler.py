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
"""

import time
import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from recaptcha_handler import RecaptchaHandler, RecaptchaError


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
        """Setup Chrome WebDriver with optimal configuration"""
        chrome_options = Options()
        
        # Headless/Xvfb configuration for non-GUI servers
        self._virtual_display = None
        try:
            # Enable virtual framebuffer (Xvfb) when requested (Linux only)
            use_xvfb = os.environ.get('USE_XVFB', '1').lower() in ['1', 'true', 'yes', 'y']
            if os.name != 'nt' and use_xvfb:
                try:
                    from pyvirtualdisplay import Display  # type: ignore
                    self._virtual_display = Display(visible=0, size=(1920, 1080))
                    self._virtual_display.start()
                    print("🖥️ Started virtual X framebuffer (Xvfb) 1920x1080")
                except Exception as xvfb_e:
                    print(f"⚠️ Could not start Xvfb virtual display: {xvfb_e}")
        except Exception:
            pass
        
        # Decide headless early for profile strategy
        headless = os.environ.get('HEADLESS', '1').lower() in ['1', 'true', 'yes', 'y']
        
        # Unique user-data-dir strategy (prevents 'already in use' conflicts on servers)
        unique_profiles = os.environ.get('UNIQUE_CHROME_PROFILE', '1').lower() in ['1', 'true', 'yes', 'y']
        explicit_user_data_env = os.environ.get('CHROME_USER_DATA_DIR')
        temp_profile_dir = None
        
        # Optional user profiles (priority order): explicit env -> custom -> vpn profile -> unique temp
        if explicit_user_data_env:
            chrome_options.add_argument(f"--user-data-dir={explicit_user_data_env}")
            chrome_options.add_argument("--profile-directory=Default")
            print(f"👤 Using explicit CHROME_USER_DATA_DIR: {explicit_user_data_env}")
        elif self.custom_user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={self.custom_user_data_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            print(f"👤 Using custom user data dir: {self.custom_user_data_dir}")
        elif self.use_vpn_profile and not (headless and unique_profiles):
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
                print(f"👤 Using VPN profile at: {user_data_dir}")
        else:
            # Default: create a unique user data dir to avoid locking conflicts (server/headless)
            try:
                base_tmp = os.environ.get('TMPDIR') or '/tmp' if os.name != 'nt' else os.environ.get('TEMP', None)
                if not base_tmp:
                    base_tmp = os.getcwd()
                import uuid, time
                temp_profile_dir = os.path.join(base_tmp, f"emodal_chrome_{int(time.time())}_{uuid.uuid4().hex[:8]}")
                os.makedirs(temp_profile_dir, exist_ok=True)
                chrome_options.add_argument(f"--user-data-dir={temp_profile_dir}")
                chrome_options.add_argument("--profile-directory=Default")
                print(f"🗂️ Using unique Chrome profile dir: {temp_profile_dir}")
            except Exception as mk_e:
                print(f"⚠️ Could not create unique profile dir: {mk_e}")
        
        # Optimize for automation - Linux-compatible options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Headless sizing and stability
        if headless:
            # Use new headless for Chrome >=109
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--hide-scrollbars")
            chrome_options.add_argument("--force-device-scale-factor=1")
        else:
            # Ensure a large window even if running under Xvfb
            chrome_options.add_argument("--window-size=1920,1080")
        
        # Linux-specific optimizations
        if os.name != 'nt':  # Non-Windows systems
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        
        # Initialize driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Maximize or set size explicitly to ensure scroll containers render fully
        try:
            if not headless:
                self.driver.maximize_window()
        except Exception:
            try:
                self.driver.set_window_size(1920, 1080)
            except Exception:
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
