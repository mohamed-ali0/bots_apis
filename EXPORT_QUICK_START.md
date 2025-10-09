# Export Appointments - Quick Start Guide

## TL;DR

Check export container appointments with one API call:

```bash
POST /check_appointments
{
  "container_type": "export",
  "session_id": "your_session",
  "booking_number": "BOOKING123",
  "trucking_company": "COMPANY_NAME",
  "terminal": "TERMINAL_NAME",
  "move_type": "DROP FULL",
  "truck_plate": "ABC123",
  "own_chassis": true
}
```

Returns: `{"calendar_found": true/false}`

## Minimal Example

```python
import requests

# 1. Create session
session = requests.post("http://localhost:5010/get_session", json={
    "username": "user",
    "password": "pass",
    "captcha_api_key": "key"
}).json()

# 2. Check export appointments
response = requests.post("http://localhost:5010/check_appointments", json={
    "container_type": "export",
    "session_id": session["session_id"],
    "booking_number": "RICFEM857500",
    "trucking_company": "LONGSHIP FREIGHT LLC",
    "terminal": "ITS Long Beach",
    "move_type": "DROP FULL",
    "truck_plate": "ABC123",  # Or "" to select any
    "own_chassis": True
}).json()

# 3. Check result
if response["success"]:
    print(f"Calendar found: {response['calendar_found']}")
else:
    print(f"Error: {response['error']}")
```

## Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `container_type` | Must be "export" | `"export"` |
| `booking_number` | Export booking number | `"RICFEM857500"` |
| `trucking_company` | Company name | `"LONGSHIP FREIGHT LLC"` |
| `terminal` | Terminal name | `"ITS Long Beach"` |
| `move_type` | Move type | `"DROP FULL"` |
| `truck_plate` | Truck plate | `"ABC123"` or `""` |
| `own_chassis` | Own chassis toggle | `true` or `false` |

## Optional Fields (Auto-Filled)

| Field | Default | Description |
|-------|---------|-------------|
| `unit_number` | `"1"` | Unit number |
| `seal_value` | `"1"` | Value for all 4 seal fields |

## Import vs Export

```python
# Import container
{
    "container_type": "import",
    "container_id": "MSCU5165756",  # Container ID
    "pin_code": "1234",  # Optional PIN
    # ... other fields
}
# Returns: {"available_times": [...], "count": 3}

# Export container
{
    "container_type": "export",
    "booking_number": "RICFEM857500",  # Booking number
    # No PIN for export
    # ... other fields
}
# Returns: {"calendar_found": true}
```

## What Happens Automatically

1. ✅ **Quantity** → Set to "1"
2. ✅ **Wait 3 seconds** → After quantity fill
3. ✅ **Unit number** → Set to "1"
4. ✅ **4 Seal fields** → All set to "1"
5. ✅ **Truck plate** → Wildcard support ("ABC123" = any plate)
6. ✅ **Calendar search** → Find and click icon
7. ✅ **Screenshot** → Captured in debug bundle

## Response

### Success
```json
{
  "success": true,
  "container_type": "export",
  "calendar_found": true,
  "session_id": "sess_xxx",
  "debug_bundle_url": "/files/bundle.zip"
}
```

### Error
```json
{
  "success": false,
  "error": "Phase 2 failed - Unit number: ...",
  "current_phase": 2,
  "appointment_session_id": "appt_xxx"
}
```

## Test It

```bash
python test_export_appointments.py
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `calendar_found: false` | Check booking number validity |
| Booking field not found | Verify `container_type: "export"` |
| Truck plate error | Use `"ABC123"` or `""` for wildcard |

## Full Documentation

- **Complete API**: `EXPORT_APPOINTMENTS_API.md`
- **Implementation**: `EXPORT_FLOW_IMPLEMENTATION_SUMMARY.md`
- **Test Script**: `test_export_appointments.py`

## Support

1. Check `debug_bundle_url` for screenshots
2. Review `phase_data` in response
3. Use `appointment_session_id` to continue from error

---

**That's it!** 🚀 You're ready to use export appointments.

