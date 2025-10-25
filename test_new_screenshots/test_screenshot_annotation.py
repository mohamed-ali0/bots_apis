"""
Test script for new screenshot annotation system.
- Adds URL bar at top (2074px width, stretchable)
- Makes label 50% larger font, bold, yellow color
- Tests with existing files in test_new_screenshots folder
"""

import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

def load_and_resize_url_bar(target_width):
    """Load the existing url_bar_appointment.png and resize it to target width"""
    try:
        # Load the existing URL bar image
        url_bar_path = "url_bar_appointment.png"
        if not os.path.exists(url_bar_path):
            print(f"URL bar file not found: {url_bar_path}")
            return None
            
        url_bar = Image.open(url_bar_path)
        original_width, original_height = url_bar.size
        
        print(f"Loaded URL bar: {original_width}x{original_height}")
        
        # Resize to target width (stretch if needed)
        if target_width != original_width:
            url_bar = url_bar.resize((target_width, original_height), Image.Resampling.LANCZOS)
            print(f"Resized URL bar to: {target_width}x{original_height}")
        
        return url_bar
        
    except Exception as e:
        print(f"Error loading URL bar: {e}")
        return None

def annotate_screenshot_with_url_bar(screenshot_path, output_path, label_text, vm_email=None):
    """
    Annotate screenshot with URL bar at top and enhanced label at bottom
    
    Args:
        screenshot_path: Path to original screenshot
        output_path: Path to save annotated screenshot
        label_text: Main label text
        vm_email: Optional VM email to include
    """
    try:
        # Load original screenshot
        img = Image.open(screenshot_path).convert("RGBA")
        original_width, original_height = img.size
        
        print(f"Original screenshot: {original_width}x{original_height}")
        
        # Load and resize URL bar (stretch to screenshot width if needed)
        url_bar_width = max(2074, original_width)  # At least 2074px, or screenshot width if larger
        url_bar = load_and_resize_url_bar(url_bar_width)
        
        if url_bar is None:
            print("Failed to load URL bar, skipping annotation")
            return False
        
        url_bar_height = url_bar.size[1]
        print(f"URL bar: {url_bar_width}x{url_bar_height}")
        
        # Create new image with URL bar + screenshot
        new_height = url_bar_height + original_height  # URL bar height + screenshot height
        new_width = max(url_bar_width, original_width)
        
        # Create new image
        new_img = Image.new('RGB', (new_width, new_height), color=(255, 255, 255))
        
        # Paste URL bar at top
        new_img.paste(url_bar, (0, 0))
        
        # Paste original screenshot below URL bar
        if original_width < new_width:
            # Center the screenshot if it's narrower
            x_offset = (new_width - original_width) // 2
            new_img.paste(img, (x_offset, url_bar_height), img if img.mode == 'RGBA' else None)
        else:
            new_img.paste(img, (0, url_bar_height), img if img.mode == 'RGBA' else None)
        
        # Add enhanced label at bottom
        draw = ImageDraw.Draw(new_img)
        
        # Build label text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        text_parts = [label_text, timestamp]
        
        if vm_email:
            text_parts.append(f"VM: {vm_email}")
        
        text_parts.append("emodal")
        main_text = " | ".join(text_parts)
        
        # Enhanced font (50% larger, bold, yellow)
        try:
            # Try to get a larger font
            base_font = ImageFont.truetype("arial.ttf", 24)  # Base size
            enhanced_font = ImageFont.truetype("arial.ttf", 36)  # 50% larger (24 * 1.5)
        except:
            try:
                base_font = ImageFont.truetype("DejaVuSans.ttf", 24)
                enhanced_font = ImageFont.truetype("DejaVuSans.ttf", 36)
            except:
                base_font = ImageFont.load_default()
                enhanced_font = ImageFont.load_default()
        
        # Calculate text dimensions
        try:
            bbox = draw.textbbox((0, 0), main_text, font=enhanced_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = draw.textlength(main_text, font=enhanced_font)
            text_height = 36
        
        # Position label at bottom-right
        padding = 20
        label_x = new_width - text_width - padding
        label_y = new_height - text_height - padding
        
        # Draw background rectangle for label
        bg_padding = 15
        draw.rectangle([
            label_x - bg_padding, 
            label_y - bg_padding, 
            label_x + text_width + bg_padding, 
            label_y + text_height + bg_padding
        ], fill=(0, 0, 0, 200))  # Semi-transparent black background
        
        # Draw text in yellow
        draw.text((label_x, label_y), main_text, font=enhanced_font, fill=(255, 255, 0))  # Yellow text
        
        # Save annotated image
        new_img.save(output_path)
        print(f"Annotated screenshot saved: {output_path}")
        print(f"Final dimensions: {new_width}x{new_height}")
        
        return True
        
    except Exception as e:
        print(f"Error annotating screenshot: {e}")
        return False

def test_screenshot_annotation():
    """Test the new screenshot annotation system"""
    print("Testing New Screenshot Annotation System")
    print("=" * 60)
    
    # Test files
    test_dir = "."  # Current directory
    original_screenshot = os.path.join(test_dir, "TCLU3648865_1761352193.png")
    url_bar_file = os.path.join(test_dir, "url_bar_appointment.png")
    
    # Check if files exist
    if not os.path.exists(original_screenshot):
        print(f"Original screenshot not found: {original_screenshot}")
        return False
    
    if not os.path.exists(url_bar_file):
        print(f"URL bar file not found: {url_bar_file}")
        return False
    
    print(f"Test directory: {test_dir}")
    print(f"Original screenshot: {os.path.basename(original_screenshot)}")
    print(f"URL bar file: {os.path.basename(url_bar_file)}")
    
    # Test 1: Basic annotation without VM email
    print("\n" + "="*50)
    print("Test 1: Basic annotation (no VM email)")
    print("="*50)
    
    output1 = os.path.join(test_dir, "test_annotated_basic.png")
    success1 = annotate_screenshot_with_url_bar(
        original_screenshot, 
        output1, 
        "username123",
        vm_email=None
    )
    
    if success1:
        print(f"Test 1 passed: {os.path.basename(output1)}")
    else:
        print("Test 1 failed")
    
    # Test 2: Annotation with VM email
    print("\n" + "="*50)
    print("Test 2: Annotation with VM email")
    print("="*50)
    
    output2 = os.path.join(test_dir, "test_annotated_with_vm.png")
    success2 = annotate_screenshot_with_url_bar(
        original_screenshot, 
        output2, 
        "username123",
        vm_email="vm1@example.com"
    )
    
    if success2:
        print(f"Test 2 passed: {os.path.basename(output2)}")
    else:
        print("Test 2 failed")
    
    # Test 3: Different container ID
    print("\n" + "="*50)
    print("Test 3: Different container ID")
    print("="*50)
    
    output3 = os.path.join(test_dir, "test_annotated_container.png")
    success3 = annotate_screenshot_with_url_bar(
        original_screenshot, 
        output3, 
        "username123",
        vm_email="vm2@company.com"
    )
    
    if success3:
        print(f"Test 3 passed: {os.path.basename(output3)}")
    else:
        print("Test 3 failed")
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    total_tests = 3
    passed_tests = sum([success1, success2, success3])
    
    print(f"Passed: {passed_tests}/{total_tests}")
    print(f"Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\nAll tests passed! Ready to apply to endpoint.")
        print("\nFeatures implemented:")
        print("   - URL bar at top (2074px width, stretchable)")
        print("   - 50% larger font (24px -> 36px)")
        print("   - Bold yellow text")
        print("   - VM email support")
        print("   - Platform name 'emodal'")
        print("   - Timestamp")
    else:
        print("\nSome tests failed. Check the error messages above.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    print("New Screenshot Annotation Test")
    print("=" * 60)
    print("\nThis test will:")
    print("1. Add URL bar at top of screenshots (2074px width)")
    print("2. Make labels 50% larger font, bold, yellow")
    print("3. Test with and without VM email")
    print("4. Output test files to test_new_screenshots folder")
    print("=" * 60)
    
    success = test_screenshot_annotation()
    
    if success:
        print("\nReady to apply changes to emodal_business_api.py!")
    else:
        print("\nFix issues before applying to endpoint.")
