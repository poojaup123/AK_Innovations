"""
Demo routes to showcase the enhanced searchable dropdown system
"""

from flask import Blueprint, render_template
from flask_login import login_required
from forms import PurchaseOrderForm

demo_searchable_bp = Blueprint('demo_searchable', __name__, url_prefix='/demo/searchable')

@demo_searchable_bp.route('/purchase-form')
@login_required
def enhanced_purchase_form():
    """Demo the enhanced purchase form with searchable dropdowns"""
    form = PurchaseOrderForm()
    return render_template('purchase/form_enhanced_searchable.html', 
                         form=form, 
                         title='Enhanced Purchase Order (Demo)')

@demo_searchable_bp.route('/inventory-list')
@login_required
def enhanced_inventory_list():
    """Demo the enhanced inventory list with filterable columns"""
    return render_template('inventory/list_enhanced_searchable.html')

@demo_searchable_bp.route('/mobile-dashboard')
@login_required
def mobile_optimized_dashboard():
    """Demo the mobile-optimized dashboard"""
    # Sample data for demonstration
    dashboard_data = {
        'total_items': 127,
        'low_stock_count': 8,
        'stock_value': 452300,
        'out_of_stock_count': 3,
        'raw_materials_count': 45,
        'finished_goods_count': 32,
        'wip_count': 28,
        'scrap_count': 22
    }
    return render_template('inventory/dashboard_mobile_optimized.html', **dashboard_data)