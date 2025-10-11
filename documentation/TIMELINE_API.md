# Container Timeline API - Full Timeline Extraction

**Endpoint:** `/get_container_timeline`  
**Method:** `POST`  
**Description:** Extract complete container timeline with all milestones, dates, and status

---

## Request Format

### Working Mode (Default)
```json
{
  "session_id": "sess_abc123",
  "container_id": "MSCU5165756",
  "debug": false
}
```

### Debug Mode
```json
{
  "session_id": "sess_abc123",
  "container_id": "MSCU5165756",
  "debug": true
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Optional* | Existing session (skip login) |
| `username` | string | Optional* | Username (if no session_id) |
| `password` | string | Optional* | Password (if no session_id) |
| `captcha_api_key` | string | Optional* | Captcha key (if no session_id) |
| `container_id` | string | **Required** | Container ID to get timeline for |
| `debug` | boolean | Optional | `true` = debug bundle, `false` = data only (default) |

*Either `session_id` OR credentials (`username`, `password`, `captcha_api_key`) required

---

## Response Format

### Working Mode Response
```json
{
  "success": true,
  "session_id": "sess_abc123",
  "is_new_session": false,
  "container_id": "MSCU5165756",
  "passed_pregate": true,
  "timeline": [
    {
      "milestone": "Departed Terminal",
      "date": "03/24/2025 13:10",
      "status": "completed"
    },
    {
      "milestone": "Pregate",
      "date": "N/A",
      "status": "completed"
    },
    {
      "milestone": "Ready for pick up",
      "date": "N/A",
      "status": "completed"
    },
    {
      "milestone": "Last Free Day",
      "date": "03/11/2025",
      "status": "completed"
    },
    {
      "milestone": "Container Manifested",
      "date": "03/04/2025 06:38",
      "status": "completed"
    },
    {
      "milestone": "Arrived at customer",
      "date": "N/A",
      "status": "pending"
    }
  ],
  "milestone_count": 6,
  "detection_method": "dom_class_check"
}
```

### Debug Mode Response
Same as working mode, plus:
```json
{
  ...
  "debug_bundle_url": "http://37.60.243.201:5010/files/sess_abc123_20251009_123456_PREGATE.zip"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `session_id` | string | Browser session ID (persistent) |
| `is_new_session` | boolean | Whether session was newly created |
| `container_id` | string | Container ID processed |
| `passed_pregate` | boolean | Whether container passed Pregate |
| `timeline` | array | Array of milestone objects (newest first) |
| `milestone_count` | number | Total number of milestones |
| `detection_method` | string | How Pregate status was determined |
| `debug_bundle_url` | string | *(Debug only)* ZIP with screenshots |

### Timeline Object

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `milestone` | string | - | Milestone name |
| `date` | string | Date or "N/A" | Milestone date/time |
| `status` | string | `"completed"` or `"pending"` | Milestone status |

---

## Key Features

✅ **Full timeline extraction** - All milestones from start to finish  
✅ **Reverse chronological order** - Newest milestones first  
✅ **Status indicators** - Completed vs pending for each milestone  
✅ **Includes N/A dates** - Shows all milestones even without dates  
✅ **Fast working mode** - Data only, no screenshots  
✅ **Debug mode** - Optional ZIP with all screenshots  
✅ **Persistent sessions** - Reuse sessions across requests  

---

## Example Usage

### Python
```python
import requests

response = requests.post(
    "http://37.60.243.201:5010/get_container_timeline",
    json={
        "session_id": "sess_abc123",
        "container_id": "MSCU5165756"
    }
)

data = response.json()
for milestone in data['timeline']:
    print(f"{milestone['milestone']} - {milestone['date']} ({milestone['status']})")
```

