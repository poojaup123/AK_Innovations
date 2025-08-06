from app import db
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class Permission(db.Model):
    """Model for system permissions"""
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), nullable=False)
    
    def __repr__(self):
        return f'<Permission {self.code}>'

class UserPermission(db.Model):
    """Model for user-specific permissions"""
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
    granted = db.Column(db.Boolean, default=True, nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="user_permissions")
    permission = relationship("Permission", backref="user_permissions")
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    def __repr__(self):
        return f'<UserPermission {self.user_id}:{self.permission_id}>'

# Permission categories and their permissions
DEFAULT_PERMISSIONS = {
    'inventory': [
        ('inventory_view', 'View Inventory', 'View inventory items and stock levels'),
        ('inventory_create', 'Add Inventory Items', 'Create new inventory items'),
        ('inventory_edit', 'Edit Inventory Items', 'Modify existing inventory items'),
        ('inventory_delete', 'Delete Inventory Items', 'Delete inventory items'),
    ],
    'purchase': [
        ('purchase_view', 'View Purchase Orders', 'View purchase orders and details'),
        ('purchase_create', 'Create Purchase Orders', 'Create new purchase orders'),
        ('purchase_edit', 'Edit Purchase Orders', 'Modify existing purchase orders'),
        ('purchase_approve', 'Approve Purchase Orders', 'Approve purchase orders'),
        ('purchase_delete', 'Delete Purchase Orders', 'Delete purchase orders'),
    ],
    'sales': [
        ('sales_view', 'View Sales Orders', 'View sales orders and details'),
        ('sales_create', 'Create Sales Orders', 'Create new sales orders'),
        ('sales_edit', 'Edit Sales Orders', 'Modify existing sales orders'),
        ('sales_approve', 'Approve Sales Orders', 'Approve sales orders'),
        ('sales_delete', 'Delete Sales Orders', 'Delete sales orders'),
    ],
    'production': [
        ('production_view', 'View Production Orders', 'View production orders and status'),
        ('production_create', 'Create Production Orders', 'Create new production orders'),
        ('production_edit', 'Edit Production Orders', 'Modify existing production orders'),
        ('production_approve', 'Approve Production Orders', 'Approve production orders'),
        ('production_start', 'Start Production', 'Start production processes'),
        ('production_complete', 'Complete Production', 'Mark production as completed'),
    ],
    'jobwork': [
        ('jobwork_view', 'View Job Work', 'View job work orders and status'),
        ('jobwork_create', 'Create Job Work', 'Create new job work orders'),
        ('jobwork_edit', 'Edit Job Work', 'Modify existing job work orders'),
        ('jobwork_approve', 'Approve Job Work', 'Approve job work orders'),
    ],
    'quality': [
        ('quality_view', 'View Quality Control', 'View quality issues and inspections'),
        ('quality_create', 'Create Quality Issues', 'Create quality control issues'),
        ('quality_edit', 'Edit Quality Issues', 'Modify quality control data'),
        ('quality_inspect', 'Perform Inspections', 'Conduct material inspections'),
    ],
    'employees': [
        ('employees_view', 'View Employees', 'View employee information'),
        ('employees_create', 'Add Employees', 'Add new employees'),
        ('employees_edit', 'Edit Employees', 'Modify employee information'),
        ('employees_delete', 'Delete Employees', 'Delete employee records'),
        ('payroll_view', 'View Payroll', 'View salary and advance records'),
        ('payroll_process', 'Process Payroll', 'Process salary payments'),
    ],
    'expenses': [
        ('expenses_view', 'View Factory Expenses', 'View factory expense records'),
        ('expenses_create', 'Create Factory Expenses', 'Create new expense entries'),
        ('expenses_edit', 'Edit Factory Expenses', 'Modify expense records'),
        ('expenses_approve', 'Approve Expenses', 'Approve factory expenses'),
    ],
    'reports': [
        ('reports_view', 'View Reports', 'Access reporting dashboard'),
        ('reports_export', 'Export Reports', 'Export data to Excel/PDF'),
        ('reports_financial', 'Financial Reports', 'Access financial reporting'),
    ],
    'settings': [
        ('settings_company', 'Company Settings', 'Modify company information'),
        ('settings_users', 'User Management', 'Manage system users'),
        ('settings_permissions', 'Permission Management', 'Assign user permissions'),
        ('settings_notifications', 'Notification Settings', 'Configure notifications'),
        ('settings_backup', 'Data Backup', 'Access data backup features'),
        ('settings_reset', 'Database Reset', 'Reset system data'),
    ],
    'admin': [
        ('admin_full_access', 'Full Admin Access', 'Complete system access'),
        ('admin_tally_integration', 'Tally Integration', 'Access Tally integration features'),
        ('admin_approval_override', 'Override Approvals', 'Bypass approval workflows'),
    ]
}

def init_permissions():
    """Initialize default permissions in the database"""
    from app import db
    
    for category, perms in DEFAULT_PERMISSIONS.items():
        for code, name, description in perms:
            existing = Permission.query.filter_by(code=code).first()
            if not existing:
                permission = Permission(
                    code=code,
                    name=name,
                    description=description,
                    category=category
                )
                db.session.add(permission)
    
    try:
        db.session.commit()
        print("Default permissions initialized successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing permissions: {e}")