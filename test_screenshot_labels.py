"""
Test script to demonstrate screenshot label controls
"""

# Simulate the control flags
print("=" * 70)
print("Screenshot Label Controls - Test Examples")
print("=" * 70)
print()

# Default settings
label_show_username = True
label_show_platform = True
label_show_container = True
label_show_datetime = True
label_show_vm_email = False  # Disabled by default

print("Current Settings (Default):")
print(f"  Username: {label_show_username}")
print(f"  Platform: {label_show_platform}")
print(f"  Container: {label_show_container}")
print(f"  Date/Time: {label_show_datetime}")
print(f"  VM Email: {label_show_vm_email} <-- DISABLED")
print()

# Example 1: Show what labels would appear with current settings
print("Example 1: Current Settings Output")
print("-" * 70)
if label_show_username:
    print("Username: jfernandez")
if label_show_platform:
    print("Platform: emodal")
if label_show_container:
    print("Container: TCLU8784503, import, DROP EMPTY")
if label_show_datetime:
    print("Date and time: 2025-01-11 | 14:30:45")
# VM Email is disabled, so it won't show
print()

# Example 2: Enable VM Email
print("Example 2: Enable VM Email")
print("-" * 70)
label_show_vm_email = True
print(f"Setting: operations.label_show_vm_email = True")
print()
print("Output would be:")
if label_show_username:
    print("Username: jfernandez")
if label_show_platform:
    print("Platform: emodal")
if label_show_container:
    print("Container: TCLU8784503, import, DROP EMPTY")
if label_show_datetime:
    print("Date and time: 2025-01-11 | 14:30:45")
if label_show_vm_email:  # Now enabled
    print("VM Email: vm@example.com")
print()

# Example 3: Show only essential info
print("Example 3: Minimal Labels (Only Username & Platform)")
print("-" * 70)
label_show_username = True
label_show_platform = True
label_show_container = False
label_show_datetime = False
label_show_vm_email = False
print("Settings:")
print("  operations.label_show_username = True")
print("  operations.label_show_platform = True")
print("  operations.label_show_container = False")
print("  operations.label_show_datetime = False")
print("  operations.label_show_vm_email = False")
print()
print("Output would be:")
if label_show_username:
    print("Username: jfernandez")
if label_show_platform:
    print("Platform: emodal")
# Other fields are disabled
print()

# Example 4: Use helper method
print("Example 4: Using Helper Method")
print("-" * 70)
print("operations.set_screenshot_labels(")
print("    username=True,")
print("    platform=True,")
print("    container=False,")
print("    datetime=False,")
print("    vm_email=False")
print(")")
print()
print("This is equivalent to:")
print("  operations.label_show_username = True")
print("  operations.label_show_platform = True")
print("  operations.label_show_container = False")
print("  operations.label_show_datetime = False")
print("  operations.label_show_vm_email = False")
print()

print("=" * 70)
print("Screenshot label controls are ready to use!")
print("=" * 70)
print()
print("Quick Tips:")
print("  - VM Email is DISABLED by default")
print("  - Enable it: operations.label_show_vm_email = True")
print("  - Disable it: operations.label_show_vm_email = False")
print("  - Use helper method: operations.set_screenshot_labels(vm_email=True)")
print()
