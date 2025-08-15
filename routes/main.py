from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Item, PurchaseOrder, SalesOrder, Employee, JobWork, Production
from models.dashboard import DashboardModule, UserDashboardPreference, get_user_dashboard_modules, init_user_default_preferences
from sqlalchemy import func
from app import db

main_bp = Blueprint('main', __name__)

# Add redirect routes for common URL mistakes
@main_bp.route('/items/add')
@login_required
def items_add_redirect():
    """Redirect from /items/add to correct inventory add route"""
    return redirect(url_for('inventory.add_item'))

@main_bp.route('/items')
@main_bp.route('/items/')
@login_required
def items_list_redirect():
    """Redirect from /items to correct inventory list route"""
    return redirect(url_for('inventory.list_items'))

@main_bp.route('/')
@login_required
def dashboard():
    # Initialize user preferences if they don't exist
    init_user_default_preferences(current_user.id)
    
    # Get user's customized dashboard modules
    user_modules = get_user_dashboard_modules(current_user.id)
    
    # Get dashboard statistics
    stats = {
        'total_items': Item.query.count(),
        'low_stock_items': Item.query.filter(Item.current_stock <= Item.minimum_stock).count(),
        'open_purchase_orders': PurchaseOrder.query.filter_by(status='open').count(),
        'pending_sales_orders': SalesOrder.query.filter_by(status='pending').count(),
        'active_employees': Employee.query.filter_by(is_active=True).count(),
        'open_job_works': JobWork.query.filter_by(status='sent').count(),
        'planned_productions': Production.query.filter_by(status='planned').count()
    }
    
    # Recent activities
    recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).limit(5).all()
    recent_sos = SalesOrder.query.order_by(SalesOrder.created_at.desc()).limit(5).all()
    low_stock_items = Item.query.filter(Item.current_stock <= Item.minimum_stock).limit(10).all()
    
    # Validate URLs for each module to prevent build errors
    for user_module in user_modules:
        module = user_module['module']
        try:
            # Try to build the URL to check if endpoint exists
            module.valid_url = url_for(module.url_endpoint)
        except:
            # If endpoint doesn't exist, set as None for fallback
            module.valid_url = None
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         recent_pos=recent_pos, 
                         recent_sos=recent_sos,
                         low_stock_items=low_stock_items,
                         user_modules=user_modules)

@main_bp.route('/customize_dashboard')
@login_required
def customize_dashboard():
    """Dashboard customization page"""
    # Get all available modules
    all_modules = DashboardModule.query.filter_by(is_active=True).all()
    
    # Get user's current preferences
    user_preferences = {}
    preferences = UserDashboardPreference.query.filter_by(user_id=current_user.id).all()
    for pref in preferences:
        user_preferences[pref.module_id] = {
            'is_visible': pref.is_visible,
            'position': pref.position,
            'size': pref.size
        }
    
    return render_template('dashboard_customize.html', 
                         all_modules=all_modules,
                         user_preferences=user_preferences)

@main_bp.route('/save_dashboard_preferences', methods=['POST'])
@login_required
def save_dashboard_preferences():
    """Save user's dashboard preferences"""
    try:
        preferences_data = request.get_json()
        
        # Clear existing preferences
        UserDashboardPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Save new preferences
        for pref_data in preferences_data:
            preference = UserDashboardPreference(
                user_id=current_user.id,
                module_id=pref_data['module_id'],
                is_visible=pref_data['is_visible'],
                position=pref_data['position'],
                size=pref_data.get('size', 'medium')
            )
            db.session.add(preference)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Dashboard preferences saved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error saving preferences: {str(e)}'
        }), 400

@main_bp.route('/reset_dashboard_preferences', methods=['POST'])
@login_required
def reset_dashboard_preferences():
    """Reset dashboard to default layout"""
    try:
        # Clear existing preferences
        UserDashboardPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Reinitialize default preferences
        init_user_default_preferences(current_user.id)
        
        flash('Dashboard reset to default layout successfully!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting dashboard: {str(e)}', 'danger')
        return redirect(url_for('main.customize_dashboard'))
