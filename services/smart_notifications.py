"""
Smart Notification System for Job Work Management
Handles stage-wise notifications, escalations, and vendor communication
"""

from datetime import datetime, timedelta
from app import db
from models import JobWork, Supplier, User
from models.batch import JobWorkBatch, JobWorkProcessWorkflow
from services.notification_helpers import send_email_notification, send_whatsapp_notification
import logging

logger = logging.getLogger(__name__)

class SmartNotificationService:
    """Intelligent notification system for job work workflows"""
    
    @staticmethod
    def send_stage_notification(job_batch_id, notification_type, context_data=None):
        """Send stage-specific notifications to vendors and stakeholders"""
        try:
            job_batch = JobWorkBatch.query.get(job_batch_id)
            if not job_batch:
                return {'success': False, 'error': 'Job work batch not found'}
            
            # Get workflow configuration
            workflow = JobWorkProcessWorkflow.query.filter_by(
                process_name=job_batch.process_name,
                vendor_name=job_batch.current_vendor
            ).first()
            
            if not workflow or not workflow.send_alerts:
                return {'success': True, 'message': 'Notifications disabled for this workflow'}
            
            # Prepare notification context
            notification_context = {
                'job_batch': job_batch,
                'job_work': job_batch.job_work,
                'workflow': workflow,
                'notification_type': notification_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if context_data:
                notification_context.update(context_data)
            
            # Send notifications based on type
            results = []
            
            if notification_type == 'material_received':
                results.append(SmartNotificationService._send_material_received_notification(
                    workflow, notification_context
                ))
            elif notification_type == 'quality_check_required':
                results.append(SmartNotificationService._send_quality_check_notification(
                    workflow, notification_context
                ))
            elif notification_type == 'process_completed':
                results.append(SmartNotificationService._send_process_completed_notification(
                    workflow, notification_context
                ))
            elif notification_type == 'delay_alert':
                results.append(SmartNotificationService._send_delay_alert(
                    workflow, notification_context
                ))
            elif notification_type == 'ready_for_pickup':
                results.append(SmartNotificationService._send_pickup_notification(
                    workflow, notification_context
                ))
            
            # Send WhatsApp notifications if configured
            if workflow.alert_phone and notification_type in ['delay_alert', 'ready_for_pickup']:
                whatsapp_result = SmartNotificationService._send_whatsapp_notification(
                    workflow, notification_context
                )
                results.append(whatsapp_result)
            
            return {
                'success': True,
                'notifications_sent': len([r for r in results if r.get('success', False)]),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error sending stage notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_material_received_notification(workflow, context):
        """Send notification when material is received at vendor"""
        try:
            if not workflow.alert_email:
                return {'success': False, 'reason': 'No email configured'}
            
            return send_email_notification(
                to_email=workflow.alert_email,
                subject=f"Material Received - Job Work {context['job_work'].job_number}",
                template='vendor_material_received',
                context=context
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_quality_check_notification(workflow, context):
        """Send notification for quality check requirement"""
        try:
            if not workflow.alert_email:
                return {'success': False, 'reason': 'No email configured'}
            
            return send_email_notification(
                to_email=workflow.alert_email,
                subject=f"Quality Check Required - Job Work {context['job_work'].job_number}",
                template='quality_check_required',
                context=context
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_process_completed_notification(workflow, context):
        """Send notification when process is completed"""
        try:
            emails_to_notify = []
            
            # Notify vendor
            if workflow.alert_email:
                emails_to_notify.append(workflow.alert_email)
            
            # Notify internal team
            emails_to_notify.append("production@company.com")  # Configure this
            
            results = []
            for email in emails_to_notify:
                result = send_email_notification(
                    to_email=email,
                    subject=f"Process Completed - Job Work {context['job_work'].job_number}",
                    template='process_completed',
                    context=context
                )
                results.append(result)
            
            return {'success': True, 'email_results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_delay_alert(workflow, context):
        """Send delay alert notification"""
        try:
            # Calculate delay information
            job_batch = context['job_batch']
            expected_completion = job_batch.updated_at.date() + timedelta(days=workflow.expected_duration_days)
            current_date = datetime.utcnow().date()
            delay_days = (current_date - expected_completion).days
            
            context.update({
                'expected_completion': expected_completion.isoformat(),
                'delay_days': delay_days,
                'urgency_level': 'HIGH' if delay_days > 5 else 'MEDIUM'
            })
            
            # Send to vendor and internal team
            results = []
            
            if workflow.alert_email:
                result = send_email_notification(
                    to_email=workflow.alert_email,
                    subject=f"URGENT: Delayed Process - Job Work {context['job_work'].job_number}",
                    template='delay_alert_vendor',
                    context=context
                )
                results.append(result)
            
            # Send escalation to internal team
            escalation_result = send_email_notification(
                to_email="manager@company.com",  # Configure this
                subject=f"Process Delay Alert - {context['job_work'].job_number} ({delay_days} days overdue)",
                template='delay_alert_internal',
                context=context
            )
            results.append(escalation_result)
            
            return {'success': True, 'alert_results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_pickup_notification(workflow, context):
        """Send notification when material is ready for pickup"""
        try:
            return send_email_notification(
                to_email="logistics@company.com",  # Configure this
                subject=f"Material Ready for Pickup - Job Work {context['job_work'].job_number}",
                template='ready_for_pickup',
                context=context
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_whatsapp_notification(workflow, context):
        """Send WhatsApp notification for urgent alerts"""
        try:
            if not workflow.alert_phone:
                return {'success': False, 'reason': 'No phone configured'}
            
            # Create WhatsApp message based on notification type
            notification_type = context['notification_type']
            job_number = context['job_work'].job_number
            
            if notification_type == 'delay_alert':
                message = f"🚨 URGENT: Job Work {job_number} is delayed at {workflow.vendor_name}. Please provide status update immediately."
            elif notification_type == 'ready_for_pickup':
                message = f"✅ Job Work {job_number} is completed and ready for pickup from {workflow.vendor_name}."
            else:
                message = f"📋 Update for Job Work {job_number} at {workflow.vendor_name}. Please check your email for details."
            
            return send_whatsapp_notification(
                phone_number=workflow.alert_phone,
                message=message
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def schedule_automatic_notifications():
        """Schedule and send automatic notifications based on workflow status"""
        try:
            current_date = datetime.utcnow().date()
            results = {
                'delay_alerts': 0,
                'reminder_notifications': 0,
                'escalation_alerts': 0,
                'errors': []
            }
            
            # Check for delayed batches
            active_batches = JobWorkBatch.query.filter(
                JobWorkBatch.status.in_(['at_vendor', 'in_transit'])
            ).all()
            
            for batch in active_batches:
                try:
                    workflow = JobWorkProcessWorkflow.query.filter_by(
                        process_name=batch.process_name,
                        vendor_name=batch.current_vendor
                    ).first()
                    
                    if not workflow or not workflow.expected_duration_days:
                        continue
                    
                    # Calculate expected completion and delay
                    expected_completion = batch.updated_at.date() + timedelta(days=workflow.expected_duration_days)
                    days_until_due = (expected_completion - current_date).days
                    
                    # Send reminder 1 day before due date
                    if days_until_due == 1:
                        SmartNotificationService.send_stage_notification(
                            batch.id, 'reminder', {'days_until_due': 1}
                        )
                        results['reminder_notifications'] += 1
                    
                    # Send delay alert for overdue batches
                    elif days_until_due < 0:
                        SmartNotificationService.send_stage_notification(
                            batch.id, 'delay_alert'
                        )
                        results['delay_alerts'] += 1
                        
                        # Send escalation for severely delayed batches
                        if days_until_due < -5:
                            SmartNotificationService._send_escalation_notification(batch)
                            results['escalation_alerts'] += 1
                
                except Exception as e:
                    logger.error(f"Error processing batch {batch.id}: {str(e)}")
                    results['errors'].append(f"Batch {batch.id}: {str(e)}")
            
            return {'success': True, 'results': results}
            
        except Exception as e:
            logger.error(f"Error in automatic notifications: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _send_escalation_notification(batch):
        """Send escalation notification for severely delayed batches"""
        try:
            send_email_notification(
                to_email="ceo@company.com",  # Configure this
                subject=f"CRITICAL: Severely Delayed Job Work - {batch.job_work.job_number}",
                template='critical_delay_escalation',
                context={
                    'batch': batch,
                    'job_work': batch.job_work,
                    'vendor': batch.current_vendor,
                    'delay_days': abs((datetime.utcnow().date() - batch.updated_at.date()).days)
                }
            )
        except Exception as e:
            logger.error(f"Error sending escalation notification: {str(e)}")
    
    @staticmethod
    def create_notification_template(template_name, template_config):
        """Create configurable notification templates"""
        try:
            from models.notifications import NotificationTemplate
            
            template = NotificationTemplate(
                name=template_name,
                template_type=template_config['type'],
                subject_template=template_config['subject'],
                body_template=template_config['body'],
                triggers=template_config.get('triggers', []),
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            db.session.add(template)
            db.session.commit()
            
            return {'success': True, 'template_id': template.id}
            
        except Exception as e:
            logger.error(f"Error creating notification template: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_notification_history(job_work_id, days=30):
        """Get notification history for a job work"""
        try:
            from models.notifications import NotificationLog
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            notifications = NotificationLog.query.filter(
                NotificationLog.reference_type == 'job_work',
                NotificationLog.reference_id == job_work_id,
                NotificationLog.created_at >= start_date
            ).order_by(NotificationLog.created_at.desc()).all()
            
            history = []
            for notification in notifications:
                history.append({
                    'id': notification.id,
                    'type': notification.notification_type,
                    'recipient': notification.recipient_email or notification.recipient_phone,
                    'subject': notification.subject,
                    'status': notification.status,
                    'sent_at': notification.sent_at.isoformat() if notification.sent_at else None,
                    'delivery_status': notification.delivery_status
                })
            
            return {'success': True, 'history': history}
            
        except Exception as e:
            logger.error(f"Error getting notification history: {str(e)}")
            return {'success': False, 'error': str(e)}