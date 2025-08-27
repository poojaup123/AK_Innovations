@echo off
title Factory Management System - Local Server

echo 🏭 Factory Management System - Starting Local Server
echo =====================================================
echo.

REM Check if we're in the right directory
if not exist "main.py" (
    echo ❌ Error: main.py not found!
    echo Please run this script from the project root directory.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo 🔧 Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ Virtual environment not found. Using global Python...
)

REM Set environment variables
set FLASK_APP=main.py
set FLASK_ENV=development
set FLASK_DEBUG=1

echo.
echo 🚀 Starting Factory Management System...
echo 📍 Server will be available at: http://localhost:5000
echo 🛑 Press Ctrl+C to stop the server
echo.

REM Start the application
python main.py

echo.
echo 👋 Server stopped.
pause