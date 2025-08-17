"""
Demo route to test price visibility system
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User, Item, db
from services.price_visibility import PriceVisibilityService

demo_price_bp = Blueprint('demo_price', __name__, url_prefix='/demo')

@demo_price_bp.route('/price-demo')
@login_required
def price_demo():
    """Demo page showing price visibility features"""
    
    # Get sample items for demonstration
    sample_items = Item.query.limit(5).all()
    
    # Get all users for admin
    users = User.query.all() if current_user.is_admin() else []
    
    demo_data = {
        'your_access_level': current_user.get_price_display_level(),
        'can_see_prices': current_user.can_view_prices(),
        'can_see_totals': current_user.can_view_financial_values(),
        'can_modify_prices': current_user.can_modify_prices(),
        'sample_items': sample_items,
        'users': users
    }
    
    return render_template('demo/price_access_demo.html', **demo_data)