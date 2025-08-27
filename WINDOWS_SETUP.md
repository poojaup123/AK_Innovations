# 🏭 Factory Management System - Windows Setup Guide

This guide will help you set up and run the Factory Management System on your local Windows machine.

## 📋 Prerequisites

### Required Software
1. **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Make sure to check "Add Python to PATH" during installation
   - ✅ Verify installation: `python --version`

2. **Git** (optional) - Download from [git-scm.com](https://git-scm.com/downloads)

### Optional (for advanced features)
- **PostgreSQL** - For production-grade database (SQLite is used by default)
- **Tesseract OCR** - For document scanning features

## 🚀 Quick Start (Automated Setup)

### Option 1: One-Click Setup (Recommended)
1. Download/extract the project files to a folder
2. Double-click `run_local.bat`
3. Wait for setup to complete automatically
4. Open browser to `http://localhost:5000`

### Option 2: Manual Setup

#### Step 1: Setup Virtual Environment
```cmd
# Open Command Prompt in project folder
python -m venv venv
venv\Scripts\activate.bat
```

#### Step 2: Install Dependencies
```cmd
pip install -r local_requirements.txt
```

#### Step 3: Configure Environment
```cmd
# Copy environment template
copy .env.example .env
# Edit .env file with your settings (optional)
```

#### Step 4: Initialize Database
```cmd
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

#### Step 5: Run Application
```cmd
python main.py
```

## 🔧 Configuration

### Database Options

#### SQLite (Default - No setup required)
```env
DATABASE_URL=sqlite:///factory_management.db
```

#### PostgreSQL (Production)
1. Install PostgreSQL on Windows
2. Create database: `createdb factory_management`
3. Update .env file:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/factory_management
```

### Optional Features Configuration

#### Email Notifications (SendGrid)
```env
SENDGRID_API_KEY=your-api-key
FROM_EMAIL=your-email@company.com
```

#### SMS Notifications (Twilio)
```env
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=your-phone-number
```

#### AI Features (OpenAI)
```env
OPENAI_API_KEY=your-openai-api-key
```

## 📁 Project Structure

```
factory-management/
├── app/                    # Application package
├── models/                 # Database models
├── routes/                 # URL routes and controllers
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── services/               # Business logic services
├── utils/                  # Utility functions
├── main.py                 # Application entry point
├── run_local.bat           # Windows setup script
├── local_requirements.txt  # Python dependencies
└── .env                    # Environment configuration
```

## 🎯 First Run

1. **Start the application**
   - Run `run_local.bat` or `python main.py`
   - Wait for "🚀 Performance monitoring enabled" message

2. **Access the application**
   - Open browser: `http://localhost:5000`
   - Default admin credentials will be displayed in console

3. **Initial setup**
   - Create your admin user account
   - Configure company settings
   - Add your first items and suppliers

## 🔑 Default Login

The system will create default admin credentials on first run:
- Username: `admin`
- Password: `admin123`

**⚠️ Change these credentials immediately after first login!**

## 🛠️ Troubleshooting

### Common Issues

#### "Python not found"
- Ensure Python is installed and added to PATH
- Try using `py` instead of `python`

#### "Permission denied" errors
- Run Command Prompt as Administrator
- Check antivirus software isn't blocking files

#### Database connection errors
- For SQLite: Check file permissions in project folder
- For PostgreSQL: Verify service is running and credentials are correct

#### Missing dependencies
- Run: `pip install -r local_requirements.txt --upgrade`
- Try: `pip install --force-reinstall -r local_requirements.txt`

#### Port 5000 already in use
- Change port in main.py: `app.run(port=5001)`
- Or find and stop the conflicting process

### Performance Optimization

#### For better performance:
1. **Use PostgreSQL** instead of SQLite for larger datasets
2. **Enable caching** in production settings
3. **Configure proper logging** levels
4. **Use production WSGI server** like Waitress for Windows

## 📞 Support

### Getting Help
- Check console output for error messages
- Review log files in `logs/` directory
- Ensure all environment variables are properly set

### System Requirements
- **Minimum**: Windows 10, 4GB RAM, 2GB disk space
- **Recommended**: Windows 11, 8GB RAM, 5GB disk space
- **Python**: 3.8 or higher
- **Browser**: Chrome, Firefox, Edge (latest versions)

## 🔄 Updates

To update the application:
1. Backup your `.env` file and database
2. Download new version
3. Run `run_local.bat` to reinstall dependencies
4. Restore your configuration files

---

**🎉 You're all set! The Factory Management System should now be running on your Windows machine.**

For production deployment, consider using a proper web server like IIS with FastCGI or a cloud platform.