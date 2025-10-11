# Process Cleanup and Emergency Recovery API

## Overview
The E-Modal Business API now includes automatic and manual process cleanup mechanisms to handle orphaned Chrome/ChromeDriver processes and provide emergency recovery when connection errors occur.

## Features

### 1. Automatic Cleanup on Connection Errors
When a session health check detects a connection error (WinError 10061), the system automatically:
- Detects orphaned ChromeDriver processes
- Kills processes not associated with active sessions
- Keeps active session processes running
- Logs all cleanup actions

### 2. Manual Orphaned Process Cleanup
Kill Chrome/ChromeDriver processes that are no longer needed while preserving active sessions.

### 3. Emergency Recovery
Complete system reset that kills ALL Chrome instances when normal recovery fails.

---

## Endpoints

### 1. Cleanup Orphaned Processes
```
POST /cleanup_orphaned_processes
```

#### Description
Identifies and kills Chrome/ChromeDriver processes that are not associated with any active session. This is safe to use during normal operation as it protects active sessions.

#### How It Works
1. Collects PIDs of all active session drivers
2. Scans all ChromeDriver processes
3. Kills ChromeDriver processes NOT in active sessions
4. Scans all Chrome processes
5. Kills Chrome processes whose parent ChromeDriver is orphaned

#### Request Format
No request body required.

#### Response Format

##### Success Response (200 OK)
```json
{
    "success": true,
    "message": "Cleaned up 3 orphaned processes",
    "killed_count": 3,
    "active_sessions": 5
}
```

##### Error Response (500)
```json
{
    "success": false,
    "error": "Error details"
}
```

#### Example Usage

##### cURL
```bash
curl -X POST http://localhost:5010/cleanup_orphaned_processes
```

##### Python
```python
import requests

response = requests.post('http://localhost:5010/cleanup_orphaned_processes')
data = response.json()

if data['success']:
    print(f"Killed {data['killed_count']} orphaned processes")
    print(f"Active sessions: {data['active_sessions']}")
```

---

### 2. Emergency Recovery
```
POST /emergency_recovery
```

#### Description
**⚠️ WARNING**: This endpoint kills ALL Chrome and ChromeDriver processes on the system, not just those managed by the API. Use this only as a last resort when:
- Normal recovery mechanisms fail
- Too many zombie processes consuming resources
- System is in an unrecoverable state

#### What It Does
1. Kills ALL ChromeDriver processes (system-wide)
2. Kills ALL Chrome processes (system-wide)
3. Clears all active sessions from memory
4. Clears all persistent session mappings
5. Frees up system resources

#### Request Format
No request body required.

#### Response Format

##### Success Response (200 OK)
```json
{
    "success": true,
    "message": "Emergency recovery completed - killed 15 processes and cleared all sessions",
    "killed_count": 15,
    "warning": "All Chrome browsers have been closed",
    "active_sessions": 0
}
```

##### Error Response (500)
```json
{
    "success": false,
    "error": "Error details"
}
```

#### Example Usage

##### cURL
```bash
curl -X POST http://localhost:5010/emergency_recovery
```

##### Python
```python
import requests

# CAUTION: This will close ALL Chrome browsers
response = requests.post('http://localhost:5010/emergency_recovery')
data = response.json()

if data['success']:
    print(f"Emergency recovery: killed {data['killed_count']} processes")
    print(f"Warning: {data['warning']}")
```

---

## Automatic Recovery Flow

### When Connection Error Detected

```
Session Health Check
    ↓
Connection Error Detected (WinError 10061)
    ↓
Automatic Orphaned Process Cleanup
    ↓
    ├─ Success → Continue with new session creation
    └─ Failure → Log error, proceed with recovery
```

### Session Retrieval Process

```
1. Check if session_id exists
    ↓
2. Check if session is alive (health check)
    ↓
    ├─ Alive → Use existing session
    └─ Dead → Trigger cleanup
        ↓
        a. Kill orphaned processes
        b. Remove dead session
        c. Create new session
```

---

## Use Cases

### Use Case 1: Regular Maintenance
**Scenario**: You notice Chrome processes accumulating over time

**Solution**: 
```bash
# Run orphaned process cleanup periodically
curl -X POST http://localhost:5010/cleanup_orphaned_processes
```

### Use Case 2: Session Stuck/Frozen
**Scenario**: A session appears frozen and not responding

**Solution**:
```python
# First, try to close the specific session
requests.delete(f'http://localhost:5010/sessions/{session_id}')

# Then clean up orphaned processes
requests.post('http://localhost:5010/cleanup_orphaned_processes')
```

### Use Case 3: System Overloaded
**Scenario**: System is sluggish, too many Chrome processes

**Solution**:
```bash
# Check active sessions
curl http://localhost:5010/sessions

# If many orphaned processes exist
curl -X POST http://localhost:5010/cleanup_orphaned_processes

# If problem persists (LAST RESORT)
curl -X POST http://localhost:5010/emergency_recovery
```

### Use Case 4: Connection Errors
**Scenario**: Getting "Connection refused" errors

**Solution**: The system now handles this automatically!
- Health check detects dead session
- Automatic orphaned process cleanup triggered
- New session created seamlessly
- No manual intervention needed

---

## Process Protection

### What Gets Protected
The orphaned process cleanup protects:
- ✅ All ChromeDriver processes associated with active sessions
- ✅ All Chrome browsers managed by active session drivers
- ✅ Running operations (sessions marked as `in_use`)

### What Gets Killed
The orphaned process cleanup kills:
- ❌ ChromeDriver processes NOT in active sessions
- ❌ Chrome processes whose parent ChromeDriver is orphaned
- ❌ Zombie processes from crashed sessions

---

## Monitoring and Logging

### Log Messages

#### Automatic Cleanup Triggered
```
WARNING: Session session_123 appears dead: [WinError 10061]
WARNING: 🔧 Connection error detected - attempting to clean up orphaned processes
INFO: Active ChromeDriver PIDs: {1234, 5678}
INFO: Killing orphaned ChromeDriver process: PID 9012
INFO: ✅ Killed 2 orphaned Chrome/ChromeDriver processes
```

#### Manual Cleanup
```
INFO: 🔧 Orphaned process cleanup triggered
INFO: Active ChromeDriver PIDs: {1234, 5678, 9012}
INFO: ✅ No orphaned processes found
```

#### Emergency Recovery
```
WARNING: 🚨 EMERGENCY RECOVERY: Killing ALL Chrome instances
INFO: Killing ChromeDriver process: PID 1234
INFO: Killing Chrome process: PID 5678
WARNING: 🚨 Emergency recovery killed 15 processes
INFO: 🗑️ Cleared all session data
```

---

## Best Practices

### 1. Use Orphaned Cleanup Regularly
```python
# Run cleanup daily or after heavy usage
schedule.every().day.at("02:00").do(cleanup_orphaned_processes)
```

### 2. Monitor Process Count
```python
# Check system Chrome processes periodically
import psutil

chrome_count = sum(1 for p in psutil.process_iter(['name']) 
                   if 'chrome' in p.info['name'].lower())
if chrome_count > 50:
    # Too many, clean up
    requests.post('http://localhost:5010/cleanup_orphaned_processes')
```

### 3. Emergency Recovery Only When Necessary
```python
# Only use emergency recovery as LAST RESORT
def handle_critical_failure():
    try:
        # First try normal cleanup
        requests.post('http://localhost:5010/cleanup_orphaned_processes')
        time.sleep(5)
        
        # Check if it worked
        sessions = requests.get('http://localhost:5010/sessions').json()
        if sessions['active_sessions'] > 0:
            return  # Normal cleanup worked
        
        # If still problems, emergency recovery
        print("WARNING: Using emergency recovery - will close ALL Chrome")
        requests.post('http://localhost:5010/emergency_recovery')
    except Exception as e:
        print(f"Recovery failed: {e}")
```

### 4. Graceful Session Closure
```python
# Always close sessions properly when done
def cleanup_session(session_id):
    try:
        # Close specific session
        response = requests.delete(f'http://localhost:5010/sessions/{session_id}')
        
        # Then clean up any orphans
        requests.post('http://localhost:5010/cleanup_orphaned_processes')
    except Exception as e:
        print(f"Cleanup error: {e}")
```

---

## Dependencies

The process cleanup feature requires the `psutil` library:

```bash
pip install psutil==5.9.6
```

This is already included in `requirements.txt`.

---

## Platform Support

- ✅ **Windows**: Full support
- ✅ **Linux**: Full support
- ✅ **macOS**: Full support

Process cleanup works across all platforms using `psutil` cross-platform process management.

---

## Summary

### Automatic Features
- ✅ Health checks on every session access
- ✅ Automatic orphaned process cleanup on connection errors
- ✅ Seamless session recovery without user intervention
- ✅ Protection of active sessions during cleanup

### Manual Control
- ✅ `/cleanup_orphaned_processes` - Safe cleanup of zombie processes
- ✅ `/emergency_recovery` - Complete system reset (last resort)
- ✅ Clear logging and monitoring
- ✅ Detailed response information

### Benefits
- 🚀 Better system resource management
- 🔧 Automatic recovery from connection errors
- 🛡️ Protection of active sessions
- 📊 Clear visibility into process cleanup
- 🔄 Seamless user experience during recovery
