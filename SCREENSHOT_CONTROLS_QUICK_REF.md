# Screenshot Label Controls - Quick Reference

## ✅ Current Setup
**VM Email is DISABLED by default** as requested!

---

## 🎛️ Quick Control

### **Enable/Disable Individual Fields**

```python
# Disable VM Email (already disabled by default)
operations.label_show_vm_email = False

# Enable VM Email
operations.label_show_vm_email = True

# Disable Username
operations.label_show_username = False

# Disable Platform
operations.label_show_platform = False

# Disable Container Info
operations.label_show_container = False

# Disable Date/Time
operations.label_show_datetime = False
```

---

## 📋 All 5 Control Flags

```python
operations.label_show_username   # Username field
operations.label_show_platform  # Platform field
operations.label_show_container  # Container info field
operations.label_show_datetime   # Date/time field
operations.label_show_vm_email    # VM Email field
```

---

## 🚀 Helper Method (Set Multiple at Once)

```python
# Enable VM Email
operations.set_screenshot_labels(vm_email=True)

# Show only Username and Platform
operations.set_screenshot_labels(
    username=True,
    platform=True,
    container=False,
    datetime=False,
    vm_email=False
)

# Show everything
operations.set_screenshot_labels(vm_email=True)
```

---

## 💡 Common Use Cases

### **Disable Everything Except Username**
```python
operations.set_screenshot_labels(
    username=True,
    platform=False,
    container=False,
    datetime=False,
    vm_email=False
)
```

### **Show Only Platform and Date**
```python
operations.set_screenshot_labels(
    username=False,
    platform=True,
    container=False,
    datetime=True,
    vm_email=False
)
```

### **Toggle VM Email On**
```python
operations.label_show_vm_email = True
```

### **Toggle VM Email Off**
```python
operations.label_show_vm_email = False
```

---

## 📸 Default Settings

| Field       | Default | Description |
|-------------|---------|-------------|
| Username    | ✅ True | Shows username |
| Platform    | ✅ True | Shows "Platform: emodal" |
| Container   | ✅ True | Shows container info |
| Date/Time   | ✅ True | Shows date and time |
| VM Email    | ❌ False | **DISABLED (as requested)** |

---

## 🔄 Where to Set Controls

```python
# In your endpoint or script
operations = EModalBusinessOperations(browser_session)

# Set controls before taking screenshots
operations.label_show_vm_email = False  # Disable VM Email

# Or use helper method
operations.set_screenshot_labels(vm_email=False)
```

---

## ✅ Status

- ✅ VM Email is DISABLED by default
- ✅ Easy to enable when needed
- ✅ Easy to disable when needed
- ✅ Helper method available for quick control
- ✅ All 5 fields individually controllable



