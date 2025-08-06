"""
Admin panel for comprehensive notification management
Provides full control over notification settings, recipients, templates, and logs
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from models.notifications import (
    NotificationSettings, NotificationRecipient, NotificationLog, 
    NotificationTemplate, InAppNotification, NotificationSchedule
)
from models import User
from datetime import datetime, timedelta
from sqlalchemy import func, desc

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Notification system admin dashboard"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get notification statistics
    stats = {
        'total_sent': NotificationLog.query.filter_by(success=True).count(),
        'total_failed': NotificationLog.query.filter_by(success=False).count(),
        'active_recipients': NotificationRecipient.query.filter_by(is_active=True).count(),
        'total_templates': NotificationTemplate.query.filter_by(is_active=True).count()
    }
    
    # Recent notification logs
    recent_logs = NotificationLog.query.order_by(desc(NotificationLog.sent_at)).limit(10).all()
    
    # Notification stats by type
    type_stats = db.session.query(
        NotificationLog.type, 
        func.count(NotificationLog.id).label('count'),
        func.sum(func.cast(NotificationLog.success, db.Integer)).label('success_count')
    ).group_by(NotificationLog.type).all()
    
    # Daily notification trends (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_stats = db.session.query(
        func.date(NotificationLog.sent_at).label('date'),
        func.count(NotificationLog.id).label('total'),
        func.sum(func.cast(NotificationLog.success, db.Integer)).label('successful')
    ).filter(
        NotificationLog.sent_at >= seven_days_ago
    ).group_by(func.date(NotificationLog.sent_at)).all()
    
    # Get current settings
    settings = NotificationSettings.get_settings()
    
    return render_template('notifications/admin/dashboard.html',
                         stats=stats,
                         recent_logs=recent_logs,
                         type_stats=type_stats,
                         daily_stats=daily_stats,
                         settings=settings)

@notifications_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Manage notification system settings"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    settings = NotificationSettings.get_settings()
    
    if request.method == 'POST':
        try:
            # Update channel settings
            settings.email_enabled = 'email_enabled' in request.form
            settings.sms_enabled = 'sms_enabled' in request.form
            settings.whatsapp_enabled = 'whatsapp_enabled' in request.form
            settings.in_app_enabled = 'in_app_enabled' in request.form
            
            # Update service configuration
            settings.sender_email = request.form.get('sender_email', settings.sender_email)
            settings.sender_name = request.form.get('sender_name', settings.sender_name)
            
            # Update event-specific settings
            settings.po_notifications = 'po_notifications' in request.form
            settings.grn_notifications = 'grn_notifications' in request.form
            settings.job_work_notifications = 'job_work_notifications' in request.form
            settings.production_notifications = 'production_notifications' in request.form
            settings.sales_notifications = 'sales_notifications' in request.form
            settings.accounts_notifications = 'accounts_notifications' in request.form
            settings.inventory_notifications = 'inventory_notifications' in request.form
            
            # Update specific event controls
            settings.po_vendor_notification = 'po_vendor_notification' in request.form
            settings.grn_rejection_notification = 'grn_rejection_notification' in request.form
            settings.job_work_vendor_notification = 'job_work_vendor_notification' in request.form
            settings.customer_invoice_notification = 'customer_invoice_notification' in request.form
            settings.payment_overdue_notification = 'payment_overdue_notification' in request.form
            settings.low_stock_notifications = 'low_stock_notifications' in request.form
            settings.scrap_threshold_notifications = 'scrap_threshold_notifications' in request.form
            
            # Update admin recipients
            settings.admin_email = request.form.get('admin_email', settings.admin_email)
            settings.admin_phone = request.form.get('admin_phone', settings.admin_phone)
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Notification settings updated successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'danger')
    
    return render_template('notifications/admin/settings.html', settings=settings)

@notifications_bp.route('/admin/recipients')
@login_required
def admin_recipients():
    """Manage notification recipients"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = NotificationRecipient.query
    
    if role_filter:
        query = query.filter(NotificationRecipient.role == role_filter)
    
    if status_filter == 'active':
        query = query.filter(NotificationRecipient.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(NotificationRecipient.is_active == False)
    
    recipients = query.order_by(NotificationRecipient.name).all()
    
    # Get unique roles for filter
    roles = db.session.query(NotificationRecipient.role).distinct().all()
    role_list = [role[0] for role in roles if role[0]]
    
    return render_template('notifications/admin/recipients.html',
                         recipients=recipients,
                         role_filter=role_filter,
                         status_filter=status_filter,
                         roles=role_list)

@notifications_bp.route('/admin/recipients/add', methods=['GET', 'POST'])
@login_required
def add_recipient():
    """Add new notification recipient"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            # Get notification types
            notification_types = []
            if 'email_notifications' in request.form:
                notification_types.append('email')
            if 'sms_notifications' in request.form:
                notification_types.append('sms')
            if 'whatsapp_notifications' in request.form:
                notification_types.append('whatsapp')
            if 'in_app_notifications' in request.form:
                notification_types.append('in_app')
            
            # Get event subscriptions
            event_types = []
            if 'po_events' in request.form:
                event_types.append('purchase_team')
            if 'grn_events' in request.form:
                event_types.append('store')
            if 'job_work_events' in request.form:
                event_types.append('production_head')
            if 'production_events' in request.form:
                event_types.append('production_supervisor')
            if 'sales_events' in request.form:
                event_types.append('sales_team')
            if 'accounts_events' in request.form:
                event_types.append('accounts')
            if 'inventory_events' in request.form:
                event_types.append('store')
            if 'hr_events' in request.form:
                event_types.append('hr_team')
            
            recipient = NotificationRecipient()
            recipient.name = request.form['name']
            recipient.email = request.form.get('email') or None
            recipient.phone = request.form.get('phone') or None
            recipient.role = request.form.get('role')
            recipient.department = request.form.get('department')
            recipient.notification_types = ','.join(notification_types)
            recipient.event_types = ','.join(event_types)
            recipient.po_events = 'po_events' in request.form
            recipient.grn_events = 'grn_events' in request.form
            recipient.job_work_events = 'job_work_events' in request.form
            recipient.production_events = 'production_events' in request.form
            recipient.sales_events = 'sales_events' in request.form
            recipient.accounts_events = 'accounts_events' in request.form
            recipient.inventory_events = 'inventory_events' in request.form
            recipient.hr_events = 'hr_events' in request.form
            recipient.immediate_notifications = 'immediate_notifications' in request.form
            recipient.daily_summary = 'daily_summary' in request.form
            recipient.weekly_summary = 'weekly_summary' in request.form
            recipient.is_active = 'is_active' in request.form
            recipient.is_external = 'is_external' in request.form
            
            db.session.add(recipient)
            db.session.commit()
            
            flash(f'Recipient "{recipient.name}" added successfully!', 'success')
            return redirect(url_for('notifications.admin_recipients'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding recipient: {str(e)}', 'danger')
    
    return render_template('notifications/admin/recipient_form.html', recipient=None, title='Add Recipient')

@notifications_bp.route('/admin/recipients/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_recipient(id):
    """Edit notification recipient"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    recipient = NotificationRecipient.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Update notification types
            notification_types = []
            if 'email_notifications' in request.form:
                notification_types.append('email')
            if 'sms_notifications' in request.form:
                notification_types.append('sms')
            if 'whatsapp_notifications' in request.form:
                notification_types.append('whatsapp')
            if 'in_app_notifications' in request.form:
                notification_types.append('in_app')
            
            # Update event subscriptions
            event_types = []
            if 'po_events' in request.form:
                event_types.append('purchase_team')
            if 'grn_events' in request.form:
                event_types.append('store')
            if 'job_work_events' in request.form:
                event_types.append('production_head')
            if 'production_events' in request.form:
                event_types.append('production_supervisor')
            if 'sales_events' in request.form:
                event_types.append('sales_team')
            if 'accounts_events' in request.form:
                event_types.append('accounts')
            if 'inventory_events' in request.form:
                event_types.append('store')
            if 'hr_events' in request.form:
                event_types.append('hr_team')
            
            recipient.name = request.form['name']
            recipient.email = request.form.get('email') or None
            recipient.phone = request.form.get('phone') or None
            recipient.role = request.form['role']
            recipient.department = request.form.get('department')
            recipient.notification_types = ','.join(notification_types)
            recipient.event_types = ','.join(event_types)
            recipient.po_events = 'po_events' in request.form
            recipient.grn_events = 'grn_events' in request.form
            recipient.job_work_events = 'job_work_events' in request.form
            recipient.production_events = 'production_events' in request.form
            recipient.sales_events = 'sales_events' in request.form
            recipient.accounts_events = 'accounts_events' in request.form
            recipient.inventory_events = 'inventory_events' in request.form
            recipient.hr_events = 'hr_events' in request.form
            recipient.immediate_notifications = 'immediate_notifications' in request.form
            recipient.daily_summary = 'daily_summary' in request.form
            recipient.weekly_summary = 'weekly_summary' in request.form
            recipient.is_active = 'is_active' in request.form
            recipient.is_external = 'is_external' in request.form
            recipient.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Recipient "{recipient.name}" updated successfully!', 'success')
            return redirect(url_for('notifications.admin_recipients'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recipient: {str(e)}', 'danger')
    
    return render_template('notifications/admin/recipient_form.html', recipient=recipient, title='Edit Recipient')

@notifications_bp.route('/admin/recipients/delete/<int:id>')
@login_required
def delete_recipient(id):
    """Delete notification recipient"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    recipient = NotificationRecipient.query.get_or_404(id)
    
    try:
        db.session.delete(recipient)
        db.session.commit()
        flash(f'Recipient "{recipient.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recipient: {str(e)}', 'danger')
    
    return redirect(url_for('notifications.admin_recipients'))

@notifications_bp.route('/admin/logs')
@login_required
def admin_logs():
    """View notification logs"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    type_filter = request.args.get('type', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    date_filter = request.args.get('date', '', type=str)
    
    query = NotificationLog.query
    
    if type_filter:
        query = query.filter(NotificationLog.type == type_filter)
    
    if status_filter == 'success':
        query = query.filter(NotificationLog.success == True)
    elif status_filter == 'failed':
        query = query.filter(NotificationLog.success == False)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(func.date(NotificationLog.sent_at) == filter_date)
        except ValueError:
            flash('Invalid date format', 'warning')
    
    logs = query.order_by(desc(NotificationLog.sent_at)).paginate(
        page=page, per_page=50, error_out=False)
    
    return render_template('notifications/admin/logs.html',
                         logs=logs,
                         type_filter=type_filter,
                         status_filter=status_filter,
                         date_filter=date_filter)

@notifications_bp.route('/admin/test', methods=['GET', 'POST'])
@login_required
def test_notifications():
    """Test notification system"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            from services.comprehensive_notifications import comprehensive_notification_service
            
            notification_type = request.form['notification_type']
            recipient = request.form['recipient']
            subject = request.form['subject']
            message = request.form['message']
            
            # Test sending notification
            if notification_type == 'email':
                from services.notification_helpers import send_email_notification
                success = send_email_notification(recipient, subject, message)
            elif notification_type == 'sms':
                from services.notification_helpers import send_sms_notification
                success = send_sms_notification(recipient, f"{subject}: {message}")
            elif notification_type == 'whatsapp':
                from services.notification_helpers import send_whatsapp_notification
                success = send_whatsapp_notification(recipient, f"{subject}: {message}")
            else:
                success = False
            
            if success:
                flash(f'Test {notification_type} notification sent successfully!', 'success')
            else:
                flash(f'Failed to send test {notification_type} notification. Check settings and credentials.', 'danger')
                
        except Exception as e:
            flash(f'Error sending test notification: {str(e)}', 'danger')
    
    return render_template('notifications/admin/test.html')

@notifications_bp.route('/api/notification-stats')
@login_required
def api_notification_stats():
    """API endpoint for notification statistics"""
    if not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    # Get hourly stats for the last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    hourly_stats = db.session.query(
        func.date_trunc('hour', NotificationLog.sent_at).label('hour'),
        func.count(NotificationLog.id).label('total'),
        func.sum(func.cast(NotificationLog.success, db.Integer)).label('successful'),
        func.sum(func.cast(~NotificationLog.success, db.Integer)).label('failed')
    ).filter(
        NotificationLog.sent_at >= twenty_four_hours_ago
    ).group_by(func.date_trunc('hour', NotificationLog.sent_at)).all()
    
    chart_data = []
    for stat in hourly_stats:
        chart_data.append({
            'hour': stat.hour.isoformat(),
            'total': stat.total,
            'successful': stat.successful,
            'failed': stat.failed
        })
    
    return jsonify({
        'hourly_stats': chart_data,
        'success': True
    })

@notifications_bp.route('/admin/bulk-test')
@login_required
def bulk_test_notifications():
    """Test comprehensive notification system across all modules"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        from services.comprehensive_notifications import comprehensive_notification_service
        
        # Test different notification scenarios
        test_results = []
        
        # Test low stock alert
        try:
            from services.notification_helpers import send_system_alert
            result = send_system_alert(
                "🧪 Test Low Stock Alert",
                "This is a test notification for low stock monitoring. System is working correctly.",
                "system_alert"
            )
            test_results.append(('Low Stock Alert', 'success' if result else 'failed'))
        except Exception as e:
            test_results.append(('Low Stock Alert', f'error: {str(e)}'))
        
        # Test system alert
        try:
            from services.notification_helpers import send_system_alert
            result = send_system_alert(
                "🧪 System Test Alert",
                "Comprehensive notification system test completed successfully.",
                "system_alert"
            )
            test_results.append(('System Alert', 'success' if result else 'failed'))
        except Exception as e:
            test_results.append(('System Alert', f'error: {str(e)}'))
        
        flash('Bulk notification test completed. Check results below.', 'info')
        
        return render_template('notifications/admin/test.html', test_results=test_results)
        
    except Exception as e:
        flash(f'Error running bulk test: {str(e)}', 'danger')
        return redirect(url_for('notifications.admin_dashboard'))