#!/usr/bin/env python3
"""
System resource checker for E-Modal API on Linux
Run with: python check_resources.py
"""

import os
import subprocess
import shutil

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return "Error running command"

def check_disk_space(path):
    """Check disk space for a path"""
    try:
        stat = shutil.disk_usage(path)
        total_gb = stat.total / (1024**3)
        used_gb = stat.used / (1024**3)
        free_gb = stat.free / (1024**3)
        percent = (stat.used / stat.total) * 100
        return {
            'total': total_gb,
            'used': used_gb,
            'free': free_gb,
            'percent': percent
        }
    except Exception as e:
        return {'error': str(e)}

print("=" * 70)
print("  SYSTEM RESOURCE CHECK FOR E-MODAL API")
print("=" * 70)
print()

# 1. Check /dev/shm
print("1. /dev/shm (Shared Memory) - CRITICAL FOR CHROME:")
print("-" * 70)
shm_info = check_disk_space('/dev/shm')
if 'error' not in shm_info:
    print(f"   Total:   {shm_info['total']:.2f} GB")
    print(f"   Used:    {shm_info['used']:.2f} GB")
    print(f"   Free:    {shm_info['free']:.2f} GB")
    print(f"   Usage:   {shm_info['percent']:.1f}%")
    if shm_info['total'] < 0.5:  # Less than 500MB
        print(f"   ⚠️  WARNING: /dev/shm is too small! ({shm_info['total']:.2f} GB)")
        print(f"   ❌ Chrome needs at least 512MB, recommended 1GB+")
        print(f"   💡 FIX: sudo mount -o remount,size=1G /dev/shm")
    elif shm_info['free'] < 0.2:  # Less than 200MB free
        print(f"   ⚠️  WARNING: /dev/shm is almost full!")
        print(f"   💡 Clean up: sudo rm -rf /dev/shm/*")
    else:
        print(f"   ✅ /dev/shm size is adequate")
else:
    print(f"   ❌ Error checking /dev/shm: {shm_info['error']}")
print()

# 2. Check /tmp
print("2. /tmp Directory:")
print("-" * 70)
tmp_info = check_disk_space('/tmp')
if 'error' not in tmp_info:
    print(f"   Total:   {tmp_info['total']:.2f} GB")
    print(f"   Used:    {tmp_info['used']:.2f} GB")
    print(f"   Free:    {tmp_info['free']:.2f} GB")
    print(f"   Usage:   {tmp_info['percent']:.1f}%")
    if tmp_info['free'] < 1.0:  # Less than 1GB free
        print(f"   ⚠️  WARNING: /tmp is running low on space!")
        print(f"   💡 Clean up Chrome temp files:")
        print(f"      sudo rm -rf /tmp/chrome_debug_*")
        print(f"      sudo rm -rf /tmp/.com.google.Chrome.*")
        print(f"      sudo rm -rf /tmp/.org.chromium.*")
    else:
        print(f"   ✅ /tmp has adequate space")
else:
    print(f"   ❌ Error checking /tmp: {tmp_info['error']}")
print()

# 3. Check memory
print("3. System Memory:")
print("-" * 70)
mem_output = run_command("free -h | grep Mem")
if mem_output:
    print(f"   {mem_output}")
    # Parse memory
    parts = mem_output.split()
    if len(parts) >= 7:
        total = parts[1]
        used = parts[2]
        free = parts[3]
        available = parts[6]
        print(f"   Available: {available}")
        # Check if available memory is low
        try:
            avail_mb = float(available.replace('Gi', '').replace('Mi', '').replace('G', '').replace('M', ''))
            if 'Mi' in available or 'M' in available:
                if avail_mb < 500:  # Less than 500MB
                    print(f"   ⚠️  WARNING: Low memory!")
            elif 'Gi' in available or 'G' in available:
                print(f"   ✅ Memory is adequate")
        except:
            pass
else:
    print("   Could not check memory")
print()

# 4. Check Chrome processes
print("4. Chrome Processes:")
print("-" * 70)
chrome_processes = run_command("ps aux | grep -i chrome | grep -v grep")
if chrome_processes:
    lines = chrome_processes.split('\n')
    print(f"   Found {len(lines)} Chrome process(es):")
    for line in lines[:5]:  # Show first 5
        parts = line.split()
        if len(parts) >= 11:
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            cmd = ' '.join(parts[10:])[:50]
            print(f"   PID {pid}: CPU={cpu}% MEM={mem}% | {cmd}...")
    if len(lines) > 5:
        print(f"   ... and {len(lines) - 5} more")
else:
    print("   ✅ No Chrome processes running")
print()

# 5. Check Xvfb processes
print("5. Xvfb Processes:")
print("-" * 70)
xvfb_processes = run_command("ps aux | grep -i xvfb | grep -v grep")
if xvfb_processes:
    lines = xvfb_processes.split('\n')
    print(f"   Found {len(lines)} Xvfb process(es):")
    for line in lines:
        parts = line.split()
        if len(parts) >= 11:
            pid = parts[1]
            display = parts[11] if len(parts) > 11 else "?"
            print(f"   PID {pid}: Display {display}")
else:
    print("   ✅ No Xvfb processes running")
print()

# 6. Check Chrome temp files
print("6. Chrome Temporary Files:")
print("-" * 70)
chrome_temp_dirs = [
    '/tmp/chrome_debug_*',
    '/tmp/.com.google.Chrome.*',
    '/tmp/.org.chromium.*',
    '/tmp/scoped_dir*'
]
total_files = 0
for pattern in chrome_temp_dirs:
    count_output = run_command(f"ls -d {pattern} 2>/dev/null | wc -l")
    try:
        count = int(count_output)
        if count > 0:
            print(f"   {pattern}: {count} items")
            total_files += count
    except:
        pass

if total_files == 0:
    print("   ✅ No Chrome temp files found")
elif total_files < 10:
    print(f"   ℹ️  {total_files} Chrome temp items (normal)")
else:
    print(f"   ⚠️  {total_files} Chrome temp items (consider cleanup)")
    print(f"   💡 Cleanup: sudo rm -rf /tmp/chrome_debug_* /tmp/.com.google.Chrome.* /tmp/.org.chromium.* /tmp/scoped_dir*")
print()

print("=" * 70)
print("  SUMMARY & RECOMMENDATIONS")
print("=" * 70)
print()

# Determine main issues
issues = []
if 'error' not in shm_info and shm_info['total'] < 0.5:
    issues.append("⚠️  /dev/shm is too small - THIS IS LIKELY THE MAIN ISSUE!")
    issues.append("   Fix: sudo mount -o remount,size=1G /dev/shm")
if 'error' not in tmp_info and tmp_info['free'] < 1.0:
    issues.append("⚠️  /tmp is low on space")
    issues.append("   Fix: sudo rm -rf /tmp/chrome_debug_* /tmp/.com.google.Chrome.*")
if total_files > 20:
    issues.append("⚠️  Too many Chrome temp files")
    issues.append("   Fix: Clean up /tmp")

if issues:
    print("🔴 Issues Found:")
    for issue in issues:
        print(f"   {issue}")
    print()
    print("📝 Quick Fix Commands:")
    print("   sudo mount -o remount,size=1G /dev/shm")
    print("   sudo rm -rf /tmp/chrome_debug_* /tmp/.com.google.Chrome.* /tmp/.org.chromium.*")
else:
    print("✅ No obvious resource issues detected")
    print()
    print("🔍 Chrome is still crashing? Check:")
    print("   1. Chrome logs: /tmp/chrome_debug.log (if exists)")
    print("   2. System logs: dmesg | tail -50")
    print("   3. Out of memory killer: dmesg | grep -i 'killed process'")

print()
print("=" * 70)

