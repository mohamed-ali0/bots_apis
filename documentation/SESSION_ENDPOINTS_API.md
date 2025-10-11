# Session Management API Documentation

## Overview
The E-Modal Business API provides session management endpoints to create, list, and manage persistent browser sessions. Sessions allow you to reuse authenticated browser instances across multiple API calls, improving performance and reducing authentication overhead.

## Session Endpoints

### 1. Create/Get Session
```
POST /get_session
```

#### Description
Creates a new persistent browser session or returns an existing session for the given credentials. Sessions are kept alive for 10 minutes and can be reused across multiple API calls.

#### Request Format

##### Headers
```
Content-Type: application/json
```

##### Request Body (JSON)
```json
{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_2captcha_api_key"
}
```

##### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Yes | E-Modal username |
| `password` | string | Yes | E-Modal password |
| `captcha_api_key` | string | Yes | 2captcha API key for reCAPTCHA solving |

#### Response Format

##### Success Response (200 OK)

###### New Session Created
```json
{
    "success": true,
    "session_id": "session_1704623456_1234567890",
    "is_new": true,
    "username": "your_username",
    "created_at": "2024-01-07T12:34:56.789Z",
    "expires_at": null,
    "message": "New persistent session created"
}
```

###### Existing Session Reused
```json
{
    "success": true,
    "session_id": "session_1704623456_1234567890",
    "is_new": false,
    "username": "your_username",
    "created_at": "2024-01-07T12:30:00.000Z",
    "expires_at": null,
    "message": "Using existing persistent session"
}
```

##### Error Response (400/401/500)

###### Missing Required Fields
```json
{
    "success": false,
    "error": "Missing required fields: username, password, captcha_api_key"
}
```

###### Authentication Failed
```json
{
    "success": false,
    "error": "Authentication failed",
    "details": "Invalid credentials"
}
```

###### Session Capacity Exceeded
```json
{
    "success": false,
    "error": "Failed to allocate session capacity"
}
```

###### Server Error
```json
{
    "success": false,
    "error": "Internal server error details"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation was successful |
| `session_id` | string | Unique session identifier for reuse in other endpoints |
| `is_new` | boolean | Whether this is a newly created session or existing one |
| `username` | string | Associated username |
| `created_at` | string | Session creation timestamp (ISO format) |
| `expires_at` | null | Always null for persistent sessions |
| `message` | string | Additional information about the operation |
| `error` | string | Error message (only when success: false) |
| `details` | string | Additional error details (only for authentication errors) |

---

### 2. List Active Sessions
```
GET /sessions
```

#### Description
Returns a list of all currently active browser sessions with their details.

#### Request Format
No request body required.

#### Response Format

##### Success Response (200 OK)
```json
{
    "active_sessions": 3,
    "sessions": [
        {
            "session_id": "session_1704623456_1234567890",
            "username": "user1",
            "created_at": "2024-01-07T12:30:00.000Z",
            "last_used": "2024-01-07T12:35:00.000Z",
            "keep_alive": true,
            "current_url": "https://truckerportal.emodal.com/containers"
        },
        {
            "session_id": "session_1704623457_0987654321",
            "username": "user2",
            "created_at": "2024-01-07T12:32:00.000Z",
            "last_used": "2024-01-07T12:33:00.000Z",
            "keep_alive": true,
            "current_url": "https://truckerportal.emodal.com/myappointments"
        }
    ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `active_sessions` | integer | Total number of active sessions |
| `sessions` | array | List of session objects |
| `sessions[].session_id` | string | Unique session identifier |
| `sessions[].username` | string | Associated username |
| `sessions[].created_at` | string | Session creation timestamp (ISO format) |
| `sessions[].last_used` | string | Last activity timestamp (ISO format) |
| `sessions[].keep_alive` | boolean | Whether session is persistent |
| `sessions[].current_url` | string | Current browser URL |

---

### 3. Close Session
```
DELETE /sessions/{session_id}
```

#### Description
Closes a specific browser session and frees up resources.

#### Request Format

##### URL Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID to close |

#### Response Format

##### Success Response (200 OK)
```json
{
    "success": true,
    "message": "Session session_1704623456_1234567890 closed"
}
```

##### Error Response (404/500)

###### Session Not Found
```json
{
    "success": false,
    "error": "Session not found"
}
```

###### Close Error
```json
{
    "success": false,
    "error": "Failed to close browser session"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation was successful |
| `message` | string | Success message (only when success: true) |
| `error` | string | Error message (only when success: false) |

---

## Session Management Features

### Persistent Sessions
- Sessions are kept alive for **10 minutes** of inactivity
- Maximum of **10 concurrent sessions** at any time
- Sessions are automatically refreshed to maintain authentication
- LRU (Least Recently Used) eviction when capacity is reached

### Session Reuse
Once you have a `session_id`, you can use it in other endpoints:

```json
{
    "session_id": "session_1704623456_1234567890",
    "container_id": "TRHU1866154",
    "debug": false
}
```

### Session Protection
- Sessions are protected from background refresh during active operations
- `in_use` flag prevents session interruption
- Automatic cleanup of expired sessions

## Example Usage

### Create Session
```bash
curl -X POST http://localhost:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_2captcha_api_key"
  }'
```

### List Sessions
```bash
curl -X GET http://localhost:5010/sessions
```

### Close Session
```bash
curl -X DELETE http://localhost:5010/sessions/session_1704623456_1234567890
```

### Use Session in Other Endpoints
```bash
curl -X POST http://localhost:5010/get_booking_number \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_1704623456_1234567890",
    "container_id": "TRHU1866154"
  }'
```

## Python Examples

### Create and Use Session
```python
import requests

# Create session
session_response = requests.post('http://localhost:5010/get_session', json={
    'username': 'your_username',
    'password': 'your_password',
    'captcha_api_key': 'your_2captcha_api_key'
})

session_data = session_response.json()
if session_data['success']:
    session_id = session_data['session_id']
    print(f"Session created: {session_id}")
    
    # Use session in other endpoints
    booking_response = requests.post('http://localhost:5010/get_booking_number', json={
        'session_id': session_id,
        'container_id': 'TRHU1866154'
    })
    
    print(booking_response.json())
```

### List and Manage Sessions
```python
# List all sessions
sessions_response = requests.get('http://localhost:5010/sessions')
sessions_data = sessions_response.json()

print(f"Active sessions: {sessions_data['active_sessions']}")
for session in sessions_data['sessions']:
    print(f"Session {session['session_id']} - User: {session['username']}")

# Close a specific session
close_response = requests.delete(f'http://localhost:5010/sessions/{session_id}')
print(close_response.json())
```

## Notes

- Sessions are automatically cleaned up after 10 minutes of inactivity
- Maximum 10 concurrent sessions are supported
- Session IDs are unique and can be reused across multiple API calls
- All endpoints support both session-based and credential-based authentication
- Sessions include automatic reCAPTCHA solving and popup blocking
