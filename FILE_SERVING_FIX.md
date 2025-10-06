# File Serving Fix for Session Directories

## ✅ Problem Fixed

**Issue**: Excel files from `/get_appointments` were returning "File not found" error because they were saved in session subdirectories (`downloads/session_id/`) but the file serving endpoint only looked in the main downloads directory.

**Root Cause**: The `/files/<filename>` endpoint only checked the main `DOWNLOADS_DIR` but appointments files are now saved in `DOWNLOADS_DIR/session_id/`.

## 🔧 Solution Implemented

**File**: `emodal_business_api.py` (Lines 6355-6387)

### Before (Problematic Code)
```python
@app.route('/files/<path:filename>', methods=['GET'])
def serve_download(filename):
    """Serve downloaded Excel files from the downloads directory"""
    safe_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.exists(safe_path):
        return jsonify({"success": False, "error": "File not found"}), 404
    return send_file(safe_path, as_attachment=True)
```

### After (Fixed Code)
```python
@app.route('/files/<path:filename>', methods=['GET'])
def serve_download(filename):
    """Serve downloaded Excel files from the downloads directory"""
    # First try the main downloads directory
    safe_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.abspath(safe_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
        return jsonify({"success": False, "error": "Invalid path"}), 400
    
    if os.path.exists(safe_path):
        return send_file(safe_path, as_attachment=True)
    
    # If not found in main directory, search in session subdirectories
    # Look for files that match the pattern: session_id_timestamp_appointments.xlsx
    if filename.endswith('_appointments.xlsx') and '_' in filename:
        # Extract session_id from filename (everything before the last two underscores)
        parts = filename.split('_')
        if len(parts) >= 3:
            session_id = '_'.join(parts[:-2])  # Everything except last two parts
            session_dir = os.path.join(DOWNLOADS_DIR, session_id)
            
            if os.path.exists(session_dir):
                session_file_path = os.path.join(session_dir, filename)
                if os.path.exists(session_file_path):
                    return send_file(session_file_path, as_attachment=True)
    
    # If still not found, search all subdirectories for the file
    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        if filename in files:
            file_path = os.path.join(root, filename)
            if os.path.abspath(file_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
                return send_file(file_path, as_attachment=True)
    
    return jsonify({"success": False, "error": "File not found"}), 404
```

## 🎯 How It Works

### 1. Main Directory Check
- First tries to find the file in the main downloads directory
- This handles files from other endpoints (like containers)

### 2. Session Directory Check
- For appointments files (`*_appointments.xlsx`), extracts session ID from filename
- Looks in `downloads/{session_id}/` directory
- Example: `session_123_20251006_143022_appointments.xlsx` → looks in `downloads/session_123/`

### 3. Recursive Search
- If still not found, searches all subdirectories
- This is a fallback for any edge cases

## 📊 File Location Examples

### Containers Files (Main Directory)
```
downloads/
├── containers_scraped_20251006_143022.xlsx  ← Main directory
└── session_123/
    └── session_123_20251006_143022_appointments.xlsx  ← Session directory
```

### Appointments Files (Session Directory)
```
downloads/
├── session_123456789/
│   └── session_123456789_20251006_143022_appointments.xlsx
├── session_987654321/
│   └── session_987654321_20251006_143155_appointments.xlsx
└── other_files...
```

## 🔍 Filename Pattern Matching

### Appointments Files
```
Pattern: {session_id}_{timestamp}_appointments.xlsx
Example: session_123456789_20251006_143022_appointments.xlsx

Extraction:
- parts = ["session", "123456789", "20251006", "143022", "appointments.xlsx"]
- session_id = "_".join(parts[:-2]) = "session_123456789"
- Look in: downloads/session_123456789/
```

### Other Files
```
Pattern: {filename}.xlsx
Example: containers_scraped_20251006_143022.xlsx

Look in: downloads/ (main directory)
```

## 🧪 Testing

### Test File Serving
```bash
# Test appointments file (should work now)
curl -I http://localhost:5010/files/session_123456789_20251006_143022_appointments.xlsx

# Test containers file (should still work)
curl -I http://localhost:5010/files/containers_scraped_20251006_143022.xlsx
```

### Expected Responses
```bash
# Appointments file (from session directory)
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=session_123456789_20251006_143022_appointments.xlsx

# Containers file (from main directory)
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=containers_scraped_20251006_143022.xlsx
```

## ✅ Benefits

1. **Backward Compatible**: Still serves files from main directory
2. **Session Support**: Now serves files from session subdirectories
3. **Smart Detection**: Automatically detects appointments files
4. **Fallback Search**: Recursive search as last resort
5. **Security**: Path validation prevents directory traversal

## 🔄 File Serving Flow

```
1. Request: /files/session_123_20251006_143022_appointments.xlsx
2. Check main directory: downloads/session_123_20251006_143022_appointments.xlsx
3. Not found, check if appointments file
4. Extract session_id: "session_123"
5. Check session directory: downloads/session_123/session_123_20251006_143022_appointments.xlsx
6. Found! Serve file
```

## 🚨 Important Notes

- **Security**: All paths are validated to prevent directory traversal
- **Performance**: Main directory check first (fastest)
- **Fallback**: Recursive search only if needed
- **Compatibility**: Works with both old and new file structures

---

**Status**: ✅ **FIXED**  
**Date**: 2025-10-06  
**Issue**: File not found for appointments Excel files  
**Solution**: Enhanced file serving to check session subdirectories

