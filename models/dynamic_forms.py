"""
Dynamic Form System Models
Allows creating flexible, customizable forms with dynamic field management
"""

from app import db
from datetime import datetime
import json
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property

class FormTemplate(db.Model):
    """Master template for dynamic forms"""
    __tablename__ = 'form_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(50), nullable=False, unique=True)  # e.g., 'bom', 'job_work', 'purchase_order'
    description = db.Column(db.Text)
    module = db.Column(db.String(50), nullable=False)  # e.g., 'production', 'inventory', 'purchase'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    fields = db.relationship('CustomField', backref='form_template', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<FormTemplate {self.name}>'
    
    @property
    def active_fields(self):
        """Get all active custom fields for this form"""
        return self.fields.filter_by(is_active=True).order_by(CustomField.display_order).all()
    
    @property
    def field_count(self):
        """Total number of active fields"""
        return self.fields.filter_by(is_active=True).count()

class CustomField(db.Model):
    """Dynamic custom fields that can be added to any form"""
    __tablename__ = 'custom_fields'
    
    id = db.Column(db.Integer, primary_key=True)
    form_template_id = db.Column(db.Integer, db.ForeignKey('form_templates.id'), nullable=False)
    
    # Field Definition
    field_name = db.Column(db.String(100), nullable=False)  # Internal name (snake_case)
    label = db.Column(db.String(200), nullable=False)  # Display label
    field_type = db.Column(db.String(50), nullable=False)  # text, number, select, checkbox, date, textarea, etc.
    
    # Field Configuration
    is_required = db.Column(db.Boolean, default=False)
    default_value = db.Column(db.Text)  # JSON string for complex defaults
    placeholder = db.Column(db.String(200))
    help_text = db.Column(db.Text)
    validation_rules = db.Column(db.Text)  # JSON string with validation rules
    
    # Select/Dropdown Options
    field_options = db.Column(db.Text)  # JSON array for select options
    
    # Display Configuration
    display_order = db.Column(db.Integer, default=0)
    field_group = db.Column(db.String(100))  # Group fields into sections
    column_width = db.Column(db.Integer, default=12)  # Bootstrap column width (1-12)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    field_values = db.relationship('CustomFieldValue', backref='custom_field', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CustomField {self.field_name} ({self.field_type})>'
    
    @hybrid_property
    def options_list(self):
        """Parse field_options JSON into Python list"""
        if self.field_options:
            try:
                return json.loads(self.field_options)
            except:
                return []
        return []
    
    @options_list.setter
    def options_list(self, value):
        """Set field_options from Python list"""
        if value:
            self.field_options = json.dumps(value)
        else:
            self.field_options = None
    
    @hybrid_property
    def validation_dict(self):
        """Parse validation_rules JSON into Python dict"""
        if self.validation_rules:
            try:
                return json.loads(self.validation_rules)
            except:
                return {}
        return {}
    
    @validation_dict.setter
    def validation_dict(self, value):
        """Set validation_rules from Python dict"""
        if value:
            self.validation_rules = json.dumps(value)
        else:
            self.validation_rules = None

class CustomFieldValue(db.Model):
    """Stores values for custom fields across different records"""
    __tablename__ = 'custom_field_values'
    
    id = db.Column(db.Integer, primary_key=True)
    custom_field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id'), nullable=False)
    
    # Record Reference - Universal approach
    record_type = db.Column(db.String(50), nullable=False)  # 'bom', 'job_work', 'purchase_order', etc.
    record_id = db.Column(db.Integer, nullable=False)  # ID of the actual record
    
    # Field Value Storage
    value_text = db.Column(db.Text)  # For text, textarea, select values
    value_number = db.Column(db.Float)  # For numeric values
    value_boolean = db.Column(db.Boolean)  # For checkbox values
    value_date = db.Column(db.Date)  # For date values
    value_datetime = db.Column(db.DateTime)  # For datetime values
    value_json = db.Column(db.Text)  # For complex data structures
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint to prevent duplicate values for same field+record
    __table_args__ = (
        db.UniqueConstraint('custom_field_id', 'record_type', 'record_id', name='unique_field_record'),
    )
    
    def __repr__(self):
        return f'<CustomFieldValue {self.custom_field.field_name if self.custom_field else "Unknown"} for {self.record_type}:{self.record_id}>'
    
    @property
    def display_value(self):
        """Get the appropriate value based on field type"""
        if self.custom_field.field_type in ['text', 'textarea', 'select', 'email', 'url']:
            return self.value_text
        elif self.custom_field.field_type in ['number', 'decimal', 'currency']:
            return self.value_number
        elif self.custom_field.field_type == 'checkbox':
            return self.value_boolean
        elif self.custom_field.field_type == 'date':
            return self.value_date
        elif self.custom_field.field_type == 'datetime':
            return self.value_datetime
        elif self.custom_field.field_type == 'json':
            return json.loads(self.value_json) if self.value_json else None
        return None
    
    def set_value(self, value):
        """Set the appropriate value field based on field type"""
        field_type = self.custom_field.field_type
        
        # Clear all value fields first
        self.value_text = None
        self.value_number = None
        self.value_boolean = None
        self.value_date = None
        self.value_datetime = None
        self.value_json = None
        
        if field_type in ['text', 'textarea', 'select', 'email', 'url']:
            self.value_text = str(value) if value is not None else None
        elif field_type in ['number', 'decimal', 'currency']:
            self.value_number = float(value) if value is not None else None
        elif field_type == 'checkbox':
            self.value_boolean = bool(value) if value is not None else False
        elif field_type == 'date':
            if isinstance(value, str):
                from datetime import datetime
                self.value_date = datetime.strptime(value, '%Y-%m-%d').date()
            else:
                self.value_date = value
        elif field_type == 'datetime':
            if isinstance(value, str):
                from datetime import datetime
                self.value_datetime = datetime.fromisoformat(value)
            else:
                self.value_datetime = value
        elif field_type == 'json':
            self.value_json = json.dumps(value) if value is not None else None

class DynamicFormManager:
    """Service class to manage dynamic forms and field values"""
    
    @staticmethod
    def get_form_template(code):
        """Get form template by code"""
        return FormTemplate.query.filter_by(code=code, is_active=True).first()
    
    @staticmethod
    def get_custom_fields(form_code):
        """Get all active custom fields for a form"""
        template = DynamicFormManager.get_form_template(form_code)
        if template:
            return template.active_fields
        return []
    
    @staticmethod
    def get_field_values(record_type, record_id):
        """Get all custom field values for a specific record"""
        return CustomFieldValue.query.filter_by(
            record_type=record_type,
            record_id=record_id
        ).all()
    
    @staticmethod
    def get_field_value(record_type, record_id, field_name):
        """Get specific custom field value"""
        field = CustomField.query.filter_by(field_name=field_name, is_active=True).first()
        if not field:
            return None
            
        value = CustomFieldValue.query.filter_by(
            custom_field_id=field.id,
            record_type=record_type,
            record_id=record_id
        ).first()
        
        return value.display_value if value else None
    
    @staticmethod
    def save_field_values(record_type, record_id, field_data):
        """Save custom field values for a record"""
        for field_name, value in field_data.items():
            field = CustomField.query.filter_by(field_name=field_name, is_active=True).first()
            if not field:
                continue
            
            # Get or create field value record
            field_value = CustomFieldValue.query.filter_by(
                custom_field_id=field.id,
                record_type=record_type,
                record_id=record_id
            ).first()
            
            if not field_value:
                field_value = CustomFieldValue(
                    custom_field_id=field.id,
                    record_type=record_type,
                    record_id=record_id
                )
                db.session.add(field_value)
            
            # Set the value
            field_value.set_value(value)
        
        db.session.commit()
    
    @staticmethod
    def delete_field_values(record_type, record_id):
        """Delete all custom field values for a record"""
        CustomFieldValue.query.filter_by(
            record_type=record_type,
            record_id=record_id
        ).delete()
        db.session.commit()
    
    @staticmethod
    def create_default_templates():
        """Create default form templates for core modules"""
        default_templates = [
            {
                'name': 'Bill of Materials',
                'code': 'bom',
                'description': 'Custom fields for BOM management',
                'module': 'production'
            },
            {
                'name': 'BOM Items',
                'code': 'bom_item',
                'description': 'Custom fields for BOM material items',
                'module': 'production'
            },
            {
                'name': 'BOM Processes',
                'code': 'bom_process',
                'description': 'Custom fields for BOM manufacturing processes',
                'module': 'production'
            },
            {
                'name': 'Job Work',
                'code': 'job_work',
                'description': 'Custom fields for job work management',
                'module': 'job_work'
            },
            {
                'name': 'Purchase Orders',
                'code': 'purchase_order',
                'description': 'Custom fields for purchase order management',
                'module': 'purchase'
            },
            {
                'name': 'Inventory Items',
                'code': 'inventory_item',
                'description': 'Custom fields for inventory management',
                'module': 'inventory'
            },
            {
                'name': 'GRN - Goods Receipt',
                'code': 'grn',
                'description': 'Custom fields for goods receipt notes',
                'module': 'grn'
            },
            {
                'name': 'Sales Orders',
                'code': 'sales_order',
                'description': 'Custom fields for sales order management',
                'module': 'sales'
            }
        ]
        
        for template_data in default_templates:
            existing = FormTemplate.query.filter_by(code=template_data['code']).first()
            if not existing:
                template = FormTemplate(**template_data)
                db.session.add(template)
        
        db.session.commit()

# Create default templates when models are imported
@event.listens_for(FormTemplate.__table__, 'after_create')
def create_default_templates(target, connection, **kw):
    """Automatically create default form templates after table creation"""
    pass  # Will be called manually to avoid circular imports