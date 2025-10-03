#!/bin/bash
# Quick fix for Python 3.12 distutils error

echo "======================================================================"
echo "  Python 3.12 Compatibility Fix"
echo "======================================================================"

# Install setuptools (replaces distutils in Python 3.12)
echo "📦 Installing setuptools and wheel..."
pip install --upgrade setuptools wheel

# Update numpy to Python 3.12 compatible version
echo "📦 Upgrading numpy to Python 3.12 compatible version..."
pip install --upgrade "numpy>=1.26.0"

# Update pandas to Python 3.12 compatible version
echo "📦 Upgrading pandas to Python 3.12 compatible version..."
pip install --upgrade "pandas>=2.1.0"

# Now install remaining requirements
echo "📦 Installing all requirements..."
pip install -r requirements.txt

echo ""
echo "✅ Python 3.12 compatibility fix complete!"
echo "======================================================================"

