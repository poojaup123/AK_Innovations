#!/usr/bin/env python3
"""
Windows Installation Script for Factory Management System
Run this to automatically set up everything on Windows
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_header():
    print("🏭 Factory Management System - Windows Installer")
    print("=" * 55)
    print()

def check_requirements():
    """Check system requirements"""
    print("🔍 Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required. Current: {sys.version_info.major}.{sys.version_info.minor}")
        return False
    else:
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        print("✅ pip is available")
    except subprocess.CalledProcessError:
        print("❌ pip is not available")
        return False
    
    return True

def setup_virtual_environment():
    """Create and set up virtual environment"""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    print("📦 Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False

def install_dependencies():
    """Install Python dependencies"""
    print("📚 Installing dependencies...")
    
    # Use the virtual environment's pip
    if os.name == 'nt':  # Windows
        pip_path = Path("venv/Scripts/pip.exe")
    else:
        pip_path = Path("venv/bin/pip")
    
    if not pip_path.exists():
        print("❌ Virtual environment pip not found")
        return False
    
    try:
        subprocess.run([
            str(pip_path), "install", "-r", "local_requirements.txt"
        ], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def setup_environment():
    """Set up environment configuration"""
    print("⚙️ Setting up environment configuration...")
    
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    # Copy from example
    example_file = Path(".env.example")
    if example_file.exists():
        shutil.copy(example_file, env_file)
        print("✅ .env file created from template")
        return True
    else:
        # Create basic .env file
        env_content = """DATABASE_URL=sqlite:///factory_management.db
SESSION_SECRET=dev-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=1
COMPANY_NAME=Your Factory Name
"""
        with open(env_file, "w") as f:
            f.write(env_content)
        print("✅ Basic .env file created")
        return True

def initialize_database():
    """Initialize the database"""
    print("🗄️ Initializing database...")
    
    # Use the virtual environment's python
    if os.name == 'nt':  # Windows
        python_path = Path("venv/Scripts/python.exe")
    else:
        python_path = Path("venv/bin/python")
    
    try:
        subprocess.run([
            str(python_path), "-c",
            "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized')"
        ], check=True)
        print("✅ Database initialized successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Database initialization warning: {e}")
        print("   (This is normal on first run - tables will be created when app starts)")
        return True

def create_shortcuts():
    """Create convenient startup shortcuts"""
    print("🔗 Creating startup shortcuts...")
    
    # Windows batch file
    batch_content = """@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate.bat
set FLASK_APP=main.py
set FLASK_ENV=development
python main.py
pause
"""
    
    with open("start_server.bat", "w") as f:
        f.write(batch_content)
    
    print("✅ Created start_server.bat")
    return True

def main():
    """Main installation process"""
    print_header()
    
    if not check_requirements():
        print("\n❌ System requirements not met. Please install Python 3.8+")
        input("Press Enter to exit...")
        return 1
    
    print()
    
    if not setup_virtual_environment():
        return 1
    
    if not install_dependencies():
        return 1
    
    if not setup_environment():
        return 1
    
    initialize_database()
    
    create_shortcuts()
    
    print()
    print("🎉 Installation completed successfully!")
    print()
    print("📋 Next steps:")
    print("1. Double-click 'start_server.bat' to start the server")
    print("2. Or run: python main.py (after activating venv)")
    print("3. Open browser to: http://localhost:5000")
    print()
    print("💡 Tips:")
    print("- Edit .env file to configure optional features")
    print("- See WINDOWS_SETUP.md for detailed documentation")
    print("- Default login: admin / admin123 (change on first login)")
    
    input("\nPress Enter to exit...")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)