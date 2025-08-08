"""
Quality Management Service
Handles process-specific quality templates, KPIs, and quality-based workflow automation
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_
from app import db
from models import JobWork, Item
from models.batch import JobWorkBatch, InventoryBatch
import logging

logger = logging.getLogger(__name__)

class QualityManagementService:
    """Comprehensive quality management for job work processes"""
    
    @staticmethod
    def create_quality_template(process_name, template_config):
        """Create process-specific quality template"""
        try:
            from models.quality import QualityTemplate, QualityCheckpoint
            
            template = QualityTemplate(
                process_name=process_name,
                template_name=template_config['name'],
                description=template_config.get('description', ''),
                is_mandatory=template_config.get('mandatory', True),
                auto_forward_on_pass=template_config.get('auto_forward', False),
                rejection_tolerance_percent=template_config.get('rejection_tolerance', 5.0),
                created_at=datetime.utcnow()
            )
            
            db.session.add(template)
            db.session.flush()
            
            # Add quality checkpoints
            for checkpoint_config in template_config.get('checkpoints', []):
                checkpoint = QualityCheckpoint(
                    template_id=template.id,
                    checkpoint_name=checkpoint_config['name'],
                    checkpoint_type=checkpoint_config['type'],  # visual, measurement, test
                    description=checkpoint_config.get('description', ''),
                    is_critical=checkpoint_config.get('critical', False),
                    sequence_order=checkpoint_config.get('sequence', 1),
                    acceptance_criteria=checkpoint_config.get('criteria', ''),
                    measurement_unit=checkpoint_config.get('unit'),
                    min_value=checkpoint_config.get('min_value'),
                    max_value=checkpoint_config.get('max_value'),
                    reference_standard=checkpoint_config.get('standard')
                )
                db.session.add(checkpoint)
            
            db.session.commit()
            
            return {'success': True, 'template_id': template.id}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating quality template: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def perform_quality_inspection(job_batch_id, inspection_data):
        """Perform quality inspection with process-specific template"""
        try:
            job_batch = JobWorkBatch.query.get(job_batch_id)
            if not job_batch:
                return {'success': False, 'error': 'Job work batch not found'}
            
            # Get quality template for this process
            from models.quality import QualityTemplate, QualityInspection, QualityResult
            
            template = QualityTemplate.query.filter_by(
                process_name=job_batch.process_name,
                is_active=True
            ).first()
            
            if not template:
                return {'success': False, 'error': f'No quality template found for process: {job_batch.process_name}'}
            
            # Create quality inspection record
            inspection = QualityInspection(
                job_batch_id=job_batch_id,
                template_id=template.id,
                inspector_name=inspection_data.get('inspector_name'),
                inspection_date=inspection_data.get('inspection_date', datetime.utcnow().date()),
                quantity_inspected=inspection_data.get('quantity_inspected', job_batch.quantity_issued),
                overall_status='pending',
                notes=inspection_data.get('notes', ''),
                created_at=datetime.utcnow()
            )
            
            db.session.add(inspection)
            db.session.flush()
            
            # Process checkpoint results
            checkpoint_results = inspection_data.get('checkpoint_results', [])
            passed_checkpoints = 0
            critical_failures = 0
            
            for result_data in checkpoint_results:
                checkpoint_id = result_data['checkpoint_id']
                
                result = QualityResult(
                    inspection_id=inspection.id,
                    checkpoint_id=checkpoint_id,
                    result_status=result_data['status'],  # pass, fail, na
                    measured_value=result_data.get('measured_value'),
                    actual_result=result_data.get('actual_result'),
                    deviation=result_data.get('deviation'),
                    notes=result_data.get('notes'),
                    inspector_remarks=result_data.get('remarks')
                )
                
                db.session.add(result)
                
                # Count results
                if result_data['status'] == 'pass':
                    passed_checkpoints += 1
                elif result_data['status'] == 'fail':
                    # Check if this is a critical checkpoint
                    from models.quality import QualityCheckpoint
                    checkpoint = QualityCheckpoint.query.get(checkpoint_id)
                    if checkpoint and checkpoint.is_critical:
                        critical_failures += 1
            
            # Determine overall inspection status
            total_checkpoints = len(checkpoint_results)
            pass_percentage = (passed_checkpoints / total_checkpoints * 100) if total_checkpoints > 0 else 0
            
            if critical_failures > 0:
                inspection.overall_status = 'rejected'
                inspection.rejection_reason = 'Critical checkpoint failure'
            elif pass_percentage >= (100 - template.rejection_tolerance_percent):
                inspection.overall_status = 'passed'
            else:
                inspection.overall_status = 'rejected'
                inspection.rejection_reason = f'Pass rate {pass_percentage:.1f}% below tolerance'
            
            inspection.pass_percentage = pass_percentage
            inspection.quantity_passed = inspection_data.get('quantity_passed', 0)
            inspection.quantity_rejected = inspection_data.get('quantity_rejected', 0)
            inspection.quantity_rework = inspection_data.get('quantity_rework', 0)
            
            # Update job batch quality status
            job_batch.quality_status = inspection.overall_status
            job_batch.quality_notes = inspection.notes
            job_batch.inspected_by = inspection.inspector_name
            job_batch.inspection_date = inspection.inspection_date
            
            db.session.commit()
            
            # Trigger auto-forwarding if quality passed and enabled
            if (inspection.overall_status == 'passed' and 
                template.auto_forward_on_pass and 
                job_batch.is_auto_forward_enabled):
                
                from services.workflow_automation import WorkflowAutomationService
                auto_forward_result = WorkflowAutomationService.auto_forward_to_next_vendor(
                    job_batch_id, inspection.overall_status
                )
                
                return {
                    'success': True,
                    'inspection_id': inspection.id,
                    'overall_status': inspection.overall_status,
                    'pass_percentage': pass_percentage,
                    'auto_forwarded': auto_forward_result.get('success', False),
                    'auto_forward_details': auto_forward_result
                }
            
            return {
                'success': True,
                'inspection_id': inspection.id,
                'overall_status': inspection.overall_status,
                'pass_percentage': pass_percentage,
                'critical_failures': critical_failures
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error performing quality inspection: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def handle_quality_rejection(inspection_id, rejection_action):
        """Handle quality rejection with rework or return options"""
        try:
            from models.quality import QualityInspection, QualityRework
            
            inspection = QualityInspection.query.get(inspection_id)
            if not inspection:
                return {'success': False, 'error': 'Quality inspection not found'}
            
            job_batch = inspection.job_batch
            
            if rejection_action['action'] == 'rework':
                # Create rework record
                rework = QualityRework(
                    inspection_id=inspection_id,
                    job_batch_id=job_batch.id,
                    rework_type=rejection_action.get('rework_type', 'standard'),
                    rework_instructions=rejection_action.get('instructions'),
                    estimated_rework_time=rejection_action.get('estimated_time'),
                    rework_cost=rejection_action.get('cost', 0),
                    status='pending',
                    created_at=datetime.utcnow()
                )
                
                db.session.add(rework)
                
                # Update job batch status
                job_batch.status = 'rework_required'
                job_batch.quality_status = 'rework_needed'
                
                # Send rework notification
                from services.smart_notifications import SmartNotificationService
                SmartNotificationService.send_stage_notification(
                    job_batch.id, 'rework_required', {
                        'rework_instructions': rejection_action.get('instructions'),
                        'rework_id': rework.id
                    }
                )
                
            elif rejection_action['action'] == 'return':
                # Return material to previous vendor or company
                job_batch.status = 'returned'
                job_batch.quality_status = 'rejected'
                job_batch.current_location = 'returned'
                
                # Create return record
                from models.quality import QualityReturn
                return_record = QualityReturn(
                    inspection_id=inspection_id,
                    job_batch_id=job_batch.id,
                    return_reason=rejection_action.get('reason'),
                    return_to=rejection_action.get('return_to', 'company'),
                    return_cost=rejection_action.get('return_cost', 0),
                    status='pending',
                    created_at=datetime.utcnow()
                )
                
                db.session.add(return_record)
            
            elif rejection_action['action'] == 'scrap':
                # Mark as scrap
                job_batch.status = 'scrapped'
                job_batch.quality_status = 'scrapped'
                
                # Update batch quantities
                if job_batch.output_batch_id:
                    output_batch = InventoryBatch.query.get(job_batch.output_batch_id)
                    if output_batch:
                        # Move from finished to scrap
                        scrap_quantity = rejection_action.get('scrap_quantity', job_batch.quantity_issued)
                        output_batch.move_quantity(scrap_quantity, 'finished', 'scrap')
            
            db.session.commit()
            
            return {
                'success': True,
                'action_taken': rejection_action['action'],
                'batch_status': job_batch.status,
                'quality_status': job_batch.quality_status
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling quality rejection: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def calculate_quality_kpis(start_date, end_date, filters=None):
        """Calculate comprehensive quality KPIs"""
        try:
            from models.quality import QualityInspection
            
            # Base query for quality inspections in date range
            query = QualityInspection.query.filter(
                QualityInspection.inspection_date >= start_date,
                QualityInspection.inspection_date <= end_date
            )
            
            # Apply filters
            if filters:
                if filters.get('process_name'):
                    query = query.join(JobWorkBatch).filter(
                        JobWorkBatch.process_name == filters['process_name']
                    )
                if filters.get('vendor_name'):
                    query = query.join(JobWorkBatch).filter(
                        JobWorkBatch.vendor_name == filters['vendor_name']
                    )
            
            inspections = query.all()
            
            if not inspections:
                return {
                    'success': True,
                    'kpis': {
                        'total_inspections': 0,
                        'overall_pass_rate': 0,
                        'critical_failure_rate': 0,
                        'rework_rate': 0,
                        'average_pass_percentage': 0
                    }
                }
            
            # Calculate KPIs
            total_inspections = len(inspections)
            passed_inspections = len([i for i in inspections if i.overall_status == 'passed'])
            rejected_inspections = len([i for i in inspections if i.overall_status == 'rejected'])
            
            # Calculate rates
            overall_pass_rate = (passed_inspections / total_inspections) * 100
            rejection_rate = (rejected_inspections / total_inspections) * 100
            
            # Average pass percentage
            total_pass_percentage = sum(i.pass_percentage or 0 for i in inspections)
            average_pass_percentage = total_pass_percentage / total_inspections
            
            # Process-wise breakdown
            process_breakdown = {}
            for inspection in inspections:
                process = inspection.job_batch.process_name
                if process not in process_breakdown:
                    process_breakdown[process] = {
                        'total': 0,
                        'passed': 0,
                        'rejected': 0,
                        'pass_rate': 0
                    }
                
                process_breakdown[process]['total'] += 1
                if inspection.overall_status == 'passed':
                    process_breakdown[process]['passed'] += 1
                elif inspection.overall_status == 'rejected':
                    process_breakdown[process]['rejected'] += 1
            
            # Calculate pass rates for each process
            for process_data in process_breakdown.values():
                if process_data['total'] > 0:
                    process_data['pass_rate'] = (process_data['passed'] / process_data['total']) * 100
            
            # Vendor-wise breakdown
            vendor_breakdown = {}
            for inspection in inspections:
                vendor = inspection.job_batch.vendor_name
                if vendor not in vendor_breakdown:
                    vendor_breakdown[vendor] = {
                        'total': 0,
                        'passed': 0,
                        'rejected': 0,
                        'pass_rate': 0,
                        'average_pass_percentage': 0
                    }
                
                vendor_breakdown[vendor]['total'] += 1
                vendor_breakdown[vendor]['average_pass_percentage'] += (inspection.pass_percentage or 0)
                
                if inspection.overall_status == 'passed':
                    vendor_breakdown[vendor]['passed'] += 1
                elif inspection.overall_status == 'rejected':
                    vendor_breakdown[vendor]['rejected'] += 1
            
            # Calculate vendor rates
            for vendor_data in vendor_breakdown.values():
                if vendor_data['total'] > 0:
                    vendor_data['pass_rate'] = (vendor_data['passed'] / vendor_data['total']) * 100
                    vendor_data['average_pass_percentage'] /= vendor_data['total']
            
            # Quality trends (last 30 days)
            trend_data = QualityManagementService._calculate_quality_trends(end_date)
            
            kpis = {
                'summary': {
                    'total_inspections': total_inspections,
                    'overall_pass_rate': round(overall_pass_rate, 2),
                    'rejection_rate': round(rejection_rate, 2),
                    'average_pass_percentage': round(average_pass_percentage, 2),
                    'passed_inspections': passed_inspections,
                    'rejected_inspections': rejected_inspections
                },
                'process_breakdown': process_breakdown,
                'vendor_breakdown': vendor_breakdown,
                'trends': trend_data
            }
            
            return {'success': True, 'kpis': kpis}
            
        except Exception as e:
            logger.error(f"Error calculating quality KPIs: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_quality_trends(end_date, days=30):
        """Calculate quality trends over the specified period"""
        try:
            from models.quality import QualityInspection
            
            start_date = end_date - timedelta(days=days)
            
            # Get daily quality data
            daily_quality = db.session.query(
                QualityInspection.inspection_date,
                func.count(QualityInspection.id).label('total'),
                func.sum(func.case([(QualityInspection.overall_status == 'passed', 1)], else_=0)).label('passed'),
                func.avg(QualityInspection.pass_percentage).label('avg_pass_percentage')
            ).filter(
                QualityInspection.inspection_date >= start_date,
                QualityInspection.inspection_date <= end_date
            ).group_by(QualityInspection.inspection_date).all()
            
            trends = []
            for record in daily_quality:
                pass_rate = (record.passed / record.total * 100) if record.total > 0 else 0
                trends.append({
                    'date': record.inspection_date.isoformat(),
                    'total_inspections': record.total,
                    'pass_rate': round(pass_rate, 2),
                    'average_pass_percentage': round(record.avg_pass_percentage or 0, 2)
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error calculating quality trends: {str(e)}")
            return []
    
    @staticmethod
    def get_quality_dashboard_data():
        """Get comprehensive quality dashboard data"""
        try:
            current_date = datetime.utcnow().date()
            
            # Current month KPIs
            month_start = current_date.replace(day=1)
            month_kpis = QualityManagementService.calculate_quality_kpis(month_start, current_date)
            
            # Pending quality checks
            from models.quality import QualityInspection
            pending_inspections = JobWorkBatch.query.filter(
                JobWorkBatch.quality_status == 'pending'
            ).count()
            
            # Recent rejections requiring action
            recent_rejections = QualityInspection.query.filter(
                QualityInspection.overall_status == 'rejected',
                QualityInspection.inspection_date >= current_date - timedelta(days=7)
            ).count()
            
            # Quality alerts
            alerts = QualityManagementService._get_quality_alerts()
            
            dashboard_data = {
                'current_month_kpis': month_kpis.get('kpis', {}),
                'pending_inspections': pending_inspections,
                'recent_rejections': recent_rejections,
                'quality_alerts': alerts,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return {'success': True, 'dashboard_data': dashboard_data}
            
        except Exception as e:
            logger.error(f"Error getting quality dashboard data: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _get_quality_alerts():
        """Get current quality alerts and issues"""
        try:
            alerts = []
            
            # Check for processes with declining quality
            current_date = datetime.utcnow().date()
            week_ago = current_date - timedelta(days=7)
            month_ago = current_date - timedelta(days=30)
            
            from models.quality import QualityInspection
            
            # Get process performance for last week vs last month
            processes = db.session.query(
                JobWorkBatch.process_name,
                func.avg(QualityInspection.pass_percentage).label('avg_pass_rate')
            ).join(QualityInspection).filter(
                QualityInspection.inspection_date >= week_ago
            ).group_by(JobWorkBatch.process_name).all()
            
            for process in processes:
                if process.avg_pass_rate < 90:  # Alert threshold
                    alerts.append({
                        'type': 'declining_quality',
                        'severity': 'medium',
                        'process': process.process_name,
                        'current_rate': round(process.avg_pass_rate, 2),
                        'message': f"Quality declining in {process.process_name} process"
                    })
            
            # Check for overdue quality inspections
            overdue_batches = JobWorkBatch.query.filter(
                JobWorkBatch.quality_status == 'pending',
                JobWorkBatch.updated_at < datetime.utcnow() - timedelta(days=2)
            ).count()
            
            if overdue_batches > 0:
                alerts.append({
                    'type': 'overdue_inspections',
                    'severity': 'high',
                    'count': overdue_batches,
                    'message': f"{overdue_batches} quality inspections are overdue"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting quality alerts: {str(e)}")
            return []