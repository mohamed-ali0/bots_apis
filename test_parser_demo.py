#!/usr/bin/env python3
"""
Demo script to test the improved booking number parser
"""

from test_booking_parser import extract_booking_number_from_text

def test_parser():
    """Test the parser with the exact pattern you provided"""
    
    # Test text with the exact pattern you described
    test_text = """
company-logo
Port Manager
product-logo
Containers
Container #
Trade Type
Status
Holds
Pregate Ticket#
Emodal Pregate Status
Gate Status
Origin
Destination
Current Loc
Line
Vessel Name
Vessel Code
Voyage
Size Type
Fees	
LFD/GTD
Tags	
MSNU3022554L	IMPORT	ON VESSEL	 YES	N/A	N/A	N/A	TTI	N/A	TTI	MSCU	MSC VITA	9702089	GO537N	20GP	
N/A
N/A
N/A
MSDU4431979L	IMPORT	GATE OUT	 NO	N/A	N/A	N/A	TTI	N/A	BNLPC	MSCU	MSC VICTORINE	9946867	G0508N	4310	
N/A
N/A
N/A
TRHU1866154L	EXPORT	GATE IN	 NO	N/A	N/A	N/A	N/A	TRP1	TRP1	ONEY	NMT	9337638	086E	20GP	
N/A
09/08/2025 - 09/08/2025
N/A
UNKNOWN
TRAPAC LLC-LOS ANGELES
Status
Booking #
GATE IN
RICFEM857500
Holds/Releases
Custom Hold
Custom Release
Line Hold
Line Release
Other Holds
LFD
Good Through
No
N/A
No
N/A
No
09/08/2025
09/08/2025
Fees
Arrival Information
Arrival Carrier
Truck #
Trucker Scac
Driver Name
Pregate Time
Pregate Status
Rail Number
N/A
N/A
N/A
N/A
N/A
N/A
N/A
Departure Information
Departure Carrier
Line
Vessel Code/Voyage
VESSEL
ONEY
9337638/086E
Other Information
Haz
OD
Reefer
Yard Location
Weight
UOM
Yard Status
N/A
N/A
NO
#991
30480
Kilograms
N/A
Loaded
N/A
Terminal In-Gate
N/A
Load Departure
N/A
Empty Received
N/A
Empty Pickup
N/A
"""
    
    print("TESTING IMPROVED BOOKING NUMBER PARSER")
    print("=" * 50)
    print("Test text contains the exact pattern:")
    print("   Booking #")
    print("   GATE IN")
    print("   RICFEM857500")
    print("   Holds/Releases")
    print("=" * 50)
    
    # Test the parser
    result = extract_booking_number_from_text(test_text)
    
    print("\n" + "=" * 50)
    print("RESULT")
    print("=" * 50)
    
    if result:
        print(f"SUCCESS: Found booking number: {result}")
        if result == "RICFEM857500":
            print("PERFECT MATCH!")
        else:
            print(f"Expected: RICFEM857500, Got: {result}")
    else:
        print("FAILED: No booking number found")
    
    print("=" * 50)

if __name__ == "__main__":
    test_parser()
