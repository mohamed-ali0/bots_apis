# ChromeDriver Crash Root Causes & Solutions

## Common Root Causes

### 1. Memory Exhaustion ⚠️ **MOST COMMON**

**What happens:**
- Chrome uses 200-500 MB per instance
- Multiple sessions = 2-5 GB RAM
- System runs out of memory
- ChromeDriver crashes with connection error

**Signs:**
```
WinError 10061: Connection refused
Max retries exceeded
Failed to establish a new connection
```

**Solution:**
- Reduce `MAX_CONCURRENT_SESSIONS` 
- Add Chrome memory optimization flags
- Monitor system RAM usage

---

### 2. ChromeDriver Process Hanging/Deadlock

**What happens:**
- Long-running operations (infinite scroll, waiting)
- ChromeDriver internal deadlock
- Process becomes unresponsive
- Eventually crashes or times out

**Signs:**
```
Operation takes very long (>2 minutes)
No logs, just hanging
Eventually: Connection refused
```

**Solution:**
- Add operation timeouts
- Break long operations into chunks
- Regular health checks during operations

---

### 3. Chrome Version Mismatch

**What happens:**
- Chrome auto-updates to version 141.x
- ChromeDriver is version 140.x
- Incompatibility causes crashes

**Signs:**
```
session not created: Chrome version must be...
This version of ChromeDriver only supports Chrome version...
```

**Your logs show:**
```
INFO:WDM:Get LATEST chromedriver version for google-chrome
INFO:WDM:Modern chrome version https://storage.googleapis.com/.../141.0.7390.76/
```

**Solution:**
- Use `webdriver-manager` (already implemented ✅)
- Auto-downloads matching version
- Keep Chrome from auto-updating

---

### 4. Too Many Open File Descriptors (Windows Handles)

**What happens:**
- Each Chrome process opens many handles (network, files, GPU)
- System limit reached (Windows: ~10,000 handles per process)
- New operations fail
- ChromeDriver crashes

**Signs:**
```
Too many open files
Cannot create new thread
Resource temporarily unavailable
```

**Solution:**
- Close unused tabs/windows
- Limit concurrent operations
- Clean up old sessions

---

### 5. Port Exhaustion

**What happens:**
- ChromeDriver uses random ports for communication
- With many sessions, ports get exhausted
- New connections fail
- "Connection refused" errors

**Signs:**
```
Failed to establish connection: [WinError 10061]
Address already in use
Cannot bind to port
```

**Solution:**
- Limit concurrent sessions
- Ensure proper driver cleanup
- Use connection pooling

---

### 6. Proxy/Network Issues

**What happens:**
- Proxy server (dc.oxylabs.io:8001) becomes unresponsive
- Network timeout during operations
- Chrome/ChromeDriver loses connection
- Crashes trying to reconnect

**Signs:**
```
Proxy connection error
ERR_PROXY_CONNECTION_FAILED
Connection timed out
```

**Your setup:**
```python
proxy = "dc.oxylabs.io:8001"
user = "mo3li_moQef"
```

**Solution:**
- Monitor proxy health
- Add proxy timeouts
- Implement proxy failover

---

### 7. GPU Process Crashes

**What happens:**
- Chrome tries to use GPU acceleration
- GPU driver incompatible or crashes
- Takes down entire Chrome instance

**Your logs show:**
```
[ERROR:gpu\command_buffer\service\gles2_cmd_decoder_passthrough.cc:1101]
Automatic fallback to software WebGL has been deprecated
```

**This is a warning but indicates GPU issues!**

**Solution:**
- Disable GPU: `--disable-gpu`
- Use software rendering: `--disable-software-rasterizer`
- Use headless mode: `--headless`

---

### 8. Selenium Command Timeout

**What happens:**
- Long-running JavaScript execution
- Page load takes forever
- ChromeDriver gives up waiting
- Connection times out

**Signs:**
```
Timeout waiting for page to load
Script timeout
Element not found after 30 seconds
```

**Solution:**
- Set explicit timeouts
- Add page load strategies
- Break operations into smaller steps

---

### 9. Multiple Sessions Resource Competition

**What happens:**
- 10 Chrome instances all running simultaneously
- All doing infinite scroll, screenshots, etc.
- System resources (CPU, RAM, disk I/O) overloaded
- Random crashes

**Solution:**
- Serialize heavy operations
- Limit concurrent operations per session
- Add resource monitoring

---

### 10. ChromeDriver Service Termination

**What happens:**
- ChromeDriver service process terminates unexpectedly
- Could be system kill, out of memory, crash
- All connections to that driver fail

**Your specific error:**
```
Failed to establish a new connection: [WinError 10061]
/session/9710f3b7ceba2fa49d39329c52ca200f/url
```

**This means:** ChromeDriver service on port 51418 is **completely gone**

---

## 🔍 Your Specific Case Analysis

Based on your logs:

```
🔒 Cleaned up expired appointment session
→ Session tries to use driver
→ WinError 10061: Connection refused (port 51418)
→ ChromeDriver service is gone!
```

**Most Likely Causes:**

**#1 - Memory Exhaustion** (70% likely)
- Multiple Chrome instances + background processes
- System runs out of RAM
- ChromeDriver killed by OS

**#2 - ChromeDriver Process Crash** (20% likely)
- Internal ChromeDriver bug
- Deadlock in driver service
- Process terminates unexpectedly

**#3 - Port/Network Issue** (10% likely)
- Port conflict
- Windows firewall
- Network driver issue

---

## 🛠️ Recommended Solutions (Priority Order)

### Priority 1: Reduce Resource Usage ⚡

**Implement Chrome optimization flags in `emodal_login_handler.py`:**

```python
options.add_argument('--disable-gpu')  # Fix GPU errors, save memory
options.add_argument('--disable-dev-shm-usage')  # Reduce shared memory usage
options.add_argument('--no-sandbox')  # Reduce process overhead
options.add_argument('--disable-setuid-sandbox')
options.add_argument('--single-process')  # Use 1 process instead of many
options.add_argument('--disable-extensions')  # No extensions overhead
options.add_argument('--disable-images')  # Don't load images (huge savings!)
options.add_argument('--blink-settings=imagesEnabled=false')
options.add_argument('--disable-software-rasterizer')
```

**Expected result:** 15-20 total Chrome processes instead of 40+

---

### Priority 2: Limit Concurrent Sessions

```python
# Line 46
MAX_CONCURRENT_SESSIONS = 5  # Reduce from 10 to 5
```

**Expected result:** Fewer crashes, more stability

---

### Priority 3: Add Operation Timeouts

**Prevent operations from hanging forever:**
```python
# For infinite scroll operations
max_scroll_time = 120  # 2 minutes max
start_time = time.time()

while scrolling:
    if time.time() - start_time > max_scroll_time:
        logger.warning("Scroll timeout - stopping")
        break
    # ... scroll logic ...
```

---

### Priority 4: Monitor System Resources

**Add RAM check before creating new sessions:**
```python
import psutil

def check_system_resources():
    mem = psutil.virtual_memory()
    if mem.percent > 85:  # More than 85% RAM used
        logger.warning(f"High memory usage: {mem.percent}%")
        return False
    return True
```

---

### Priority 5: Implement ChromeDriver Watchdog

**Restart ChromeDriver if it becomes unresponsive:**
```python
def check_chromedriver_health(session):
    """Ping ChromeDriver to check if responsive"""
    try:
        _ = session.driver.current_url
        return True
    except:
        # Try to restart the connection
        logger.warning("ChromeDriver unresponsive, attempting recovery...")
        return False
```

---

## 🚀 Quick Wins You Can Implement Now

### Win 1: Reduce Session Limit
```python
MAX_CONCURRENT_SESSIONS = 5  # More stable
```

### Win 2: Clean Up Regularly
```bash
# Every hour, run:
curl -X POST http://localhost:5010/cleanup_orphaned_processes
```

### Win 3: Monitor Chrome Processes
```powershell
# Check process count:
(Get-Process chrome -ErrorAction SilentlyContinue).Count

# Should be ~15-25 for 2-3 sessions
# If >40, run cleanup
```

### Win 4: Check System RAM
```powershell
Get-Counter '\Memory\Available MBytes'
# Should have >2GB available
```

---

## 🎯 Immediate Action Items

**To fix your current issue, do these in order:**

**1. Restart the server** (clears everything)
```
Ctrl+C (stop server)
python emodal_business_api.py
```

**2. Check Chrome processes after startup**
```powershell
(Get-Process chrome -ErrorAction SilentlyContinue).Count
```
Should be 0 or very low

**3. Create ONE session and test**
```
Don't create 5-10 sessions at once
Test with just 1-2 sessions first
```

**4. Monitor for crashes**
```
Watch the console for connection errors
If you see "Connection refused", run cleanup immediately
```

---

## 🔧 Want Me To Implement Chrome Optimizations?

I can add memory-efficient Chrome flags to reduce from 40+ processes to ~15-20 processes.

**Should I:**
1. ✅ Add Chrome optimization flags (disable GPU, images, etc.)
2. ✅ Reduce MAX_CONCURRENT_SESSIONS to 5
3. ✅ Add system resource monitoring
4. ✅ All of the above

**Let me know and I'll implement it!** 🛠️
