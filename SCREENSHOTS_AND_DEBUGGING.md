# Screenshots and Debugging Enhancements

## Changes Made

### 1. ✅ Screenshots Enabled by Default
**Changed**: `capture_screens` now defaults to `True` instead of `False`

```python
# Before
capture_screens = data.get('capture_screens', False)

# After  
capture_screens = data.get('capture_screens', True)  # Default: enabled for debugging
```

**Impact**: All API requests will now automatically capture screenshots at each step unless explicitly disabled with `"capture_screens": false`.

### 2. ✅ Public Download URL Printed in Terminal

After creating the bundle ZIP file, the system now prints a prominent download link:

```
======================================================================
📦 BUNDLE READY FOR DOWNLOAD
======================================================================
🌐 Public URL: http://89.117.63.196:5010/files/session_123_20251002_143045.zip
📂 File: session_123_20251002_143045.zip
📊 Size: 1234567 bytes
======================================================================
```

**Benefits**:
- ✅ Immediate visibility of download link
- ✅ Easy copy-paste from terminal
- ✅ Shows file size for verification
- ✅ Works on both Windows and Linux

### 3. ✅ Improved Checkbox Selection for Linux

Added robust click sequence with retry logic:

```python
# Method 1: Click TH parent (most reliable)
th_parent = checkbox.find_element(By.XPATH, "ancestor::th[1]")
driver.execute_script("arguments[0].click();", th_parent)
time.sleep(1)

# Wait and check if selection worked
time.sleep(3)

# If first click didn't work, double-click
if not checkbox.is_selected():
    print("⚠️ First click didn't select, trying double-click...")
    driver.execute_script("arguments[0].click();", th_parent)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", th_parent)
    time.sleep(2)
```

**Why this works**:
- On Linux with Xvfb, single clicks sometimes don't register
- Clicking the `<th>` parent is more reliable than the `<input>`
- Double-click ensures selection happens

### 4. ✅ Enhanced Download Debugging

Added progress reporting every 10 seconds:

```
⏳ Waiting for file download...
  📊 Check #10: 0 files, 0 in progress, 0 complete
  📊 Check #20: 1 files, 1 in progress, 0 complete
     Files: ['container_watch_list.xlsx.crdownload']
  📊 Check #25: 1 files, 0 in progress, 1 complete
     Files: ['container_watch_list.xlsx']
✅ File downloaded: container_watch_list.xlsx (24206 bytes)
```

## Screenshot Locations

### Inside ZIP Bundle

```
session_123_20251002_143045.zip
├── session_123/
│   ├── downloads/
│   │   └── container_watch_list.xlsx
│   └── screenshots/
│       ├── 20251002_143001_123456_app_ready.png
│       ├── 20251002_143005_234567_before_select_all.png
│       ├── 20251002_143010_345678_after_select_all.png
│       ├── 20251002_143015_456789_before_export.png
│       ├── 20251002_143020_567890_after_export_click.png
│       └── 20251002_143025_678901_after_download.png
```

### Screenshot Naming Convention

Format: `YYYYMMDD_HHMMSS_microseconds_tag.png`

Example: `20251002_143045_123456_before_select_all.png`

- **Date/Time**: When screenshot was taken
- **Microseconds**: Ensures unique filenames
- **Tag**: Describes what step/action

## Common Screenshot Tags

| Tag | Description | When Captured |
|-----|-------------|---------------|
| `app_ready` | App fully loaded | After login, before operations |
| `before_select_all` | Before clicking select-all checkbox | Before selection |
| `after_select_all` | After clicking select-all checkbox | After selection |
| `before_export` | Before clicking Excel button | Before export |
| `after_export_click` | After clicking Excel button | After export click |
| `after_download` | After file downloaded | After successful download |

## API Usage

### Enable Screenshots (Default)
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "your_key",
  "capture_screens": true  // Can omit - defaults to true
}
```

### Disable Screenshots (Faster)
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "your_key",
  "capture_screens": false  // Explicitly disable
}
```

### Response with Bundle URL
```json
{
  "success": true,
  "bundle_url": "/files/session_123_20251002_143045.zip",
  "total_containers": 40,
  "scroll_cycles": 0
}
```

## Downloading the Bundle

### Method 1: Direct Browser
```
http://89.117.63.196:5010/files/session_123_20251002_143045.zip
```

### Method 2: curl (Linux/Mac)
```bash
curl -O http://89.117.63.196:5010/files/session_123_20251002_143045.zip
```

### Method 3: wget (Linux)
```bash
wget http://89.117.63.196:5010/files/session_123_20251002_143045.zip
```

### Method 4: PowerShell (Windows)
```powershell
Invoke-WebRequest -Uri "http://89.117.63.196:5010/files/session_123_20251002_143045.zip" -OutFile "bundle.zip"
```

## Troubleshooting

### Issue: No screenshots in bundle

**Check 1**: Verify screenshots were captured
```bash
ls -la screenshots/session_*/
```

**Check 2**: Check operations.screens_enabled
```python
operations = EModalBusinessOperations(session)
operations.screens_enabled = bool(capture_screens)  # Should be True
```

### Issue: Bundle URL not printed

**Possible causes**:
1. Bundle creation failed (check for error messages)
2. Output is being buffered (flush stdout)
3. Terminal encoding issues (use UTF-8)

**Fix**:
```python
print(f"Public URL: {url}", flush=True)  # Force flush
```

### Issue: Checkbox still not selecting on Linux

**Debug steps**:
1. Check if checkbox is found: `print(checkbox.get_attribute('id'))`
2. Check if TH parent exists: `print(th_parent.tag_name)`
3. Try manual inspection: keep browser alive and check state
4. Verify aria-checked attribute changes

**Additional fallback**:
```python
# If double-click still doesn't work, try selecting individual rows
all_row_checkboxes = driver.find_elements(By.XPATH, "//tbody//input[@type='checkbox']")
for cb in all_row_checkboxes[:10]:  # Select first 10
    driver.execute_script("arguments[0].click();", cb)
```

## Performance Impact

| Setting | Speed | Screenshots | Use Case |
|---------|-------|-------------|----------|
| `capture_screens: true` | Normal (+5-10s) | ✅ Yes | **Debugging, troubleshooting** |
| `capture_screens: false` | Fast | ❌ No | Production, speed-critical |

**Recommendation**: Keep enabled for debugging until system is stable, then disable for production.

## Security Note

⚠️ **Screenshots may contain sensitive information**:
- Container numbers
- Usernames
- Company data
- Session IDs

**Best practices**:
1. ✅ Auto-delete bundles after 24 hours
2. ✅ Restrict `/files/` endpoint access
3. ✅ Use HTTPS in production
4. ✅ Don't share bundle URLs publicly

## File Cleanup

### Manual Cleanup
```bash
# Remove old screenshots
rm -rf screenshots/session_*

# Remove old downloads
rm -rf downloads/session_*

# Remove old bundles
rm -f downloads/*.zip
```

### Automatic Cleanup (TODO)
Add cron job to delete files older than 24 hours:

```bash
# Add to crontab
0 * * * * find /path/to/emodal/downloads/*.zip -mtime +1 -delete
0 * * * * find /path/to/emodal/screenshots/* -type d -mtime +1 -exec rm -rf {} \;
```

## Summary

✅ **Screenshots enabled by default** for better debugging
✅ **Public download URL printed** prominently in terminal  
✅ **Improved checkbox selection** with double-click retry
✅ **Enhanced download debugging** with progress reports
✅ **Complete bundle** includes both downloads and screenshots

**Next test should show**:
- Clear public download URL in terminal
- Screenshots in the bundle
- Better checkbox selection on Linux
- Download progress visibility


