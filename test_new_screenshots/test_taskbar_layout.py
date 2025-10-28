"""
Test script for taskbar layout - URL bar + screenshot + taskbar + labels on right
"""
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

def test_taskbar_layout():
    print("Testing taskbar layout...")
    
    # File paths
    test_dir = "."
    url_bar_path = os.path.join(test_dir, "url_bar_appointment.png")
    taskbar_path = os.path.join(test_dir, "taskbar_appointment.png")
    screenshot_path = os.path.join(test_dir, "TCLU3648865_1761352193.png")
    
    # Check if files exist
    if not os.path.exists(url_bar_path):
        print(f"URL bar not found: {url_bar_path}")
        return
    if not os.path.exists(taskbar_path):
        print(f"Taskbar not found: {taskbar_path}")
        return
    if not os.path.exists(screenshot_path):
        print(f"Screenshot not found: {screenshot_path}")
        return
    
    print("All files found")
    
    try:
        # Load images
        url_bar = Image.open(url_bar_path)
        taskbar = Image.open(taskbar_path)
        screenshot = Image.open(screenshot_path).convert("RGBA")
        
        print(f"URL bar size: {url_bar.size}")
        print(f"Taskbar size: {taskbar.size}")
        print(f"Screenshot size: {screenshot.size}")
        
        # Get dimensions
        screenshot_width, screenshot_height = screenshot.size
        url_bar_width, url_bar_height = url_bar.size
        taskbar_width, taskbar_height = taskbar.size
        
        # Calculate final dimensions
        final_width = max(screenshot_width, url_bar_width, taskbar_width)
        final_height = url_bar_height + screenshot_height + taskbar_height
        
        print(f"Final composite size: {final_width}x{final_height}")
        
        # Resize URL bar and taskbar to match width if needed
        if url_bar_width != final_width:
            url_bar = url_bar.resize((final_width, url_bar_height), Image.Resampling.LANCZOS)
            print(f"Resized URL bar to: {final_width}x{url_bar_height}")
        
        if taskbar_width != final_width:
            taskbar = taskbar.resize((final_width, taskbar_height), Image.Resampling.LANCZOS)
            print(f"Resized taskbar to: {final_width}x{taskbar_height}")
        
        # Create composite image
        composite = Image.new('RGB', (final_width, final_height), color=(255, 255, 255))
        
        # Paste URL bar at top
        composite.paste(url_bar, (0, 0))
        
        # Paste screenshot in middle (center if narrower)
        if screenshot_width < final_width:
            x_offset = (final_width - screenshot_width) // 2
            composite.paste(screenshot, (x_offset, url_bar_height), screenshot if screenshot.mode == 'RGBA' else None)
        else:
            composite.paste(screenshot, (0, url_bar_height), screenshot if screenshot.mode == 'RGBA' else None)
        
        # Paste taskbar at bottom
        composite.paste(taskbar, (0, url_bar_height + screenshot_height))
        
        # Add labels on the RIGHT side
        draw = ImageDraw.Draw(composite)
        
        # Sample label data
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y-%m-%d')
        time_str = timestamp.strftime('%H:%M:%S')
        
        label_lines = [
            "Username: jfernandez",
            "Platform: emodal",
            "Container: TCLU3648865, import, DROP EMPTY",
            f"Date and time: {date_str} | {time_str}"
        ]
        
        # Enhanced font (36px, yellow)
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 36)
            except:
                font = ImageFont.load_default()
        
        # Calculate label dimensions
        line_height = 45
        max_line_width = 0
        
        for line in label_lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = draw.textlength(line, font=font)
            if line_width > max_line_width:
                max_line_width = line_width
        
        total_label_height = len(label_lines) * line_height
        padding = 20
        
        # Position labels on the LEFT side, just above the taskbar
        label_x = padding  # Left side with padding
        label_y = url_bar_height + screenshot_height - total_label_height - padding  # Just above taskbar
        
        # Draw background rectangle for labels
        bg_padding = 15
        draw.rectangle([
            label_x - bg_padding,
            label_y - bg_padding,
            label_x + max_line_width + bg_padding,
            label_y + total_label_height + bg_padding
        ], fill=(0, 0, 0, 200))  # Semi-transparent black background
        
        # Draw each label line
        current_y = label_y
        for line in label_lines:
            draw.text((label_x, current_y), line, font=font, fill=(255, 255, 0))  # Yellow text
            current_y += line_height
        
        # WRITE DATE AND TIME ON TASKBAR (same position as original)
        # Based on screenshot analysis: time is on right side of taskbar
        taskbar_start_y = url_bar_height + screenshot_height
        
        # Format time and date like in the screenshot
        # Use fixed time: 6:12 PM
        time_text = "6:12 PM"
        date_text = "10/28/2025"
        
        # Taskbar font controls
        taskbar_font_size = 24  # Change this value to control font size
        taskbar_font_bold = False  # Change this to control bold (True/False)
        
        # Load font based on bold setting
        if taskbar_font_bold:
            try:
                taskbar_font = ImageFont.truetype("segoeuib.ttf", taskbar_font_size)  # Segoe UI Bold
            except:
                try:
                    taskbar_font = ImageFont.truetype("arialbd.ttf", taskbar_font_size)  # Arial Bold
                except:
                    try:
                        taskbar_font = ImageFont.truetype("DejaVuSans-Bold.ttf", taskbar_font_size)  # DejaVu Bold
                    except:
                        taskbar_font = ImageFont.load_default()
        else:
            try:
                taskbar_font = ImageFont.truetype("segoeui.ttf", taskbar_font_size)  # Segoe UI Regular
            except:
                try:
                    taskbar_font = ImageFont.truetype("arial.ttf", taskbar_font_size)  # Arial Regular
                except:
                    try:
                        taskbar_font = ImageFont.truetype("DejaVuSans.ttf", taskbar_font_size)  # DejaVu Regular
                    except:
                        taskbar_font = ImageFont.load_default()
        
        print(f"Using taskbar font: {taskbar_font_size}px, Bold: {taskbar_font_bold}")
        
        # Position control for taskbar text
        date_x_offset = 216  # Distance from right edge
        date_y_offset = 40   # Distance from top of taskbar
        time_x_offset = 200  # Distance from right edge  
        time_y_offset = 5   # Distance from top of taskbar (elevated 10px from 25)
        
        # Position on right side of taskbar (like in original screenshot)
        # Date position (top part of taskbar)
        date_x = final_width - date_x_offset
        date_y = taskbar_start_y + date_y_offset
        
        # Time position (bottom part of taskbar)
        time_x = final_width - time_x_offset
        time_y = taskbar_start_y + time_y_offset
        
        # Draw time and date with WHITE font
        draw.text((time_x, time_y), time_text, font=taskbar_font, fill=(255, 255, 255))  # White text
        draw.text((date_x, date_y), date_text, font=taskbar_font, fill=(255, 255, 255))  # White text
        
        print(f"Writing on taskbar:")
        print(f"  Time: '{time_text}' at position ({time_x}, {time_y})")
        print(f"  Date: '{date_text}' at position ({date_x}, {date_y})")
        print(f"  Taskbar area: y={taskbar_start_y} to y={taskbar_start_y + taskbar_height}")
        
        # Save test output
        output_path = "test_taskbar_layout_output.png"
        composite.save(output_path)
        print(f"Test output saved: {output_path}")
        
        # Show layout info
        print("\n" + "="*60)
        print("LAYOUT PREVIEW:")
        print("="*60)
        print(f"TOP: URL BAR ({url_bar_height}px height)")
        print(f"MIDDLE: SCREENSHOT ({screenshot_height}px height)")
        print(f"  - LABELS ON LEFT SIDE (above taskbar)")
        print(f"BOTTOM: TASKBAR ({taskbar_height}px height)")
        print(f"Total height: {final_height}px")
        print(f"Total width: {final_width}px")
        print("="*60)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_taskbar_layout()
