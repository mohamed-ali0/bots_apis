# Bulk Information Testing Guide

## Overview
This guide explains how to test the `/get_info_bulk` endpoint with actual container data from your E-Modal account.

## Important: Container IDs Must Be Real

⚠️ **The container IDs in the test script are placeholders!**

You **must** replace them with actual container IDs from your E-Modal account, otherwise the tests will fail because the containers don't exist.

---

## Step 1: Get Actual Container IDs

You have 3 options to find real container IDs:

### Option A: Use the Helper Script (Recommended)

```bash
python get_container_ids.py
```

This script will:
1. Connect to your E-Modal account
2. Fetch a list of containers
3. Download an Excel file with container IDs
4. Show you how to extract the IDs

The Excel file will have columns:
- **Container #**: The container ID (what you need!)
- **Trade Type**: IMPORT or EXPORT
- **Status**: GATE IN, GATE OUT, IN YARD, ON VESSEL, etc.

### Option B: Manual Lookup

1. Login to E-Modal manually: https://truckerportal.emodal.com
2. Go to **Containers** page
3. Look at your container list
4. Copy container IDs from the first column
5. Note which are IMPORT and which are EXPORT

### Option C: Use Existing Test Data

If you've already tested other endpoints, check:
- `test_get_booking_number.py` - Has container IDs
- `test_containers.py` - Has container IDs
- Any Excel files in `downloads/` folder

---

## Step 2: Update test_bulk_info.py

Open `test_bulk_info.py` and replace the placeholder container IDs:

```python
# BEFORE (placeholders):
IMPORT_CONTAINERS = [
    "MSCU5165756",  # Replace with actual import container
    "MSDU4431979",  # Replace with actual import container
]

EXPORT_CONTAINERS = [
    "TRHU1866154",  # Replace with actual export container
]

# AFTER (your real containers):
IMPORT_CONTAINERS = [
    "YOUR_IMPORT_CONTAINER_1",
    "YOUR_IMPORT_CONTAINER_2",
]

EXPORT_CONTAINERS = [
    "YOUR_EXPORT_CONTAINER_1",
]
```

### Container Selection Tips

**For IMPORT containers** (Pregate status testing):
- Choose containers with trade type = IMPORT
- Mix of different statuses is good (GATE IN, IN YARD, etc.)
- Ideally 2-3 containers

**For EXPORT containers** (Booking number testing):
- Choose containers with trade type = EXPORT
- Look for containers that have booking numbers
- Ideally 1-2 containers

**Example Real Container IDs** (format):
```
MSCU5165756  ← 4 letters + 7 digits
TRHU1866154  ← Standard format
MSDU4431979  ← Total 11 characters
```

---

## Step 3: Verify Configuration

Check the API URL and credentials in `test_bulk_info.py`:

```python
# API Configuration
API_BASE_URL = "http://37.60.243.201:5010"  # Remote server (default)
# API_BASE_URL = "http://localhost:5010"  # Uncomment for local testing

# Credentials
USERNAME = "Gustavoa"
PASSWORD = "Julian_1"
CAPTCHA_API_KEY = "7bf85bb6f37c9799543a2a463aab2b4f"
```

Update these if needed for your account.

---

## Step 4: Run the Tests

```bash
python test_bulk_info.py
```

### Expected Output

```
======================================================================
  🧪 E-Modal Bulk Info Testing Suite
======================================================================

API URL: http://37.60.243.201:5010
Username: Gustavoa

Starting Test 1...

======================================================================
  TEST 1: Bulk Processing with New Session
======================================================================

📦 Sending request to http://37.60.243.201:5010/get_info_bulk
   Import containers: 2
   Export containers: 1

⏱️  Response time: 45.23 seconds
📊 Status code: 200

✅ SUCCESS
   Session ID: session_1234567890
   New session: True
   Message: Bulk processing completed: 3 successful, 0 failed

📊 SUMMARY:
   Import: 2/2 successful
   Export: 1/1 successful
   Total Failed: 0

📥 IMPORT RESULTS:
   MSCU5165756: ✅ PASSED
      Details: Container has passed Pregate
   MSDU4431979: ❌ NOT PASSED
      Details: Container has not passed Pregate

📤 EXPORT RESULTS:
   TRHU1866154: ✅ Booking: RICFEM857500

...
```

---

## Understanding the Results

### Import Container Results

Each import container will show:
- **Container ID**: The container number
- **Success**: Whether processing succeeded
- **Pregate Status**: 
  - `✅ PASSED` - Container has passed pregate checkpoint
  - `❌ NOT PASSED` - Container has not passed pregate
  - `⚠️ UNKNOWN` - Status could not be determined
- **Details**: Additional information about the status

### Export Container Results

Each export container will show:
- **Container ID**: The container number
- **Success**: Whether processing succeeded
- **Booking Number**: 
  - `✅ Booking: RICFEM857500` - Booking number found
  - `⚠️ Booking: Not available` - No booking number
  - `❌ FAILED` - Error occurred

### Summary Statistics

```
📊 SUMMARY:
   Import: 2/2 successful    ← 2 out of 2 import containers processed
   Export: 1/1 successful    ← 1 out of 1 export containers processed
   Total Failed: 0           ← No failures
```

---

## Troubleshooting

### "Container not found"

**Problem**: The container ID doesn't exist in your account

**Solution**: 
1. Verify the container ID is correct
2. Check it exists in your E-Modal account
3. Update `test_bulk_info.py` with valid container IDs

### "Failed to expand"

**Problem**: Container exists but couldn't be expanded

**Solution**:
1. Check if the container is accessible
2. Try with a different container
3. Enable debug mode to see screenshots

### "Timeout"

**Problem**: Request took too long (> 10 minutes)

**Solution**:
1. Reduce the number of containers being tested
2. Check network connection to remote server
3. Increase timeout in the test script

### Enable Debug Mode

To see what's happening, enable debug mode:

```python
payload = {
    ...
    "debug": True  # ← Change to True
}
```

This will return a debug bundle ZIP with screenshots.

---

## Performance Expectations

### Normal Performance

| Containers | Expected Time |
|-----------|---------------|
| 1-2 containers | 20-30 seconds |
| 3-5 containers | 30-60 seconds |
| 6-10 containers | 60-120 seconds |
| 11-20 containers | 2-4 minutes |

### Factors Affecting Speed

- **Network latency** to remote server
- **Container search time** (scrolling if not visible)
- **Page load speed** on E-Modal
- **Number of containers** being processed

---

## Best Practices

### 1. Start Small
```python
# Test with 1-2 containers first
IMPORT_CONTAINERS = ["CONTAINER1"]
EXPORT_CONTAINERS = ["CONTAINER2"]
```

### 2. Use Session Reuse
```python
# Test 1: Create session
response1 = requests.post(..., json={
    "username": "...",
    "import_containers": ["CONTAINER1"]
})

session_id = response1.json()['session_id']

# Test 2: Reuse session (faster!)
response2 = requests.post(..., json={
    "session_id": session_id,
    "export_containers": ["CONTAINER2"]
})
```

### 3. Handle Errors Gracefully
```python
data = response.json()
for result in data['results']['import_results']:
    if result['success']:
        print(f"✅ {result['container_id']}: {result['pregate_status']}")
    else:
        print(f"❌ {result['container_id']}: {result['error']}")
```

### 4. Batch Wisely
- Don't process 100+ containers in one request
- Break into batches of 10-20 containers
- Reuse session across batches

---

## Example Workflow

```python
import requests

API_URL = "http://37.60.243.201:5010"
CREDENTIALS = {
    "username": "Gustavoa",
    "password": "Julian_1",
    "captcha_api_key": "7bf85bb6f37c9799543a2a463aab2b4f"
}

# Batch 1: First 10 containers
response1 = requests.post(f"{API_URL}/get_info_bulk", json={
    **CREDENTIALS,
    "import_containers": ["CONT1", "CONT2", ..., "CONT10"]
})

session_id = response1.json()['session_id']

# Batch 2: Next 10 containers (reuse session)
response2 = requests.post(f"{API_URL}/get_info_bulk", json={
    "session_id": session_id,
    "import_containers": ["CONT11", "CONT12", ..., "CONT20"]
})

# Process results
for batch_response in [response1, response2]:
    data = batch_response.json()
    for result in data['results']['import_results']:
        # Your processing logic here
        pass
```

---

## Summary

1. ✅ Get real container IDs using `get_container_ids.py`
2. ✅ Update `test_bulk_info.py` with actual container IDs
3. ✅ Verify credentials and API URL
4. ✅ Run tests: `python test_bulk_info.py`
5. ✅ Check results and handle errors

**Remember**: The test script uses **Remote Server** (`37.60.243.201:5010`) by default!
