"""
User-friendly user management routes with price visibility controls
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import User, db
from models.permissions import Permission, UserPermission
from services.price_visibility import PriceVisibilityService
from functools import wraps

user_management_bp = Blueprint('user_management', __name__, url_prefix='/users')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@user_management_bp.route('/')
@login_required
@admin_required
def list_users():
    """List all users with their price access levels"""
    users = User.query.all()
    
    # Add price access info to each user
    users_with_access = []
    for user in users:
        user_info = {
            'user': user,
            'price_role': PriceVisibilityService.get_user_price_role_display(user),
            'price_badge': PriceVisibilityService.create_price_access_badge(user),
            'can_see_prices': user.can_view_prices(),
            'can_see_totals': user.can_view_financial_values(),
            'can_modify_prices': user.can_modify_prices()
        }
        users_with_access.append(user_info)
    
    return render_template('users/list_users.html', users_data=users_with_access)

@user_management_bp.route('/<int:user_id>/price-permissions')
@login_required
@admin_required
def manage_price_permissions(user_id):
    """Manage price-related permissions for a user"""
    user = User.query.get_or_404(user_id)
    
    # Get all price-related permissions
    price_permissions = Permission.query.filter_by(category='pricing').all()
    
    # Get user's current permissions
    user_permissions = {}
    for perm in price_permissions:
        user_permissions[perm.code] = user.has_permission(perm.code)
    
    if request.method == 'POST':
        # Update permissions
        for perm in price_permissions:
            has_permission = request.form.get(f'perm_{perm.code}') == 'on'
            
            if has_permission and not user_permissions[perm.code]:
                user.grant_permission(perm.code, current_user.id)
            elif not has_permission and user_permissions[perm.code]:
                user.revoke_permission(perm.code)
        
        db.session.commit()
        flash(f'Price permissions updated for {user.username}', 'success')
        return redirect(url_for('user_management.list_users'))
    
    return render_template('users/price_permissions.html', 
                         user=user, 
                         permissions=price_permissions,
                         user_permissions=user_permissions)

@user_management_bp.route('/price-access-guide')
@login_required
def price_access_guide():
    """User-friendly guide explaining price access levels"""
    
    access_levels = [
        {
            'level': 'Administrator',
            'badge': 'success',
            'icon': 'crown',
            'description': 'Complete access to all pricing information, cost analysis, and financial data',
            'permissions': [
                'View all item prices and rates',
                'See complete financial totals and inventory valuations',
                'Access historical price changes',
                'Modify item prices and approve bulk changes',
                'View detailed cost analysis and profitability reports'
            ]
        },
        {
            'level': 'Manager (Full Financial)',
            'badge': 'primary',
            'icon': 'chart-line',
            'description': 'Full financial access including totals and cost analysis',
            'permissions': [
                'View all item prices and rates',
                'See complete financial totals and inventory valuations',
                'Access historical price changes',
                'View detailed cost analysis and profitability reports'
            ]
        },
        {
            'level': 'Financial Staff',
            'badge': 'info',
            'icon': 'calculator',
            'description': 'Can see financial values and totals for accounting purposes',
            'permissions': [
                'View inventory valuations and totals',
                'See basic cost information',
                'Access financial reports'
            ]
        },
        {
            'level': 'Basic Staff',
            'badge': 'warning',
            'icon': 'tag',
            'description': 'Limited price access for daily operations',
            'permissions': [
                'View basic item prices and rates',
                'See quantities and availability',
                'No access to financial totals'
            ]
        },
        {
            'level': 'Production Operator',
            'badge': 'secondary',
            'icon': 'eye-slash',
            'description': 'No price access - focus on production operations',
            'permissions': [
                'View item quantities and availability',
                'See production schedules and job cards',
                'Access quality control information',
                'All pricing information is hidden'
            ]
        }
    ]
    
    return render_template('users/price_access_guide.html', access_levels=access_levels)

@user_management_bp.route('/api/toggle-price-permission', methods=['POST'])
@login_required
@admin_required
def toggle_price_permission():
    """API endpoint to quickly toggle price permissions"""
    data = request.get_json()
    user_id = data.get('user_id')
    permission_code = data.get('permission_code')
    enable = data.get('enable', False)
    
    user = User.query.get_or_404(user_id)
    
    if enable:
        success = user.grant_permission(permission_code, current_user.id)
    else:
        success = user.revoke_permission(permission_code)
    
    if success:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Permission {"granted" if enable else "revoked"} successfully',
            'new_badge': str(PriceVisibilityService.create_price_access_badge(user))
        })
    
    return jsonify({'success': False, 'message': 'Failed to update permission'}), 400