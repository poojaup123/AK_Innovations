import os
import sys
from pathlib import Path

# Load environment variables from .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, environment variables should be set externally
    pass

from app import create_app, db

def setup_database(app):
    """Initialize database and create default admin user"""
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            print("✅ Database tables created/verified")
            
            # Ensure default admin user exists
            from models import User
            from werkzeug.security import generate_password_hash
            
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User()
                admin_user.username = 'admin'
                admin_user.email = 'admin@yourfactory.com'
                admin_user.password_hash = generate_password_hash('admin123')
                admin_user.role = 'admin'
                db.session.add(admin_user)
                db.session.commit()
                print("✅ Default admin user created (admin/admin123)")
            else:
                print("✅ Admin user already exists")
                
        except Exception as e:
            print(f"⚠️ Database setup warning: {e}")
            print("   This is normal on first run - continuing...")

def main():
    """Main application entry point"""
    print("🏭 Factory Management System")
    print("=" * 40)
    
    # Create Flask application
    app = create_app()
    
    # Setup database
    setup_database(app)
    
    # Print startup information
    print()
    print("🚀 Starting server...")
    print("📍 Local URL: http://localhost:5000")
    print("📍 Network URL: http://0.0.0.0:5000")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    # For local development, use Flask's built-in server
    # For production, use a proper WSGI server
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=debug_mode,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)

# Create app instance for gunicorn/other WSGI servers
app = create_app()
setup_database(app)

if __name__ == '__main__':
    main()
