# Appointments Download Folder Fix

## ✅ Problem Fixed

**Issue**: The `/get_appointments` endpoint was downloading files to the main downloads folder instead of the session-specific downloads folder.

**Root Cause**: The endpoint was not configuring Chrome's download behavior to use the session-specific directory before clicking the Excel download button.

## 🔧 Solution Implemented

**File**: `emodal_business_api.py` (Lines 6103-6174)

### Before (Problematic Code)
```python
# Click Excel download button
download_result = operations.click_excel_download_button()

# Wait for file to download
time.sleep(5)

# Find the downloaded file in the downloads folder
download_folder = operations.screens_dir.replace("screenshots", "downloads")
if not os.path.exists(download_folder):
    download_folder = DOWNLOADS_DIR
```

### After (Fixed Code)
```python
# Set up session-specific download directory
download_dir = os.path.join(DOWNLOADS_DIR, session_id)
try:
    os.makedirs(download_dir, exist_ok=True)
except Exception as mkdir_e:
    print(f"⚠️ Could not create download directory: {mkdir_e}")

# CRITICAL: Use absolute path for Linux compatibility
download_dir_abs = os.path.abspath(download_dir)
print(f"📁 Download directory: {download_dir_abs}")

# Configure active Chrome session to allow downloads into our dir via DevTools
try:
    operations.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir_abs
    })
    print("✅ Download behavior configured for session directory")
except Exception as cdp_e:
    print(f"⚠️ Could not configure download behavior: {cdp_e}")

# Click Excel download button
download_result = operations.click_excel_download_button()

# Wait for file to download
time.sleep(5)

# Find the downloaded file in the session-specific downloads folder
download_folder = download_dir
```

## 🎯 Key Improvements

### 1. Session-Specific Directory
- **Before**: Downloaded to main downloads folder
- **After**: Downloads to `downloads/{session_id}/` folder

### 2. Chrome Download Configuration
- **Before**: No download path configuration
- **After**: Uses Chrome DevTools Protocol to set download path

### 3. Proper File Handling
- **Before**: Searched in wrong directory
- **After**: Searches in correct session directory

### 4. Better Error Handling
- **Before**: Could not find files
- **After**: Graceful fallback if rename fails

## 📊 Expected Behavior Now

### Console Output
```
✅ Selected 50 appointments
📁 Download directory: /path/to/downloads/session_123456789
✅ Download behavior configured for session directory
📥 Clicking Excel download button...
⏳ Waiting 5 seconds for download...
✅ Appointments Excel file saved as: session_123456789_20251006_143022_appointments.xlsx
✅ Appointments Excel file ready: http://server:5010/files/session_123456789_20251006_143022_appointments.xlsx
```

### Directory Structure
```
downloads/
├── session_123456789/
│   ├── session_123456789_20251006_143022_appointments.xlsx
│   └── other_session_files...
├── session_987654321/
│   └── session_987654321_20251006_143155_appointments.xlsx
└── other_files...
```

### Response Format
```json
{
  "success": true,
  "selected_count": 50,
  "file_url": "http://server:5010/files/session_123456789_20251006_143022_appointments.xlsx",
  "session_id": "session_123456789",
  "is_new_session": false
}
```

## 🔍 How It Works

### Timeline
```
1. User calls /get_appointments
2. Navigate to myappointments page
3. Select checkboxes (50 appointments)
4. Create session-specific download directory: downloads/session_123/
5. Configure Chrome to download to that directory
6. Click Excel download button
7. File downloads to: downloads/session_123/appointments.xlsx
8. Rename to: session_123_20251006_143022_appointments.xlsx
9. Return correct file URL
```

### Chrome DevTools Protocol
```javascript
// This is what gets executed in Chrome
chrome.devtools.protocol.sendCommand("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": "/absolute/path/to/downloads/session_123"
});
```

## 🧪 Testing

### Test the Fix
```bash
# Test appointments endpoint
python test_get_appointments.py

# Or direct API call
curl -X POST http://localhost:5010/get_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your_session_id",
    "target_count": 10,
    "debug": false
  }'
```

### Verify Directory Structure
```bash
# Check that file is in session directory
ls -la downloads/session_123456789/
# Should see: session_123456789_20251006_143022_appointments.xlsx

# Check main downloads directory
ls -la downloads/
# Should see session directories, not individual files
```

## ✅ Benefits

1. **Organized Files**: Each session has its own download folder
2. **No Conflicts**: Files from different sessions don't interfere
3. **Easy Cleanup**: Can delete entire session folder when done
4. **Consistent**: Matches behavior of other endpoints
5. **Debug Friendly**: Easy to find files for specific sessions

## 🔄 Consistency with Other Endpoints

This fix makes `/get_appointments` consistent with other endpoints:

### `/get_containers` (Already Working)
```python
# Set up session-specific download directory
download_dir = os.path.join(DOWNLOADS_DIR, self.session.session_id)
os.makedirs(download_dir, exist_ok=True)

# Configure Chrome download behavior
self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": download_dir_abs
})
```

### `/get_appointments` (Now Fixed)
```python
# Set up session-specific download directory
download_dir = os.path.join(DOWNLOADS_DIR, session_id)
os.makedirs(download_dir, exist_ok=True)

# Configure Chrome download behavior
operations.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": download_dir_abs
})
```

## 🚨 Important Notes

- **Session Directory**: Files now download to `downloads/{session_id}/`
- **Chrome Configuration**: Uses DevTools Protocol to set download path
- **File Naming**: Still creates unique filenames with timestamp
- **Error Handling**: Graceful fallback if rename fails
- **Consistency**: Now matches other endpoints' behavior

---

**Status**: ✅ **FIXED**  
**Date**: 2025-10-06  
**Issue**: Files downloaded to wrong directory  
**Solution**: Session-specific download directory + Chrome configuration

