# Check Appointments API - Line Dropdown Fallback

## Overview

The `/check_appointments` endpoint now includes intelligent fallback handling for the Line dropdown selection. When the specified line is not found in the dropdown options, the system will automatically select any available option to continue the appointment flow.

## Request Format

### Basic Request Structure

```json
{
  "container_type": "import",
  "session_id": "session_1234567890_abc123",
  "trucking_company": "Your Trucking Company",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "ABCD1234567",
  "line": "COSCO",
  "equip_size": "40",
  "pin_code": "1234",
  "truck_plate": "ABC123",
  "own_chassis": true,
  "debug": false
}
```

### New Line Fallback Behavior

When using the alternative import form (Line/Equip Size fields), the system now handles missing line options gracefully:

#### Before (Old Behavior)
```json
{
  "line": "COSCO",
  "equip_size": "40"
}
```
- If "COSCO" not found → **FAILS** with error
- User must retry with correct line name

#### After (New Behavior)
```json
{
  "line": "COSCO",
  "equip_size": "40"
}
```
- If "COSCO" not found → **AUTOMATICALLY** selects any available line
- Continues with appointment flow
- Logs the fallback selection

## Request Parameters

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `container_type` | string | "import" or "export" |
| `session_id` | string | Browser session ID (optional) |
| `trucking_company` | string | Trucking company name |
| `terminal` | string | Terminal name (e.g., "ITS Long Beach") |
| `move_type` | string | Move type (e.g., "DROP EMPTY") |

### Container Identification

**For Import Containers:**
```json
{
  "container_id": "ABCD1234567"
}
```

**For Export Containers:**
```json
{
  "booking_number": "BOOK123456"
}
```

### Alternative Import Form (Line/Equip Size)

When container/booking number fields are not available, use:

```json
{
  "line": "COSCO",
  "equip_size": "40"
}
```

**Line Fallback Behavior:**
- ✅ If "COSCO" exists → Selects "COSCO"
- ⚠️ If "COSCO" not found → Selects any available line automatically
- 📝 Logs: `Line 'COSCO' not found, used fallback: 'MSC'`

### Phase 2 Fields

**For Import:**
```json
{
  "pin_code": "1234",
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

**For Export:**
```json
{
  "unit_number": "1",
  "seal_value": "1",
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `container_number` | string | Display name for screenshots |
| `manifested_date` | string | Date for import counter (YYYY-MM-DD) |
| `departed_date` | string | Date for import counter (YYYY-MM-DD) |
| `last_free_day_date` | string | Date for import counter (YYYY-MM-DD) |
| `debug` | boolean | Enable debug bundle (default: false) |

## Response Format

### Success Response (Import)

```json
{
  "success": true,
  "session_id": "session_1234567890_abc123",
  "is_new_session": false,
  "appointment_session_id": "appt_session_1234567890_abc123",
  "available_times": [
    "08:00 AM",
    "09:00 AM",
    "10:00 AM"
  ],
  "current_phase": 3,
  "message": "Appointment times retrieved successfully"
}
```

### Success Response (Export)

```json
{
  "success": true,
  "session_id": "session_1234567890_abc123",
  "is_new_session": false,
  "appointment_session_id": "appt_session_1234567890_abc123",
  "calendar_found": true,
  "calendar_screenshot_url": "http://server:5000/files/calendar_1234567890.png",
  "current_phase": 3,
  "message": "Calendar opened successfully"
}
```

### Error Response

```json
{
  "success": false,
  "error": "Phase 1 failed - Line: Option 'INVALID_LINE' not found in Line. Available options: MSC, CMA, HAPAG",
  "session_id": "session_1234567890_abc123",
  "is_new_session": false,
  "appointment_session_id": "appt_session_1234567890_abc123",
  "current_phase": 1
}
```

## Line Fallback Examples

### Example 1: Line Found
```json
{
  "line": "MSC",
  "equip_size": "40"
}
```
**Result:** ✅ Selects "MSC" (exact match)

### Example 2: Line Not Found - Fallback Used
```json
{
  "line": "UNKNOWN_LINE",
  "equip_size": "40"
}
```
**Result:** ⚠️ Selects first available option (e.g., "MSC")
**Log:** `Line 'UNKNOWN_LINE' not found, used fallback: 'MSC'`

### Example 3: No Options Available
```json
{
  "line": "ANY_LINE",
  "equip_size": "40"
}
```
**Result:** ❌ Fails with "No options available in Line dropdown"

## Benefits

1. **Improved Reliability:** No more failures due to missing line options
2. **Automatic Recovery:** System continues with any available line
3. **Better User Experience:** Reduces retry requirements
4. **Transparent Logging:** Users know when fallback was used
5. **Maintains Functionality:** Appointment flow continues successfully

## Usage Notes

- Line fallback only applies to the alternative import form (Line/Equip Size fields)
- Fallback selects the first available option in the dropdown
- Original line preference is logged for transparency
- No changes to response format - same success/error structure
- Debug mode shows fallback selections in screenshots

## Error Handling

The system handles various scenarios:

1. **Line Found:** Normal selection
2. **Line Not Found:** Automatic fallback to any option
3. **No Options Available:** Returns error with available options
4. **Dropdown Not Found:** Returns standard dropdown error
5. **Network Issues:** Returns connection error

This ensures maximum reliability while maintaining clear error reporting when truly necessary.
