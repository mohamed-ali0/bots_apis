# Booking Number Parser Test Script

## Overview
This script allows you to test the booking number extraction logic by pasting page text and seeing what booking numbers are found.

## Usage

### 1. Run the Script
```bash
python test_booking_parser.py
```

### 2. Paste Page Text
- Copy the page text from your browser (Ctrl+A, Ctrl+C)
- Paste it into the script
- Press Enter twice to finish input

### 3. View Results
The script will:
- Analyze the text structure
- Try multiple extraction methods
- Show all potential booking numbers found
- Highlight the primary booking number

## Example Output

```
🎯 BOOKING NUMBER PARSER TEST SCRIPT
==================================================

📝 Instructions:
1. Copy the page text from your browser
2. Paste it below (press Enter twice when done)
3. The script will extract the booking number

==================================================

📋 Paste the page text here:
[PASTE YOUR TEXT HERE]

✅ Text received (15420 characters)

📊 Text Structure Analysis:
📋 Total lines: 245
📋 Total characters: 15420

📍 Lines containing 'booking':
   Line 156: 'Booking #'
   Line 158: 'RICFEM857500'

==================================================
🎯 BOOKING NUMBER EXTRACTION
==================================================

🔍 Searching for booking number in text...
📋 Text length: 15420 characters
📋 First 200 characters: 'company-logo Port Manager product-logo Containers Container # Trade Type Status Holds Pregate Ticket# Emodal Pregate Status Gate Status Origin Destination Current Loc Line Vessel Name Vessel Code Voyage Size Type Fees LFD/GTD Tags MSNU3022554L IMPORT ON VESSEL YES N/A N/A N/A TTI N/A TTI MSCU MSC VITA 9702089 GO537N 20GP N/A N/A N/A...'

🔍 Method 1: Primary pattern search...
✅ Found booking number (method 1): RICFEM857500

==================================================
📊 RESULTS
==================================================

✅ PRIMARY BOOKING NUMBER: RICFEM857500

📋 ALL POTENTIAL BOOKING NUMBERS:
   ✅ 1. RICFEM857500
      2. MSNU3022554L
      3. MSDU4431979L
      4. MSNU8447490
      5. MSCU5165756L
      ...

==================================================
🎉 Test completed!
```

## Extraction Methods

The script uses the same 4 methods as the API:

1. **Primary Pattern**: `Booking\s*#\s*\n\s*[A-Z\s]+\n\s*([A-Z0-9]{8,12})`
   - Matches "Booking #" followed by status, then booking number

2. **Fallback Pattern**: `Booking\s*#\s*[^\w]*([A-Z0-9]{8,12})`
   - Matches "Booking #" followed by non-word chars, then booking number

3. **Line-by-Line Search**: 
   - Finds "Booking #" and checks next 3 lines for booking numbers

4. **General Patterns**: 
   - Finds any 8-12 character alphanumeric strings

## Testing Tips

1. **Copy Full Page**: Use Ctrl+A to select all text on the page
2. **Include Context**: Make sure to include the "Booking #" section
3. **Check Results**: Review all potential booking numbers found
4. **Verify Primary**: The primary booking number should be highlighted

## Troubleshooting

- **No booking number found**: Check if "Booking #" appears in the text
- **Wrong booking number**: Review the text structure analysis
- **Multiple matches**: The script shows all potential matches for review

## Files

- `test_booking_parser.py` - Main test script
- `BOOKING_PARSER_TEST_GUIDE.md` - This guide
