# Alternative Import Form Test Guide

## Overview
This guide covers testing the alternative import appointment form that uses **Line** and **Equip Size** dropdowns instead of a container number field.

---

## Test Script

**Location:** `testers/test_import_line_equipsize.py`

**Run Command:**
```bash
cd "C:\Users\Mohamed Ali\Downloads\emodal"
python testers/test_import_line_equipsize.py
```

---

## Test Data

**Container:** `TCLU8784503` (IMPORT)

**Form Fields:**
- **Trucking Company:** K & R TRANSPORTATION LLC
- **Terminal:** TraPac LLC - Los Angeles
- **Move Type:** DROP EMPTY
- **Line:** GMSU
- **Equip Size:** 40DH
- **Quantity:** 1 (auto-filled)

**Phase 2 Fields:**
- **Truck Plate:** ABC123
- **Own Chassis:** true

---

## Request Format

```json
{
  "username": "jfernandez",
  "password": "Julian_1",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "container_type": "import",
  "container_id": "TCLU8784503",
  "trucking_company": "K & R TRANSPORTATION LLC",
  "terminal": "TraPac LLC - Los Angeles",
  "move_type": "DROP EMPTY",
  "line": "GMSU",
  "equip_size": "40DH",
  "truck_plate": "ABC123",
  "own_chassis": true,
  "debug": false
}
```

---

## Expected Flow

### Phase 1: Alternative Form
```
1. Select Trucking Company: K & R TRANSPORTATION LLC
2. Select Terminal: TraPac LLC - Los Angeles
3. Select Move Type: DROP EMPTY
4. Try to fill Container Number → Not found
5. Fallback to alternative fields:
   - Select Line: GMSU
   - Select Equip Size: 40DH
   - Fill Quantity: 1
6. Click Next
```

### Phase 2: Standard Import Flow
```
1. Select Container Checkbox
2. Fill PIN (auto-filled with 1111 if not provided)
3. Select Truck Plate: ABC123
4. Toggle Own Chassis: true
5. Click Next
```

### Phase 3: Appointment Times
```
1. Open appointment dropdown
2. Capture screenshot
3. Extract available times
4. Return times list
```

---

## Console Output Examples

### Success Case
```
╔═══════════════════════════════════════════════════════════════════╗
║  Alternative Import Form Test (Line/Equip Size)                  ║
╚═══════════════════════════════════════════════════════════════════╝

🔗 API Base URL: http://localhost:5010
👤 Username: jfernandez

======================================================================
  CHECK APPOINTMENTS - Alternative Import Form Test
======================================================================
📋 Testing alternative import form (Line/Equip Size)
   Container: TCLU8784503
   Line: GMSU
   Equip Size: 40DH
   Terminal: TraPac LLC - Los Angeles
   Move Type: DROP EMPTY
   Trucking: K & R TRANSPORTATION LLC

🚀 Sending request to http://localhost:5010/check_appointments...

📊 Status Code: 200

📄 Response:
{
  "success": true,
  "session_id": "session_1234567890",
  "is_new_session": true,
  "current_phase": 3,
  "appointment_times": [
    "2025-10-12 08:00",
    "2025-10-12 09:00",
    ...
  ],
  "dropdown_screenshot_url": "http://localhost:5010/files/screenshot.png"
}

======================================================================
✅ SUCCESS
======================================================================
✅ Alternative form worked successfully!
   Session ID: session_1234567890
   Is New Session: True
   Current Phase: 3

📅 Available Appointment Times: 15
   1. 2025-10-12 08:00
   2. 2025-10-12 09:00
   3. 2025-10-12 10:00
   4. 2025-10-12 11:00
   5. 2025-10-12 12:00
   ... and 10 more

📸 Dropdown Screenshot: http://localhost:5010/files/screenshot.png
```

### Server-Side Logs
```
📋 PHASE 1 (IMPORT): Trucking Company, Terminal, Move Type, Container
⏳ Waiting 5 seconds for Phase 1 to fully load...
✅ Phase 1 ready
✅ Trucking company selected: K & R TRANSPORTATION LLC
✅ Terminal selected: TraPac LLC - Los Angeles
✅ Move type selected: DROP EMPTY
  ℹ️ Container field not found - checking for Line/Equip Size fields...
  📋 Using alternative fields: Line=GMSU, Equip Size=40DH
✅ Line selected: GMSU
✅ Equip Size selected: 40DH
🔢 Filling quantity field...
  📊 Current quantity: 0
  ✅ Quantity set to 1
  ⏳ Waiting 3 seconds...
✅ Phase 1 completed
```

---

## Test Options

### Option 1: New Session (Complete Flow)
- Creates new browser session
- Goes through full authentication
- Tests complete appointment flow
- **Time:** ~60-90 seconds

### Option 2: Existing Session (Fast)
- Creates session first
- Reuses session for test
- Skips authentication
- **Time:** ~20-30 seconds

### Option 3: Both Tests
- Runs both Option 1 and Option 2
- Good for comprehensive testing
- **Time:** ~90-120 seconds

---

## Troubleshooting

### Error: "Container field not found. Please provide 'line' and 'equip_size'"
**Cause:** Container number field doesn't exist, and alternative fields not provided  
**Solution:** Make sure request includes `"line"` and `"equip_size"` fields

### Error: "Phase 1 failed - Line: [error]"
**Cause:** Line value not found in dropdown  
**Solution:** 
- Check spelling of line value ("GMSU")
- Verify line is available in dropdown
- Try different line value (e.g., "MSC", "MAERSK")

### Error: "Phase 1 failed - Equip Size: [error]"
**Cause:** Equip Size value not found in dropdown  
**Solution:**
- Check spelling ("40DH" not "40DH ")
- Common sizes: "20GP", "40GP", "40DH", "45DH"
- Verify size is available for selected line

### Error: "Quantity field not found"
**Cause:** Quantity field not present on page  
**Solution:**
- Check if quantity field is visible
- May need to wait longer after selecting Line/Equip Size
- Check console logs for more details

---

## Key Differences from Standard Form

| Aspect | Standard Form | Alternative Form |
|--------|--------------|------------------|
| **Container Field** | ✅ Yes | ❌ No |
| **Line Dropdown** | ❌ No | ✅ Yes |
| **Equip Size Dropdown** | ❌ No | ✅ Yes |
| **Quantity Field** | ❌ No | ✅ Yes (always 1) |
| **Detection** | Default | Auto-fallback when container field not found |

---

## Request Fields Reference

### Required for All Import Appointments
- `container_type` = "import"
- `trucking_company`
- `terminal`
- `move_type`
- `truck_plate` (for Phase 2)

### Alternative Form Specific
- `line` - Shipping line (e.g., "GMSU", "MSC")
- `equip_size` - Equipment size (e.g., "40DH", "20GP")
- Quantity is always auto-filled with "1"

### Optional
- `container_id` - For display in screenshots only
- `pin_code` - Auto-fills with "1111" if not provided
- `own_chassis` - Default behavior if not specified
- `debug` - Set to `true` for debug bundle

---

## API Endpoint

**URL:** `POST /check_appointments`

**Response Fields:**
```json
{
  "success": true/false,
  "session_id": "session_xxx",
  "is_new_session": true/false,
  "current_phase": 3,
  "appointment_times": ["time1", "time2", ...],
  "dropdown_screenshot_url": "http://...",
  "debug_bundle_url": "http://..." // Only if debug=true
}
```

---

## Quick Test Commands

**Test Locally:**
```bash
python testers/test_import_line_equipsize.py
```

**Test Remote Server:**
Edit script and change:
```python
API_BASE_URL = "http://89.117.63.196:5010"
```

**With Debug Mode:**
Edit script and change:
```python
"debug": True
```

---

## Notes

✅ Container ID is optional - used only for screenshot annotation  
✅ Quantity is always auto-filled with "1"  
✅ PIN is auto-filled with "1111" if not provided  
✅ System automatically detects form type and uses appropriate fields  
✅ No breaking changes to existing API - fully backward compatible  

---

**Ready to test!** Run the script and check the results. 🚀


