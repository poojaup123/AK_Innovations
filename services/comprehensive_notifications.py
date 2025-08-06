"""
Comprehensive notification service for all business workflows
Implements the complete notification specification with all event triggers
"""
from typing import Dict, List, Optional, Any
from services.notifications import notification_service, NotificationTemplates
from services.notification_helpers import send_email_notification, send_whatsapp_notification, send_sms_notification
import logging

logger = logging.getLogger(__name__)

class ComprehensiveNotificationService:
    """Service to handle all business workflow notifications"""
    
    def __init__(self):
        self.templates = NotificationTemplates()
    
    # ===================
    # PURCHASE ORDER NOTIFICATIONS
    # ===================
    
    def notify_po_created(self, purchase_order, vendor_contact_info: Dict[str, str] = None):
        """PO Created → Notify Vendor"""
        try:
            template = self.templates.po_created_vendor(
                purchase_order.po_number,
                purchase_order.supplier.name,
                purchase_order.total_amount,
                len(purchase_order.items)
            )
            
            # Send to vendor if contact info provided
            if vendor_contact_info:
                if vendor_contact_info.get('email'):
                    send_email_notification(
                        vendor_contact_info['email'],
                        template['subject'],
                        template['message'],
                        template['html']
                    )
                
                if vendor_contact_info.get('phone'):
                    send_whatsapp_notification(
                        vendor_contact_info['phone'],
                        template['message']
                    )
            
            # Send to internal purchase team
            self._send_to_role_recipients('purchase_team', template)
            
            logger.info(f"PO created notification sent for {purchase_order.po_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send PO created notification: {e}")
            return False
    
    def notify_po_approved(self, purchase_order, approver_name: str):
        """PO Approved → Notify Internal Purchase Head"""
        try:
            template = self.templates.po_approved_internal(
                purchase_order.po_number,
                purchase_order.supplier.name,
                approver_name
            )
            
            self._send_to_role_recipients('purchase_head', template)
            
            logger.info(f"PO approved notification sent for {purchase_order.po_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send PO approved notification: {e}")
            return False
    
    def notify_po_partially_fulfilled(self, purchase_order, completed_items: int):
        """PO Partially Fulfilled → Notify Buyer/Store"""
        try:
            template = self.templates.po_partially_fulfilled(
                purchase_order.po_number,
                completed_items,
                len(purchase_order.items)
            )
            
            self._send_to_role_recipients('buyer', template)
            self._send_to_role_recipients('store', template)
            
            logger.info(f"PO partial fulfillment notification sent for {purchase_order.po_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send PO partial fulfillment notification: {e}")
            return False
    
    # ===================
    # GRN NOTIFICATIONS
    # ===================
    
    def notify_grn_created(self, grn):
        """GRN Created → Notify Internal Accounts"""
        try:
            template = self.templates.grn_created_accounts(
                grn.grn_number,
                grn.supplier.name,
                grn.total_amount
            )
            
            self._send_to_role_recipients('accounts', template)
            
            logger.info(f"GRN created notification sent for {grn.grn_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send GRN created notification: {e}")
            return False
    
    def notify_material_rejected(self, grn, item_name: str, rejected_qty: float, reason: str):
        """Material Rejected → Notify Vendor + QC Head"""
        try:
            template = self.templates.material_rejected(
                grn.grn_number,
                item_name,
                rejected_qty,
                reason
            )
            
            # Send to vendor
            if hasattr(grn.supplier, 'email') and grn.supplier.email:
                send_email_notification(
                    grn.supplier.email,
                    template['subject'],
                    template['message'],
                    template['html']
                )
            
            if hasattr(grn.supplier, 'phone') and grn.supplier.phone:
                send_whatsapp_notification(
                    grn.supplier.phone,
                    template['message']
                )
            
            # Send to QC head
            self._send_to_role_recipients('qc_head', template)
            
            logger.info(f"Material rejection notification sent for {grn.grn_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send material rejection notification: {e}")
            return False
    
    # ===================
    # JOB WORK NOTIFICATIONS
    # ===================
    
    def notify_job_work_issued(self, job_work, vendor_contact_info: Dict[str, str] = None):
        """Job Work Issued → Notify Job Work Vendor"""
        try:
            template = self.templates.job_work_issued(
                job_work.job_work_number,
                job_work.vendor.name,
                job_work.item.name,
                job_work.quantity
            )
            
            # Send to vendor
            if vendor_contact_info:
                if vendor_contact_info.get('email'):
                    send_email_notification(
                        vendor_contact_info['email'],
                        template['subject'],
                        template['message'],
                        template['html']
                    )
                
                if vendor_contact_info.get('phone'):
                    send_whatsapp_notification(
                        vendor_contact_info['phone'],
                        template['message']
                    )
            
            logger.info(f"Job work issued notification sent for {job_work.job_work_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send job work issued notification: {e}")
            return False
    
    def notify_job_work_delayed(self, job_work, days_delayed: int):
        """Job Work Delayed → Notify Internal Production Head"""
        try:
            template = self.templates.job_work_delayed(
                job_work.job_work_number,
                job_work.vendor.name,
                days_delayed
            )
            
            self._send_to_role_recipients('production_head', template)
            
            logger.info(f"Job work delayed notification sent for {job_work.job_work_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send job work delayed notification: {e}")
            return False
    
    def notify_job_work_received(self, job_work):
        """Job Work Output Received → Notify Store & Accounts"""
        try:
            template = self.templates.job_work_received(
                job_work.job_work_number,
                job_work.item.name,
                job_work.quantity
            )
            
            self._send_to_role_recipients('store', template)
            self._send_to_role_recipients('accounts', template)
            
            logger.info(f"Job work received notification sent for {job_work.job_work_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send job work received notification: {e}")
            return False
    
    # ===================
    # PRODUCTION NOTIFICATIONS
    # ===================
    
    def notify_production_order_created(self, production_order):
        """Production Order Created → Notify Production Supervisor"""
        try:
            from services.notifications import NotificationTemplates
            template = NotificationTemplates.production_complete(
                production_order.production_number,
                production_order.item.name,
                production_order.target_quantity
            )
            template['subject'] = f'🏭 Production Order #{production_order.production_number} Created'
            template['message'] = f'New production order #{production_order.production_number} for {production_order.target_quantity} units of {production_order.item.name}. Please start operations.'
            
            self._send_to_role_recipients('production_supervisor', template)
            
            logger.info(f"Production order created notification sent for {production_order.production_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send production order created notification: {e}")
            return False
    
    def notify_raw_material_shortage(self, item_name: str, required_qty: float, available_qty: float):
        """Raw Material Shortage → Notify Store/Purchase Team"""
        try:
            template = {
                'subject': f'🚨 Raw Material Shortage - {item_name}',
                'message': f'Raw material shortage for {item_name}. Required: {required_qty}, Available: {available_qty}. Immediate action needed.',
                'html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #dc3545;">🚨 Raw Material Shortage</h2>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h3>{item_name}</h3>
                        <p><strong>Required:</strong> {required_qty}</p>
                        <p><strong>Available:</strong> {available_qty}</p>
                        <p><strong>Action:</strong> Immediate purchase/issue needed</p>
                    </div>
                    <p>Please arrange material immediately.</p>
                    <p>Best regards,<br>AK Innovations Production System</p>
                </div>
                '''
            }
            
            self._send_to_role_recipients('store', template)
            self._send_to_role_recipients('purchase_team', template)
            
            logger.info(f"Raw material shortage notification sent for {item_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send raw material shortage notification: {e}")
            return False
    
    def notify_production_completed(self, production_order):
        """Production Completed → Notify QC, Store, Accounts"""
        try:
            from services.notifications import NotificationTemplates
            template = NotificationTemplates.production_complete(
                production_order.production_number,
                production_order.item.name,
                production_order.completed_quantity
            )
            
            self._send_to_role_recipients('qc', template)
            self._send_to_role_recipients('store', template)
            self._send_to_role_recipients('accounts', template)
            
            logger.info(f"Production completed notification sent for {production_order.production_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send production completed notification: {e}")
            return False
    
    # ===================
    # SALES ORDER NOTIFICATIONS
    # ===================
    
    def notify_so_created(self, sales_order):
        """SO Created → Notify Internal Sales Team"""
        try:
            template = self.templates.so_created_internal(
                sales_order.so_number,
                sales_order.customer.name,
                sales_order.total_amount
            )
            
            self._send_to_role_recipients('sales_team', template)
            
            logger.info(f"SO created notification sent for {sales_order.so_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SO created notification: {e}")
            return False
    
    def notify_material_ready_dispatch(self, sales_order, items_ready: int):
        """Material Ready to Dispatch → Notify Logistics/Customer"""
        try:
            template = self.templates.material_ready_dispatch(
                sales_order.so_number,
                sales_order.customer.name,
                items_ready
            )
            
            # Send to logistics
            self._send_to_role_recipients('logistics', template)
            
            # Send to customer if contact info available
            if hasattr(sales_order.customer, 'email') and sales_order.customer.email:
                send_email_notification(
                    sales_order.customer.email,
                    template['subject'],
                    template['message'],
                    template['html']
                )
            
            logger.info(f"Material ready for dispatch notification sent for {sales_order.so_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send material ready notification: {e}")
            return False
    
    def notify_invoice_generated(self, sales_order, invoice_number: str):
        """Invoice Generated → Notify Customer"""
        try:
            template = self.templates.invoice_generated_customer(
                invoice_number,
                sales_order.customer.name,
                sales_order.total_amount
            )
            
            # Send to customer
            if hasattr(sales_order.customer, 'email') and sales_order.customer.email:
                send_email_notification(
                    sales_order.customer.email,
                    template['subject'],
                    template['message'],
                    template['html']
                )
            
            logger.info(f"Invoice generated notification sent for {invoice_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send invoice generated notification: {e}")
            return False
    
    def notify_payment_overdue(self, customer, invoice_number: str, overdue_days: int, amount: float):
        """Payment Overdue → Notify Customer, Sales"""
        try:
            template = self.templates.payment_overdue(
                customer.name,
                invoice_number,
                overdue_days,
                amount
            )
            
            # Send to customer
            if hasattr(customer, 'email') and customer.email:
                send_email_notification(
                    customer.email,
                    template['subject'],
                    template['message'],
                    template['html']
                )
            
            # Send to sales team
            self._send_to_role_recipients('sales_team', template)
            
            logger.info(f"Payment overdue notification sent for {invoice_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payment overdue notification: {e}")
            return False
    
    # ===================
    # ACCOUNTS NOTIFICATIONS
    # ===================
    
    def notify_vendor_payment_due(self, vendor, amount: float, due_date: str):
        """Vendor Payment Due → Notify Accounts Payable Team"""
        try:
            template = self.templates.vendor_payment_due(
                vendor.name,
                amount,
                due_date
            )
            
            self._send_to_role_recipients('accounts_payable', template)
            
            logger.info(f"Vendor payment due notification sent for {vendor.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send vendor payment due notification: {e}")
            return False
    
    def notify_customer_payment_received(self, customer, amount: float, reference: str):
        """Customer Payment Received → Notify Sales + Accounts"""
        try:
            template = self.templates.customer_payment_received(
                customer.name,
                amount,
                reference
            )
            
            self._send_to_role_recipients('sales_team', template)
            self._send_to_role_recipients('accounts', template)
            
            logger.info(f"Customer payment received notification sent for {customer.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send customer payment received notification: {e}")
            return False
    
    def notify_journal_voucher_posted(self, voucher_number: str, amount: float, narration: str):
        """Journal Voucher Auto-posted → Notify Internal Accountant"""
        try:
            template = self.templates.journal_voucher_posted(
                voucher_number,
                amount,
                narration
            )
            
            self._send_to_role_recipients('accountant', template)
            
            logger.info(f"Journal voucher posted notification sent for {voucher_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send journal voucher posted notification: {e}")
            return False
    
    # ===================
    # INVENTORY NOTIFICATIONS
    # ===================
    
    def notify_scrap_threshold_exceeded(self, item_name: str, scrap_qty: float, threshold: float):
        """Scrap Exceeds Threshold → Notify Production/QA Head"""
        try:
            template = self.templates.scrap_threshold_exceeded(
                item_name,
                scrap_qty,
                threshold
            )
            
            self._send_to_role_recipients('production_head', template)
            self._send_to_role_recipients('qa_head', template)
            
            logger.info(f"Scrap threshold exceeded notification sent for {item_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send scrap threshold notification: {e}")
            return False
    
    def notify_transfer_complete(self, from_location: str, to_location: str, items_count: int):
        """Transfer Complete → Notify Destination Location"""
        try:
            template = self.templates.transfer_complete(
                from_location,
                to_location,
                items_count
            )
            
            self._send_to_role_recipients('store', template)
            
            logger.info(f"Transfer complete notification sent: {from_location} → {to_location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send transfer complete notification: {e}")
            return False
    
    # ===================
    # HELPER METHODS
    # ===================
    
    def _send_to_role_recipients(self, role: str, template: Dict[str, str]):
        """Send notification to all recipients with specified role"""
        try:
            from models import NotificationRecipient, NotificationSettings
            
            settings = NotificationSettings.query.first()
            if not settings:
                return False
            
            recipients = NotificationRecipient.query.filter(
                NotificationRecipient.is_active == True,
                NotificationRecipient.event_types.contains(role)
            ).all()
            
            for recipient in recipients:
                notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
                
                for notification_type in notification_types:
                    notification_type = notification_type.strip()
                    
                    if notification_type == 'email' and recipient.email and settings.email_enabled:
                        send_email_notification(
                            recipient.email,
                            template['subject'],
                            template['message'],
                            template.get('html')
                        )
                    
                    elif notification_type == 'sms' and recipient.phone and settings.sms_enabled:
                        send_sms_notification(
                            recipient.phone,
                            template['message']
                        )
                    
                    elif notification_type == 'whatsapp' and recipient.phone and settings.whatsapp_enabled:
                        send_whatsapp_notification(
                            recipient.phone,
                            template['message']
                        )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification to role {role}: {e}")
            return False
    
    def get_notification_settings(self):
        """Get current notification settings"""
        try:
            from models import NotificationSettings
            return NotificationSettings.query.first()
        except Exception as e:
            logger.error(f"Failed to get notification settings: {e}")
            return None

# Global instance
comprehensive_notification_service = ComprehensiveNotificationService()