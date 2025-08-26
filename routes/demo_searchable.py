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