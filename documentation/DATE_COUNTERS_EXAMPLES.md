# Date Counters Feature - All Scenarios

## Overview
The `/check_appointments` endpoint now displays date counters for **import containers only** in all screenshots.

---

## Scenario 1: Both Dates Provided ✅

**Request:**
```json
{
  "container_type": "import",
  "manifested_date": "10/06/2025",
  "departed_date": "10/08/2025",
  "container_id": "MSCU5165756",
  ...
}
```

**Screenshot Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Days from Manifested: 4/4                                │
│ Days from Departed: 2/4                                  │
│ jfernandez | 2025-10-10 13:45:23 | Container: MSCU5165756│
│ https://truckerportal.emodal.com/...                     │
└──────────────────────────────────────────────────────────┘
```

**Console Output:**
```
📅 Manifested Date: 10/06/2025
📅 Departed Date: 10/08/2025
```

---

## Scenario 2: Only Manifested Date Provided

**Request:**
```json
{
  "container_type": "import",
  "manifested_date": "10/06/2025",
  "container_id": "MSCU5165756",
  ...
}
```

**Screenshot Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Days from Manifested: 4/4                                │
│ Days from Departed: ??/4 (N/A)                           │
│ jfernandez | 2025-10-10 13:45:23 | Container: MSCU5165756│
│ https://truckerportal.emodal.com/...                     │
└──────────────────────────────────────────────────────────┘
```

**Console Output:**
```
📅 Manifested Date: 10/06/2025
📅 Departed Date: N/A
```

---

## Scenario 3: Only Departed Date Provided

**Request:**
```json
{
  "container_type": "import",
  "departed_date": "10/08/2025",
  "container_id": "MSCU5165756",
  ...
}
```

**Screenshot Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Days from Manifested: ??/4 (N/A)                         │
│ Days from Departed: 2/4                                  │
│ jfernandez | 2025-10-10 13:45:23 | Container: MSCU5165756│
│ https://truckerportal.emodal.com/...                     │
└──────────────────────────────────────────────────────────┘
```

**Console Output:**
```
📅 Manifested Date: N/A
📅 Departed Date: 10/08/2025
```

---

## Scenario 4: No Dates Provided

**Request:**
```json
{
  "container_type": "import",
  "container_id": "MSCU5165756",
  ...
}
```

**Screenshot Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Days from Manifested: ??/4 (N/A)                         │
│ Days from Departed: ??/4 (N/A)                           │
│ jfernandez | 2025-10-10 13:45:23 | Container: MSCU5165756│
│ https://truckerportal.emodal.com/...                     │
└──────────────────────────────────────────────────────────┘
```

**Console Output:**
```
📅 Manifested Date: N/A
📅 Departed Date: N/A
```

---

## Scenario 5: Invalid Date Format

**Request:**
```json
{
  "container_type": "import",
  "manifested_date": "invalid-date",
  "departed_date": "10/08/2025",
  "container_id": "MSCU5165756",
  ...
}
```

**Screenshot Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Days from Manifested: ??/4 (Invalid date)                │
│ Days from Departed: 2/4                                  │
│ jfernandez | 2025-10-10 13:45:23 | Container: MSCU5165756│
│ https://truckerportal.emodal.com/...                     │
└──────────────────────────────────────────────────────────┘
```

---

## Scenario 6: Export Container (No Counters)

**Request:**
```json
{
  "container_type": "export",
  "booking_number": "RICFEM857500",
  ...
}
```

**Screenshot Display:**
```
┌────────────────────────────────────────────────────────────┐
│ jfernandez | 2025-10-10 13:45:23 | Container: RICFEM857500│
│ https://truckerportal.emodal.com/...                       │
└────────────────────────────────────────────────────────────┘
```

*Export containers show standard single-line annotation (no date counters)*

---

## Key Features

✅ **Always Shows Both Lines** - For import containers, both counters always appear  
✅ **??/4 for Missing Data** - Shows "??/4 (N/A)" when date not provided  
✅ **??/4 for Invalid Data** - Shows "??/4 (Invalid date)" when date cannot be parsed  
✅ **Flexible Date Formats** - Accepts `MM/DD/YYYY` or `YYYY-MM-DD` or any format recognized by dateutil  
✅ **Auto-Calculation** - Calculates days from date to current date  
✅ **Fixed Maximum** - Always shows `/4` as the maximum waiting period  
✅ **Import Only** - Only applies to `container_type: "import"`  
✅ **Export Unchanged** - Export containers show standard annotation  

---

## Date Format Examples

**Accepted Formats:**
- `10/06/2025` (MM/DD/YYYY)
- `2025-10-06` (YYYY-MM-DD)
- `Oct 6, 2025` (natural format)
- `2025/10/06` (YYYY/MM/DD)

**Calculation:**
```
Current Date: October 10, 2025
Manifested: October 6, 2025
Days Since: (10/10/2025 - 10/06/2025) = 4 days
Display: "Days from Manifested: 4/4"
```

---

## Implementation Notes

- Date counters are displayed **above** the existing annotation
- Multi-line text box automatically expands to fit all lines
- Each line is 30 pixels tall with proper spacing
- Background box is semi-transparent black (alpha 180)
- Text is white for maximum contrast
- All import screenshots will show these counters (Phase 1, 2, 3, errors, success)

---

## Request Fields (Import Only)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `manifested_date` | string | No | Date container was manifested |
| `departed_date` | string | No | Date container departed |

**Note:** Both fields are optional. If not provided, counters will show `??/4 (N/A)`

