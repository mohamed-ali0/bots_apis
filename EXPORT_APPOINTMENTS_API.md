# Export Container Appointment Flow API Documentation

## Overview

The `/check_appointments` endpoint now supports both **IMPORT** and **EXPORT** container workflows. This document focuses on the export flow.

## Key Differences: Import vs Export

### Phase 1 - Basic Information
| Field | Import | Export |
|-------|--------|--------|
| Trucking Company | ✅ Required | ✅ Required |
| Terminal | ✅ Required | ✅ Required |
| Move Type | ✅ Required | ✅ Required |
| Container ID | ✅ Required | ❌ N/A |
| Booking Number | ❌ N/A | ✅ Required |
| Quantity | ❌ N/A | ✅ Required (auto-filled with "1") |

### Phase 2 - Container Details
| Field | Import | Export |
|-------|--------|--------|
| Container Checkbox | ✅ Required | ✅ Required |
| PIN Code | ⚠️ Optional | ❌ N/A |
| Unit Number | ❌ N/A | ✅ Required (default: "1") |
| Seal Fields (4x) | ❌ N/A | ✅ Required (default: "1" each) |
| Truck Plate | ✅ Required | ✅ Required |
| Own Chassis | ✅ Required | ✅ Required |

### Phase 3 - Appointment Selection
| Action | Import | Export |
|--------|--------|--------|
| Get Available Times | ✅ Returns list of time slots | ❌ N/A |
| Find Calendar Icon | ❌ N/A | ✅ Returns calendar_found: true/false |

## API Endpoint

### POST `/check_appointments`

Check available appointment times for import or export containers.

## Request Format

### Required Fields (All Types)
```json
{
  "container_type": "export",  // REQUIRED: "import" or "export"
  
  // Authentication (one of the following)
  "session_id": "sess_xxx",  // Use existing session
  // OR
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_api_key"
}
```

### Export-Specific Request
```json
{
  "container_type": "export",
  "session_id": "sess_xxx",
  
  // Phase 1 fields
  "trucking_company": "LONGSHIP FREIGHT LLC",
  "terminal": "ITS Long Beach",
  "move_type": "DROP FULL",
  "booking_number": "RICFEM857500",
  
  // Phase 2 fields
  "unit_number": "1",        // Optional, defaults to "1"
  "seal_value": "1",         // Optional, defaults to "1"
  "truck_plate": "ABC123",   // Can use "ABC123" or "" to select any available
  "own_chassis": true
}
```

### Import-Specific Request (For Comparison)
```json
{
  "container_type": "import",
  "session_id": "sess_xxx",
  
  // Phase 1 fields
  "trucking_company": "LONGSHIP FREIGHT LLC",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "MSCU5165756",
  
  // Phase 2 fields
  "pin_code": "1234",        // Optional
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

## Response Format

### Export Success Response
```json
{
  "success": true,
  "container_type": "export",
  "session_id": "sess_xxx",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_xxx_12345",
  "calendar_found": true,  // Boolean: was calendar icon found?
  "debug_bundle_url": "/files/appt_sess_xxx_12345_20251009_123456_check_appointments.zip",
  "phase_data": {
    "container_type": "export",
    "trucking_company": "LONGSHIP FREIGHT LLC",
    "terminal": "ITS Long Beach",
    "move_type": "DROP FULL",
    "booking_number": "RICFEM857500",
    "unit_number": "1",
    "seal_value": "1",
    "truck_plate": "ABC123",
    "own_chassis": true
  }
}
```

### Import Success Response (For Comparison)
```json
{
  "success": true,
  "container_type": "import",
  "session_id": "sess_xxx",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_xxx_12345",
  "available_times": [
    "10/10/2025 08:00 AM - 09:00 AM",
    "10/10/2025 09:00 AM - 10:00 AM",
    "10/10/2025 10:00 AM - 11:00 AM"
  ],
  "count": 3,
  "dropdown_screenshot_url": "http://89.117.63.196:5010/files/screenshot_123456.png",
  "debug_bundle_url": "/files/appt_sess_xxx_12345_20251009_123456_check_appointments.zip",
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

### Error Response
```json
{
  "success": false,
  "error": "Phase 2 failed - Unit number: Unit number field not found",
  "session_id": "sess_xxx",
  "is_new_session": false,
  "appointment_session_id": "appt_sess_xxx_12345",
  "current_phase": 2,
  "message": "Please provide missing fields and retry with appointment_session_id"
}
```

## Export Flow Details

### Phase 1: Basic Information + Booking Number + Quantity

**What happens:**
1. Selects trucking company from dropdown
2. Selects terminal from dropdown
3. Selects move type from dropdown
4. Fills booking number field (uses the same chip input as container number)
5. Fills quantity field with "1"
6. Waits 3 seconds (as requested)
7. Clicks "Next" button to advance to Phase 2

**Fields:**
- `trucking_company`: Company name (e.g., "LONGSHIP FREIGHT LLC")
- `terminal`: Terminal name (e.g., "ITS Long Beach")
- `move_type`: Move type (e.g., "DROP FULL")
- `booking_number`: Booking number (e.g., "RICFEM857500")

**Automatic Actions:**
- Quantity is automatically set to "1"
- System waits 3 seconds after filling quantity before clicking Next

### Phase 2: Container Selection + Export Fields

**What happens:**
1. Checks the container checkbox (only if not already checked)
2. Fills unit number field with "1" (or provided value)
3. Fills all 4 seal fields with "1" (or provided value):
   - Seal1_Num
   - Seal2_Num
   - Seal3_Num
   - Seal4_Num
4. Fills truck plate (supports wildcard "ABC123" or "" to select any available)
5. Toggles own chassis to desired state
6. Clicks "Next" button to advance to Phase 3

**Fields:**
- `unit_number`: Unit number (default: "1")
- `seal_value`: Value for all seal fields (default: "1")
- `truck_plate`: Truck plate number or wildcard
- `own_chassis`: Boolean (true/false)

**Smart Features:**
- Truck plate supports wildcard: use "ABC123" or empty string "" to select any available option
- Seal fields are filled efficiently in a loop
- Own chassis toggle checks current state before clicking

### Phase 3: Find Calendar Icon

**What happens:**
1. Searches for calendar icon with text "calendar_month"
2. If found, clicks the calendar icon
3. Takes screenshot showing the calendar
4. Returns `calendar_found: true` or `false`

**Important:**
- This phase does NOT select a time or submit anything
- It only verifies that the calendar icon is present and clickable
- The response includes a screenshot in the debug bundle

## Field Defaults

Export containers have sensible defaults:

| Field | Default Value | Required? |
|-------|---------------|-----------|
| unit_number | "1" | ✅ Yes (auto-filled) |
| seal_value | "1" | ✅ Yes (auto-filled) |
| truck_plate | N/A | ✅ Yes (must provide) |
| own_chassis | false | ⚠️ Optional (defaults to false) |

## Timing

- Phase load wait: 5 seconds (consistent across all phases)
- Quantity fill wait: 3 seconds after setting quantity
- Between fields: 0.2-0.5 seconds for smooth input

## Session Continuation

If an error occurs mid-flow, you can continue from where you left off:

```json
{
  "container_type": "export",
  "appointment_session_id": "appt_sess_xxx_12345",  // From error response
  
  // Only provide the missing or corrected fields
  "truck_plate": "CORRECT_PLATE"
}
```

The system will:
1. Resume from the current phase
2. Re-use the existing browser session
3. Keep all previously filled data

## Debug Bundle

The debug bundle (ZIP file) contains:
- Screenshots from all phases
- Screenshots after every field fill and button click
- Special screenshot showing calendar (for export)
- Or appointment dropdown (for import)

Access the bundle at: `http://your-server:5010{debug_bundle_url}`

## Testing

Use the provided test script:

```bash
python test_export_appointments.py
```

The test script will:
1. Create a persistent session
2. Test the complete export flow
3. Optionally test import flow for comparison

## Common Issues and Solutions

### Issue: Calendar Not Found
**Symptom:** `calendar_found: false`

**Solutions:**
1. Check if the booking number is valid for export
2. Verify move type is appropriate for export (e.g., "DROP FULL")
3. Review debug bundle screenshots to see what's on Phase 3

### Issue: Booking Number Field Not Found
**Symptom:** `Phase 1 failed - Booking number: Booking number field not found`

**Solutions:**
1. Ensure `container_type` is set to "export"
2. Verify the website structure hasn't changed
3. Check if the booking number field requires different identification

### Issue: Seal Fields Not All Filled
**Symptom:** Response shows `seals_filled: 2` instead of 4

**Cause:** Some seal fields might not be present on the page

**Action:** This is expected in some cases. The system fills as many as it finds (1-4).

## Best Practices

1. **Always specify container_type first** - This determines the entire flow
2. **Use wildcard truck plates** - "ABC123" or "" to avoid plate-specific errors
3. **Review debug bundles** - Screenshots show exactly what happened
4. **Use session continuation** - Don't start over if there's a correctable error
5. **Default values work well** - unit_number and seal_value defaults are usually correct

## API Compatibility

- Fully backward compatible with import flow
- Existing import requests continue to work without changes
- Container type is explicitly required to prevent confusion
- Both flows use the same session management

## Next Steps

After successfully checking export appointments with `calendar_found: true`, you can:
1. Proceed to `/make_appointment` endpoint (when implemented)
2. Select specific appointment time
3. Submit the appointment

## Related Documentation

- `SESSION_ENDPOINTS_API.md` - Session management
- `CHECK_APPOINTMENTS_API.md` - Import flow details
- `test_export_appointments.py` - Test script with examples

