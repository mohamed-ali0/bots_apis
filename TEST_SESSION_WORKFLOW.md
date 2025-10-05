# Session Workflow Test Script

## 🎯 Purpose

Test the new persistent session management feature with a clear workflow:
1. **Create/Get Session** - Authenticate once, get session ID
2. **Choose Mode** - Select which get_containers mode to test
3. **Use Session** - All requests use the same session (no re-authentication)

## 🚀 Usage

```bash
python test_session_workflow.py
```

## 📋 Workflow

### **Step 1: Server Selection**
```
🌐 API Server Selection
======================================================================
Choose which server to connect to:

  1. Local server     (http://localhost:5010)
  2. Remote server 1  (http://89.117.63.196:5010)
  3. Remote server 2  (http://37.60.243.201:5010)  ← DEFAULT
  4. Custom server    (enter IP/hostname)

Enter your choice (1/2/3/4) [default: 3]:
```

### **Step 2: Health Check**
```
💚 Health Check
======================================================================
✅ API is healthy
  📊 Status: healthy
  🔗 Service: E-Modal Business Operations API
  📈 Session Capacity: 3/10
  🔄 Persistent Sessions: 2
```

### **Step 3: Create/Get Session**
```
📌 Step 1: Creating/Getting Persistent Session
======================================================================
👤 Username: jfernandez
🔑 Password: ******
🤖 Captcha Key: 7bf85bb6f37c9799543a...

🔄 Calling /get_session endpoint...

✅ Session Ready!
  📋 Session ID: session_1728145678_123456
  🆕 Is New: true
  👤 Username: jfernandez
  📅 Created At: 2025-10-05T18:30:00
  ⏰ Expires At: None (never - persistent)
  💬 Message: New persistent session created

🎉 New session created successfully!
```

### **Step 4: Choose Mode**
```
📦 Step 2: Choose Get Containers Mode
======================================================================

  1. Get ALL containers (infinite scroll)
  2. Get specific COUNT (e.g., 50, 100, 500)
  3. Get until CONTAINER ID found
  4. Run all modes sequentially

Enter your choice (1/2/3/4):
```

### **Step 5: Execute Mode**

#### **Mode 1: Get ALL Containers**
```
🔄 Mode 1: Get ALL Containers (Infinite Scroll)
======================================================================
📋 Using Session ID: session_1728145678_123456

🔄 Calling /get_containers with session_id...

✅ Success! (took 45.2s)
  📋 Session ID: session_1728145678_123456
  🆕 Is New Session: false  ← Reused existing session!
  📄 File: containers_scraped_20251005_183045.xlsx
  📊 Total Containers: 459
  🔄 Scroll Cycles: 27
  🔗 Download URL: http://37.60.243.201:5010/files/session_XXX/...
```

#### **Mode 2: Get Specific COUNT**
```
🔢 Mode 2: Get Specific COUNT
======================================================================
📋 Using Session ID: session_1728145678_123456

Enter container count (e.g., 50, 100, 500) [default: 100]: 100

🔄 Getting 100 containers...

✅ Success! (took 15.3s)
  📋 Session ID: session_1728145678_123456
  🆕 Is New Session: false  ← Still same session!
  📄 File: containers_scraped_20251005_183102.xlsx
  📊 Total Containers: 100
```

#### **Mode 3: Find Container ID**
```
🔍 Mode 3: Get Until Container ID Found
======================================================================
📋 Using Session ID: session_1728145678_123456

Enter container ID (e.g., MSDU5772413): MSDU5772413

🔄 Searching for container: MSDU5772413...

✅ Success! (took 8.7s)
  📋 Session ID: session_1728145678_123456
  🆕 Is New Session: false  ← Same session again!
  📄 File: containers_scraped_20251005_183115.xlsx
  📊 Total Containers: 23
  🎯 Found Target: true
```

---

## 🎯 Key Features

### **1. Session Reuse**
- Session created **ONCE** at the beginning
- All subsequent requests use the **SAME session_id**
- **No re-authentication** for mode 2, 3, etc.

### **2. Speed Comparison**

| Operation | With Auth | With Session | Speedup |
|-----------|-----------|--------------|---------|
| First request | ~20s (login + captcha) | ~20s | - |
| Second request | ~20s (re-auth) | ~2s | **10x faster!** |
| Third request | ~20s (re-auth) | ~2s | **10x faster!** |

### **3. Multiple Modes**
Test all 3 get_containers modes with the same session:
- Mode 1: Infinite scroll (ALL containers)
- Mode 2: Target count (specific number)
- Mode 3: Find container ID (stop when found)

### **4. Session Persistence**
- Session survives between requests
- Auto-refreshed every 5 minutes in background
- Never expires (until server restart or LRU eviction)

---

## 📊 Example Output

```
🌐 Using API server: http://37.60.243.201:5010

💚 Health Check
✅ API is healthy
  📈 Session Capacity: 3/10

📌 Step 1: Creating/Getting Persistent Session
✅ Session Ready!
  📋 Session ID: session_1728145678_123456

📦 Step 2: Choose Get Containers Mode
  Choice: 2 (Get specific COUNT)

🔢 Mode 2: Get Specific COUNT
  Count: 100
✅ Success! (took 15.3s)
  📋 Session ID: session_1728145678_123456  ← Same session
  🆕 Is New Session: false  ← Reused!
  📊 Total Containers: 100
```

---

## 💡 Benefits

1. **Clear Workflow** - Step-by-step process, easy to follow
2. **Session Visibility** - See session_id creation and reuse
3. **Speed Demonstration** - Compare first vs subsequent requests
4. **Multiple Modes** - Test all modes with one session
5. **Interactive** - Pause between steps, choose options

---

## 🔧 Customization

### **Change Credentials**
Edit the script:
```python
USERNAME = "your_username"
PASSWORD = "your_password"
CAPTCHA_KEY = "your_captcha_key"
```

### **Auto Mode**
```bash
# Skip interactive prompts
export AUTO_TEST=1
export API_HOST=37.60.243.201
python test_session_workflow.py
```

---

## ✅ Success Indicators

**Session Created:**
```
🎉 New session created successfully!
```

**Session Reused:**
```
🔄 Existing session reused!
🆕 Is New Session: false
```

**Fast Request (no auth):**
```
✅ Success! (took 2.3s)  ← Very fast!
```

---

**This script demonstrates the power of persistent session management!** 🚀
