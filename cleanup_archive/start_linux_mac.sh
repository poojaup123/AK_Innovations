#!/bin/bash

echo ""
echo "================================================"
echo " Factory Management System - Linux/Mac Startup"
echo "================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed"
    echo "Please install Python3 from your package manager"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is not installed"
    echo "Please install pip3 from your package manager"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements-local.txt

# Check if database exists, create if not
if [ ! -f "factory.db" ]; then
    echo "💾 Setting up database..."
    python create_admin.py
    echo "📊 Loading sample data..."
    python create_basic_sample_data.py
fi

# Start the application
echo "🚀 Starting Factory Management System..."
echo ""
python run_local.py