# Linux Server Setup Guide for E-Modal Automation

This guide helps you set up the E-Modal automation system on a Linux server (including non-GUI servers).

## System Requirements

- **Linux Distribution**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+ / RHEL 8+
- **RAM**: Minimum 2GB (4GB recommended)
- **Disk**: Minimum 2GB free space
- **Network**: Outbound internet access

## Installation Steps

### 1. Update System Packages

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Install System Dependencies

```bash
# Install Python 3.8+
sudo apt-get install -y python3 python3-pip python3-venv

# Install Xvfb (Virtual Framebuffer for non-GUI servers)
sudo apt-get install -y xvfb

# Install Chrome/Chromium
sudo apt-get install -y wget unzip

# Option A: Install Google Chrome (recommended)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Option B: Install Chromium (alternative)
# sudo apt-get install -y chromium-browser

# Install FFmpeg (for audio processing in reCAPTCHA)
sudo apt-get install -y ffmpeg

# Install additional dependencies
sudo apt-get install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1
```

### 3. Install ChromeDriver

```bash
# Download ChromeDriver (check Chrome version first)
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+')
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION%%.*}")

wget -N "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
rm chromedriver_linux64.zip

# Verify installation
chromedriver --version
```

### 4. Clone and Setup Project

```bash
# Clone or upload your project
cd /home/your_user/
# git clone <your-repo> emodal
# OR upload files manually

cd emodal

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
EMODAL_USERNAME=your_username
EMODAL_PASSWORD=your_password
CAPTCHA_API_KEY=your_2captcha_api_key
KEEP_BROWSER_ALIVE=true
INFINITE_SCROLLING=true
EOF

# Or export directly
export EMODAL_USERNAME="jfernandez"
export EMODAL_PASSWORD="taffie"
export CAPTCHA_API_KEY="5a0a4a97f8b4c9505d0b719cd92a9dcb"
export KEEP_BROWSER_ALIVE="true"
export INFINITE_SCROLLING="true"
```

## Running the Application

### Option 1: Direct Execution (Xvfb Auto-Start)

The application automatically detects Linux and starts Xvfb if no display is available:

```bash
# Start the API server
python emodal_business_api.py

# In another terminal, run tests
python test_business_api.py
```

### Option 2: Manual Xvfb Control

```bash
# Start Xvfb manually
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Start the API server
python emodal_business_api.py
```

### Option 3: Using xvfb-run Wrapper

```bash
# Run with xvfb-run
xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python emodal_business_api.py
```

## Testing the Setup

### 1. Test Health Endpoint

```bash
curl http://localhost:5000/health
```

### 2. Test Container Extraction

```bash
# With infinite scrolling (default)
curl -X POST http://localhost:5000/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "your_api_key",
    "keep_browser_alive": false,
    "infinite_scrolling": true
  }'

# Without infinite scrolling (first page only)
curl -X POST http://localhost:5000/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "your_api_key",
    "keep_browser_alive": false,
    "infinite_scrolling": false
  }'
```

### 3. Test Container Timeline

```bash
curl -X POST http://localhost:5000/get_container_timeline \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "your_api_key",
    "container_id": "MEDU7894898"
  }'
```

## Running as a Service (systemd)

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/emodal-api.service
```

```ini
[Unit]
Description=E-Modal Business API
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/emodal
Environment="PATH=/home/your_user/emodal/venv/bin"
Environment="EMODAL_USERNAME=your_username"
Environment="EMODAL_PASSWORD=your_password"
Environment="CAPTCHA_API_KEY=your_api_key"
ExecStart=/home/your_user/emodal/venv/bin/python emodal_business_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable emodal-api
sudo systemctl start emodal-api
sudo systemctl status emodal-api
```

### 3. View Logs

```bash
sudo journalctl -u emodal-api -f
```

## Troubleshooting

### Issue: Chrome crashes on startup

**Solution**: Add more shared memory

```bash
# Increase /dev/shm size
sudo mount -o remount,size=2G /dev/shm
```

### Issue: "Display not available" error

**Solution**: Ensure Xvfb is installed and DISPLAY is set

```bash
sudo apt-get install -y xvfb
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &
```

### Issue: ChromeDriver version mismatch

**Solution**: Update ChromeDriver to match Chrome version

```bash
google-chrome --version
# Download matching ChromeDriver version from:
# https://chromedriver.chromium.org/downloads
```

### Issue: Permission denied errors

**Solution**: Fix file permissions

```bash
chmod +x /usr/local/bin/chromedriver
sudo chown -R $USER:$USER /home/$USER/emodal
```

### Issue: Network errors / 403 Forbidden

**Solution**: Check VPN/proxy settings if E-Modal requires US access

```bash
# Test connectivity
curl -I https://ecp2.emodal.com/login
```

## Performance Tuning

### Optimize for High Load

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Increase kernel parameters
sudo sysctl -w net.core.somaxconn=1024
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=2048
```

### Memory Management

```bash
# Monitor memory usage
free -h
htop

# Set swap if needed
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## Security Recommendations

1. **Use environment variables** instead of hardcoding credentials
2. **Firewall**: Only expose port 5000 to trusted networks
3. **HTTPS**: Use nginx/apache as reverse proxy with SSL
4. **Rate limiting**: Implement rate limiting on API endpoints
5. **Monitoring**: Set up logging and monitoring

## API Parameters

### `/get_containers`

```json
{
  "username": "string (required)",
  "password": "string (required)",
  "captcha_api_key": "string (required)",
  "keep_browser_alive": "boolean (default: false)",
  "infinite_scrolling": "boolean (default: true)",
  "capture_screens": "boolean (default: false)",
  "screens_label": "string (default: username)",
  "return_url": "boolean (default: false)"
}
```

- **`infinite_scrolling`**: Set to `false` to only extract first page of containers (faster but incomplete)
- **`keep_browser_alive`**: Set to `true` to reuse browser session for multiple requests

## Support

For issues specific to Linux deployment, check:
- Chrome/ChromeDriver compatibility
- Xvfb display configuration
- System resource limits
- Firewall and network settings

## Additional Resources

- [Selenium on Linux](https://www.selenium.dev/documentation/)
- [Xvfb Documentation](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml)
- [Chrome Headless Options](https://peter.sh/experiments/chromium-command-line-switches/)
