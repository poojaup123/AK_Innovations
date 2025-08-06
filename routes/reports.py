from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, jsonify
from flask_login import login_required, current_user
from models import Item, PurchaseOrder, SalesOrder, Employee, JobWork, Production
from models.uom import ItemUOMConversion
from models.custom_reports import CustomReport, CustomReportExecution
from forms_custom_reports import CustomReportForm
from app import db
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta
import csv
import io
import json

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/dashboard')
@login_required
def dashboard():
    # Report generation options and recent exports
    report_types = [
        {'name': 'Inventory Report', 'url': 'reports.inventory_report'},
        {'name': 'Purchase Orders Report', 'url': 'reports.purchase_report'},
        {'name': 'Sales Orders Report', 'url': 'reports.sales_report'},
        {'name': 'Employee Report', 'url': 'reports.employee_report'},
        {'name': 'Job Work Report', 'url': 'reports.jobwork_report'},
        {'name': 'Production Report', 'url': 'reports.production_report'}
    ]
    
    return render_template('reports/dashboard.html', report_types=report_types)

@reports_bp.route('/inventory')
@login_required
def inventory_report():
    # Get inventory data with filters
    item_type_filter = request.args.get('item_type', '', type=str)
    low_stock_only = request.args.get('low_stock', False, type=bool)
    
    query = Item.query.options(joinedload(Item.uom_conversion))
    
    if item_type_filter:
        query = query.filter_by(item_type=item_type_filter)
    
    if low_stock_only:
        query = query.filter(db.func.coalesce(Item.current_stock, 0) <= db.func.coalesce(Item.minimum_stock, 0))
    
    items = query.order_by(Item.name).all()
    
    # Calculate totals
    total_items = len(items)
    total_stock_value = sum((item.current_stock or 0) * (item.unit_price or 0) for item in items)
    low_stock_count = len([item for item in items if (item.current_stock or 0) <= (item.minimum_stock or 0)])
    
    # Add pagination support
    page = request.args.get('page', 1, type=int)
    items_paginated = query.paginate(page=page, per_page=50, error_out=False)
    
    # Calculate additional stats
    all_items = Item.query.all()
    total_value = sum((item.current_stock or 0) * (item.unit_price or 0) for item in all_items)
    out_of_stock_count = len([item for item in all_items if (item.current_stock or 0) == 0])
    
    return render_template('reports/inventory_report.html', 
                         items=items_paginated,
                         total_items=total_items,
                         total_value=total_value,
                         low_stock_count=low_stock_count,
                         out_of_stock_count=out_of_stock_count,
                         item_type_filter=item_type_filter,
                         low_stock_only=low_stock_only)

@reports_bp.route('/inventory/export')
@login_required
def export_inventory():
    # Get same data as inventory report
    item_type_filter = request.args.get('item_type', '', type=str)
    low_stock_only = request.args.get('low_stock', False, type=bool)
    
    query = Item.query
    
    if item_type_filter:
        query = query.filter_by(item_type=item_type_filter)
    
    if low_stock_only:
        query = query.filter(db.func.coalesce(Item.current_stock, 0) <= db.func.coalesce(Item.minimum_stock, 0))
    
    items = query.order_by(Item.name).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Item Code', 'Item Name', 'Description', 'UOM', 'Current Stock', 
                    'Minimum Stock', 'Unit Price', 'Stock Value', 'Item Type'])
    
    # Write data
    for item in items:
        stock_value = (item.current_stock or 0) * (item.unit_price or 0)
        writer.writerow([item.code, item.name, item.description or '', item.unit_of_measure,
                        item.current_stock, item.minimum_stock, item.unit_price, 
                        stock_value, item.item_type])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=inventory_report_{date.today()}.csv'
    
    return response

@reports_bp.route('/purchase')
@login_required
def purchase_report():
    # Date filters
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = PurchaseOrder.query
    
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(PurchaseOrder.order_date >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(PurchaseOrder.order_date <= end_date_obj)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    purchase_orders = query.order_by(PurchaseOrder.order_date.desc()).all()
    
    # Calculate totals
    total_orders = len(purchase_orders)
    total_amount = sum(po.total_amount for po in purchase_orders)
    
    return render_template('reports/purchase_report.html',
                         purchase_orders=purchase_orders,
                         total_orders=total_orders,
                         total_amount=total_amount,
                         start_date=start_date,
                         end_date=end_date,
                         status_filter=status_filter)

@reports_bp.route('/sales')
@login_required
def sales_report():
    # Date filters
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = SalesOrder.query
    
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(SalesOrder.order_date >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(SalesOrder.order_date <= end_date_obj)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    sales_orders = query.order_by(SalesOrder.order_date.desc()).all()
    
    # Calculate totals
    total_orders = len(sales_orders)
    total_amount = sum(so.total_amount for so in sales_orders)
    
    return render_template('reports/sales_report.html',
                         sales_orders=sales_orders,
                         total_orders=total_orders,
                         total_amount=total_amount,
                         start_date=start_date,
                         end_date=end_date,
                         status_filter=status_filter)

@reports_bp.route('/employee')
@login_required
def employee_report():
    # Employee filters
    department_filter = request.args.get('department', '', type=str)
    salary_type_filter = request.args.get('salary_type', '', type=str)
    status_filter = request.args.get('status', 'active', type=str)
    
    query = Employee.query
    
    if department_filter:
        query = query.filter_by(department=department_filter)
    
    if salary_type_filter:
        query = query.filter_by(salary_type=salary_type_filter)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    employees = query.order_by(Employee.name).all()
    
    # Get departments and salary types for filters
    departments = db.session.query(Employee.department).distinct().filter(Employee.department.isnot(None)).all()
    departments = [dept[0] for dept in departments if dept[0]]
    
    salary_types = ['daily', 'monthly', 'piece_rate']
    
    return render_template('reports/employee_report.html',
                         employees=employees,
                         departments=departments,
                         salary_types=salary_types,
                         department_filter=department_filter,
                         salary_type_filter=salary_type_filter,
                         status_filter=status_filter)

@reports_bp.route('/jobwork')
@login_required
def jobwork_report():
    # Date and status filters
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = JobWork.query
    
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(JobWork.sent_date >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(JobWork.sent_date <= end_date_obj)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    job_works = query.order_by(JobWork.sent_date.desc()).all()
    
    return render_template('reports/jobwork_report.html',
                         job_works=job_works,
                         start_date=start_date,
                         end_date=end_date,
                         status_filter=status_filter)

@reports_bp.route('/production')
@login_required
def production_report():
    # Date and status filters
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = Production.query
    
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Production.production_date >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Production.production_date <= end_date_obj)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    productions = query.order_by(Production.production_date.desc()).all()
    
    return render_template('reports/production_report.html',
                         productions=productions,
                         start_date=start_date,
                         end_date=end_date,
                         status_filter=status_filter)

# Custom Report Builder Routes

@reports_bp.route('/custom')
@login_required 
def custom_reports_list():
    """List all custom reports for the current user"""
    # Get user's own reports
    my_reports = CustomReport.query.filter_by(created_by=current_user.id).order_by(CustomReport.created_at.desc()).all()
    
    # Get shared reports from other users
    shared_reports = CustomReport.query.filter(
        and_(CustomReport.is_shared == True, CustomReport.created_by != current_user.id)
    ).order_by(CustomReport.created_at.desc()).all()
    
    return render_template('reports/custom_reports_list.html', 
                         my_reports=my_reports, 
                         shared_reports=shared_reports)

@reports_bp.route('/custom/new', methods=['GET', 'POST'])
@login_required
def create_custom_report():
    """Create a new custom report"""
    form = CustomReportForm()
    
    if form.validate_on_submit():
        # Parse configuration from hidden field
        config_json = request.form.get('config', '{}')
        
        try:
            config = json.loads(config_json)
        except:
            config = {}
        
        # Create new custom report
        custom_report = CustomReport(
            name=form.name.data,
            description=form.description.data,
            report_type=form.report_type.data,
            config=config_json,
            created_by=current_user.id,
            is_shared=form.is_shared.data
        )
        
        db.session.add(custom_report)
        db.session.commit()
        
        flash(f'Custom report "{form.name.data}" created successfully!', 'success')
        return redirect(url_for('reports.custom_reports_list'))
    
    return render_template('reports/custom_report_builder.html', form=form)

@reports_bp.route('/custom/<int:report_id>')
@login_required
def view_custom_report(report_id):
    """View/run a custom report"""
    custom_report = CustomReport.query.get_or_404(report_id)
    
    # Check access permissions
    if custom_report.created_by != current_user.id and not custom_report.is_shared:
        flash('You do not have permission to view this report.', 'error')
        return redirect(url_for('reports.custom_reports_list'))
    
    # Get report configuration
    config = custom_report.get_config()
    
    # Execute the report
    try:
        data, headers = execute_custom_report(custom_report)
        
        # Log execution
        execution = CustomReportExecution(
            custom_report_id=custom_report.id,
            executed_by=current_user.id,
            row_count=len(data)
        )
        db.session.add(execution)
        db.session.commit()
        
    except Exception as e:
        flash(f'Error executing report: {str(e)}', 'error')
        data, headers = [], []
    
    return render_template('reports/custom_report_view.html', 
                         custom_report=custom_report,
                         data=data,
                         headers=headers,
                         config=config)

@reports_bp.route('/custom/<int:report_id>/export')
@login_required
def export_custom_report(report_id):
    """Export custom report to CSV"""
    custom_report = CustomReport.query.get_or_404(report_id)
    
    # Check access permissions
    if custom_report.created_by != current_user.id and not custom_report.is_shared:
        flash('You do not have permission to export this report.', 'error')
        return redirect(url_for('reports.custom_reports_list'))
    
    try:
        # Execute the report
        data, headers = execute_custom_report(custom_report)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(headers)
        
        # Write data
        for row in data:
            writer.writerow(row)
        
        # Log export
        execution = CustomReportExecution(
            custom_report_id=custom_report.id,
            executed_by=current_user.id,
            row_count=len(data),
            export_format='csv'
        )
        db.session.add(execution)
        db.session.commit()
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={custom_report.name}_{date.today()}.csv'
        
        return response
        
    except Exception as e:
        flash(f'Error exporting report: {str(e)}', 'error')
        return redirect(url_for('reports.view_custom_report', report_id=report_id))

@reports_bp.route('/custom/<int:report_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_custom_report(report_id):
    """Edit an existing custom report"""
    custom_report = CustomReport.query.get_or_404(report_id)
    
    # Check ownership
    if custom_report.created_by != current_user.id:
        flash('You can only edit your own reports.', 'error')
        return redirect(url_for('reports.custom_reports_list'))
    
    form = CustomReportForm(obj=custom_report)
    
    if form.validate_on_submit():
        # Update report
        custom_report.name = form.name.data
        custom_report.description = form.description.data
        custom_report.report_type = form.report_type.data
        custom_report.is_shared = form.is_shared.data
        
        # Update configuration
        config_json = request.form.get('config', '{}')
        custom_report.config = config_json
        
        db.session.commit()
        
        flash(f'Custom report "{form.name.data}" updated successfully!', 'success')
        return redirect(url_for('reports.view_custom_report', report_id=report_id))
    
    return render_template('reports/custom_report_builder.html', form=form, report=custom_report)

@reports_bp.route('/custom/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_custom_report(report_id):
    """Delete a custom report"""
    custom_report = CustomReport.query.get_or_404(report_id)
    
    # Check ownership
    if custom_report.created_by != current_user.id:
        flash('You can only delete your own reports.', 'error')
        return redirect(url_for('reports.custom_reports_list'))
    
    # Delete related executions first
    CustomReportExecution.query.filter_by(custom_report_id=report_id).delete()
    
    # Delete the report
    db.session.delete(custom_report)
    db.session.commit()
    
    flash(f'Custom report "{custom_report.name}" deleted successfully!', 'success')
    return redirect(url_for('reports.custom_reports_list'))

@reports_bp.route('/custom/preview', methods=['POST'])
@login_required
def preview_custom_report():
    """AJAX endpoint to preview custom report"""
    try:
        data = request.get_json()
        
        # Create temporary custom report object
        temp_report = CustomReport(
            report_type=data.get('report_type'),
            config=json.dumps(data)
        )
        
        # Execute and get first 10 rows for preview
        preview_data, headers = execute_custom_report(temp_report, limit=10)
        
        # Generate HTML table
        html = '<div class="table-responsive">'
        html += '<table class="table table-sm table-striped">'
        html += '<thead class="table-dark"><tr>'
        
        for header in headers:
            html += f'<th>{header}</th>'
        html += '</tr></thead><tbody>'
        
        for row in preview_data:
            html += '<tr>'
            for cell in row:
                html += f'<td>{cell or ""}</td>'
            html += '</tr>'
        
        html += '</tbody></table></div>'
        
        if len(preview_data) == 10:
            html += '<p class="text-muted small mt-2"><i class="fas fa-info-circle"></i> Showing first 10 rows. Full report may contain more data.</p>'
        
        return jsonify({
            'success': True,
            'preview_html': html,
            'row_count': len(preview_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def execute_custom_report(custom_report, limit=None):
    """Execute a custom report and return data"""
    config = custom_report.get_config()
    report_type = custom_report.report_type
    fields = config.get('fields', [])
    filters = config.get('filters', [])
    sort_field = config.get('sort_field')
    sort_order = config.get('sort_order', 'asc')
    
    # Map report types to models and field mappings
    model_mapping = {
        'inventory': {
            'model': Item,
            'field_mapping': {
                'name': 'name',
                'code': 'code', 
                'description': 'description',
                'current_stock': 'current_stock',
                'minimum_stock': 'minimum_stock',
                'unit_price': 'unit_price',
                'unit_of_measure': 'unit_of_measure',
                'item_type': 'item_type',
                'gst_rate': 'gst_rate',
                'hsn_code': 'hsn_code'
            }
        },
        'purchase': {
            'model': PurchaseOrder,
            'field_mapping': {
                'po_number': 'po_number',
                'supplier_name': 'supplier_name',
                'order_date': 'order_date',
                'expected_delivery_date': 'expected_delivery_date',
                'status': 'status',
                'total_amount': 'total_amount',
                'payment_terms': 'payment_terms'
            }
        },
        'sales': {
            'model': SalesOrder,
            'field_mapping': {
                'so_number': 'so_number',
                'customer_name': 'customer_name',
                'order_date': 'order_date',
                'delivery_date': 'delivery_date',
                'status': 'status',
                'total_amount': 'total_amount'
            }
        },
        'jobwork': {
            'model': JobWork,
            'field_mapping': {
                'job_number': 'job_number',
                'customer_name': 'customer_name',
                'item_name': 'item.name',
                'quantity_sent': 'quantity_sent',
                'quantity_received': 'quantity_received',
                'rate_per_unit': 'rate_per_unit',
                'work_type': 'work_type',
                'status': 'status'
            }
        },
        'production': {
            'model': Production,
            'field_mapping': {
                'production_number': 'production_number',
                'item_name': 'item.name',
                'planned_quantity': 'planned_quantity',
                'produced_quantity': 'produced_quantity',
                'production_date': 'production_date',
                'status': 'status'
            }
        },
        'employee': {
            'model': Employee,
            'field_mapping': {
                'employee_code': 'employee_code',
                'name': 'name',
                'department': 'department',
                'designation': 'designation',
                'hire_date': 'hire_date',
                'status': 'status',
                'contact_number': 'contact_number'
            }
        }
    }
    
    if report_type not in model_mapping:
        raise ValueError(f'Unsupported report type: {report_type}')
    
    model_info = model_mapping[report_type]
    model = model_info['model']
    field_mapping = model_info['field_mapping']
    
    # Build query
    query = model.query
    
    # Apply filters
    for filter_config in filters:
        field_name = filter_config.get('field')
        operator = filter_config.get('operator')
        value = filter_config.get('value')
        
        if not field_name or not operator or not value:
            continue
            
        if field_name not in field_mapping:
            continue
            
        model_field = getattr(model, field_mapping[field_name].split('.')[0])
        
        # Apply different operators
        if operator == 'equals':
            query = query.filter(model_field == value)
        elif operator == 'contains':
            query = query.filter(model_field.ilike(f'%{value}%'))
        elif operator == 'greater_than':
            query = query.filter(model_field > value)
        elif operator == 'less_than':
            query = query.filter(model_field < value)
    
    # Apply sorting
    if sort_field and sort_field in field_mapping:
        sort_column = getattr(model, field_mapping[sort_field].split('.')[0])
        if sort_order == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
    
    # Apply limit for preview
    if limit:
        query = query.limit(limit)
    
    # Execute query
    results = query.all()
    
    # Extract data based on selected fields
    headers = []
    data = []
    
    # Build headers
    for field in fields:
        if field in field_mapping:
            headers.append(field.replace('_', ' ').title())
    
    # Extract data
    for result in results:
        row = []
        for field in fields:
            if field in field_mapping:
                field_path = field_mapping[field]
                
                # Handle nested fields (e.g., item.name)
                if '.' in field_path:
                    parts = field_path.split('.')
                    value = result
                    for part in parts:
                        value = getattr(value, part, None) if value else None
                else:
                    value = getattr(result, field_path, None)
                
                row.append(value)
        data.append(row)
    
    return data, headers
