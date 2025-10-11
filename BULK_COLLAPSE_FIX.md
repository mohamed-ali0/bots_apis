# Bulk Endpoint - Container Collapse Fix

## Problem Identified ✅

In the `/get_info_bulk` endpoint, containers were being expanded to extract data but **never collapsed** afterward. This caused:

❌ The same expanded container to be parsed repeatedly  
❌ Incorrect data extraction for subsequent containers  
❌ Accumulated expanded rows causing page performance issues  

---

## Solution Implemented

### 1. New Method: `collapse_container_row()` 

**Location:** Lines 3965-4041 in `emodal_business_api.py`

**Features:**
- Finds the container row by container ID
- Checks if already collapsed (right arrow visible)
- Finds and clicks the down arrow (`keyboard_arrow_down`)
- Verifies collapse by checking for right arrow
- Returns success/failure status

**XPath Selectors Used:**
```python
".//mat-icon[normalize-space(text())='keyboard_arrow_down']"
".//mat-icon[normalize-space(text())='expand_less']"
".//button[contains(@aria-label,'collapse') or contains(@aria-label,'Collapse')]"
```

---

### 2. Integration in `/get_info_bulk`

**Import Containers (Lines 8106-8112):**
```python
# After extracting timeline and Pregate status
print(f"  🔽 Collapsing container row...")
collapse_result = operations.collapse_container_row(container_id)
if collapse_result.get("success"):
    print(f"  ✅ Container collapsed")
else:
    print(f"  ⚠️ Collapse warning: {collapse_result.get('error')}")
```

**Export Containers (Lines 8190-8196):**
```python
# After extracting booking number
print(f"  🔽 Collapsing container row...")
collapse_result = operations.collapse_container_row(container_id)
if collapse_result.get("success"):
    print(f"  ✅ Container collapsed")
else:
    print(f"  ⚠️ Collapse warning: {collapse_result.get('error')}")
```

---

## Workflow Comparison

### Before (Incorrect) ❌
```
1. Expand Container A → Extract data
2. Move to Container B
3. Expand Container B (but A is still expanded!)
4. Extract data (might extract A's data again)
5. Move to Container C...
```

### After (Correct) ✅
```
1. Expand Container A → Extract data → Collapse A
2. Move to Container B
3. Expand Container B → Extract data → Collapse B
4. Move to Container C
5. Expand Container C → Extract data → Collapse C
```

---

## Console Output Examples

**Successful Collapse:**
```
[1/3] Processing IMPORT: MSDU8716455
  ✅ Extracted 8 milestones
  ✅ Pregate: True
  🔽 Collapsing container row...
  ✅ Found container row
  ✅ Found collapse element via: .//mat-icon[normalize-space(text())='keyboard_arrow_down']
  ✅ JavaScript click executed on collapse element
  ✅ Collapse verified - arrow changed to right
  ✅ Container collapsed

[2/3] Processing IMPORT: TCLU8784503
  ✅ Extracted 6 milestones
  ✅ Pregate: False
  🔽 Collapsing container row...
  ✅ Container collapsed
```

**Already Collapsed:**
```
[3/3] Processing IMPORT: MEDU7724823
  ✅ Extracted 5 milestones
  ✅ Pregate: True
  🔽 Collapsing container row...
  ✅ Row is already collapsed (right arrow visible)
  ✅ Container collapsed
```

**Collapse Warning (Non-Critical):**
```
[1/2] Processing EXPORT: TRHU1866154
  ✅ Booking: RICFEM857500
  🔽 Collapsing container row...
  ⚠️ No collapse arrow found, row might already be collapsed
  ⚠️ Collapse warning: No arrow found (but processing continues)
```

---

## Method Details: `collapse_container_row()`

### Parameters
- `container_id` (str): The container ID to collapse

### Returns
```python
{
    "success": True/False,
    "collapsed": True/False,
    "method": "collapse_click" | "already_collapsed" | "no_arrow_found",
    "error": "Error message if failed"
}
```

### Return Methods
| Method | Description |
|--------|-------------|
| `already_collapsed` | Row was already collapsed (right arrow visible) |
| `no_arrow_found` | No collapse arrow found (likely already collapsed) |
| `collapse_click` | Successfully clicked and verified collapse |
| `collapse_click_unverified` | Click executed but verification failed |

---

## Error Handling

**Non-Critical Errors:**
- If collapse fails, a warning is logged but processing continues
- This prevents one collapse failure from stopping the entire bulk operation

**Example:**
```python
collapse_result = operations.collapse_container_row(container_id)
if collapse_result.get("success"):
    print(f"  ✅ Container collapsed")
else:
    print(f"  ⚠️ Collapse warning: {collapse_result.get('error')}")
# Processing continues regardless
```

---

## Testing Recommendations

### Test Case 1: Sequential Processing
```json
{
  "import_containers": ["MSDU8716455", "TCLU8784503", "MEDU7724823"],
  "session_id": "your_session_id"
}
```
**Expected:** Each container should be collapsed after extraction

### Test Case 2: Mixed Import/Export
```json
{
  "import_containers": ["MSDU8716455"],
  "export_containers": ["TRHU1866154"],
  "session_id": "your_session_id"
}
```
**Expected:** Both types should collapse properly

### Test Case 3: Large Batch
```json
{
  "import_containers": ["ID1", "ID2", "ID3", "ID4", "ID5", ...],
  "session_id": "your_session_id"
}
```
**Expected:** No accumulated expanded rows, consistent performance

---

## Performance Impact

✅ **Prevents DOM Bloat** - No accumulated expanded rows  
✅ **Consistent Speed** - Each operation works on a clean state  
✅ **Accurate Data** - Each container's data is extracted independently  
✅ **Memory Efficient** - Browser doesn't hold multiple expanded states  

---

## Key Changes Summary

| File | Lines | Change |
|------|-------|--------|
| `emodal_business_api.py` | 3965-4041 | Added `collapse_container_row()` method |
| `emodal_business_api.py` | 8106-8112 | Added collapse call for import containers |
| `emodal_business_api.py` | 8190-8196 | Added collapse call for export containers |

---

## Console Output Legend

| Icon | Meaning |
|------|---------|
| 🔽 | Starting collapse operation |
| ⤴️ | Collapsing row (internal log) |
| ✅ | Collapse successful |
| ⚠️ | Collapse warning (non-critical) |
| ❌ | Collapse failed |

---

**Status:** ✅ Fixed and Ready for Testing

The bulk endpoint now properly collapses each container after processing, ensuring accurate and independent data extraction for all containers in the batch.

