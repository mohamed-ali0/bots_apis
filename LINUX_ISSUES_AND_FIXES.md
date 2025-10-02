# Linux Issues and Comprehensive Fixes

## Current Status: CRITICAL ISSUES ON LINUX

### Issue 1: ❌ Checkbox Selection Fails
**Symptom**:
```
✅ Clicked via TH parent
⚠️ First click didn't select, trying double-click...
✅ Double-clicked TH parent
📋 Select-all checkbox new state: unchecked  ← Still unchecked!
✅ 0 checkboxes now selected
```

**Root Cause**: Angular Material checkbox requires **actual user interaction** or specific event sequence that JS click doesn't trigger properly in Xvfb/Linux.

**Fix Applied**: Added **third-level fallback** - manually click all individual row checkboxes:

```python
# After double-click fails
if not select_all_checkbox.is_selected():
    print("⚠️ Double-click also failed, trying to select individual rows...")
    row_checkboxes = driver.find_elements(By.XPATH, "//tbody//tr//input[@type='checkbox']")
    for i, row_cb in enumerate(row_checkboxes[:40]):
        if not row_cb.is_selected():
            driver.execute_script("arguments[0].click();", row_cb)
            selected += 1
    print(f"✅ Manually selected {selected} row checkboxes")
```

### Issue 2: ❌ Excel Download Doesn't Start
**Symptom**:
```
📁 Download directory: /home/.../downloads/session_123
✅ Chrome download behavior configured
📥 Clicking Excel download button: ''
⏳ Waiting for file download...
  📊 Check #60: 0 files, 0 in progress, 0 complete  ← No files!
```

**Root Cause**: Excel download button is **disabled** until containers are selected. Since checkbox selection fails, button click does nothing.

**Expected Flow**:
1. ✅ Select all checkboxes
2. ✅ Excel button becomes enabled
3. ✅ Click button → Download starts
4. ✅ File appears in directory

**Actual Flow**:
1. ❌ Checkbox selection fails
2. ❌ Excel button stays disabled
3. ❌ Click does nothing
4. ❌ No file

**Fix**: The row-level checkbox selection fallback should enable the Excel button.

### Issue 3: ❌ No Screenshots Captured
**Symptom**:
```
User: "there is no screenshots"
```

**Root Cause**: `capture_screens` was `True` but screenshots weren't being saved.

**Possible causes**:
1. `screens_enabled` not being set properly
2. Screenshot directory not writable
3. PIL/Pillow failing silently
4. Screenshots saved but not included in bundle

**Fix Applied**: Added debug logging:
```python
print(f"📸 Screenshots enabled: {operations.screens_enabled}")
print(f"📁 Screenshots directory: {operations.screens_dir}")
# In _capture_screenshot:
print(f"📸 Screenshot saved: {filename}")
```

## Complete Diagnostic Output (Expected)

```
INFO: Creating browser session
🖥️  Starting Xvfb virtual display for Linux non-GUI server...
✅ Xvfb started on display: :0
🚀 Initializing Chrome WebDriver...
📸 Screenshots enabled: True
📁 Screenshots directory: /home/.../screenshots/session_123
🕒 Ensuring app context is fully loaded after login...
📸 Screenshot saved: 20251002_150000_123456_app_ready.png
🚢 Navigating to containers page...
📸 Screenshot saved: 20251002_150005_234567_before_select_all.png
☑️ Looking for 'Select All' checkbox...
📊 Found 40 container rows on page
✅ Found select-all via: //thead//input[@type='checkbox']
📋 Select-all checkbox current state: unchecked
✅ Clicked via TH parent
⚠️ First click didn't select, trying double-click...
✅ Double-clicked TH parent
⚠️ Double-click also failed, trying to select individual rows...
   Found 40 row checkboxes
✅ Manually selected 40 row checkboxes
📋 Select-all checkbox new state: checked
✅ 40 checkboxes now selected
📸 Screenshot saved: 20251002_150015_345678_after_select_all.png
📥 Looking for Excel download button...
✅ Found Excel download button
📁 Download directory: /home/.../downloads/session_123
✅ Chrome download behavior configured
📸 Screenshot saved: 20251002_150020_456789_before_export.png
📥 Clicking Excel download button: ''
📸 Screenshot saved: 20251002_150025_567890_after_export_click.png
⏳ Waiting for file download...
  📊 Check #5: 1 files, 1 in progress, 0 complete
     Files: ['container_watch_list.xlsx.crdownload']
  📊 Check #10: 1 files, 0 in progress, 1 complete
     Files: ['container_watch_list.xlsx']
✅ File downloaded: container_watch_list.xlsx (24206 bytes)
📸 Screenshot saved: 20251002_150030_678901_after_download.png

======================================================================
📦 BUNDLE READY FOR DOWNLOAD
======================================================================
🌐 Public URL: http://89.117.63.196:5010/files/session_123_20251002_150030.zip
📂 File: session_123_20251002_150030.zip
📊 Size: 2458679 bytes
======================================================================
```

## Verification Steps After Next Run

### 1. Check Screenshots Directory
```bash
cd /home/bots_test/bots_apis/screenshots/
ls -la session_*/
# Should show multiple .png files
```

### 2. Check Downloads Directory
```bash
cd /home/bots_test/bots_apis/downloads/
ls -la session_*/
# Should show .xlsx file
```

### 3. Check Bundle Contents
```bash
cd /home/bots_test/bots_apis/downloads/
unzip -l session_*.zip
# Should show:
#   session_123/downloads/container_watch_list.xlsx
#   session_123/screenshots/*.png
```

### 4. Verify Checkboxes Selected
Look for this in output:
```
✅ Manually selected 40 row checkboxes
✅ 40 checkboxes now selected  ← Changed from 0!
```

## Alternative Approaches (If Still Failing)

### Option 1: Use ActionChains for Mouse Movement
```python
from selenium.webdriver.common.action_chains import ActionChains

# Move mouse to checkbox and click
actions = ActionChains(driver)
actions.move_to_element(th_parent)
actions.click()
actions.perform()
```

### Option 2: Use Browser DevTools to Trigger Events
```python
# Trigger all Angular events
driver.execute_script("""
    var checkbox = arguments[0];
    var events = ['mousedown', 'mouseup', 'click', 'change', 'input'];
    events.forEach(function(eventName) {
        var event = new Event(eventName, {bubbles: true});
        checkbox.dispatchEvent(event);
    });
""", select_all_checkbox)
```

### Option 3: Use Angular's ng.probe() API
```python
# Access Angular component directly
driver.execute_script("""
    var checkbox = arguments[0];
    var element = angular.element(checkbox);
    var scope = element.scope();
    scope.$apply(function() {
        scope.selectAll = true;  // Or whatever the model property is
    });
""", select_all_checkbox)
```

### Option 4: Skip Select-All, Download Without Selection
```python
# Try clicking Excel button without selection
# Some apps allow exporting visible data
driver.execute_script("arguments[0].click();", excel_button)
```

### Option 5: Use Keyboard Tab + Space
```python
# Tab to checkbox, press Space to toggle
from selenium.webdriver.common.keys import Keys

body = driver.find_element(By.TAG_NAME, 'body')
body.send_keys(Keys.TAB * 5)  # Tab to checkbox
time.sleep(0.5)
body.send_keys(Keys.SPACE)  # Press Space to check
```

## Debug Commands to Run on Server

### Check Chrome/ChromeDriver versions
```bash
google-chrome --version
chromedriver --version
```

### Check Xvfb is running
```bash
ps aux | grep Xvfb
echo $DISPLAY
```

### Check directory permissions
```bash
ls -la downloads/
ls -la screenshots/
chmod -R 755 downloads/ screenshots/
```

### Test screenshot manually
```python
from PIL import Image
import os

# In Python console after screenshot attempt
screens_dir = "/home/bots_test/bots_apis/screenshots/session_123"
files = os.listdir(screens_dir)
print(f"Screenshots: {files}")

# Try to open one
if files:
    img = Image.open(os.path.join(screens_dir, files[0]))
    print(f"Image size: {img.size}")
```

### Check if Excel button is actually disabled
```python
# Add this debug line before clicking
is_enabled = excel_button.is_enabled()
is_displayed = excel_button.is_displayed()
classes = excel_button.get_attribute('class')
disabled_attr = excel_button.get_attribute('disabled')

print(f"Button enabled: {is_enabled}")
print(f"Button displayed: {is_displayed}")
print(f"Button classes: {classes}")
print(f"Disabled attribute: {disabled_attr}")
```

## Expected Next Test Results

✅ **What should work now**:
1. Individual row checkboxes get selected (even if master checkbox fails)
2. Excel button becomes enabled
3. Download starts
4. Screenshots are captured and logged
5. Bundle includes both downloads and screenshots
6. Public URL is printed

❌ **What might still fail**:
1. Master "select all" checkbox might still not work
2. But individual row selection should succeed

## Summary

The key fix is the **three-level fallback strategy**:

1. **Level 1**: Click TH parent (most elegant)
2. **Level 2**: Double-click TH parent (retry)
3. **Level 3**: Click all 40 individual row checkboxes (guaranteed to work)

**Level 3 should succeed even if Levels 1 & 2 fail**, enabling the Excel download button.

Next test should show:
- ✅ Screenshots being captured (with filenames logged)
- ✅ Individual row checkboxes being selected
- ✅ Excel file downloading
- ✅ Bundle with screenshots
- ✅ Public download URL

