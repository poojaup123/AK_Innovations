# Factory Management System - Local Setup Guide

## Prerequisites

Before setting up the application locally, ensure you have the following installed:

1. **Python 3.8 or higher**
   - Download from [python.org](https://python.org/downloads/)
   - Verify installation: `python --version`

2. **pip (Python package manager)**
   - Usually comes with Python
   - Verify installation: `pip --version`

3. **Git** (optional, for version control)
   - Download from [git-scm.com](https://git-scm.com/)

## Step 1: Download the Application

1. Download all project files from Replit
2. Create a new folder on your computer (e.g., `factory-management`)
3. Extract all files into this folder

## Step 2: Set up Virtual Environment (Recommended)

```bash
# Navigate to your project folder
cd factory-management

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

## Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements-local.txt
```

## Step 4: Set up Environment Variables

Create a `.env` file in the root directory with the following content:

```env
# Database Configuration
DATABASE_URL=sqlite:///factory.db

# Session Security
SESSION_SECRET=your-super-secret-key-change-this

# Optional: Email Notifications (SendGrid)
SENDGRID_API_KEY=your-sendgrid-api-key

# Optional: SMS/WhatsApp Notifications (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number
```

**Important:** Change `SESSION_SECRET` to a random, secure string.

## Step 5: Initialize Database

```bash
# Create admin user and initialize database
python create_admin.py

# Load sample data (optional)
python create_sample_data.py
```

## Step 6: Run the Application

```bash
# Start the Flask development server
python main.py
```

The application will be available at: `http://localhost:5000`

## Default Login Credentials

- **Username:** admin
- **Password:** admin123

**Important:** Change the admin password after first login!

## Directory Structure

```
factory-management/
├── app.py                 # Flask app configuration
├── main.py               # Application entry point
├── models.py             # Database models
├── forms.py              # Form definitions
├── config.py             # Configuration settings
├── routes/               # Route blueprints
│   ├── auth.py
│   ├── inventory.py
│   ├── jobwork.py
│   └── ...
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── uploads/              # File uploads
└── requirements-local.txt # Dependencies
```

## Troubleshooting

### Common Issues:

1. **Port already in use:**
   ```bash
   # Kill process using port 5000
   # Windows:
   netstat -ano | findstr :5000
   taskkill /PID <PID_NUMBER> /F
   
   # macOS/Linux:
   lsof -ti:5000 | xargs kill -9
   ```

2. **Database errors:**
   ```bash
   # Delete database and recreate
   rm factory.db
   python create_admin.py
   ```

3. **Missing dependencies:**
   ```bash
   # Reinstall all packages
   pip install -r requirements-local.txt --force-reinstall
   ```

## Features Available Locally

✓ Complete inventory management
✓ Purchase and sales orders
✓ Job work tracking with team assignments
✓ Employee management and attendance
✓ Quality control system
✓ Factory expenses with OCR
✓ Reporting and analytics
✓ Document management
✓ Tally integration
✓ Email/SMS notifications (with API keys)

## Production Deployment

For production deployment, consider:
- Using PostgreSQL instead of SQLite
- Setting up proper environment variables
- Using a WSGI server like Gunicorn
- Implementing proper logging
- Setting up SSL certificates

## Support

If you encounter any issues:
1. Check the console for error messages
2. Verify all dependencies are installed
3. Ensure environment variables are set correctly
4. Check file permissions