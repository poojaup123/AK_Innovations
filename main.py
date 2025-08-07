from app import create_app, db

app = create_app()

with app.app_context():
    # Create database tables
    db.create_all()
    
    # Ensure default admin user exists
    from models import User
    from werkzeug.security import generate_password_hash
    
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@akinnovations.com',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
