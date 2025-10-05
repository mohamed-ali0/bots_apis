#!/usr/bin/env python3
"""
Anti-Detection Configuration for E-Modal Automation
==================================================

Advanced anti-detection features to avoid Google's automation detection:
- Proxy/VPN support
- User agent rotation
- Fingerprint randomization
- Stealth mode configuration
"""

import random
import platform
import os
from typing import Dict, List, Optional, Tuple


class AntiDetectionConfig:
    """Advanced anti-detection configuration for Chrome automation"""
    
    def __init__(self, use_proxy: bool = False, proxy_config: Optional[Dict] = None):
        self.use_proxy = use_proxy
        self.proxy_config = proxy_config or {}
        
        # User agents for rotation
        self.user_agents = [
            # Windows Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            
            # macOS Chrome
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            
            # Linux Chrome
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        ]
        
        # Viewport sizes for randomization
        self.viewport_sizes = [
            (1920, 1080), (1366, 768), (1440, 900), (1536, 864),
            (1600, 900), (1280, 720), (1024, 768), (1280, 800)
        ]
        
        # Timezone options
        self.timezones = [
            "America/New_York", "America/Los_Angeles", "America/Chicago",
            "Europe/London", "Europe/Paris", "Europe/Berlin",
            "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"
        ]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        return random.choice(self.user_agents)
    
    def get_random_viewport(self) -> Tuple[int, int]:
        """Get a random viewport size"""
        return random.choice(self.viewport_sizes)
    
    def get_random_timezone(self) -> str:
        """Get a random timezone"""
        return random.choice(self.timezones)
    
    def get_stealth_chrome_options(self):
        """Get Chrome options with maximum stealth configuration"""
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        
        # === CORE STEALTH SETTINGS ===
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # === ANTI-DETECTION FEATURES ===
        # Disable automation indicators
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-prompt-on-repost")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")  # Faster loading
        
        # === FINGERPRINT RANDOMIZATION ===
        # Random user agent
        user_agent = self.get_random_user_agent()
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # Random viewport
        width, height = self.get_random_viewport()
        chrome_options.add_argument(f"--window-size={width},{height}")
        
        # Random timezone
        timezone = self.get_random_timezone()
        chrome_options.add_argument(f"--timezone={timezone}")
        
        # === PROXY CONFIGURATION ===
        if self.use_proxy and self.proxy_config:
            proxy_string = self._build_proxy_string()
            if proxy_string:
                chrome_options.add_argument(f"--proxy-server={proxy_string}")
                print(f"🌐 Using proxy: {proxy_string}")
        
        # === ADVANCED STEALTH ===
        # Disable automation flags
        chrome_options.add_argument("--disable-automation")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        
        # Memory and performance
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=4096")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        
        # === PRIVACY AND SECURITY ===
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-gpu-logging")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-login-animations")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # === EXPERIMENTAL OPTIONS ===
        prefs = {
            # Disable automation detection
            "credentials_enable_service": False,
            "password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2,
            
            # Randomize fingerprint
            "intl.accept_languages": "en-US,en;q=0.9",
            "profile.default_content_setting_values.media_stream_mic": 2,
            "profile.default_content_setting_values.media_stream_camera": 2,
            "profile.default_content_setting_values.geolocation": 2,
            
            # Download settings
            "download.default_directory": "/tmp",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # === PLATFORM-SPECIFIC OPTIMIZATIONS ===
        if platform.system() == 'Linux':
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-setuid-sandbox")
            chrome_options.add_argument("--disable-accelerated-2d-canvas")
            chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
            chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
            chrome_options.add_argument("--disable-accelerated-video-decode")
            chrome_options.add_argument("--disable-gpu-sandbox")
            chrome_options.add_argument("--disable-software-rasterizer")
        
        return chrome_options
    
    def _build_proxy_string(self) -> Optional[str]:
        """Build proxy string from configuration"""
        if not self.proxy_config:
            return None
        
        proxy_type = self.proxy_config.get('type', 'http').lower()
        host = self.proxy_config.get('host')
        port = self.proxy_config.get('port')
        username = self.proxy_config.get('username')
        password = self.proxy_config.get('password')
        
        if not host or not port:
            return None
        
        # Build proxy URL
        if username and password:
            proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"{proxy_type}://{host}:{port}"
        
        return proxy_url
    
    def get_stealth_js_scripts(self) -> List[str]:
        """Get JavaScript scripts to run for additional stealth"""
        return [
            # Remove webdriver property
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
            
            # Override automation detection
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})",
            
            # Randomize screen properties
            f"Object.defineProperty(screen, 'width', {{get: () => {random.randint(1200, 1920)}}})",
            f"Object.defineProperty(screen, 'height', {{get: () => {random.randint(800, 1080)}}})",
            
            # Override Chrome runtime
            "window.chrome = {runtime: {}}",
            
            # Randomize timezone
            f"Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {{value: () => ({{timeZone: '{self.get_random_timezone()}'}})}})",
        ]


def get_proxy_config_from_env() -> Optional[Dict]:
    """Get proxy configuration from environment variables"""
    proxy_host = os.environ.get('PROXY_HOST')
    proxy_port = os.environ.get('PROXY_PORT')
    proxy_type = os.environ.get('PROXY_TYPE', 'http')
    proxy_username = os.environ.get('PROXY_USERNAME')
    proxy_password = os.environ.get('PROXY_PASSWORD')
    
    if proxy_host and proxy_port:
        return {
            'type': proxy_type,
            'host': proxy_host,
            'port': proxy_port,
            'username': proxy_username,
            'password': proxy_password
        }
    return None


def get_vpn_config_from_env() -> Optional[Dict]:
    """Get VPN configuration from environment variables"""
    vpn_host = os.environ.get('VPN_HOST')
    vpn_port = os.environ.get('VPN_PORT')
    vpn_type = os.environ.get('VPN_TYPE', 'socks5')
    vpn_username = os.environ.get('VPN_USERNAME')
    vpn_password = os.environ.get('VPN_PASSWORD')
    
    if vpn_host and vpn_port:
        return {
            'type': vpn_type,
            'host': vpn_host,
            'port': vpn_port,
            'username': vpn_username,
            'password': vpn_password
        }
    return None


# Example usage configurations
PROXY_CONFIGS = {
    'residential_proxy': {
        'type': 'http',
        'host': 'proxy.example.com',
        'port': '8080',
        'username': 'user',
        'password': 'pass'
    },
    'socks5_proxy': {
        'type': 'socks5',
        'host': 'socks.example.com',
        'port': '1080',
        'username': 'user',
        'password': 'pass'
    },
    'vpn_config': {
        'type': 'socks5',
        'host': 'vpn.example.com',
        'port': '1080',
        'username': 'vpn_user',
        'password': 'vpn_pass'
    }
}
