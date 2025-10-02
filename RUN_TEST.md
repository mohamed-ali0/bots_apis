# 🧪 How to Test the Appointment Endpoints

## Quick Start

### Step 1: Start the API Server

```bash
cd "C:\Users\Mohamed Ali\Downloads\emodal"
python emodal_business_api.py
```

Wait for:
```
* Running on http://127.0.0.1:5010
* Running on http://89.117.63.196:5010
```

---

### Step 2: Run the Test Script

**Open a new terminal** and run:

```bash
cd "C:\Users\Mohamed Ali\Downloads\emodal"
python test_appointments.py
```

---

### Step 3: Select Test Type

```
======================================================================
  E-MODAL APPOINTMENT TESTING
======================================================================

Select test to run:
  1. Check Available Appointments (does NOT submit)
  2. Make Appointment (WILL SUBMIT)
  3. Exit

Enter choice (1-3):
```

**Choose option 1** for safe testing.

---

### Step 4: Enter Credentials

If credentials are not in environment variables, you'll be prompted:

```
📝 Credentials not found in environment variables
Enter E-Modal username: jfernandez
Enter E-Modal password: ********
Enter 2captcha API key: abc123...
```

---

### Step 5: Enter Form Data

The script will prompt for each field with sensible defaults:

```
Enter trucking company name [default: TEST TRUCKING]: 
Enter terminal [default: ITS Long Beach]: 
Enter move type [default: DROP EMPTY]: 
Enter container ID [default: CAIU7181746]: 
Enter truck plate [default: ABC123]: 
Enter PIN code (optional, press Enter to skip): 
Own chassis? (yes/no) [default: no]: 
```

Just press **Enter** to use defaults, or type custom values.

---

### Step 6: Wait for Results

```
📤 Sending request to /check_appointments...
   Trucking: TEST TRUCKING
   Terminal: ITS Long Beach
   Move Type: DROP EMPTY
   Container: CAIU7181746
   Truck Plate: ABC123
   PIN Code: No
   Own Chassis: No

⏳ This may take 2-3 minutes...
```

The system will:
1. Login to E-Modal
2. Navigate to appointment page
3. Fill Phase 1 form
4. Fill Phase 2 form
5. Get available appointment times from Phase 3

---

### Step 7: Review Results

```
📥 Response Status: 200

✅ SUCCESS!
   Available Times: 3

📅 Available Appointment Times:
   1. Thursday 10/02/2025 07:00 - 12:00
   2. Thursday 10/02/2025 13:00 - 18:00
   3. Friday 10/03/2025 07:00 - 12:00

📦 Debug Bundle: http://89.117.63.196:5010/files/session_123_..._check_appointments.zip
```

---

## 📦 Viewing Debug Bundle

1. Copy the debug bundle URL from the response
2. Open in browser: `http://89.117.63.196:5010/files/session_..._.zip`
3. Download and extract the ZIP file
4. Inside you'll find screenshots from every step:
   - `dropdown_trucking_opened.png`
   - `dropdown_trucking_selected.png`
   - `dropdown_terminal_opened.png`
   - `dropdown_terminal_selected.png`
   - `dropdown_move_opened.png`
   - `dropdown_move_selected.png`
   - `container_added.png`
   - `phase_2_loaded.png`
   - `checkbox_selected.png`
   - `truck_plate_entered.png`
   - `own_chassis_already_set.png`
   - `phase_3_loaded.png`
   - `appointment_dropdown_opened.png`
   - `appointment_times_retrieved.png`

---

## ⚠️ Testing /make_appointment (Production)

**ONLY use this when you want to ACTUALLY submit an appointment!**

1. Run `python test_appointments.py`
2. Choose option **2**
3. Type **`YES I WANT TO SUBMIT`** to confirm
4. Enter all credentials and form data
5. **IMPORTANT**: Enter exact appointment time from available times
6. The system will submit the appointment

---

## 🐛 Troubleshooting

### "Missing credentials"
→ Enter them manually or set environment variables:
```bash
export EMODAL_USERNAME="jfernandez"
export EMODAL_PASSWORD="password123"
export CAPTCHA_API_KEY="abc123..."
```

### Connection error
→ Make sure API server is running on port 5010

### Timeout error
→ Try again - reCAPTCHA solving can sometimes take longer

### "Dropdown not found"
→ Check debug bundle screenshots to see actual page state

### "Option not found"
→ Make sure dropdown values match exactly (case-sensitive)

---

## 📝 Example with Custom Values

```bash
Enter trucking company name [default: TEST TRUCKING]: ACME TRUCKING
Enter terminal [default: ITS Long Beach]: TTI Long Beach
Enter move type [default: DROP EMPTY]: PICK FULL
Enter container ID [default: CAIU7181746]: MSDU5772413
Enter truck plate [default: ABC123]: XYZ789
Enter PIN code (optional, press Enter to skip): 1234
Own chassis? (yes/no) [default: no]: yes
```

---

## ✅ Success Indicators

When it works, you'll see:
- ✅ Each dropdown selection confirmed
- ✅ Each input field filled confirmed
- ✅ Each phase completed
- ✅ Final list of available appointment times
- 📦 Debug bundle URL

---

## 🔗 More Documentation

- **`APPOINTMENT_ENDPOINTS.md`** - Full API documentation
- **`APPOINTMENT_QUICK_REFERENCE.md`** - Quick reference
- **`APPOINTMENT_IMPLEMENTATION_SUMMARY.md`** - Technical details

---

**Ready to test! Start with option 1 (Check Available Appointments) - it's completely safe!** 🚀

