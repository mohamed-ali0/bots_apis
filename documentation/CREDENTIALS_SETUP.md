# 🔐 Credentials Setup - Complete!

## ✅ What Was Done

The credentials from `test_business_api.py` have been **hardcoded** into `test_appointments.py` for easy testing.

---

## 📝 Hardcoded Credentials

The following credentials are now **built into the test script**:

```python
DEFAULT_USERNAME = "jfernandez"
DEFAULT_PASSWORD = "taffie"
DEFAULT_CAPTCHA_KEY = "5a0a4a97f8b4c9505d0b719cd92a9dcb"
```

---

## 🚀 How to Use

### **Just Run the Script!**

```bash
python test_appointments.py
```

### **No Setup Required!**

- ✅ **No environment variables needed**
- ✅ **No manual credential entry**
- ✅ **No configuration files**

The script will **automatically use** the hardcoded credentials.

---

## 🎯 Test Flow

```
1. Run: python test_appointments.py
   ↓
2. Choose option 1 (Check Appointments)
   ↓
3. Script automatically uses: jfernandez / taffie
   ↓
4. Press Enter for all defaults (or customize)
   ↓
5. Wait 2-3 minutes
   ↓
6. Get available appointment times!
```

---

## 📋 Default Test Values

When you press **Enter** for everything:

| Field | Default Value |
|-------|--------------|
| **Username** | `jfernandez` (hardcoded) |
| **Password** | `taffie` (hardcoded) |
| **2captcha Key** | `5a0a...9dcb` (hardcoded) |
| **Trucking Company** | `TEST TRUCKING` |
| **Terminal** | `ITS Long Beach` |
| **Move Type** | `DROP EMPTY` |
| **Container ID** | `CAIU7181746` |
| **Truck Plate** | `ABC123` |
| **PIN Code** | *(none)* |
| **Own Chassis** | `No` |

---

## 🔧 Override Credentials (Optional)

You can still override using environment variables:

```bash
export EMODAL_USERNAME="different_user"
export EMODAL_PASSWORD="different_pass"
export CAPTCHA_API_KEY="different_key"
```

But it's **not required** - the script will use hardcoded defaults if not set.

---

## ✨ What This Means

### **Before (Old Script)**
```
❌ Missing credentials. Set environment variables:
   EMODAL_USERNAME, EMODAL_PASSWORD, CAPTCHA_API_KEY
```

### **Now (Updated Script)**
```
✅ Using credentials for user: jfernandez

Enter trucking company name [default: TEST TRUCKING]:
```

**No credential prompts - just works!** 🎉

---

## 🧪 Quick Test

```bash
cd "C:\Users\Mohamed Ali\Downloads\emodal"
python test_appointments.py
```

Then:
1. Press **1** (Check Appointments)
2. Press **Enter** for all fields (use defaults)
3. Wait for results!

---

## 📦 Credentials Source

These credentials came from `test_business_api.py` lines 112-114:

```python
username = os.environ.get('EMODAL_USERNAME', 'jfernandez')
password = os.environ.get('EMODAL_PASSWORD', 'taffie')
api_key = os.environ.get('CAPTCHA_API_KEY', '5a0a4a97f8b4c9505d0b719cd92a9dcb')
```

---

## ✅ Ready to Test!

**No setup required - just run it!**

```bash
python test_appointments.py
```

The script is now **fully self-contained** with working credentials! 🚀


