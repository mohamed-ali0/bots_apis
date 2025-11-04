# Timeline Milestones in Bulk Info Endpoint

## Overview

The `/get_info_bulk` endpoint extracts **full timeline data** for **import containers** only. Each timeline contains multiple milestones with their dates and status.

---

## Timeline Milestones

The timeline milestones are extracted from the eModal system's visual timeline display. Here are all the possible milestones:

### **Import Container Milestones** (in reverse chronological order - newest first)

| # | Milestone Name | Description | Date Format | Status |
|---|----------------|-------------|-------------|--------|
| 1 | **Empty Received** | Empty container received at terminal | Date or `N/A` | completed/pending |
| 2 | **Empty released by customer** | Empty container released | Date or `N/A` | completed/pending |
| 3 | **Arrived at customer** | Container arrived at customer location | Date or `N/A` | completed/pending |
| 4 | **Departed Terminal** | Container departed from terminal | `MM/DD/YYYY HH:MM` or `N/A` | completed/pending |
| 5 | **Pregate** | Pregate milestone (import gate inspection) | Date or `N/A` | completed/pending |
| 6 | **Ready for pick up** | Container ready for pickup | Date or `N/A` | completed/pending |
| 7 | **Last Free Day** | Last free day (demurrage deadline) | `MM/DD/YYYY` or `N/A` | completed/pending |
| 8 | **Discharged** | Container discharged from vessel | Date or `N/A` | completed/pending |
| 9 | **Container Manifested** | Container manifested on vessel | `MM/DD/YYYY HH:MM` or `N/A` | completed/pending |

---

## Timeline Data Structure

Each milestone in the timeline array contains:

```json
{
  "milestone": "Milestone Name",
  "date": "MM/DD/YYYY HH:MM or N/A",
  "status": "completed or pending"
}
```

### **Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `milestone` | string | The name of the milestone (e.g., "Pregate", "Departed Terminal") |
| `date` | string | Date/time of the milestone or "N/A" if not available |
| `status` | string | Either "completed" (colored line) or "pending" (gray line) |

---

## Status Determination

The status is determined by the visual appearance of the timeline divider:

- **`completed`**: The timeline divider line is **colored** (blue/green) - milestone has been reached
- **`pending`**: The timeline divider line is **gray** - milestone has not been reached yet

The system checks the CSS class of the divider element:
- `dividerflowcolor` (without `horizontalconflow`) → **completed**
- `horizontalconflow` or `dividerflowcolor2` → **pending**

---

## Example Timeline Response

### **Full Import Container Timeline:**

```json
{
  "container_id": "MSDU8716455",
  "success": true,
  "pregate_status": true,
  "pregate_details": "Container passed pregate",
  "timeline": [
    {
      "milestone": "Empty Received",
      "date": "N/A",
      "status": "pending"
    },
    {
      "milestone": "Empty released by customer",
      "date": "N/A",
      "status": "pending"
    },
    {
      "milestone": "Arrived at customer",
      "date": "N/A",
      "status": "pending"
    },
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
      "milestone": "Discharged",
      "date": "N/A",
      "status": "completed"
    },
    {
      "milestone": "Container Manifested",
      "date": "03/04/2025 06:38",
      "status": "completed"
    }
  ],
  "milestone_count": 9
}
```

---

## Timeline Order

- **Order:** Reverse chronological (newest milestone first, oldest last)
- **Extraction:** The system extracts milestones from the bottom of the visual timeline upward
- **Reversal:** The array is reversed so the most recent milestone is at index 0

---

## Pregate Status

In addition to the timeline, the bulk info endpoint also provides:

- `pregate_status` (boolean): Whether the container has passed pregate inspection
- `pregate_details` (string): Human-readable description of pregate status

The pregate status is determined by checking if the "Pregate" milestone has a colored divider line.

---

## Export Containers

**Note:** Export containers in the bulk info endpoint **do NOT** include timeline data. They only return:

```json
{
  "container_id": "TRHU1866154",
  "success": true,
  "booking_number": "RICFEM857500"
}
```

---

## Date Formats

The timeline uses two date formats:

1. **Full DateTime:** `MM/DD/YYYY HH:MM` (e.g., "03/24/2025 13:10")
   - Used for: Container Manifested, Departed Terminal
   
2. **Date Only:** `MM/DD/YYYY` (e.g., "03/11/2025")
   - Used for: Last Free Day
   
3. **Not Available:** `N/A`
   - Used when the milestone date is not set or not applicable

---

## Milestone Count

The `milestone_count` field indicates the total number of milestones extracted from the timeline:

```json
{
  "milestone_count": 9
}
```

This count includes both completed and pending milestones.

---

## API Endpoints Using Timeline

The full timeline extraction is used in:

1. **`/get_info_bulk`** - Bulk processing (import containers only)
2. **`/get_container_timeline`** - Single container timeline extraction

---

## Implementation Details

### **Extraction Method:**

The timeline is extracted by:
1. Finding the `<app-containerflow>` or timeline container element
2. Locating all milestone rows (`div[@fxlayout='row']`)
3. For each row, extracting:
   - Milestone name (first `span.location-details-label`)
   - Date (second `span.location-details-label`)
   - Status (from `div.timeline-divider` CSS classes)
4. Reversing the array to show newest first

### **Code Location:**

- **Method:** `extract_full_timeline()` in `EModalBusinessOperations` class
- **File:** `emodal_business_api.py` (lines 4763-4851)

---

## Error Handling

If timeline extraction fails, the response will include:

```json
{
  "container_id": "XXXX1234567",
  "success": false,
  "error": "Timeline extraction failed: Timeline container not found"
}
```

Possible errors:
- "Timeline container not found" - Element not found on page
- "No timeline milestones found" - No milestones extracted
- Other parsing errors

---

## Use Cases

### **1. Tracking Container Progress**
Monitor which milestones have been completed and which are pending.

### **2. Pregate Verification**
Check if container has passed pregate inspection before scheduling pickup.

### **3. Last Free Day Monitoring**
Identify containers approaching demurrage deadlines.

### **4. Departure Tracking**
Know when containers departed the terminal.

### **5. Manifest Date Verification**
Verify when container was manifested on the vessel.

---

**Last Updated:** October 21, 2025  
**Version:** 1.0









