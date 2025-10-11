# Test All Endpoints - Comprehensive Testing Guide

## Overview
`test_all_endpoints.py` is a comprehensive test script that validates all E-Modal Business API endpoints in both session creation and session reuse modes.

---

## 🎯 **What It Tests**

### **Endpoints Covered**
1. ✅ `/get_session` - Create persistent session
2. ✅ `/get_containers` - Extract container data
3. ✅ `/get_container_timeline` - Get Pregate status
4. ✅ `/check_appointments` - Check available appointment times
5. ℹ️ `/make_appointment` - Preview only (no actual submission)

### **Test Modes**
- **MODE 1**: Create session explicitly → Use `session_id` in all requests
- **MODE 2**: Use credentials → System auto-reuses existing sessions

---

## 🚀 **Quick Start**

### **Run All Tests**
```bash
python test_all_endpoints.py
```

**Follow prompts:**
1. Choose server (local/remote)
2. Choose test mode (1, 2, 3, or 4)
3. Press Enter to proceed through each test
4. Review results

---

## 📋 **Test Modes Explained**

### **Mode 1: Create Session + Use Session ID**
```
1. Create session via /get_session
2. Test /get_containers with session_id
3. Test /get_container_timeline with session_id
4. Test /check_appointments with session_id (optional)
5. Preview /make_appointment
6. Final health check
```

**Expected Results:**
- ✅ All endpoints return `is_new_session: false`
- ✅ Same `session_id` used throughout
- ⚡ Fast operations (no repeated logins)

---

### **Mode 2: Use Credentials (Auto-Reuse)**
```
1. Test /get_containers with credentials
2. Test /get_container_timeline with credentials
3. Test /check_appointments with credentials (optional)
4. Final health check
```

**Expected Results (if MODE 1 ran first):**
- ✅ All endpoints return `is_new_session: false`
- ✅ System automatically finds and reuses existing session
- ⚡ Fast operations (credential-based session matching)

**Expected Results (if MODE 1 did NOT run):**
- ℹ️ First request creates new session (`is_new_session: true`)
- ✅ Subsequent requests reuse that session (`is_new_session: false`)

---

### **Mode 3: Both Modes Sequentially**
- Runs MODE 1, then MODE 2
- Best for comprehensive testing
- Validates both explicit and automatic session reuse

---

### **Mode 4: Quick Test**
- MODE 1 only, skips appointments
- Fast validation (~30 seconds)
- Perfect for smoke testing

---

## 📊 **Sample Output**

### **MODE 1 - Create Session**
```
======================================================================
 MODE 1: Create Session + Test All Endpoints
======================================================================

======================================================================
 Health Check
======================================================================
✅ API is healthy
   Status: healthy
   Session Capacity: 1/10

⏸️  Press Enter to create session...

======================================================================
 Test 1: /get_session - Create Persistent Session
======================================================================

📤 Testing: Create new persistent session
   Endpoint: /get_session
   ⏱️  Response time: 18.45s
   ✅ Success!

📋 Session Created:
   Session ID: session_1759683996_249140832508791461
   Is New: true
   Username: jfernandez
   Time: 18.45s

⏸️  Press Enter to test /get_containers with session...

======================================================================
 Test 2a: /get_containers - Using Existing Session (Mode: count)
======================================================================

📤 Testing: Get containers using session (mode: count)
   Endpoint: /get_containers
   ⏱️  Response time: 8.32s
   ✅ Success!

📊 Results:
   Session ID: session_1759683996_249140832508791461
   Is New Session: false  ← Session reused!
   File URL: /files/containers_20251005_190234.xlsx
   Container Count: 50
   Time: 8.32s
   ✅ SUCCESS: Session was reused!

⏸️  Press Enter to test /get_container_timeline with session...

======================================================================
 Test 3a: /get_container_timeline - Using Existing Session
======================================================================

📤 Testing: Get timeline for MSDU5772413L
   Endpoint: /get_container_timeline
   ⏱️  Response time: 5.67s
   ✅ Success!

📊 Results:
   Session ID: session_1759683996_249140832508791461
   Is New Session: false  ← Session reused!
   Container ID: MSDU5772413L
   Passed Pregate: true
   Detection Method: dom_check
   Time: 5.67s
   ✅ SUCCESS: Session was reused!
```

---

### **MODE 2 - Use Credentials**
```
======================================================================
 MODE 2: Use Credentials (Auto Session Reuse)
======================================================================

This mode tests credential-based session reuse.
If you ran MODE 1 first, the system should automatically reuse that session!

⏸️  Press Enter to test /get_containers with credentials...

======================================================================
 Test 2b: /get_containers - Using Credentials (Should Reuse Session)
======================================================================

📤 Testing: Get containers using credentials
   Endpoint: /get_containers
   ⏱️  Response time: 2.89s  ← Very fast! No login!
   ✅ Success!

📊 Results:
   Session ID: session_1759683996_249140832508791461  ← Same session!
   Is New Session: false  ← Reused!
   File URL: /files/containers_20251005_190245.xlsx
   Container Count: 20
   Time: 2.89s
   ✅ SUCCESS: Existing session was reused (credential match)!
```

---

## 🎛️ **Configuration**

### **Edit Test Data**
Open `test_all_endpoints.py` and modify:

```python
# Default credentials
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"

# Test data
TEST_CONTAINER_ID = "MSDU5772413L"
TEST_TRUCKING_COMPANY = "FENIX MARINE SERVICES LTD"
TEST_TERMINAL = "ITS Long Beach"
TEST_MOVE_TYPE = "DROP EMPTY"
TEST_TRUCK_PLATE = "1234567"
TEST_OWN_CHASSIS = False
```

---

## 🔍 **What to Look For**

### **✅ Success Indicators**
1. **Session Reuse**:
   - `is_new_session: false` in MODE 1 (after first request)
   - `is_new_session: false` in MODE 2 (if MODE 1 ran first)
   - Same `session_id` across multiple requests

2. **Performance**:
   - First request (with login): ~15-20 seconds
   - Subsequent requests (session reuse): ~2-10 seconds
   - Much faster when skipping authentication

3. **Credential Matching**:
   - MODE 2 automatically finds existing session
   - No new browser window opened
   - Instant operation start

### **⚠️ Warning Signs**
1. **New Sessions Created**:
   - If `is_new_session: true` on every request → Session not being reused
   - Check health check output for session count

2. **Slow Performance**:
   - If every request takes 15-20 seconds → Not reusing sessions
   - Indicates new login each time

3. **Different Session IDs**:
   - If `session_id` changes between requests → Sessions not persisting
   - Check API logs for session cleanup

---

## 🧪 **Test Scenarios**

### **Scenario 1: Fresh Start**
```bash
# Start with clean state
python test_all_endpoints.py
# Choose Mode 3 (both modes)
```

**Expected:**
- MODE 1: Creates new session, reuses for all subsequent requests
- MODE 2: Finds MODE 1's session, reuses it (very fast)

---

### **Scenario 2: Session Already Exists**
```bash
# Run MODE 1 first
python test_all_endpoints.py  # Choose Mode 1

# Then run MODE 2 in separate terminal
python test_all_endpoints.py  # Choose Mode 2
```

**Expected:**
- MODE 2 finds existing session immediately
- All requests very fast (2-5 seconds)

---

### **Scenario 3: Different Users**
```bash
# Terminal 1: User 1
python test_session_workflow.py  # jfernandez

# Terminal 2: User 2 (different credentials)
python test_session_workflow_user2.py  # Gustavoa
```

**Expected:**
- Each user gets their own session
- Sessions don't interfere with each other
- Health check shows 2 active sessions

---

### **Scenario 4: LRU Eviction**
```bash
# Run 10+ different users to trigger LRU eviction
# Session capacity will show 10/10
# Oldest session gets evicted for new one
```

---

## 📝 **Optional Tests**

### **Skip Appointments**
Appointment tests take ~60 seconds each. When prompted:
```
⏸️  Test /check_appointments with session? (takes ~60s) [y/N]:
```
- Press `N` (or just Enter) to skip
- Press `y` to run the test

### **Make Appointment Preview**
The script shows a preview of how `/make_appointment` works but does NOT actually submit appointments (to prevent accidental bookings).

To test `/make_appointment` manually:
```python
payload = {
    "session_id": "session_XXX",
    "trucking_company": "...",
    "terminal": "...",
    "move_type": "...",
    "container_id": "...",
    "truck_plate": "...",
    "own_chassis": false,
    "appointment_time": "2025-10-10 08:00"  # Use actual available time
}
requests.post(f"{API_BASE_URL}/make_appointment", json=payload)
```

---

## 🐛 **Troubleshooting**

### **Issue: "Session not reused"**
**Symptoms**: `is_new_session: true` on every request

**Solutions:**
1. Check health endpoint for active sessions
2. Verify credentials are identical
3. Check API logs for session cleanup
4. Ensure 10-window limit not exceeded

---

### **Issue: "Timeout errors"**
**Symptoms**: Request timeout after 300 seconds

**Solutions:**
1. Check API server is running
2. Verify network connectivity
3. Check API logs for errors
4. Try local server instead of remote

---

### **Issue: "Health check failed"**
**Symptoms**: Cannot connect to API

**Solutions:**
1. Verify correct URL selected
2. Check API server is running
3. Test with `curl http://localhost:5000/health`
4. Check firewall settings

---

## 📊 **Interpreting Results**

### **Performance Metrics**

| Operation | First Request (Login) | Session Reuse |
|-----------|----------------------|---------------|
| `/get_session` | ~15-20s | N/A |
| `/get_containers` (50) | ~20-25s | ~5-10s |
| `/get_timeline` | ~18-23s | ~3-8s |
| `/check_appointments` | ~50-70s | ~40-60s |

**Speedup**: 2-3x faster with session reuse!

---

### **Health Check Metrics**

```json
{
  "sessions": {
    "active_count": 3,
    "session_capacity": "3/10"
  },
  "persistent_sessions": 2
}
```

- **active_count**: Total browser windows open
- **session_capacity**: Current/Maximum (10 limit)
- **persistent_sessions**: Sessions with `keep_alive: true`

---

## ✅ **Success Criteria**

Test is successful if:
1. ✅ MODE 1 creates session, all subsequent requests reuse it
2. ✅ MODE 2 finds existing session (if MODE 1 ran)
3. ✅ Same `session_id` across all requests in same mode
4. ✅ `is_new_session: false` after first request
5. ✅ Performance improvement (2-3x faster with session reuse)
6. ✅ Health check shows correct session count
7. ✅ All endpoints return success (200)

---

## 📖 **Related Documentation**

- `PERSISTENT_SESSIONS_ALL_ENDPOINTS.md` - Detailed endpoint documentation
- `LRU_SESSION_MANAGEMENT.md` - LRU eviction details
- `TEST_SESSION_WORKFLOW.md` - Single-user workflow testing
- `TEST_CONCURRENCY.md` - Multi-user concurrency testing

---

**Last Updated**: October 5, 2025  
**Script Version**: 1.0


