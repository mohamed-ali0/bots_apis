# Persistent Sessions - All Endpoints Updated

## Overview
All E-Modal Business API endpoints now support persistent browser sessions with automatic session management and reuse.

---

## 🎯 **Key Features**

### **1. Universal Session Support**
- All endpoints accept optional `session_id` parameter
- Automatically creates persistent sessions if no `session_id` provided
- Sessions are reused for the same credentials
- Maximum 10 concurrent browser windows with LRU eviction

### **2. Updated Endpoints**

#### ✅ `/get_session`
- **Purpose**: Create a persistent browser session without performing any operation
- **Input**: `username`, `password`, `captcha_api_key`
- **Output**: `session_id`, `is_new`, `username`, `created_at`, `expires_at: null`

#### ✅ `/get_containers`
- **Purpose**: Extract container data with infinite scrolling
- **Input (Option A)**: `session_id` (skip login)
- **Input (Option B)**: `username`, `password`, `captcha_api_key` (auto-create session)
- **Output**: `session_id`, `is_new_session`, `file_url`, container data

#### ✅ `/get_container_timeline`
- **Purpose**: Get Pregate status and timeline screenshot
- **Input (Option A)**: `session_id` + `container_id`
- **Input (Option B)**: `username`, `password`, `captcha_api_key` + `container_id`
- **Output**: `session_id`, `is_new_session`, `passed_pregate`, `detection_method`

#### ✅ `/check_appointments`
- **Purpose**: Check available appointment times (3-phase workflow)
- **Input (Option A)**: `session_id` + phase-specific fields
- **Input (Option B)**: `username`, `password`, `captcha_api_key` + phase fields
- **Special**: Uses `appointment_session_id` for workflow tracking (separate from browser `session_id`)
- **Output**: `session_id`, `is_new_session`, `appointment_session_id`, `available_times`

#### ✅ `/make_appointment`
- **Purpose**: Submit appointment booking (3-phase workflow + submit)
- **Input (Option A)**: `session_id` + all phase fields
- **Input (Option B)**: `username`, `password`, `captcha_api_key` + all phase fields
- **Output**: `session_id`, `is_new_session`, `appointment_confirmed`, `debug_bundle_url`

---

## 📋 **Usage Patterns**

### **Pattern 1: Single Request (Auto-Session)**
```json
POST /get_containers
{
  "username": "myuser",
  "password": "mypass",
  "captcha_api_key": "abc123",
  "infinite_scrolling": true
}
```
**Response:**
```json
{
  "success": true,
  "session_id": "session_1234567890_XXX",
  "is_new_session": true,
  "file_url": "/files/containers.xlsx"
}
```

---

### **Pattern 2: Explicit Session Creation**
```json
POST /get_session
{
  "username": "myuser",
  "password": "mypass",
  "captcha_api_key": "abc123"
}
```
**Response:**
```json
{
  "success": true,
  "session_id": "session_1234567890_XXX",
  "is_new": true,
  "username": "myuser"
}
```

**Then use in subsequent requests:**
```json
POST /get_containers
{
  "session_id": "session_1234567890_XXX",
  "infinite_scrolling": true
}
```
**Response:**
```json
{
  "success": true,
  "session_id": "session_1234567890_XXX",
  "is_new_session": false,  ← Session reused!
  "file_url": "/files/containers.xlsx"
}
```

---

### **Pattern 3: Credential-Based Session Reuse**
First user makes a request:
```json
POST /get_containers
{
  "username": "myuser",
  "password": "mypass",
  "captcha_api_key": "abc123",
  "infinite_scrolling": true
}
```
**Response:**
```json
{
  "session_id": "session_1234567890_XXX",
  "is_new_session": true
}
```

Later, the **same user** makes another request (without session_id):
```json
POST /get_container_timeline
{
  "username": "myuser",
  "password": "mypass",
  "captcha_api_key": "abc123",
  "container_id": "MSDU1234567"
}
```
**Response:**
```json
{
  "session_id": "session_1234567890_XXX",  ← Same session!
  "is_new_session": false,  ← Reused!
  "passed_pregate": true
}
```

---

### **Pattern 4: Appointment Workflow (Multi-Phase)**

**Note**: Appointments use TWO session types:
- **`session_id`**: Persistent browser session (reusable across operations)
- **`appointment_session_id`**: Workflow tracking session (temporary, for error recovery)

#### Initial Request:
```json
POST /check_appointments
{
  "username": "myuser",
  "password": "mypass",
  "captcha_api_key": "abc123",
  "trucking_company": "ABC Trucking",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "container_id": "MSDU1234567",
  "truck_plate": "ABC123",
  "own_chassis": false
}
```

#### Success Response:
```json
{
  "success": true,
  "session_id": "session_1234567890_XXX",
  "is_new_session": true,
  "appointment_session_id": "appt_session_1234567890_XXX",
  "available_times": ["2025-10-10 08:00", "2025-10-10 09:00"],
  "debug_bundle_url": "/files/check_appointments.zip"
}
```

#### Error Response (Missing Field):
```json
{
  "success": false,
  "error": "Missing required field for Phase 2: truck_plate",
  "session_id": "session_1234567890_XXX",
  "is_new_session": false,
  "appointment_session_id": "appt_session_1234567890_XXX",
  "current_phase": 2,
  "message": "Please provide truck_plate and retry with appointment_session_id"
}
```

#### Retry with Appointment Session:
```json
POST /check_appointments
{
  "appointment_session_id": "appt_session_1234567890_XXX",
  "truck_plate": "XYZ789"
}
```

---

## 🔄 **Session Lifecycle**

### **Creation**
1. **Explicit**: Call `/get_session` with credentials
2. **Implicit**: Call any endpoint without `session_id`
3. **Credential Match**: System finds existing session for same credentials

### **Reuse**
- Pass `session_id` to any endpoint
- System skips login, uses existing browser window
- Much faster (no authentication delay)

### **Refresh**
- Background thread refreshes all `keep_alive` sessions every 5 minutes
- Navigates to containers page to verify authentication
- Removes sessions that have been logged out

### **Eviction**
- Maximum 10 concurrent browser windows
- LRU (Least Recently Used) algorithm
- When limit reached, oldest session is terminated
- New session created for incoming request

### **Expiration**
- Appointment workflow sessions: 10 minutes (for error recovery)
- Browser sessions: Never expire (kept alive indefinitely)

---

## 🎛️ **Health Check**

```json
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "E-Modal Business Operations API",
  "sessions": {
    "active_count": 3,
    "max_sessions": 10,
    "session_capacity": "3/10"
  },
  "persistent_sessions": 2,
  "timestamp": "2025-10-05T19:00:00"
}
```

---

## 🚀 **Benefits**

### **Performance**
- ⚡ **Faster Operations**: No repeated logins (save ~15-20 seconds per request)
- 🔄 **Session Reuse**: Same browser window across multiple operations
- 📊 **Efficient**: Only 1 login per user, not per request

### **Resource Management**
- 🎯 **10-Window Limit**: Prevents resource exhaustion
- 🔄 **LRU Eviction**: Smart cleanup of unused sessions
- 🧹 **Auto-Cleanup**: Background refresh removes dead sessions

### **User Experience**
- 🔗 **Seamless**: Works with or without `session_id`
- 🎯 **Flexible**: Multiple usage patterns
- 🔁 **Reliable**: Automatic session recovery

### **Error Recovery**
- 🛡️ **Appointment Workflows**: Resume from where you left off
- 📝 **Error Details**: Clear messages with session IDs
- ⏱️ **10-Minute Window**: Time to fix and retry

---

## 📊 **Session Management Endpoints**

### **List Sessions**
```json
GET /sessions
```
**Response:**
```json
{
  "active_sessions": [
    {
      "session_id": "session_1234567890_XXX",
      "username": "user1",
      "keep_alive": true,
      "created_at": "2025-10-05T18:00:00",
      "last_used": "2025-10-05T18:30:00",
      "age_seconds": 1800
    }
  ],
  "count": 1
}
```

### **Close Session**
```json
POST /close_session
{
  "session_id": "session_1234567890_XXX"
}
```

---

## 🔧 **Implementation Details**

### **Helper Function: `get_or_create_browser_session()`**
- Centralized session management logic
- Checks for `session_id` in request
- Falls back to credential-based session lookup
- Calls `ensure_session_capacity()` before creating new sessions
- Returns `(driver, username, session_id, is_new_session)` or error

### **LRU Eviction: `evict_lru_session()`**
- Finds session with oldest `last_used` timestamp
- Closes browser window
- Removes from `active_sessions` and `persistent_sessions` dictionaries

### **Background Refresh: `periodic_session_refresh()`**
- Runs every 60 seconds in background thread
- Checks all sessions with `needs_refresh()` (older than 5 minutes)
- Calls `refresh_session()` to verify authentication
- Removes sessions that fail refresh

### **Unique Chrome Profiles**
- Each session gets a unique temporary profile directory
- Uses `tempfile.mkdtemp()` for isolation
- Prevents `--user-data-dir` conflicts
- Cleaned up on session termination

---

## ✅ **Migration Guide**

### **Old Code (Without Persistent Sessions)**
```python
response = requests.post("http://localhost:5000/get_containers", json={
    "username": "myuser",
    "password": "mypass",
    "captcha_api_key": "abc123",
    "infinite_scrolling": True
})
```

### **New Code (Explicit Session)**
```python
# Step 1: Create session once
session_response = requests.post("http://localhost:5000/get_session", json={
    "username": "myuser",
    "password": "mypass",
    "captcha_api_key": "abc123"
})
session_id = session_response.json()["session_id"]

# Step 2: Reuse session for multiple requests
for container in containers:
    response = requests.post("http://localhost:5000/get_container_timeline", json={
        "session_id": session_id,  ← Reuse!
        "container_id": container
    })
```

### **New Code (Automatic Session)**
```python
# No changes needed! Just omit session_id and the system will:
# 1. Check for existing session with same credentials
# 2. Reuse if found
# 3. Create new if not found

response = requests.post("http://localhost:5000/get_containers", json={
    "username": "myuser",
    "password": "mypass",
    "captcha_api_key": "abc123",
    "infinite_scrolling": True
})

# Later requests with same credentials automatically reuse the session!
```

---

## 🧪 **Testing**

See test scripts:
- `test_session_workflow.py` - Complete workflow test
- `test_session_workflow_user2.py` - Concurrency test (different user)
- `test_use_existing_session.py` - Explicit session reuse test

---

## 📖 **Related Documentation**

- `PERSISTENT_SESSIONS.md` - Original persistent session design
- `LRU_SESSION_MANAGEMENT.md` - LRU eviction details
- `TEST_SESSION_WORKFLOW.md` - Test script guide
- `TEST_CONCURRENCY.md` - Concurrency testing guide

---

**Last Updated**: October 5, 2025  
**API Version**: 2.0 (Persistent Sessions)


