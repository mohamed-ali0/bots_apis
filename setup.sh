#!/bin/bash
# E-Modal Business Operations API - Linux Setup Script
# ==================================================

set -e  # Exit on any error

echo "🚀 E-Modal Business Operations API Setup (Linux)"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This script is designed for Linux systems only"
    print_info "For Windows, use: python -m pip install -r requirements.txt"
    exit 1
fi

print_info "Detected Linux system: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown")"

# Step 1: System Dependencies
echo ""
echo "🔧 Installing system dependencies..."
print_info "You may need to enter your sudo password"

# Update package lists
sudo apt-get update -qq

# Install essential packages
sudo apt-get install -y \
    wget \
    unzip \
    curl \
    xvfb \
    python3-pip \
    python3-venv \
    ffmpeg \
    || {
        print_error "Failed to install system dependencies"
        exit 1
    }

print_status "System dependencies installed"

# Step 2: Chrome/Chromium Installation
echo ""
echo "🌐 Setting up Chrome browser..."

# Check if Chrome is already installed
if command -v google-chrome &> /dev/null; then
    print_status "Google Chrome already installed: $(google-chrome --version)"
elif command -v chromium-browser &> /dev/null; then
    print_status "Chromium browser already installed: $(chromium-browser --version)"
else
    print_info "Installing Google Chrome..."
    
    # Add Google's signing key
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add - 2>/dev/null || {
        print_warning "Could not add Google signing key, trying Chromium instead..."
        sudo apt-get install -y chromium-browser
    }
    
    # Add Google Chrome repository
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list > /dev/null
    
    # Update and install
    sudo apt-get update -qq
    sudo apt-get install -y google-chrome-stable || {
        print_warning "Google Chrome installation failed, installing Chromium..."
        sudo apt-get install -y chromium-browser
    }
    
    print_status "Browser installed successfully"
fi

# Step 3: Python Virtual Environment
echo ""
echo "🐍 Setting up Python environment..."

if [ -d "venv" ]; then
    print_info "Virtual environment already exists"
else
    python3 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
print_info "Virtual environment activated"

# Step 4: Python Dependencies
echo ""
echo "📦 Installing Python dependencies..."

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

print_status "Python dependencies installed"

# Step 5: ChromeDriver Setup
echo ""
echo "🔧 Setting up ChromeDriver..."

# Get Chrome version
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+')
elif command -v chromium-browser &> /dev/null; then
    CHROME_VERSION=$(chromium-browser --version | grep -oP '\d+\.\d+\.\d+')
else
    print_error "No compatible browser found"
    exit 1
fi

print_info "Detected browser version: $CHROME_VERSION"

# Install compatible ChromeDriver using webdriver-manager (handled by Python)
python3 -c "
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

try:
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver_path = ChromeDriverManager().install()
    print(f'ChromeDriver installed at: {driver_path}')
    
    # Test driver
    driver = webdriver.Chrome(options=options)
    driver.quit()
    print('ChromeDriver test: SUCCESS')
except Exception as e:
    print(f'ChromeDriver setup error: {e}')
    exit(1)
"

print_status "ChromeDriver configured successfully"

# Step 6: Create Linux-specific test script
echo ""
echo "🧪 Creating test script..."

cat > test_linux_setup.py << 'EOF'
#!/usr/bin/env python3
"""
Test script for Linux E-Modal setup verification
"""
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def test_selenium():
    print("🧪 Testing Selenium setup...")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        driver = webdriver.Chrome(options=options)
        driver.get('https://www.google.com')
        title = driver.title
        driver.quit()
        
        print(f"✅ Selenium test passed - Page title: {title}")
        return True
    except Exception as e:
        print(f"❌ Selenium test failed: {e}")
        return False

def test_imports():
    print("📦 Testing Python imports...")
    try:
        import flask
        import selenium
        import requests
        print(f"✅ Flask: {flask.__version__}")
        print(f"✅ Selenium: {selenium.__version__}")
        print(f"✅ Requests: {requests.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 E-Modal Linux Setup Verification")
    print("===================================")
    
    success = True
    success &= test_imports()
    success &= test_selenium()
    
    if success:
        print("\n🎉 Setup verification completed successfully!")
        print("You can now run: python emodal_business_api.py")
    else:
        print("\n❌ Setup verification failed")
        sys.exit(1)
EOF

chmod +x test_linux_setup.py
print_status "Test script created"

# Step 7: Environment Configuration
echo ""
echo "⚙️  Creating environment configuration..."

cat > .env.example << 'EOF'
# E-Modal Business API Configuration
# Copy this file to .env and configure your settings

# 2captcha API Key (required for reCAPTCHA solving)
CAPTCHA_API_KEY=your_2captcha_api_key_here

# E-Modal Credentials
EMODAL_USERNAME=your_username
EMODAL_PASSWORD=your_password

# Browser Settings (Linux-specific)
CHROME_USER_DATA_DIR=/home/$(whoami)/.config/google-chrome
USE_VPN_PROFILE=true

# API Settings
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# Session Settings
SESSION_TIMEOUT=1800  # 30 minutes

# Linux Display (for headless environments)
DISPLAY=:99
EOF

print_status "Environment configuration created"

# Step 8: Create startup script
echo ""
echo "🚀 Creating startup script..."

cat > start_api.sh << 'EOF'
#!/bin/bash
# E-Modal Business API Startup Script (Linux)

# Activate virtual environment
source venv/bin/activate

# Set up display for headless environments (optional)
export DISPLAY=${DISPLAY:-:99}

# Start Xvfb if needed (for truly headless servers)
if ! pgrep -x "Xvfb" > /dev/null; then
    Xvfb :99 -screen 0 1024x768x24 &
    export XVFB_PID=$!
    echo "Started Xvfb with PID: $XVFB_PID"
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

echo "🚀 Starting E-Modal Business Operations API..."
python emodal_business_api.py

# Cleanup Xvfb if we started it
if [ ! -z "$XVFB_PID" ]; then
    kill $XVFB_PID 2>/dev/null
    echo "Stopped Xvfb"
fi
EOF

chmod +x start_api.sh
print_status "Startup script created"

# Step 9: Final Setup Verification
echo ""
echo "🔍 Running setup verification..."

# Test the setup
python test_linux_setup.py

echo ""
echo "🎉 Linux Setup Complete!"
echo "======================="
print_info "Virtual environment: $(pwd)/venv"
print_info "Startup script: ./start_api.sh"
print_info "Test script: ./test_linux_setup.py"

echo ""
echo "📋 Next Steps:"
echo "1. Copy .env.example to .env and configure your settings"
echo "2. Add your 2captcha API key and E-Modal credentials"
echo "3. Run: ./start_api.sh"

echo ""
echo "🔗 API Endpoints:"
echo "- http://localhost:5000/health"
echo "- http://localhost:5000/get_containers"
echo "- http://localhost:5000/sessions"

echo ""
print_warning "For VPN functionality, install Urban VPN extension in your Chrome browser manually"
print_info "Setup completed successfully! 🚀"


