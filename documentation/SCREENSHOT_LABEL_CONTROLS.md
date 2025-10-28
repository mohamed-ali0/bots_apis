# Screenshot Label Controls - Easy Enable/Disable

## ✅ **Simple Control Over Screenshot Elements**

You can now easily control which fields appear on screenshots using simple boolean flags!

---

## 🎛️ **Control Flags**

Each screenshot element has its own control flag:

```python
operations.label_show_username = True   # Username
operations.label_show_platform = True   # Platform
operations.label_show_container = True  # Container info
operations.label_show_datetime = True   # Date and time
operations.label_show_vm_email = False  # VM Email (disabled by default)
```

---

## 🚀 **Easy Usage Examples**

### **Example 1: Disable VM Email (Current Setup)**
```python
# Already disabled by default!
operations.label_show_vm_email = False
```

### **Example 2: Enable VM Email When Needed**
```python
operations.label_show_vm_email = True
```

### **Example 3: Show Only Essential Fields**
```python
operations.label_show_username = True
operations.label_show_platform = True
operations.label_show_container = True
operations.label_show_datetime = False
operations.label_show_vm_email = False
```

### **Example 4: Show Everything**
```python
operations.label_show_username = True
operations.label_show_platform = True
operations.label_show_container = True
operations.label_show_datetime = True
operations.label_show_vm_email = True
```

### **Example 5: Hide Username Only**
```python
operations.label_show_username = False
# All other fields remain enabled
```

---

## 📋 **Helper Method - Easy Control**

Use the helper method to set multiple flags at once:

```python
# Enable all fields including VM email
operations.set_screenshot_labels(vm_email=True)

# Disable everything except username and platform
operations.set_screenshot_labels(username=True, platform=True, container=False, datetime=False, vm_email=False)

# Show only container info
operations.set_screenshot_labels(username=False, platform=False, container=True, datetime=False, vm_email=False)
```

---

## 🎯 **Method Signature**

```python
operations.set_screenshot_labels(
    username=True,    # Show username field (default: True)
    platform=True,    # Show platform field (default: True)
    container=True,   # Show container info field (default: True)
    datetime=True,    # Show date/time field (default: True)
    vm_email=False    # Show VM email field (default: False)
)
```

---

## 📸 **What Each Field Shows**

### **Username**
```
Username: jfernandez
```

### **Platform**
```
Platform: emodal
```

### **Container**
```
Container: TCLU8784503, import, DROP EMPTY
```
(or "Container: N/A" if no container info available)

### **Date and Time**
```
Date and time: 2025-01-11 | 14:30:45
```

### **VM Email**
```
VM Email: vm@example.com
```
(Only shown if enabled and provided)

---

## 🔧 **Where to Set These Controls**

### **Option 1: When Creating Operations Object**
```python
operations = EModalBusinessOperations(browser_session)
operations.label_show_vm_email = True  # Enable VM email
```

### **Option 2: After Initialization**
```python
operations.set_screenshot_labels(vm_email=True)
```

### **Option 3: In Endpoint Before Taking Screenshots**
```python
# In /check_appointments or /make_appointment endpoint
operations.label_show_vm_email = True  # Enable it for this session
```

---

## ✅ **Current Default Settings**

| Field | Default | Status |
|-------|---------|--------|
| Username | ✅ True | Enabled |
| Platform | ✅ True | Enabled |
| Container | ✅ True | Enabled |
| Date/Time | ✅ True | Enabled |
| VM Email | ❌ False | **Disabled** |

---

## 🎨 **Visual Examples**

### **With VM Email Disabled (Current)**
```
Username: jfernandez
Platform: emodal
Container: TCLU8784503, import, DROP EMPTY
Date and time: 2025-01-11 | 14:30:45
```

### **With VM Email Enabled**
```
Username: jfernandez
Platform: emodal
Container: TCLU8784503, import, DROP EMPTY
Date and time: 2025-01-11 | 14:30:45
VM Email: vm@example.com
```

### **Minimal Labels (Only Username & Platform)**
```
Username: jfernandez
Platform: emodal
```

---

## 💡 **Quick Reference**

### **Disable VM Email**
```python
operations.label_show_vm_email = False
```

### **Enable VM Email**
```python
operations.label_show_vm_email = True
```

### **Show Only Essential Info**
```python
operations.set_screenshot_labels(
    username=True,
    platform=True,
    container=True,
    datetime=False,
    vm_email=False
)
```

### **Custom Labels**
```python
# Whatever combination you want!
operations.set_screenshot_labels(
    username=True,
    platform=True,
    container=False,
    datetime=True,
    vm_email=False
)
```

---

## 🔄 **Per-Session Control**

Each `EModalBusinessOperations` object has its own label settings, so you can control labels differently for each request!

---

**Last Updated:** January 11, 2025  
**Status:** ✅ Ready to Use
