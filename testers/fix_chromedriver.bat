@echo off
echo 🔧 ChromeDriver Fix Script
echo =========================

echo.
echo 🧹 Clearing corrupted cache...
if exist "%USERPROFILE%\.wdm" rmdir /s /q "%USERPROFILE%\.wdm"
if exist "%USERPROFILE%\.cache\selenium" rmdir /s /q "%USERPROFILE%\.cache\selenium"

echo.
echo 📦 Running Python fix script...
python fix_chromedriver.py

echo.
echo ✅ ChromeDriver fix completed!
pause

