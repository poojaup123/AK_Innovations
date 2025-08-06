"""
Utility functions for auto-generation of codes and numbers
"""
from datetime import datetime
from models import PurchaseOrder, Item, SalesOrder
from sqlalchemy import func

def generate_po_number():
    """Generate unique PO number in format: PO-YYYY-0001"""
    current_year = datetime.now().year
    
    # Get the latest PO number for current year
    latest_po = PurchaseOrder.query.filter(
        PurchaseOrder.po_number.like(f'PO-{current_year}-%')
    ).order_by(PurchaseOrder.po_number.desc()).first()
    
    if latest_po:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_po.po_number.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"PO-{current_year}-{next_sequence:04d}"

def generate_item_code(item_type='ITEM'):
    """Generate unique item code in format: ITEM-0001"""
    # Get the latest item code with same prefix
    latest_item = Item.query.filter(
        Item.code.like(f'{item_type}-%')
    ).order_by(Item.code.desc()).first()
    
    if latest_item:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_item.code.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"{item_type}-{next_sequence:04d}"

def generate_so_number():
    """Generate unique SO number in format: SO-YYYY-0001"""
    current_year = datetime.now().year
    
    # Get the latest SO number for current year
    latest_so = SalesOrder.query.filter(
        SalesOrder.so_number.like(f'SO-{current_year}-%')
    ).order_by(SalesOrder.so_number.desc()).first()
    
    if latest_so:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_so.so_number.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"SO-{current_year}-{next_sequence:04d}"

def generate_employee_code():
    """Generate unique employee code in format: EMP-0001"""
    from models import Employee
    
    # Get the latest employee code
    latest_emp = Employee.query.filter(
        Employee.employee_code.like('EMP-%')
    ).order_by(Employee.employee_code.desc()).first()
    
    if latest_emp:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_emp.employee_code.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"EMP-{next_sequence:04d}"

def generate_job_number():
    """Generate unique job work number in format: JOB-YYYY-0001"""
    current_year = datetime.now().year
    from models import JobWork
    
    # Get the latest job number for current year
    latest_job = JobWork.query.filter(
        JobWork.job_number.like(f'JOB-{current_year}-%')
    ).order_by(JobWork.job_number.desc()).first()
    
    if latest_job:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_job.job_number.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"JOB-{current_year}-{next_sequence:04d}"

def generate_production_number():
    """Generate unique production number in format: PROD-YYYY-0001"""
    current_year = datetime.now().year
    from models import Production
    
    # Get the latest production number for current year
    latest_prod = Production.query.filter(
        Production.production_number.like(f'PROD-{current_year}-%')
    ).order_by(Production.production_number.desc()).first()
    
    if latest_prod:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_prod.production_number.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"PROD-{current_year}-{next_sequence:04d}"

def generate_quality_issue_number():
    """Generate unique quality issue number in format: QI-YYYY-0001"""
    current_year = datetime.now().year
    from models import QualityIssue
    
    # Get the latest quality issue number for current year
    latest_issue = QualityIssue.query.filter(
        QualityIssue.issue_number.like(f'QI-{current_year}-%')
    ).order_by(QualityIssue.issue_number.desc()).first()
    
    if latest_issue:
        # Extract sequence number and increment
        try:
            last_sequence = int(latest_issue.issue_number.split('-')[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    return f"QI-{current_year}-{next_sequence:04d}"

def generate_next_number(prefix, table_name, column_name, year_based=True):
    """
    Generate the next sequential number with given prefix
    
    Args:
        prefix: Prefix for the number (e.g., 'INSPECT', 'QI', 'SO')
        table_name: Name of the database table
        column_name: Name of the column containing the numbers
        year_based: Whether to include year in format (default: True)
    
    Returns:
        Next sequential number in format PREFIX-YYYY-0001 or PREFIX-0001
    """
    from app import db
    from sqlalchemy import text
    
    current_year = datetime.now().year
    
    if year_based:
        pattern = f'{prefix}-{current_year}-%'
        format_template = f'{prefix}-{current_year}-{{:04d}}'
    else:
        pattern = f'{prefix}-%'
        format_template = f'{prefix}-{{:04d}}'
    
    # Dynamic query using table name
    query = text(f"SELECT {column_name} FROM {table_name} WHERE {column_name} LIKE :pattern ORDER BY {column_name} DESC LIMIT 1")
    result = db.session.execute(query, {'pattern': pattern}).fetchone()
    
    if result:
        # Extract the sequence number and increment
        sequence = int(result[0].split('-')[-1]) + 1
    else:
        sequence = 1
    
    return format_template.format(sequence)

def admin_required(f):
    """Decorator to require admin role for certain views"""
    from functools import wraps
    from flask_login import current_user
    from flask import abort
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        # For now, allow all authenticated users - you can modify this to check role
        return f(*args, **kwargs)
    return decorated_function