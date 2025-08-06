"""
Centralized Settings Models for Multi-Company ERP System
Provides configuration controls for all system behaviors
"""

from app import db
from datetime import datetime
from sqlalchemy import func

class Company(db.Model):
    """Multi-company management"""
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    
    # Company Details
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    
    # Legal Information
    gst_number = db.Column(db.String(50))
    arn_number = db.Column(db.String(50))
    pan_number = db.Column(db.String(20))
    cin_number = db.Column(db.String(30))
    website = db.Column(db.String(200))
    
    # Logo and Branding
    logo_path = db.Column(db.String(300))
    letterhead_path = db.Column(db.String(300))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('UserCompanyAccess', backref='company', lazy=True)
    
    @classmethod
    def get_default_company(cls):
        """Get the default company"""
        return cls.query.filter_by(is_default=True, is_active=True).first()
    
    @classmethod
    def set_default_company(cls, company_id):
        """Set a company as default"""
        # Remove default from all companies
        cls.query.update({'is_default': False})
        # Set new default
        company = cls.query.get(company_id)
        if company:
            company.is_default = True
            db.session.commit()
            return True
        return False
    
    def __repr__(self):
        return f'<Company {self.name}>'

class UserCompanyAccess(db.Model):
    """User access to companies"""
    __tablename__ = 'user_company_access'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='company_access')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])
    
    __table_args__ = (db.UniqueConstraint('user_id', 'company_id'),)

class SystemSettings(db.Model):
    """Centralized system configuration"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # inventory, accounting, production, jobwork
    setting_key = db.Column(db.String(100), nullable=False)
    setting_value = db.Column(db.Text)
    data_type = db.Column(db.String(20), default='string')  # string, boolean, integer, float, json
    description = db.Column(db.Text)
    
    # Company-specific or global
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    is_global = db.Column(db.Boolean, default=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    company = db.relationship('Company', backref='settings')
    updated_by_user = db.relationship('User', backref='settings_updated')
    
    __table_args__ = (db.UniqueConstraint('category', 'setting_key', 'company_id'),)
    
    @classmethod
    def get_setting(cls, category, key, company_id=None, default=None):
        """Get a setting value"""
        # Try company-specific first
        if company_id:
            setting = cls.query.filter_by(
                category=category, 
                setting_key=key, 
                company_id=company_id
            ).first()
            if setting:
                return cls._convert_value(setting.setting_value, setting.data_type)
        
        # Fall back to global setting
        setting = cls.query.filter_by(
            category=category, 
            setting_key=key, 
            is_global=True
        ).first()
        
        if setting:
            return cls._convert_value(setting.setting_value, setting.data_type)
        
        return default
    
    @classmethod
    def set_setting(cls, category, key, value, data_type='string', company_id=None, user_id=None, description=None):
        """Set a setting value"""
        # Find existing setting
        filters = {'category': category, 'setting_key': key}
        if company_id:
            filters['company_id'] = company_id
        else:
            filters['is_global'] = True
            
        setting = cls.query.filter_by(**filters).first()
        
        if setting:
            setting.setting_value = str(value)
            setting.data_type = data_type
            setting.updated_by = user_id
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(
                category=category,
                setting_key=key,
                setting_value=str(value),
                data_type=data_type,
                company_id=company_id,
                is_global=company_id is None,
                updated_by=user_id,
                description=description
            )
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @staticmethod
    def _convert_value(value, data_type):
        """Convert string value to appropriate type"""
        if value is None:
            return None
            
        if data_type == 'boolean':
            return value.lower() in ('true', '1', 'yes', 'on')
        elif data_type == 'integer':
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        elif data_type == 'float':
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif data_type == 'json':
            try:
                import json
                return json.loads(value)
            except (ValueError, TypeError):
                return {}
        else:
            return value

class InventorySettings(db.Model):
    """Inventory-specific settings model for easier management"""
    __tablename__ = 'inventory_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    
    # Inventory Behavior Settings
    shared_inventory = db.Column(db.Boolean, default=False)  # Global vs per-company
    stock_valuation_method = db.Column(db.String(20), default='FIFO')  # FIFO, LIFO, Moving Average
    enable_multi_uom = db.Column(db.Boolean, default=True)
    enable_batch_tracking = db.Column(db.Boolean, default=True)
    warn_negative_stock = db.Column(db.Boolean, default=True)
    auto_generate_batch = db.Column(db.Boolean, default=True)
    
    # Stock Control
    minimum_stock_alert = db.Column(db.Boolean, default=True)
    reorder_level_alert = db.Column(db.Boolean, default=True)
    expiry_alert_days = db.Column(db.Integer, default=30)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    company = db.relationship('Company', backref='inventory_settings')
    updated_by_user = db.relationship('User', backref='inventory_settings_updated')

class AccountingSettings(db.Model):
    """Accounting-specific settings"""
    __tablename__ = 'accounting_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    
    # Automation Settings
    auto_journal_entries = db.Column(db.Boolean, default=True)
    auto_grn_accounting = db.Column(db.Boolean, default=True)
    auto_sales_accounting = db.Column(db.Boolean, default=True)
    auto_production_accounting = db.Column(db.Boolean, default=True)
    
    # Default Ledger Mapping
    default_sales_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_purchase_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_wip_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_cogs_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    
    # Financial Year
    financial_year_start = db.Column(db.Date)
    financial_year_end = db.Column(db.Date)
    
    # GST Settings
    default_cgst_rate = db.Column(db.Float, default=9.0)
    default_sgst_rate = db.Column(db.Float, default=9.0)
    default_igst_rate = db.Column(db.Float, default=18.0)
    gst_calculation_method = db.Column(db.String(20), default='inclusive')  # inclusive, exclusive
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    company = db.relationship('Company', backref='accounting_settings')
    updated_by_user = db.relationship('User', backref='accounting_settings_updated')

class ProductionSettings(db.Model):
    """Production-specific settings"""
    __tablename__ = 'production_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    
    # BOM Settings
    enable_nested_bom = db.Column(db.Boolean, default=True)
    auto_cost_calculation = db.Column(db.Boolean, default=True)
    link_output_to_batch = db.Column(db.Boolean, default=True)
    lock_consumption = db.Column(db.Boolean, default=False)
    
    # Production Control
    allow_overproduction = db.Column(db.Boolean, default=False)
    overproduction_limit_percent = db.Column(db.Float, default=10.0)
    require_material_availability = db.Column(db.Boolean, default=True)
    auto_reserve_materials = db.Column(db.Boolean, default=True)
    
    # Quality Control
    mandatory_quality_check = db.Column(db.Boolean, default=False)
    auto_scrap_failed_items = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    company = db.relationship('Company', backref='production_settings')
    updated_by_user = db.relationship('User', backref='production_settings_updated')

class JobWorkSettings(db.Model):
    """Job Work-specific settings"""
    __tablename__ = 'jobwork_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    
    # Job Work Control
    grn_required_on_return = db.Column(db.Boolean, default=True)
    track_vendor_rates = db.Column(db.Boolean, default=True)
    enable_scrap_entry = db.Column(db.Boolean, default=True)
    billing_mode = db.Column(db.String(20), default='manual')  # manual, auto
    
    # Process Tracking
    mandatory_process_selection = db.Column(db.Boolean, default=True)
    allow_partial_returns = db.Column(db.Boolean, default=True)
    auto_calculate_loss = db.Column(db.Boolean, default=True)
    
    # Approval Workflow
    require_approval_for_issue = db.Column(db.Boolean, default=False)
    require_approval_for_return = db.Column(db.Boolean, default=False)
    approval_limit_amount = db.Column(db.Float, default=0.0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    company = db.relationship('Company', backref='jobwork_settings')
    updated_by_user = db.relationship('User', backref='jobwork_settings_updated')

# Default settings to be created during setup
DEFAULT_SETTINGS = {
    'inventory': {
        'shared_inventory': ('false', 'boolean', 'Enable shared inventory across companies'),
        'stock_valuation_method': ('FIFO', 'string', 'Stock valuation method: FIFO, LIFO, Moving Average'),
        'enable_multi_uom': ('true', 'boolean', 'Enable multiple units of measure'),
        'enable_batch_tracking': ('true', 'boolean', 'Enable batch-wise inventory tracking'),
        'warn_negative_stock': ('true', 'boolean', 'Warn when stock goes negative'),
    },
    'accounting': {
        'auto_journal_entries': ('true', 'boolean', 'Automatically create journal entries'),
        'auto_grn_accounting': ('true', 'boolean', 'Auto accounting for GRN transactions'),
        'auto_sales_accounting': ('true', 'boolean', 'Auto accounting for sales transactions'),
        'default_cgst_rate': ('9.0', 'float', 'Default CGST rate percentage'),
        'default_sgst_rate': ('9.0', 'float', 'Default SGST rate percentage'),
        'default_igst_rate': ('18.0', 'float', 'Default IGST rate percentage'),
    },
    'production': {
        'enable_nested_bom': ('true', 'boolean', 'Allow multi-level BOM structures'),
        'auto_cost_calculation': ('true', 'boolean', 'Automatically calculate production costs'),
        'link_output_to_batch': ('true', 'boolean', 'Link production output to batches'),
        'lock_consumption': ('false', 'boolean', 'Prevent overconsumption in production'),
    },
    'jobwork': {
        'grn_required_on_return': ('true', 'boolean', 'Require GRN when job work returns'),
        'track_vendor_rates': ('true', 'boolean', 'Track vendor rates per process'),
        'enable_scrap_entry': ('true', 'boolean', 'Allow scrap entry in job work'),
        'billing_mode': ('manual', 'string', 'Job work billing mode: manual or auto'),
    }
}