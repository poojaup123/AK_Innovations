#!/usr/bin/env python3
"""
Local Development Runner for Factory Management System
"""
import os
from app import app

if __name__ == "__main__":
    # Set environment variables for local development
    os.environ.setdefault('DATABASE_URL', 'sqlite:///factory.db')
    os.environ.setdefault('SESSION_SECRET', 'local-dev-secret-key-change-in-production')
    
    print("=" * 60)
    print("🏭 Factory Management System - Local Development")
    print("=" * 60)
    print("📍 Server: http://localhost:5000")
    print("👤 Default Login: admin / admin123")
    print("🔧 Environment: Development")
    print("💾 Database: SQLite (factory.db)")
    print("=" * 60)
    print("\n🚀 Starting server...\n")
    
    # Run Flask development server
    app.run(
        host='127.0.0.1',  # localhost only for security
        port=5000,
        debug=True,
        use_reloader=True,
        use_debugger=True
    )