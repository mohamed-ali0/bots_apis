"""
Appointment Operations
Business logic for appointment booking workflows.
"""

import time
import os
from typing import Dict, Any, Optional
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.screenshot_utils import capture_screenshot


class AppointmentOperations:
    """
    Handles all appointment-related business operations.
    """
    
    # Appointment URLs
    APPOINTMENT_URL = "https://termops.emodal.com/trucker/web/addvisit"
    
    def __init__(self, driver, screenshot_dir: str):
        """
        Initialize appointment operations.
        
        Args:
            driver: Selenium WebDriver instance
            screenshot_dir: Directory for screenshots
        """
        self.driver = driver
        self.screenshot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)
    
    def _capture_screenshot(self, name: str) -> Optional[str]:
        """Helper to capture screenshot"""
        return capture_screenshot(self.driver, name, self.screenshot_dir)
    
    def navigate_to_appointment(self) -> Dict[str, Any]:
        """
        Navigate to the appointment booking page.
        
        Returns:
            Dict with success status
        """
        try:
            print(f"🚀 Navigating to appointment page...")
            print(f"  📍 URL: {self.APPOINTMENT_URL}")
            
            self._capture_screenshot("before_appointment_navigation")
            
            self.driver.get(self.APPOINTMENT_URL)
            
            # Wait 30 seconds for page to fully load
            print("⏳ Waiting 30 seconds for appointment page to fully load...")
            self._capture_screenshot("appointment_before_wait")
            time.sleep(30)
            print("✅ Page load wait complete")
            
            self._capture_screenshot("appointment_after_wait")
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            print(f"  ➜ Current URL: {current_url}")
            print(f"  ➜ Page title: {page_title}")
            
            # Check if we're on the right page
            if "addvisit" in current_url.lower() or "appointment" in page_title.lower():
                print("✅ Appointment page loaded successfully")
                return {"success": True, "url": current_url}
            else:
                print(f"⚠️ May not be on appointment page, but continuing...")
                return {"success": True, "url": current_url}
                
        except Exception as e:
            print(f"❌ Error navigating to appointment page: {e}")
            return {"success": False, "error": str(e)}
    
    def select_dropdown_by_text(self, dropdown_label: str, option_text: str) -> Dict[str, Any]:
        """
        Select an option from a Material dropdown by exact text match.
        
        Args:
            dropdown_label: Label of the dropdown (Trucking, Terminal, Move)
            option_text: Exact text of the option to select
        
        Returns:
            Dict with success status
        """
        try:
            print(f"🔽 Selecting '{option_text}' from '{dropdown_label}' dropdown...")
            
            # Find dropdown by label
            dropdowns = self.driver.find_elements(By.XPATH,
                f"//mat-label[contains(text(),'{dropdown_label}')]/ancestor::mat-form-field//mat-select")
            
            if not dropdowns:
                return {"success": False, "error": f"{dropdown_label} dropdown not found"}
            
            dropdown = dropdowns[0]
            
            # Click to open dropdown
            self.driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
            time.sleep(0.5)
            dropdown.click()
            time.sleep(1)
            
            print(f"  ✅ Opened {dropdown_label} dropdown")
            self._capture_screenshot(f"dropdown_{dropdown_label.lower().replace(' ', '_')}_opened")
            
            # Find option by exact text
            options = self.driver.find_elements(By.XPATH,
                f"//mat-option//span[normalize-space(text())='{option_text}']")
            
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
            print(f"  ❌ Error selecting from {dropdown_label}: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_container_number(self, container_id: str) -> Dict[str, Any]:
        """
        Fill the container number input (chip list).
        
        Args:
            container_id: Container number to add
        
        Returns:
            Dict with success status
        """
        try:
            print(f"📦 Filling container number: {container_id}...")
            
            # Clear existing chips first
            remove_buttons = self.driver.find_elements(By.XPATH,
                "//mat-icon[@matchipremove and contains(text(),'cancel')]")
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
                container_input = self.driver.find_element(By.XPATH,
                    "//input[@formcontrolname='containerNumber']")
            except:
                try:
                    container_input = self.driver.find_element(By.XPATH,
                        "//input[@placeholder='Container number(s)']")
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
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
                print(f"  ✅ Container chip confirmed")
            except:
                pass
            
            # Verify chip was added
            chips = self.driver.find_elements(By.XPATH,
                f"//mat-chip//span[contains(text(),'{container_id}')]")
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
        
        Returns:
            Phase number (1-4) or 0 if unable to detect
        """
        try:
            # Find the selected/active step header
            selected_headers = self.driver.find_elements(By.XPATH,
                "//mat-step-header[contains(@class,'mat-step-icon-selected')]")
            
            if selected_headers:
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
            
            # Find Next button (prioritize active button with 'text-next' class)
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
            
            next_button = visible_buttons[0] if visible_buttons else next_buttons[0]
            print(f"  ✅ Found visible and enabled Next button")
            
            # Scroll into view (center of viewport)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                next_button
            )
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
                    return {
                        "success": False,
                        "error": f"Phase did not advance from {stepper_phase_before}",
                        "needs_retry": True
                    }
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
        """
        Select the container checkbox in Phase 2.
        
        Returns:
            Dict with success status
        """
        try:
            print("☑️ Selecting container checkbox...")
            checkboxes = self.driver.find_elements(By.XPATH,
                "//input[@type='checkbox' and contains(@class,'mat-checkbox-input')]")
            if not checkboxes:
                return {"success": False, "error": "Container checkbox not found"}
            
            checkbox = checkboxes[0]
            is_checked = checkbox.is_selected()
            
            if not is_checked:
                # Click the parent label for better reliability
                parent = checkbox.find_element(By.XPATH, "..")
                parent.click()
                time.sleep(0.5)
                print("  ✅ Checkbox selected")
            else:
                print("  ✅ Checkbox already selected")
            
            self._capture_screenshot("checkbox_selected")
            return {"success": True}
            
        except Exception as e:
            print(f"  ❌ Error selecting checkbox: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_pin_code(self, pin_code: str) -> Dict[str, Any]:
        """
        Fill the PIN code field in Phase 2 (optional).
        
        Args:
            pin_code: PIN code to enter
        
        Returns:
            Dict with success status
        """
        if not pin_code:
            print("  ℹ️  No PIN code provided, skipping...")
            return {"success": True, "skipped": True}
        
        try:
            print(f"🔢 Filling PIN code...")
            pin_input = self.driver.find_element(By.XPATH,
                "//input[@formcontrolname='Pin']")
            pin_input.clear()
            pin_input.send_keys(pin_code)
            time.sleep(0.5)
            print(f"  ✅ PIN code entered")
            self._capture_screenshot("pin_entered")
            return {"success": True}
            
        except NoSuchElementException:
            print("  ⚠️ PIN field not found (may not be required)")
            return {"success": True, "not_found": True}
        except Exception as e:
            print(f"  ❌ Error filling PIN: {e}")
            return {"success": False, "error": str(e)}
    
    def fill_truck_plate(self, truck_plate: str, allow_any_if_missing: bool = True) -> Dict[str, Any]:
        """
        Fill the truck plate field with autocomplete.
        
        Args:
            truck_plate: Truck plate number
            allow_any_if_missing: If true, select first option if exact match not found
        
        Returns:
            Dict with success status
        """
        try:
            print(f"🚛 Filling truck plate: {truck_plate}...")
            
            # Find truck plate input
            plate_input = self.driver.find_element(By.XPATH,
                "//input[@formcontrolname='Plate']")
            plate_input.clear()
            plate_input.send_keys(truck_plate)
            time.sleep(2)  # Wait for autocomplete
            
            # Try to find exact match in autocomplete
            exact_options = self.driver.find_elements(By.XPATH,
                f"//mat-option//span[normalize-space(text())='{truck_plate}']")
            
            if exact_options:
                exact_options[0].click()
                print(f"  ✅ Selected exact match: {truck_plate}")
            elif allow_any_if_missing:
                # Select first available option
                any_options = self.driver.find_elements(By.XPATH,
                    "//mat-option")
                if any_options:
                    any_options[0].click()
                    print(f"  ✅ Selected first available option")
                else:
                    print(f"  ⚠️ No options available, value entered as-is")
            else:
                print(f"  ⚠️ Exact match not found, value entered as-is")
            
            # Click blank area to confirm
            try:
                self.driver.find_element(By.TAG_NAME, "body").click()
                time.sleep(0.5)
            except:
                pass
            
            self._capture_screenshot("truck_plate_entered")
            return {"success": True, "truck_plate": truck_plate}
            
        except Exception as e:
            print(f"  ❌ Error filling truck plate: {e}")
            return {"success": False, "error": str(e)}
    
    def toggle_own_chassis(self, own_chassis: bool) -> Dict[str, Any]:
        """
        Toggle the Own Chassis button intelligently.
        
        Args:
            own_chassis: Desired state (True = YES, False = NO)
        
        Returns:
            Dict with success status
        """
        try:
            target = "YES" if own_chassis else "NO"
            print(f"🚚 Setting 'Own Chassis' to: {target}...")
            
            # Find the toggle buttons
            buttons = self.driver.find_elements(By.XPATH,
                "//mat-button-toggle//span[text()='YES' or text()='NO']/..")
            
            if len(buttons) < 2:
                return {"success": False, "error": "Own chassis toggle not found"}
            
            # Determine current state
            current_state = None
            for btn in buttons:
                try:
                    # Check parent for selected state
                    parent = btn.find_element(By.XPATH, "..")
                    is_checked = ("mat-button-toggle-checked" in parent.get_attribute("class") or
                                 parent.get_attribute("aria-pressed") == "true")
                    
                    btn_text = btn.text.strip()
                    if is_checked and btn_text in ["YES", "NO"]:
                        current_state = btn_text
                        break
                except:
                    pass
            
            if current_state:
                print(f"  📊 Current state: {current_state}")
            else:
                print(f"  ⚠️ Could not detect state, assuming default: NO")
                current_state = "NO"
            
            # Check if we need to click
            if current_state == target:
                print(f"  ✅ Already set to {target} - no action needed")
                self._capture_screenshot(f"own_chassis_already_set")
                return {"success": True, "already_set": True}
            
            # Find and click the target button
            for btn in buttons:
                if btn.text.strip() == target:
                    btn.click()
                    time.sleep(0.5)
                    print(f"  ✅ Toggled to {target}")
                    self._capture_screenshot(f"own_chassis_toggled")
                    return {"success": True, "toggled": True}
            
            return {"success": False, "error": f"Could not find {target} option"}
            
        except Exception as e:
            print(f"  ❌ Error toggling own chassis: {e}")
            return {"success": False, "error": str(e)}
    
    def get_available_appointment_times(self) -> Dict[str, Any]:
        """
        Get all available appointment time slots from Phase 3 dropdown.
        ⚠️ This method DOES NOT click Submit - only retrieves available times.
        Safe for /check_appointments endpoint.
        
        Returns:
            Dict with success status and available_times list
        """
        try:
            print("📅 Getting available appointment times...")
            print("  ℹ️  NOTE: Will NOT click Submit button - only retrieving times")
            
            # Take screenshot before attempting to find dropdown
            self._capture_screenshot("phase_3_before_dropdown")
            
            # Try multiple strategies to find the appointment dropdown
            print("  🔍 Looking for appointment dropdown...")
            
            # Strategy 1: By formcontrolname='slot'
            dropdowns = self.driver.find_elements(By.XPATH,
                "//mat-select[@formcontrolname='slot']")
            print(f"  📊 Strategy 1 (formcontrolname='slot'): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                # Strategy 2: By mat-label text
                dropdowns = self.driver.find_elements(By.XPATH,
                    "//mat-label[contains(text(),'Appointment') or contains(text(),'Time')]/ancestor::mat-form-field//mat-select")
                print(f"  📊 Strategy 2 (mat-label): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                # Strategy 3: Any mat-select in Phase 3
                dropdowns = self.driver.find_elements(By.XPATH, "//mat-select")
                print(f"  📊 Strategy 3 (any mat-select): Found {len(dropdowns)} dropdowns")
            
            if not dropdowns:
                self._capture_screenshot("appointment_dropdown_not_found")
                return {
                    "success": False,
                    "error": "Appointment time dropdown not found after trying all strategies"
                }
            
            dropdown = dropdowns[0]
            print(f"  ✅ Found dropdown, using first one")
            
            # Scroll into view and click
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                dropdown
            )
            time.sleep(1)
            
            # Try clicking
            try:
                dropdown.click()
                print("  ✅ Clicked dropdown (regular click)")
            except Exception:
                print(f"  ⚠️ Regular click failed, using JavaScript click...")
                self.driver.execute_script("arguments[0].click();", dropdown)
                print("  ✅ Clicked dropdown (JavaScript click)")
            
            time.sleep(2)
            print("  ✅ Opened appointment dropdown")
            self._capture_screenshot("appointment_dropdown_opened")
            
            # Get options
            options = self.driver.find_elements(By.XPATH,
                "//mat-option//span[@class='mat-option-text' or contains(@class,'mat-select-min-line')]")
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
            return {
                "success": True,
                "available_times": available_times,
                "count": len(available_times)
            }
            
        except Exception as e:
            print(f"  ❌ Error getting appointment times: {e}")
            import traceback
            traceback.print_exc()
            self._capture_screenshot("appointment_error")
            return {"success": False, "error": str(e)}

