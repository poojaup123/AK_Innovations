"""
Advanced Workflow Automation Service
Handles multi-vendor sequential processing, auto-forwarding, and smart notifications
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app import db
from models.batch import JobWorkBatch, JobWorkLocationHistory, JobWorkProcessWorkflow
from models import JobWork, Supplier, User
from services.notification_helpers import send_email_notification, send_whatsapp_notification
# from services.partial_job_service import PartialJobService  # Import removed to avoid circular dependency
import logging

logger = logging.getLogger(__name__)

class WorkflowAutomationService:
    """Advanced workflow automation for multi-vendor processing"""
    
    @staticmethod
    def create_multi_vendor_workflow(job_work_id, vendor_chain, auto_forward_settings=None):
        """Create a multi-vendor sequential workflow"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            workflow_records = []
            
            for sequence, vendor_config in enumerate(vendor_chain, 1):
                workflow = JobWorkProcessWorkflow(
                    workflow_name=f"JW-{job_work.job_number}-{vendor_config['process']}",
                    item_id=job_work.item_id,
                    sequence_number=sequence,
                    process_name=vendor_config['process'],
                    vendor_name=vendor_config['vendor_name'],
                    department_name=vendor_config.get('department'),
                    auto_forward_enabled=vendor_config.get('auto_forward', False),
                    requires_quality_check=vendor_config.get('quality_check', True),
                    expected_duration_days=vendor_config.get('duration_days', 3),
                    send_alerts=vendor_config.get('send_alerts', True),
                    alert_email=vendor_config.get('alert_email'),
                    alert_phone=vendor_config.get('alert_phone')
                )
                
                db.session.add(workflow)
                workflow_records.append(workflow)
            
            db.session.flush()
            
            # Create initial job work batches for first vendor
            first_vendor = vendor_chain[0]
            initial_batch_result = WorkflowAutomationService._create_initial_batch(
                job_work, first_vendor, workflow_records[0].id
            )
            
            if not initial_batch_result['success']:
                db.session.rollback()
                return initial_batch_result
            
            db.session.commit()
            
            # Send initial notifications
            WorkflowAutomationService._send_workflow_start_notifications(
                job_work, first_vendor, initial_batch_result['batch']
            )
            
            return {
                'success': True,
                'workflow_records': [w.id for w in workflow_records],
                'initial_batch': initial_batch_result['batch'],
                'message': f'Multi-vendor workflow created with {len(vendor_chain)} stages'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating multi-vendor workflow: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _create_initial_batch(job_work, vendor_config, workflow_id):
        """Create initial job work batch for first vendor"""
        try:
            from models.batch import InventoryBatch
            
            # Find suitable input batch
            input_batch = InventoryBatch.query.filter(
                InventoryBatch.item_id == job_work.item_id,
                InventoryBatch.available_quantity >= job_work.quantity_sent
            ).order_by(InventoryBatch.mfg_date.asc()).first()
            
            if not input_batch:
                return {'success': False, 'error': 'No suitable input batch found'}
            
            # Create job work batch
            job_batch = JobWorkBatch(
                job_work_id=job_work.id,
                input_batch_id=input_batch.id,
                input_item_id=job_work.item_id,
                quantity_issued=job_work.quantity_sent,
                process_name=vendor_config['process'],
                vendor_name=vendor_config['vendor_name'],
                current_location='issued',
                current_vendor=vendor_config['vendor_name'],
                process_sequence=1,
                is_auto_forward_enabled=vendor_config.get('auto_forward', False),
                status='issued'
            )
            
            db.session.add(job_batch)
            db.session.flush()
            
            # Update input batch quantities
            input_batch.move_quantity(
                job_work.quantity_sent, 
                'raw', 
                'wip',
                ref_type='job_work',
                ref_id=job_work.id,
                notes=f"Issued for job work {job_work.job_number}"
            )
            
            return {'success': True, 'batch': job_batch}
            
        except Exception as e:
            logger.error(f"Error creating initial batch: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def auto_forward_to_next_vendor(job_batch_id, quality_status='passed'):
        """Automatically forward material to next vendor in sequence"""
        try:
            job_batch = JobWorkBatch.query.get(job_batch_id)
            if not job_batch:
                return {'success': False, 'error': 'Job work batch not found'}
            
            if not job_batch.is_auto_forward_enabled:
                return {'success': False, 'error': 'Auto-forwarding not enabled for this batch'}
            
            # Find next workflow step
            next_workflow = JobWorkProcessWorkflow.query.filter(
                JobWorkProcessWorkflow.item_id == job_batch.input_item_id,
                JobWorkProcessWorkflow.sequence_number == job_batch.process_sequence + 1,
                JobWorkProcessWorkflow.is_active == True
            ).first()
            
            if not next_workflow:
                # No next step - complete the job work
                return WorkflowAutomationService._complete_workflow(job_batch)
            
            # Quality check requirement
            if next_workflow.requires_quality_check and quality_status != 'passed':
                return {'success': False, 'error': f'Quality check failed: {quality_status}'}
            
            # Update batch for next vendor
            old_vendor = job_batch.current_vendor
            job_batch.current_vendor = next_workflow.vendor_name
            job_batch.next_vendor = None
            job_batch.current_location = 'in_transit'
            job_batch.process_sequence += 1
            job_batch.process_name = next_workflow.process_name
            
            # Create location history
            WorkflowAutomationService._create_location_history(
                job_batch, 'auto_forward', old_vendor, next_workflow.vendor_name
            )
            
            db.session.commit()
            
            # Send notifications
            WorkflowAutomationService._send_auto_forward_notifications(
                job_batch, old_vendor, next_workflow
            )
            
            return {
                'success': True,
                'forwarded_to': next_workflow.vendor_name,
                'process': next_workflow.process_name,
                'sequence': job_batch.process_sequence,
                'message': f'Auto-forwarded to {next_workflow.vendor_name} for {next_workflow.process_name}'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error auto-forwarding to next vendor: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _complete_workflow(job_batch):
        """Complete the multi-vendor workflow"""
        try:
            job_batch.status = 'completed'
            job_batch.current_location = 'completed'
            job_batch.return_date = datetime.utcnow().date()
            
            # Update job work status
            job_work = job_batch.job_work
            job_work.status = 'completed'
            job_work.received_date = datetime.utcnow().date()
            
            db.session.commit()
            
            # Send completion notifications
            WorkflowAutomationService._send_completion_notifications(job_batch)
            
            return {
                'success': True,
                'status': 'completed',
                'message': 'Multi-vendor workflow completed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error completing workflow: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def check_and_trigger_auto_forwards():
        """Check all eligible batches for auto-forwarding"""
        try:
            # Find batches eligible for auto-forwarding
            eligible_batches = JobWorkBatch.query.filter(
                JobWorkBatch.is_auto_forward_enabled == True,
                JobWorkBatch.status == 'at_vendor',
                JobWorkBatch.quality_status == 'passed'
            ).all()
            
            results = []
            
            for batch in eligible_batches:
                # Check if enough time has passed
                workflow = JobWorkProcessWorkflow.query.filter_by(
                    process_name=batch.process_name,
                    vendor_name=batch.current_vendor
                ).first()
                
                if workflow and workflow.expected_duration_days:
                    days_at_vendor = (datetime.utcnow().date() - batch.updated_at.date()).days
                    if days_at_vendor >= workflow.expected_duration_days:
                        result = WorkflowAutomationService.auto_forward_to_next_vendor(batch.id)
                        results.append({
                            'batch_id': batch.id,
                            'job_number': batch.job_work.job_number,
                            'result': result
                        })
            
            return {
                'success': True,
                'processed_count': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error checking auto-forwards: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def detect_delayed_batches():
        """Detect and report delayed job work batches"""
        try:
            current_date = datetime.utcnow().date()
            
            # Find batches that are overdue
            delayed_batches = []
            
            active_batches = JobWorkBatch.query.filter(
                JobWorkBatch.status.in_(['issued', 'at_vendor', 'in_transit'])
            ).all()
            
            for batch in active_batches:
                workflow = JobWorkProcessWorkflow.query.filter_by(
                    process_name=batch.process_name,
                    vendor_name=batch.current_vendor
                ).first()
                
                if workflow and workflow.expected_duration_days:
                    expected_completion = batch.updated_at.date() + timedelta(days=workflow.expected_duration_days)
                    
                    if current_date > expected_completion:
                        delay_days = (current_date - expected_completion).days
                        delayed_batches.append({
                            'batch_id': batch.id,
                            'job_number': batch.job_work.job_number,
                            'vendor': batch.current_vendor,
                            'process': batch.process_name,
                            'delay_days': delay_days,
                            'expected_completion': expected_completion.isoformat(),
                            'current_location': batch.current_location
                        })
            
            # Send escalation alerts for severely delayed batches
            severely_delayed = [b for b in delayed_batches if b['delay_days'] > 5]
            for batch_info in severely_delayed:
                WorkflowAutomationService._send_escalation_alert(batch_info)
            
            return {
                'success': True,
                'total_delayed': len(delayed_batches),
                'severely_delayed': len(severely_delayed),
                'delayed_batches': delayed_batches
            }
            
        except Exception as e:
            logger.error(f"Error detecting delayed batches: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_workflow_status(job_work_id):
        """Get comprehensive workflow status for a job work"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            # Get all batches for this job work
            batches = JobWorkBatch.query.filter_by(job_work_id=job_work_id).all()
            
            # Get workflow definitions
            workflows = JobWorkProcessWorkflow.query.filter_by(
                item_id=job_work.item_id
            ).order_by(JobWorkProcessWorkflow.sequence_number).all()
            
            workflow_status = {
                'job_work': {
                    'id': job_work.id,
                    'job_number': job_work.job_number,
                    'status': job_work.status,
                    'item_name': job_work.item.name
                },
                'workflow_steps': [],
                'active_batches': [],
                'completed_steps': 0,
                'total_steps': len(workflows),
                'overall_progress': 0
            }
            
            # Build workflow steps status
            for workflow in workflows:
                batch = next((b for b in batches if b.process_name == workflow.process_name), None)
                
                step_status = {
                    'sequence': workflow.sequence_number,
                    'process': workflow.process_name,
                    'vendor': workflow.vendor_name,
                    'status': 'pending',
                    'batch_id': None,
                    'location': None,
                    'quality_status': None,
                    'auto_forward': workflow.auto_forward_enabled
                }
                
                if batch:
                    step_status.update({
                        'status': batch.status,
                        'batch_id': batch.id,
                        'location': batch.current_location,
                        'quality_status': batch.quality_status
                    })
                    
                    if batch.status == 'completed':
                        workflow_status['completed_steps'] += 1
                
                workflow_status['workflow_steps'].append(step_status)
            
            # Calculate overall progress
            if workflow_status['total_steps'] > 0:
                workflow_status['overall_progress'] = round(
                    (workflow_status['completed_steps'] / workflow_status['total_steps']) * 100, 2
                )
            
            # Get active batches details
            for batch in batches:
                if batch.status not in ['completed', 'cancelled']:
                    batch_info = {
                        'id': batch.id,
                        'process': batch.process_name,
                        'vendor': batch.current_vendor,
                        'location': batch.current_location,
                        'quantity': batch.quantity_issued,
                        'status': batch.status,
                        'quality_status': batch.quality_status,
                        'days_at_current': (datetime.utcnow().date() - batch.updated_at.date()).days
                    }
                    workflow_status['active_batches'].append(batch_info)
            
            return {'success': True, 'workflow_status': workflow_status}
            
        except Exception as e:
            logger.error(f"Error getting workflow status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _create_location_history(job_batch, action_type, from_vendor, to_vendor):
        """Create location history record"""
        history = JobWorkLocationHistory(
            jobwork_batch_id=job_batch.id,
            from_location=f"at_{from_vendor.lower().replace(' ', '_')}" if from_vendor else None,
            to_location=f"at_{to_vendor.lower().replace(' ', '_')}" if to_vendor else job_batch.current_location,
            vendor_name=to_vendor,
            notes=f"Auto-forwarded from {from_vendor} to {to_vendor}" if action_type == 'auto_forward' else f"Manual transfer to {to_vendor}",
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
    
    @staticmethod
    def _send_workflow_start_notifications(job_work, vendor_config, batch):
        """Send notifications when workflow starts"""
        if vendor_config.get('alert_email'):
            send_email_notification(
                to_email=vendor_config['alert_email'],
                subject=f"New Job Work Assignment - {job_work.job_number}",
                template='job_work_assignment',
                context={
                    'job_work': job_work,
                    'vendor_name': vendor_config['vendor_name'],
                    'process': vendor_config['process'],
                    'quantity': batch.quantity_issued,
                    'batch_id': batch.id
                }
            )
    
    @staticmethod
    def _send_auto_forward_notifications(job_batch, from_vendor, next_workflow):
        """Send notifications for auto-forwarding"""
        if next_workflow.alert_email:
            send_email_notification(
                to_email=next_workflow.alert_email,
                subject=f"Material Forwarded - {job_batch.job_work.job_number}",
                template='auto_forward_notification',
                context={
                    'job_batch': job_batch,
                    'from_vendor': from_vendor,
                    'to_vendor': next_workflow.vendor_name,
                    'process': next_workflow.process_name
                }
            )
    
    @staticmethod
    def _send_completion_notifications(job_batch):
        """Send notifications when workflow completes"""
        # Notify internal team
        send_email_notification(
            to_email="production@company.com",  # Configure this
            subject=f"Job Work Completed - {job_batch.job_work.job_number}",
            template='job_work_completion',
            context={'job_batch': job_batch}
        )
    
    @staticmethod
    def _send_escalation_alert(batch_info):
        """Send escalation alert for severely delayed batches"""
        send_email_notification(
            to_email="manager@company.com",  # Configure this
            subject=f"URGENT: Delayed Job Work - {batch_info['job_number']}",
            template='delay_escalation',
            context=batch_info
        )