@echo off
echo 🏭 Factory Management System - Local Development
echo ================================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are installed
echo 📚 Installing/updating dependencies...
pip install -r local_requirements.txt

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo ⚙️ Creating .env file...
    copy .env.example .env
    echo ✅ .env file created from template
)

REM Set Flask environment variables
set FLASK_APP=main.py
set FLASK_ENV=development
set FLASK_DEBUG=1

REM Create database tables (if needed)
echo 🗄️ Setting up database...
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('✅ Database tables created')"

echo.
echo 🚀 Starting Factory Management System...
echo 📍 Server running on: http://localhost:5000
echo 🛑 Press Ctrl+C to stop the server
echo.

REM Run the application
python main.py

echo.
echo 👋 Server stopped. Press any key to exit...
pause