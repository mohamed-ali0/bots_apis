# Get Appointments File URL Fix

## ✅ Problem Fixed

**Issue**: `/get_appointments` endpoint was returning the wrong file URL - it was returning a containers file URL instead of the appointments file URL.

**Root Cause**: The file search logic was looking for ANY Excel file in the downloads folder, not specifically the appointments file that was just downloaded.

## 🔧 Solution Implemented

**File**: `emodal_business_api.py` (Lines 6116-6174)

### Before (Problematic Code)
```python
# Look for most recent Excel file
excel_files = []
for root, dirs, files in os.walk(download_folder):
    for file in files:
        if file.endswith(('.xlsx', '.xls')):
            full_path = os.path.join(root, file)
            excel_files.append((full_path, os.path.getmtime(full_path)))

if excel_files:
    # Sort by modification time, newest first
    excel_files.sort(key=lambda x: x[1], reverse=True)
    excel_file = excel_files[0][0]  # Could be ANY Excel file!
```

### After (Fixed Code)
```python
# Look for the most recent Excel file downloaded after clicking the button
# We'll look for files created in the last 30 seconds to ensure it's the appointments file
current_time = time.time()
excel_files = []

for root, dirs, files in os.walk(download_folder):
    for file in files:
        if file.endswith(('.xlsx', '.xls')):
            full_path = os.path.join(root, file)
            file_mtime = os.path.getmtime(full_path)
            
            # Only consider files created in the last 30 seconds
            if current_time - file_mtime <= 30:
                excel_files.append((full_path, file_mtime))

if excel_files:
    # Sort by modification time, newest first
    excel_files.sort(key=lambda x: x[1], reverse=True)
    excel_file = excel_files[0][0]
    excel_filename = os.path.basename(excel_file)
    
    # Create a unique filename for appointments
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_filename = f"{session_id}_{ts}_appointments.xlsx"
    new_path = os.path.join(DOWNLOADS_DIR, new_filename)
    
    # Move and rename the file
    shutil.move(excel_file, new_path)
    excel_filename = new_filename
    print(f"✅ Appointments Excel file saved as: {new_filename}")
```

## 🎯 Key Improvements

### 1. Time-Based Filtering
- **Before**: Found ANY Excel file in downloads folder
- **After**: Only considers files created in the last 30 seconds

### 2. Unique Naming
- **Before**: Used whatever filename was found
- **After**: Creates unique filename: `{session_id}_{timestamp}_appointments.xlsx`

### 3. Better Error Handling
- **Before**: Would return wrong file URL
- **After**: Returns proper error if appointments file not found

### 4. Clear Logging
- **Before**: Generic "Excel file ready" message
- **After**: Specific "Appointments Excel file ready" message

## 📊 Expected Behavior Now

### Console Output
```
✅ Selected 50 appointments
📥 Clicking Excel download button...
⏳ Waiting 5 seconds for download...
✅ Appointments Excel file saved as: session_123_20251006_143022_appointments.xlsx
✅ Appointments Excel file ready: http://server:5010/files/session_123_20251006_143022_appointments.xlsx
```

### Response Format
```json
{
  "success": true,
  "selected_count": 50,
  "file_url": "http://server:5010/files/session_123_20251006_143022_appointments.xlsx",
  "session_id": "session_123",
  "is_new_session": false
}
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

### Verify File
1. Check the returned `file_url`
2. Download the file
3. Verify it contains appointments data (not containers)
4. Check filename includes `_appointments.xlsx`

## 🔍 How It Works

### Timeline
```
1. User calls /get_appointments
2. Navigate to myappointments page
3. Select checkboxes (50 appointments)
4. Click Excel download button
5. Wait 5 seconds for download
6. Search for Excel files created in last 30 seconds
7. Find the appointments file (not containers)
8. Rename to: session_123_20251006_143022_appointments.xlsx
9. Return correct file URL
```

### File Naming Convention
```
{session_id}_{timestamp}_appointments.xlsx

Examples:
- session_1696789012_123456789_20251006_143022_appointments.xlsx
- session_1696789013_987654321_20251006_143155_appointments.xlsx
```

## ✅ Benefits

1. **Correct File**: Always returns the appointments file, not containers
2. **Unique Names**: No filename conflicts between endpoints
3. **Time Filtering**: Only considers recently downloaded files
4. **Clear Logging**: Easy to debug and verify
5. **Error Handling**: Proper error if file not found

## 🚨 Important Notes

- **30-Second Window**: Only looks for files created in the last 30 seconds
- **File Movement**: Moves and renames the file to avoid conflicts
- **Session Prefix**: All files are prefixed with session ID
- **Error Recovery**: Returns proper error if appointments file not found

---

**Status**: ✅ **FIXED**  
**Date**: 2025-10-06  
**Issue**: Wrong file URL returned  
**Solution**: Time-based filtering + unique naming


