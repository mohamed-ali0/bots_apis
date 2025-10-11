# Test Scripts for /get_booking_number Endpoint

## 📋 Overview

This guide covers three test scripts for the `/get_booking_number` endpoint:

1. **`test_get_booking_number.py`** - Comprehensive test suite
2. **`test_booking_simple.py`** - Quick single test
3. **`test_booking_workflow.py`** - Session workflow demonstration

---

## 🧪 Test Scripts

### 1. Comprehensive Test (`test_get_booking_number.py`)

**Purpose**: Full test suite with multiple scenarios and error handling

**Features**:
- ✅ Server health check
- ✅ Session creation and reuse
- ✅ Multiple container testing
- ✅ Debug mode testing
- ✅ Error case testing
- ✅ Interactive server selection
- ✅ Custom container testing

**Usage**:
```bash
python test_get_booking_number.py
```

**Test Modes**:
1. **Quick test** - Single container test
2. **Comprehensive test** - All containers + error cases
3. **Custom container test** - Test specific container ID

**Example Output**:
```
🎯 GET_BOOKING_NUMBER ENDPOINT TEST SCRIPT
==================================================

🌐 Choose Server:
1. Local server (http://localhost:5010)
2. Remote server 1 (http://89.117.63.196:5010)
3. Remote server 2 (http://37.60.243.201:5010) [DEFAULT]
4. Custom server

Enter choice (1-4) [3]: 

👤 Enter credentials:
Username [jfernandez]: 
Password [taffie]: 
Captcha API Key [7bf85bb6f37c9799543a2a463aab2b4f]: 

🧪 Choose test mode:
1. Quick test (single container)
2. Comprehensive test (all containers + error cases)
3. Custom container test

Enter choice (1-3) [1]: 2

🏥 Testing server health: http://37.60.243.201:5010
✅ Server is healthy
   📊 Active sessions: 2/10
   🔄 Persistent sessions: 2

🔐 Creating session for user: jfernandez
✅ Session created successfully
   🆔 Session ID: session_1696612345_123456789
   🆕 New session: True
   👤 Username: jfernandez

📋 Testing get_booking_number with session
   🆔 Session: session_1696612345_123456789
   📦 Container: MSCU5165756
   🐛 Debug mode: True
   ⏱️  Response time: 15.23 seconds
✅ Booking number extraction successful
   📦 Container ID: MSCU5165756
   🎫 Booking Number: RICFEM857500
   🆔 Session ID: session_1696612345_123456789
   🆕 New session: False
   🐛 Debug bundle: http://37.60.243.201:5010/files/session_XXX_debug.zip
```

### 2. Simple Test (`test_booking_simple.py`)

**Purpose**: Quick single test with minimal setup

**Features**:
- ✅ Pre-configured settings
- ✅ Single container test
- ✅ Debug mode enabled
- ✅ Simple output

**Usage**:
```bash
python test_booking_simple.py
```

**Configuration** (edit script to change):
```python
SERVER_URL = "http://37.60.243.201:5010"
USERNAME = "jfernandez"
PASSWORD = "taffie"
CAPTCHA_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"
CONTAINER_ID = "MSCU5165756"
```

**Example Output**:
```
🚀 GET_BOOKING_NUMBER SIMPLE TEST
========================================
🎯 Testing /get_booking_number endpoint
🌐 Server: http://37.60.243.201:5010
📦 Container: MSCU5165756

📤 Sending request...
📥 Response received:
   Status: 200
   Content-Type: application/json

✅ SUCCESS!
   📦 Container ID: MSCU5165756
   🎫 Booking Number: RICFEM857500
   🆔 Session ID: session_1696612345_123456789
   🆕 New session: True
   🐛 Debug bundle: http://37.60.243.201:5010/files/session_XXX_debug.zip

🎉 Test completed successfully!
```

### 3. Workflow Test (`test_booking_workflow.py`)

**Purpose**: Demonstrates session creation, reuse, and multiple container testing

**Features**:
- ✅ Session creation
- ✅ Multiple container testing
- ✅ Session reuse demonstration
- ✅ Credentials bypass test
- ✅ Performance timing

**Usage**:
```bash
python test_booking_workflow.py
```

**Test Flow**:
1. **Create Session** - Get persistent session
2. **Test Multiple Containers** - Use session for multiple requests
3. **Test Session Reuse** - Reuse same session
4. **Test with Credentials** - Bypass session with credentials

**Example Output**:
```
🎯 GET_BOOKING_NUMBER WORKFLOW TEST
==================================================
🌐 Server: http://37.60.243.201:5010
👤 Username: jfernandez
📦 Containers: MSCU5165756, TRHU1866154, MSDU5772413

==============================
STEP 1: Create Session
==============================
🔐 Creating session...
✅ Session created: session_1696612345_123456789

==============================
STEP 2: Test Multiple Containers
==============================

--- Container 1/3: MSCU5165756 ---
📋 Getting booking number for: MSCU5165756
   ⏱️  Response time: 12.45s
   ✅ Success!
   🎫 Booking Number: RICFEM857500
   🐛 Debug bundle: http://37.60.243.201:5010/files/session_XXX_debug.zip

--- Container 2/3: TRHU1866154 ---
📋 Getting booking number for: TRHU1866154
   ⏱️  Response time: 8.23s
   ✅ Success!
   🎫 Booking Number: Not found

--- Container 3/3: MSDU5772413 ---
📋 Getting booking number for: MSDU5772413
   ⏱️  Response time: 7.89s
   ✅ Success!
   🎫 Booking Number: Not found

==============================
STEP 3: Test Session Reuse
==============================
🔄 Reusing same session for another container...
📋 Getting booking number for: MSCU5165756
   ⏱️  Response time: 6.12s
   ✅ Success!
   🎫 Booking Number: RICFEM857500

==============================
STEP 4: Test with Credentials (New Session)
==============================
🔐 Testing with credentials (bypasses session)...
✅ Success with credentials!
   🆔 New session: session_1696612456_987654321
   🎫 Booking Number: RICFEM857500

==================================================
📊 WORKFLOW TEST SUMMARY
==================================================
✅ Successful operations: 5
📦 Total containers tested: 4
🕐 Completed at: 2025-10-06 15:45:30
🎉 Overall result: PASSED
```

---

## 🔧 Configuration

### Server URLs
- **Local**: `http://localhost:5010`
- **Remote 1**: `http://89.117.63.196:5010`
- **Remote 2**: `http://37.60.243.201:5010` (Default)

### Test Containers
- `MSCU5165756` - Primary test container (has booking number)
- `TRHU1866154` - Secondary test container
- `MSDU5772413` - Additional test container
- `INVALID123` - Invalid container for error testing

### Default Credentials
- **Username**: `jfernandez`
- **Password**: `taffie`
- **Captcha Key**: `7bf85bb6f37c9799543a2a463aab2b4f`

---

## 📊 Expected Results

### Successful Response
```json
{
  "success": true,
  "container_id": "MSCU5165756",
  "booking_number": "RICFEM857500",
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "debug_bundle_url": "http://37.60.243.201:5010/files/session_XXX_debug.zip"
}
```

### No Booking Number Found
```json
{
  "success": true,
  "container_id": "TRHU1866154",
  "booking_number": null,
  "session_id": "session_1696612345_123456789",
  "is_new_session": false,
  "debug_bundle_url": null
}
```

### Error Response
```json
{
  "success": false,
  "error": "Container not found",
  "session_id": "session_1696612345_123456789",
  "is_new_session": false
}
```

---

## 🚨 Troubleshooting

### Common Issues

**1. Server Connection Failed**
```
❌ Server health check error: Connection refused
```
- Check if API server is running
- Verify server URL is correct
- Check network connectivity

**2. Authentication Failed**
```
❌ Session creation failed: Authentication failed
```
- Verify credentials are correct
- Check captcha API key is valid
- Ensure account is not locked

**3. Container Not Found**
```
❌ Booking number extraction failed: Container not found
```
- Verify container ID exists in the system
- Check if container is accessible to the user
- Try with a different container ID

**4. Timeout Error**
```
❌ Request error: Read timeout
```
- Increase timeout value in script
- Check server performance
- Try again during off-peak hours

### Debug Mode

Enable debug mode to get detailed information:
```python
"debug": True
```

This provides:
- Screenshots of each step
- Debug bundle with all files
- Detailed error information

---

## 📝 Customization

### Change Test Container
Edit the `CONTAINER_ID` variable in the simple test:
```python
CONTAINER_ID = "YOUR_CONTAINER_ID"
```

### Add More Test Containers
Edit the `CONTAINERS` list in workflow test:
```python
CONTAINERS = [
    "MSCU5165756",
    "TRHU1866154", 
    "MSDU5772413",
    "YOUR_CONTAINER_1",
    "YOUR_CONTAINER_2"
]
```

### Change Server
Edit the `SERVER_URL` variable:
```python
SERVER_URL = "http://your-server:5010"
```

### Change Credentials
Edit the credential variables:
```python
USERNAME = "your_username"
PASSWORD = "your_password"
CAPTCHA_KEY = "your_captcha_key"
```

---

## 🎯 Quick Start

**For immediate testing:**
```bash
python test_booking_simple.py
```

**For comprehensive testing:**
```bash
python test_get_booking_number.py
```

**For workflow demonstration:**
```bash
python test_booking_workflow.py
```

All scripts are ready to run with default configurations! 🚀
