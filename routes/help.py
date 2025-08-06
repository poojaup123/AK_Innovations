from flask import Blueprint, render_template

help_bp = Blueprint('help', __name__)

@help_bp.route('/item-types')
def item_types_help():
    """Help page for Item Types"""
    return render_template('help/item_types.html')

@help_bp.route('/inventory')
def inventory_help():
    """Help page for Inventory Management"""
    return render_template('help/inventory.html')

@help_bp.route('/purchase-orders')
def purchase_orders_help():
    """Help page for Purchase Orders"""
    return render_template('help/purchase_orders.html')

@help_bp.route('/sales-orders')
def sales_orders_help():
    """Help page for Sales Orders"""
    return render_template('help/sales_orders.html')

@help_bp.route('/job-work')
def job_work_help():
    """Help page for Job Work Management"""
    return render_template('help/job_work.html')

@help_bp.route('/production')
def production_help():
    """Help page for Production Management"""
    return render_template('help/production.html')

@help_bp.route('/accounting')
def accounting_help():
    """Help page for Accounting System"""
    return render_template('help/accounting.html')

@help_bp.route('/bom')
def bom_help():
    """Help page for Bill of Materials"""
    return render_template('help/bom.html')

@help_bp.route('/batch-tracking')
def batch_tracking_help():
    """Help page for Batch Tracking"""
    return render_template('help/batch_tracking.html')

@help_bp.route('/grn')
def grn_help():
    """Help page for Goods Receipt Note"""
    return render_template('help/grn.html')