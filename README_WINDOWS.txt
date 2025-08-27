🏭 FACTORY MANAGEMENT SYSTEM - WINDOWS QUICK START
========================================================

📋 QUICK SETUP (5 minutes)
===========================

STEP 1: Requirements
- Windows 10/11
- Python 3.8+ (download from python.org)
- 2GB free disk space

STEP 2: One-Click Setup
- Extract all files to a folder (e.g., C:\FactoryManagement\)
- Double-click "run_local.bat"
- Wait for automatic setup to complete
- Browser opens automatically at http://localhost:5000

STEP 3: First Login
- Username: admin
- Password: admin123
- CHANGE these immediately after login!

🚀 STARTUP OPTIONS
==================

OPTION A: Double-click "run_local.bat" (Automatic setup + start)
OPTION B: Double-click "start_server.bat" (Quick start)
OPTION C: Command line:
   1. Open Command Prompt in project folder
   2. Type: python main.py

📁 IMPORTANT FILES
==================

run_local.bat          - Complete setup and start (recommended)
start_server.bat       - Quick start server only
local_requirements.txt - Python dependencies
.env.example           - Configuration template  
WINDOWS_SETUP.md       - Detailed documentation
install_windows.py     - Alternative setup script

🔧 CONFIGURATION
================

Edit .env file to configure:
- Company information
- Email/SMS notifications (optional)
- Database settings
- AI features (optional)

📱 ACCESS URLS
==============

Local computer:  http://localhost:5000
Network access:  http://YOUR-IP:5000
Mobile/tablet:   http://YOUR-IP:5000

🗄️ DATABASE
============

Default: SQLite (no setup required)
File location: factory_management.db

For production: Configure PostgreSQL in .env file

🆘 TROUBLESHOOTING
==================

"Python not found"
- Install Python from python.org
- Make sure "Add to PATH" is checked

"Permission denied"
- Run as Administrator
- Check antivirus settings

"Port 5000 in use"
- Change port in main.py
- Or stop conflicting program

Can't access from other devices:
- Check Windows Firewall
- Ensure connected to same network
- Use computer's IP address

🎯 FEATURES INCLUDED
====================

✅ Inventory Management with Batch Tracking
✅ Purchase Orders & GRN Processing  
✅ Job Work Management (In-house & Outsourced)
✅ Production Planning & BOM Management
✅ Sales Orders & Invoice Generation
✅ Quality Control & Inspection
✅ Financial Reports & Analytics
✅ User Management & Permissions
✅ Mobile-Responsive Interface
✅ Data Export (Excel/PDF)

📞 NEED HELP?
=============

1. Check console output for error messages
2. Review WINDOWS_SETUP.md for detailed guide
3. Ensure .env file is properly configured
4. Verify Python and dependencies are installed

💡 TIPS
=======

- Backup your .env file and database regularly
- Use PostgreSQL for better performance with large data
- Configure email/SMS for automated notifications
- Set up proper user accounts for your team
- Regularly update admin password for security

🎉 YOU'RE READY TO GO!
=====================

The Factory Management System is now running on your Windows machine.
Access it at http://localhost:5000 and start managing your factory operations!

For detailed documentation, see WINDOWS_SETUP.md