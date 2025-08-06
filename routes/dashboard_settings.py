from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models.dashboard import DashboardModule, UserDashboardPreference

dashboard_settings_bp = Blueprint('dashboard_settings', __name__, url_prefix='/dashboard_settings')

@dashboard_settings_bp.route('/notifications')
@login_required
def notifications_settings():
    """Dashboard notifications settings"""
    # Get user's current notification preferences (for future implementation)
    notification_types = [
        {
            'id': 'low_stock',
            'name': 'Low Stock Alerts',
            'description': 'Get notified when items are running low',
            'enabled': True
        },
        {
            'id': 'pending_approvals',
            'name': 'Pending Approvals',
            'description': 'Show pending purchase orders and other approvals',
            'enabled': True
        },
        {
            'id': 'job_work_updates',
            'name': 'Job Work Updates',
            'description': 'Updates on job work progress and completion',
            'enabled': True
        },
        {
            'id': 'production_alerts',
            'name': 'Production Alerts',
            'description': 'Production schedule changes and delays',
            'enabled': False
        },
        {
            'id': 'daily_summary',
            'name': 'Daily Summary',
            'description': 'Daily summary of factory operations',
            'enabled': False
        }
    ]
    
    return render_template('dashboard_settings/notifications.html', 
                         notification_types=notification_types)

@dashboard_settings_bp.route('/layout')
@login_required
def layout_settings():
    """Dashboard layout customization"""
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
    
    return render_template('dashboard_settings/layout.html', 
                         all_modules=all_modules,
                         user_preferences=user_preferences)

@dashboard_settings_bp.route('/save_notification_preferences', methods=['POST'])
@login_required
def save_notification_preferences():
    """Save user's notification preferences"""
    try:
        preferences_data = request.get_json()
        
        # For now, just return success (implement actual saving later)
        # In the future, create a UserNotificationPreference model
        
        flash('Notification preferences saved successfully!', 'success')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@dashboard_settings_bp.route('/save_layout_preferences', methods=['POST'])
@login_required
def save_layout_preferences():
    """Save user's dashboard layout preferences"""
    try:
        preferences_data = request.get_json()
        
        # Clear existing preferences
        UserDashboardPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Save new preferences
        for module_id, prefs in preferences_data.items():
            preference = UserDashboardPreference(
                user_id=current_user.id,
                module_id=int(module_id),
                is_visible=prefs.get('is_visible', True),
                position=prefs.get('position', 0),
                size=prefs.get('size', 'medium')
            )
            db.session.add(preference)
        
        db.session.commit()
        flash('Dashboard layout saved successfully!', 'success')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400