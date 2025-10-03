#!/bin/bash
# System resource check for E-Modal API on Linux

echo "======================================================================"
echo "  SYSTEM RESOURCE CHECK FOR E-MODAL API"
echo "======================================================================"

echo ""
echo "1. Checking /dev/shm (shared memory):"
df -h /dev/shm
echo ""

echo "2. Checking /tmp directory:"
df -h /tmp
echo ""

echo "3. Checking available memory:"
free -h
echo ""

echo "4. Checking Chrome processes:"
ps aux | grep -i chrome | grep -v grep || echo "No Chrome processes running"
echo ""

echo "5. Checking Xvfb processes:"
ps aux | grep -i xvfb | grep -v grep || echo "No Xvfb processes running"
echo ""

echo "======================================================================"
echo "  RECOMMENDED FIXES (if needed):"
echo "======================================================================"
echo ""
echo "If /dev/shm is too small (< 512MB), increase it:"
echo "  sudo mount -o remount,size=1G /dev/shm"
echo ""
echo "If /tmp is too small (< 1GB), clean it:"
echo "  sudo rm -rf /tmp/chrome_debug_*"
echo "  sudo rm -rf /tmp/.com.google.Chrome.*"
echo ""
echo "======================================================================"

