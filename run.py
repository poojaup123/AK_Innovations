"""
Entry point for Factory Management System
Creates and runs the Flask application using the application factory pattern
"""

import os
from app import create_app

# Create Flask application instance
app = create_app()

if __name__ == '__main__':
    # Development server configuration
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)