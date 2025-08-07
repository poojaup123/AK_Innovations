"""
Job Work Automation Service
Handles vendor location tracking, auto-forwarding, and notifications
"""

from datetime import datetime, timedelta
from sqlalchemy import and_
from app import db
# Importing at function level to avoid circular imports
# from models.batch import JobWorkBatch, JobWorkLocationHistory, JobWorkProcessWorkflow
# from models import JobWork, Supplier, User
from services.notification_helpers import send_email_notification, send_whatsapp_notification


class JobWorkAutomationService:
    """Service for automating job work processes and vendor management"""
    
    @staticmethod
    def update_location_tracking(jobwork_batch_id, new_location, vendor_name=None, notes=None, user_id=None):
        """Update location tracking for job work batch"""
        try:
            from models.batch import JobWorkBatch, JobWorkLocationHistory
            batch = JobWorkBatch.query.get(jobwork_batch_id)
            if not batch:
                return False, "Job work batch not found"
            
            # Update location with history tracking
            batch.update_location(new_location, vendor_name, notes)
            
            # Add user reference to history if provided
            if user_id:
                history_record = JobWorkLocationHistory.query.filter_by(
                    jobwork_batch_id=jobwork_batch_id
                ).order_by(JobWorkLocationHistory.timestamp.desc()).first()
                if history_record:
                    history_record.created_by = user_id
            
            db.session.commit()
            
            # Send notifications if configured
            JobWorkAutomationService._send_location_notifications(batch, new_location, vendor_name)
            
            return True, f"Location updated to {new_location}"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error updating location: {str(e)}"
    
    @staticmethod
    def check_auto_forward_eligibility(jobwork_batch_id):
        """Check if job work batch is eligible for auto-forwarding"""
        try:
            from models.batch import JobWorkBatch
            batch = JobWorkBatch.query.get(jobwork_batch_id)
            if not batch:
                return False, "Batch not found"
            
            # Check if auto-forward is enabled
            if not batch.is_auto_forward_enabled:
                return False, "Auto-forward not enabled for this batch"
            
            # Check if current process is completed
            if batch.status != 'returned':
                return False, "Current process not completed"
            
            # Check quality status
            if batch.quality_status not in ['passed', 'pending']:
                return False, f"Quality check failed: {batch.quality_status}"
            
            # Check if next vendor is defined
            if not batch.next_vendor:
                return False, "Next vendor not defined"
            
            return True, "Ready for auto-forward"
            
        except Exception as e:
            return False, f"Error checking eligibility: {str(e)}"
    
    @staticmethod
    def auto_forward_to_next_vendor(jobwork_batch_id, force=False):
        """Automatically forward material to next vendor in sequence"""
        try:
            from models.batch import JobWorkBatch, JobWorkProcessWorkflow
            # Check eligibility unless forced
            if not force:
                eligible, message = JobWorkAutomationService.check_auto_forward_eligibility(jobwork_batch_id)
                if not eligible:
                    return False, message
            
            batch = JobWorkBatch.query.get(jobwork_batch_id)
            next_vendor = batch.next_vendor
            
            # Update location to in_transit
            batch.update_location('in_transit', next_vendor, f"Auto-forwarded to {next_vendor}")
            
            # Create new job work process for next vendor
            # This would integrate with your existing job work creation logic
            
            # Update sequence
            batch.process_sequence += 1
            
            # Find next workflow step
            workflow = JobWorkProcessWorkflow.query.filter_by(
                item_id=batch.job_work.item_id,
                sequence_number=batch.process_sequence + 1
            ).first()
            
            if workflow:
                batch.next_vendor = workflow.vendor_name
            else:
                batch.next_vendor = None  # Final step
            
            db.session.commit()
            
            # Send notifications
            JobWorkAutomationService._send_forward_notifications(batch, next_vendor)
            
            return True, f"Auto-forwarded to {next_vendor}"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error auto-forwarding: {str(e)}"
    
    @staticmethod
    def get_location_history(jobwork_batch_id):
        """Get complete location history for a job work batch"""
        try:
            from models.batch import JobWorkLocationHistory
            history = JobWorkLocationHistory.query.filter_by(
                jobwork_batch_id=jobwork_batch_id
            ).order_by(JobWorkLocationHistory.timestamp.desc()).all()
            
            return history
            
        except Exception as e:
            print(f"Error getting location history: {e}")
            return []
    
    @staticmethod
    def get_vendor_workload(vendor_name, start_date=None, end_date=None):
        """Get current workload for a vendor"""
        try:
            from models.batch import JobWorkBatch
            query = JobWorkBatch.query.filter_by(current_vendor=vendor_name)
            
            if start_date:
                query = query.filter(JobWorkBatch.issue_date >= start_date)
            if end_date:
                query = query.filter(JobWorkBatch.issue_date <= end_date)
            
            batches = query.all()
            
            workload = {
                'total_batches': len(batches),
                'pending_batches': len([b for b in batches if b.status == 'issued']),
                'in_progress_batches': len([b for b in batches if b.status == 'in_progress']),
                'completed_batches': len([b for b in batches if b.status == 'returned']),
                'total_quantity': sum(b.quantity_issued for b in batches),
                'pending_quantity': sum(b.quantity_issued for b in batches if b.status == 'issued')
            }
            
            return workload
            
        except Exception as e:
            print(f"Error getting vendor workload: {e}")
            return {}
    
    @staticmethod
    def check_overdue_batches():
        """Check for overdue job work batches and send alerts"""
        try:
            from models.batch import JobWorkBatch
            # Get batches that are overdue (example: more than 7 days old and still pending)
            cutoff_date = datetime.now().date() - timedelta(days=7)
            
            overdue_batches = JobWorkBatch.query.filter(
                and_(
                    JobWorkBatch.issue_date <= cutoff_date,
                    JobWorkBatch.status.in_(['issued', 'in_progress'])
                )
            ).all()
            
            alerts_sent = 0
            for batch in overdue_batches:
                if batch.current_vendor:
                    # Send alert about overdue batch
                    JobWorkAutomationService._send_overdue_alert(batch)
                    alerts_sent += 1
            
            return alerts_sent, f"Checked {len(overdue_batches)} overdue batches"
            
        except Exception as e:
            return 0, f"Error checking overdue batches: {str(e)}"
    
    @staticmethod
    def create_process_workflow(item_id, workflow_name, process_steps):
        """Create a multi-vendor process workflow"""
        try:
            from models.batch import JobWorkProcessWorkflow
            # Delete existing workflow for this item
            JobWorkProcessWorkflow.query.filter_by(
                item_id=item_id,
                workflow_name=workflow_name
            ).delete()
            
            # Create new workflow steps
            for i, step in enumerate(process_steps, 1):
                workflow = JobWorkProcessWorkflow(
                    workflow_name=workflow_name,
                    item_id=item_id,
                    sequence_number=i,
                    process_name=step.get('process_name'),
                    vendor_name=step.get('vendor_name'),
                    department_name=step.get('department_name'),
                    auto_forward_enabled=step.get('auto_forward_enabled', False),
                    requires_quality_check=step.get('requires_quality_check', True),
                    expected_duration_days=step.get('expected_duration_days', 3),
                    send_alerts=step.get('send_alerts', True),
                    alert_email=step.get('alert_email'),
                    alert_phone=step.get('alert_phone')
                )
                db.session.add(workflow)
            
            db.session.commit()
            return True, f"Created workflow '{workflow_name}' with {len(process_steps)} steps"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error creating workflow: {str(e)}"
    
    @staticmethod
    def _send_location_notifications(batch, new_location, vendor_name):
        """Send notifications when location changes"""
        try:
            job_work = batch.job_work
            if not job_work:
                return
            
            # Prepare notification message
            message = f"""
Job Work Location Update

Job Number: {job_work.job_number}
Item: {job_work.item.name if job_work.item else 'Unknown'}
Process: {batch.process_name}
Quantity: {batch.quantity_issued}

New Location: {batch.current_location_display}
""" + (f"Vendor: {vendor_name}\n" if vendor_name else "")
            
            # Send to job work creator
            creator = job_work.creator
            if creator and creator.email:
                send_email_notification(
                    creator.email,
                    f"Job Work Location Update - {job_work.job_number}",
                    message
                )
            
            # Send to vendor if they have contact info
            if vendor_name:
                # Here you could look up vendor contact details and send notifications
                pass
                
        except Exception as e:
            print(f"Error sending location notifications: {e}")
    
    @staticmethod
    def _send_forward_notifications(batch, next_vendor):
        """Send notifications when material is forwarded"""
        try:
            job_work = batch.job_work
            message = f"""
Material Auto-Forwarded

Job Number: {job_work.job_number}
Item: {job_work.item.name if job_work.item else 'Unknown'}
Process: {batch.process_name}
Quantity: {batch.quantity_produced or batch.quantity_issued}

Forwarded To: {next_vendor}
Next Process: Step {batch.process_sequence}

Please prepare for material receipt.
"""
            
            # Send notifications to relevant parties
            creator = job_work.creator
            if creator and creator.email:
                send_email_notification(
                    creator.email,
                    f"Material Auto-Forwarded - {job_work.job_number}",
                    message
                )
                
        except Exception as e:
            print(f"Error sending forward notifications: {e}")
    
    @staticmethod
    def _send_overdue_alert(batch):
        """Send alert for overdue batch"""
        try:
            job_work = batch.job_work
            days_overdue = (datetime.now().date() - batch.issue_date).days
            
            message = f"""
OVERDUE ALERT: Job Work Batch

Job Number: {job_work.job_number}
Item: {job_work.item.name if job_work.item else 'Unknown'}
Process: {batch.process_name}
Vendor: {batch.current_vendor}
Days Overdue: {days_overdue}

Please follow up immediately.
"""
            
            # Send to job work creator
            creator = job_work.creator
            if creator and creator.email:
                send_email_notification(
                    creator.email,
                    f"OVERDUE: {job_work.job_number} - {batch.process_name}",
                    message
                )
                
        except Exception as e:
            print(f"Error sending overdue alert: {e}")


class JobWorkProgressTracker:
    """Service for tracking and visualizing job work progress"""
    
    @staticmethod
    def get_progress_timeline(job_work_id):
        """Get complete progress timeline for a job work"""
        try:
            from models import JobWork
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return []
            
            timeline = []
            
            # Add job work creation
            timeline.append({
                'date': job_work.created_at,
                'event': 'Job Work Created',
                'description': f"Job Work {job_work.job_number} created",
                'status': 'completed',
                'type': 'creation'
            })
            
            # Add batch events
            for batch in job_work.batch_records:
                # Material issued
                timeline.append({
                    'date': batch.issue_date,
                    'event': f"Material Issued - {batch.process_name}",
                    'description': f"{batch.quantity_issued} units issued to {batch.vendor_name or 'Unknown vendor'}",
                    'status': 'completed',
                    'type': 'issue',
                    'vendor': batch.vendor_name,
                    'location': batch.current_location_display
                })
                
                # Location history
                for history in batch.location_history:
                    timeline.append({
                        'date': history.timestamp,
                        'event': f"Location Update - {batch.process_name}",
                        'description': f"Material moved from {history.from_location or 'Unknown'} to {history.to_location}",
                        'status': 'completed',
                        'type': 'movement',
                        'vendor': history.vendor_name,
                        'notes': history.notes
                    })
                
                # Material returned
                if batch.return_date:
                    timeline.append({
                        'date': batch.return_date,
                        'event': f"Material Returned - {batch.process_name}",
                        'description': f"{batch.quantity_produced} units returned, {batch.quantity_scrap} scrap",
                        'status': 'completed',
                        'type': 'return',
                        'vendor': batch.vendor_name
                    })
            
            # Sort by date
            timeline.sort(key=lambda x: x['date'])
            
            return timeline
            
        except Exception as e:
            print(f"Error getting progress timeline: {e}")
            return []
    
    @staticmethod
    def get_vendor_pipeline():
        """Get current pipeline status across all vendors"""
        try:
            from models.batch import JobWorkBatch
            pipeline = {}
            
            # Get all active job work batches
            active_batches = JobWorkBatch.query.filter(
                JobWorkBatch.status.in_(['issued', 'in_progress', 'returned'])
            ).all()
            
            for batch in active_batches:
                vendor = batch.current_vendor or 'Unknown'
                
                if vendor not in pipeline:
                    pipeline[vendor] = {
                        'total_batches': 0,
                        'pending': 0,
                        'in_progress': 0,
                        'ready_for_return': 0,
                        'batches': []
                    }
                
                pipeline[vendor]['total_batches'] += 1
                pipeline[vendor]['batches'].append({
                    'job_number': batch.job_work.job_number,
                    'item_name': batch.job_work.item.name if batch.job_work.item else 'Unknown',
                    'process': batch.process_name,
                    'quantity': batch.quantity_issued,
                    'status': batch.status,
                    'location': batch.current_location,
                    'issue_date': batch.issue_date,
                    'days_pending': (datetime.now().date() - batch.issue_date).days
                })
                
                # Count by status
                if batch.status == 'issued':
                    pipeline[vendor]['pending'] += 1
                elif batch.status == 'in_progress':
                    pipeline[vendor]['in_progress'] += 1
                elif batch.status == 'returned':
                    pipeline[vendor]['ready_for_return'] += 1
            
            return pipeline
            
        except Exception as e:
            print(f"Error getting vendor pipeline: {e}")
            return {}
    
    @staticmethod
    def get_bottleneck_analysis():
        """Analyze bottlenecks in the job work process"""
        try:
            from models.batch import JobWorkBatch
            analysis = {
                'vendor_delays': {},
                'process_delays': {},
                'quality_issues': {},
                'recommendations': []
            }
            
            # Analyze vendor performance
            vendors = db.session.query(JobWorkBatch.current_vendor).distinct().all()
            
            for (vendor,) in vendors:
                if not vendor:
                    continue
                    
                vendor_batches = JobWorkBatch.query.filter_by(current_vendor=vendor).all()
                
                if vendor_batches:
                    avg_duration = sum(
                        (b.return_date - b.issue_date).days 
                        for b in vendor_batches 
                        if b.return_date and b.issue_date
                    ) / len([b for b in vendor_batches if b.return_date])
                    
                    quality_failures = len([
                        b for b in vendor_batches 
                        if b.quality_status in ['failed', 'rework_needed']
                    ])
                    
                    analysis['vendor_delays'][vendor] = {
                        'avg_duration_days': avg_duration,
                        'total_batches': len(vendor_batches),
                        'quality_failures': quality_failures,
                        'failure_rate': (quality_failures / len(vendor_batches)) * 100
                    }
            
            # Generate recommendations
            for vendor, data in analysis['vendor_delays'].items():
                if data['avg_duration_days'] > 7:
                    analysis['recommendations'].append(
                        f"Vendor '{vendor}' has high average duration ({data['avg_duration_days']:.1f} days). Consider discussing timeline optimization."
                    )
                
                if data['failure_rate'] > 10:
                    analysis['recommendations'].append(
                        f"Vendor '{vendor}' has high quality failure rate ({data['failure_rate']:.1f}%). Consider quality improvement discussions."
                    )
            
            return analysis
            
        except Exception as e:
            print(f"Error analyzing bottlenecks: {e}")
            return {}