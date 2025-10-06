# E-Modal API - Quick Reference Card

## 🚀 Base URLs
```
Local:    http://localhost:5010
Remote 1: http://89.117.63.196:5010
Remote 2: http://37.60.243.201:5010  (default)
```

## 🔑 Test Credentials
```python
Username: jfernandez
Password: taffie
Captcha:  7bf85bb6f37c9799543a2a463aab2b4f
```

## 📡 Endpoints at a Glance

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check API status |
| `/get_session` | POST | Create persistent session |
| `/get_containers` | POST | Get container data (3 modes) |
| `/get_container_timeline` | POST | Get timeline + Pregate status |
| `/get_booking_number` | POST | Extract booking number |
| `/get_appointments` | POST | Download appointments Excel |
| `/check_appointments` | POST | Get available times (no submit) |
| `/make_appointment` | POST | Submit appointment (⚠️ REAL) |
| `/cleanup` | POST | Manual file cleanup |

## 📝 Request Formats

### Session Creation
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
}
```

### Get Containers (3 Modes)
```json
// Mode 1: Infinite Scrolling
{"session_id": "xxx", "infinite_scrolling": true}

// Mode 2: Target Count
{"session_id": "xxx", "target_count": 100}

// Mode 3: Target Container ID
{"session_id": "xxx", "target_container_id": "MSCU5165756"}
```

### Get Timeline
```json
{
  "session_id": "xxx",
  "container_id": "MSCU5165756",
  "debug": true
}
```

### Get Appointments (3 Modes)
```json
// Mode 1: Infinite
{"session_id": "xxx", "infinite_scrolling": true}

// Mode 2: Count
{"session_id": "xxx", "target_count": 50}

// Mode 3: Target ID
{"session_id": "xxx", "target_appointment_id": "APPT123"}
```

### Check Appointments
```json
{
  "session_id": "xxx",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  "truck_plate": "ABC123",
  "own_chassis": false
}
```

## ✅ Success Responses

### Session Created
```json
{
  "success": true,
  "session_id": "session_1696789012_123",
  "is_new": true,
  "username": "jfernandez"
}
```

### Containers Retrieved
```json
{
  "success": true,
  "file_url": "http://server:5010/files/containers.xlsx",
  "containers_count": 459,
  "session_id": "session_xxx",
  "is_new_session": false
}
```

### Timeline Retrieved
```json
{
  "success": true,
  "container_id": "MSCU5165756",
  "pregate_passed": true,
  "pregate_screenshot": "http://server:5010/files/pregate.png",
  "session_id": "session_xxx"
}
```

### Appointments Available
```json
{
  "success": true,
  "available_times": [
    "10/07/2025 08:00 AM",
    "10/07/2025 09:00 AM"
  ],
  "count": 2,
  "dropdown_screenshot_url": "http://server:5010/files/dropdown.png",
  "session_id": "session_xxx"
}
```

## ❌ Error Responses

### Authentication Failed
```json
{
  "success": false,
  "error": "Authentication failed",
  "details": "INVALID_CREDENTIALS"
}
```

### Session Not Found
```json
{
  "success": false,
  "error": "Session not found or expired",
  "session_id": "session_invalid"
}
```

### Container Not Found
```json
{
  "success": false,
  "error": "Container not found after scrolling",
  "container_id": "INVALID123"
}
```

## 🔄 Session Management

### Persistent Sessions
- **Max Capacity**: 10 concurrent windows
- **Lifetime**: Keep-alive (refreshed every 5 min)
- **Identification**: By credentials hash
- **Eviction**: LRU (Least Recently Used)

### Using Sessions
```bash
# 1. Create session
curl -X POST http://localhost:5010/get_session -d '{...}'
# Returns: session_id

# 2. Use session in subsequent requests
curl -X POST http://localhost:5010/get_containers \
  -d '{"session_id": "session_xxx", "target_count": 50}'
```

## 🐛 Debug Mode

Add `"debug": true` to any request:
```json
{
  "session_id": "xxx",
  "debug": true
}
```

Returns additional field:
```json
{
  "debug_bundle_url": "http://server:5010/files/debug.zip"
}
```

Bundle contains:
- Screenshots at each step
- HTML source
- Console logs
- Error details

## 🧪 Quick Tests

### Health Check
```bash
curl http://localhost:5010/health
```

### Create Session
```bash
curl -X POST http://localhost:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{"username":"jfernandez","password":"taffie","captcha_api_key":"7bf85bb6f37c9799543a2a463aab2b4f"}'
```

### Get 10 Containers
```bash
curl -X POST http://localhost:5010/get_containers \
  -H "Content-Type: application/json" \
  -d '{"session_id":"SESSION_ID_HERE","target_count":10}'
```

## 📊 Common Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No* | Use existing session |
| `username` | string | No* | E-Modal username |
| `password` | string | No* | E-Modal password |
| `captcha_api_key` | string | No* | 2captcha API key |
| `debug` | boolean | No | Enable debug mode |

*Either `session_id` OR credentials required

## ⚙️ Configuration

### Timeouts
```python
NAVIGATION = 45s      # Page load wait
SCROLL_WAIT = 0.7s    # Between scrolls
PHASE_WAIT = 5s       # Between appointment phases
STEPPER_WAIT = 15s    # For stepper update
SESSION_TTL = 10min   # Appointment sessions
```

### Limits
```python
MAX_SESSIONS = 10              # Concurrent windows
REFRESH_INTERVAL = 300s        # Session refresh
NO_NEW_CONTENT_MAX = 6         # Scroll cycles
CLEANUP_AGE = 24h              # File cleanup
```

## 📂 File Locations

```
downloads/          # Excel exports
screenshots/        # Debug screenshots
proxy_extension/    # Proxy auth files
logs/              # Application logs
```

## 🚨 Important Notes

1. **Session Reuse**: Always prefer reusing `session_id` to avoid login overhead
2. **Debug Mode**: Use sparingly in production (creates large files)
3. **Make Appointment**: ⚠️ Actually submits - use carefully!
4. **Proxy**: Automatically configured (dc.oxylabs.io:8001)
5. **Cleanup**: Automatic every 24h, manual via `/cleanup` endpoint

## 🔗 Related Docs

- **Full API Docs**: `API_DOCUMENTATION.md`
- **Proxy Setup**: `PROXY_AUTHENTICATION.md`
- **Session Management**: `PERSISTENT_SESSIONS_ALL_ENDPOINTS.md`
- **Testing Guide**: `TEST_ALL_ENDPOINTS.md`

---

**Quick Start**: `python test_all_endpoints.py`  
**Version**: 1.0  
**Last Updated**: 2025-10-06

