# Bulk Endpoint - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Basic Request

```bash
curl -X POST http://37.60.243.201:5010/get_info_bulk \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password",
    "captcha_api_key": "your_api_key",
    "import_containers": ["MSDU8716455", "TCLU8784503"],
    "export_containers": ["TRHU1866154"],
    "debug": false
  }'
```

### 2. Response

```json
{
  "success": true,
  "session_id": "session_123",
  "results": {
    "import_results": [
      {"container_id": "MSDU8716455", "success": true, "pregate_status": true},
      {"container_id": "TCLU8784503", "success": true, "pregate_status": false}
    ],
    "export_results": [
      {"container_id": "TRHU1866154", "success": true, "booking_number": "RICFEM857500"}
    ],
    "summary": {
      "total_import": 2, "import_success": 2,
      "total_export": 1, "export_success": 1
    }
  }
}
```

---

## 📝 Code Snippets

### JavaScript
```javascript
const response = await fetch('http://37.60.243.201:5010/get_info_bulk', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'your_username',
    password: 'your_password',
    captcha_api_key: 'your_api_key',
    import_containers: ['MSDU8716455'],
    export_containers: ['TRHU1866154']
  })
});
const data = await response.json();
```

### Python
```python
import requests

response = requests.post('http://37.60.243.201:5010/get_info_bulk', json={
    'username': 'your_username',
    'password': 'your_password',
    'captcha_api_key': 'your_api_key',
    'import_containers': ['MSDU8716455'],
    'export_containers': ['TRHU1866154']
})
data = response.json()
```

---

## 🎯 Key Points

| What | How |
|------|-----|
| **Import containers** | Returns pregate status (passed/not passed) |
| **Export containers** | Returns booking number |
| **Session reuse** | Use `session_id` from response in next request (faster!) |
| **Batch size** | Recommended: 5-15 containers |
| **Timeout** | Set to 10 minutes |

---

## ⚡ Pro Tips

1. **Reuse sessions**: Include `session_id` from first response in subsequent requests
2. **Batch wisely**: Don't exceed 20 containers per request
3. **Handle errors**: Check both `success` field and individual container results
4. **Set timeouts**: 10 minutes recommended for large batches

---

## 📚 Full Documentation

See `BULK_ENDPOINT_DOCUMENTATION.md` for:
- Complete API reference
- All code examples
- Error handling
- Best practices
- Performance optimization
