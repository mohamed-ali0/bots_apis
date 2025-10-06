# Test Using Existing Session

## 🎯 Purpose

Quick test to verify that you can reuse an already-created `session_id` without creating a new session.

---

## 🚀 Quick Start

### **Step 1: Create a Session First**
```bash
# Run this first to create a session
python test_session_workflow.py
```

**Note the session_id from the output:**
```
✅ Session Ready!
  📋 Session ID: session_1759683996_249140832508791461  ← Copy this!
```

### **Step 2: Use the Existing Session**
```bash
# Run the test script
python test_use_existing_session.py
```

**When prompted, paste the session_id:**
```
Enter session_id to use: session_1759683996_249140832508791461
```

---

## 📋 What the Script Does

1. **Health Check** - Shows API status and session capacity
2. **List Sessions** - Shows all active sessions (helpful to copy session_id)
3. **Prompt for Session ID** - Asks you to enter a session_id
4. **Test Operation** - Calls `/get_containers` with the session_id
5. **Verify Reuse** - Confirms the session was reused (not created new)
6. **Final Health Check** - Shows updated session status

---

## 📊 Expected Output

### **Successful Session Reuse:**
```
💚 Health Check
✅ API is healthy
  📈 Session Capacity: 1/10
  🔄 Persistent Sessions: 1

📋 Active Sessions
Found 1 active session(s):

  1. Session ID: session_1759683996_249140832508791461
     👤 Username: jfernandez
     📅 Created: 2025-10-05T19:05:00
     🔄 Last Used: 2025-10-05T19:10:00
     💾 Keep Alive: true

📝 Enter Session ID
Enter session_id to use: session_1759683996_249140832508791461

🧪 Testing with Existing Session
Enter container count to fetch [default: 20]: 50

🔄 Getting 50 containers using existing session...
⏱️ Starting timer...

✅ Success! (took 2.3s)  ← Very fast!

📊 Response Details:
  📋 Session ID: session_1759683996_249140832508791461
  🆕 Is New Session: false  ← Reused existing session!
  📄 File: containers_scraped_20251005_192045.xlsx
  📊 Total Containers: 50
  🔗 Download URL: http://37.60.243.201:5010/files/...

✅ SUCCESS: Existing session was reused!
   ⚡ Fast operation (no login required)
   ⏱️  Time: 2.3s (vs ~20s with login)
```

### **Invalid Session ID:**
```
❌ Failed: 400
  Error: Invalid or expired session_id

💡 Tip: The session_id might be invalid or expired.
   Try creating a new session with test_session_workflow.py
```

---

## 🎯 Use Cases

### **Use Case 1: Quick Test**
You created a session earlier and want to quickly test it:
```bash
python test_use_existing_session.py
# Enter the session_id you saved earlier
```

### **Use Case 2: Verify Session Persistence**
Check if a session is still active after some time:
```bash
# Morning: Create session
python test_session_workflow.py
# Note session_id: session_XXX

# Afternoon: Test if still active
python test_use_existing_session.py
# Enter session_id: session_XXX
# Should still work (persistent sessions never expire!)
```

### **Use Case 3: Performance Testing**
Compare speed with and without login:
```bash
# With login (first time):
python test_session_workflow.py
# Time: ~20-25 seconds

# Without login (reusing session):
python test_use_existing_session.py
# Time: ~2-3 seconds
# 10x faster! ⚡
```

---

## 🔍 What to Verify

### **✅ Session Found**
- [ ] Script lists active sessions
- [ ] Your session_id appears in the list
- [ ] Session shows `keep_alive: true`

### **✅ Session Reused**
- [ ] Response shows `is_new_session: false`
- [ ] Same session_id returned
- [ ] Operation completes quickly (~2-3s)

### **✅ Performance**
- [ ] First request: ~20s (with login)
- [ ] Second request: ~2s (no login)
- [ ] **10x speed improvement!** ⚡

### **✅ Session Remains Active**
- [ ] Final health check shows session still exists
- [ ] Can use the same session_id again
- [ ] Session never expires (persistent)

---

## 🐛 Troubleshooting

### **Error: "Invalid or expired session_id"**
**Cause:** Session doesn't exist or was evicted (LRU)  
**Solution:** Create a new session:
```bash
python test_session_workflow.py
```

### **Error: "No active sessions found"**
**Cause:** No sessions have been created yet  
**Solution:** Create a session first:
```bash
python test_session_workflow.py
```

### **Error: Connection refused**
**Cause:** API server not running  
**Solution:** Start the API:
```bash
python emodal_business_api.py
```

---

## 💡 Pro Tips

### **Tip 1: Copy Session ID from List**
The script lists all active sessions - just copy the session_id from there!

### **Tip 2: Save Session ID**
```bash
# Save to file for later use
echo "session_1759683996_249140832508791461" > my_session.txt

# Use later
cat my_session.txt
```

### **Tip 3: Test Multiple Sessions**
```bash
# Terminal 1: Create User 1 session
python test_session_workflow.py
# Note session_id_1

# Terminal 2: Create User 2 session
python test_session_workflow_user2.py
# Note session_id_2

# Terminal 3: Test both sessions
python test_use_existing_session.py
# Test with session_id_1

python test_use_existing_session.py
# Test with session_id_2
```

---

## 📝 Example Workflow

```bash
# Step 1: Create a session (one time)
$ python test_session_workflow.py
✅ Session ID: session_XXX

# Step 2: Use it multiple times (fast!)
$ python test_use_existing_session.py
Enter session_id: session_XXX
✅ Success! (2.1s)

$ python test_use_existing_session.py
Enter session_id: session_XXX
✅ Success! (2.3s)

$ python test_use_existing_session.py
Enter session_id: session_XXX
✅ Success! (2.2s)

# All fast! No re-authentication needed! ⚡
```

---

## ✅ Success Indicators

**Session Reuse Working:**
```
✅ SUCCESS: Existing session was reused!
   ⚡ Fast operation (no login required)
   ⏱️  Time: 2.3s (vs ~20s with login)
```

**Performance Improvement:**
- First request (with login): ~20-25s
- Subsequent requests (with session_id): ~2-3s
- **Speed improvement: 10x faster!** 🚀

---

**Ready to test! This script makes it easy to verify session reuse works correctly.** 🎯

