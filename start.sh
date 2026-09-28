#!/bin/bash
# FitConvert Startup Script

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source ../venv/bin/activate


# Start server
echo ""
echo "="*60
echo "✅ FitConvert is starting!"
echo "🌐 Open your browser to: http://localhost:5000"
echo "="*60
echo ""

python3 server.py
