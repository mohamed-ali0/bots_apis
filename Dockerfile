# E-Modal Business Operations API - Linux Docker Container
FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set timezone
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    xvfb \
    python3 \
    python3-pip \
    python3-venv \
    gnupg \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install Python dependencies
RUN python3 -m venv venv \
    && . venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application code
COPY . .

# Create environment file template
RUN cp .env.example .env 2>/dev/null || echo "# Configure your environment variables" > .env

# Set up Chrome user data directory
RUN mkdir -p /app/.config/google-chrome

# Expose API port
EXPOSE 5000

# Set environment variables
ENV DISPLAY=:99
ENV CHROME_USER_DATA_DIR=/app/.config/google-chrome
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start script that handles display and runs the API
CMD ["bash", "-c", "Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 & sleep 2 && source venv/bin/activate && python emodal_business_api.py"]
