"""
Cost Change Notification Routes
Phase 2: Smart automation features
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models.cost_settings import CostCalculationSettings, CostChangeNotification
from services.cost_notifications import CostNotificationService, SmartBomCreationService
from app import db
import logging

logger = logging.getLogger(__name__)

cost_notifications_bp = Blueprint('cost_notifications', __name__, url_prefix='/cost-notifications')


@cost_notifications_bp.route('/dashboard')
@login_required
def notifications_dashboard():
    """Cost change notifications dashboard"""
    try:
        settings = CostCalculationSettings.get_current_settings()
        
        if not settings.enable_cost_change_notifications:
            flash('Cost change notifications are disabled', 'info')
            return redirect(url_for('cost_calculation.cost_dashboard'))
        
        # Get pending notifications
        pending_notifications = CostNotificationService.get_pending_notifications()
        
        # Get outdated costs
        outdated_result = CostNotificationService.check_outdated_costs()
        outdated_items = outdated_result.get('outdated_items', [])
        
        return render_template('cost_calculation/notifications.html',
                             pending_notifications=pending_notifications,
                             outdated_items=outdated_items,
                             settings=settings)
        
    except Exception as e:
        logger.error(f"Error loading notifications dashboard: {str(e)}")
        flash('Error loading notifications', 'error')
        return redirect(url_for('cost_calculation.cost_dashboard'))


@cost_notifications_bp.route('/api/check-changes', methods=['POST'])
@login_required
def check_cost_changes():
    """API endpoint to manually trigger cost change check"""
    try:
        result = CostNotificationService.check_cost_changes()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error checking cost changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_notifications_bp.route('/api/acknowledge/<int:notification_id>', methods=['POST'])
@login_required
def acknowledge_notification(notification_id):
    """API endpoint to acknowledge a notification"""
    try:
        success = CostNotificationService.acknowledge_notification(
            notification_id, 
            current_user.username if current_user else 'Unknown'
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Notification acknowledged'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Notification not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error acknowledging notification: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_notifications_bp.route('/api/bulk-acknowledge', methods=['POST'])
@login_required
def bulk_acknowledge_notifications():
    """API endpoint to acknowledge multiple notifications"""
    try:
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if not notification_ids:
            return jsonify({
                'success': False,
                'error': 'No notifications selected'
            }), 400
        
        acknowledged_count = 0
        for notification_id in notification_ids:
            success = CostNotificationService.acknowledge_notification(
                notification_id,
                current_user.username if current_user else 'Unknown'
            )
            if success:
                acknowledged_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Acknowledged {acknowledged_count} notifications',
            'acknowledged_count': acknowledged_count
        })
        
    except Exception as e:
        logger.error(f"Error bulk acknowledging notifications: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_notifications_bp.route('/smart-bom')
@login_required
def smart_bom_creation():
    """Smart BOM creation workflow"""
    try:
        settings = CostCalculationSettings.get_current_settings()
        
        if not settings.enable_smart_bom_creation:
            flash('Smart BOM creation is disabled', 'info')
            return redirect(url_for('bom.list_boms'))
        
        return render_template('cost_calculation/smart_bom.html', settings=settings)
        
    except Exception as e:
        logger.error(f"Error loading smart BOM creation: {str(e)}")
        flash('Error loading smart BOM creation', 'error')
        return redirect(url_for('bom.list_boms'))


@cost_notifications_bp.route('/api/validate-bom', methods=['POST'])
@login_required
def validate_bom_for_costing():
    """API endpoint to validate BOM for cost calculation"""
    try:
        data = request.get_json()
        bom_data = data.get('bom_data', {})
        
        validation_result = SmartBomCreationService.validate_bom_for_costing(bom_data)
        
        return jsonify({
            'success': True,
            'validation': validation_result
        })
        
    except Exception as e:
        logger.error(f"Error validating BOM: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_notifications_bp.route('/api/suggest-components', methods=['POST'])
@login_required
def suggest_missing_components():
    """API endpoint to suggest missing BOM components"""
    try:
        data = request.get_json()
        product_name = data.get('product_name', '')
        existing_components = data.get('existing_components', [])
        
        suggestions = SmartBomCreationService.suggest_missing_components(
            product_name, existing_components
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error suggesting components: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_notifications_bp.route('/api/outdated-costs')
@login_required
def get_outdated_costs():
    """API endpoint to get items with outdated cost calculations"""
    try:
        result = CostNotificationService.check_outdated_costs()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting outdated costs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500