# Linux Download Fix

## Problem
The Excel file download was failing on Linux servers despite working perfectly on Windows. The issues were:

1. **Chrome download path**: CDP `setDownloadBehavior` requires **absolute path** on Linux (not relative)
2. **Chrome preferences**: Missing download configuration in Chrome options
3. **Checkbox click intercepted**: Angular Material checkbox in `<th>` element intercepted direct input clicks
4. **Limited debugging**: No visibility into download progress

## Root Causes

### Issue 1: Relative Download Path
**Windows**: Accepts relative paths like `downloads/session_123`
**Linux**: Requires absolute paths like `/home/user/project/downloads/session_123`

### Issue 2: Missing Chrome Download Prefs
Linux Chrome needs explicit download preferences:
- `download.prompt_for_download: False`
- `download.directory_upgrade: True`
- `safebrowsing.enabled: False`

### Issue 3: Element Click Intercepted
The `<input type="checkbox">` inside `<th>` element:
- On Windows: Direct click works
- On Linux: Click is intercepted by parent `<th>` element
- Solution: Click the `<th>` parent instead of the input

## Fixes Applied

### 1. Chrome Download Configuration (`emodal_login_handler.py`)

Added download preferences to Chrome options:

```python
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
```

### 2. Absolute Path for CDP Command (`emodal_business_api.py`)

Changed from relative to absolute path:

```python
# BEFORE (Failed on Linux)
download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": download_dir  # ❌ Relative path
})

# AFTER (Works on Linux)
download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
download_dir_abs = os.path.abspath(download_dir)  # ✅ Absolute path
self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": download_dir_abs
})
```

### 3. Improved Checkbox Click (`emodal_business_api.py`)

Changed click strategy with priority order:

```python
# Method 1: Click TH parent (most reliable for Angular Material)
try:
    th_parent = select_all_checkbox.find_element(By.XPATH, "ancestor::th[1]")
    self.driver.execute_script("arguments[0].click();", th_parent)
    clicked = True
except Exception:
    pass

# Method 2: Click label[for]
if not clicked:
    try:
        label = self.driver.find_element(By.XPATH, f"//label[@for='{cb_id}']")
        self.driver.execute_script("arguments[0].click();", label)
        clicked = True
    except Exception:
        pass

# Method 3: Click mat-checkbox inner container
# Method 4: JS click on input (last resort)
```

### 4. Enhanced Debugging

Added detailed download monitoring:

```python
# Debug output every 10 seconds
if check_count % 10 == 0 or complete_files or in_progress:
    print(f"  📊 Check #{check_count}: {len(entries)} files, "
          f"{len(in_progress)} in progress, {len(complete_files)} complete")
    if entries:
        print(f"     Files: {entries}")
```

## Expected Output (Linux)

### Before Fix
```
📁 Download directory: downloads/session_123  # ❌ Relative
✅ Chrome download behavior configured
⏳ Waiting for file download...
[60 seconds timeout]
❌ Download timeout - file not found
```

### After Fix
```
📁 Download directory: /home/user/bots_apis/downloads/session_123  # ✅ Absolute
✅ Chrome download behavior configured
📥 Clicking Excel download button: ''
⏳ Waiting for file download...
  📊 Check #1: 1 files, 1 in progress, 0 complete
     Files: ['container_watch_list.xlsx.crdownload']
  📊 Check #5: 1 files, 0 in progress, 1 complete
     Files: ['container_watch_list.xlsx']
✅ File downloaded: container_watch_list.xlsx (24206 bytes)
```

## Testing

### Test on Linux
```bash
# Start API server
python emodal_business_api.py

# In another terminal, run test
export API_HOST="localhost"
export EMODAL_USERNAME="jfernandez"
export EMODAL_PASSWORD="taffie"
export CAPTCHA_API_KEY="your_key"
export INFINITE_SCROLLING="false"
python test_business_api.py
```

### Verify Download Directory
```bash
cd downloads/
ls -la session_*/
# Should show .xlsx file
```

## Key Differences: Windows vs Linux

| Aspect | Windows | Linux |
|--------|---------|-------|
| **Download Path** | Relative OK | Absolute required |
| **Chrome Prefs** | Optional | Required |
| **Checkbox Click** | Direct input works | Parent element needed |
| **Xvfb** | Not needed | Required for non-GUI |
| **File Paths** | Backslashes | Forward slashes |

## Troubleshooting

### Issue: Download still times out

**Check 1**: Verify absolute path is being used
```python
print(f"Download dir: {os.path.abspath(download_dir)}")
# Should show: /home/user/... (absolute)
# Not: downloads/... (relative)
```

**Check 2**: Verify directory permissions
```bash
ls -la downloads/session_*/
chmod 755 downloads/
```

**Check 3**: Check Chrome download settings
```python
# Add this debug line after CDP command:
result = self.driver.execute_cdp_cmd("Page.getDownloadState", {})
print(f"Download state: {result}")
```

### Issue: Checkbox doesn't get selected

**Solution**: The TH parent click should work, but verify:
```python
# After click, check both input state and aria-checked
is_selected = checkbox.is_selected()
mat = checkbox.find_element(By.XPATH, "ancestor::mat-checkbox")
aria_checked = mat.get_attribute('aria-checked')
print(f"Input selected: {is_selected}, aria-checked: {aria_checked}")
```

### Issue: Permission denied on download directory

**Fix permissions**:
```bash
sudo chown -R $USER:$USER /path/to/project/downloads
chmod -R 755 /path/to/project/downloads
```

## Platform-Specific Code

### Auto-detect and handle platform differences:

```python
import os
import platform

# Use absolute path on all platforms (works everywhere)
download_dir = os.path.join(DOWNLOADS_DIR, session_id)
download_dir_abs = os.path.abspath(download_dir)

# Platform-specific Chrome options
if platform.system() == 'Linux':
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # Add download prefs
    prefs = {"download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
```

## Summary

The fixes ensure **identical behavior on Windows and Linux** by:
1. ✅ Using absolute paths for CDP commands
2. ✅ Adding Linux-specific Chrome preferences
3. ✅ Using robust click strategies for Angular Material
4. ✅ Adding comprehensive debugging

**Result**: Excel downloads now work reliably on both platforms! 🎉

