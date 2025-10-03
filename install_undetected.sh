#!/bin/bash
# Installation script for undetected-chromedriver on Linux

echo "======================================================================"
echo "  Installing undetected-chromedriver"
echo "======================================================================"

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install undetected-chromedriver
echo "📦 Installing undetected-chromedriver..."
pip install undetected-chromedriver==3.5.5

echo ""
echo "✅ Installation complete!"
echo ""
echo "======================================================================"
echo "  Testing import..."
echo "======================================================================"

python3 << EOF
try:
    import undetected_chromedriver as uc
    print("✅ undetected-chromedriver imported successfully!")
    print(f"   Version: {uc.__version__}")
except Exception as e:
    print(f"❌ Import failed: {e}")
EOF

echo ""
echo "======================================================================"
echo "  Ready to use!"
echo "======================================================================"
echo "Restart your API server: python emodal_business_api.py"
echo "======================================================================"

