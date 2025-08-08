"""
Enhanced Partial Processing Service
Advanced dashboard and consolidation system for partial job work processing
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import JobWork
from models.batch import JobWorkBatch, InventoryBatch, BatchMovement
# from services.partial_job_service import PartialJobService  # Commented to avoid circular dependency
import logging

logger = logging.getLogger(__name__)

class PartialProcessingService:
    """Enhanced partial processing with dashboard and smart consolidation"""
    
    @staticmethod
    def get_partial_processing_dashboard():
        """Get comprehensive partial processing dashboard data"""
        try:
            current_date = datetime.utcnow().date()
            
            # Active partial jobs
            active_partials = JobWork.query.filter(
                JobWork.status.in_(['partial_issued', 'partial_received'])
            ).all()
            
            # Categorize partial jobs
            partial_summary = {
                'total_active_partials': len(active_partials),
                'pending_issue': 0,
                'pending_receipt': 0,
                'ready_for_consolidation': 0,
                'partial_details': []
            }
            
            for job_work in active_partials:
                # Get basic status data directly
                status_result = {
                    'success': True,
                    'quantities': {
                        'to_issue': job_work.quantity_sent or 0,
                        'issued': job_work.quantity_sent or 0,
                        'received': job_work.quantity_received or 0,
                        'remaining_to_issue': 0,
                        'remaining_to_receive': max(0, (job_work.quantity_sent or 0) - (job_work.quantity_received or 0))
                    },
                    'progress': {
                        'issue_progress': 100,
                        'receipt_progress': ((job_work.quantity_received or 0) / (job_work.quantity_sent or 1)) * 100
                    },
                    'batch_details': []
                }
                
                if status_result['success']:
                    status_data = status_result
                    quantities = status_data['quantities']
                    
                    # Categorize based on status
                    if quantities['remaining_to_issue'] > 0:
                        partial_summary['pending_issue'] += 1
                    elif quantities['remaining_to_receive'] > 0:
                        partial_summary['pending_receipt'] += 1
                    elif quantities['remaining_to_receive'] == 0:
                        partial_summary['ready_for_consolidation'] += 1
                    
                    # Enhanced partial details
                    partial_detail = {
                        'job_work_id': job_work.id,
                        'job_number': job_work.job_number,
                        'item_name': job_work.item.name,
                        'vendor': job_work.customer_name,
                        'process': job_work.process,
                        'status': job_work.status,
                        'quantities': quantities,
                        'progress': status_data['progress'],
                        'batch_count': len(status_data['batch_details']),
                        'completion_estimate': PartialProcessingService._calculate_completion_estimate(job_work),
                        'risk_level': PartialProcessingService._assess_risk_level(job_work, quantities),
                        'next_action': PartialProcessingService._determine_next_action(quantities)
                    }
                    
                    partial_summary['partial_details'].append(partial_detail)
            
            # Weekly trends
            weekly_trends = PartialProcessingService._get_partial_processing_trends()
            
            # Performance metrics
            performance_metrics = PartialProcessingService._calculate_partial_performance_metrics()
            
            # Recommendations
            recommendations = PartialProcessingService._generate_smart_recommendations(active_partials)
            
            dashboard_data = {
                'summary': partial_summary,
                'trends': weekly_trends,
                'performance_metrics': performance_metrics,
                'recommendations': recommendations,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return {'success': True, 'dashboard_data': dashboard_data}
            
        except Exception as e:
            logger.error(f"Error getting partial processing dashboard: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_completion_estimate(job_work):
        """Calculate estimated completion date for partial job work"""
        try:
            # Get recent batch processing times
            recent_batches = JobWorkBatch.query.filter(
                JobWorkBatch.job_work_id == job_work.id,
                JobWorkBatch.return_date.isnot(None)
            ).all()
            
            if not recent_batches:
                # Default estimate based on expected return date
                if job_work.expected_return:
                    return job_work.expected_return.isoformat()
                else:
                    # Default to 7 days from now
                    estimated_date = datetime.utcnow().date() + timedelta(days=7)
                    return estimated_date.isoformat()
            
            # Calculate average processing time
            total_processing_days = 0
            for batch in recent_batches:
                if batch.issue_date and batch.return_date:
                    processing_days = (batch.return_date - batch.issue_date).days
                    total_processing_days += processing_days
            
            avg_processing_days = total_processing_days / len(recent_batches)
            
            # Estimate completion based on last issued batch + average processing time
            last_batch = max(recent_batches, key=lambda b: b.issue_date or datetime.min.date())
            estimated_completion = last_batch.issue_date + timedelta(days=avg_processing_days)
            
            return estimated_completion.isoformat()
            
        except Exception as e:
            logger.error(f"Error calculating completion estimate: {str(e)}")
            return None
    
    @staticmethod
    def _assess_risk_level(job_work, quantities):
        """Assess risk level for partial job work"""
        try:
            risk_factors = 0
            
            # Time-based risk
            if job_work.expected_return and datetime.utcnow().date() > job_work.expected_return:
                risk_factors += 2  # Overdue
            
            # Quantity-based risk
            issue_progress = quantities['issued'] / quantities['to_issue'] * 100 if quantities['to_issue'] > 0 else 0
            if issue_progress < 50:
                risk_factors += 1  # Slow issuance
            
            # Completion-based risk
            if quantities['remaining_to_receive'] > quantities['remaining_to_issue']:
                risk_factors += 1  # More pending receipts than issues
            
            # Vendor performance risk (check recent delays)
            recent_delays = JobWork.query.filter(
                JobWork.customer_name == job_work.customer_name,
                JobWork.received_date > JobWork.expected_return,
                JobWork.created_at >= datetime.utcnow() - timedelta(days=90)
            ).count()
            
            if recent_delays > 2:
                risk_factors += 1  # Vendor has history of delays
            
            # Risk level mapping
            if risk_factors >= 4:
                return 'high'
            elif risk_factors >= 2:
                return 'medium'
            else:
                return 'low'
                
        except Exception as e:
            logger.error(f"Error assessing risk level: {str(e)}")
            return 'unknown'
    
    @staticmethod
    def _determine_next_action(quantities):
        """Determine the next recommended action"""
        if quantities['remaining_to_issue'] > 0:
            return 'issue_next_batch'
        elif quantities['remaining_to_receive'] > 0:
            return 'follow_up_receipt'
        elif quantities['remaining_to_receive'] == 0:
            return 'consolidate_job'
        else:
            return 'review_status'
    
    @staticmethod
    def _get_partial_processing_trends():
        """Get partial processing trends over last 4 weeks"""
        try:
            trends = []
            current_date = datetime.utcnow().date()
            
            for week in range(4):
                week_start = current_date - timedelta(days=(week + 1) * 7)
                week_end = current_date - timedelta(days=week * 7)
                
                # Count partial jobs started this week
                new_partials = JobWork.query.filter(
                    JobWork.status.in_(['partial_issued', 'partial_received']),
                    JobWork.created_at >= week_start,
                    JobWork.created_at < week_end
                ).count()
                
                # Count partial jobs completed this week
                completed_partials = JobWork.query.filter(
                    JobWork.status == 'completed',
                    JobWork.received_date >= week_start,
                    JobWork.received_date < week_end,
                    JobWork.created_at < week_start  # Was previously partial
                ).count()
                
                trends.append({
                    'week_start': week_start.isoformat(),
                    'week_end': week_end.isoformat(),
                    'new_partials': new_partials,
                    'completed_partials': completed_partials,
                    'completion_rate': (completed_partials / new_partials * 100) if new_partials > 0 else 0
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting partial processing trends: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_partial_performance_metrics():
        """Calculate performance metrics for partial processing"""
        try:
            current_date = datetime.utcnow().date()
            month_start = current_date.replace(day=1)
            
            # Partial jobs in current month
            monthly_partials = JobWork.query.filter(
                JobWork.status.in_(['partial_issued', 'partial_received', 'completed']),
                JobWork.created_at >= month_start
            ).all()
            
            metrics = {
                'total_partial_jobs': len(monthly_partials),
                'average_batches_per_job': 0,
                'average_completion_time': 0,
                'efficiency_score': 0,
                'cost_impact': 0
            }
            
            if not monthly_partials:
                return metrics
            
            # Calculate average batches per job
            total_batches = 0
            total_completion_days = 0
            completed_jobs = 0
            
            for job_work in monthly_partials:
                # Count batches for this job
                batch_count = JobWorkBatch.query.filter_by(job_work_id=job_work.id).count()
                total_batches += batch_count
                
                # Calculate completion time for completed jobs
                if job_work.status == 'completed' and job_work.received_date:
                    completion_days = (job_work.received_date - job_work.sent_date).days
                    total_completion_days += completion_days
                    completed_jobs += 1
            
            metrics['average_batches_per_job'] = round(total_batches / len(monthly_partials), 1)
            
            if completed_jobs > 0:
                metrics['average_completion_time'] = round(total_completion_days / completed_jobs, 1)
            
            # Calculate efficiency score (fewer batches = more efficient)
            # Base efficiency is 100%, reduce by 10% for each additional batch beyond 1
            base_efficiency = 100
            efficiency_penalty = max(0, (metrics['average_batches_per_job'] - 1) * 10)
            metrics['efficiency_score'] = max(0, base_efficiency - efficiency_penalty)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating partial performance metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_smart_recommendations(active_partials):
        """Generate smart recommendations for partial processing optimization"""
        try:
            recommendations = []
            
            # Check for jobs with too many small batches
            high_batch_count_jobs = []
            for job_work in active_partials:
                batch_count = JobWorkBatch.query.filter_by(job_work_id=job_work.id).count()
                if batch_count > 5:
                    high_batch_count_jobs.append(job_work.job_number)
            
            if high_batch_count_jobs:
                recommendations.append({
                    'type': 'optimization',
                    'priority': 'medium',
                    'title': 'Consolidate Small Batches',
                    'description': f"Jobs {', '.join(high_batch_count_jobs[:3])} have many small batches. Consider consolidating for efficiency.",
                    'action': 'review_batch_sizing'
                })
            
            # Check for overdue jobs
            overdue_jobs = []
            current_date = datetime.utcnow().date()
            for job_work in active_partials:
                if job_work.expected_return and current_date > job_work.expected_return:
                    overdue_jobs.append(job_work.job_number)
            
            if overdue_jobs:
                recommendations.append({
                    'type': 'alert',
                    'priority': 'high',
                    'title': 'Overdue Partial Jobs',
                    'description': f"Jobs {', '.join(overdue_jobs[:3])} are past their expected completion date.",
                    'action': 'expedite_processing'
                })
            
            # Check for jobs ready for consolidation
            ready_for_consolidation = []
            for job_work in active_partials:
                remaining_to_receive = max(0, (job_work.quantity_sent or 0) - (job_work.quantity_received or 0))
                if remaining_to_receive == 0:
                    ready_for_consolidation.append(job_work.job_number)
            
            if ready_for_consolidation:
                recommendations.append({
                    'type': 'action',
                    'priority': 'medium',
                    'title': 'Jobs Ready for Completion',
                    'description': f"Jobs {', '.join(ready_for_consolidation[:3])} are ready for final consolidation.",
                    'action': 'complete_jobs'
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return []
    
    @staticmethod
    def smart_consolidate_partial_jobs(consolidation_rules=None):
        """Intelligently consolidate completed partial jobs"""
        try:
            if not consolidation_rules:
                consolidation_rules = {
                    'auto_consolidate_threshold': 0.95,  # 95% complete
                    'min_quantity_threshold': 0.1,  # Minimum 10% of original quantity
                    'quality_requirement': 'passed'
                }
            
            # Find jobs eligible for consolidation
            eligible_jobs = JobWork.query.filter(
                JobWork.status.in_(['partial_received'])
            ).all()
            
            consolidation_results = []
            
            for job_work in eligible_jobs:
                # Calculate quantities directly
                quantities = {
                    'to_issue': job_work.quantity_sent or 0,
                    'issued': job_work.quantity_sent or 0,
                    'received': job_work.quantity_received or 0,
                    'remaining_to_receive': max(0, (job_work.quantity_sent or 0) - (job_work.quantity_received or 0))
                }
                
                # Check consolidation criteria
                completion_rate = quantities['received'] / quantities['to_issue'] if quantities['to_issue'] > 0 else 0
                
                if completion_rate >= consolidation_rules['auto_consolidate_threshold']:
                    # Auto-consolidate this job
                    consolidation_result = PartialProcessingService._consolidate_job(
                        job_work, quantities, consolidation_rules
                    )
                    consolidation_results.append(consolidation_result)
            
            return {
                'success': True,
                'consolidation_count': len(consolidation_results),
                'results': consolidation_results
            }
            
        except Exception as e:
            logger.error(f"Error in smart consolidation: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _consolidate_job(job_work, quantities, rules):
        """Consolidate a single partial job"""
        try:
            # Update job work status
            job_work.status = 'completed'
            job_work.received_date = datetime.utcnow().date()
            
            # Create consolidation record
            consolidation_record = {
                'job_work_id': job_work.id,
                'job_number': job_work.job_number,
                'original_quantity': quantities['to_issue'],
                'final_received_quantity': quantities['received'],
                'completion_rate': round((quantities['received'] / quantities['to_issue']) * 100, 2),
                'consolidation_date': datetime.utcnow().isoformat(),
                'batch_count': len(status_result['batch_details']) if 'status_result' in locals() else 0
            }
            
            # Create final GRN if needed
            if quantities['received'] > 0:
                from services.grn_service import GRNService
                
                grn_data = {
                    'supplier_id': 1,  # Default supplier
                    'job_work_id': job_work.id,
                    'receipt_date': datetime.utcnow().date(),
                    'receipt_type': 'job_work_consolidation',
                    'received_by': 1,  # System user
                    'remarks': f'Automatic consolidation of partial job work {job_work.job_number}',
                    'line_items': [{
                        'item_id': job_work.item_id,
                        'quantity_received': quantities['received'],
                        'quantity_accepted': quantities['received'],
                        'quality_status': 'passed',
                        'batch_code': f'CONSOL-{job_work.job_number}-{datetime.now().strftime("%Y%m%d")}'
                    }]
                }
                
                grn_result = GRNService.create_material_receipt(grn_data)
                consolidation_record['final_grn_id'] = grn_result.get('grn', {}).get('id')
            
            db.session.commit()
            
            consolidation_record['success'] = True
            return consolidation_record
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error consolidating job {job_work.job_number}: {str(e)}")
            return {
                'job_work_id': job_work.id,
                'job_number': job_work.job_number,
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def generate_partial_processing_report(start_date, end_date):
        """Generate comprehensive partial processing report"""
        try:
            # Get all partial jobs in date range
            partial_jobs = JobWork.query.filter(
                JobWork.status.in_(['partial_issued', 'partial_received', 'completed']),
                JobWork.created_at >= start_date,
                JobWork.created_at <= end_date
            ).all()
            
            report_data = {
                'report_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary': {
                    'total_partial_jobs': len(partial_jobs),
                    'completed_jobs': 0,
                    'active_jobs': 0,
                    'average_batches_per_job': 0,
                    'efficiency_metrics': {}
                },
                'detailed_analysis': [],
                'vendor_performance': {},
                'process_performance': {},
                'recommendations': []
            }
            
            total_batches = 0
            vendor_stats = {}
            process_stats = {}
            
            for job_work in partial_jobs:
                # Calculate quantities directly
                quantities = {
                    'to_issue': job_work.quantity_sent or 0,
                    'received': job_work.quantity_received or 0
                }
                
                job_analysis = {
                    'job_number': job_work.job_number,
                    'item_name': job_work.item.name,
                    'vendor': job_work.customer_name,
                    'process': job_work.process,
                    'status': job_work.status,
                    'created_date': job_work.created_at.date().isoformat(),
                    'completion_date': job_work.received_date.isoformat() if job_work.received_date else None,
                    'quantities': quantities,
                    'batch_count': 1,  # Default to 1 batch for simplicity
                    'completion_rate': round((quantities['received'] / quantities['to_issue']) * 100, 2) if quantities['to_issue'] > 0 else 0
                }
                
                total_batches += 1  # Default to 1 batch per job
                
                # Update vendor stats
                vendor = job_work.customer_name
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {'jobs': 0, 'total_batches': 0, 'completed_jobs': 0}
                vendor_stats[vendor]['jobs'] += 1
                vendor_stats[vendor]['total_batches'] += 1  # Use simplified batch count
                if job_work.status == 'completed':
                    vendor_stats[vendor]['completed_jobs'] += 1
                
                # Update process stats
                process = job_work.process
                if process not in process_stats:
                    process_stats[process] = {'jobs': 0, 'total_batches': 0, 'completed_jobs': 0}
                process_stats[process]['jobs'] += 1
                process_stats[process]['total_batches'] += 1  # Use simplified batch count
                if job_work.status == 'completed':
                    process_stats[process]['completed_jobs'] += 1
                
                report_data['detailed_analysis'].append(job_analysis)
                
                # Count job statuses
                if job_work.status == 'completed':
                    report_data['summary']['completed_jobs'] += 1
                else:
                    report_data['summary']['active_jobs'] += 1
            
            # Calculate summary metrics
            if len(partial_jobs) > 0:
                report_data['summary']['average_batches_per_job'] = round(total_batches / len(partial_jobs), 2)
                completion_rate = (report_data['summary']['completed_jobs'] / len(partial_jobs)) * 100
                report_data['summary']['efficiency_metrics']['completion_rate'] = round(completion_rate, 2)
            
            # Calculate vendor performance
            for vendor, stats in vendor_stats.items():
                stats['avg_batches_per_job'] = round(stats['total_batches'] / stats['jobs'], 2)
                stats['completion_rate'] = round((stats['completed_jobs'] / stats['jobs']) * 100, 2) if stats['jobs'] > 0 else 0
            
            report_data['vendor_performance'] = vendor_stats
            
            # Calculate process performance
            for process, stats in process_stats.items():
                stats['avg_batches_per_job'] = round(stats['total_batches'] / stats['jobs'], 2)
                stats['completion_rate'] = round((stats['completed_jobs'] / stats['jobs']) * 100, 2) if stats['jobs'] > 0 else 0
            
            report_data['process_performance'] = process_stats
            
            return {'success': True, 'report': report_data}
            
        except Exception as e:
            logger.error(f"Error generating partial processing report: {str(e)}")
            return {'success': False, 'error': str(e)}