# Selenium Scrolling Methods Reference

## Overview

This document outlines all the scrolling methods used in the E-Modal Business API's `get_containers` endpoint for infinite scrolling implementation. These methods can be reused in other Selenium automation projects.

---

## 1. Element-Based JavaScript Scrolling

### Method 1: scrollBy on Specific Element
```python
# Scroll down by specific pixels within an element
driver.execute_script("arguments[0].scrollBy(0, 800);", scroll_target)
```
- **Use Case**: Scroll within a specific container/div
- **Advantage**: Precise control, works with overflow containers
- **Parameters**: `(x_offset, y_offset)` - 800px down in this case

### Method 2: scrollIntoView for Element Positioning
```python
# Bring element into view (centered)
driver.execute_script("arguments[0].scrollIntoView({block:'center'});", scroll_target)

# Bring element into view (top aligned)
driver.execute_script("arguments[0].scrollIntoView(true);", element)
```
- **Use Case**: Position specific elements in viewport
- **Options**: 
  - `{block:'center'}` - Center the element
  - `true` - Align to top
  - `false` - Align to bottom

---

## 2. Window-Based JavaScript Scrolling

### Method 3: Window scrollBy (Relative)
```python
# Scroll window by relative amount
driver.execute_script("window.scrollBy(0, 800);")
```
- **Use Case**: Scroll entire page when no specific container
- **Parameters**: `(x_offset, y_offset)`

### Method 4: Window scrollTo (Absolute)
```python
# Scroll to absolute position (bottom of page)
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

# Scroll to specific position
driver.execute_script("window.scrollTo(0, 1000);")
```
- **Use Case**: Jump to specific page positions
- **Common**: `document.body.scrollHeight` for bottom of page

---

## 3. Selenium Action Chains

### Method 5: Keyboard Scrolling with Page Down
```python
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

actions = ActionChains(driver)
actions.send_keys(Keys.PAGE_DOWN).perform()
```
- **Use Case**: Simulate user keyboard scrolling
- **Advantage**: Natural scrolling behavior

### Method 6: Arrow Key Scrolling
```python
actions = ActionChains(driver)
actions.send_keys(Keys.ARROW_DOWN * 10).perform()
```
- **Use Case**: Fine-grained scrolling control
- **Parameters**: Multiply by number for multiple key presses

### Method 7: Mouse Wheel Scrolling
```python
actions = ActionChains(driver)
actions.move_to_element(scroll_target)
actions.scroll_by_amount(0, 800).perform()  # If supported by WebDriver version
```
- **Use Case**: Simulate mouse wheel scrolling
- **Note**: Requires newer WebDriver versions

---

## 4. Smart Target Detection

### Priority-Based Scroll Target Selection
```python
def find_scroll_target(driver):
    scroll_target = None
    
    # Priority 1: Specific ID with infinite scroll
    try:
        scroll_target = driver.find_element(By.ID, "searchres")
        if scroll_target and scroll_target.is_displayed():
            print("Found #searchres (matinfinitescroll container)")
            return scroll_target
    except Exception:
        pass
    
    # Priority 2: Any element with infinite scroll attribute
    try:
        scroll_target = driver.find_element(By.XPATH, "//*[@matinfinitescroll]")
        if scroll_target and scroll_target.is_displayed():
            print("Found element with matinfinitescroll attribute")
            return scroll_target
    except Exception:
        pass
    
    # Priority 3: Common class names
    try:
        scroll_target = driver.find_element(By.CLASS_NAME, "search-results")
        if scroll_target and scroll_target.is_displayed():
            print("Found .search-results container")
            return scroll_target
    except Exception:
        pass
    
    # Priority 4: Auto-detect scrollable divs
    try:
        js = """
            var divs = document.querySelectorAll('div');
            for (var i = 0; i < divs.length; i++) {
                var el = divs[i];
                var style = window.getComputedStyle(el);
                if (el.scrollHeight > el.clientHeight + 10 && 
                    style.overflowY !== 'hidden' &&
                    style.height && style.height !== 'auto') {
                    return el;
                }
            }
            return null;
        """
        scroll_target = driver.execute_script(js)
        if scroll_target:
            print("Found fixed-height scrollable div")
            return scroll_target
    except Exception:
        pass
    
    print("No scroll container found, will use window scrolling")
    return None
```

---

## 5. Hybrid Scrolling Implementation

### Multi-Method Fallback System
```python
def perform_scroll(driver, scroll_target=None, scroll_amount=800):
    """
    Perform scrolling with multiple fallback methods
    """
    success = False
    
    if scroll_target:
        # Method 1: Element scrollBy
        try:
            driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", scroll_target, scroll_amount)
            success = True
            print(f"✅ Element scrollBy successful ({scroll_amount}px)")
        except Exception as e:
            print(f"⚠️ Element scrollBy failed: {e}")
    
    if not success:
        # Method 2: Window scrollBy
        try:
            driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_amount)
            success = True
            print(f"✅ Window scrollBy successful ({scroll_amount}px)")
        except Exception as e:
            print(f"⚠️ Window scrollBy failed: {e}")
    
    if not success:
        # Method 3: Page Down key
        try:
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.send_keys(Keys.PAGE_DOWN).perform()
            success = True
            print("✅ Page Down key successful")
        except Exception as e:
            print(f"⚠️ Page Down failed: {e}")
    
    if not success:
        # Method 4: Arrow keys
        try:
            actions = ActionChains(driver)
            actions.send_keys(Keys.ARROW_DOWN * 10).perform()
            success = True
            print("✅ Arrow keys successful")
        except Exception as e:
            print(f"⚠️ Arrow keys failed: {e}")
    
    return success
```

---

## 6. Infinite Scroll Implementation

### Complete Infinite Scroll Function
```python
def infinite_scroll_load_content(driver, target_count=None, target_element_text=None, max_cycles=50):
    """
    Perform infinite scrolling to load dynamic content
    
    Args:
        driver: WebDriver instance
        target_count: Stop when this many items loaded (None = load all)
        target_element_text: Stop when element with this text found
        max_cycles: Maximum scroll cycles before giving up
    
    Returns:
        Dict with success, total_items, scroll_cycles, found_target
    """
    
    # Find scroll target
    scroll_target = find_scroll_target(driver)
    
    # Initialize tracking
    previous_count = 0
    no_new_content_count = 0
    max_no_new_content_cycles = 3
    scroll_cycle = 0
    
    print("🔄 Starting infinite scroll...")
    
    while (scroll_cycle < max_cycles and 
           no_new_content_count < max_no_new_content_cycles):
        
        scroll_cycle += 1
        print(f"📜 Scroll cycle {scroll_cycle}")
        
        # Count current content (customize this logic)
        current_count = count_loaded_items(driver)
        
        # Check for target element if specified
        if target_element_text:
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{target_element_text}')]")
                if element and element.is_displayed():
                    print(f"🎯 Target element found: {target_element_text}")
                    return {
                        "success": True,
                        "total_items": current_count,
                        "scroll_cycles": scroll_cycle,
                        "found_target": target_element_text
                    }
            except Exception:
                pass
        
        # Check if we got new content
        if current_count > previous_count:
            print(f"✅ New content: {previous_count} → {current_count}")
            previous_count = current_count
            no_new_content_count = 0
        else:
            no_new_content_count += 1
            print(f"⚠️ No new content ({no_new_content_count}/{max_no_new_content_cycles})")
        
        # Check target count
        if target_count and current_count >= target_count:
            print(f"🎯 Target count reached: {current_count}")
            return {
                "success": True,
                "total_items": current_count,
                "scroll_cycles": scroll_cycle,
                "stopped_reason": f"Target count {target_count} reached"
            }
        
        # Perform scroll
        perform_scroll(driver, scroll_target, 800)
        
        # Wait for content to load
        time.sleep(2)
    
    # Return final results
    return {
        "success": True,
        "total_items": current_count,
        "scroll_cycles": scroll_cycle,
        "stopped_reason": "Max cycles reached or no new content"
    }

def count_loaded_items(driver):
    """
    Count loaded items - customize this for your use case
    """
    try:
        # Example: Count table rows
        rows = driver.find_elements(By.XPATH, "//tr[@class='data-row']")
        return len(rows)
    except:
        return 0
```

---

## 7. Best Practices

### 1. **Always Use Fallbacks**
- Start with element-specific scrolling
- Fall back to window scrolling
- Use keyboard methods as last resort

### 2. **Wait Between Scrolls**
```python
time.sleep(2)  # Wait for content to load
```

### 3. **Detect Scroll Completion**
```python
# Check if at bottom of page
at_bottom = driver.execute_script("""
    return (window.innerHeight + window.scrollY) >= document.body.offsetHeight;
""")
```

### 4. **Handle Iframes**
```python
# Switch to iframe if content is inside
frames = driver.find_elements(By.TAG_NAME, "iframe")
for frame in frames:
    try:
        driver.switch_to.frame(frame)
        # Try scrolling here
        break
    except:
        driver.switch_to.default_content()
```

### 5. **Focus and Mouse Positioning**
```python
# Focus page and position mouse for better scrolling
driver.execute_script("window.focus();")
actions = ActionChains(driver)
actions.move_to_element(scroll_target).perform()
```

---

## 8. Common Issues and Solutions

### Issue 1: Scrolling Not Working
**Solution**: Check if content is in iframe, try different scroll targets

### Issue 2: Content Not Loading
**Solution**: Increase wait time, check for loading indicators

### Issue 3: Infinite Loop
**Solution**: Implement max cycles and "no new content" detection

### Issue 4: Element Not Found
**Solution**: Use multiple fallback selectors and auto-detection

---

## Usage Example

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Initialize driver
driver = webdriver.Chrome()
driver.get("https://example.com/infinite-scroll-page")

# Perform infinite scroll
result = infinite_scroll_load_content(
    driver=driver,
    target_count=100,  # Stop at 100 items
    max_cycles=20      # Max 20 scroll cycles
)

print(f"Loaded {result['total_items']} items in {result['scroll_cycles']} cycles")
driver.quit()
```

---

**Note**: These methods are battle-tested in the E-Modal Business API and handle various edge cases including iframes, dynamic content, and different page layouts.



