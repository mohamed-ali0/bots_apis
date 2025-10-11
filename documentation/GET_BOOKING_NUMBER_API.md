# Get Booking Number API Documentation

## Endpoint
```
POST /get_booking_number
```

## Description
Extracts booking number from an expanded container row on the E-Modal containers page. This endpoint searches for a specific container, expands it, and extracts the booking number from the detailed view.

## Request Format

### Headers
```
Content-Type: application/json
```

### Request Body (JSON)

#### Option 1: Using Existing Session
```json
{
    "session_id": "browser_session_12345",
    "container_id": "TRHU1866154",
    "debug": false
}
```

#### Option 2: Creating New Session
```json
{
    "username": "your_username",
    "password": "your_password", 
    "captcha_api_key": "your_2captcha_api_key",
    "container_id": "TRHU1866154",
    "debug": false
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No* | Browser session ID to reuse existing session |
| `username` | string | No* | E-Modal username (required if no session_id) |
| `password` | string | No* | E-Modal password (required if no session_id) |
| `captcha_api_key` | string | No* | 2captcha API key for reCAPTCHA solving (required if no session_id) |
| `container_id` | string | Yes | Container number to search for (e.g., "TRHU1866154") |
| `debug` | boolean | No | If true, returns debug bundle with screenshots (default: false) |

*Either `session_id` OR the authentication credentials (`username`, `password`, `captcha_api_key`) are required.

## Response Format

### Success Response (200 OK)

#### Normal Mode (debug: false)
```json
{
    "success": true,
    "booking_number": "RICFEM857500",
    "container_id": "TRHU1866154",
    "session_id": "browser_session_12345",
    "is_new_session": false,
    "message": "Booking number extracted successfully"
}
```

#### Debug Mode (debug: true)
```json
{
    "success": true,
    "booking_number": "RICFEM857500",
    "container_id": "TRHU1866154", 
    "session_id": "browser_session_12345",
    "is_new_session": false,
    "debug_bundle_url": "http://your-server.com/debug_bundles/debug_20250107_123456.zip",
    "message": "Booking number extracted successfully"
}
```

### Error Response (400/500)

#### Missing Container ID
```json
{
    "success": false,
    "error": "container_id is required",
    "session_id": "browser_session_12345",
    "is_new_session": false
}
```

#### Container Not Found
```json
{
    "success": false,
    "error": "Container TRHU1866154 not found after scrolling",
    "booking_number": null,
    "container_id": "TRHU1866154",
    "session_id": "browser_session_12345", 
    "is_new_session": false
}
```

#### Booking Number Not Available
```json
{
    "success": true,
    "booking_number": null,
    "container_id": "TRHU1866154",
    "session_id": "browser_session_12345",
    "is_new_session": false,
    "message": "Booking number not available for this container"
}
```

#### Authentication Error
```json
{
    "success": false,
    "error": "Login failed: Invalid credentials detected",
    "session_id": null,
    "is_new_session": false
}
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation was successful |
| `booking_number` | string\|null | Extracted booking number (e.g., "RICFEM857500") or null if not found |
| `container_id` | string | The container ID that was searched |
| `session_id` | string | Browser session ID (for reuse in subsequent requests) |
| `is_new_session` | boolean | Whether a new browser session was created |
| `debug_bundle_url` | string | URL to download debug bundle (only when debug: true) |
| `error` | string | Error message (only when success: false) |
| `message` | string | Additional information about the operation |

## Extraction Methods

The endpoint uses multiple methods to extract booking numbers:

1. **Method 1**: Direct HTML element search for "Booking #" label
2. **Method 2**: Search for clickable field-data elements
3. **Method 3**: Direct text search near "Booking #" label
4. **Method 4**: Look for blue/clickable text near booking section
5. **Method 5**: Full page text extraction with regex patterns
6. **Method 6**: Image-based OCR extraction (if Tesseract is installed)

## Example Usage

### cURL Example
```bash
curl -X POST http://localhost:5010/get_booking_number \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_2captcha_api_key", 
    "container_id": "TRHU1866154",
    "debug": false
  }'
```

### Python Example
```python
import requests

response = requests.post('http://localhost:5010/get_booking_number', json={
    'session_id': 'browser_session_12345',
    'container_id': 'TRHU1866154',
    'debug': False
})

data = response.json()
if data['success']:
    print(f"Booking number: {data['booking_number']}")
else:
    print(f"Error: {data['error']}")
```

## Notes

- The endpoint automatically creates persistent browser sessions that can be reused
- Sessions are kept alive for 10 minutes and can be reused across multiple requests
- The container search includes infinite scrolling to find containers not initially visible
- Debug mode provides screenshots and detailed logs for troubleshooting
- Booking numbers are typically 8-12 alphanumeric characters (e.g., "RICFEM857500")
- Some containers may not have booking numbers available
