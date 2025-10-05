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
        
        # Enhanced anti-detection measures to avoid Google blocking
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-javascript")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-permissions-api")
        chrome_options.add_argument("--disable-presentation-api")
        chrome_options.add_argument("--disable-print-preview")
        chrome_options.add_argument("--disable-speech-api")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        
        # Remove automation indicators
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("detach", True)
        
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
        print("📦 Auto-downloading matching ChromeDriver version...")
        
        # Automatic ChromeDriver architecture fix for Windows
        service = None
        try:
            if platform.system() == 'Windows':
                print("🪟 Detected Windows - applying automatic architecture fix...")
                service = self._get_correct_chromedriver_windows()
            else:
                service = Service(ChromeDriverManager().install())
        except Exception as e:
            print(f"⚠️ ChromeDriver setup failed: {e}")
            print("🔄 Trying fallback approaches...")
            
            # Fallback 1: Try existing chromedriver.exe
            try:
                if os.path.exists("./chromedriver.exe"):
                    print("  📁 Using local chromedriver.exe")
                    service = Service("./chromedriver.exe")
                else:
                    print("  ❌ Local chromedriver.exe not found")
            except Exception as fallback_e:
                print(f"  ⚠️ Local chromedriver failed: {fallback_e}")
            
            # Fallback 2: Try system PATH
            if not service:
                try:
                    print("  🔍 Trying system PATH chromedriver...")
                    service = Service()  # Let Selenium find it in PATH
                except Exception as path_e:
                    print(f"  ❌ PATH chromedriver failed: {path_e}")
                    service = None
        
        if service:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            self.driver = webdriver.Chrome(options=chrome_options)
        
        print("✅ ChromeDriver initialized successfully")
        
        # Apply enhanced stealth measures
        self._apply_stealth_measures()
        
        self.wait = WebDriverWait(self.driver, self.timeout)
        
        # Initialize reCAPTCHA handler
        self.recaptcha_handler = RecaptchaHandler(self.captcha_api_key, self.timeout)
    
    def _apply_stealth_measures(self) -> None:
        """Apply comprehensive stealth measures to avoid detection"""
        try:
            print("🥷 Applying stealth measures...")
            
            # Remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Override automation indicators
            stealth_script = """
            // Remove automation indicators
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            
            // Override chrome detection
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Override getParameter
            const getParameter = WebGLRenderingContext.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter(parameter);
            };
            
            // Override toString methods
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            """
            
            self.driver.execute_script(stealth_script)
            
            # Set realistic user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            ]
            
            import random
            user_agent = random.choice(user_agents)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent,
                "acceptLanguage": "en-US,en;q=0.9",
                "platform": "Win32"
            })
            
            print("✅ Stealth measures applied successfully")
            
        except Exception as e:
            print(f"⚠️  Stealth measures warning: {e}")
            # Continue anyway - stealth is best effort
    
    def _get_correct_chromedriver_windows(self):
        """
        Automatically download and setup correct ChromeDriver for Windows
        Handles win32 vs win64 architecture issues automatically
        """
        try:
            print("🔧 Applying automatic ChromeDriver architecture fix...")
            
            # Step 1: Clear WebDriver Manager cache
            import shutil
            cache_dir = os.path.expanduser("~/.wdm")
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    print("  🗑️ Cleared WebDriver Manager cache")
                except Exception as cache_e:
                    print(f"  ⚠️ Cache clear warning: {cache_e}")
            
            # Step 2: Check if we already have a working chromedriver.exe
            if os.path.exists("./chromedriver.exe"):
                try:
                    # Test if the existing file works
                    test_service = Service("./chromedriver.exe")
                    print("  ✅ Found working local chromedriver.exe")
                    return test_service
                except Exception as test_e:
                    print(f"  ⚠️ Local chromedriver test failed: {test_e}")
                    # Remove the bad file
                    try:
                        os.remove("./chromedriver.exe")
                        print("  🗑️ Removed incompatible chromedriver.exe")
                    except:
                        pass
            
            # Step 3: Download correct win64 ChromeDriver
            print("  📥 Downloading correct win64 ChromeDriver...")
            return self._download_win64_chromedriver()
            
        except Exception as e:
            print(f"  ❌ Automatic fix failed: {e}")
            # Fallback to WebDriver Manager
            print("  🔄 Falling back to WebDriver Manager...")
            return Service(ChromeDriverManager().install())
    
    def _download_win64_chromedriver(self):
        """
        Download the correct win64 ChromeDriver automatically
        """
        try:
            import requests
            import zipfile
            
            # Use a known working ChromeDriver version
            driver_version = "141.0.7390.54"
            download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{driver_version}/win64/chromedriver-win64.zip"
            
            print(f"  🌐 Downloading ChromeDriver {driver_version} (win64)...")
            print(f"  🔗 URL: {download_url}")
            
            # Download the file
            response = requests.get(download_url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"Download failed: HTTP {response.status_code}")
            
            # Save to temporary file
            temp_zip = "chromedriver_temp.zip"
            with open(temp_zip, 'wb') as f:
                f.write(response.content)
            
            print("  📦 Extracting ChromeDriver...")
            
            # Extract zip file
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # Find the chromedriver.exe in the extracted folder
            extracted_dir = "chromedriver-win64"
            chromedriver_path = os.path.join(extracted_dir, "chromedriver.exe")
            
            if os.path.exists(chromedriver_path):
                # Move to current directory
                shutil.move(chromedriver_path, "chromedriver.exe")
                print("  ✅ ChromeDriver extracted successfully")
                
                # Clean up
                os.remove(temp_zip)
                if os.path.exists(extracted_dir):
                    shutil.rmtree(extracted_dir)
                
                # Verify the file
                if os.path.exists("chromedriver.exe"):
                    file_size = os.path.getsize("chromedriver.exe")
                    print(f"  📊 ChromeDriver ready: {file_size} bytes")
                    
                    # Test the service
                    service = Service("./chromedriver.exe")
                    print("  ✅ ChromeDriver service created successfully")
                    return service
                else:
                    raise Exception("ChromeDriver not found after extraction")
            else:
                raise Exception("ChromeDriver executable not found in extracted files")
                
        except Exception as e:
            print(f"  ❌ Download error: {e}")
            raise e
    
    
    def _human_like_click(self, element) -> None:
        """Simulate human-like clicking with mouse movement"""
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            import random
            
            # Move to element with slight offset (like human mouse movement)
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(element, 
                random.randint(-5, 5), random.randint(-5, 5))
            actions.pause(random.uniform(0.1, 0.3))
            actions.click()
            actions.perform()
            
        except Exception:
            # Fallback to regular click
            element.click()
    
    def _human_like_type(self, element, text: str) -> None:
        """Simulate human-like typing with variable delays"""
        try:
            import random
            
            for char in text:
                element.send_keys(char)
                # Variable delay between keystrokes (human-like)
                delay = random.uniform(0.05, 0.25)
                time.sleep(delay)
                
        except Exception:
            # Fallback to regular typing
            element.send_keys(text)
    
    def _human_like_pause(self) -> None:
        """Add human-like random pause"""
        import random
        pause_time = random.uniform(1.5, 3.0)
        print(f"⏳ Human-like pause: {pause_time:.1f}s")
        time.sleep(pause_time)
    
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
        """Fill username and password fields with human-like behavior"""
        try:
            import random
            
            # Find and fill username with human-like typing
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "Username"))
            )
            
            # Human-like click and focus
            self._human_like_click(username_field)
            time.sleep(random.uniform(0.5, 1.0))
            
            # Clear field with human-like behavior
            username_field.clear()
            time.sleep(random.uniform(0.2, 0.5))
            
            # Type with human-like delays
            self._human_like_type(username_field, username)
            
            # Small pause between fields
            time.sleep(random.uniform(0.8, 1.5))
            
            # Find and fill password with human-like typing
            password_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "Password"))
            )
            
            # Human-like click and focus
            self._human_like_click(password_field)
            time.sleep(random.uniform(0.5, 1.0))
            
            # Clear field with human-like behavior
            password_field.clear()
            time.sleep(random.uniform(0.2, 0.5))
            
            # Type with human-like delays
            self._human_like_type(password_field, password)
            
            # Final pause before proceeding
            time.sleep(random.uniform(1.0, 2.0))
            
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
            
            # Human-like pause before reCAPTCHA
            self._human_like_pause()
            
            # Step 4: Handle reCAPTCHA FIRST (LOGIN button is disabled until reCAPTCHA solved)
            print("🔒 Handling reCAPTCHA...")
            recaptcha_result = self._handle_recaptcha()
            if not recaptcha_result.success:
                return recaptcha_result
            print(f"✅ reCAPTCHA handled: {recaptcha_result.recaptcha_method}")
            
            # Human-like pause after reCAPTCHA
            self._human_like_pause()
            
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
