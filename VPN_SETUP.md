# VPN/Proxy Setup Guide for E-Modal API

To avoid 403 errors from the E-Modal website, you need to route your requests through a US IP address. Here are your options:

## Option 1: VPN (Recommended for simplicity)

### Popular VPN Services:
1. **NordVPN** - Reliable, many US servers
2. **ExpressVPN** - Fast, good for automation
3. **Surfshark** - Affordable, unlimited devices
4. **CyberGhost** - User-friendly

### Steps:
1. Sign up for a VPN service
2. Install their app
3. Connect to a US server
4. Run the API normally (no proxy config needed)

### Test your VPN:
```bash
# Check your IP location
curl https://ipapi.co/json/

# Should show US location
```

## Option 2: HTTP/HTTPS Proxy

### Commercial Proxy Services:
1. **ProxyMesh** - $10/month, reliable
   - Format: `us.proxymesh.com:31280`
   - Requires username/password

2. **Bright Data** - Enterprise grade
   - Format: `brd.superproxy.io:22225` 
   - Requires authentication

3. **IPRoyal** - Affordable datacenter proxies
   - Format: `us.iproyal.com:8000`
   - Username/password authentication

### Usage Example:
```python
# Simple proxy
proxy_config = "us-proxy.example.com:8080"

# Authenticated proxy  
proxy_config = {
    "type": "http",
    "host": "us-proxy.example.com",
    "port": 8080,
    "username": "your_username", 
    "password": "your_password"
}
```

## Option 3: SOCKS Proxy

### Usage:
```python
proxy_config = {
    "type": "socks5",
    "host": "socks-proxy.example.com",
    "port": 1080,
    "username": "user",  # Optional
    "password": "pass"   # Optional
}
```

## Testing Your Setup

### 1. Start the VPN-enabled API:
```bash
python vpn_app.py
```

### 2. Check proxy info:
```bash
curl http://localhost:5000/proxy-info
```

### 3. Test with proxy:
```bash
curl -X POST http://localhost:5000/test-with-proxy \
  -H "Content-Type: application/json" \
  -d '{"proxy_config": "your-proxy.com:8080"}'
```

### 4. Test full login:
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie", 
    "proxy_config": "your-proxy.com:8080",
    "show_browser": true
  }'
```

## Free Proxy Options (Not Recommended)

Free proxies are unreliable and often blocked:
- https://free-proxy-list.net/
- https://www.proxy-list.download/
- https://spys.one/

## Troubleshooting

### Still getting 403 errors?
1. Verify your IP is US-based: https://whatismyipaddress.com/
2. Try different US proxy servers
3. Check if the proxy supports HTTPS
4. Some sites block known proxy IPs

### Browser not starting?
1. Make sure chromedriver.exe is in the folder
2. Try without proxy first: `{"proxy_config": null}`
3. Check Chrome browser is installed

### Proxy authentication issues?
1. Verify username/password are correct
2. Try simple proxy format first: `"host:port"`
3. Check if proxy requires IP whitelisting

## Recommended Workflow

1. **Development**: Use a VPN (NordVPN, ExpressVPN)
2. **Production**: Use dedicated proxy service (ProxyMesh, Bright Data)
3. **Testing**: Start without proxy, then add proxy configuration

## Cost Comparison

| Service | Type | Monthly Cost | Pros |
|---------|------|--------------|------|
| NordVPN | VPN | $3-12 | Easy setup, multiple devices |
| ProxyMesh | HTTP Proxy | $10 | Automation-friendly |
| Bright Data | Residential | $500+ | High success rate |
| IPRoyal | Datacenter | $7+ | Affordable |

For this E-Modal automation project, **NordVPN or ProxyMesh** are recommended for the best balance of cost and reliability.


