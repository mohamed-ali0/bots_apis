# API Response Types

## Overview

The E-Modal Business API uses **TWO types of responses**:

1. **JSON responses** (most endpoints)
2. **File downloads** (Excel files from `/get_containers` when `return_url: false`)

---

## Response Type by Endpoint

### 📊 **Always JSON Responses**

These endpoints **always** return JSON:

| Endpoint | Response Type | Content-Type |
|----------|---------------|--------------|
| `GET /health` | JSON | `application/json` |
| `POST /get_session` | JSON | `application/json` |
| `POST /check_appointments` | JSON | `application/json` |
| `POST /make_appointment` | JSON | `application/json` |
| `POST /get_container_timeline` | JSON | `application/json` |
| `POST /get_booking_number` | JSON | `application/json` |
| `POST /get_appointments` | JSON | `application/json` |
| `POST /cleanup` | JSON | `application/json` |

### 📁 **Conditional Response (JSON or File)**

This endpoint can return **either** JSON or a file download:

| Endpoint | Response Type | Condition |
|----------|---------------|-----------|
| `POST /get_containers` | **JSON** | When `return_url: true` in request |
| `POST /get_containers` | **Excel File** | When `return_url: false` (default) |

---

## Detailed Response Types

### 1. **JSON Responses (Default)**

**Content-Type:** `application/json`

All JSON responses follow this structure:

```json
{
  "success": true/false,
  "session_id": "session_XXXXX",
  "is_new_session": true/false,
  // ... endpoint-specific data ...
}
```

**Example - `/get_session`:**
```json
{
  "success": true,
  "session_id": "session_1696612345_123456789",
  "is_new": false,
  "username": "jfernandez",
  "created_at": "2025-10-06T15:30:00",
  "expires_at": null,
  "message": "Using existing persistent session"
}
```

**Example - `/check_appointments`:**
```json
{
  "success": true,
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "appointment_session_id": "appt_1696612400",
  "available_appointments": [
    {
      "time": "10/08/2025 07:00",
      "value": "2025-10-08T07:00:00"
    }
  ],
  "dropdown_screenshot_url": "http://37.60.243.201:5010/files/session_XXX_appointment_dropdown_opened.png"
}
```

**Example - `/get_container_timeline`:**
```json
{
  "success": true,
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "timeline_data": {
    "container_id": "MSCU5165756",
    "has_pregate": true,
    "passed_pregate": true,
    "pregate_screenshot": "http://37.60.243.201:5010/files/session_XXX_pregate_cropped.png"
  },
  "debug_bundle_url": null
}
```

**Example - `/get_containers` with `return_url: true`:**
```json
{
  "success": true,
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "file_url": "/files/session_1696612345_123456789_20251006_153000.xlsx",
  "total_containers": 500,
  "scroll_cycles": 25,
  "work_mode": "all",
  "infinite_scrolling": true
}
```

**Example - `/get_appointments`:**
```json
{
  "success": true,
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "selected_count": 150,
  "file_url": "http://37.60.243.201:5010/files/session_XXX_appointments.xlsx",
  "debug_bundle_url": null
}
```

### 2. **File Download Response**

**Content-Type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**Only Used By:** `/get_containers` when `return_url: false` (or not specified)

**Response Headers:**
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="session_XXX_20251006_153000.xlsx"
```

**How It Works:**
```python
# In /get_containers endpoint:
if return_url:
    # Return JSON with download URL
    return jsonify(response_data)
else:
    # Return file directly
    return send_file(
        dest_path,
        as_attachment=True,
        download_name=final_name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
```

---

## Request Parameter: `return_url`

### `/get_containers` Special Behavior

You can control the response type using the `return_url` parameter:

**Return JSON with URL:**
```json
POST /get_containers
{
  "session_id": "session_XXX",
  "return_url": true,  ← Returns JSON
  "infinite_scrolling": true
}
```

**Response:**
```json
{
  "success": true,
  "file_url": "/files/session_XXX.xlsx",
  "session_id": "session_XXX"
}
```

**Return File Directly:**
```json
POST /get_containers
{
  "session_id": "session_XXX",
  "return_url": false,  ← Returns Excel file
  "infinite_scrolling": true
}
```

**Response:** Excel file download

---

## Error Responses

**All errors return JSON**, regardless of endpoint:

**Format:**
```json
{
  "success": false,
  "error": "Error message here",
  "session_id": "session_XXX",  // if applicable
  "details": "Additional details"  // if applicable
}
```

**HTTP Status Codes:**
- `200` - Success (with JSON response)
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (authentication failed)
- `500` - Internal Server Error (operation failed)

**Example Error:**
```json
{
  "success": false,
  "error": "Navigation failed: Page load timeout",
  "session_id": "session_1696612345_123456789",
  "is_new_session": false
}
```

---

## Debug Mode Responses

When `debug: true` is included in the request, responses include debug information:

```json
{
  "success": true,
  "session_id": "session_XXX",
  "is_new_session": false,
  // ... normal response data ...
  "debug_bundle_url": "/files/session_XXX_20251006_153000_debug.zip"
}
```

**Debug bundle contains:**
- All screenshots from the operation
- Extracted text files
- Error logs (if any)
- Operation metadata

---

## Content-Type Summary

| Response Type | Content-Type | Used By |
|---------------|--------------|---------|
| **JSON** | `application/json` | All endpoints (default) |
| **Excel File** | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `/get_containers` only (when `return_url: false`) |
| **ZIP File** | `application/zip` | Debug bundles (via URL in JSON response) |
| **PNG Image** | `image/png` | Screenshots (via URL in JSON response) |

---

## Best Practices

### For API Clients:

1. **Always check `Content-Type` header:**
   ```python
   response = requests.post(url, json=data)
   if response.headers['Content-Type'] == 'application/json':
       data = response.json()
   else:
       # File download
       with open('containers.xlsx', 'wb') as f:
           f.write(response.content)
   ```

2. **Use `return_url: true` for consistent JSON responses:**
   ```json
   {
     "return_url": true  // Always get JSON, never file
   }
   ```

3. **Handle both success and error JSON:**
   ```python
   result = response.json()
   if result['success']:
       # Process success data
   else:
       # Handle error
       print(f"Error: {result['error']}")
   ```

### For `/get_containers` Specifically:

**If you want JSON response:**
```json
{
  "session_id": "session_XXX",
  "return_url": true,
  "infinite_scrolling": true
}
```

**If you want direct file download:**
```json
{
  "session_id": "session_XXX",
  "return_url": false,  // or omit this field
  "infinite_scrolling": true
}
```

---

## Summary

✅ **Default:** All endpoints return **JSON**  
✅ **Exception:** `/get_containers` can return **Excel file** when `return_url: false`  
✅ **Errors:** Always **JSON**  
✅ **Debug bundles:** URLs in JSON responses (not direct downloads)  
✅ **Screenshots:** URLs in JSON responses (not direct downloads)

**Recommendation:** Use `return_url: true` in `/get_containers` requests for consistent JSON responses across all endpoints.
