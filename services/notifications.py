import os
import logging
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app import db

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"

class NotificationService:
    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize API clients if credentials are available"""
        try:
            sendgrid_key = os.environ.get('SENDGRID_API_KEY')
            if sendgrid_key:
                self.sendgrid_client = SendGridAPIClient(sendgrid_key)
                
            twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
            if twilio_sid and twilio_token:
                self.twilio_client = Client(twilio_sid, twilio_token)
        except Exception as e:
            logger.error(f"Error initializing notification clients: {e}")
    
    def send_email(self, to_email: str, subject: str, content: str, html_content: str = None) -> bool:
        """Send email notification"""
        if not self.sendgrid_client:
            logger.warning("SendGrid client not initialized - check SENDGRID_API_KEY")
            return False
        
        try:
            from_email = Email("noreply@akfactory.com", "AK Innovations Factory")
            to_email_obj = To(to_email)
            
            message = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
                plain_text_content=content,
                html_content=html_content or content
            )
            
            response = self.sendgrid_client.send(message)
            success = response.status_code in [200, 201, 202]
            
            self._log_notification(NotificationType.EMAIL, to_email, subject, success, response.status_code)
            return success
            
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            self._log_notification(NotificationType.EMAIL, to_email, subject, False, str(e))
            return False
    
    def send_email_with_attachment(self, to_email: str, subject: str, content: str, attachment: dict, html_content: str = None) -> bool:
        """Send email notification with attachment"""
        if not self.sendgrid_client:
            logger.warning("SendGrid client not initialized - check SENDGRID_API_KEY")
            return False
        
        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment
            import base64
            
            from_email = Email("noreply@akfactory.com", "AK Innovations Factory")
            to_email_obj = To(to_email)
            
            message = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
                plain_text_content=content,
                html_content=html_content or content
            )
            
            # Add attachment
            attached_file = Attachment()
            attached_file.content = attachment['content']
            attached_file.type = attachment['type']
            attached_file.filename = attachment['filename']
            attached_file.disposition = attachment['disposition']
            message.attachment = attached_file
            
            response = self.sendgrid_client.send(message)
            success = response.status_code in [200, 201, 202]
            
            self._log_notification(NotificationType.EMAIL, to_email, f"{subject} (with attachment)", success, response.status_code)
            return success
            
        except Exception as e:
            logger.error(f"Email with attachment sending failed: {e}")
            self._log_notification(NotificationType.EMAIL, to_email, f"{subject} (with attachment)", False, str(e))
            return False
    
    def send_sms(self, to_phone: str, message: str) -> bool:
        """Send SMS notification"""
        if not self.twilio_client:
            logger.warning("Twilio client not initialized - check credentials")
            return False
        
        try:
            from_phone = os.environ.get('TWILIO_PHONE_NUMBER')
            if not from_phone:
                logger.error("TWILIO_PHONE_NUMBER not configured")
                return False
            
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=from_phone,
                to=to_phone
            )
            
            success = message_obj.status in ['queued', 'sent', 'delivered']
            self._log_notification(NotificationType.SMS, to_phone, message[:50] + "...", success, message_obj.sid)
            return success
            
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            self._log_notification(NotificationType.SMS, to_phone, message[:50] + "...", False, str(e))
            return False
    
    def send_whatsapp(self, to_phone: str, message: str) -> bool:
        """Send WhatsApp notification via Twilio"""
        if not self.twilio_client:
            logger.warning("Twilio client not initialized - check credentials")
            return False
        
        try:
            from_phone = os.environ.get('TWILIO_PHONE_NUMBER')
            if not from_phone:
                logger.error("TWILIO_PHONE_NUMBER not configured")
                return False
            
            # WhatsApp requires 'whatsapp:' prefix
            whatsapp_from = f"whatsapp:{from_phone}"
            whatsapp_to = f"whatsapp:{to_phone}"
            
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=whatsapp_from,
                to=whatsapp_to
            )
            
            success = message_obj.status in ['queued', 'sent', 'delivered']
            self._log_notification(NotificationType.WHATSAPP, to_phone, message[:50] + "...", success, message_obj.sid)
            return success
            
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
            self._log_notification(NotificationType.WHATSAPP, to_phone, message[:50] + "...", False, str(e))
            return False
    
    def send_notification(self, notification_type: NotificationType, recipient: str, 
                         subject: str, message: str, html_content: str = None) -> bool:
        """Send notification based on type"""
        if notification_type == NotificationType.EMAIL:
            return self.send_email(recipient, subject, message, html_content)
        elif notification_type == NotificationType.SMS:
            return self.send_sms(recipient, message)
        elif notification_type == NotificationType.WHATSAPP:
            return self.send_whatsapp(recipient, message)
        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return False
    
    def send_multi_channel_notification(self, recipients: Dict[str, List[str]], 
                                      subject: str, message: str, html_content: str = None) -> Dict[str, bool]:
        """Send notification to multiple channels"""
        results = {}
        
        for channel, recipient_list in recipients.items():
            channel_results = []
            notification_type = NotificationType(channel)
            
            for recipient in recipient_list:
                success = self.send_notification(notification_type, recipient, subject, message, html_content)
                channel_results.append(success)
            
            results[channel] = all(channel_results)
        
        return results
    
    def _log_notification(self, notification_type: NotificationType, recipient: str, 
                         subject: str, success: bool, response: str):
        """Log notification attempt to database"""
        try:
            from models.notifications import NotificationLog
            log_entry = NotificationLog(
                type=notification_type.value,
                recipient=recipient,
                subject=subject,
                success=success,
                response=str(response),
                sent_at=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    def get_notification_settings(self):
        """Get current notification settings"""
        try:
            from models import NotificationSettings
            return NotificationSettings.query.first()
        except Exception as e:
            logger.error(f"Failed to get notification settings: {e}")
            return None
    
    def update_notification_settings(self, settings_data: Dict[str, Any]) -> bool:
        """Update notification settings"""
        try:
            from models import NotificationSettings
            settings = NotificationSettings.query.first()
            if not settings:
                settings = NotificationSettings()
            
            for key, value in settings_data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            db.session.merge(settings)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update notification settings: {e}")
            return False

# Global notification service instance
notification_service = NotificationService()

# Notification templates for different events
class NotificationTemplates:
    @staticmethod
    def low_stock_alert(item_name: str, current_stock: int, minimum_stock: int) -> Dict[str, str]:
        return {
            'subject': f'🚨 Low Stock Alert: {item_name}',
            'message': f'Low stock alert for {item_name}. Current stock: {current_stock}, Minimum required: {minimum_stock}. Please reorder immediately.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">🚨 Low Stock Alert</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>{item_name}</h3>
                    <p><strong>Current Stock:</strong> {current_stock}</p>
                    <p><strong>Minimum Required:</strong> {minimum_stock}</p>
                    <p style="color: #dc3545;"><strong>Action Required:</strong> Please reorder immediately</p>
                </div>
                <p>Best regards,<br>AK Innovations Factory Management System</p>
            </div>
            '''
        }
    
    @staticmethod
    def order_status_update(order_type: str, order_id: str, status: str) -> Dict[str, str]:
        return {
            'subject': f'📋 {order_type} Order #{order_id} - Status Update',
            'message': f'Your {order_type} order #{order_id} status has been updated to: {status}',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">📋 Order Status Update</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>{order_type} Order #{order_id}</h3>
                    <p><strong>New Status:</strong> <span style="color: #28a745;">{status}</span></p>
                </div>
                <p>Best regards,<br>AK Innovations Factory Management System</p>
            </div>
            '''
        }
    
    @staticmethod
    def production_complete(production_id: str, item_name: str, quantity: int) -> Dict[str, str]:
        return {
            'subject': f'✅ Production Complete: {item_name}',
            'message': f'Production #{production_id} completed successfully. {quantity} units of {item_name} have been produced.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">✅ Production Complete</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Production #{production_id}</h3>
                    <p><strong>Item:</strong> {item_name}</p>
                    <p><strong>Quantity Produced:</strong> {quantity} units</p>
                </div>
                <p>Best regards,<br>AK Innovations Factory Management System</p>
            </div>
            '''
        }
    
    # PURCHASE ORDER TEMPLATES
    @staticmethod
    def po_created_vendor(po_number: str, vendor_name: str, total_amount: float, items_count: int) -> Dict[str, str]:
        return {
            'subject': f'🛒 Purchase Order #{po_number} - AK Innovations',
            'message': f'Dear {vendor_name}, We have issued Purchase Order #{po_number} for {items_count} items worth ₹{total_amount:,.2f}. Please confirm receipt and delivery schedule.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #007bff;">🛒 Purchase Order Issued</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>PO #{po_number}</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Items:</strong> {items_count}</p>
                    <p><strong>Total Amount:</strong> ₹{total_amount:,.2f}</p>
                </div>
                <p>Please confirm receipt and provide delivery schedule.</p>
                <p>Best regards,<br>AK Innovations Procurement Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def po_approved_internal(po_number: str, vendor_name: str, approver_name: str) -> Dict[str, str]:
        return {
            'subject': f'✅ PO #{po_number} Approved by {approver_name}',
            'message': f'Purchase Order #{po_number} for {vendor_name} has been approved by {approver_name}. Proceeding with procurement.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">✅ Purchase Order Approved</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>PO #{po_number}</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Approved by:</strong> {approver_name}</p>
                </div>
                <p>Procurement can proceed as planned.</p>
                <p>Best regards,<br>AK Innovations Purchase Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def po_partially_fulfilled(po_number: str, completed_items: int, total_items: int) -> Dict[str, str]:
        return {
            'subject': f'⚠️ PO #{po_number} Partially Fulfilled',
            'message': f'Purchase Order #{po_number} is partially complete. {completed_items}/{total_items} items received. Follow up on pending deliveries.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #ffc107;">⚠️ Partial Fulfillment Alert</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>PO #{po_number}</h3>
                    <p><strong>Completed:</strong> {completed_items}/{total_items} items</p>
                    <p><strong>Status:</strong> Pending follow up</p>
                </div>
                <p>Please follow up on remaining deliveries.</p>
                <p>Best regards,<br>AK Innovations Store Team</p>
            </div>
            '''
        }
    
    # GRN TEMPLATES
    @staticmethod
    def grn_created_accounts(grn_number: str, vendor_name: str, total_amount: float) -> Dict[str, str]:
        return {
            'subject': f'📦 GRN #{grn_number} Created - Update Required',
            'message': f'GRN #{grn_number} from {vendor_name} (₹{total_amount:,.2f}) has been created. Please update accounting records.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #007bff;">📦 GRN Created</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>GRN #{grn_number}</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Amount:</strong> ₹{total_amount:,.2f}</p>
                    <p><strong>Action:</strong> Update accounting records</p>
                </div>
                <p>Best regards,<br>AK Innovations Store Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def material_rejected(grn_number: str, item_name: str, rejected_qty: float, reason: str) -> Dict[str, str]:
        return {
            'subject': f'❌ Material Rejected - GRN #{grn_number}',
            'message': f'Material rejected in GRN #{grn_number}. Item: {item_name}, Qty: {rejected_qty}, Reason: {reason}. Replacement required.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">❌ Material Rejection Notice</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>GRN #{grn_number}</h3>
                    <p><strong>Item:</strong> {item_name}</p>
                    <p><strong>Rejected Qty:</strong> {rejected_qty}</p>
                    <p><strong>Reason:</strong> {reason}</p>
                </div>
                <p>Please arrange replacement material.</p>
                <p>Best regards,<br>AK Innovations QC Team</p>
            </div>
            '''
        }
    
    # JOB WORK TEMPLATES
    @staticmethod
    def job_work_issued(jw_number: str, vendor_name: str, item_name: str, quantity: float) -> Dict[str, str]:
        return {
            'subject': f'🔧 Job Work #{jw_number} Dispatched to {vendor_name}',
            'message': f'Job Work #{jw_number} has been dispatched. Item: {item_name}, Qty: {quantity}. Please confirm receipt.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #fd7e14;">🔧 Job Work Dispatched</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Job Work #{jw_number}</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Item:</strong> {item_name}</p>
                    <p><strong>Quantity:</strong> {quantity}</p>
                </div>
                <p>Please confirm receipt and provide expected completion date.</p>
                <p>Best regards,<br>AK Innovations Production Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def job_work_delayed(jw_number: str, vendor_name: str, days_delayed: int) -> Dict[str, str]:
        return {
            'subject': f'⚠️ Job Work #{jw_number} Delayed - Follow Up Required',
            'message': f'Job Work #{jw_number} from {vendor_name} is delayed by {days_delayed} days. Immediate follow up required.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #ffc107;">⚠️ Job Work Delayed</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Job Work #{jw_number}</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Delayed by:</strong> {days_delayed} days</p>
                    <p><strong>Action:</strong> Immediate follow up required</p>
                </div>
                <p>Please contact vendor immediately.</p>
                <p>Best regards,<br>AK Innovations Production Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def job_work_received(jw_number: str, item_name: str, quantity: float) -> Dict[str, str]:
        return {
            'subject': f'✅ Job Work #{jw_number} Output Received',
            'message': f'Job Work #{jw_number} output received. Item: {item_name}, Qty: {quantity}. Update inventory and accounting.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">✅ Job Work Output Received</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Job Work #{jw_number}</h3>
                    <p><strong>Item:</strong> {item_name}</p>
                    <p><strong>Quantity:</strong> {quantity}</p>
                    <p><strong>Action:</strong> Update inventory and accounting</p>
                </div>
                <p>Best regards,<br>AK Innovations Store Team</p>
            </div>
            '''
        }
    
    # SALES ORDER TEMPLATES
    @staticmethod
    def so_created_internal(so_number: str, customer_name: str, total_amount: float) -> Dict[str, str]:
        return {
            'subject': f'🛍️ Sales Order #{so_number} Created',
            'message': f'New Sales Order #{so_number} from {customer_name} for ₹{total_amount:,.2f}. Please confirm booking.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">🛍️ New Sales Order</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>SO #{so_number}</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Amount:</strong> ₹{total_amount:,.2f}</p>
                    <p><strong>Status:</strong> Booking confirmed</p>
                </div>
                <p>Best regards,<br>AK Innovations Sales Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def material_ready_dispatch(so_number: str, customer_name: str, items_ready: int) -> Dict[str, str]:
        return {
            'subject': f'🚚 SO #{so_number} Ready for Dispatch',
            'message': f'Sales Order #{so_number} for {customer_name} is ready for dispatch. {items_ready} items prepared.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #17a2b8;">🚚 Ready for Dispatch</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>SO #{so_number}</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Items Ready:</strong> {items_ready}</p>
                    <p><strong>Status:</strong> Awaiting dispatch coordination</p>
                </div>
                <p>Please coordinate dispatch schedule.</p>
                <p>Best regards,<br>AK Innovations Logistics Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def invoice_generated_customer(invoice_number: str, customer_name: str, total_amount: float) -> Dict[str, str]:
        return {
            'subject': f'📋 Invoice #{invoice_number} - AK Innovations',
            'message': f'Dear {customer_name}, Your invoice #{invoice_number} for ₹{total_amount:,.2f} has been generated. Please find attached.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #007bff;">📋 Invoice Generated</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Invoice #{invoice_number}</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Amount:</strong> ₹{total_amount:,.2f}</p>
                    <p><strong>Due Date:</strong> As per terms</p>
                </div>
                <p>Payment as per agreed terms and conditions.</p>
                <p>Best regards,<br>AK Innovations Accounts Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def payment_overdue(customer_name: str, invoice_number: str, overdue_days: int, amount: float) -> Dict[str, str]:
        return {
            'subject': f'🔔 Payment Overdue - Invoice #{invoice_number}',
            'message': f'Dear {customer_name}, Payment for Invoice #{invoice_number} (₹{amount:,.2f}) is overdue by {overdue_days} days. Please arrange payment.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">🔔 Payment Overdue Notice</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Invoice #{invoice_number}</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Amount:</strong> ₹{amount:,.2f}</p>
                    <p><strong>Overdue by:</strong> {overdue_days} days</p>
                </div>
                <p>Please arrange immediate payment to avoid service interruption.</p>
                <p>Best regards,<br>AK Innovations Accounts Team</p>
            </div>
            '''
        }
    
    # ACCOUNTS TEMPLATES
    @staticmethod
    def vendor_payment_due(vendor_name: str, amount: float, due_date: str) -> Dict[str, str]:
        return {
            'subject': f'💰 Payment Due to {vendor_name} - ₹{amount:,.2f}',
            'message': f'Payment of ₹{amount:,.2f} to {vendor_name} is due on {due_date}. Please process payment.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #ffc107;">💰 Payment Due Notice</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Payment Due</h3>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                    <p><strong>Amount:</strong> ₹{amount:,.2f}</p>
                    <p><strong>Due Date:</strong> {due_date}</p>
                </div>
                <p>Please process payment to maintain good vendor relations.</p>
                <p>Best regards,<br>AK Innovations Accounts Payable</p>
            </div>
            '''
        }
    
    @staticmethod
    def customer_payment_received(customer_name: str, amount: float, reference: str) -> Dict[str, str]:
        return {
            'subject': f'✅ Payment Received from {customer_name}',
            'message': f'Payment of ₹{amount:,.2f} received from {customer_name}. Reference: {reference}',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">✅ Payment Received</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Payment Confirmation</h3>
                    <p><strong>Customer:</strong> {customer_name}</p>
                    <p><strong>Amount:</strong> ₹{amount:,.2f}</p>
                    <p><strong>Reference:</strong> {reference}</p>
                </div>
                <p>Payment successfully recorded in accounts.</p>
                <p>Best regards,<br>AK Innovations Accounts Receivable</p>
            </div>
            '''
        }
    
    @staticmethod
    def journal_voucher_posted(voucher_number: str, amount: float, narration: str) -> Dict[str, str]:
        return {
            'subject': f'📊 Journal Voucher #{voucher_number} Auto-Posted',
            'message': f'Journal Voucher #{voucher_number} (₹{amount:,.2f}) has been auto-posted. Narration: {narration}',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #6f42c1;">📊 Journal Voucher Posted</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Voucher #{voucher_number}</h3>
                    <p><strong>Amount:</strong> ₹{amount:,.2f}</p>
                    <p><strong>Narration:</strong> {narration}</p>
                    <p><strong>Status:</strong> Auto-posted</p>
                </div>
                <p>Please review for audit trail.</p>
                <p>Best regards,<br>AK Innovations Accounting System</p>
            </div>
            '''
        }
    
    # INVENTORY TEMPLATES
    @staticmethod
    def scrap_threshold_exceeded(item_name: str, scrap_qty: float, threshold: float) -> Dict[str, str]:
        return {
            'subject': f'⚠️ Scrap Threshold Exceeded - {item_name}',
            'message': f'Scrap quantity for {item_name} ({scrap_qty}) has exceeded threshold ({threshold}). Quality investigation required.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">⚠️ Scrap Threshold Alert</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>{item_name}</h3>
                    <p><strong>Scrap Quantity:</strong> {scrap_qty}</p>
                    <p><strong>Threshold:</strong> {threshold}</p>
                    <p><strong>Action:</strong> Quality investigation required</p>
                </div>
                <p>Please investigate quality issues immediately.</p>
                <p>Best regards,<br>AK Innovations Quality Team</p>
            </div>
            '''
        }
    
    @staticmethod
    def transfer_complete(from_location: str, to_location: str, items_count: int) -> Dict[str, str]:
        return {
            'subject': f'📦 Transfer Complete: {from_location} → {to_location}',
            'message': f'Stock transfer from {from_location} to {to_location} completed. {items_count} items transferred.',
            'html': f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #17a2b8;">📦 Transfer Complete</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>Stock Transfer</h3>
                    <p><strong>From:</strong> {from_location}</p>
                    <p><strong>To:</strong> {to_location}</p>
                    <p><strong>Items:</strong> {items_count}</p>
                </div>
                <p>Please acknowledge receipt at destination.</p>
                <p>Best regards,<br>AK Innovations Store Team</p>
            </div>
            '''
        }