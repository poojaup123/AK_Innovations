"""
Form Optimization Service

This service provides caching and optimization for form choices to reduce
database calls and improve form loading performance.
"""

from datetime import datetime
from functools import wraps
from models.uom import UnitOfMeasure
from models import ItemType

class FormChoiceCache:
    """Cache for form choices to avoid repeated database calls"""
    
    _cache = {}
    _cache_timestamps = {}
    _cache_duration = 300  # 5 minutes
    
    @classmethod
    def get_cached_choices(cls, key, fetch_function, fallback_choices=None):
        """Get cached choices or fetch from database"""
        now = datetime.now()
        
        # Check if cache is valid
        if (key in cls._cache and 
            key in cls._cache_timestamps and 
            (now - cls._cache_timestamps[key]).seconds < cls._cache_duration):
            return cls._cache[key]
        
        # Fetch fresh data
        try:
            choices = fetch_function()
            if not choices and fallback_choices:
                choices = fallback_choices
            
            cls._cache[key] = choices
            cls._cache_timestamps[key] = now
            return choices
            
        except Exception as e:
            print(f"Error fetching choices for {key}: {e}")
            if fallback_choices:
                cls._cache[key] = fallback_choices
                cls._cache_timestamps[key] = now
                return fallback_choices
            return []
    
    @classmethod
    def clear_cache(cls, key=None):
        """Clear cache for specific key or all keys"""
        if key:
            cls._cache.pop(key, None)
            cls._cache_timestamps.pop(key, None)
        else:
            cls._cache.clear()
            cls._cache_timestamps.clear()
    
    @classmethod
    def get_uom_choices(cls):
        """Get cached UOM choices"""
        def fetch_uom():
            UnitOfMeasure.ensure_default_units()
            return UnitOfMeasure.get_choices()
        
        fallback = [
            ('Pcs', 'Pieces (Pcs) - Count'), 
            ('Kg', 'Kilogram (Kg) - Weight'), 
            ('M', 'Meter (M) - Length'),
            ('L', 'Liter (L) - Volume')
        ]
        
        return cls.get_cached_choices('uom_choices', fetch_uom, fallback)
    
    @classmethod
    def get_item_type_choices(cls):
        """Get cached Item Type choices"""
        def fetch_item_types():
            ItemType.get_default_types()
            return ItemType.get_choices()
        
        fallback = [
            ('1', 'Material'), 
            ('2', 'Product'), 
            ('3', 'Consumable'),
            ('4', 'Tool'),
            ('5', 'Spare Part'),
            ('6', 'Packaging')
        ]
        
        return cls.get_cached_choices('item_type_choices', fetch_item_types, fallback)
    
    @classmethod
    def get_supplier_choices(cls):
        """Get cached Supplier choices"""
        def fetch_suppliers():
            from models import Supplier
            return [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()]
        
        return cls.get_cached_choices('supplier_choices', fetch_suppliers, [])
    
    @classmethod
    def get_employee_choices(cls):
        """Get cached Employee choices"""
        def fetch_employees():
            from models import Employee
            return [(e.id, f"{e.name} - {e.employee_code}") for e in Employee.query.filter_by(is_active=True).order_by(Employee.name).all()]
        
        return cls.get_cached_choices('employee_choices', fetch_employees, [])
    
    @classmethod
    def get_department_choices(cls):
        """Get cached Department choices"""
        def fetch_departments():
            from models.department import Department
            return [(d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name).all()]
        
        return cls.get_cached_choices('department_choices', fetch_departments, [])


def cached_form_choices(form_class):
    """Decorator to optimize form choice loading"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Pre-load common choices
            if hasattr(form_class, 'unit_of_measure'):
                form_class._cached_uom_choices = FormChoiceCache.get_uom_choices()
            if hasattr(form_class, 'item_type'):
                form_class._cached_item_type_choices = FormChoiceCache.get_item_type_choices()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def optimize_form_loading(form_instance):
    """Optimize form loading by setting cached choices"""
    # Set UOM choices if field exists
    if hasattr(form_instance, 'unit_of_measure'):
        form_instance.unit_of_measure.choices = FormChoiceCache.get_uom_choices()
    
    # Set Item Type choices if field exists
    if hasattr(form_instance, 'item_type'):
        form_instance.item_type.choices = FormChoiceCache.get_item_type_choices()
    
    # Set Supplier choices if field exists
    if hasattr(form_instance, 'supplier_id'):
        form_instance.supplier_id.choices = [(0, 'Select Supplier')] + FormChoiceCache.get_supplier_choices()
    
    # Set Employee choices if field exists
    if hasattr(form_instance, 'employee_id'):
        form_instance.employee_id.choices = [(0, 'Select Employee')] + FormChoiceCache.get_employee_choices()
    
    # Set Department choices if field exists
    if hasattr(form_instance, 'department_id'):
        form_instance.department_id.choices = [(0, 'Select Department')] + FormChoiceCache.get_department_choices()
    
    return form_instance


def clear_form_cache(cache_type=None):
    """Clear form cache - useful when master data is updated"""
    if cache_type:
        FormChoiceCache.clear_cache(cache_type)
    else:
        FormChoiceCache.clear_cache()