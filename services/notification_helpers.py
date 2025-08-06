"""
Helper functions to integrate notifications with existing system components
"""
from typing import List, Dict, Optional
from services.notifications import notification_service, NotificationTemplates
import logging

logger = logging.getLogger(__name__)

def send_low_stock_alert(item):
    """Send low stock alert for an item"""
    try:
        from models import NotificationSettings
        from models.notifications import NotificationRecipient
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.low_stock_notifications:
            return False
        
        # Get template
        template = NotificationTemplates.low_stock_alert(
            item.name, 
            item.current_stock, 
            item.minimum_stock
        )
        
        # Get recipients for low stock alerts
        recipients = NotificationRecipient.query.filter(
            NotificationRecipient.is_active == True,
            NotificationRecipient.event_types.contains('low_stock')
        ).all()
        
        success_count = 0
        for recipient in recipients:
            notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
            
            for notification_type in notification_types:
                notification_type = notification_type.strip()
                
                if notification_type == 'email' and recipient.email and settings.email_enabled:
                    success = notification_service.send_email(
                        recipient.email,
                        template['subject'],
                        template['message'],
                        template['html']
                    )
                    if success:
                        success_count += 1
                
                elif notification_type == 'sms' and recipient.phone and settings.sms_enabled:
                    success = notification_service.send_sms(
                        recipient.phone,
                        template['message']
                    )
                    if success:
                        success_count += 1
                
                elif notification_type == 'whatsapp' and recipient.phone and settings.whatsapp_enabled:
                    success = notification_service.send_whatsapp(
                        recipient.phone,
                        template['message']
                    )
                    if success:
                        success_count += 1
        
        # Also send to admin if configured
        if settings.admin_email and settings.email_enabled:
            notification_service.send_email(
                settings.admin_email,
                template['subject'],
                template['message'],
                template['html']
            )
        
        if settings.admin_phone and settings.sms_enabled:
            notification_service.send_sms(
                settings.admin_phone,
                template['message']
            )
        
        logger.info(f"Low stock alert sent for {item.name} - {success_count} notifications sent")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Failed to send low stock alert: {e}")
        return False

def send_order_status_update(order_type: str, order_id: str, status: str, customer_email: str = None):
    """Send order status update notification"""
    try:
        from models import NotificationSettings
        from models.notifications import NotificationRecipient
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.order_status_notifications:
            return False
        
        template = NotificationTemplates.order_status_update(order_type, order_id, status)
        
        # Send to customer if email provided
        if customer_email and settings.email_enabled:
            notification_service.send_email(
                customer_email,
                template['subject'],
                template['message'],
                template['html']
            )
        
        # Send to internal recipients
        recipients = NotificationRecipient.query.filter(
            NotificationRecipient.is_active == True,
            NotificationRecipient.event_types.contains('order_update')
        ).all()
        
        success_count = 0
        for recipient in recipients:
            notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
            
            for notification_type in notification_types:
                notification_type = notification_type.strip()
                
                if notification_type == 'email' and recipient.email and settings.email_enabled:
                    success = notification_service.send_email(
                        recipient.email,
                        template['subject'],
                        template['message'],
                        template['html']
                    )
                    if success:
                        success_count += 1
        
        logger.info(f"Order status update sent for {order_type} #{order_id} - {success_count} notifications sent")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Failed to send order status update: {e}")
        return False

def send_production_complete_notification(production_id: str, item_name: str, quantity: int):
    """Send production completion notification"""
    try:
        from models import NotificationSettings
        from models.notifications import NotificationRecipient
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.production_notifications:
            return False
        
        template = NotificationTemplates.production_complete(production_id, item_name, quantity)
        
        recipients = NotificationRecipient.query.filter(
            NotificationRecipient.is_active == True,
            NotificationRecipient.event_types.contains('production_complete')
        ).all()
        
        success_count = 0
        for recipient in recipients:
            notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
            
            for notification_type in notification_types:
                notification_type = notification_type.strip()
                
                if notification_type == 'email' and recipient.email and settings.email_enabled:
                    success = notification_service.send_email(
                        recipient.email,
                        template['subject'],
                        template['message'],
                        template['html']
                    )
                    if success:
                        success_count += 1
                
                elif notification_type == 'sms' and recipient.phone and settings.sms_enabled:
                    success = notification_service.send_sms(
                        recipient.phone,
                        template['message']
                    )
                    if success:
                        success_count += 1
        
        logger.info(f"Production complete notification sent for {item_name} - {success_count} notifications sent")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Failed to send production complete notification: {e}")
        return False

def check_and_alert_low_stock():
    """Check all items for low stock and send alerts"""
    try:
        from models import Item
        
        low_stock_items = Item.query.filter(
            Item.current_stock <= Item.minimum_stock,
            Item.minimum_stock > 0
        ).all()
        
        alerts_sent = 0
        for item in low_stock_items:
            if send_low_stock_alert(item):
                alerts_sent += 1
        
        logger.info(f"Low stock check completed - {alerts_sent} alerts sent for {len(low_stock_items)} items")
        return alerts_sent
        
    except Exception as e:
        logger.error(f"Failed to check low stock: {e}")
        return 0

def send_system_alert(subject: str, message: str, alert_type: str = 'system_alert'):
    """Send system alert to relevant recipients"""
    try:
        from models import NotificationSettings
        from models.notifications import NotificationRecipient
        
        settings = NotificationSettings.query.first()
        if not settings:
            return False
        
        recipients = NotificationRecipient.query.filter(
            NotificationRecipient.is_active == True,
            NotificationRecipient.event_types.contains(alert_type)
        ).all()
        
        success_count = 0
        for recipient in recipients:
            notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
            
            for notification_type in notification_types:
                notification_type = notification_type.strip()
                
                if notification_type == 'email' and recipient.email and settings.email_enabled:
                    success = notification_service.send_email(
                        recipient.email,
                        subject,
                        message
                    )
                    if success:
                        success_count += 1
                
                elif notification_type == 'sms' and recipient.phone and settings.sms_enabled:
                    success = notification_service.send_sms(
                        recipient.phone,
                        f"{subject}: {message}"
                    )
                    if success:
                        success_count += 1
        
        logger.info(f"System alert sent: {subject} - {success_count} notifications sent")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Failed to send system alert: {e}")
        return False

def send_email_notification(to_email: str, subject: str, message: str, html_content: str = None):
    """Send email notification"""
    try:
        from models import NotificationSettings
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.email_enabled:
            return False
        
        return notification_service.send_email(to_email, subject, message, html_content)
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False

def send_whatsapp_notification(to_phone: str, message: str):
    """Send WhatsApp notification"""
    try:
        from models import NotificationSettings
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.whatsapp_enabled:
            return False
        
        return notification_service.send_whatsapp(to_phone, message)
    except Exception as e:
        logger.error(f"Failed to send WhatsApp notification: {e}")
        return False

def send_sms_notification(to_phone: str, message: str):
    """Send SMS notification"""
    try:
        from models import NotificationSettings
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.sms_enabled:
            return False
        
        return notification_service.send_sms(to_phone, message)
    except Exception as e:
        logger.error(f"Failed to send SMS notification: {e}")
        return False

def send_email_with_attachment(to_email: str, subject: str, message: str, pdf_bytes: bytes, filename: str):
    """Send email notification with PDF attachment"""
    try:
        from models import NotificationSettings
        import base64
        
        settings = NotificationSettings.query.first()
        if not settings or not settings.email_enabled:
            return False
        
        # Encode PDF as base64 for attachment
        attachment = {
            'content': base64.b64encode(pdf_bytes).decode(),
            'type': 'application/pdf',
            'filename': filename,
            'disposition': 'attachment'
        }
        
        return notification_service.send_email_with_attachment(to_email, subject, message, attachment)
    except Exception as e:
        logger.error(f"Failed to send email with attachment: {e}")
        return False