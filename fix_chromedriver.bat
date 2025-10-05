@echo off
echo 🔧 ChromeDriver Architecture Fix
echo ================================
echo.

echo 🐍 Running Python fix script...
python fix_chromedriver.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ ChromeDriver fix completed successfully!
    echo 🚀 You can now run your automation scripts
) else (
    echo.
    echo ❌ ChromeDriver fix failed
    echo 💡 Try running as administrator or check your internet connection
)

echo.
pause
