from datetime import datetime
from app import db
import json

class CustomReport(db.Model):
    """Model for storing custom report configurations"""
    __tablename__ = 'custom_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    report_type = db.Column(db.String(50), nullable=False)  # inventory, purchase, sales, etc.
    
    # Report configuration stored as JSON
    config = db.Column(db.Text, nullable=False)  # JSON config for fields, filters, etc.
    
    # Access control
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)  # Whether other users can access
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='custom_reports')
    
    def get_config(self):
        """Parse JSON config"""
        try:
            return json.loads(self.config)
        except:
            return {}
    
    def set_config(self, config_dict):
        """Set config from dictionary"""
        self.config = json.dumps(config_dict)
    
    @property
    def report_type_display(self):
        """Human readable report type"""
        type_mapping = {
            'inventory': 'Inventory',
            'purchase': 'Purchase Orders',
            'sales': 'Sales Orders',
            'jobwork': 'Job Work',
            'production': 'Production',
            'employee': 'Employee',
            'expenses': 'Factory Expenses',
            'quality': 'Quality Control',
            'mixed': 'Mixed Data'
        }
        return type_mapping.get(self.report_type, self.report_type.title())
    
    def __repr__(self):
        return f'<CustomReport {self.name}>'

class CustomReportExecution(db.Model):
    """Model for tracking custom report executions"""
    __tablename__ = 'custom_report_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    custom_report_id = db.Column(db.Integer, db.ForeignKey('custom_reports.id'), nullable=False)
    executed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    execution_time = db.Column(db.DateTime, default=datetime.utcnow)
    row_count = db.Column(db.Integer)  # Number of rows returned
    export_format = db.Column(db.String(20))  # csv, excel, pdf
    
    # Relationships
    custom_report = db.relationship('CustomReport', backref='executions')
    executor = db.relationship('User', backref='report_executions')
    
    def __repr__(self):
        return f'<CustomReportExecution {self.custom_report.name} by {self.executor.username}>'