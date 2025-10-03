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
            
            # Wait 3 seconds for challenge iframe to fully load
            print("  ⏳ Waiting for challenge iframe to load...")
            time.sleep(3)
            
            # Take screenshot for debugging
            try:
                self.driver.save_screenshot("/tmp/recaptcha_challenge_iframe.png")
                print("  📸 Screenshot saved: /tmp/recaptcha_challenge_iframe.png")
            except:
                pass
            
            # Find and click audio button
            audio_button_selectors = [
                "#recaptcha-audio-button",
                "button[id*='audio']",
                "button[aria-label*='audio']",
                ".rc-button-audio"
            ]
            
            audio_button = None
            for selector in audio_button_selectors:
                try:
                    print(f"  🔍 Trying selector: {selector}")
                    audio_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    print(f"  ✅ Found audio button with: {selector}")
                    break
                except Exception as e:
                    print(f"  ⚠️ Selector failed: {selector} - {str(e)[:50]}")
                    continue
            
            # If still not found, try to see what's in the iframe
            if not audio_button:
                try:
                    body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                    print(f"  📄 Challenge iframe body (first 500 chars):")
                    print(f"  {body_html[:500]}")
                except:
                    pass
                raise RecaptchaError("Audio button not found - reCAPTCHA may be blocking automation")
            
            audio_button.click()
            print("  ✅ Audio challenge selected")
            
            # Wait longer for audio challenge UI to load
            print("  ⏳ Waiting 5 seconds for audio challenge UI...")
            time.sleep(5)
            
            # Take screenshot of audio challenge
            try:
                self.driver.save_screenshot("/tmp/recaptcha_audio_challenge.png")
                print("  📸 Screenshot saved: /tmp/recaptcha_audio_challenge.png")
            except:
                pass
            
            # Step 5: Click play button and get audio
            print("▶️ Getting audio challenge...")
            play_button_selectors = [
                ".rc-audiochallenge-play-button button",  # Play button inside audio challenge
                "button.rc-button.goog-inline-block:not([id])",  # Generic play button without ID
                ".rc-audiochallenge-play-button",
                "button[aria-label*='PLAY']",  # Uppercase PLAY
                "button[title*='PLAY']",
                "button.rc-button:not(#recaptcha-audio-button):not(.rc-button-disabled)"  # Exclude audio button and disabled
            ]
            
            play_button = None
            for selector in play_button_selectors:
                try:
                    print(f"  🔍 Trying play button selector: {selector}")
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        # Check if it's NOT the audio challenge button and NOT disabled
                        btn_id = btn.get_attribute("id")
                        btn_disabled = btn.get_attribute("disabled")
                        btn_class = btn.get_attribute("class") or ""
                        
                        if btn_id == "recaptcha-audio-button":
                            print(f"    ⚠️ Skipping audio challenge button")
                            continue
                        if btn_disabled or "rc-button-disabled" in btn_class:
                            print(f"    ⚠️ Skipping disabled button")
                            continue
                        if btn.is_displayed():
                            play_button = btn
                            print(f"  ✅ Found valid play button with: {selector}")
                            print(f"    Button ID: {btn_id}, Class: {btn_class[:50]}")
                            break
                    if play_button:
                        break
                except Exception as e:
                    print(f"  ⚠️ Play selector failed: {selector} - {str(e)[:80]}")
                    continue
            
            # If still not found, dump the HTML
            if not play_button:
                try:
                    body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                    print(f"  📄 Audio challenge body (first 800 chars):")
                    print(f"  {body_html[:800]}")
                except:
                    pass
                raise RecaptchaError("Play button not found - Audio challenge UI may not have loaded")
            
            play_button.click()
            print("  ✅ Audio playing")
            time.sleep(2)
            
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

