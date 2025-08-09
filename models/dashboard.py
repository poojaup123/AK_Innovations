from app import db
from datetime import datetime
from flask_login import current_user

class DashboardModule(db.Model):
    """Available dashboard modules"""
    __tablename__ = 'dashboard_modules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50), nullable=False)
    url_endpoint = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserDashboardPreference(db.Model):
    """User-specific dashboard preferences"""
    __tablename__ = 'user_dashboard_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('dashboard_modules.id'), nullable=False)
    is_visible = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)  # For ordering modules
    size = db.Column(db.String(20), default='medium')  # small, medium, large
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='dashboard_preferences')
    module = db.relationship('DashboardModule', backref='user_preferences')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'module_id'),)

def init_default_modules():
    """Initialize default dashboard modules"""
    default_modules = [
        {
            'name': 'inventory',
            'title': 'Inventory',
            'description': 'Manage inventory items and stock levels',
            'icon': 'fas fa-boxes',
            'url_endpoint': 'inventory.dashboard'
        },
        {
            'name': 'production',
            'title': 'Production',
            'description': 'Production orders and manufacturing',
            'icon': 'fas fa-cogs',
            'url_endpoint': 'production.dashboard'
        },
        {
            'name': 'jobwork',
            'title': 'Job Work',
            'description': 'External job work management',
            'icon': 'fas fa-tools',
            'url_endpoint': 'jobwork.dashboard'
        },
        {
            'name': 'sales',
            'title': 'Sales Orders',
            'description': 'Customer orders and sales tracking',
            'icon': 'fas fa-chart-line',
            'url_endpoint': 'sales.dashboard'
        },
        {
            'name': 'purchase',
            'title': 'Purchase Orders',
            'description': 'Supplier orders and procurement',
            'icon': 'fas fa-file-invoice',
            'url_endpoint': 'purchase.dashboard'
        },
        {
            'name': 'reports',
            'title': 'Reports & Analytics',
            'description': 'Business reports and data analytics',
            'icon': 'fas fa-chart-bar',
            'url_endpoint': 'reports_dashboard'
        },
        {
            'name': 'notifications',
            'title': 'Notifications',
            'description': 'System notifications and alerts',
            'icon': 'fas fa-bell',
            'url_endpoint': 'notifications_dashboard'
        },
        {
            'name': 'quality_control',
            'title': 'Quality Control',
            'description': 'Quality inspections and issue tracking',
            'icon': 'fas fa-shield-alt',
            'url_endpoint': 'quality.dashboard'
        },

        {
            'name': 'factory_expenses',
            'title': 'Factory Expenses',
            'description': 'Factory operational expenses tracking',
            'icon': 'fas fa-receipt',
            'url_endpoint': 'expenses.dashboard'
        },
        {
            'name': 'tally_integration',
            'title': 'Tally Integration',
            'description': 'Accounting system integration',
            'icon': 'fas fa-exchange-alt',
            'url_endpoint': 'tally.dashboard'
        },
        {
            'name': 'documents',
            'title': 'Document Management',
            'description': 'File and document management system',
            'icon': 'fas fa-folder-open',
            'url_endpoint': 'documents.list'
        },
        {
            'name': 'employees',
            'title': 'Employees',
            'description': 'HR and employee management',
            'icon': 'fas fa-users',
            'url_endpoint': 'hr.dashboard'
        },
        {
            'name': 'packing',
            'title': 'Packing Optimization',
            'description': 'Material cutting and layout optimization using advanced algorithms',
            'icon': 'fas fa-cubes',
            'url_endpoint': 'packing.dashboard'
        }

    ]
    
    for module_data in default_modules:
        existing = DashboardModule.query.filter_by(name=module_data['name']).first()
        if not existing:
            module = DashboardModule(**module_data)
            db.session.add(module)
    
    db.session.commit()

def get_user_dashboard_modules(user_id):
    """Get user's customized dashboard modules"""
    # Get user preferences
    preferences = db.session.query(UserDashboardPreference, DashboardModule).join(
        DashboardModule, UserDashboardPreference.module_id == DashboardModule.id
    ).filter(
        UserDashboardPreference.user_id == user_id,
        UserDashboardPreference.is_visible == True,
        DashboardModule.is_active == True
    ).order_by(UserDashboardPreference.position).all()
    
    if preferences:
        return [{'preference': pref, 'module': module} for pref, module in preferences]
    
    # If no preferences exist, initialize defaults for the user first
    init_user_default_preferences(user_id)
    
    # Then get the newly created preferences
    preferences = db.session.query(UserDashboardPreference, DashboardModule).join(
        DashboardModule, UserDashboardPreference.module_id == DashboardModule.id
    ).filter(
        UserDashboardPreference.user_id == user_id,
        UserDashboardPreference.is_visible == True,
        DashboardModule.is_active == True
    ).order_by(UserDashboardPreference.position).all()
    
    return [{'preference': pref, 'module': module} for pref, module in preferences]

def init_user_default_preferences(user_id):
    """Initialize default preferences for a new user"""
    existing_prefs = UserDashboardPreference.query.filter_by(user_id=user_id).first()
    if existing_prefs:
        return  # User already has preferences
    
    modules = DashboardModule.query.filter_by(is_active=True).all()
    for index, module in enumerate(modules):
        preference = UserDashboardPreference(
            user_id=user_id,
            module_id=module.id,
            is_visible=True,
            position=index,
            size='medium'
        )
        db.session.add(preference)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing user preferences: {e}")
        db.session.add(preference)
    
    db.session.commit()