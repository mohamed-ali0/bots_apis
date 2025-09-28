# Linux Setup Guide for E-Modal Business Operations API

## 🐧 Quick Start (Linux)

### 1. Automated Setup (Recommended)
```bash
# Clone/download the project
cd emodal

# Make setup script executable
chmod +x setup.sh

# Run automated setup
./setup.sh
```

### 2. Manual Setup

#### System Dependencies
```bash
# Update system
sudo apt-get update

# Install required packages
sudo apt-get install -y wget unzip curl xvfb python3-pip python3-venv ffmpeg

# Install Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Alternative: Install Chromium
# sudo apt-get install -y chromium-browser
```

#### Python Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Add your credentials:
```env
CAPTCHA_API_KEY=your_2captcha_api_key
EMODAL_USERNAME=your_username
EMODAL_PASSWORD=your_password
```

### 3. Running the API

#### Standard Mode
```bash
# Activate virtual environment
source venv/bin/activate

# Start API
python emodal_business_api.py
```

#### With Startup Script
```bash
# Make executable
chmod +x start_api.sh

# Run
./start_api.sh
```

#### Headless Server Mode
```bash
# For servers without display
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
python emodal_business_api.py
```

## 🔧 Linux-Specific Features

### Browser Profile Detection
The API automatically detects Linux Chrome profiles:
- **Primary**: `~/.config/google-chrome`
- **Fallback**: `~/.config/chromium`

### Chrome Options (Linux-Optimized)
```python
# Automatically applied on Linux
--disable-gpu
--no-sandbox
--disable-dev-shm-usage
--remote-debugging-port=9222
--disable-background-timer-throttling
```

### Download Handling
- Uses `tempfile.mkdtemp()` for cross-platform compatibility
- Automatically configures Chrome download preferences for Linux
- Handles file permissions correctly

## 🐳 Docker Support

### Dockerfile
```dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl xvfb python3 python3-pip python3-venv \
    google-chrome-stable ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app
WORKDIR /app

# Setup Python environment
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install -r requirements.txt

# Expose port
EXPOSE 5000

# Start with display
CMD ["bash", "-c", "Xvfb :99 -screen 0 1024x768x24 & source venv/bin/activate && python emodal_business_api.py"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  emodal-api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DISPLAY=:99
      - CAPTCHA_API_KEY=${CAPTCHA_API_KEY}
      - EMODAL_USERNAME=${EMODAL_USERNAME}
      - EMODAL_PASSWORD=${EMODAL_PASSWORD}
    volumes:
      - ./downloads:/app/downloads
```

## 🚀 Testing

### Verify Setup
```bash
# Run verification script
python test_linux_setup.py

# Test API
curl http://localhost:5000/health
```

### Test Container Extraction
```bash
curl -X POST http://localhost:5000/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password", 
    "captcha_api_key": "your_key"
  }' \
  --output containers.xlsx
```

## 🔍 Troubleshooting

### Chrome Issues
```bash
# Check Chrome installation
google-chrome --version
chromium-browser --version

# Test Chrome headless
google-chrome --headless --no-sandbox --disable-gpu --dump-dom https://google.com
```

### Display Issues
```bash
# Check display
echo $DISPLAY

# Start Xvfb manually
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99
```

### Permission Issues
```bash
# Fix Chrome sandbox
sudo chown root:root /opt/google/chrome/chrome-sandbox
sudo chmod 4755 /opt/google/chrome/chrome-sandbox

# Alternative: Run with --no-sandbox (less secure)
```

### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📊 Performance Optimization (Linux)

### System Tuning
```bash
# Increase shared memory (for Chrome)
sudo mount -o remount,size=2G /dev/shm

# Adjust file limits
ulimit -n 4096
```

### Chrome Performance
```python
# Additional Linux-specific options
chrome_options.add_argument("--memory-pressure-off")
chrome_options.add_argument("--max_old_space_size=4096")
chrome_options.add_argument("--disable-background-timer-throttling")
```

## 🔐 Security (Production)

### Firewall
```bash
# Allow API port
sudo ufw allow 5000

# Restrict to specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 5000
```

### Service User
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash emodal-api
sudo su - emodal-api

# Install in user directory
cd /home/emodal-api
# ... setup process ...
```

### Systemd Service
```ini
[Unit]
Description=E-Modal Business Operations API
After=network.target

[Service]
Type=simple
User=emodal-api
WorkingDirectory=/home/emodal-api/emodal
Environment=DISPLAY=:99
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1024x768x24
ExecStart=/home/emodal-api/emodal/start_api.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📈 Monitoring

### Health Check
```bash
# Monitor API health
watch -n 30 'curl -s http://localhost:5000/health | jq'

# Check browser sessions
curl http://localhost:5000/sessions
```

### Logs
```bash
# API logs
tail -f emodal_api.log

# System logs
sudo journalctl -u emodal-api -f
```

## 🎯 Production Deployment

### Load Balancer (nginx)
```nginx
upstream emodal_api {
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;  # Multiple instances
}

server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://emodal_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Process Manager (supervisord)
```ini
[program:emodal-api]
command=/home/emodal-api/emodal/start_api.sh
directory=/home/emodal-api/emodal
user=emodal-api
autostart=true
autorestart=true
environment=DISPLAY=":99"
```

---

## ✅ Linux Compatibility Summary

- ✅ **Cross-platform file paths** using `os.path.join`
- ✅ **Linux Chrome profile detection** (`~/.config/google-chrome`, `~/.config/chromium`)  
- ✅ **Linux-optimized Chrome options** (`--disable-gpu`, `--no-sandbox`, etc.)
- ✅ **Headless server support** with Xvfb
- ✅ **System dependency management** (apt packages)
- ✅ **Virtual environment setup** with proper activation
- ✅ **Cross-platform download handling** using `tempfile`
- ✅ **Service deployment** with systemd
- ✅ **Docker containerization** support
- ✅ **Automated setup script** with verification

**The E-Modal Business Operations API is fully Linux-compatible and production-ready!** 🚀🐧
