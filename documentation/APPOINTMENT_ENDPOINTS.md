# 📅 Appointment Booking Endpoints

## Overview

Two new endpoints for managing E-Modal appointment bookings:

1. **`/check_appointments`** - Check available appointment times (does NOT submit)
2. **`/make_appointment`** - Make an appointment (ACTUALLY SUBMITS)

Both endpoints go through a **3-phase process**:
- **Phase 1**: Trucking company, Terminal, Move type, Container number
- **Phase 2**: Container selection, PIN code, Truck plate, Own chassis
- **Phase 3**: Appointment time selection (and Submit for `/make_appointment`)

---

## 🔍 `/check_appointments` - Check Available Times

**Purpose**: Go through all 3 phases to retrieve available appointment time slots without submitting.

### Request Format

```json
{
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_2captcha_key",
  
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  
  "truck_plate": "ABC123",
  "pin_code": "0000",  // Optional
  "own_chassis": false
}
```

### Response Format (Success)

```json
{
  "success": true,
  "available_times": [
    "Thursday 10/02/2025 07:00 - 12:00",
    "Thursday 10/02/2025 13:00 - 18:00",
    "Friday 10/03/2025 07:00 - 12:00"
  ],
  "count": 3,
  "debug_bundle_url": "/files/session_123_20251002_143045_check_appointments.zip",
  "phase_data": {
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "pin_code": "0000",
    "truck_plate": "ABC123",
    "own_chassis": false
  }
}
```

### Response Format (Error - Missing Fields)

If a required field is missing, the endpoint returns an error with `session_id` to continue:

```json
{
  "success": false,
  "error": "Missing required field for Phase 2: truck_plate",
  "session_id": "session_123_456",
  "current_phase": 2,
  "message": "Please provide truck_plate and retry with session_id"
}
```

**To continue**: Send another request with the missing field(s) and the `session_id`:

```json
{
  "session_id": "session_123_456",
  "truck_plate": "ABC123"
}
```

The session will be kept alive for **10 minutes** to allow recovery.

---

## ✅ `/make_appointment` - Submit Appointment

**⚠️ WARNING**: This endpoint **ACTUALLY SUBMITS** the appointment!

**Purpose**: Complete all 3 phases and click the Submit button to finalize the appointment.

### Request Format

```json
{
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_2captcha_key",
  
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  
  "truck_plate": "ABC123",
  "pin_code": "0000",  // Optional
  "own_chassis": false,
  
  "appointment_time": "Thursday 10/02/2025 07:00 - 12:00"
}
```

### Response Format (Success)

```json
{
  "success": true,
  "appointment_confirmed": true,
  "debug_bundle_url": "/files/session_123_20251002_143045_appointment_submitted.zip",
  "appointment_details": {
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "truck_plate": "ABC123",
    "own_chassis": false,
    "appointment_time": "Thursday 10/02/2025 07:00 - 12:00"
  }
}
```

---

## 📋 Field Reference

### Phase 1 Fields (Always Required)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `username` | string | E-Modal username | `"jfernandez"` |
| `password` | string | E-Modal password | `"password123"` |
| `captcha_api_key` | string | 2captcha API key | `"abc123..."` |
| `trucking_company` | string | Trucking company name (exact match) | `"TEST TRUCKING"` |
| `terminal` | string | Terminal name (exact match) | `"ITS Long Beach"` |
| `move_type` | string | Move type (exact match) | `"DROP EMPTY"` |
| `container_id` | string | Container number | `"CAIU7181746"` |

### Phase 2 Fields (Required Unless Continuing Session)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `truck_plate` | string | Truck license plate | `"ABC123"` |
| `pin_code` | string | PIN code (optional) | `"0000"` |
| `own_chassis` | boolean | Own chassis toggle | `false` |

### Phase 3 Fields (`/make_appointment` Only)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `appointment_time` | string | Exact appointment time from available list | `"Thursday 10/02/2025 07:00 - 12:00"` |

---

## 🔄 Session Recovery (Error Handling)

If the endpoint encounters a missing field or error during any phase, it will:
1. Keep the browser session alive for **10 minutes**
2. Return a `session_id` in the error response
3. Wait for you to send a follow-up request with the missing data

### Example Flow

**Request 1** (missing `truck_plate`):
```json
{
  "username": "jfernandez",
  "password": "pass123",
  "captcha_api_key": "abc...",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746"
  // Missing truck_plate!
}
```

**Response 1** (Error):
```json
{
  "success": false,
  "error": "Missing required field for Phase 2: truck_plate",
  "session_id": "session_123_456",
  "current_phase": 2,
  "message": "Please provide truck_plate and retry with session_id"
}
```

**Request 2** (continue with session):
```json
{
  "session_id": "session_123_456",
  "truck_plate": "ABC123"
}
```

**Response 2** (Success):
```json
{
  "success": true,
  "available_times": [...]
}
```

---

## 🖼️ Debug Bundles

Both endpoints generate a **debug bundle ZIP file** containing:
- Screenshots after every action (dropdown selection, button click, etc.)
- Full page screenshots at each phase
- Appointment confirmation screenshot (for `/make_appointment`)

Download the bundle from the `debug_bundle_url` in the response.

---

## 🧪 Testing

### Using the Test Script

```bash
python test_appointments.py
```

**Menu Options:**
1. **Check Available Appointments** - Safe to test, does NOT submit
2. **Make Appointment** - ⚠️ WILL SUBMIT - Only for production use
3. **Exit**

### Manual Testing with cURL

**Check appointments:**
```bash
curl -X POST http://89.117.63.196:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "pass123",
    "captcha_api_key": "abc...",
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "truck_plate": "ABC123",
    "own_chassis": false
  }'
```

---

## ⚠️ Important Notes

1. **`/check_appointments` is SAFE** - It only retrieves time slots, never submits
2. **`/make_appointment` is PRODUCTION** - It ACTUALLY submits the appointment!
3. **Session timeout**: Appointment sessions expire after 10 minutes
4. **Exact text matching**: Dropdown values must match EXACTLY (case-sensitive)
5. **PIN code**: Optional - omit if not required
6. **Screenshots**: Always captured for debugging - included in ZIP bundle
7. **Browser cleanup**: Sessions are automatically closed after completion or timeout

---

## 📊 Implementation Details

### Phase Flow

```
┌─────────────────────────────────────────────────────┐
│  PHASE 1: Basic Information                         │
├─────────────────────────────────────────────────────┤
│  - Select Trucking Company dropdown                 │
│  - Select Terminal dropdown                         │
│  - Select Move Type dropdown                        │
│  - Fill Container Number input                      │
│  - Click "Next" button                              │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 2: Container Details                         │
├─────────────────────────────────────────────────────┤
│  - Select Container checkbox                        │
│  - Fill PIN Code input (optional)                   │
│  - Fill Truck Plate input                           │
│  - Toggle Own Chassis (YES/NO)                      │
│  - Click "Next" button                              │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 3: Appointment Time                          │
├─────────────────────────────────────────────────────┤
│  /check_appointments:                               │
│    - Get available times from dropdown              │
│    - Return list to user                            │
│                                                      │
│  /make_appointment:                                 │
│    - Select specific appointment time               │
│    - Click "Submit" button ⚠️                       │
└─────────────────────────────────────────────────────┘
```

### Element Selection Strategy

All form interactions use:
- **XPath selectors** for robustness
- **Material Design compatibility** (mat-select, mat-checkbox, etc.)
- **Multiple fallback patterns** for each element
- **JavaScript scrollIntoView** to ensure visibility
- **Screenshots after every action** for debugging

---

## 🐛 Troubleshooting

### "Dropdown not found"
- Check that the dropdown label is correct (case-sensitive)
- Ensure the page has fully loaded before interaction
- Check debug bundle screenshots to see page state

### "Option not found in dropdown"
- The option text must match EXACTLY (including spaces, punctuation)
- Check available options by inspecting the debug bundle

### "Session expired"
- 10-minute timeout has passed since error
- Restart with a fresh request (no session_id)

### "Checkbox not clickable"
- Browser viewport might be too small
- Element might be obscured - check screenshots

---

## 📝 Change Log

**v1.0** (2025-10-02)
- Initial implementation of `/check_appointments` and `/make_appointment`
- 3-phase appointment booking flow
- Session recovery with 10-minute timeout
- Debug bundle generation with full screenshot history
- Exact text matching for all dropdowns
- Material Design component compatibility

---

## 🔗 Related Endpoints

- `/get_containers` - Retrieve container list
- `/get_container_timeline` - Check container timeline and Pregate status
- `/health` - API health check
- `/sessions` - List active sessions

---

**Need Help?** Check the debug bundle screenshots to see exactly what the system is doing at each step!


