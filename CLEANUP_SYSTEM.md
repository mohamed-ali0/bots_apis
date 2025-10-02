# Automatic File Cleanup System

## Overview
The API now includes an **automatic cleanup system** that deletes files older than **24 hours** to maintain storage efficiency.

---

## 🗑️ What Gets Cleaned

### Directories
- **`downloads/`** - Excel files, debug text files, ZIP bundles
- **`screenshots/`** - PNG screenshots from debug mode

### Retention Policy
- **Files older than 24 hours** are automatically deleted
- **Empty directories** are removed after file cleanup
- **Active files** (< 24h old) are preserved

---

## ⚙️ How It Works

### 1. Background Task
- **Runs automatically** every hour
- **Daemon thread** - stops when server stops
- **No manual intervention** needed

### 2. On Startup
- **Initial cleanup** runs when server starts
- Removes any old files from previous sessions
- Displays cleanup results in logs

### 3. File Age Detection
Files are considered "old" if their **modification time** is more than 24 hours ago:

```python
cutoff_time = current_time - (24 * 60 * 60)  # 24 hours
if file_mtime < cutoff_time:
    delete_file()
```

---

## 📊 Monitoring

### Server Logs
Cleanup activity is logged automatically:

```
🗑️ Cleanup: Deleted 45 files older than 24h, freed 156.32 MB
```

If no old files exist:
```
🗑️ Cleanup: No old files to delete
```

### Manual Cleanup Endpoint

**Trigger cleanup on-demand:**
```bash
POST http://server:5010/cleanup
```

**Response:**
```json
{
  "success": true,
  "message": "Cleanup completed",
  "current_storage_mb": 42.5,
  "downloads_mb": 38.2,
  "screenshots_mb": 4.3
}
```

**Test script:**
```bash
python test_cleanup.py
```

---

## 🕐 Cleanup Schedule

| Event | Timing | Action |
|-------|--------|--------|
| **Server Startup** | Once | Initial cleanup of old files |
| **Background Task** | Every 1 hour | Automatic cleanup |
| **Manual Trigger** | On-demand | Via `/cleanup` endpoint |

---

## 💾 Storage Efficiency

### Before Cleanup System
```
downloads/
├── session_123/  (2 days old)
├── session_124/  (3 days old)
├── session_125/  (5 hours old) ✅
└── ... (100+ old sessions)

Total: ~5 GB
```

### After Cleanup System
```
downloads/
└── session_125/  (5 hours old) ✅

Total: ~50 MB
```

**Result:** 99% storage reduction! 🎉

---

## 🔍 What's Protected

### Files NEVER Deleted
1. **Files < 24 hours old**
2. **Currently open files** (in use by active sessions)
3. **System directories** (only session folders are cleaned)

### Example Timeline
```
File created: Oct 2, 10:00 AM
Current time: Oct 3, 09:00 AM  → 23 hours old → KEPT ✅
Current time: Oct 3, 11:00 AM  → 25 hours old → DELETED 🗑️
```

---

## 🧪 Testing Cleanup

### Test Manual Cleanup
```bash
python test_cleanup.py
```

**Expected output:**
```
🗑️ Testing Manual Cleanup Endpoint
============================================================
✅ Cleanup successful!
  📊 Current storage: 42.5 MB
  📂 Downloads: 38.2 MB
  📸 Screenshots: 4.3 MB
```

### Verify Cleanup Logs
**On server terminal:**
```bash
tail -f server.log
```

**Look for:**
```
INFO:__main__:🗑️ Cleanup: Deleted 12 files older than 24h, freed 45.67 MB
```

---

## 🔧 Configuration

### Change Retention Period
**Current:** 24 hours  
**To modify:** Edit `cleanup_old_files()` function

```python
# In emodal_business_api.py
def cleanup_old_files():
    cutoff_time = now - (48 * 60 * 60)  # 48 hours instead of 24
```

### Change Cleanup Frequency
**Current:** Every 1 hour  
**To modify:** Edit `periodic_cleanup_task()` function

```python
# In emodal_business_api.py
def periodic_cleanup_task():
    while True:
        time.sleep(7200)  # 2 hours instead of 1
        cleanup_old_files()
```

---

## 📁 Directory Structure

### After 24 Hours
```
emodal/
├── downloads/
│   └── session_12345_20251003/  (< 24h) ✅
│       ├── containers.xlsx
│       ├── copied_text.txt
│       └── parsing_debug.txt
├── screenshots/
│   └── session_12345_20251003/  (< 24h) ✅
│       ├── before_scroll.png
│       └── after_scroll.png
└── emodal_business_api.py
```

**Old sessions automatically deleted!**

---

## ⚠️ Error Handling

### If Cleanup Fails
- **Logs warning** for individual file failures
- **Continues cleanup** for other files
- **Retries** after 1 minute

### Example Error Log
```
WARNING:__main__:Failed to delete /downloads/session_123/file.xlsx: Permission denied
```

**Solution:** Check file permissions or if file is in use

---

## 🎯 Use Cases

### Production Server
- **Benefit:** Prevents disk from filling up
- **Storage:** Stays under 100 MB
- **Performance:** No manual cleanup needed

### Development Server
- **Benefit:** Old test files removed automatically
- **Debug mode:** Recent screenshots preserved for 24h
- **Manual cleanup:** Available via `/cleanup` endpoint

### High-Volume Server
- **Benefit:** Automatic cleanup after each day
- **Frequency:** Hourly checks ensure timely deletion
- **Storage:** Predictable, bounded disk usage

---

## 📊 API Endpoints Summary

### GET /health
**Check cleanup status:**
```json
{
  "status": "healthy",
  "service": "E-Modal Business API",
  "active_sessions": 2
}
```

### POST /cleanup
**Manual cleanup trigger:**
```json
{
  "success": true,
  "message": "Cleanup completed",
  "current_storage_mb": 42.5
}
```

---

## 🚀 Server Startup

**When you start the server:**
```bash
python emodal_business_api.py
```

**You'll see:**
```
🚀 E-Modal Business Operations API
==================================================
✅ Container data extraction
✅ Excel file downloads
✅ Browser session management
✅ Persistent authentication
✅ Automatic cleanup (24h retention)
==================================================
🔗 Starting server on http://0.0.0.0:5010
🗑️ Starting background cleanup task (runs every hour)
🗑️ Running initial cleanup...
🗑️ Cleanup: Deleted 15 files older than 24h, freed 67.89 MB
==================================================
```

---

## ✅ Benefits

1. **No manual cleanup** required
2. **Predictable storage usage** (< 100 MB typical)
3. **Automatic on startup** (cleans old sessions)
4. **Hourly maintenance** (prevents accumulation)
5. **On-demand cleanup** (manual trigger available)
6. **Safe deletion** (only files > 24h old)
7. **Empty directory removal** (keeps filesystem clean)
8. **Detailed logging** (track what's deleted)

---

## 📝 Summary

✅ **Automatic cleanup** every hour  
✅ **24-hour retention** policy  
✅ **Manual trigger** via `/cleanup` endpoint  
✅ **Storage monitoring** in response  
✅ **Safe deletion** (old files only)  
✅ **Error handling** (individual file failures)  
✅ **Background task** (daemon thread)  
✅ **Startup cleanup** (removes old sessions)  

**Storage efficient and fully automated!** 🎉

---

**Last Updated:** October 2, 2025  
**API Version:** 2.0  
**Retention Period:** 24 hours

