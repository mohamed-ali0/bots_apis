# Bulk Container Information Endpoint - Complete Documentation

## Overview

The `/get_info_bulk` endpoint allows you to process multiple containers in a single API call, significantly improving efficiency for batch operations.

**Time Savings**: ~50% faster than individual API calls for multiple containers.

---

## Endpoint Details

```
POST /get_info_bulk
Content-Type: application/json
```

### Base URLs
- **Local**: `http://localhost:5010/get_info_bulk`
- **Remote**: `http://37.60.243.201:5010/get_info_bulk`

---

## What It Does

The endpoint processes containers based on their type:

| Container Type | Information Extracted | Use Case |
|----------------|----------------------|----------|
| **IMPORT** | Pregate status (passed/not passed) | Check if containers cleared pregate checkpoint |
| **EXPORT** | Booking number | Get booking reference for export shipments |

### Processing Flow

```
1. Authenticate (or reuse session)
2. Navigate to containers page
3. For each container:
   a. Search with infinite scrolling
   b. Expand container row
   c. Extract information (pregate/booking)
   d. Continue to next
4. Return all results in single response
```

---

## Request Format

### Basic Request (New Session)

```json
{
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_2captcha_api_key",
  "import_containers": ["MSDU8716455", "TCLU8784503"],
  "export_containers": ["TRHU1866154", "YMMU1089936"],
  "debug": false
}
```

### Request with Existing Session (Faster!)

```json
{
  "session_id": "session_1234567890",
  "import_containers": ["MSDU8716455", "TCLU8784503"],
  "export_containers": ["TRHU1866154", "YMMU1089936"],
  "debug": false
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Conditional* | E-Modal username |
| `password` | string | Conditional* | E-Modal password |
| `captcha_api_key` | string | Conditional* | 2captcha API key |
| `session_id` | string | Conditional* | Existing session ID (faster) |
| `import_containers` | array of strings | Conditional** | List of import container IDs |
| `export_containers` | array of strings | Conditional** | List of export container IDs |
| `debug` | boolean | No | Enable debug mode (default: false) |

*Either `session_id` OR credentials (`username`, `password`, `captcha_api_key`) required  
**At least one of `import_containers` or `export_containers` required

---

## Response Format

### Success Response

```json
{
  "success": true,
  "session_id": "session_1704623456_1234567890",
  "is_new_session": false,
  "message": "Bulk processing completed: 4 successful, 0 failed",
  "results": {
    "import_results": [
      {
        "container_id": "MSDU8716455",
        "success": true,
        "pregate_status": true,
        "pregate_details": "Container has passed Pregate"
      },
      {
        "container_id": "TCLU8784503",
        "success": true,
        "pregate_status": false,
        "pregate_details": "Container has not passed Pregate"
      }
    ],
    "export_results": [
      {
        "container_id": "TRHU1866154",
        "success": true,
        "booking_number": "RICFEM857500"
      },
      {
        "container_id": "YMMU1089936",
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

### Error Response

```json
{
  "success": false,
  "error": "Error message here"
}
```

### Response with Partial Failures

```json
{
  "success": true,
  "message": "Bulk processing completed: 3 successful, 1 failed",
  "results": {
    "import_results": [
      {
        "container_id": "MSDU8716455",
        "success": true,
        "pregate_status": true,
        "pregate_details": "Container has passed Pregate"
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

---

## Response Fields Reference

### Root Level

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Overall operation success |
| `session_id` | string | Session ID for reuse |
| `is_new_session` | boolean | True if new session created |
| `message` | string | Summary message |
| `results` | object | Detailed results |
| `debug_bundle_url` | string | Debug ZIP URL (if debug: true) |
| `error` | string | Error message (if failed) |

### Import Result Object

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container number |
| `success` | boolean | Processing success |
| `pregate_status` | boolean\|null | `true` = passed, `false` = not passed, `null` = unknown |
| `pregate_details` | string | Status details/message |
| `error` | string | Error (if success: false) |

### Export Result Object

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container number |
| `success` | boolean | Processing success |
| `booking_number` | string\|null | Booking number or null |
| `error` | string | Error (if success: false) |

### Summary Object

| Field | Type | Description |
|-------|------|-------------|
| `total_import` | integer | Import containers requested |
| `total_export` | integer | Export containers requested |
| `import_success` | integer | Successful imports |
| `import_failed` | integer | Failed imports |
| `export_success` | integer | Successful exports |
| `export_failed` | integer | Failed exports |

---

## Code Examples

### JavaScript/TypeScript

```typescript
// Using fetch API
async function getBulkInfo(containers: {
  import: string[],
  export: string[]
}) {
  const response = await fetch('http://37.60.243.201:5010/get_info_bulk', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: 'your_username',
      password: 'your_password',
      captcha_api_key: 'your_api_key',
      import_containers: containers.import,
      export_containers: containers.export,
      debug: false
    })
  });

  const data = await response.json();
  
  if (data.success) {
    console.log(`Processed ${data.results.summary.total_import + data.results.summary.total_export} containers`);
    
    // Process import results
    data.results.import_results.forEach(result => {
      if (result.success) {
        console.log(`${result.container_id}: Pregate ${result.pregate_status ? 'PASSED' : 'NOT PASSED'}`);
      } else {
        console.error(`${result.container_id}: Error - ${result.error}`);
      }
    });
    
    // Process export results
    data.results.export_results.forEach(result => {
      if (result.success) {
        console.log(`${result.container_id}: Booking ${result.booking_number || 'N/A'}`);
      } else {
        console.error(`${result.container_id}: Error - ${result.error}`);
      }
    });
    
    // Save session for reuse
    return data.session_id;
  } else {
    throw new Error(data.error);
  }
}

// Usage
const sessionId = await getBulkInfo({
  import: ['MSDU8716455', 'TCLU8784503'],
  export: ['TRHU1866154', 'YMMU1089936']
});

// Reuse session for next batch (faster!)
async function reuseSession(sessionId: string, containers: string[]) {
  const response = await fetch('http://37.60.243.201:5010/get_info_bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      import_containers: containers,
      debug: false
    })
  });
  
  return await response.json();
}
```

### Python

```python
import requests

def get_bulk_info(import_containers=None, export_containers=None, 
                   session_id=None, username=None, password=None, 
                   captcha_api_key=None):
    """
    Get bulk container information
    
    Args:
        import_containers: List of import container IDs
        export_containers: List of export container IDs
        session_id: Existing session ID (optional)
        username: E-Modal username (required if no session_id)
        password: E-Modal password (required if no session_id)
        captcha_api_key: 2captcha API key (required if no session_id)
    
    Returns:
        dict: Response data
    """
    url = 'http://37.60.243.201:5010/get_info_bulk'
    
    payload = {
        'import_containers': import_containers or [],
        'export_containers': export_containers or [],
        'debug': False
    }
    
    if session_id:
        payload['session_id'] = session_id
    else:
        payload.update({
            'username': username,
            'password': password,
            'captcha_api_key': captcha_api_key
        })
    
    response = requests.post(url, json=payload, timeout=600)
    return response.json()

# Usage
result = get_bulk_info(
    import_containers=['MSDU8716455', 'TCLU8784503'],
    export_containers=['TRHU1866154', 'YMMU1089936'],
    username='your_username',
    password='your_password',
    captcha_api_key='your_api_key'
)

if result['success']:
    # Process import results
    for container in result['results']['import_results']:
        if container['success']:
            status = 'PASSED' if container['pregate_status'] else 'NOT PASSED'
            print(f"{container['container_id']}: Pregate {status}")
        else:
            print(f"{container['container_id']}: Error - {container['error']}")
    
    # Process export results
    for container in result['results']['export_results']:
        if container['success']:
            booking = container['booking_number'] or 'N/A'
            print(f"{container['container_id']}: Booking {booking}")
        else:
            print(f"{container['container_id']}: Error - {container['error']}")
    
    # Save session for reuse
    session_id = result['session_id']
    
    # Next batch (faster with session reuse!)
    result2 = get_bulk_info(
        import_containers=['MEDU7724823'],
        session_id=session_id
    )
```

### PHP

```php
<?php
function getBulkInfo($params) {
    $url = 'http://37.60.243.201:5010/get_info_bulk';
    
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($params));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_TIMEOUT, 600);
    
    $response = curl_exec($ch);
    curl_close($ch);
    
    return json_decode($response, true);
}

// Usage
$result = getBulkInfo([
    'username' => 'your_username',
    'password' => 'your_password',
    'captcha_api_key' => 'your_api_key',
    'import_containers' => ['MSDU8716455', 'TCLU8784503'],
    'export_containers' => ['TRHU1866154', 'YMMU1089936'],
    'debug' => false
]);

if ($result['success']) {
    foreach ($result['results']['import_results'] as $container) {
        if ($container['success']) {
            $status = $container['pregate_status'] ? 'PASSED' : 'NOT PASSED';
            echo "{$container['container_id']}: Pregate $status\n";
        }
    }
    
    foreach ($result['results']['export_results'] as $container) {
        if ($container['success']) {
            $booking = $container['booking_number'] ?? 'N/A';
            echo "{$container['container_id']}: Booking $booking\n";
        }
    }
    
    // Save session for reuse
    $sessionId = $result['session_id'];
}
?>
```

---

## Best Practices

### 1. Batch Size

**Recommended**: 5-15 containers per request
```javascript
// Good
const batch1 = containers.slice(0, 15);
const batch2 = containers.slice(15, 30);

// Process in batches
const result1 = await getBulkInfo(batch1);
const result2 = await getBulkInfo(batch2, result1.session_id);
```

**Not Recommended**: 50+ containers in one request
```javascript
// Avoid - may timeout
const result = await getBulkInfo(allContainers); // 100 containers
```

### 2. Session Reuse

Always reuse sessions for multiple batches:
```javascript
// ✅ Good - Reuse session
const session = await createSession();
const batch1 = await processBulk(containers1, session);
const batch2 = await processBulk(containers2, session);
const batch3 = await processBulk(containers3, session);

// ❌ Bad - New session each time
const batch1 = await processBulk(containers1); // Creates new session
const batch2 = await processBulk(containers2); // Creates new session
const batch3 = await processBulk(containers3); // Creates new session
```

### 3. Error Handling

Handle both request-level and container-level errors:
```javascript
try {
  const result = await getBulkInfo(containers);
  
  if (!result.success) {
    // Request-level error
    console.error('Bulk request failed:', result.error);
    return;
  }
  
  // Check individual container results
  result.results.import_results.forEach(container => {
    if (!container.success) {
      // Container-level error
      console.error(`Container ${container.container_id} failed:`, container.error);
    }
  });
  
} catch (error) {
  // Network or other errors
  console.error('Request error:', error);
}
```

### 4. Timeout Configuration

Set adequate timeouts based on batch size:
```javascript
// Small batch (1-5 containers): 2 minutes
fetch(url, { ...options, timeout: 120000 });

// Medium batch (6-15 containers): 5 minutes
fetch(url, { ...options, timeout: 300000 });

// Large batch (16+ containers): 10 minutes
fetch(url, { ...options, timeout: 600000 });
```

### 5. Progress Tracking

For large batches, show progress to users:
```javascript
async function processBatchWithProgress(containers, onProgress) {
  const batchSize = 10;
  const batches = chunk(containers, batchSize);
  const results = [];
  
  for (let i = 0; i < batches.length; i++) {
    const result = await getBulkInfo(batches[i]);
    results.push(result);
    
    // Update progress
    const processed = (i + 1) * batchSize;
    const total = containers.length;
    onProgress(Math.min(processed, total), total);
  }
  
  return results;
}

// Usage
await processBatchWithProgress(containers, (current, total) => {
  console.log(`Processing: ${current}/${total} containers`);
  updateProgressBar((current / total) * 100);
});
```

---

## Performance Characteristics

### Timing Expectations

| Operation | Time (seconds) |
|-----------|----------------|
| Login (first request) | 15-20 |
| Per container (with session) | 5-10 |
| Small batch (5 containers) | 30-60 |
| Medium batch (10 containers) | 60-120 |
| Large batch (20 containers) | 120-240 |

### Comparison: Individual vs Bulk

**Scenario**: Process 10 containers

| Approach | Time | API Calls | Logins |
|----------|------|-----------|--------|
| Individual endpoints | ~3-4 min | 10 | 1 |
| Bulk endpoint | ~1-2 min | 1 | 1 |
| **Savings** | **~50%** | **90%** | **Same** |

---

## Error Codes and Messages

### Common Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "At least one of 'import_containers' or 'export_containers' must be provided" | Empty arrays | Provide at least one container |
| "Missing required fields: username, password, captcha_api_key" | No session_id and missing credentials | Provide session_id OR credentials |
| "Failed to navigate to containers page" | Navigation error | Retry or check session validity |
| "Container not found" | Container doesn't exist or not accessible | Verify container ID |
| "Failed to expand" | Expand operation failed | Container may be in unusual state |
| "Session not found or expired" | Invalid session_id | Create new session |

---

## Debug Mode

Enable debug mode to get screenshots and detailed logs:

```json
{
  "session_id": "session_123",
  "import_containers": ["MSDU8716455"],
  "debug": true
}
```

**Response includes**:
```json
{
  "success": true,
  "debug_bundle_url": "http://your-server.com/debug_bundles/debug_20250107_123456.zip",
  "results": { ... }
}
```

**Debug bundle contains**:
- Screenshots of each operation
- Browser console logs
- Detailed operation timeline
- Error traces if any

---

## Integration Checklist

- [ ] Set correct API base URL (local/remote)
- [ ] Store credentials securely (environment variables)
- [ ] Implement session management
- [ ] Handle timeouts appropriately
- [ ] Process both success and error responses
- [ ] Implement retry logic for failed containers
- [ ] Add progress indicators for user feedback
- [ ] Log errors for debugging
- [ ] Test with various batch sizes
- [ ] Implement rate limiting if needed

---

## Support and Troubleshooting

### Getting Help

1. **Check logs**: Look for detailed error messages
2. **Enable debug mode**: Get screenshots and full logs
3. **Test with single container**: Isolate issues
4. **Verify credentials**: Ensure login works
5. **Check session validity**: Sessions expire after 10 minutes

### Common Issues

**Issue**: Timeout errors
**Solution**: Reduce batch size or increase timeout

**Issue**: "Container not found"
**Solution**: Verify container exists in your account

**Issue**: Slow processing
**Solution**: Reuse sessions, reduce batch size

**Issue**: Inconsistent results
**Solution**: Enable debug mode to see what's happening

---

## Changelog

### Version 1.0 (Current)
- Initial release
- Support for import/export containers
- Session reuse
- Debug mode
- Batch processing
- Error isolation per container

---

## License and Usage

This API is part of the E-Modal Business Integration system. Use requires valid E-Modal account credentials and 2captcha API key for reCAPTCHA solving.

**Rate Limits**: Recommended maximum 100 containers per minute
**Session Limit**: Maximum 10 concurrent sessions per server

---

## Quick Reference Card

```
Endpoint: POST /get_info_bulk

Request:
{
  "session_id": "optional",
  "username": "required_if_no_session",
  "password": "required_if_no_session",
  "captcha_api_key": "required_if_no_session",
  "import_containers": ["CONTAINER1", "CONTAINER2"],
  "export_containers": ["CONTAINER3", "CONTAINER4"],
  "debug": false
}

Response:
{
  "success": true,
  "session_id": "session_id_for_reuse",
  "is_new_session": false,
  "results": {
    "import_results": [...],
    "export_results": [...],
    "summary": {
      "total_import": 2,
      "import_success": 2,
      "import_failed": 0,
      "total_export": 2,
      "export_success": 2,
      "export_failed": 0
    }
  }
}

Recommended batch size: 5-15 containers
Timeout: 10 minutes
Session reuse: Always recommended
```
