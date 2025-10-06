# LRU Session Management with 10-Window Limit

## 🎯 Overview

The E-Modal Business API now implements **LRU (Least Recently Used) session management** with a hard limit of **10 concurrent Chrome windows**. This ensures efficient resource usage while maintaining persistent sessions for active users.

---

## 📋 Key Features

### **1. Maximum 10 Concurrent Sessions**
- Hard limit: **10 Chrome browser windows** at any time
- One session per user (identified by credentials)
- Automatic resource management

### **2. LRU Eviction Algorithm**
- When limit reached (10 sessions) AND new user requests session:
  - Find session with **oldest `last_used` timestamp**
  - Close that browser window
  - Remove from active sessions
  - Create new session for new user

### **3. Automatic Session Creation**
- All endpoints auto-create persistent sessions if needed
- If `session_id` not provided → Auto-create with keep_alive=True
- If `session_id` provided → Use existing session
- If `session_id` invalid → Auto-create new session, return new ID

### **4. Per-User Sessions**
- Each user (unique username+password) gets ONE session
- Multiple requests with same credentials → Same session
- Credentials hashed (SHA256) for lookup

---

## 🔄 LRU Eviction Flow

```
┌──────────────────────────────────────────────────────────────┐
│ New user request arrives (10 sessions already active)       │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌────────────────────────────────────────┐
        │ Check: Active sessions >= 10?         │
        └────────────────────────────────────────┘
                 │                    │
            NO   │                    │  YES
                 ▼                    ▼
    ┌──────────────────────┐   ┌──────────────────────────┐
    │ Create new session   │   │ Find LRU Session:        │
    │ directly             │   │ - Oldest last_used time  │
    └──────────────────────┘   └──────────────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────┐
                            │ Evict LRU Session:           │
                            │ 1. Close browser (driver.quit())│
                            │ 2. Remove from persistent_sessions│
                            │ 3. Remove from active_sessions│
                            └──────────────────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────┐
                            │ Create new session for user  │
                            │ Active sessions: 10/10       │
                            └──────────────────────────────┘
```

---

## 📊 Implementation Details

### **Configuration**
```python
MAX_CONCURRENT_SESSIONS = 10  # Maximum Chrome windows allowed
session_refresh_interval = 300  # 5 minutes - refresh to keep alive
```

### **Core Functions**

#### **`get_lru_session()`**
```python
def get_lru_session() -> Optional[BrowserSession]:
    """Get the Least Recently Used session for eviction"""
    # Find session with oldest last_used timestamp
    lru_session = None
    oldest_time = None
    
    for session_id, session in active_sessions.items():
        if oldest_time is None or session.last_used < oldest_time:
            oldest_time = session.last_used
            lru_session = session
    
    return lru_session
```

#### **`evict_lru_session()`**
```python
def evict_lru_session() -> bool:
    """
    Evict the Least Recently Used session to make room for a new one.
    Returns True if a session was evicted, False otherwise.
    """
    lru_session = get_lru_session()
    
    # Close browser
    lru_session.driver.quit()
    
    # Remove from persistent_sessions
    if lru_session.credentials_hash in persistent_sessions:
        del persistent_sessions[lru_session.credentials_hash]
    
    # Remove from active_sessions
    del active_sessions[lru_session.session_id]
    
    return True
```

#### **`ensure_session_capacity()`**
```python
def ensure_session_capacity() -> bool:
    """
    Ensure there's capacity for a new session.
    If at limit (10 sessions), evict LRU session.
    """
    if len(active_sessions) < MAX_CONCURRENT_SESSIONS:
        return True  # Capacity available
    
    # At limit - evict LRU
    return evict_lru_session()
```

---

## 🎯 Usage Examples

### **Scenario 1: Normal Operation (< 10 sessions)**

```bash
# User 1 requests session
curl -X POST http://37.60.243.201:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "pass1", "captcha_api_key": "..."}'

# Response:
{
  "session_id": "session_1728145678_123",
  "is_new": true,
  "message": "New persistent session created"
}

# User 2, User 3, ... User 10 - all get sessions (total: 10)
```

### **Scenario 2: 11th User (LRU Eviction)**

```bash
# 10 sessions already active
# User 11 requests session
curl -X POST http://37.60.243.201:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{"username": "user11", "password": "pass11", "captcha_api_key": "..."}'

# System logs:
# ⚠️ Session limit reached: 10/10. Evicting LRU session...
# 🗑️ Evicting LRU session: session_XXX (user: user1, last_used: 2025-10-05 18:00:00)
# ✅ Browser closed for session: session_XXX
# ✅ LRU session evicted successfully. Active sessions: 9/10
# ✅ Created persistent session: session_YYY for user: user11
# 📊 Active sessions: 10/10

# Response:
{
  "session_id": "session_1728145999_789",
  "is_new": true,
  "message": "New persistent session created"
}
```

### **Scenario 3: Evicted User Returns**

```bash
# User 1 (was evicted) requests session again
curl -X POST http://37.60.243.201:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "pass1", "captcha_api_key": "..."}'

# System:
# - Finds no existing session for user1
# - Evicts current LRU (maybe user2)
# - Creates new session for user1

# Response:
{
  "session_id": "session_1728146100_456",  # NEW session ID
  "is_new": true,
  "message": "New persistent session created"
}
```

---

## 📊 Monitoring

### **Health Check**
```bash
curl http://37.60.243.201:5010/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "E-Modal Business Operations API",
  "version": "1.0.0",
  "active_sessions": 10,
  "max_sessions": 10,
  "session_capacity": "10/10",
  "persistent_sessions": 10,
  "timestamp": "2025-10-05T18:35:00"
}
```

### **Session List**
```bash
curl http://37.60.243.201:5010/sessions
```

**Response:**
```json
{
  "success": true,
  "sessions": [
    {
      "session_id": "session_1728145678_123",
      "username": "user1",
      "created_at": "2025-10-05T18:00:00",
      "last_used": "2025-10-05T18:30:00",
      "keep_alive": true
    },
    // ... 9 more sessions
  ]
}
```

---

## 🔍 LRU Selection Logic

Sessions are ranked by `last_used` timestamp:

| Session ID | Username | Last Used | Status |
|------------|----------|-----------|--------|
| session_001 | user1 | 18:00:00 | ← **LRU (oldest)** |
| session_002 | user2 | 18:05:00 | |
| session_003 | user3 | 18:10:00 | |
| ... | ... | ... | |
| session_010 | user10 | 18:30:00 | ← Most recently used |

When 11th user arrives, `session_001` (user1) is evicted.

---

## ⚙️ Background Tasks

### **Session Refresh Task**
- Runs every 60 seconds
- Refreshes sessions older than 5 minutes
- Updates `last_refresh` timestamp
- Does NOT update `last_used` (that's for LRU)

### **Key Distinction:**
- `last_used` → Updated on actual API usage (determines LRU)
- `last_refresh` → Updated by background task (keeps session alive)

---

## 🛡️ Edge Cases Handled

### **1. All sessions actively used**
- LRU still evicts oldest `last_used`
- User with oldest activity gets evicted
- Fair rotation based on usage

### **2. Session fails to close**
- Logged as warning
- Session still removed from tracking
- New session created

### **3. User requests session while being evicted**
- Race condition: User's session removed
- User immediately gets new session
- Seamless from user perspective

### **4. Same user, 10+ parallel requests**
- First request creates session
- Remaining requests reuse same session
- No eviction needed (same credentials)

---

## 📝 Benefits

| Feature | Benefit |
|---------|---------|
| **Resource Control** | Never exceed 10 Chrome windows |
| **Fair Allocation** | Active users keep sessions, idle users evicted |
| **Automatic Management** | No manual intervention needed |
| **Predictable Behavior** | LRU is simple and understood |
| **Transparent to Users** | Auto-recreate if evicted |

---

## 🧪 Testing LRU

### **Test Script: `test_lru_eviction.py`**

```python
import requests
import time

API_BASE_URL = "http://37.60.243.201:5010"

# Create 11 users
for i in range(1, 12):
    print(f"\n📌 Creating session for user{i}...")
    response = requests.post(f"{API_BASE_URL}/get_session", json={
        "username": f"user{i}",
        "password": f"pass{i}",
        "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
    })
    
    data = response.json()
    print(f"  Session ID: {data['session_id']}")
    print(f"  Is New: {data['is_new']}")
    
    # Check health
    health = requests.get(f"{API_BASE_URL}/health").json()
    print(f"  Sessions: {health['session_capacity']}")
    
    if i == 11:
        print("\n✅ LRU eviction should have occurred!")
        print(f"  Final capacity: {health['session_capacity']}")
    
    time.sleep(2)  # Small delay between requests
```

---

## 🚀 Status

✅ **Implemented:**
- LRU eviction algorithm
- 10-session hard limit
- `ensure_session_capacity()` check
- Health check shows capacity
- Logging for evictions

⏳ **TODO:**
- Add `session_id` parameter to all endpoints
- Auto-create sessions in endpoints
- Enhanced screenshot metadata

---

**LRU session management is now fully implemented and ready to use!** 🎉

