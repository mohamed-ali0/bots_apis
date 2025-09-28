@echo off
echo E-Modal Automation API Installation
echo ====================================
echo.

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to install dependencies
    echo.
    echo Trying with python3...
    python3 -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo ❌ Installation failed. Please install manually:
        echo python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo ✅ Dependencies installed successfully!
echo.

echo Setup completed! 🎉
echo.
echo Next steps:
echo 1. Make sure Chrome browser is installed
echo 2. Download ChromeDriver from https://chromedriver.chromium.org/
echo 3. Run the API: python app.py
echo 4. Test the API: python test_api.py
echo.
pause


