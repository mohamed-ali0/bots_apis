"""
Test script for multiline label format in screenshots.
Each piece of data on its own line with titles.
"""

import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

def load_and_resize_url_bar(target_width):
    """Load the existing url_bar_appointment.png and resize it to target width"""
    try:
        url_bar_path = "url_bar_appointment.png"
        if not os.path.exists(url_bar_path):
            print(f"URL bar file not found: {url_bar_path}")
            return None
            
        url_bar = Image.open(url_bar_path)
        original_width, original_height = url_bar.size
        
        print(f"Loaded URL bar: {original_width}x{original_height}")
        
        if target_width != original_width:
            url_bar = url_bar.resize((target_width, original_height), Image.Resampling.LANCZOS)
            print(f"Resized URL bar to: {target_width}x{original_height}")
        
        return url_bar
        
    except Exception as e:
        print(f"Error loading URL bar: {e}")
        return None

def annotate_screenshot_multiline_label(screenshot_path, output_path, username, container_id, container_type, move_type, vm_email=None):
    """Annotate screenshot with URL bar at top and multiline label at bottom"""
    try:
        img = Image.open(screenshot_path).convert("RGBA")
        original_width, original_height = img.size
        
        print(f"Original screenshot: {original_width}x{original_height}")
        
        url_bar_width = max(2074, original_width)
        url_bar = load_and_resize_url_bar(url_bar_width)
        
        if url_bar is None:
            print("Failed to load URL bar, skipping annotation")
            return False
        
        url_bar_height = url_bar.size[1]
        print(f"URL bar: {url_bar_width}x{url_bar_height}")
        
        new_height = url_bar_height + original_height
        new_width = max(url_bar_width, original_width)
        
        new_img = Image.new('RGB', (new_width, new_height), color=(255, 255, 255))
        
        new_img.paste(url_bar, (0, 0))
        
        if original_width < new_width:
            x_offset = (new_width - original_width) // 2
            new_img.paste(img, (x_offset, url_bar_height), img if img.mode == 'RGBA' else None)
        else:
            new_img.paste(img, (0, url_bar_height), img if img.mode == 'RGBA' else None)
        
        draw = ImageDraw.Draw(new_img)
        
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y-%m-%d')
        time_str = timestamp.strftime('%H:%M:%S')
        
        label_lines = [
            f"Username: {username}",
            f"Platform: emodal",
            f"Container: {container_id}, {container_type}, {move_type}",
            f"Date and time: {date_str} | {time_str}"
        ]
        
        if vm_email:
            label_lines.append(f"VM Email: {vm_email}")
        
        try:
            enhanced_font = ImageFont.truetype("arial.ttf", 36)
        except:
            try:
                enhanced_font = ImageFont.truetype("DejaVuSans.ttf", 36)
            except:
                enhanced_font = ImageFont.load_default()
        
        line_height = 45
        max_width = 0
        
        for line in label_lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=enhanced_font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = draw.textlength(line, font=enhanced_font)
            if line_width > max_width:
                max_width = line_width
        
        total_height = len(label_lines) * line_height
        padding = 20
        
        label_x = new_width - max_width - padding
        label_y = new_height - total_height - padding
        
        bg_padding = 15
        draw.rectangle([
            label_x - bg_padding, 
            label_y - bg_padding, 
            label_x + max_width + bg_padding, 
            label_y + total_height + bg_padding
        ], fill=(0, 0, 0, 200))
        
        current_y = label_y
        for line in label_lines:
            draw.text((label_x, current_y), line, font=enhanced_font, fill=(255, 255, 0))
            current_y += line_height
        
        new_img.save(output_path)
        print(f"Annotated screenshot saved: {output_path}")
        print(f"Final dimensions: {new_width}x{new_height}")
        
        return True
        
    except Exception as e:
        print(f"Error annotating screenshot: {e}")
        return False

def test_multiline_labels():
    """Test the multiline label format"""
    print("Testing Multiline Label Format")
    print("=" * 60)
    
    test_dir = "."
    original_screenshot = os.path.join(test_dir, "TCLU3648865_1761352193.png")
    
    if not os.path.exists(original_screenshot):
        print(f"Original screenshot not found: {original_screenshot}")
        return False
    
    print(f"Original screenshot: {os.path.basename(original_screenshot)}")
    
    print("\n" + "="*50)
    print("Test 1: Import container (no VM email)")
    print("="*50)
    
    output1 = os.path.join(test_dir, "test_multiline_import.png")
    success1 = annotate_screenshot_multiline_label(
        original_screenshot, 
        output1, 
        username="john_doe",
        container_id="MSDU8716455",
        container_type="import",
        move_type="DROP EMPTY",
        vm_email=None
    )
    
    if success1:
        print(f"Test 1 passed: {os.path.basename(output1)}")
    else:
        print("Test 1 failed")
    
    print("\n" + "="*50)
    print("Test 2: Export container (with VM email)")
    print("="*50)
    
    output2 = os.path.join(test_dir, "test_multiline_export.png")
    success2 = annotate_screenshot_multiline_label(
        original_screenshot, 
        output2, 
        username="jane_smith",
        container_id="TRHU1866154",
        container_type="export",
        move_type="PICK LOAD",
        vm_email="vm1@company.com"
    )
    
    if success2:
        print(f"Test 2 passed: {os.path.basename(output2)}")
    else:
        print("Test 2 failed")
    
    print("\n" + "="*50)
    print("Test 3: Different container (with VM email)")
    print("="*50)
    
    output3 = os.path.join(test_dir, "test_multiline_different.png")
    success3 = annotate_screenshot_multiline_label(
        original_screenshot, 
        output3, 
        username="bob_wilson",
        container_id="ABCD1234567",
        container_type="import",
        move_type="DROP EMPTY",
        vm_email="vm2@example.com"
    )
    
    if success3:
        print(f"Test 3 passed: {os.path.basename(output3)}")
    else:
        print("Test 3 failed")
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    total_tests = 3
    passed_tests = sum([success1, success2, success3])
    
    print(f"Passed: {passed_tests}/{total_tests}")
    print(f"Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\nAll tests passed! Multiline label format ready.")
        print("\nLabel format implemented:")
        print("   - Username: [username]")
        print("   - Platform: emodal")
        print("   - Container: [id], [type], [move_type]")
        print("   - Date and time: [date] | [time]")
        print("   - VM Email: [email] (if provided)")
        print("   - 50% larger font (36px)")
        print("   - Bold yellow text")
    else:
        print("\nSome tests failed. Check the error messages above.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    print("Multiline Label Format Test")
    print("=" * 60)
    print("\nThis test will:")
    print("1. Use existing url_bar_appointment.png")
    print("2. Create multiline labels with titles")
    print("3. Test import and export containers")
    print("4. Test with and without VM email")
    print("=" * 60)
    
    success = test_multiline_labels()
    
    if success:
        print("\nReady to apply multiline format to emodal_business_api.py!")
    else:
        print("\nFix issues before applying to endpoint.")





