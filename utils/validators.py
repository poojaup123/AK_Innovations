"""
Enhanced Validation Utilities
Custom validators with user-friendly error messages for manufacturing management
"""

from wtforms.validators import ValidationError, Regexp
import re
from decimal import Decimal, InvalidOperation

class UserFriendlyValidator:
    """Base class for user-friendly validators"""
    
    def __init__(self, message=None):
        self.message = message
    
    def __call__(self, form, field):
        if not self.validate_field(form, field):
            raise ValidationError(self.message or self.get_default_message())
    
    def validate_field(self, form, field):
        """Override this method in subclasses"""
        return True
    
    def get_default_message(self):
        """Override this method to provide default error message"""
        return "Invalid input"

class IndianPhoneValidator(UserFriendlyValidator):
    """Validates Indian mobile phone numbers"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        # Remove all non-digits
        phone = re.sub(r'\D', '', str(field.data))
        
        # Check if it's a valid Indian mobile number (10 digits starting with 6-9)
        return re.match(r'^[6-9]\d{9}$', phone) is not None
    
    def get_default_message(self):
        return "Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9"

class GSTNumberValidator(UserFriendlyValidator):
    """Validates Indian GST numbers"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        gst = str(field.data).strip().upper()
        
        # GST format: 15 characters (2 state code + 10 PAN + 1 entity code + 1 check digit + 1 Z + 1 check digit)
        gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        return re.match(gst_pattern, gst) is not None
    
    def get_default_message(self):
        return "Please enter a valid GST number (e.g., 29ABCDE1234F1Z9)"

class PANNumberValidator(UserFriendlyValidator):
    """Validates Indian PAN numbers"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        pan = str(field.data).strip().upper()
        
        # PAN format: 10 characters (5 letters + 4 digits + 1 letter)
        pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        return re.match(pan_pattern, pan) is not None
    
    def get_default_message(self):
        return "Please enter a valid PAN number (e.g., ABCDE1234F)"

class IFSCCodeValidator(UserFriendlyValidator):
    """Validates Indian IFSC codes"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        ifsc = str(field.data).strip().upper()
        
        # IFSC format: 11 characters (4 bank letters + 1 zero + 6 branch code)
        ifsc_pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
        return re.match(ifsc_pattern, ifsc) is not None
    
    def get_default_message(self):
        return "Please enter a valid IFSC code (e.g., SBIN0001234)"

class ItemCodeValidator(UserFriendlyValidator):
    """Validates item codes (alphanumeric with hyphens and underscores only)"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        code = str(field.data).strip()
        
        # Allow letters, numbers, hyphens, and underscores only
        return re.match(r'^[A-Za-z0-9_-]+$', code) is not None
    
    def get_default_message(self):
        return "Item code can only contain letters, numbers, hyphens (-), and underscores (_)"

class PositiveNumberValidator(UserFriendlyValidator):
    """Validates positive numbers with user-friendly messages"""
    
    def __init__(self, min_value=0, max_value=None, message=None, allow_zero=True):
        self.min_value = min_value
        self.max_value = max_value
        self.allow_zero = allow_zero
        super().__init__(message)
    
    def validate_field(self, form, field):
        if not field.data and field.data != 0:
            return True
        
        try:
            value = float(field.data)
            
            if not self.allow_zero and value == 0:
                return False
            
            if value < self.min_value:
                return False
            
            if self.max_value is not None and value > self.max_value:
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    def get_default_message(self):
        if self.max_value is not None:
            if not self.allow_zero:
                return f"Please enter a positive number between {self.min_value} and {self.max_value} (zero not allowed)"
            return f"Please enter a number between {self.min_value} and {self.max_value}"
        else:
            if not self.allow_zero:
                return f"Please enter a positive number greater than {self.min_value}"
            return f"Please enter a number greater than or equal to {self.min_value}"

class PercentageValidator(PositiveNumberValidator):
    """Validates percentage values (0-100)"""
    
    def __init__(self, message=None):
        super().__init__(min_value=0, max_value=100, message=message)
    
    def get_default_message(self):
        return "Please enter a valid percentage between 0 and 100"

class RequiredFieldValidator(UserFriendlyValidator):
    """Enhanced required field validator with better messages"""
    
    def __init__(self, field_name=None, message=None):
        self.field_name = field_name
        super().__init__(message)
    
    def validate_field(self, form, field):
        if field.data is None:
            return False
        
        if isinstance(field.data, str):
            return bool(field.data.strip())
        
        return bool(field.data)
    
    def get_default_message(self):
        field_name = self.field_name or "This field"
        return f"{field_name} is required and cannot be empty"

class UniqueFieldValidator(UserFriendlyValidator):
    """Validates field uniqueness against database"""
    
    def __init__(self, model, field_name, current_id=None, message=None):
        self.model = model
        self.field_name = field_name
        self.current_id = current_id
        super().__init__(message)
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        query = self.model.query.filter(getattr(self.model, self.field_name) == field.data)
        
        # Exclude current record when editing
        if self.current_id:
            query = query.filter(self.model.id != self.current_id)
        
        return query.first() is None
    
    def get_default_message(self):
        return f"This {self.field_name.replace('_', ' ')} already exists. Please choose a different one."

class StockValidator(UserFriendlyValidator):
    """Validates stock quantities against available stock"""
    
    def __init__(self, item_id_field=None, available_stock=None, message=None):
        self.item_id_field = item_id_field
        self.available_stock = available_stock
        super().__init__(message)
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        try:
            requested_qty = float(field.data)
            
            # If available stock is provided directly
            if self.available_stock is not None:
                return requested_qty <= self.available_stock
            
            # If item_id_field is provided, get stock from database
            if self.item_id_field and hasattr(form, self.item_id_field):
                item_id = getattr(form, self.item_id_field).data
                if item_id:
                    from models import Item
                    item = Item.query.get(item_id)
                    if item:
                        return requested_qty <= (item.current_stock or 0)
            
            return True
        except (ValueError, TypeError):
            return False
    
    def get_default_message(self):
        return "Requested quantity exceeds available stock"

# Utility functions for common validation patterns

def validate_form_with_friendly_messages(form):
    """
    Validates a form and returns user-friendly error messages
    """
    errors = []
    
    if not form.validate():
        for field_name, field_errors in form.errors.items():
            field = getattr(form, field_name, None)
            field_label = getattr(field, 'label', {}).text if field else field_name.replace('_', ' ').title()
            
            for error in field_errors:
                errors.append(f"{field_label}: {error}")
    
    return errors

def add_validation_classes_to_field(field, additional_classes=None):
    """
    Adds CSS classes for validation styling to form fields
    """
    classes = ['form-control']
    
    if field.errors:
        classes.append('is-invalid')
    
    if hasattr(field, 'validators'):
        for validator in field.validators:
            if hasattr(validator, '__class__') and 'Required' in validator.__class__.__name__:
                classes.append('required')
    
    if additional_classes:
        if isinstance(additional_classes, str):
            classes.append(additional_classes)
        else:
            classes.extend(additional_classes)
    
    return ' '.join(classes)

# Custom validation decorators

def validate_business_rules(func):
    """
    Decorator for custom business rule validation
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError(f"Validation failed: {str(e)}")
    
    return wrapper

# Manufacturing-specific validators

class HSNCodeValidator(UserFriendlyValidator):
    """Validates HSN (Harmonized System of Nomenclature) codes"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        hsn = str(field.data).strip()
        
        # HSN codes can be 4, 6, or 8 digits
        return re.match(r'^\d{4,8}$', hsn) is not None
    
    def get_default_message(self):
        return "Please enter a valid HSN code (4 to 8 digits)"

class BatchCodeValidator(UserFriendlyValidator):
    """Validates batch codes for manufacturing"""
    
    def validate_field(self, form, field):
        if not field.data:
            return True
        
        batch_code = str(field.data).strip()
        
        # Batch codes: alphanumeric with hyphens, underscores, and slashes
        return re.match(r'^[A-Za-z0-9_/-]+$', batch_code) is not None
    
    def get_default_message(self):
        return "Batch code can only contain letters, numbers, hyphens (-), underscores (_), and slashes (/)"