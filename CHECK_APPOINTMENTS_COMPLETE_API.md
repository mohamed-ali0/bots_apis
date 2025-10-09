# Check Appointments API - Complete Documentation

## Overview

The `/check_appointments` endpoint checks available appointment times for both **IMPORT** and **EXPORT** container workflows. It navigates through all 3 phases of the appointment booking process without submitting.

**Endpoint**: `POST /check_appointments`

**Server**: `http://37.60.243.201:5010`

---

## Request Format

### Common Fields (All Types)

```json
{
  "container_type": "import" | "export",  // REQUIRED
  
  // Authentication (choose one)
  "session_id": "sess_xxx",  // Use existing session
  // OR
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_api_key",
  
  // Optional for screenshots
  "container_number": "CONTAINER123"  // Display in screenshot annotations
}
```

---

## Import Container Request

### Required Fields

```json
{
  "container_type": "import",
  
  // Phase 1
  "trucking_company": "LONGSHIP FREIGHT LLC",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "MSCU5165756",
  
  // Phase 2
  "pin_code": "1234",          // Optional
  "truck_plate": "ABC123",     // Required (use "ABC123" or "" for wildcard)
  "own_chassis": true          // Required (true = YES, false = NO)
}
```

### Complete Example

```json
{
  "container_type": "import",
  "session_id": "sess_abc123",
  "trucking_company": "LONGSHIP FREIGHT LLC",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "MSCU5165756",
  "container_number": "MSCU5165756",
  "pin_code": "1234",
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

### Import Flow

```
Phase 1: Company → Terminal → Move Type → Container ID → Next
Phase 2: Checkbox → PIN (optional) → Truck Plate → Own Chassis → Next
Phase 3: Get Available Appointment Times
```

---

## Export Container Request

### Required Fields

```json
{
  "container_type": "export",
  
  // Phase 1
  "trucking_company": "K & R TRANSPORTATION LLC",
  "terminal": "Everport Terminal Services - Los Angeles",
  "move_type": "DROP FULL",
  "booking_number": "510476551",
  
  // Phase 2
  "unit_number": "1",          // Optional, defaults to "1"
  "seal_value": "1",           // Optional, defaults to "1"
  "truck_plate": "ABC123",     // Required (use "ABC123" or "" for wildcard)
  "own_chassis": true          // Required (true = YES, false = NO)
}
```

### Complete Example

```json
{
  "container_type": "export",
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "trucking_company": "K & R TRANSPORTATION LLC",
  "terminal": "Everport Terminal Services - Los Angeles",
  "move_type": "DROP FULL",
  "booking_number": "510476551",
  "container_number": "EXPORT123",
  "unit_number": "1",
  "seal_value": "1",
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

### Export Flow

```
Phase 1: Company → Terminal → Move Type → Booking Number → 
         Click Blank → Check Popup → Wait 5s → Quantity ("1") → Wait 3s → Next

Phase 2: Checkbox → Unit Number ("1") → 4x Seal Fields ("1") → 
         Truck Plate → Own Chassis (smart toggle) → Next

Phase 3: Find Calendar Icon → Click → Screenshot
```

---

## Response Format

### Import Success Response

```json
{
  "success": true,
  "container_type": "import",
  "session_id": "sess_abc123",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_abc123_1696848000",
  "available_times": [
    "10/10/2025 08:00 AM - 09:00 AM",
    "10/10/2025 09:00 AM - 10:00 AM",
    "10/10/2025 10:00 AM - 11:00 AM",
    "10/10/2025 11:00 AM - 12:00 PM",
    "10/10/2025 01:00 PM - 02:00 PM"
  ],
  "count": 5,
  "dropdown_screenshot_url": "http://37.60.243.201:5010/files/20251009_123456_appointment_dropdown.png",
  "debug_bundle_url": "http://37.60.243.201:5010/files/appt_sess_abc123_1696848000_20251009_123456_check_appointments.zip",
  "phase_data": {
    "container_type": "import",
    "trucking_company": "LONGSHIP FREIGHT LLC",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "MSCU5165756",
    "pin_code": "1234",
    "truck_plate": "ABC123",
    "own_chassis": true
  }
}
```

### Export Success Response

```json
{
  "success": true,
  "container_type": "export",
  "session_id": "sess_xyz789",
  "is_new_session": true,
  "appointment_session_id": "appt_sess_xyz789_1696848100",
  "calendar_found": true,
  "calendar_screenshot_url": "http://37.60.243.201:5010/files/20251009_123456_calendar_opened.png",
  "debug_bundle_url": "http://37.60.243.201:5010/files/appt_sess_xyz789_1696848100_20251009_123500_check_appointments.zip",
  "phase_data": {
    "container_type": "export",
    "trucking_company": "K & R TRANSPORTATION LLC",
    "terminal": "Everport Terminal Services - Los Angeles",
    "move_type": "DROP FULL",
    "booking_number": "510476551",
    "unit_number": "1",
    "seal_value": "1",
    "truck_plate": "9E43369",
    "own_chassis": true
  }
}
```

### Error Response (Generic)

```json
{
  "success": false,
  "error": "Phase 2 failed - Truck plate: Truck plate field not found",
  "session_id": "sess_abc123",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_abc123_1696848000",
  "current_phase": 2,
  "message": "Please provide truck_plate and retry with appointment_session_id"
}
```

### Error Response (Booking Number Validation - Export Only)

```json
{
  "success": false,
  "error": "Booking number validation failed",
  "error_message": "No open transactions for this booking number.",
  "session_id": "sess_xyz789",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_xyz789_1696848100",
  "current_phase": 1,
  "screenshot_url": "http://37.60.243.201:5010/files/sess_xyz789/booking_number_error.png"
}
```

---

## Response Fields

### Common Fields (All Responses)

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation succeeded |
| `container_type` | string | "import" or "export" |
| `session_id` | string | Browser session ID (persistent) |
| `is_new_session` | boolean | Whether browser session was newly created |
| `appointment_session_id` | string | Appointment workflow session ID |
| `debug_bundle_url` | string | Full URL to ZIP file with all screenshots |
| `phase_data` | object | All data collected through phases |

### Import-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `available_times` | array | List of available appointment time slots |
| `count` | number | Number of available times |
| `dropdown_screenshot_url` | string | Screenshot of appointment dropdown opened |

### Export-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `calendar_found` | boolean | Whether calendar icon was found and clicked |
| `calendar_screenshot_url` | string | Direct screenshot of opened calendar (if found) |

### Error-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `error` | string | Error message |
| `error_message` | string | Detailed error message from system (if available) |
| `current_phase` | number | Phase where error occurred (1-3) |
| `message` | string | Guidance for fixing and retrying |
| `screenshot_url` | string | Screenshot of error (if captured) |

---

## Field Comparison: Import vs Export

### Phase 1

| Field | Import | Export |
|-------|--------|--------|
| Trucking Company | ✅ Required | ✅ Required |
| Terminal | ✅ Required | ✅ Required |
| Move Type | ✅ Required | ✅ Required |
| Container ID | ✅ Required | ❌ N/A |
| Booking Number | ❌ N/A | ✅ Required |
| Quantity | ❌ N/A | ✅ Auto-filled ("1") |

### Phase 2

| Field | Import | Export |
|-------|--------|--------|
| Container Checkbox | ✅ Required | ✅ Required |
| PIN Code | ⚠️ Optional | ❌ N/A |
| Unit Number | ❌ N/A | ✅ Auto-filled ("1") |
| Seal Fields (4x) | ❌ N/A | ✅ Auto-filled ("1") |
| Truck Plate | ✅ Required | ✅ Required |
| Own Chassis | ✅ Required | ✅ Required |

### Phase 3

| Action | Import | Export |
|--------|--------|--------|
| Get Available Times | ✅ Returns array | ❌ N/A |
| Find Calendar Icon | ❌ N/A | ✅ Returns boolean |

---

## Special Features

### 1. Wildcard Truck Plate

Use `"ABC123"` or `""` (empty string) to select any available truck plate:

```json
{
  "truck_plate": "ABC123"  // or ""
}
```

**System will**:
- Open truck plate dropdown
- Select the first available option
- Log selected plate in response

### 2. Smart Own Chassis Toggle

The system reads the current state before toggling:

```
Console Output:
  🔍 Found 2 toggle span(s)
    Span 'NO': pressed=false, has-checked-class=False
    Span 'YES': pressed=true, has-checked-class=True
  ✅ Detected current state: YES
  ✅ Already set to YES - no action needed
```

**Only toggles if needed** - saves time and avoids errors.

### 3. Popup Detection (Export Only)

After entering booking number, system automatically:
- Checks for popup messages
- Clicks "CLOSE" button if found
- Continues flow seamlessly

### 4. Booking Number Validation (Export Only)

After entering booking number, system automatically:
- Checks for validation errors
- Detects "No open transactions" message
- Takes screenshot of error dialog
- Returns error response with details

**Error Response**:
```json
{
  "success": false,
  "error": "Booking number validation failed",
  "error_message": "No open transactions for this booking number.",
  "screenshot_url": "http://37.60.243.201:5010/files/sess_xyz/booking_number_error.png"
}
```

### 5. Session Continuation

If error occurs, retry with `appointment_session_id`:

```json
{
  "appointment_session_id": "appt_sess_abc123_1696848000",
  "truck_plate": "CORRECT_PLATE"
}
```

System will:
- Resume from current phase
- Re-use browser session
- Keep all previous data

### 5. Container Number Annotation

Use `container_number` to display in screenshots:

```json
{
  "container_number": "DISPLAY_NAME"
}
```

Priority: `container_number` → `booking_number` → `container_id`

---

## Timing

### Import Flow Timing

| Phase | Duration |
|-------|----------|
| Phase 1 | ~15 seconds |
| Phase 2 | ~10 seconds |
| Phase 3 | ~5 seconds |
| **Total** | **~30 seconds** |

### Export Flow Timing

| Phase | Duration |
|-------|----------|
| Phase 1 | ~25 seconds (includes 5s wait + 3s wait) |
| Phase 2 | ~15 seconds (4 seal fields) |
| Phase 3 | ~5 seconds |
| **Total** | **~45 seconds** |

---

## Python Examples

### Import Example

```python
import requests

# Create session
session_response = requests.post(
    "http://37.60.243.201:5010/get_session",
    json={
        "username": "your_username",
        "password": "your_password",
        "captcha_api_key": "your_api_key"
    }
)
session_id = session_response.json()["session_id"]

# Check import appointments
response = requests.post(
    "http://37.60.243.201:5010/check_appointments",
    json={
        "container_type": "import",
        "session_id": session_id,
        "trucking_company": "LONGSHIP FREIGHT LLC",
        "terminal": "ITS Long Beach",
        "move_type": "DROP EMPTY",
        "container_id": "MSCU5165756",
        "truck_plate": "ABC123",
        "own_chassis": True
    },
    timeout=600
)

result = response.json()
if result["success"]:
    print(f"Found {result['count']} available times:")
    for time_slot in result["available_times"]:
        print(f"  - {time_slot}")
```

### Export Example

```python
import requests

response = requests.post(
    "http://37.60.243.201:5010/check_appointments",
    json={
        "container_type": "export",
        "username": "jfernandez",
        "password": "taffie",
        "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
        "trucking_company": "K & R TRANSPORTATION LLC",
        "terminal": "Everport Terminal Services - Los Angeles",
        "move_type": "DROP FULL",
        "booking_number": "510476551",
        "container_number": "EXPORT123",
        "truck_plate": "",  # Wildcard
        "own_chassis": True
    },
    timeout=600
)

result = response.json()
if result["success"]:
    if result["calendar_found"]:
        print("✅ Calendar found and ready for appointment booking")
        print(f"📸 Calendar screenshot: {result['calendar_screenshot_url']}")
    else:
        print("⚠️ Calendar not found")
    print(f"📦 Debug bundle: {result['debug_bundle_url']}")
```

---

## cURL Examples

### Import

```bash
curl -X POST http://37.60.243.201:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "container_type": "import",
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_api_key",
    "trucking_company": "LONGSHIP FREIGHT LLC",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "MSCU5165756",
    "truck_plate": "ABC123",
    "own_chassis": true
  }'
```

### Export

```bash
curl -X POST http://37.60.243.201:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "container_type": "export",
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
    "trucking_company": "K & R TRANSPORTATION LLC",
    "terminal": "Everport Terminal Services - Los Angeles",
    "move_type": "DROP FULL",
    "booking_number": "510476551",
    "truck_plate": "",
    "own_chassis": true
  }'
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `container_type must be 'import' or 'export'` | Missing or invalid type | Provide "import" or "export" |
| `Missing required fields for Phase 1` | Missing company/terminal/move/container | Provide all Phase 1 fields |
| `Missing required field for Phase 2: truck_plate` | truck_plate not provided | Add truck_plate to request |
| `Booking number validation failed` | No open transactions for booking | Booking number has no active transactions |
| `Phase 1 failed - Booking number: ...` | Booking number field error | Check booking number validity |
| `Phase 2 failed - Truck plate: ...` | Truck plate not found | Use wildcard ("ABC123" or "") |
| `Phase 3 failed: No dropdown found` | Page structure changed | Check debug bundle screenshots |

### Debugging

1. **Check debug_bundle_url**: Download ZIP with all screenshots
2. **Review phase_data**: See what was successfully filled
3. **Use appointment_session_id**: Continue from where it stopped
4. **Check console logs**: Server logs show detailed step-by-step execution

---

## Best Practices

### 1. Session Management
- ✅ Create session once, reuse for multiple requests
- ✅ Sessions are persistent (10 max, LRU eviction)
- ✅ One session per user credentials

### 2. Error Recovery
- ✅ Use `appointment_session_id` to continue after errors
- ✅ Don't start over - fix the issue and retry
- ✅ Review debug bundle before retrying

### 3. Truck Plate
- ✅ Use wildcard ("ABC123" or "") when plate unknown
- ✅ System selects first available automatically
- ✅ Actual selected plate returned in response

### 4. Own Chassis
- ✅ System reads current state automatically
- ✅ Only toggles if different from desired state
- ✅ Default is YES for export, NO for import

### 5. Timeouts
- ✅ Set timeout to at least 600 seconds (10 minutes)
- ✅ Export takes longer than import (~45s vs ~30s)
- ✅ Allow extra time for network/server delays

---

## Test Scripts

### Run Import Test
```bash
python test_appointments.py
```

### Run Export Test
```bash
python test_export_appointments.py
```

---

## Related Endpoints

- **GET `/sessions`** - List all active sessions
- **GET `/sessions/<session_id>`** - Get session details
- **POST `/get_session`** - Create persistent session
- **DELETE `/sessions/<session_id>`** - Terminate session
- **POST `/make_appointment`** - Submit appointment (next step after check)

---

## Support

For issues or questions:
1. Check debug bundle screenshots
2. Review server console logs
3. Verify all required fields are provided
4. Test with known working container/booking numbers

---

**Last Updated**: October 9, 2025  
**API Version**: 2.0 (Import + Export Support)

