"""
Cost Calculation Settings Routes
Manage feature toggles and configuration
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.cost_settings import CostCalculationSettings
from app import db
import logging

logger = logging.getLogger(__name__)

cost_settings_bp = Blueprint('cost_settings', __name__, url_prefix='/cost-settings')


@cost_settings_bp.route('/')
@login_required
def settings_dashboard():
    """Cost calculation settings dashboard"""
    try:
        settings = CostCalculationSettings.get_current_settings()
        return render_template('cost_calculation/settings.html', settings=settings)
    except Exception as e:
        logger.error(f"Error loading cost settings: {str(e)}")
        flash('Error loading settings', 'error')
        return redirect(url_for('cost_calculation.cost_dashboard'))


@cost_settings_bp.route('/api/get', methods=['GET'])
@login_required
def get_settings_api():
    """API endpoint to get current settings"""
    try:
        settings = CostCalculationSettings.get_current_settings()
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        })
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_settings_bp.route('/api/update', methods=['POST'])
@login_required
def update_settings_api():
    """API endpoint to update settings"""
    try:
        data = request.get_json()
        settings = CostCalculationSettings.get_current_settings()
        
        # Update Phase 2 settings
        if 'phase2' in data:
            settings.enable_cost_change_notifications = data['phase2'].get('cost_change_notifications', settings.enable_cost_change_notifications)
            settings.enable_smart_bom_creation = data['phase2'].get('smart_bom_creation', settings.enable_smart_bom_creation)
            settings.enable_automated_cost_validation = data['phase2'].get('automated_cost_validation', settings.enable_automated_cost_validation)
            settings.enable_integration_alerts = data['phase2'].get('integration_alerts', settings.enable_integration_alerts)
        
        # Update Phase 3 settings
        if 'phase3' in data:
            settings.enable_interactive_calculator = data['phase3'].get('interactive_calculator', settings.enable_interactive_calculator)
            settings.enable_cost_simulation = data['phase3'].get('cost_simulation', settings.enable_cost_simulation)
            settings.enable_drag_drop_bom = data['phase3'].get('drag_drop_bom', settings.enable_drag_drop_bom)
            settings.enable_smart_search = data['phase3'].get('smart_search', settings.enable_smart_search)
        
        # Update threshold settings
        if 'thresholds' in data:
            settings.cost_change_threshold_percent = data['thresholds'].get('cost_change_threshold', settings.cost_change_threshold_percent)
            settings.outdated_cost_days = data['thresholds'].get('outdated_cost_days', settings.outdated_cost_days)
        
        # Update performance settings
        if 'performance' in data:
            settings.real_time_calculation_enabled = data['performance'].get('real_time_calculation', settings.real_time_calculation_enabled)
            settings.batch_calculation_size = data['performance'].get('batch_size', settings.batch_calculation_size)
        
        # Update UI settings
        if 'ui' in data:
            settings.default_cost_view = data['ui'].get('default_view', settings.default_cost_view)
            settings.show_advanced_analytics = data['ui'].get('advanced_analytics', settings.show_advanced_analytics)
            settings.enable_bulk_operations = data['ui'].get('bulk_operations', settings.enable_bulk_operations)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Settings updated successfully',
            'settings': settings.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_settings_bp.route('/reset-defaults', methods=['POST'])
@login_required
def reset_to_defaults():
    """Reset all settings to default values"""
    try:
        settings = CostCalculationSettings.get_current_settings()
        
        # Reset to defaults
        settings.enable_cost_change_notifications = True
        settings.enable_smart_bom_creation = True
        settings.enable_automated_cost_validation = True
        settings.enable_integration_alerts = True
        settings.enable_interactive_calculator = True
        settings.enable_cost_simulation = True
        settings.enable_drag_drop_bom = True
        settings.enable_smart_search = True
        settings.cost_change_threshold_percent = 10.0
        settings.outdated_cost_days = 7
        settings.real_time_calculation_enabled = True
        settings.batch_calculation_size = 50
        settings.default_cost_view = 'comparison'
        settings.show_advanced_analytics = True
        settings.enable_bulk_operations = True
        
        db.session.commit()
        
        flash('Settings reset to defaults', 'success')
        return redirect(url_for('cost_settings.settings_dashboard'))
        
    except Exception as e:
        logger.error(f"Error resetting settings: {str(e)}")
        flash('Error resetting settings', 'error')
        return redirect(url_for('cost_settings.settings_dashboard'))


@cost_settings_bp.route('/toggle-feature', methods=['POST'])
@login_required
def toggle_feature():
    """Quick toggle for individual features"""
    try:
        data = request.get_json()
        feature_name = data.get('feature')
        enabled = data.get('enabled', False)
        
        settings = CostCalculationSettings.get_current_settings()
        
        if hasattr(settings, feature_name):
            setattr(settings, feature_name, enabled)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Feature {feature_name} {"enabled" if enabled else "disabled"}',
                'feature': feature_name,
                'enabled': enabled
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown feature: {feature_name}'
            }), 400
            
    except Exception as e:
        logger.error(f"Error toggling feature: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500