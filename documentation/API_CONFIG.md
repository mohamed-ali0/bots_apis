# E-Modal API Configuration

## Server Configuration

### API Server
- **Host**: `0.0.0.0` (listens on all network interfaces)
- **Port**: `5010`
- **URL**: `http://<server-ip>:5010`

### Production Deployment
- **Public IP**: `89.117.63.196`
- **Full URL**: `http://89.117.63.196:5010`

## Default Settings

### Infinite Scrolling
- **Default**: `false` (disabled)
- **Behavior**: Only processes first page of containers for faster response
- **Override**: Set `"infinite_scrolling": true` in API request or `INFINITE_SCROLLING=true` environment variable

### Client Configuration
Test script automatically connects to `89.117.63.196:5010` by default.

## Environment Variables

### API Server (emodal_business_api.py)
```bash
# No environment variables needed for server
# Server always runs on 0.0.0.0:5010
```

### Test Client (test_business_api.py)
```bash
# API Connection
export API_HOST="89.117.63.196"  # Default: 89.117.63.196
export API_PORT="5010"            # Default: 5010

# Authentication
export EMODAL_USERNAME="jfernandez"
export EMODAL_PASSWORD="taffie"
export CAPTCHA_API_KEY="your_2captcha_key"

# Options
export KEEP_BROWSER_ALIVE="true"     # Default: false
export INFINITE_SCROLLING="false"    # Default: false (changed from true)
export AUTO_TEST="1"                 # Use env vars instead of prompts
```

## API Endpoints

### Base URL: `http://89.117.63.196:5010`

#### 1. Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "service": "E-Modal Business Operations API",
  "version": "1.0.0",
  "active_sessions": 0,
  "timestamp": "2025-10-02T..."
}
```

#### 2. Get Containers
```bash
POST /get_containers

Request:
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "your_key",
  "keep_browser_alive": false,
  "infinite_scrolling": false,  // false = first page only (faster)
  "capture_screens": true,
  "screens_label": "jfernandez",
  "return_url": true
}

Response:
{
  "success": true,
  "bundle_url": "http://89.117.63.196:5010/files/session_123.zip",
  "total_containers": "first_page_only",
  "scroll_cycles": 0,
  ...
}
```

#### 3. Get Container Timeline
```bash
POST /get_container_timeline

Request:
{
  "username": "jfernandez",
  "password": "taffie",
  "captcha_api_key": "your_key",
  "container_id": "MEDU7894898"
}

Response:
{
  "success": true,
  "container_id": "MEDU7894898",
  "status": "before_pregate",
  ...
}
```

#### 4. List Sessions
```bash
GET /sessions

Response:
{
  "success": true,
  "active_sessions": 1,
  "sessions": [...]
}
```

#### 5. Close Session
```bash
DELETE /sessions/<session_id>

Response:
{
  "success": true,
  "message": "Session closed"
}
```

## Usage Examples

### Start Server
```bash
# On server (89.117.63.196)
cd /path/to/emodal
python emodal_business_api.py

# Server starts on 0.0.0.0:5010
# Accessible via http://89.117.63.196:5010
```

### Run Test Client

#### From Same Server
```bash
export API_HOST="localhost"  # or "127.0.0.1"
export API_PORT="5010"
python test_business_api.py
```

#### From Remote Machine
```bash
# Uses default: 89.117.63.196:5010
python test_business_api.py

# Or specify different server
export API_HOST="192.168.1.100"
export API_PORT="5010"
python test_business_api.py
```

### Direct API Calls

#### Test from command line (Windows)
```powershell
# Health check
curl http://89.117.63.196:5010/health

# Get containers (first page only, no scrolling)
curl -X POST http://89.117.63.196:5010/get_containers `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"jfernandez\",\"password\":\"taffie\",\"captcha_api_key\":\"your_key\",\"infinite_scrolling\":false}'
```

#### Test from command line (Linux)
```bash
# Health check
curl http://89.117.63.196:5010/health

# Get containers (first page only, no scrolling)
curl -X POST http://89.117.63.196:5010/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "your_key",
    "infinite_scrolling": false
  }'
```

## Firewall Configuration

### On Server (89.117.63.196)
```bash
# Allow incoming connections on port 5010
sudo ufw allow 5010/tcp

# Or for firewalld
sudo firewall-cmd --permanent --add-port=5010/tcp
sudo firewall-cmd --reload
```

### On Cloud Provider
Ensure security group / network ACL allows:
- **Inbound**: TCP port 5010 from allowed IP ranges
- **Outbound**: HTTPS (443) for API calls to E-Modal and 2captcha

## Performance Notes

### Infinite Scrolling Impact
| Setting | Speed | Completeness | Use Case |
|---------|-------|--------------|----------|
| `infinite_scrolling: false` | **Fast** (30-60s) | First page only | Quick checks, testing |
| `infinite_scrolling: true` | Slow (90-180s) | All containers | Production, full export |

### Current Default: `false`
- Optimized for speed
- Only retrieves first page of containers
- Suitable for most use cases where complete data is not required
- Change to `true` when you need all containers

## Troubleshooting

### Cannot Connect to API
```bash
# Check if server is running
curl http://89.117.63.196:5010/health

# Check firewall
sudo ufw status
sudo netstat -tulpn | grep 5010

# Check server logs
# (in terminal where emodal_business_api.py is running)
```

### Test Script Connection Issues
```bash
# Verify API_HOST and API_PORT
echo $API_HOST
echo $API_PORT

# Test with explicit host
export API_HOST="89.117.63.196"
export API_PORT="5010"
python test_business_api.py
```

### Change API Target
```bash
# Connect to localhost instead
export API_HOST="localhost"
python test_business_api.py

# Connect to different server
export API_HOST="192.168.1.50"
export API_PORT="5010"
python test_business_api.py
```

## Security Considerations

1. **Network Security**: Port 5010 is exposed on public IP `89.117.63.196`
   - Consider using reverse proxy (nginx/apache) with SSL
   - Implement IP whitelisting if possible
   - Use VPN for production access

2. **Authentication**: API accepts credentials in request body
   - Credentials transmitted over HTTP (unencrypted)
   - **Recommendation**: Set up HTTPS/SSL for production

3. **Rate Limiting**: No rate limiting implemented
   - Consider adding rate limiting for production
   - Monitor for abuse

4. **API Keys**: 2captcha API key exposed in requests
   - Store securely
   - Rotate regularly
   - Monitor usage

## Production Deployment Checklist

- [ ] Set up HTTPS/SSL (recommended: Let's Encrypt + nginx reverse proxy)
- [ ] Configure firewall rules (allow only trusted IPs)
- [ ] Set up systemd service for auto-restart
- [ ] Configure log rotation
- [ ] Set up monitoring and alerting
- [ ] Implement rate limiting
- [ ] Set up backups for downloads directory
- [ ] Configure proper file permissions
- [ ] Set resource limits (memory, CPU)
- [ ] Test from all client locations

## Reference

- **Server Port**: `5010`
- **Server IP**: `89.117.63.196`
- **Default Scrolling**: `false` (first page only)
- **Test Script**: Auto-configured for `89.117.63.196:5010`


