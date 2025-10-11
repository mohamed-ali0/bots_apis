# Concurrency Testing Guide

## 🎯 Purpose

Test the persistent session management with **2 concurrent users** to verify:
- Each user gets their own session
- Sessions don't interfere with each other
- LRU eviction works correctly when limit reached
- Session capacity management (10 max)

---

## 👥 Test Users

| Script | Username | Password | Purpose |
|--------|----------|----------|---------|
| `test_session_workflow.py` | jfernandez | taffie | User 1 (original) |
| `test_session_workflow_user2.py` | Gustavoa | Julian_1 | User 2 (new) |

---

## 🚀 Test Scenarios

### **Scenario 1: Sequential Testing (Basic)**

Run one user, then the other:

```bash
# Terminal 1
python test_session_workflow.py

# Wait for completion, then Terminal 2
python test_session_workflow_user2.py
```

**Expected:**
- User 1 creates session → 1/10 capacity
- User 1 completes
- User 2 creates session → 2/10 capacity
- Both sessions remain active

---

### **Scenario 2: Concurrent Testing (Advanced)**

Run both users at the same time:

```bash
# Terminal 1
python test_session_workflow.py

# Terminal 2 (start immediately, don't wait)
python test_session_workflow_user2.py
```

**Expected:**
- Both sessions created simultaneously
- Session capacity: 2/10
- No conflicts between sessions
- Each user's operations isolated

---

### **Scenario 3: Session Reuse**

Test that each user gets their own persistent session:

```bash
# Terminal 1 - User 1
python test_session_workflow.py
# Choose Mode 2, get 50 containers
# Note the session_id

# Terminal 2 - User 2
python test_session_workflow_user2.py
# Choose Mode 2, get 50 containers
# Note the session_id (should be different)

# Terminal 1 - User 1 again
python test_session_workflow.py
# Should reuse the same session_id from before!
```

**Expected:**
```
User 1 Session 1: session_XXX_111  (new)
User 2 Session 1: session_XXX_222  (new)
User 1 Session 2: session_XXX_111  (reused!) ← Same as User 1 Session 1
```

---

### **Scenario 4: Health Monitoring**

Monitor session capacity:

```bash
# Terminal 1 - Create User 1 session
python test_session_workflow.py
# After session created, press Enter to continue

# Terminal 2 - Check health
curl http://37.60.243.201:5010/health

# Should show:
# "session_capacity": "1/10"
# "persistent_sessions": 1

# Terminal 3 - Create User 2 session
python test_session_workflow_user2.py

# Terminal 2 - Check health again
curl http://37.60.243.201:5010/health

# Should show:
# "session_capacity": "2/10"
# "persistent_sessions": 2
```

---

### **Scenario 5: LRU Eviction (Stress Test)**

Test the 10-session limit:

1. Create 10 different user sessions (you'd need 10 test scripts)
2. Create an 11th session
3. Verify that the oldest (LRU) session is evicted
4. Check that capacity remains 10/10

**Quick Test:**
```bash
# Use the same credentials 10 times but with different session contexts
# The system should allow up to 10 concurrent sessions
```

---

## 📊 Expected Results

### **Health Check Output:**

```json
{
  "status": "healthy",
  "active_sessions": 2,
  "max_sessions": 10,
  "session_capacity": "2/10",
  "persistent_sessions": 2
}
```

### **User 1 Output:**
```
✅ Session Ready!
  📋 Session ID: session_1759683996_249140832508791461
  👤 Username: jfernandez
  
✅ Success! (took 2.3s)
  📋 Session ID: session_1759683996_249140832508791461
  🆕 Is New Session: false  ← Reused!
```

### **User 2 Output:**
```
✅ Session Ready!
  📋 Session ID: session_1759684123_987654321098765432
  👤 Username: Gustavoa
  
✅ Success! (took 2.1s)
  📋 Session ID: session_1759684123_987654321098765432
  🆕 Is New Session: false  ← Reused!
```

---

## 🔍 What to Verify

### **✅ Session Isolation**
- [ ] Each user has unique session_id
- [ ] User 1's operations don't affect User 2
- [ ] Sessions can run concurrently

### **✅ Session Persistence**
- [ ] Same user gets same session_id on second run
- [ ] `is_new_session: false` on reuse
- [ ] Session survives between requests

### **✅ Performance**
- [ ] First request: ~20-25s (login + operation)
- [ ] Second request: ~2-3s (no login!)
- [ ] **10x speed improvement** ⚡

### **✅ Capacity Management**
- [ ] Health check shows correct capacity
- [ ] Max 10 sessions enforced
- [ ] LRU eviction works when limit reached

### **✅ Session Refresh**
- [ ] Background task refreshes sessions
- [ ] Sessions stay alive (not logged out)
- [ ] Refresh happens every 5 minutes

---

## 🐛 Troubleshooting

### **Issue: Both users get same session_id**
**Problem:** Sessions matched by credentials  
**Expected:** Each user should get unique session based on username  
**Fix:** Check that credentials are different

### **Issue: Session killed after use**
**Problem:** Refresh detecting false logout  
**Expected:** Session should stay alive  
**Fix:** Check server logs for refresh errors

### **Issue: Capacity shows wrong number**
**Problem:** Sessions not being tracked  
**Expected:** Capacity should increment with each new session  
**Fix:** Restart API server

---

## 📝 Test Checklist

Run these tests in order:

1. ✅ **Sequential Test** - Run User 1, then User 2
2. ✅ **Concurrent Test** - Run both at same time
3. ✅ **Session Reuse** - Verify User 1 reuses session
4. ✅ **Health Monitoring** - Check capacity updates
5. ✅ **Performance** - Verify speed improvement

---

## 🎉 Success Criteria

**All tests pass if:**
- ✅ Each user gets unique session
- ✅ Sessions persist between requests
- ✅ Second request is 10x faster
- ✅ Capacity management works (X/10)
- ✅ No session conflicts
- ✅ Sessions stay alive (refresh works)

---

**Ready to test concurrency! Run both scripts simultaneously to see persistent session management in action!** 🚀

