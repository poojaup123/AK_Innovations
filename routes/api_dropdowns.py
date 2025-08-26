"""
API endpoints for searchable dropdown data
Provides JSON data for various dropdown components across the factory management system
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from models import (Item, Supplier, Employee, Department, UnitOfMeasure, 
                   PurchaseOrder, SalesOrder, JobWork, Production, BOM)
from models.batch import InventoryBatch
from models.accounting import Account, AccountGroup, VoucherType
from models.settings import Company
from sqlalchemy import func, or_, distinct
import logging

api_dropdowns_bp = Blueprint('api_dropdowns', __name__, url_prefix='/api/dropdowns')

def format_dropdown_item(item, text_field='name', value_field='id', subtitle_field=None, extra_fields=None):
    """Helper function to format items for dropdown display"""
    result = {
        'id': getattr(item, value_field),
        'value': getattr(item, value_field),
        'text': getattr(item, text_field),
        'name': getattr(item, text_field)
    }
    
    if subtitle_field and hasattr(item, subtitle_field):
        subtitle = getattr(item, subtitle_field)
        if subtitle:
            result['subtitle'] = subtitle
    
    if extra_fields:
        for field in extra_fields:
            if hasattr(item, field):
                result[field] = getattr(item, field)
    
    return result

@api_dropdowns_bp.route('/items')
@login_required
def get_items():
    """Get items for dropdown selection"""
    search = request.args.get('search', '').strip()
    item_type = request.args.get('type', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = Item.query
        
        # Filter by item type if specified
        if item_type:
            query = query.filter(Item.item_type == item_type)
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                Item.name.ilike(f'%{search}%'),
                Item.code.ilike(f'%{search}%'),
                Item.description.ilike(f'%{search}%')
            ))
        
        # Order by name and limit
        items = query.order_by(Item.name).limit(limit).all()
        
        # Format for dropdown
        formatted_items = []
        for item in items:
            subtitle_parts = []
            if item.code:
                subtitle_parts.append(f"Code: {item.code}")
            if item.current_stock is not None:
                subtitle_parts.append(f"Stock: {item.current_stock} {item.unit_of_measure or ''}")
            
            formatted_items.append(format_dropdown_item(
                item,
                subtitle_field=None,
                extra_fields=['code', 'current_stock', 'unit_of_measure', 'unit_price', 'item_type']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_items[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_items)
        
    except Exception as e:
        logging.error(f"Error fetching items: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/suppliers')
@login_required
def get_suppliers():
    """Get suppliers for dropdown selection"""
    search = request.args.get('search', '').strip()
    partner_type = request.args.get('partner_type', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = Supplier.query
        
        # Filter by partner type if specified
        if partner_type:
            if partner_type == 'both':
                query = query.filter(Supplier.partner_type.in_(['supplier', 'customer', 'both']))
            else:
                query = query.filter(or_(
                    Supplier.partner_type == partner_type,
                    Supplier.partner_type == 'both'
                ))
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                Supplier.name.ilike(f'%{search}%'),
                Supplier.contact_person.ilike(f'%{search}%'),
                Supplier.email.ilike(f'%{search}%'),
                Supplier.phone.ilike(f'%{search}%')
            ))
        
        # Order by name and limit
        suppliers = query.order_by(Supplier.name).limit(limit).all()
        
        # Format for dropdown
        formatted_suppliers = []
        for supplier in suppliers:
            subtitle_parts = []
            if supplier.contact_person:
                subtitle_parts.append(supplier.contact_person)
            if supplier.phone:
                subtitle_parts.append(supplier.phone)
            
            formatted_suppliers.append(format_dropdown_item(
                supplier,
                extra_fields=['contact_person', 'email', 'phone', 'partner_type']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_suppliers[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_suppliers)
        
    except Exception as e:
        logging.error(f"Error fetching suppliers: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/employees')
@login_required
def get_employees():
    """Get employees for dropdown selection"""
    search = request.args.get('search', '').strip()
    department = request.args.get('department', '').strip()
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = Employee.query
        
        # Apply search filter
        if search:
            query = query.filter(Employee.name.ilike(f'%{search}%'))
        
        # Order by name and limit
        employees = query.order_by(Employee.name).limit(limit).all()
        
        # Format for dropdown
        formatted_employees = []
        for employee in employees:
            formatted_employees.append(format_dropdown_item(
                employee,
                extra_fields=['name']
            ))
        
        return jsonify(formatted_employees)
        
    except Exception as e:
        logging.error(f"Error fetching employees: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/departments')
@login_required
def get_departments():
    """Get departments for dropdown selection"""
    search = request.args.get('search', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = Department.query
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                Department.name.ilike(f'%{search}%'),
                Department.code.ilike(f'%{search}%'),
                Department.description.ilike(f'%{search}%')
            ))
        
        # Order by name and limit
        departments = query.order_by(Department.name).limit(limit).all()
        
        # Format for dropdown
        formatted_departments = []
        for dept in departments:
            formatted_departments.append(format_dropdown_item(
                dept,
                subtitle_field='description',
                extra_fields=['code', 'description']
            ))
        
        return jsonify(formatted_departments)
        
    except Exception as e:
        logging.error(f"Error fetching departments: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/uom')
@login_required
def get_units_of_measure():
    """Get units of measure for dropdown selection"""
    search = request.args.get('search', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = UnitOfMeasure.query
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                UnitOfMeasure.name.ilike(f'%{search}%'),
                UnitOfMeasure.symbol.ilike(f'%{search}%'),
                UnitOfMeasure.category.ilike(f'%{search}%')
            ))
        
        # Order by name and limit
        uoms = query.order_by(UnitOfMeasure.name).limit(limit).all()
        
        # Format for dropdown
        formatted_uoms = []
        for uom in uoms:
            subtitle_parts = []
            if uom.symbol:
                subtitle_parts.append(f"Symbol: {uom.symbol}")
            if uom.category:
                subtitle_parts.append(f"Category: {uom.category}")
            
            formatted_uoms.append(format_dropdown_item(
                uom,
                extra_fields=['symbol', 'category']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_uoms[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_uoms)
        
    except Exception as e:
        logging.error(f"Error fetching UOMs: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/purchase-orders')
@login_required
def get_purchase_orders():
    """Get purchase orders for dropdown selection"""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    supplier_id = request.args.get('supplier_id', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = PurchaseOrder.query
        
        # Filter by status if specified
        if status:
            query = query.filter(PurchaseOrder.status == status)
        
        # Filter by supplier if specified
        if supplier_id:
            query = query.filter(PurchaseOrder.supplier_id == supplier_id)
        
        # Apply search filter
        if search:
            query = query.filter(PurchaseOrder.po_number.ilike(f'%{search}%'))
        
        # Order by date and limit
        pos = query.order_by(PurchaseOrder.created_at.desc()).limit(limit).all()
        
        # Format for dropdown
        formatted_pos = []
        for po in pos:
            formatted_pos.append(format_dropdown_item(
                po,
                text_field='po_number',
                extra_fields=['status', 'supplier_id']
            ))
        
        return jsonify(formatted_pos)
        
    except Exception as e:
        logging.error(f"Error fetching purchase orders: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/job-works')
@login_required
def get_job_works():
    """Get job works for dropdown selection"""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    work_type = request.args.get('work_type', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = JobWork.query
        
        # Filter by status if specified
        if status:
            query = query.filter(JobWork.status == status)
        
        # Filter by work type if specified
        if work_type:
            query = query.filter(JobWork.work_type == work_type)
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                JobWork.job_number.ilike(f'%{search}%'),
                JobWork.customer_name.ilike(f'%{search}%'),
                JobWork.item.has(Item.name.ilike(f'%{search}%'))
            ))
        
        # Order by date and limit
        job_works = query.order_by(JobWork.created_at.desc()).limit(limit).all()
        
        # Format for dropdown
        formatted_jobs = []
        for job in job_works:
            subtitle_parts = []
            if job.customer_name:
                subtitle_parts.append(f"Customer: {job.customer_name}")
            if job.item:
                subtitle_parts.append(f"Item: {job.item.name}")
            if job.quantity:
                subtitle_parts.append(f"Qty: {job.quantity}")
            
            formatted_jobs.append(format_dropdown_item(
                job,
                text_field='job_number',
                extra_fields=['status', 'work_type', 'customer_name', 'quantity', 'item_id']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_jobs[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_jobs)
        
    except Exception as e:
        logging.error(f"Error fetching job works: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/batches')
@login_required
def get_batches():
    """Get inventory batches for dropdown selection"""
    search = request.args.get('search', '').strip()
    item_id = request.args.get('item_id', '').strip()
    status = request.args.get('status', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = InventoryBatch.query
        
        # Filter by item if specified
        if item_id:
            query = query.filter(InventoryBatch.item_id == item_id)
        
        # Filter by status if specified
        if status:
            query = query.filter(InventoryBatch.status == status)
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                InventoryBatch.batch_number.ilike(f'%{search}%'),
                InventoryBatch.item.has(Item.name.ilike(f'%{search}%'))
            ))
        
        # Order by date and limit
        batches = query.order_by(InventoryBatch.created_date.desc()).limit(limit).all()
        
        # Format for dropdown
        formatted_batches = []
        for batch in batches:
            subtitle_parts = []
            if batch.item:
                subtitle_parts.append(f"Item: {batch.item.name}")
            if batch.quantity_available:
                subtitle_parts.append(f"Available: {batch.quantity_available}")
            if batch.expiry_date:
                subtitle_parts.append(f"Expiry: {batch.expiry_date.strftime('%Y-%m-%d')}")
            
            formatted_batches.append(format_dropdown_item(
                batch,
                text_field='batch_number',
                extra_fields=['item_id', 'status', 'quantity_available', 'expiry_date']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_batches[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_batches)
        
    except Exception as e:
        logging.error(f"Error fetching batches: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/accounts')
@login_required
def get_accounts():
    """Get accounts for dropdown selection"""
    search = request.args.get('search', '').strip()
    account_type = request.args.get('account_type', '').strip()
    group_id = request.args.get('group_id', '').strip()
    limit = min(int(request.args.get('limit', 100)), 1000)
    
    try:
        query = Account.query
        
        # Filter by account type if specified
        if account_type:
            query = query.filter(Account.account_type == account_type)
        
        # Filter by group if specified
        if group_id:
            query = query.filter(Account.account_group_id == group_id)
        
        # Apply search filter
        if search:
            query = query.filter(or_(
                Account.name.ilike(f'%{search}%'),
                Account.code.ilike(f'%{search}%'),
                Account.account_group.has(AccountGroup.name.ilike(f'%{search}%'))
            ))
        
        # Order by name and limit
        accounts = query.order_by(Account.name).limit(limit).all()
        
        # Format for dropdown
        formatted_accounts = []
        for account in accounts:
            subtitle_parts = []
            if account.code:
                subtitle_parts.append(f"Code: {account.code}")
            if account.account_group:
                subtitle_parts.append(f"Group: {account.account_group.name}")
            
            formatted_accounts.append(format_dropdown_item(
                account,
                extra_fields=['code', 'account_type', 'account_group_id']
            ))
            
            # Add custom subtitle
            if subtitle_parts:
                formatted_accounts[-1]['subtitle'] = " | ".join(subtitle_parts)
        
        return jsonify(formatted_accounts)
        
    except Exception as e:
        logging.error(f"Error fetching accounts: {e}")
        return jsonify([]), 500

@api_dropdowns_bp.route('/table-filter-data/<table_name>/<column_name>')
@login_required
def get_table_filter_data(table_name, column_name):
    """Get unique values for table column filtering"""
    limit = min(int(request.args.get('limit', 500)), 1000)
    
    try:
        # Map table names to models and columns
        table_map = {
            'items': {'model': Item, 'columns': {
                'name': Item.name,
                'code': Item.code,
                'item_type': Item.item_type,
                'unit_of_measure': Item.unit_of_measure,
                'current_stock': Item.current_stock
            }},
            'suppliers': {'model': Supplier, 'columns': {
                'name': Supplier.name,
                'partner_type': Supplier.partner_type,
                'contact_person': Supplier.contact_person
            }},
            'purchase_orders': {'model': PurchaseOrder, 'columns': {
                'po_number': PurchaseOrder.po_number,
                'status': PurchaseOrder.status,
                'supplier_name': Supplier.name
            }},
            'job_works': {'model': JobWork, 'columns': {
                'job_number': JobWork.job_number,
                'status': JobWork.status,
                'work_type': JobWork.work_type,
                'customer_name': JobWork.customer_name
            }}
        }
        
        if table_name not in table_map:
            return jsonify([]), 404
        
        config = table_map[table_name]
        if column_name not in config['columns']:
            return jsonify([]), 404
        
        column = config['columns'][column_name]
        if column is None:
            return jsonify([]), 404
        
        # Get distinct values
        query = config['model'].query.with_entities(column).distinct()
        
        # Handle joined tables
        if table_name == 'purchase_orders' and column_name == 'supplier_name':
            query = query.join(Supplier)
        
        values = query.filter(column.isnot(None)).order_by(column).limit(limit).all()
        
        # Format as simple list of strings
        result = [str(value[0]) for value in values if value[0]]
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching table filter data: {e}")
        return jsonify([]), 500

# Add utility endpoints for common dropdown combinations
@api_dropdowns_bp.route('/recent-items')
@login_required
def get_recent_items():
    """Get recently used items"""
    limit = min(int(request.args.get('limit', 20)), 50)
    
    try:
        # Get items that have been recently used in POs, Job Works, etc.
        recent_items = Item.query.order_by(Item.id.desc()).limit(limit).all()
        
        formatted_items = []
        for item in recent_items:
            formatted_items.append(format_dropdown_item(
                item,
                extra_fields=['code', 'current_stock', 'unit_of_measure']
            ))
        
        return jsonify(formatted_items)
        
    except Exception as e:
        logging.error(f"Error fetching recent items: {e}")
        return jsonify([]), 500