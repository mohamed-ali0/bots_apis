# E-Modal Business API

Complete automation API for E-Modal trucking portal operations.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start API server
python emodal_business_api.py

# 3. Test the API
python test_all_endpoints.py
```

## 📚 Documentation

### Essential Docs (Start Here)
- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference with all endpoints
- **[Quick Reference](QUICK_REFERENCE.md)** - One-page cheat sheet for common operations
- **[Implementation Complete](IMPLEMENTATION_COMPLETE.md)** - Current status and features

### Technical Guides
- **[Proxy Authentication](PROXY_AUTHENTICATION.md)** - How proxy auto-auth works
- **[Persistent Sessions](PERSISTENT_SESSIONS_ALL_ENDPOINTS.md)** - Session management system
- **[LRU Session Management](LRU_SESSION_MANAGEMENT.md)** - Session eviction policy
- **[Changes Summary](CHANGES_SUMMARY.md)** - Recent changes log

### Testing
- **[Test All Endpoints](TEST_ALL_ENDPOINTS.md)** - Testing guide
- **[Test Session Workflow](TEST_SESSION_WORKFLOW.md)** - Session testing
- **[Test Concurrency](TEST_CONCURRENCY.md)** - Concurrent sessions

## 🎯 Features

### Core Operations
✅ **Container Management** - Get, search, filter container data (3 modes)  
✅ **Timeline Extraction** - Extract container timeline with Pregate detection  
✅ **Booking Numbers** - Retrieve booking numbers from container details  
✅ **Appointments** - Download appointment data (3 scrolling modes)  
✅ **Appointment Booking** - Check available times and make appointments  

### Advanced Features
✅ **Persistent Sessions** - Keep-alive sessions with automatic refresh  
✅ **LRU Eviction** - Intelligent session management (max 10 concurrent)  
✅ **Proxy Support** - Automatic residential proxy authentication  
✅ **Debug Mode** - Screenshot capture and debug bundles  
✅ **Auto Cleanup** - Automatic file cleanup after 24 hours  

## 🔌 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check API status |
| `/get_session` | POST | Create persistent session |
| `/get_containers` | POST | Get container data |
| `/get_container_timeline` | POST | Extract timeline |
| `/get_booking_number` | POST | Get booking number |
| `/get_appointments` | POST | Download appointments Excel |
| `/check_appointments` | POST | Get available times |
| `/make_appointment` | POST | Submit appointment |
| `/cleanup` | POST | Manual file cleanup |

## 📝 Quick Examples

### Health Check
```bash
curl http://localhost:5010/health
```

### Create Session
```bash
curl -X POST http://localhost:5010/get_session \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jfernandez",
    "password": "taffie",
    "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
  }'
```

### Get Containers
```bash
curl -X POST http://localhost:5010/get_containers \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xxx",
    "target_count": 100,
    "debug": false
  }'
```

### Check Appointments
```bash
curl -X POST http://localhost:5010/check_appointments \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xxx",
    "trucking_company": "TEST TRUCKING",
    "terminal": "ITS Long Beach",
    "move_type": "DROP EMPTY",
    "container_id": "CAIU7181746",
    "truck_plate": "ABC123",
    "own_chassis": false
  }'
```

## 🧪 Testing

### Run All Tests
```bash
python test_all_endpoints.py
```

### Test Specific Features
```bash
# Appointments
python test_get_appointments.py

# Session workflow
python test_session_workflow.py

# Appointment booking
python test_appointments.py

# Proxy extension
python test_proxy_extension.py
```

## ⚙️ Configuration

### Server URLs
```
Local:    http://localhost:5010
Remote 1: http://89.117.63.196:5010
Remote 2: http://37.60.243.201:5010  (default)
```

### Test Credentials
```
Username: jfernandez
Password: taffie
Captcha:  7bf85bb6f37c9799543a2a463aab2b4f
```

### System Limits
- **Max Sessions**: 10 concurrent Chrome windows
- **Session Refresh**: Every 5 minutes
- **File Cleanup**: Automatic after 24 hours
- **Appointment Session TTL**: 10 minutes

## 🗂️ Project Structure

```
emodal/
├── emodal_business_api.py       # Main API server
├── emodal_login_handler.py      # Login & driver setup
├── recaptcha_handler.py         # Captcha solving
├── requirements.txt             # Python dependencies
│
├── test_all_endpoints.py        # Test all endpoints
├── test_get_appointments.py     # Test appointments
├── test_session_workflow.py     # Test sessions
├── test_appointments.py         # Test booking
│
├── downloads/                   # Excel files
├── screenshots/                 # Debug screenshots
├── proxy_extension/             # Proxy auth files
│
├── API_DOCUMENTATION.md         # Complete API docs
├── QUICK_REFERENCE.md           # Quick reference
├── IMPLEMENTATION_COMPLETE.md   # Status summary
└── README.md                    # This file
```

## 🔧 Requirements

### Python Dependencies
```
flask>=2.3.0
selenium>=4.20.0
webdriver-manager>=4.0.1
requests>=2.31.0
pandas>=2.0.0
openpyxl>=3.1.0
pillow>=10.0.0
numpy>=1.24.0
python-dotenv>=1.0.0
undetected-chromedriver>=3.5.4
selenium-wire>=5.1.0
```

### System Requirements
- Python 3.8+
- Chrome browser
- Internet connection
- Proxy credentials (Oxylabs)
- 2captcha API key

## 🚨 Important Notes

1. **Session Reuse**: Always prefer reusing `session_id` to avoid login overhead
2. **Debug Mode**: Use sparingly in production (creates large files)
3. **Make Appointment**: ⚠️ Actually submits appointments - use carefully!
4. **Proxy**: Automatically configured (dc.oxylabs.io:8001)
5. **Cleanup**: Automatic every 24h, manual via `/cleanup` endpoint

## 📞 Support

### Documentation Files
- [API Documentation](API_DOCUMENTATION.md) - Complete reference
- [Quick Reference](QUICK_REFERENCE.md) - Cheat sheet
- [Proxy Setup](PROXY_AUTHENTICATION.md) - Proxy guide
- [Session Management](PERSISTENT_SESSIONS_ALL_ENDPOINTS.md) - Sessions
- [Testing Guide](TEST_ALL_ENDPOINTS.md) - Testing

### Common Issues

**Issue**: Session not found  
**Solution**: Create a new session or check if maximum capacity (10) reached

**Issue**: Proxy authentication prompt  
**Solution**: Verify proxy extension is created (`proxy_extension.zip`)

**Issue**: Captcha timeout  
**Solution**: Check 2captcha API key and account balance

**Issue**: Chrome version mismatch  
**Solution**: webdriver-manager auto-updates, or clear cache: `~/.wdm/`

## 🎯 Workflow Examples

### Simple Workflow
```python
import requests

# 1. Create session
response = requests.post('http://localhost:5010/get_session', json={
    'username': 'jfernandez',
    'password': 'taffie',
    'captcha_api_key': '7bf85bb6f37c9799543a2a463aab2b4f'
})
session_id = response.json()['session_id']

# 2. Get containers
response = requests.post('http://localhost:5010/get_containers', json={
    'session_id': session_id,
    'target_count': 50
})
print(response.json()['file_url'])

# 3. Get timeline
response = requests.post('http://localhost:5010/get_container_timeline', json={
    'session_id': session_id,
    'container_id': 'MSCU5165756'
})
print(response.json()['pregate_passed'])
```

### Appointment Booking Workflow
```python
# 1. Check available times (does NOT submit)
response = requests.post('http://localhost:5010/check_appointments', json={
    'session_id': session_id,
    'trucking_company': 'TEST TRUCKING',
    'terminal': 'ITS Long Beach',
    'move_type': 'DROP EMPTY',
    'container_id': 'CAIU7181746',
    'truck_plate': 'ABC123',
    'own_chassis': False
})
available_times = response.json()['available_times']

# 2. Make appointment (ACTUALLY SUBMITS)
response = requests.post('http://localhost:5010/make_appointment', json={
    'session_id': session_id,
    'trucking_company': 'TEST TRUCKING',
    'terminal': 'ITS Long Beach',
    'move_type': 'DROP EMPTY',
    'container_id': 'CAIU7181746',
    'truck_plate': 'ABC123',
    'own_chassis': False,
    'appointment_time': available_times[0]  # First available
})
```

## 🎉 Status

✅ **Production Ready**  
✅ **Fully Documented**  
✅ **Tested**  
✅ **All Features Working**

---

**Version**: 1.0  
**Last Updated**: 2025-10-06  
**Author**: E-Modal API Development Team
