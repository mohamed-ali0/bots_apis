# Bulk Info API - With Full Timeline for Import Containers

**Endpoint:** `/get_info_bulk`  
**Method:** `POST`  
**Description:** Bulk process multiple containers - extracts full timeline for import, booking number for export

---

## Request Format

```json
{
  "session_id": "sess_abc123",
  "import_containers": ["MSDU8716455", "TCLU8784503", "MEDU7724823"],
  "export_containers": ["TRHU1866154", "YMMU1089936"],
  "debug": false
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Optional* | Existing session (skip login) |
| `username` | string | Optional* | Username (if no session_id) |
| `password` | string | Optional* | Password (if no session_id) |
| `captcha_api_key` | string | Optional* | Captcha key (if no session_id) |
| `import_containers` | array | Optional** | List of import container IDs |
| `export_containers` | array | Optional** | List of export container IDs |
| `debug` | boolean | Optional | Debug mode (default: false) |

*Either `session_id` OR credentials required  
**At least one of `import_containers` or `export_containers` required

---

## Response Format

```json
{
  "success": true,
  "session_id": "sess_abc123",
  "is_new_session": false,
  "message": "Processed 3 import and 2 export containers",
  "results": {
    "import_results": [
      {
        "container_id": "MSDU8716455",
        "success": true,
        "pregate_status": true,
        "pregate_details": "Container passed pregate",
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
            "milestone": "Last Free Day",
            "date": "03/11/2025",
            "status": "completed"
          }
        ],
        "milestone_count": 3
      }
    ],
    "export_results": [
      {
        "container_id": "TRHU1866154",
        "success": true,
        "booking_number": "RICFEM857500"
      }
    ],
    "summary": {
      "total_import": 3,
      "total_export": 2,
      "import_success": 3,
      "import_failed": 0,
      "export_success": 2,
      "export_failed": 0
    }
  }
}
```

---

## Import Result Object

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container ID |
| `success` | boolean | Processing success |
| `pregate_status` | boolean | Whether container passed Pregate |
| `pregate_details` | string | Pregate status details |
| `timeline` | array | Full timeline (newest first) |
| `milestone_count` | number | Total milestones |
| `error` | string | Error message (if failed) |

---

## Export Result Object (Unchanged)

| Field | Type | Description |
|-------|------|-------------|
| `container_id` | string | Container ID |
| `success` | boolean | Processing success |
| `booking_number` | string/null | Booking number or null |
| `error` | string | Error message (if failed) |

