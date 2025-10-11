# Bulk Container Information API

## Endpoint
```
POST /get_info_bulk
```

## Description
Efficiently process multiple containers in a single request to extract information based on container type:
- **Import containers**: Get Pregate status (passed/not passed)
- **Export containers**: Get Booking number

This endpoint significantly reduces processing time by:
- Reusing a single browser session
- Sequential processing with automatic search, expand, extract, and collapse
- Returning all results in one response

## Use Case
Perfect for batch operations where you need to check multiple containers at once, such as:
- Daily import status checks
- Bulk booking number extraction for export shipments
- Mixed import/export container processing

---

## Request Format

### Headers
```
Content-Type: application/json
```

### Request Body (JSON)

#### Option 1: Using Existing Session
```json
{
    "session_id": "session_1234567890",
    "import_containers": ["MSCU5165756", "TRHU1866154"],
    "export_containers": ["MSDU5772413", "FFAU1969808"],
    "debug": false
}
```

#### Option 2: Creating New Session
```json
{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_2captcha_api_key",
    "import_containers": ["MSCU5165756", "TRHU1866154"],
    "export_containers": ["MSDU5772413", "FFAU1969808"],
    "debug": false
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | No* | Browser session ID to reuse existing session |
| `username` | string | No* | E-Modal username (required if no session_id) |
| `password` | string | No* | E-Modal password (required if no session_id) |
| `captcha_api_key` | string | No* | 2captcha API key (required if no session_id) |
| `import_containers` | array | No** | List of import container IDs to check Pregate status |
| `export_containers` | array | No** | List of export container IDs to get booking numbers |
| `debug` | boolean | No | If true, returns debug bundle with screenshots (default: false) |

*Either `session_id` OR authentication credentials are required  
**At least one of `import_containers` or `export_containers` must be provided

---

## Response Format

### Success Response (200 OK)

```json
{
    "success": true,
    "session_id": "session_1234567890",
    "is_new_session": false,
    "message": "Bulk processing completed: 4 successful, 0 failed",
    "results": {
        "import_results": [
            {
                "container_id": "MSCU5165756",
                "success": true,
                "pregate_status": true,
                "pregate_details": "Container has passed Pregate"
            },
            {
                "container_id": "TRHU1866154",
                "success": true,
                "pregate_status": false,
                "pregate_details": "Container has not passed Pregate"
            }
        ],
        "export_results": [
            {
                "container_id": "MSDU5772413",
                "success": true,
                "booking_number": "RICFEM857500"
            },
            {
                "container_id": "FFAU1969808",
                "success": true,
                "booking_number": null
            }
        ],
        "summary": {
            "total_import": 2,
            "total_export": 2,
            "import_success": 2,
            "import_failed": 0,
            "export_success": 2,
            "export_failed": 0
        }
    }
}
```

### With Debug Mode

```json
{
    "success": true,
    "session_id": "session_1234567890",
    "is_new_session": false,
    "message": "Bulk processing completed: 4 successful, 0 failed",
    "results": { ... },
    "debug_bundle_url": "http://your-server.com/debug_bundles/debug_20250107_123456.zip"
}
```

### Error Response (400/500)

#### Missing Containers
```json
{
    "success": false,
    "error": "At least one of 'import_containers' or 'export_containers' must be provided"
}
```

#### Authentication Error
```json
{
    "success": false,
    "error": "Missing required fields: username, password, captcha_api_key (or valid session_id)"
}
```

#### Processing Error
```json
{
    "success": false,
    "error": "Error details"
}
```

---

## Response Fields

### Root Level

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the bulk operation was successful |
| `session_id` | string | Browser session ID for reuse |
| `is_new_session` | boolean | Whether a new session was created |
| `message` | string | Summary message |
| `results` | object | Detailed results for all containers |
| `debug_bundle_url` | string | Debug ZIP URL (only when debug: true) |
| `error` | string | Error message (only when success: false) |

### Results Object

| Field | Type | Description |
|-------|------|-------------|
| `import_results` | array | Results for import containers |
| `export_results` | array | Results for export containers |
| `summary` | object | Summary statistics |

### Import Result Object

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container ID |
| `success` | boolean | Whether processing succeeded |
| `pregate_status` | boolean\|null | true = passed, false = not passed, null = unknown |
| `pregate_details` | string | Detailed status message |
| `error` | string | Error message (only when success: false) |

### Export Result Object

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container ID |
| `success` | boolean | Whether processing succeeded |
| `booking_number` | string\|null | Booking number or null if not available |
| `error` | string | Error message (only when success: false) |

### Summary Object

| Field | Type | Description |
|-------|------|-------------|
| `total_import` | integer | Total import containers requested |
| `total_export` | integer | Total export containers requested |
| `import_success` | integer | Successful import container checks |
| `import_failed` | integer | Failed import container checks |
| `export_success` | integer | Successful export container checks |
| `export_failed` | integer | Failed export container checks |

---

## Processing Flow

### For Import Containers
```
For each container:
1. Search container on page (with scrolling if needed)
2. Expand container row
3. Extract Pregate status from timeline
4. Collapse container row
5. Continue to next container
```

### For Export Containers
```
For each container:
1. Search container on page (with scrolling if needed)
2. Expand container row
3. Extract booking number from details
4. Collapse container row
5. Continue to next container
```

---

## Example Usage

### cURL Example

```bash
curl -X POST http://localhost:5010/get_info_bulk \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_2captcha_api_key",
    "import_containers": ["MSCU5165756", "TRHU1866154"],
    "export_containers": ["MSDU5772413"],
    "debug": false
  }'
```

### Python Example

```python
import requests

# Bulk processing with new session
response = requests.post('http://localhost:5010/get_info_bulk', json={
    'username': 'your_username',
    'password': 'your_password',
    'captcha_api_key': 'your_2captcha_api_key',
    'import_containers': ['MSCU5165756', 'TRHU1866154'],
    'export_containers': ['MSDU5772413', 'FFAU1969808'],
    'debug': False
}, timeout=600)

data = response.json()

if data['success']:
    print(f"Processed {len(data['results']['import_results'])} import containers")
    print(f"Processed {len(data['results']['export_results'])} export containers")
    
    # Check import pregate statuses
    for result in data['results']['import_results']:
        container = result['container_id']
        if result['success']:
            status = "PASSED" if result['pregate_status'] else "NOT PASSED"
            print(f"{container}: Pregate {status}")
        else:
            print(f"{container}: Error - {result['error']}")
    
    # Check export booking numbers
    for result in data['results']['export_results']:
        container = result['container_id']
        if result['success']:
            booking = result['booking_number'] or "Not available"
            print(f"{container}: Booking {booking}")
        else:
            print(f"{container}: Error - {result['error']}")
```

### Reusing Session

```python
# First request creates session
first_response = requests.post('http://localhost:5010/get_info_bulk', json={
    'username': 'your_username',
    'password': 'your_password',
    'captcha_api_key': 'your_2captcha_api_key',
    'import_containers': ['MSCU5165756'],
    'export_containers': ['MSDU5772413']
})

session_id = first_response.json()['session_id']

# Second request reuses session (faster!)
second_response = requests.post('http://localhost:5010/get_info_bulk', json={
    'session_id': session_id,
    'import_containers': ['TRHU1866154'],
    'export_containers': ['FFAU1969808']
})
```

---

## Performance

### Time Savings

**Without Bulk Endpoint** (individual API calls):
- Login: ~15-20 seconds
- Per container: ~10-15 seconds
- 10 containers: ~2-3 minutes

**With Bulk Endpoint**:
- Login (once): ~15-20 seconds
- Per container: ~5-10 seconds (shared session, no re-login)
- 10 containers: ~1-1.5 minutes

**Savings**: ~50% faster for bulk operations!

### Best Practices

1. **Batch Size**: Process 10-20 containers per request for optimal performance
2. **Session Reuse**: Always reuse sessions for multiple bulk operations
3. **Timeout**: Set adequate timeout (10+ minutes for large batches)
4. **Error Handling**: Individual container failures won't stop processing

---

## Error Handling

Individual container failures don't stop the entire bulk operation. Each container result is independent:

```json
{
    "success": true,
    "results": {
        "import_results": [
            {
                "container_id": "MSCU5165756",
                "success": true,
                "pregate_status": true
            },
            {
                "container_id": "INVALID123",
                "success": false,
                "error": "Container not found",
                "pregate_status": null
            }
        ]
    }
}
```

The overall `success: true` indicates the bulk operation completed, but check individual results for container-level errors.

---

## Testing

A comprehensive test script is provided: `test_bulk_info.py`

Run tests:
```bash
python test_bulk_info.py
```

The test script includes:
1. Bulk processing with new session
2. Bulk processing with existing session
3. Import containers only
4. Export containers only

---

## Notes

- Containers are processed sequentially (not in parallel)
- Session is automatically released after processing
- Debug mode captures screenshots for each container
- Both import and export lists can be empty arrays, but at least one must be provided
- Session can be reused across multiple bulk requests
- Maximum session timeout: 10 minutes of inactivity

---

## Comparison with Individual Endpoints

| Feature | Bulk Endpoint | Individual Endpoints |
|---------|---------------|---------------------|
| Containers per request | Unlimited | 1 |
| Session reuse | Automatic | Manual |
| Login overhead | Once per batch | Once per container |
| Response size | Single large response | Multiple small responses |
| Error handling | Per-container | Per-request |
| Best for | Batch operations | Single container checks |

---

## Summary

The `/get_info_bulk` endpoint is designed for efficient batch processing of containers:

✅ **Efficient**: Processes multiple containers in one session  
✅ **Flexible**: Supports both import and export containers  
✅ **Robust**: Individual failures don't stop processing  
✅ **Fast**: ~50% faster than individual API calls  
✅ **Reusable**: Session can be reused for multiple batches  
✅ **Detailed**: Returns individual results for each container
