# E-Modal Business API - Complete Documentation

## 📋 Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Session Management](#session-management)
4. [API Endpoints](#api-endpoints)
5. [Request & Response Formats](#request--response-formats)
6. [Error Handling](#error-handling)
7. [Testing](#testing)
8. [Configuration](#configuration)

---

## Overview

**E-Modal Business API** is a Flask-based RESTful API for automating business operations on the E-Modal trucking portal.

### Key Features
✅ **Persistent Sessions**: Maximum 10 concurrent Chrome windows with LRU eviction  
✅ **Automatic Login**: reCAPTCHA solving with 2captcha integration  
✅ **Container Management**: Get, search, and filter container data  
✅ **Timeline Analysis**: Extract container timeline and milestones  
✅ **Appointment Booking**: Check and make appointments  
✅ **Proxy Support**: Residential proxy with automatic authentication  
✅ **Debug Mode**: Screenshot capture and debug bundles  

### Technology Stack
- **Backend**: Flask (Python)
- **Browser Automation**: Selenium WebDriver
- **Driver Management**: webdriver-manager
- **Proxy**: Chrome extension for automatic authentication
- **Captcha**: 2captcha API integration

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask API Server                         │
│                   (emodal_business_api.py)                   │
├─────────────────────────────────────────────────────────────┤
│  • Health Check                  • Session Management        │
│  • Container Operations          • Timeline Extraction       │
│  • Appointment Booking           • Debug Bundles             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Login Handler Layer                        │
│                (emodal_login_handler.py)                     │
├─────────────────────────────────────────────────────────────┤
│  • Chrome Driver Setup           • Proxy Configuration       │
│  • reCAPTCHA Solving             • Credential Management     │
│  • Screenshot Capture            • Error Detection           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Browser Automation                          │
│            (Chrome + Proxy Extension + Selenium)             │
├─────────────────────────────────────────────────────────────┤
│  • E-Modal Portal Navigation     • Element Interaction       │
│  • Infinite Scrolling            • Data Extraction           │
│  • File Downloads                • Form Filling              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   E-Modal Portal                             │
│         https://truckerportal.emodal.com                     │
└─────────────────────────────────────────────────────────────┘
```

### Session Management Flow

```
User Request → Check session_id
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
   session_id provided     No session_id
        ↓                       ↓
   Find in cache          Get credentials
        ↓                       ↓
   ┌────┴────┐           Check cache by
   ↓         ↓           credentials hash
Found    Not Found             ↓
   ↓         ↓           ┌─────┴─────┐
Return   Error        Found    Not Found
          ↓              ↓          ↓
       Fail         Return     Create new
                                   ↓
                            Check capacity
                                   ↓
                            ┌──────┴──────┐
                            ↓             ↓
                       At limit    Available
                            ↓             ↓
                       Evict LRU    Create session
                            ↓             ↓
                       ←─────────────────┘
                            ↓
                       Login & Return
```

---

## Session Management

### Persistent Sessions
- **Maximum Capacity**: 10 concurrent Chrome windows
- **Session Lifecycle**: Keep-alive with automatic refresh every 5 minutes
- **Identification**: By credentials hash (username + password)
- **Eviction Policy**: LRU (Least Recently Used)

### Session Creation
Sessions are created automatically by any endpoint when:
1. No `session_id` provided
2. `session_id` provided but invalid/expired
3. Credentials provided match existing session → reuse

### Session Refresh
- **Interval**: Every 5 minutes (300 seconds)
- **Method**: Navigate to containers page, verify user button exists
- **Automatic**: Background thread handles all keep-alive sessions

---

## API Endpoints

### Base URL
```
http://localhost:5010
http://89.117.63.196:5010
http://37.60.243.201:5010
```

### 1. Health Check

**GET /health**

Check if API server is running.

**Response**:
```json
{
  "status": "healthy",
  "service": "E-Modal Business Operations API",
  "active_sessions": 3,
  "max_sessions": 10,
  "session_capacity": "3/10",
  "persistent_sessions": 3,
  "timestamp": "2025-10-06T12:34:56.789"
}
```

---

### 2. Get Session

**POST /get_session**

Create a new persistent session (login only, no operations).

**Request**:
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
}
```

**Response**:
```json
{
  "success": true,
  "session_id": "session_1696789012_123456789",
  "is_new": true,
  "username": "jfernandez",
  "created_at": "2025-10-06T12:35:00.123",
  "expires_at": null
}
```

---

### 3. Get Containers

**POST /get_containers**

Retrieve container data with infinite scrolling support.

**Request (Infinite Scrolling)**:
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "infinite_scrolling": true,
  "debug": false
}
```

**Request (Target Count)**:
```json
{
  "session_id": "session_1696789012_123456789",
  "target_count": 100,
  "debug": true
}
```

**Request (Target Container ID)**:
```json
{
  "session_id": "session_1696789012_123456789",
  "target_container_id": "MSCU5165756",
  "debug": false
}
```

**Response (Success)**:
```json
{
  "success": true,
  "file_url": "http://server:5010/files/session_123_containers.xlsx",
  "containers_count": 459,
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "debug_bundle_url": "http://server:5010/files/session_123_debug.zip"
}
```

**Response (Error)**:
```json
{
  "success": false,
  "error": "Authentication failed",
  "details": "Invalid credentials"
}
```

---

### 4. Get Container Timeline

**POST /get_container_timeline**

Extract timeline data for a specific container, including Pregate milestone.

**Request**:
```json
{
  "session_id": "session_1696789012_123456789",
  "container_id": "MSCU5165756",
  "debug": true
}
```

**Response (Success)**:
```json
{
  "success": true,
  "container_id": "MSCU5165756",
  "pregate_passed": true,
  "pregate_screenshot": "http://server:5010/files/pregate_MSCU5165756.png",
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "debug_bundle_url": "http://server:5010/files/session_123_timeline_debug.zip"
}
```

---

### 5. Get Booking Number

**POST /get_booking_number**

Extract booking number for a specific container.

**Request**:
```json
{
  "session_id": "session_1696789012_123456789",
  "container_id": "MSCU5165756",
  "debug": false
}
```

**Response (Success)**:
```json
{
  "success": true,
  "container_id": "MSCU5165756",
  "booking_number": "RICFEM857500",
  "session_id": "session_1696789012_123456789",
  "is_new_session": false
}
```

**Response (Not Found)**:
```json
{
  "success": true,
  "container_id": "MSCU5165756",
  "booking_number": null,
  "session_id": "session_1696789012_123456789",
  "is_new_session": false
}
```

---

### 6. Get Appointments

**POST /get_appointments**

Navigate to appointments page, select all checkboxes, download Excel file.

**Request (Infinite Scrolling)**:
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "infinite_scrolling": true,
  "debug": true
}
```

**Request (Target Count)**:
```json
{
  "session_id": "session_1696789012_123456789",
  "target_count": 50,
  "debug": false
}
```

**Response (Success)**:
```json
{
  "success": true,
  "selected_count": 150,
  "file_url": "http://server:5010/files/session_123_appointments.xlsx",
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "debug_bundle_url": "http://server:5010/files/session_123_debug.zip"
}
```

---

### 7. Check Appointments

**POST /check_appointments**

Navigate through appointment booking phases and retrieve available times (does NOT submit).

**Request**:
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  "truck_plate": "ABC123",
  "pin_code": "1234",
  "own_chassis": false,
  "debug": true
}
```

**Response (Success)**:
```json
{
  "success": true,
  "available_times": [
    "10/07/2025 08:00 AM",
    "10/07/2025 09:00 AM",
    "10/07/2025 10:00 AM",
    "10/07/2025 11:00 AM"
  ],
  "count": 4,
  "dropdown_screenshot_url": "http://server:5010/files/appointment_dropdown.png",
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "appointment_session_id": "appt_session_123",
  "debug_bundle_url": "http://server:5010/files/appt_123_debug.zip"
}
```

**Response (Phase Error - Session Continues)**:
```json
{
  "success": false,
  "error": "Invalid trucking company selection",
  "current_phase": 1,
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "appointment_session_id": "appt_session_123",
  "expires_in_seconds": 600
}
```

---

### 8. Make Appointment

**POST /make_appointment**

Navigate through appointment booking phases and SUBMIT an appointment.

⚠️ **WARNING**: This endpoint ACTUALLY SUBMITS appointments!

**Request**:
```json
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f",
  "trucking_company": "TEST TRUCKING",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "CAIU7181746",
  "truck_plate": "ABC123",
  "own_chassis": false,
  "appointment_time": "10/07/2025 08:00 AM",
  "debug": true
}
```

**Response (Success)**:
```json
{
  "success": true,
  "message": "Appointment submitted successfully",
  "appointment_details": {
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "truck_plate": "ABC123",
    "appointment_time": "10/07/2025 08:00 AM"
  },
  "session_id": "session_1696789012_123456789",
  "is_new_session": false,
  "debug_bundle_url": "http://server:5010/files/appt_123_debug.zip"
}
```

---

### 9. Manual Cleanup

**POST /cleanup**

Manually delete files older than 24 hours from downloads and screenshots folders.

**Request**: No body required

**Response**:
```json
{
  "success": true,
  "message": "Cleanup completed successfully",
  "files_deleted": 45,
  "space_freed_mb": 120.5
}
```

---

## Request & Response Formats

### Common Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No* | Existing session ID (skip login) |
| `username` | string | No* | E-Modal username |
| `password` | string | No* | E-Modal password |
| `captcha_api_key` | string | No* | 2captcha API key |
| `debug` | boolean | No | Enable debug mode (screenshots & bundles) |

*Either `session_id` OR credentials (`username`, `password`, `captcha_api_key`) must be provided.

### Common Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `session_id` | string | Browser session ID |
| `is_new_session` | boolean | Whether session was newly created |
| `error` | string | Error message (if failed) |
| `debug_bundle_url` | string | URL to debug ZIP (if debug=true) |

### Get Containers - Specific Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `infinite_scrolling` | boolean | Scroll until no new content (default: false) |
| `target_count` | integer | Stop after reaching N containers |
| `target_container_id` | string | Stop after finding specific container |

### Get Timeline - Specific Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `container_id` | string | Container ID to extract timeline for |

### Check/Make Appointment - Specific Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `trucking_company` | string | Yes | Trucking company name |
| `terminal` | string | Yes | Terminal name |
| `move_type` | string | Yes | Move type (e.g., "DROP EMPTY") |
| `container_id` | string | Yes | Container number |
| `truck_plate` | string | Yes | Truck license plate |
| `pin_code` | string | No | PIN code (optional) |
| `own_chassis` | boolean | Yes | Whether using own chassis |
| `appointment_time` | string | Yes* | Appointment time (make_appointment only) |

*Required only for `/make_appointment`

### Response HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid request format or missing parameters |
| 401 | Unauthorized | Authentication failed |
| 404 | Not Found | Container/resource not found |
| 500 | Server Error | Internal server error or operation failed |

---

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "Error message description",
  "details": "Additional error details",
  "session_id": "session_123 (if applicable)",
  "current_phase": 2 (for appointment errors)
}
```

### Common Error Types

#### 1. Authentication Errors
```json
{
  "success": false,
  "error": "Authentication failed",
  "details": "INVALID_CREDENTIALS"
}
```

#### 2. Session Errors
```json
{
  "success": false,
  "error": "Session not found or expired",
  "session_id": "session_invalid_123"
}
```

#### 3. Container Not Found
```json
{
  "success": false,
  "error": "Container not found after scrolling",
  "container_id": "INVALID123"
}
```

#### 4. Appointment Phase Errors
```json
{
  "success": false,
  "error": "Invalid trucking company selection",
  "current_phase": 1,
  "session_id": "session_123",
  "appointment_session_id": "appt_123",
  "expires_in_seconds": 600
}
```

### Error Recovery

**For Appointment Errors**:
- Browser session remains open for 10 minutes
- Use returned `session_id` and `appointment_session_id` to continue
- Fix the invalid field and retry

**For Container Errors**:
- Session remains alive (persistent)
- Retry with corrected parameters
- Check debug bundle for screenshots

---

## Testing

### Test Scripts

| Script | Purpose |
|--------|---------|
| `test_all_endpoints.py` | Test all endpoints in session/credentials modes |
| `test_get_appointments.py` | Test appointments endpoint with 3 modes |
| `test_new_endpoints.py` | Test booking_number and appointments |
| `test_session_workflow.py` | Test persistent session workflow |
| `test_appointments.py` | Test check/make appointments |
| `test_proxy_extension.py` | Verify proxy extension creation |

### Running Tests

```bash
# Test all endpoints
python test_all_endpoints.py

# Test appointments
python test_get_appointments.py

# Test session workflow
python test_session_workflow.py

# Quick health check
curl http://localhost:5010/health
```

### Test Credentials

```python
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"
```

### Test Container IDs

```python
CONTAINER_ID_1 = "MSCU5165756"  # For timeline/booking tests
CONTAINER_ID_2 = "CAIU7181746"  # For appointment tests
```

---

## Configuration

### Environment Variables

```bash
# Server
FLASK_PORT=5010
FLASK_HOST=0.0.0.0

# Proxy
PROXY_HOST=dc.oxylabs.io
PROXY_PORT=8001
PROXY_USERNAME=mo3li_moQef
PROXY_PASSWORD=MMMM_15718_mmmm

# Session
MAX_CONCURRENT_SESSIONS=10
SESSION_REFRESH_INTERVAL=300

# Cleanup
AUTO_CLEANUP_HOURS=24
```

### Directories

```
emodal/
├── downloads/          # Excel files and exports
├── screenshots/        # Debug screenshots
├── proxy_extension/    # Proxy extension files
└── logs/              # Application logs
```

### Timeouts

```python
# Navigation
NAVIGATION_TIMEOUT = 45  # seconds

# Scrolling
SCROLL_WAIT = 0.7       # seconds between scrolls
NO_NEW_CONTENT_MAX = 6  # cycles before stopping

# Appointments
PHASE_WAIT = 5          # seconds between phases
STEPPER_WAIT = 15       # seconds for stepper update

# Session
APPOINTMENT_SESSION_TTL = 600  # 10 minutes
```

---

## Quick Reference

### Create Session
```bash
curl -X POST http://localhost:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
  }'
```

### Get Containers (Infinite)
```bash
curl -X POST http://localhost:5010/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "infinite_scrolling": true,
    "debug": false
  }'
```

### Check Appointments
```bash
curl -X POST http://localhost:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "truck_plate": "ABC123",
    "own_chassis": false
  }'
```

---

## Support & Documentation

- **API Documentation**: `API_DOCUMENTATION.md` (this file)
- **Proxy Setup**: `PROXY_AUTHENTICATION.md`
- **Session Management**: `PERSISTENT_SESSIONS_ALL_ENDPOINTS.md`
- **LRU Eviction**: `LRU_SESSION_MANAGEMENT.md`
- **Test Guide**: `TEST_ALL_ENDPOINTS.md`

---

**Version**: 1.0  
**Last Updated**: 2025-10-06  
**Author**: E-Modal API Development Team


