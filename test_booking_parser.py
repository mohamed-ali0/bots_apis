#!/usr/bin/env python3
"""
Test script for booking number parser

This script allows you to paste page text and extract booking numbers
using the same logic as the /get_booking_number endpoint.
"""

import re
import sys
from typing import Optional, List

def extract_booking_number_from_text(text: str) -> Optional[str]:
    """
    Extract booking number from text using the same logic as the API.
    
    Args:
        text: The full page text to search
        
    Returns:
        Booking number string or None if not found
    """
    print("Searching for booking number in text...")
    print(f"Text length: {len(text)} characters")
    print(f"First 200 characters: '{text[:200]}...'")
    
    # Method 1: Line-by-line search (most reliable)
    print("\nMethod 1: Line-by-line search...")
    lines = text.split('\n')
    print(f"Total lines: {len(lines)}")
    
    for i, line in enumerate(lines):
        if 'Booking #' in line:
            print(f"Found 'Booking #' at line {i+1}: '{line.strip()}'")
            
            # Look for the pattern: Booking # -> Status -> Booking Number
            # Check the next few lines for a booking number pattern
            for j in range(1, 6):  # Check next 5 lines
                if i + j < len(lines):
                    potential_line = lines[i + j].strip()
                    print(f"   Checking line {i+j+1}: '{potential_line}'")
                    
                    # Check if this line contains a booking number pattern
                    if re.match(r'^[A-Z0-9]{8,12}$', potential_line):
                        print(f"SUCCESS: Found booking number (method 1): {potential_line}")
                        return potential_line
                    
                    # Also check if the line contains a booking number within it
                    booking_match = re.search(r'\b([A-Z0-9]{8,12})\b', potential_line)
                    if booking_match:
                        booking_number = booking_match.group(1)
                        print(f"SUCCESS: Found booking number in line (method 1): {booking_number}")
                        return booking_number
    
    # Method 2: Regex pattern - "Booking #" followed by status, then booking number
    print("\n🔍 Method 2: Regex pattern search...")
    booking_pattern = r'Booking\s*#\s*\n\s*[A-Z\s]+\n\s*([A-Z0-9]{8,12})'
    match = re.search(booking_pattern, text, re.MULTILINE)
    
    if match:
        booking_number = match.group(1).strip()
        print(f"✅ Found booking number (method 2): {booking_number}")
        return booking_number
    
    # Method 3: More flexible regex - "Booking #" followed by any text, then booking number
    print("\n🔍 Method 3: Flexible regex search...")
    booking_flexible_pattern = r'Booking\s*#\s*\n\s*.*?\n\s*([A-Z0-9]{8,12})'
    match = re.search(booking_flexible_pattern, text, re.MULTILINE | re.DOTALL)
    
    if match:
        booking_number = match.group(1).strip()
        print(f"✅ Found booking number (method 3): {booking_number}")
        return booking_number
    
    # Method 4: Find "Booking #" and get the next alphanumeric string
    print("\n🔍 Method 4: Next alphanumeric search...")
    booking_simple_pattern = r'Booking\s*#\s*[^\w]*([A-Z0-9]{8,12})'
    match = re.search(booking_simple_pattern, text)
    
    if match:
        booking_number = match.group(1).strip()
        print(f"✅ Found booking number (method 4): {booking_number}")
        return booking_number
    
    # Method 5: General booking number patterns (fallback)
    print("\n🔍 Method 5: General booking number patterns...")
    booking_patterns = [
        r'([A-Z]{2,4}[A-Z0-9]{6,10})',  # Pattern like RICFEM857500
        r'([A-Z0-9]{8,12})',            # General alphanumeric
        r'([A-Z]{3,6}[0-9]{4,8})',      # Letters followed by numbers
    ]
    
    for pattern in booking_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) >= 8:  # Booking numbers are usually at least 8 characters
                print(f"🎯 Found potential booking number (method 5): {match}")
                return match
    
    print("❌ No booking number found")
    return None

def find_all_booking_numbers(text: str) -> List[str]:
    """
    Find all potential booking numbers in the text.
    
    Args:
        text: The full page text to search
        
    Returns:
        List of all potential booking numbers found
    """
    print("\n🔍 Finding all potential booking numbers...")
    
    booking_numbers = []
    
    # Pattern for booking numbers (8-12 alphanumeric characters)
    pattern = r'\b([A-Z0-9]{8,12})\b'
    matches = re.findall(pattern, text)
    
    for match in matches:
        if match not in booking_numbers:
            booking_numbers.append(match)
    
    print(f"📋 Found {len(booking_numbers)} potential booking numbers:")
    for i, booking_num in enumerate(booking_numbers, 1):
        print(f"   {i}. {booking_num}")
    
    return booking_numbers

def analyze_text_structure(text: str):
    """
    Analyze the text structure to help understand the format.
    
    Args:
        text: The full page text to analyze
    """
    print("\n📊 Text Structure Analysis:")
    
    lines = text.split('\n')
    print(f"📋 Total lines: {len(lines)}")
    print(f"📋 Total characters: {len(text)}")
    
    # Find lines containing "Booking"
    booking_lines = []
    for i, line in enumerate(lines):
        if 'booking' in line.lower():
            booking_lines.append((i+1, line.strip()))
    
    if booking_lines:
        print(f"\n📍 Lines containing 'booking':")
        for line_num, line_content in booking_lines:
            print(f"   Line {line_num}: '{line_content}'")
    else:
        print("\n❌ No lines containing 'booking' found")
    
    # Show context around booking lines
    if booking_lines:
        print(f"\n📋 Context around booking lines:")
        for line_num, _ in booking_lines:
            start = max(0, line_num - 3)
            end = min(len(lines), line_num + 4)
            print(f"\n   Lines {start+1}-{end}:")
            for i in range(start, end):
                marker = ">>> " if i == line_num - 1 else "    "
                print(f"   {marker}{i+1:3d}: '{lines[i].strip()}'")

def main():
    """Main function"""
    print("🎯 BOOKING NUMBER PARSER TEST SCRIPT")
    print("=" * 50)
    
    print("\n📝 Instructions:")
    print("1. Copy the page text from your browser")
    print("2. Paste it below (press Enter twice when done)")
    print("3. The script will extract the booking number")
    print("\n" + "=" * 50)
    
    # Get text input from user
    print("\n📋 Paste the page text here:")
    lines = []
    empty_lines = 0
    
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
                if empty_lines >= 2:  # Two consecutive empty lines = end of input
                    break
            else:
                empty_lines = 0
            lines.append(line)
        except EOFError:
            break
    
    if not lines:
        print("❌ No text provided")
        return
    
    text = '\n'.join(lines)
    
    print(f"\n✅ Text received ({len(text)} characters)")
    
    # Analyze text structure
    analyze_text_structure(text)
    
    # Extract booking number
    print("\n" + "=" * 50)
    print("🎯 BOOKING NUMBER EXTRACTION")
    print("=" * 50)
    
    booking_number = extract_booking_number_from_text(text)
    
    # Find all potential booking numbers
    all_booking_numbers = find_all_booking_numbers(text)
    
    # Results
    print("\n" + "=" * 50)
    print("📊 RESULTS")
    print("=" * 50)
    
    if booking_number:
        print(f"✅ PRIMARY BOOKING NUMBER: {booking_number}")
    else:
        print("❌ No primary booking number found")
    
    if all_booking_numbers:
        print(f"\n📋 ALL POTENTIAL BOOKING NUMBERS:")
        for i, booking_num in enumerate(all_booking_numbers, 1):
            marker = "✅" if booking_num == booking_number else "  "
            print(f"   {marker} {i}. {booking_num}")
    
    print("\n" + "=" * 50)
    print("🎉 Test completed!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
