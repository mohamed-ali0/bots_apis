# Screenshot Labels Update - check_appointments Endpoint

## Summary of Changes

The screenshot annotation system has been updated with the following modifications:

### 1. **URL Replaced with Platform Name**
   - **Before:** Screenshots displayed the full URL (e.g., `https://ecp2.emodal.com/containers`)
   - **After:** Screenshots now display the hardcoded platform name: `emodal`

### 2. **Date Counters Removed**
   - **Before:** Import containers showed 3 date counter lines:
     - `Days from Manifested: X/4`
     - `Days from Departed: X/4`
     - `Days to Last Free Day: X/4`
   - **After:** All date counter lines have been completely removed

### 3. **VM Email Added**
   - **New Field:** `vm_email` (optional)
   - **Location:** Request body for `check_appointments` endpoint
   - **Display:** If provided, displays as `VM: {email}` in the screenshot label

---

## New Screenshot Label Format

### **Format:**
```
{username} | {timestamp} | Container: {container_id} | VM: {vm_email} | emodal
```

### **With VM Email:**
```
username123 | 2025-10-21 14:30:25 | Container: ABCD1234567 | VM: vm1@example.com | emodal
```

### **Without VM Email:**
```
username123 | 2025-10-21 14:30:25 | Container: ABCD1234567 | emodal
```

---

## API Changes

### **New Request Field**

The `check_appointments` endpoint now accepts an optional `vm_email` field:

```json
{
  "username": "your_username",
  "password": "your_password",
  "captcha_api_key": "your_api_key",
  "container_type": "import",
  "container_id": "ABCD1234567",
  "trucking_company": "Your Trucking Company",
  "terminal": "ITS Long Beach",
  "move_type": "DROP EMPTY",
  "pin_code": "1234",
  "truck_plate": "ABC123",
  "own_chassis": false,
  "vm_email": "vm1@example.com"  // ← NEW FIELD (optional)
}
```

### **Field Details**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vm_email` | string | No | Email address to display in screenshot labels. If not provided, the VM label will be omitted from screenshots. |

---

## Code Changes

### **Modified Files:**

1. **`emodal_business_api.py`**
   - `_capture_screenshot()` method (lines 800-862)
     - Removed all date counter logic
     - Replaced URL with hardcoded "emodal" platform name
     - Added vm_email to screenshot label if provided
   
   - `check_appointments()` endpoint (lines 6968-7074)
     - Added extraction of `vm_email` from request body
     - Set `operations.vm_email` for screenshot annotations
     - Removed date counter field assignments

### **New Files:**

1. **`testers/test_vm_email_screenshot.py`**
   - Test script demonstrating vm_email functionality
   - Tests both with and without vm_email field

2. **`documentation/SCREENSHOT_LABELS_UPDATE.md`**
   - This documentation file

---

## Backward Compatibility

### ✅ **Fully Backward Compatible**

- The `vm_email` field is **optional**
- If not provided, screenshots will not display the VM label
- All existing requests will continue to work without modification
- Date-related fields (`manifested_date`, `departed_date`, `last_free_day_date`) are now **ignored** if sent

---

## Testing

### **Test Script:**
```bash
cd testers
python test_vm_email_screenshot.py
```

### **Test Scenarios:**

1. **With vm_email provided:**
   - Screenshot should show: `username | timestamp | Container: XXX | VM: email@example.com | emodal`

2. **Without vm_email provided:**
   - Screenshot should show: `username | timestamp | Container: XXX | emodal`

3. **Date fields sent (should be ignored):**
   - No date counters should appear in screenshots
   - No errors should occur

---

## Benefits

### **1. Cleaner Screenshots**
   - More concise labels without lengthy URLs
   - No cluttered date counter lines
   - Only essential information displayed

### **2. VM Tracking**
   - Ability to identify which VM processed each appointment
   - Useful for distributed systems and load balancing
   - Optional field allows gradual adoption

### **3. Consistent Branding**
   - Hardcoded "emodal" platform name is consistent across all screenshots
   - No confusion from different URL formats

---

## Example Comparison

### **Before (Old Format):**
```
Days from Manifested: 3/4
Days from Departed: 1/4
Days to Last Free Day: 2/4
username123 | 2025-10-21 14:30:25 | Container: ABCD1234567 | https://ecp2.emodal.com/containers/appointments/...
```

### **After (New Format):**
```
username123 | 2025-10-21 14:30:25 | Container: ABCD1234567 | VM: vm1@example.com | emodal
```

---

## Notes

- The platform name "emodal" is **hardcoded** in the `_capture_screenshot()` method
- VM email is stored in `operations.vm_email` and only displayed if set
- All date-related logic has been completely removed from the screenshot annotation system
- The VM email label appears before the platform name in the screenshot

---

## Support

For questions or issues related to this update:
1. Check the test script: `testers/test_vm_email_screenshot.py`
2. Review the implementation in `emodal_business_api.py` (lines 800-862, 6968-7074)
3. Test with and without the `vm_email` field to verify behavior

---

**Last Updated:** October 21, 2025
**Version:** 1.0









