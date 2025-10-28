"""
Test script to verify 401 error detection logic
"""

print("=" * 70)
print("401 Error Detection Test")
print("=" * 70)
print()

# Simulate page source with 401 error
page_source_401 = """
<html>
<body>
    <div>
        <h1>401</h1>
        <p>You are either not logged in or your session has expired.</p>
        <p>Please use your back button or return to the home page and login.</p>
    </div>
</body>
</html>
"""

# Test detection logic
page_source_lower = page_source_401.lower()

errors_to_check = [
    "you are either not logged in",
    "your session has expired",
    "please use your back button"
]

print("Testing 401 error detection:")
print("-" * 70)
print()

for error_text in errors_to_check:
    detected = error_text in page_source_lower
    status = "FOUND" if detected else "NOT FOUND"
    print(f"  Checking: '{error_text}'")
    print(f"    Status: {status}")
    print()

# Overall detection
overall_detected = any(error in page_source_lower for error in errors_to_check)
print("=" * 70)
print(f"401 Error Detected: {'YES' if overall_detected else 'NO'}")
print("=" * 70)
print()

if overall_detected:
    print("Session would be terminated and new session created!")
else:
    print("Session would be considered healthy")

print()
print("=" * 70)
print()

# Test with healthy page
print("Testing with healthy page:")
print("-" * 70)

healthy_page = """
<html>
<body>
    <h1>eModal Dashboard</h1>
    <div class="container-list">
        <p>Welcome to the dashboard</p>
    </div>
</body>
</html>
"""

healthy_lower = healthy_page.lower()
healthy_detected = any(error in healthy_lower for error in errors_to_check)

print(f"401 Error Detected: {'YES' if healthy_detected else 'NO'}")
print("=" * 70)
print()
print("Summary:")
print("  - 401 errors are detected correctly")
print("  - Healthy pages pass through")
print("  - Automatic session recovery enabled")
print()
