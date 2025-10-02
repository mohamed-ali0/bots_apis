# 📋 Appointment Endpoints - Quick Reference

## 🔍 Check Appointments (Safe)

**Endpoint**: `POST /check_appointments`

**Purpose**: Get available appointment times WITHOUT submitting

**Required Fields**:
```json
{
  "username": "jfernandez",
  "password": "pass123",
  "captcha_api_key": "abc...",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  "truck_plate": "ABC123",
  "own_chassis": false
}
```

**Optional Fields**:
- `pin_code`: PIN code (string)

**Response**:
```json
{
  "success": true,
  "available_times": ["Thursday 10/02/2025 07:00 - 12:00", ...],
  "count": 3,
  "debug_bundle_url": "/files/..."
}
```

---

## ✅ Make Appointment (⚠️ SUBMITS!)

**Endpoint**: `POST /make_appointment`

**Purpose**: Submit an actual appointment

**Required Fields**:
```json
{
  "username": "jfernandez",
  "password": "pass123",
  "captcha_api_key": "abc...",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  "truck_plate": "ABC123",
  "own_chassis": false,
  "appointment_time": "Thursday 10/02/2025 07:00 - 12:00"
}
```

**Optional Fields**:
- `pin_code`: PIN code (string)

**Response**:
```json
{
  "success": true,
  "appointment_confirmed": true,
  "debug_bundle_url": "/files/...",
  "appointment_details": { ... }
}
```

---

## 🔄 Error Recovery

If you get an error like:
```json
{
  "success": false,
  "error": "Missing required field for Phase 2: truck_plate",
  "session_id": "session_123_456",
  "current_phase": 2
}
```

**Continue with**:
```json
{
  "session_id": "session_123_456",
  "truck_plate": "ABC123"
}
```

⏰ Session stays alive for **10 minutes**

---

## 📝 Field Reference

| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `username` | ✅ | `"jfernandez"` | E-Modal username |
| `password` | ✅ | `"pass123"` | E-Modal password |
| `captcha_api_key` | ✅ | `"abc..."` | 2captcha API key |
| `trucking_company` | ✅ | `"TEST TRUCKING"` | Exact text match |
| `terminal` | ✅ | `"ITS Long Beach"` | Exact text match |
| `move_type` | ✅ | `"DROP EMPTY"` | Exact text match |
| `container_id` | ✅ | `"CAIU7181746"` | Container number |
| `truck_plate` | ✅ | `"ABC123"` | Truck license plate |
| `own_chassis` | ✅ | `false` | Boolean (true/false) |
| `appointment_time` | ✅* | `"Thursday 10/02/2025 07:00"` | *Only for `/make_appointment` |
| `pin_code` | ❌ | `"0000"` | Optional |

---

## 🧪 Testing

### Quick Test
```bash
python test_appointments.py
```

### Manual cURL Test
```bash
curl -X POST http://89.117.63.196:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d @payload.json
```

---

## ⚡ Key Points

✅ `/check_appointments` is **SAFE** - never submits  
⚠️ `/make_appointment` **SUBMITS** - use carefully  
📸 Both generate **debug bundles** with screenshots  
⏰ Session timeout: **10 minutes** for error recovery  
🔤 Dropdown values: **Exact text match** required  
🎯 Phases: **3 phases** (dropdowns → details → appointment)

---

## 🐛 Common Issues

**"Dropdown not found"**
→ Check exact text match (case-sensitive)

**"Option not found"**
→ Verify option text exactly matches available option

**"Session expired"**
→ 10 minutes passed, restart with fresh request

**"Checkbox not clickable"**
→ Check debug bundle screenshots for page state

---

## 📦 Debug Bundle

Every request generates a ZIP file with screenshots:
- Every dropdown selection
- Every button click
- Every input field fill
- Final confirmation screen

Download from `debug_bundle_url` in response.

---

## 📚 Full Documentation

- **`APPOINTMENT_ENDPOINTS.md`** - Complete API documentation
- **`APPOINTMENT_IMPLEMENTATION_SUMMARY.md`** - Technical details
- **`test_appointments.py`** - Test script

---

## 🚀 Workflow

1. **First**: Test with `/check_appointments` to get available times
2. **Then**: Use `/make_appointment` with specific time to submit
3. **Always**: Check debug bundle if issues occur

---

**Need help?** Check the full documentation in `APPOINTMENT_ENDPOINTS.md`!

