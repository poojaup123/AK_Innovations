#!/usr/bin/env python3
"""
Local Setup Script for Factory Management System
Run this script to set up the application on your local Windows system
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def check_python_version():
    """Check if Python 3.8+ is installed"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def create_virtual_environment():
    """Create and activate virtual environment"""
    venv_path = Path("venv")
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
    else:
        print("✅ Virtual environment already exists")
    
    # Print activation instructions
    if os.name == 'nt':  # Windows
        activate_script = "venv\\Scripts\\activate.bat"
    else:  # Unix/Linux/Mac
        activate_script = "source venv/bin/activate"
    
    print(f"🔧 Activate it with: {activate_script}")
    return str(venv_path)

def install_dependencies():
    """Install Python dependencies"""
    print("📚 Installing dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "local_requirements.txt"
        ], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def setup_database():
    """Set up SQLite database for local development"""
    print("🗄️ Setting up local SQLite database...")
    
    # Create database file
    db_path = "factory_management.db"
    
    try:
        # Just create the file - Flask-SQLAlchemy will handle the schema
        conn = sqlite3.connect(db_path)
        conn.close()
        print(f"✅ Database file created: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def create_env_file():
    """Create .env file from template"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚙️ Creating .env file...")
        
        env_content = """# Factory Management System - Local Development
DATABASE_URL=sqlite:///factory_management.db
SESSION_SECRET=dev-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=True

# Optional: Configure these if you want email/SMS features
# SENDGRID_API_KEY=your-sendgrid-api-key
# TWILIO_ACCOUNT_SID=your-twilio-sid
# TWILIO_AUTH_TOKEN=your-twilio-token
# TWILIO_PHONE_NUMBER=your-twilio-phone
# OPENAI_API_KEY=your-openai-key

# Company settings
COMPANY_NAME=Your Factory Name
COMPANY_ADDRESS=Your Factory Address
COMPANY_PHONE=+91-XXX-XXXXXXX
COMPANY_EMAIL=info@yourfactory.com
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        print("✅ .env file created")
    else:
        print("✅ .env file already exists")

def create_run_script():
    """Create run script for Windows"""
    print("🚀 Creating run script...")
    
    # Windows batch script
    batch_content = """@echo off
echo Starting Factory Management System...
echo.

REM Activate virtual environment
call venv\\Scripts\\activate.bat

REM Set environment variables
set FLASK_APP=main.py
set FLASK_ENV=development

REM Run the application
echo Starting Flask application on http://localhost:5000
echo Press Ctrl+C to stop the server
echo.
python main.py

pause
"""
    
    with open("run_local.bat", "w") as f:
        f.write(batch_content)
    
    # Also create a Python script version
    python_content = """#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def main():
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Set environment variables
    os.environ['FLASK_APP'] = 'main.py'
    os.environ['FLASK_ENV'] = 'development'
    
    print("🏭 Starting Factory Management System...")
    print("📍 Server will run on: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    # Import and run the app
    try:
        from main import app
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    with open("run_local.py", "w") as f:
        f.write(python_content)
    
    print("✅ Run scripts created (run_local.bat and run_local.py)")

def main():
    """Main setup function"""
    print("🏭 Factory Management System - Local Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Create virtual environment
    create_virtual_environment()
    
    print("\\n📋 Next Steps:")
    print("1. Activate virtual environment:")
    if os.name == 'nt':
        print("   venv\\Scripts\\activate.bat")
    else:
        print("   source venv/bin/activate")
    
    print("2. Install dependencies:")
    print("   pip install -r local_requirements.txt")
    
    print("3. Set up environment:")
    create_env_file()
    
    print("4. Create run scripts:")
    create_run_script()
    
    print("\\n🚀 Setup complete! To start the application:")
    print("   • On Windows: run_local.bat")
    print("   • Or run: python run_local.py")
    print("   • Then visit: http://localhost:5000")
    
    print("\\n📝 Notes:")
    print("   • Uses SQLite database (no PostgreSQL needed)")
    print("   • Edit .env file to configure optional features")
    print("   • First run will create database tables automatically")

if __name__ == "__main__":
    main()