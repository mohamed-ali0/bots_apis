# Postman Testing Guide for E-Modal Business API

This guide explains how to use the Postman collection and environment files to test the E-Modal Business API.

## 📦 Files

- `E-Modal_API.postman_collection.json` - Complete API collection with all endpoints
- `E-Modal_API.postman_environment.json` - Environment variables and credentials

## 🚀 Quick Start

### 1. Import into Postman

1. Open Postman
2. Click **Import** button (top left)
3. Drag and drop both JSON files or click "Choose Files"
4. Select:
   - `E-Modal_API.postman_collection.json`
   - `E-Modal_API.postman_environment.json`
5. Click **Import**

### 2. Select Environment

1. In the top-right corner, click the environment dropdown
2. Select **E-Modal API Environment**

### 3. Configure Environment Variables

Click the eye icon (👁️) next to the environment dropdown to view/edit variables:

#### Required Variables (Update Before Testing)
- `username` - Your E-Modal username (default: jfernandez)
- `password` - Your E-Modal password (default: taffie)
- `captcha_api_key` - Your 2Captcha API key (default: 7bf85bb6f37c9799543a2a463aab2b4f)

#### Server URLs
- `base_url` - Active server URL (default: Remote server 2)
- `base_url_local` - Local server (http://localhost:5010)
- `base_url_remote1` - Remote server 1 (http://89.117.63.196:5010)
- `base_url_remote2` - Remote server 2 (http://37.60.243.201:5010)

**To switch servers:** Change the `base_url` value to one of the predefined server URLs.

#### Test Data
- `test_container_id` - Container ID for testing (default: TRHU1866154)
- `test_container_id2` - Alternative container ID (default: MSDU5772413L)

#### Appointment Booking Variables (Update for booking tests)
- `trucking_company` - Your trucking company name
- `terminal` - Terminal name
- `move_type` - Import/Export (default: Import)
- `pin_code` - Container PIN code
- `truck_plate` - Truck plate number
- `own_chassis` - true/false
- `appointment_time` - Appointment time (format: 2025-10-10 10:00)

#### Auto-Saved Variables
- `session_id` - Automatically saved after session creation (don't edit manually)

## 📋 Collection Structure

### 1. Health & Session
- **Health Check** - Check API status and active sessions
- **Create Session** - Create persistent session (auto-saves session_id)
- **Manual Cleanup** - Trigger cleanup of old files

### 2. Containers
- **Get Containers - Infinite (Session)** - Get all containers with infinite scroll
- **Get Containers - Count (Session)** - Get specific number of containers
- **Get Containers - Until ID (Session)** - Get containers until target ID found (optimized)
- **Get Containers - With Credentials** - Auto-create session and get containers
- **Get Containers - Debug Mode** - Returns debug bundle with screenshots

### 3. Container Details
- **Get Container Timeline (Session)** - Get timeline with Pregate detection
- **Get Container Timeline (Credentials)** - Timeline with auto-session creation
- **Get Booking Number (Session)** - Extract booking number from container
- **Get Booking Number (Credentials)** - Booking number with auto-session creation
- **Get Booking Number - Debug** - With debug bundle

### 4. Appointments
- **Get Appointments - Infinite (Session)** - Get all appointments
- **Get Appointments - Count (Session)** - Get specific number of appointments
- **Get Appointments - Until ID (Session)** - Get appointments until target ID
- **Get Appointments (Credentials)** - Auto-create session and get appointments
- **Get Appointments - Debug** - With debug bundle

### 5. Appointment Booking
- **Check Appointments (Session)** - Check available times (never submits)
- **Check Appointments (Credentials)** - Check with auto-session creation
- **Make Appointment (Session)** - ⚠️ **SUBMITS booking!**
- **Make Appointment (Credentials)** - ⚠️ **SUBMITS booking with credentials!**

## 🎯 Recommended Testing Workflow

### Option 1: Session-Based Testing (Recommended)

1. **Health Check** - Verify API is running
2. **Create Session** - Creates persistent session (session_id auto-saved)
3. **Use any endpoint** - All "Session" requests will use the saved session_id
4. **Health Check** - Verify session is still active

**Benefits:**
- Faster (login once, reuse session)
- One Chrome window stays open
- Session is kept alive automatically (5-min refresh)

### Option 2: Credentials-Based Testing

1. **Health Check** - Verify API is running
2. **Use any "Credentials" endpoint** - Auto-creates session on first use
3. Session is created automatically and session_id is saved for subsequent requests

**Benefits:**
- No need to create session explicitly
- Automatic session management

## 🔄 Automatic Session Management

The collection includes JavaScript test scripts that automatically:
- Save `session_id` after session creation
- Save `session_id` from any endpoint that creates a session
- Reuse saved `session_id` in subsequent requests

## 📊 Testing Modes

### Get Containers / Get Appointments Modes

**1. Infinite Scrolling**
```json
{
  "infinite_scrolling": true
}
```
- Scrolls until no new content appears
- Gets ALL available items

**2. Target Count**
```json
{
  "infinite_scrolling": false,
  "target_count": 50
}
```
- Stops after reaching specified count
- Faster for specific quantities

**3. Target ID**
```json
{
  "infinite_scrolling": false,
  "target_container_id": "TRHU1866154"
}
```
- Stops when specific ID is found
- Returns all items up to and including target
- **Optimized with early exit** (for `/get_containers`)

### Debug Mode

Add `"debug": true` to any request to get:
- Screenshots of every step
- Debug files and logs
- ZIP bundle with all debug data

## 🧪 Example Test Sequences

### Test Sequence 1: Basic Container Operations
1. Health Check
2. Create Session
3. Get Containers - Count (Session) - 50 containers
4. Get Container Timeline (Session) - Use test_container_id
5. Get Booking Number (Session) - Same container
6. Health Check

### Test Sequence 2: Appointments Flow
1. Health Check
2. Create Session
3. Get Appointments - Count (Session) - 20 appointments
4. Check Appointments (Session) - See available times
5. Health Check

### Test Sequence 3: Credentials-Based
1. Health Check
2. Get Containers - With Credentials (auto-creates session)
3. Get Container Timeline (Session) - Reuses auto-created session
4. Get Booking Number (Session) - Same session
5. Get Appointments (Session) - Same session
6. Health Check

### Test Sequence 4: Debug Investigation
1. Health Check
2. Create Session
3. Get Containers - Debug Mode - Get ZIP with all debug data
4. Get Booking Number - Debug - Get screenshots and logs

## ⚠️ Important Notes

### Session Management
- Maximum 10 concurrent Chrome windows
- One session per user (identified by credentials)
- Sessions are kept alive automatically (5-min refresh)
- LRU eviction when limit reached
- Each session uses unique Chrome profile

### Appointment Booking Endpoints
- **`/check_appointments`** - Safe to test, NEVER submits
- **`/make_appointment`** - ⚠️ **WILL SUBMIT** the booking! Use with caution!

### Response Types
- Most endpoints return JSON
- **Debug mode** always returns JSON with `debug_bundle_url`
- **Non-debug `/get_containers`** can return Excel file directly (use `return_url: true` for JSON)

### File Downloads
- Excel files are stored on server
- Access via public URL in response: `file_url` or `debug_bundle_url`
- Files older than 24 hours are auto-deleted

## 🔍 Troubleshooting

### Session ID Not Saved
- Check that you're using the correct environment
- Look for "Session ID saved" in Postman Console (View → Show Postman Console)
- Manually copy session_id from response and paste into environment

### 401 Authentication Failed
- Verify credentials in environment variables
- Check captcha_api_key is valid
- Ensure server is running and accessible

### 500 Server Error
- Check server logs
- Verify ChromeDriver is compatible with Chrome version
- Try Manual Cleanup endpoint to free up resources

### Container/Appointment Not Found
- Update `test_container_id` with valid container ID
- Ensure container exists in the system
- Check container is visible for your user account

## 📈 Health Check Response

```json
{
  "status": "healthy",
  "service": "E-Modal Business Operations API",
  "active_sessions": 1,
  "max_sessions": 10,
  "persistent_sessions": 1,
  "session_capacity": "1/10",
  "timestamp": "2025-10-05T..."
}
```

**What to check:**
- `active_sessions` - Current Chrome windows open
- `max_sessions` - Maximum allowed (10)
- `persistent_sessions` - Sessions kept alive

## 🎓 Tips

1. **Start with Health Check** - Always verify API is running first
2. **Use Session Mode** - More efficient than creating new sessions each time
3. **Enable Debug for Issues** - Helps diagnose problems with screenshots
4. **Check Console** - Postman Console shows script execution and session_id saves
5. **Test Incrementally** - Start with small counts, then increase
6. **Monitor Health** - Check session capacity if seeing slow responses
7. **Use Collection Runner** - Run entire folders for comprehensive testing

## 🔐 Security

- Environment variables marked as `secret` are hidden by default
- Don't share environment file with sensitive credentials
- Keep captcha_api_key private

## 📚 Additional Resources

- API Documentation: See `PERSISTENT_SESSIONS_ALL_ENDPOINTS.md`
- Session Management: See `LRU_SESSION_MANAGEMENT.md`
- New Endpoints: See `NEW_ENDPOINTS_SUMMARY.md`
- Test Scripts: See Python test scripts in project root


