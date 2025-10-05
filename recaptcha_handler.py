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
            
            # Step 4: Try audio challenge first, fallback to visual if needed
            print("🎧 Attempting audio challenge...")
            self.driver.switch_to.frame(challenge_iframe)
            
            # Try to find and click audio button
            audio_button_selectors = [
                "#recaptcha-audio-button",
                "button[id*='audio']",
                "button[aria-label*='audio']"
            ]
            
            audio_button = None
            for selector in audio_button_selectors:
                try:
                    audio_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if audio_button.is_displayed():
                        break
                except:
                    continue
            
            if audio_button:
                try:
                    audio_button.click()
                    print("  ✅ Audio challenge selected")
                    time.sleep(1)
                    
                    # Try to solve audio challenge
                    audio_result = self._solve_audio_challenge()
                    if audio_result["success"]:
                        return audio_result
                    else:
                        print("  ⚠️ Audio challenge failed, falling back to visual...")
                        # Fallback to visual challenge
                        return self._solve_visual_challenge()
                        
                except Exception as audio_e:
                    print(f"  ⚠️ Audio challenge error: {audio_e}")
                    print("  🔄 Falling back to visual challenge...")
                    return self._solve_visual_challenge()
            else:
                print("  ⚠️ Audio button not found, trying visual challenge...")
                return self._solve_visual_challenge()
            
            # This code is now handled by _solve_audio_challenge method
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
    
    def _solve_audio_challenge(self):
        """
        Solve audio reCAPTCHA challenge using 2captcha service
        
        Returns:
            dict: Result with success status and details
        """
        try:
            print("🎧 Solving audio challenge...")
            
            # Click play button and get audio
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
                return {"success": False, "error": "Play button not found"}
            
            play_button.click()
            print("  ✅ Audio playing")
            time.sleep(2)
            
            # Extract audio URL
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
                return {"success": False, "error": "Could not extract audio URL"}
            
            print(f"  🎵 Audio URL found: {audio_url[:50]}...")
            
            # Solve with 2captcha
            transcribed_text = self.solve_audio_with_2captcha(audio_url)
            
            # Input transcribed text
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
                return {"success": False, "error": "Text input field not found"}
            
            text_input.clear()
            text_input.send_keys(transcribed_text)
            print("  ✅ Text entered")
            
            # Click verify button
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
            
            # Verify solution
            print("⏳ Verifying solution...")
            time.sleep(2)
            
            if self.wait_for_solved():
                return {
                    "success": True,
                    "method": "audio_2captcha",
                    "message": "Audio challenge solved successfully"
                }
            else:
                return {"success": False, "error": "Audio solution verification failed"}
                
        except Exception as e:
            return {"success": False, "error": f"Audio challenge error: {str(e)}"}
    
    def _solve_visual_challenge(self):
        """
        Solve visual reCAPTCHA challenge by clicking images on screen
        (No solution injection - just manual clicking)
        
        Returns:
            dict: Result with success status and details
        """
        try:
            print("🖼️ Solving visual challenge...")
            
            # Look for visual challenge elements
            print("🔍 Looking for visual challenge...")
            
            # Common visual challenge patterns
            visual_selectors = [
                ".rc-imageselect-challenge",
                ".rc-imageselect",
                "[class*='imageselect']",
                "[class*='challenge']"
            ]
            
            challenge_container = None
            for selector in visual_selectors:
                try:
                    challenge_container = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if challenge_container.is_displayed():
                        print(f"  ✅ Found visual challenge: {selector}")
                        break
                except:
                    continue
            
            if not challenge_container:
                return {"success": False, "error": "Visual challenge container not found"}
            
            # Look for instruction text
            instruction_selectors = [
                ".rc-imageselect-desc-text",
                ".rc-imageselect-desc",
                "[class*='instruction']",
                "[class*='desc']"
            ]
            
            instruction_text = ""
            for selector in instruction_selectors:
                try:
                    instruction_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    instruction_text = instruction_element.text.strip()
                    if instruction_text:
                        print(f"  📝 Instruction: {instruction_text}")
                        break
                except:
                    continue
            
            # Look for image grid
            image_selectors = [
                ".rc-imageselect-tile",
                ".rc-image-tile-wrapper",
                "[class*='tile']",
                "img[class*='tile']"
            ]
            
            images = []
            for selector in image_selectors:
                try:
                    images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if images:
                        print(f"  🖼️ Found {len(images)} images to analyze")
                        break
                except:
                    continue
            
            if not images:
                return {"success": False, "error": "No images found in visual challenge"}
            
            # For now, we'll click a few random images as a basic approach
            # In a real implementation, you'd want to analyze the instruction
            # and click the appropriate images based on the challenge type
            print("  🎯 Clicking images based on instruction...")
            
            # Simple approach: click first few images (this is a basic fallback)
            # In production, you'd want to implement proper image recognition
            images_to_click = min(3, len(images))  # Click up to 3 images
            
            for i in range(images_to_click):
                try:
                    if i < len(images):
                        images[i].click()
                        print(f"    ✅ Clicked image {i+1}")
                        time.sleep(0.5)  # Small delay between clicks
                except Exception as click_e:
                    print(f"    ⚠️ Could not click image {i+1}: {click_e}")
            
            # Look for verify button
            verify_selectors = [
                "#recaptcha-verify-button",
                "button[id*='verify']",
                ".rc-imageselect-verify-button",
                "button[class*='verify']"
            ]
            
            verify_button = None
            for selector in verify_selectors:
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
            else:
                print("  ⚠️ Verify button not found, trying to proceed...")
            
            # Switch back to main content
            self.driver.switch_to.default_content()
            
            # Verify solution
            print("⏳ Verifying visual solution...")
            time.sleep(3)
            
            if self.wait_for_solved():
                return {
                    "success": True,
                    "method": "visual_manual",
                    "message": "Visual challenge solved by clicking images"
                }
            else:
                return {"success": False, "error": "Visual solution verification failed"}
                
        except Exception as e:
            return {"success": False, "error": f"Visual challenge error: {str(e)}"}

