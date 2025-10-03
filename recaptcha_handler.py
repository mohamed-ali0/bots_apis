#!/usr/bin/env python3
"""
reCAPTCHA Handler for E-Modal Authentication
===========================================

Professional reCAPTCHA handling module with:
- Audio challenge solving using 2captcha
- Fallback for trusted/no-challenge scenarios
- Comprehensive error handling
- Modular design for reusability
"""

import time
import requests
import base64
import tempfile
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import urllib.request


class RecaptchaError(Exception):
    """Custom exception for reCAPTCHA-related errors"""
    pass


class RecaptchaHandler:
    """
    Professional reCAPTCHA handler with audio challenge support
    """
    
    def __init__(self, api_key, timeout=30):
        """
        Initialize reCAPTCHA handler
        
        Args:
            api_key (str): 2captcha API key
            timeout (int): Timeout for operations in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.driver = None
        self.wait = None
    
    def set_driver(self, driver):
        """Set Selenium WebDriver instance"""
        self.driver = driver
        self.wait = WebDriverWait(driver, self.timeout)
    
    def solve_audio_with_2captcha(self, audio_url):
        """
        Solve audio reCAPTCHA using 2captcha service
        
        Args:
            audio_url (str): URL to the audio challenge
            
        Returns:
            str: Transcribed text or None if failed
        """
        try:
            print("🎧 Solving audio reCAPTCHA with 2captcha...")
            
            # Download audio file
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(audio_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                audio_data = response.read()
            
            # Save to temporary file and convert to base64
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_audio_path = temp_file.name
            
            with open(temp_audio_path, 'rb') as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
            
            # Submit to 2captcha
            submit_url = "http://2captcha.com/in.php"
            submit_data = {
                'key': self.api_key,
                'method': 'audio',
                'body': audio_base64,
                'json': 1
            }
            
            response = requests.post(submit_url, data=submit_data)
            response_data = response.json()
            
            if response_data.get('status') == 1:
                captcha_id = response_data.get('request')
                print(f"  ✅ Audio submitted to 2captcha (ID: {captcha_id})")
            else:
                error_text = response_data.get('request', 'Unknown error')
                raise RecaptchaError(f"2captcha submission failed: {error_text}")
            
            # Wait for transcription
            retrieve_url = "http://2captcha.com/res.php"
            max_attempts = 24  # 2 minutes max
            
            for attempt in range(max_attempts):
                time.sleep(5)
                retrieve_params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(retrieve_url, params=retrieve_params)
                result_data = response.json()
                
                if result_data.get('status') == 0:
                    continue
                elif result_data.get('status') == 1:
                    transcribed_text = result_data.get('request')
                    print(f"  ✅ Audio transcribed: '{transcribed_text}'")
                    
                    # Cleanup temp file
                    try:
                        os.unlink(temp_audio_path)
                    except:
                        pass
                    
                    return transcribed_text
                else:
                    error_text = result_data.get('request', 'Transcription failed')
                    raise RecaptchaError(f"2captcha transcription failed: {error_text}")
            
            # Cleanup temp file on timeout
            try:
                os.unlink(temp_audio_path)
            except:
                pass
            
            raise RecaptchaError("2captcha transcription timed out")
            
        except Exception as e:
            raise RecaptchaError(f"Audio solving failed: {str(e)}")
    
    def handle_recaptcha_challenge(self):
        """
        Handle complete reCAPTCHA challenge flow with fallback
        
        Returns:
            dict: Result with success status and details
        """
        if not self.driver:
            raise RecaptchaError("WebDriver not set")
        
        try:
            # Step 1: Click reCAPTCHA checkbox
            print("👆 Clicking reCAPTCHA checkbox...")
            anchor_iframe = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]"))
            )
            self.driver.switch_to.frame(anchor_iframe)
            
            checkbox = self.wait.until(EC.element_to_be_clickable((By.ID, "recaptcha-anchor")))
            checkbox.click()
            print("  ✅ Checkbox clicked")
            
            self.driver.switch_to.default_content()
            
            # Step 2: Check if challenge appears or if trusted
            print("🔍 Checking for challenge or trusted status...")
            time.sleep(3)
            
            # Check if reCAPTCHA is already solved (trusted user)
            try:
                anchor_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
                self.driver.switch_to.frame(anchor_iframe)
                
                checkbox = self.driver.find_element(By.ID, "recaptcha-anchor")
                aria_checked = checkbox.get_attribute("aria-checked")
                
                self.driver.switch_to.default_content()
                
                if aria_checked == "true":
                    print("  ✅ reCAPTCHA trusted - no challenge needed!")
                    return {
                        "success": True,
                        "method": "trusted",
                        "message": "reCAPTCHA passed without challenge"
                    }
            except Exception as e:
                print(f"  ⚠️ Could not check trusted status: {e}")
            
            # Step 3: Look for challenge iframe
            try:
                challenge_iframe = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/bframe')]"))
                )
                print("  📸 Challenge detected - proceeding with audio solving")
            except TimeoutException:
                # No challenge appeared - might be solved already
                print("  ✅ No challenge appeared - likely solved")
                return {
                    "success": True,
                    "method": "no_challenge",
                    "message": "No challenge required"
                }
            
            # Step 4: Switch to audio challenge
            print("🎧 Switching to audio challenge...")
            self.driver.switch_to.frame(challenge_iframe)
            
            # Wait for iframe to fully load (critical on Linux)
            time.sleep(2)
            
            # Find and click audio button
            audio_button_selectors = [
                "#recaptcha-audio-button",
                "button[id*='audio']",
                "button[aria-label*='audio']"
            ]
            
            audio_button = None
            for selector in audio_button_selectors:
                try:
                    audio_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    # Extra check: ensure it's not disabled
                    if audio_button.get_attribute("disabled"):
                        print(f"  ⏳ Audio button is disabled, waiting...")
                        time.sleep(2)
                        audio_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue
            
            if not audio_button:
                raise RecaptchaError("Audio button not found")
            
            # Scroll button into view and click with JavaScript (more reliable on Linux)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", audio_button)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", audio_button)
                print("  ✅ Audio challenge selected (JS click)")
            except:
                # Fallback to regular click
                audio_button.click()
                print("  ✅ Audio challenge selected")
            
            time.sleep(2)  # Wait for audio challenge to load
            
            # Step 5: Click play button and get audio
            print("▶️ Getting audio challenge...")
            play_button_selectors = [
                ".rc-audiochallenge-play-button",
                "button[aria-label*='play']",
                "button[title*='play']",
                "button.rc-button-audio"
            ]
            
            play_button = None
            max_attempts = 3
            for attempt in range(max_attempts):
                for selector in play_button_selectors:
                    try:
                        play_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if play_button.is_displayed():
                            break
                    except:
                        continue
                
                if play_button:
                    break
                
                if attempt < max_attempts - 1:
                    print(f"  ⏳ Play button not found (attempt {attempt + 1}/{max_attempts}), waiting...")
                    time.sleep(2)
            
            if not play_button:
                # Try to take a screenshot for debugging
                try:
                    screenshot_path = f"/tmp/recaptcha_play_button_error_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    print(f"  📸 Screenshot saved: {screenshot_path}")
                except:
                    pass
                raise RecaptchaError("Play button not found after 3 attempts")
            
            # Click with retry logic - prefer JavaScript on Linux
            click_success = False
            for click_attempt in range(3):
                try:
                    if click_attempt == 0:
                        # Try JavaScript click first (most reliable)
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", play_button)
                        time.sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", play_button)
                        print("  ✅ Audio playing (JS click)")
                    elif click_attempt == 1:
                        # Try regular click
                        play_button.click()
                        print("  ✅ Audio playing (regular click)")
                    else:
                        # Final attempt: ActionChains
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(play_button).click().perform()
                        print("  ✅ Audio playing (ActionChains)")
                    
                    click_success = True
                    break
                except Exception as e:
                    if click_attempt < 2:
                        print(f"  ⚠️ Click attempt {click_attempt + 1} failed, retrying... ({str(e)[:50]})")
                        time.sleep(1.5)
                    else:
                        raise
            
            if click_success:
                time.sleep(3)  # Increased wait time for audio to load
            
            # Step 6: Extract audio URL
            print("🎵 Extracting audio URL...")
            audio_url = None
            
            # Look for audio element
            try:
                audio_element = self.driver.find_element(By.TAG_NAME, "audio")
                audio_url = audio_element.get_attribute("src")
            except:
                # Look in page source
                page_source = self.driver.page_source
                audio_patterns = [
                    r'src="([^"]*payload[^"]*)"',
                    r'(https://[^\s]*payload[^\s]*)'
                ]
                
                for pattern in audio_patterns:
                    matches = re.findall(pattern, page_source)
                    if matches:
                        audio_url = matches[0]
                        break
            
            if not audio_url:
                raise RecaptchaError("Could not extract audio URL")
            
            print(f"  🎵 Audio URL found: {audio_url[:50]}...")
            
            # Step 7: Solve with 2captcha
            transcribed_text = self.solve_audio_with_2captcha(audio_url)
            
            # Step 8: Input transcribed text
            print("📝 Entering transcribed text...")
            text_input_selectors = [
                "input[id*='audio']",
                "input[type='text']",
                ".rc-audiochallenge-input-label input"
            ]
            
            text_input = None
            for selector in text_input_selectors:
                try:
                    text_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if text_input.is_displayed():
                        break
                except:
                    continue
            
            if not text_input:
                raise RecaptchaError("Text input field not found")
            
            text_input.clear()
            text_input.send_keys(transcribed_text)
            print("  ✅ Text entered")
            
            # Step 9: Click verify button
            print("✅ Clicking VERIFY...")
            verify_button_selectors = [
                "#recaptcha-verify-button",
                "button[id*='verify']",
                ".rc-audiochallenge-verify-button"
            ]
            
            verify_button = None
            for selector in verify_button_selectors:
                try:
                    verify_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if verify_button.is_displayed():
                        break
                except:
                    continue
            
            if verify_button:
                verify_button.click()
                print("  ✅ VERIFY clicked")
                time.sleep(2)
            
            # Switch back to main content
            self.driver.switch_to.default_content()
            
            # Step 10: Verify solution
            print("⏳ Verifying solution...")
            time.sleep(2)
            
            try:
                anchor_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
                self.driver.switch_to.frame(anchor_iframe)
                
                checkbox = self.driver.find_element(By.ID, "recaptcha-anchor")
                aria_checked = checkbox.get_attribute("aria-checked")
                
                self.driver.switch_to.default_content()
                
                if aria_checked == "true":
                    print("  ✅ reCAPTCHA solved successfully!")
                    return {
                        "success": True,
                        "method": "audio_challenge",
                        "message": f"Audio challenge solved: '{transcribed_text}'"
                    }
                else:
                    raise RecaptchaError("reCAPTCHA solution not accepted")
                    
            except Exception as e:
                raise RecaptchaError(f"Could not verify solution: {str(e)}")
            
        except RecaptchaError:
            raise
        except Exception as e:
            raise RecaptchaError(f"reCAPTCHA handling failed: {str(e)}")
    
    def is_recaptcha_present(self):
        """
        Check if reCAPTCHA is present on the page
        
        Returns:
            bool: True if reCAPTCHA is found
        """
        if not self.driver:
            return False
        
        try:
            recaptcha_elements = self.driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]")
            return len(recaptcha_elements) > 0
        except:
            return False
    
    def wait_for_solved(self, timeout=10):
        """
        Wait for reCAPTCHA to be solved
        
        Args:
            timeout (int): Maximum wait time in seconds
            
        Returns:
            bool: True if solved, False if timeout
        """
        if not self.driver:
            return False
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                anchor_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
                self.driver.switch_to.frame(anchor_iframe)
                
                checkbox = self.driver.find_element(By.ID, "recaptcha-anchor")
                aria_checked = checkbox.get_attribute("aria-checked")
                
                self.driver.switch_to.default_content()
                
                if aria_checked == "true":
                    return True
                    
            except:
                pass
            
            time.sleep(1)
        
        return False

