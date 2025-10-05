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
            # Step 1: Click reCAPTCHA checkbox (with retry for loading wheel issue)
            print("👆 Clicking reCAPTCHA checkbox...")
            max_checkbox_attempts = 3
            checkbox_success = False
            
            for attempt in range(max_checkbox_attempts):
                try:
                    anchor_iframe = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]"))
                    )
                    self.driver.switch_to.frame(anchor_iframe)
                    
                    # Wait for checkbox to be fully loaded and clickable
                    checkbox = self.wait.until(EC.element_to_be_clickable((By.ID, "recaptcha-anchor")))
                    
                    # Small delay to ensure iframe is fully rendered (anti-detection + stability)
                    time.sleep(0.5)
                    
                    # Click using JavaScript instead of Selenium click (more reliable for reCAPTCHA)
                    # This avoids mouse movement simulation which can interfere with reCAPTCHA
                    self.driver.execute_script("arguments[0].click();", checkbox)
                    print(f"  ✅ Checkbox clicked via JavaScript (attempt {attempt + 1}/{max_checkbox_attempts})")
                    
                    self.driver.switch_to.default_content()
                    
                    # Wait for reCAPTCHA to process the click
                    # Increased from 3s to 4s for better reliability
                    print("🔍 Waiting for reCAPTCHA response...")
                    time.sleep(4)
                    
                    # Check if we got stuck on loading wheel (aria-checked="false" + no challenge iframe)
                    try:
                        anchor_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
                        self.driver.switch_to.frame(anchor_iframe)
                        
                        checkbox = self.driver.find_element(By.ID, "recaptcha-anchor")
                        aria_checked = checkbox.get_attribute("aria-checked")
                        
                        # Also check for spinner/loading state
                        checkbox_classes = checkbox.get_attribute("class") or ""
                        is_loading = "recaptcha-checkbox-loading" in checkbox_classes
                        
                        self.driver.switch_to.default_content()
                        
                        # Check if challenge iframe exists
                        challenge_exists = False
                        try:
                            self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/bframe')]")
                            challenge_exists = True
                        except:
                            pass
                        
                        # Debug output
                        print(f"  📊 State: aria-checked={aria_checked}, loading={is_loading}, challenge={challenge_exists}")
                        
                        # If checkbox still not checked and no challenge iframe, we're stuck on loading wheel
                        if aria_checked != "true" and not challenge_exists:
                            # If it's actively loading, give it a bit more time
                            if is_loading and attempt == 0:
                                print(f"  ⏳ reCAPTCHA is processing, waiting 2 more seconds...")
                                time.sleep(2)
                                # Re-check after extra wait
                                anchor_iframe = self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/anchor')]")
                                self.driver.switch_to.frame(anchor_iframe)
                                aria_checked = checkbox.get_attribute("aria-checked")
                                self.driver.switch_to.default_content()
                                
                                # Check challenge again
                                try:
                                    self.driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/bframe')]")
                                    challenge_exists = True
                                except:
                                    pass
                                
                                if aria_checked == "true" or challenge_exists:
                                    print(f"  ✅ Success after extra wait!")
                                    checkbox_success = True
                                    break
                            
                            # Still stuck
                            print(f"  ⚠️ Loading wheel detected - checkbox stuck (attempt {attempt + 1})")
                            if attempt < max_checkbox_attempts - 1:
                                print("  🔄 Retrying checkbox click...")
                                time.sleep(3)  # Longer cooldown before retry
                                continue
                            else:
                                print("  ❌ Checkbox still stuck after all attempts")
                                raise RecaptchaError("reCAPTCHA checkbox stuck on loading wheel")
                        else:
                            # Either checkbox is checked or challenge appeared - success!
                            print(f"  ✅ reCAPTCHA responded successfully!")
                            checkbox_success = True
                            break
                            
                    except Exception as check_error:
                        print(f"  ⚠️ Error checking checkbox state: {check_error}")
                        # Assume success and continue
                        checkbox_success = True
                        break
                        
                except Exception as click_error:
                    print(f"  ❌ Checkbox click failed (attempt {attempt + 1}): {click_error}")
                    if attempt < max_checkbox_attempts - 1:
                        print("  🔄 Retrying...")
                        time.sleep(2)
                        self.driver.switch_to.default_content()
                        continue
                    else:
                        raise
            
            if not checkbox_success:
                raise RecaptchaError("Failed to interact with reCAPTCHA checkbox after all attempts")
            
            # Step 2: Check if challenge appears or if trusted
            print("🔍 Checking for challenge or trusted status...")
            time.sleep(2)
            
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
                    break
                except:
                    continue
            
            if not audio_button:
                raise RecaptchaError("Audio button not found")
            
            audio_button.click()
            print("  ✅ Audio challenge selected")
            time.sleep(1)
            
            # Step 5: Click play button and get audio
            print("▶️ Getting audio challenge...")
            play_button_selectors = [
                ".rc-audiochallenge-play-button",
                "button[aria-label*='play']",
                "button[title*='play']"
            ]
            
            play_button = None
            for selector in play_button_selectors:
                try:
                    play_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if play_button.is_displayed():
                        break
                except:
                    continue
            
            if not play_button:
                raise RecaptchaError("Play button not found")
            
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

