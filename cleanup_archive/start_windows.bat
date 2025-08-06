@echo off
echo.
echo ================================================
echo  Factory Management System - Windows Startup
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python from https://python.org/downloads/
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements-local.txt

REM Check if database exists, create if not
if not exist "factory.db" (
    echo 💾 Setting up database...
    python create_admin.py
    echo 📊 Loading sample data...
    python create_basic_sample_data.py
)

REM Start the application
echo 🚀 Starting Factory Management System...
echo.
python run_local.py

pause