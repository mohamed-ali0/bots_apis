# ChromeDriver Fix for Server Issues

## 🚨 Problem
The server is experiencing ChromeDriver issues:
```
ERROR: [WinError 193] %1 is not a valid Win32 application
```

This indicates a corrupted or incompatible ChromeDriver binary.

## 🔧 Quick Fix

### Option 1: Run Fix Script (Recommended)
```bash
# On the server, run:
python fix_chromedriver.py
```

### Option 2: Manual Cache Clear
```bash
# Clear webdriver-manager cache
rmdir /s /q "%USERPROFILE%\.wdm"
rmdir /s /q "%USERPROFILE%\.cache\selenium"

# Restart the API server
python emodal_business_api.py
```

### Option 3: Use Local ChromeDriver
The API now has fallback to local `chromedriver.exe` if webdriver-manager fails.

## 🛠️ What the Fix Does

### 1. **Enhanced Error Handling**
```python
# Try webdriver-manager first, with fallback to local chromedriver
try:
    # Clear any corrupted ChromeDriver cache
    cache_dir = os.path.expanduser("~/.wdm")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    service = Service(ChromeDriverManager().install())
    self.driver = webdriver.Chrome(service=service, options=chrome_options)
    print("✅ ChromeDriver initialized successfully with webdriver-manager")
except Exception as wdm_error:
    print(f"⚠️ WebDriver Manager failed: {wdm_error}")
    print("🔄 Trying local chromedriver.exe...")
    
    # Fallback to local chromedriver.exe
    local_chromedriver = os.path.join(os.getcwd(), "chromedriver.exe")
    if os.path.exists(local_chromedriver):
        service = Service(local_chromedriver)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ ChromeDriver initialized successfully with local chromedriver.exe")
```

### 2. **Cache Clearing**
- Clears `~/.wdm` directory (webdriver-manager cache)
- Clears `~/.cache/selenium` directory
- Forces fresh download

### 3. **Fallback Mechanism**
- **Primary**: webdriver-manager (auto-downloads matching version)
- **Fallback**: local `chromedriver.exe` in project directory
- **Error**: Clear error messages for both failures

## 📋 Server Commands

### Windows Server
```cmd
# Method 1: Python script
python fix_chromedriver.py

# Method 2: Batch script
fix_chromedriver.bat

# Method 3: PowerShell script
powershell -ExecutionPolicy Bypass -File fix_chromedriver.ps1
```

### Linux Server
```bash
# Clear cache
rm -rf ~/.wdm
rm -rf ~/.cache/selenium

# Run fix
python fix_chromedriver.py
```

## 🔍 Verification

After running the fix, you should see:
```
🚀 Initializing Chrome WebDriver...
📦 Auto-downloading matching ChromeDriver version...
🧹 Clearing ChromeDriver cache...
✅ ChromeDriver initialized successfully with webdriver-manager
```

Or if fallback is used:
```
⚠️ WebDriver Manager failed: [error details]
🔄 Trying local chromedriver.exe...
✅ ChromeDriver initialized successfully with local chromedriver.exe
```

## 🚀 API Restart

After fixing ChromeDriver, restart the API server:
```bash
python emodal_business_api.py
```

## 📊 Expected Results

- ✅ No more `[WinError 193]` errors
- ✅ Successful browser session creation
- ✅ Login process works normally
- ✅ Appointment endpoints functional

## 🔧 Troubleshooting

### If webdriver-manager still fails:
1. **Check Chrome version**: Make sure Chrome is installed and up-to-date
2. **Use local ChromeDriver**: Place `chromedriver.exe` in the project directory
3. **Manual download**: Download ChromeDriver manually from https://chromedriver.chromium.org/

### If local ChromeDriver fails:
1. **Check compatibility**: Ensure ChromeDriver version matches Chrome version
2. **Check permissions**: Ensure ChromeDriver is executable
3. **Check antivirus**: Some antivirus software blocks ChromeDriver

## 📝 Files Created

- `fix_chromedriver.py` - Python fix script
- `fix_chromedriver.bat` - Windows batch script  
- `fix_chromedriver.ps1` - PowerShell script
- `CHROMEDRIVER_FIX_SERVER.md` - This documentation

## ✅ Success Indicators

When the fix works, you'll see:
```
INFO:__main__:[check_appt_1759678497] Check appointments request for user: jfernandez
🌐 Creating browser session: session_1759678497_-9068772491849371675
🚀 Initializing Chrome WebDriver...
📦 Auto-downloading matching ChromeDriver version...
✅ ChromeDriver initialized successfully with webdriver-manager
✅ Browser session created successfully
```

Instead of:
```
ERROR:__main__:[check_appt_1759678497] Authentication failed: [WinError 193] %1 is not a valid Win32 application
```

