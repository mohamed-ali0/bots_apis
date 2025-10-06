# Get Containers - New Work Modes

## Overview
The `/get_containers` endpoint now supports **3 work modes** plus a **debug flag** for flexible container data extraction.

---

## 🎯 Work Modes

### Mode 1: Get ALL Containers (Infinite Scroll)
**Default mode** - Loads all available containers by scrolling until no new content appears.

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "infinite_scrolling": true
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers.xlsx",
  "file_name": "containers_scraped_20251002.xlsx",
  "file_size": 44146,
  "total_containers": 459,
  "scroll_cycles": 27
}
```

---

### Mode 2: Get Specific Count
Scrolls until a **target number** of containers is loaded, then stops.

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "target_count": 100
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers.xlsx",
  "total_containers": 102,
  "scroll_cycles": 5,
  "stopped_reason": "Target count 100 reached"
}
```

**Note:** Actual loaded count may be slightly higher than target (e.g., 102 instead of 100) because scrolling loads in chunks.

---

### Mode 3: Find Specific Container
Scrolls progressively searching for a **specific container ID**, stops when found.

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "target_container_id": "MSDU5772413"
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers.xlsx",
  "total_containers": 234,
  "scroll_cycles": 12,
  "found_target_container": "MSDU5772413",
  "stopped_reason": "Container MSDU5772413 found"
}
```

**Excel contains:** All containers from start up to and including the target.

**If not found:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers.xlsx",
  "total_containers": 459,
  "scroll_cycles": 27,
  "stopped_reason": "Infinite scroll completed - all content loaded"
}
```

---

### Mode 4: First Page Only (No Scrolling)
Extracts only the first ~40 containers without any scrolling.

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "infinite_scrolling": false
}
```

---

## 🐛 Debug Mode

### Normal Mode (Default: `debug: false`)
- **No screenshots** captured (faster)
- Returns **Excel file URL only**
- Minimal overhead

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "infinite_scrolling": true,
  "debug": false
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers_scraped.xlsx",
  "total_containers": 459
}
```

---

### Debug Mode (`debug: true`)
- **Captures screenshots** at each step
- Includes **debug files** (copied_text.txt, parsing_debug.txt)
- Returns **ZIP bundle** with Excel + screenshots + debug files

```json
{
  "username": "user",
  "password": "pass",
  "captcha_api_key": "key",
  "infinite_scrolling": true,
  "debug": true
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "http://server/files/session_123/containers_scraped.xlsx",
  "total_containers": 459,
  "debug_bundle_url": "/files/session_123_20251002_173309_DEBUG.zip"
}
```

**ZIP Contents:**
```
session_123/
├── downloads/
│   ├── containers_scraped_20251002.xlsx
│   ├── copied_text.txt (raw extracted text)
│   └── parsing_debug.txt (parsing analysis)
└── screenshots/
    ├── 20251002_173300_before_infinite_scroll.png
    ├── 20251002_173306_after_infinite_scroll.png
    ├── 20251002_173306_before_scraping.png
    └── 20251002_173309_after_scraping.png
```

---

## 📊 Priority Order

If multiple mode parameters are provided, the API uses this priority:

1. **`target_container_id`** (highest priority)
2. **`target_count`**
3. **`infinite_scrolling`**

Example: If you send both `target_count` and `infinite_scrolling: true`, only `target_count` will be used.

---

## ✅ Complete Request Examples

### Example 1: Production - Get All (No Debug)
```json
{
  "username": "jfernandez",
  "password": "Puffco23",
  "captcha_api_key": "c18ae99ddce0a8acb4a4de876e2c90c4",
  "keep_browser_alive": false,
  "infinite_scrolling": true,
  "debug": false,
  "return_url": true
}
```

**Use case:** Production scraping - fast, no overhead.

---

### Example 2: Development - Get 50 with Debug
```json
{
  "username": "jfernandez",
  "password": "Puffco23",
  "captcha_api_key": "c18ae99ddce0a8acb4a4de876e2c90c4",
  "keep_browser_alive": true,
  "target_count": 50,
  "debug": true,
  "return_url": true
}
```

**Use case:** Testing parser with screenshots for debugging.

---

### Example 3: Search - Find Container
```json
{
  "username": "jfernandez",
  "password": "Puffco23",
  "captcha_api_key": "c18ae99ddce0a8acb4a4de876e2c90c4",
  "keep_browser_alive": false,
  "target_container_id": "HMMU9048448",
  "debug": false,
  "return_url": true
}
```

**Use case:** Check if a specific container exists and get all containers up to it.

---

## 🧪 Testing

### Quick Test (First Page Only)
```bash
python test_new_modes.py
# Choose option 4 (debug mode test)
```

### Full Test (All Modes)
```bash
python test_new_modes.py
# Choose option 5 (run all tests)
```

### Individual Mode Tests
```bash
# Mode 1: Get all
python test_new_modes.py  # Choose 1

# Mode 2: Target count
python test_new_modes.py  # Choose 2

# Mode 3: Find container
python test_new_modes.py  # Choose 3
```

---

## 📝 Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation status |
| `file_url` | string | Direct link to Excel file |
| `file_name` | string | Excel filename |
| `file_size` | integer | File size in bytes |
| `total_containers` | integer | Number of containers in Excel |
| `scroll_cycles` | integer | Number of scroll iterations performed |
| `found_target_container` | string | (Mode 3 only) Container ID if found |
| `stopped_reason` | string | Why scrolling stopped |
| `debug_bundle_url` | string | (Debug mode only) ZIP download link |

---

## ⚡ Performance Tips

1. **For production:** Use `debug: false` (default) - 30-40% faster
2. **For large datasets:** Use `target_count` to limit scope
3. **For specific search:** Use `target_container_id` for early exit
4. **For development:** Use `debug: true` + `keep_browser_alive: true`

---

## 🔧 Troubleshooting

### Container Counter Accuracy
The counter now uses **text-based counting** (same as parser) instead of DOM element counting. This means:

- **Before:** "Found 920 containers" (DOM rows including headers)
- **After:** "Found 459 containers" (actual container IDs) ✅

### Debug Bundle Not Created
- Ensure `debug: true` is in request body
- Check API server logs for bundle creation errors
- Verify download directory permissions (Linux)

### Container Not Found (Mode 3)
- The system will scroll through **all** content
- If not found, returns all containers loaded
- Check container ID format (e.g., "MSDU5772413" not "msdu5772413")

---

## 📚 API Documentation

### Endpoint
```
POST /get_containers
```

### Headers
```
Content-Type: application/json
```

### Request Body
```json
{
  "username": "string (required)",
  "password": "string (required)",
  "captcha_api_key": "string (required)",
  "keep_browser_alive": "boolean (optional, default: false)",
  "return_url": "boolean (optional, default: false)",
  
  // Work Mode (choose one)
  "infinite_scrolling": "boolean (optional, default: true)",
  "target_count": "integer (optional)",
  "target_container_id": "string (optional)",
  
  // Debug
  "debug": "boolean (optional, default: false)"
}
```

### Success Response (200 OK)
```json
{
  "success": true,
  "file_url": "string",
  "file_name": "string",
  "file_size": integer,
  "total_containers": integer,
  "scroll_cycles": integer,
  "found_target_container": "string (optional)",
  "stopped_reason": "string (optional)",
  "debug_bundle_url": "string (optional)"
}
```

### Error Response (4xx/5xx)
```json
{
  "success": false,
  "error": "string",
  "debug_bundle_url": "string (if debug mode enabled)"
}
```

---

## 🎉 Summary

✅ **3 flexible work modes** for different use cases  
✅ **Debug flag** for development vs production  
✅ **Accurate container counting** using text parsing  
✅ **Excel file only** in normal mode (fast)  
✅ **ZIP with screenshots** in debug mode (comprehensive)  
✅ **Progressive search** for container IDs  
✅ **Target count** for limited scraping  

---

**Last Updated:** October 2, 2025  
**API Version:** 2.0  
**Port:** 5010


