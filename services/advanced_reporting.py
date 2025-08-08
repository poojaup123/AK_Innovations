"""
Advanced Reporting Service
Material flow reports, vendor timelines, efficiency analysis, and cost reporting
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, text
from app import db
from models import JobWork, Item, Supplier
from models.batch import JobWorkBatch, JobWorkLocationHistory, InventoryBatch, BatchMovement
from models.quality import QualityInspection, QualityKPI
from services.vendor_analytics import VendorAnalyticsService
from services.costing_service import CostingService
import logging

logger = logging.getLogger(__name__)

class AdvancedReportingService:
    """Comprehensive reporting system for material flow, vendor performance, and efficiency analysis"""
    
    @staticmethod
    def generate_material_flow_report(filters=None):
        """Generate comprehensive material flow report with vendor timelines"""
        try:
            # Default filters
            if not filters:
                filters = {
                    'start_date': datetime.utcnow().date() - timedelta(days=30),
                    'end_date': datetime.utcnow().date(),
                    'item_ids': None,
                    'vendor_names': None,
                    'process_names': None
                }
            
            # Build base query
            query_conditions = [
                JobWork.created_at >= filters['start_date'],
                JobWork.created_at <= filters['end_date']
            ]
            
            if filters.get('item_ids'):
                query_conditions.append(JobWork.item_id.in_(filters['item_ids']))
            
            if filters.get('vendor_names'):
                query_conditions.append(JobWork.customer_name.in_(filters['vendor_names']))
            
            if filters.get('process_names'):
                query_conditions.append(JobWork.process.in_(filters['process_names']))
            
            # Get job works with their batches and location history
            job_works = JobWork.query.filter(and_(*query_conditions)).all()
            
            material_flows = []
            
            for job_work in job_works:
                # Get all batches for this job work
                job_batches = JobWorkBatch.query.filter_by(job_work_id=job_work.id).all()
                
                flow_data = {
                    'job_work': {
                        'id': job_work.id,
                        'job_number': job_work.job_number,
                        'item_name': job_work.item.name,
                        'item_code': job_work.item.code,
                        'vendor': job_work.customer_name,
                        'process': job_work.process,
                        'status': job_work.status,
                        'quantity_sent': job_work.quantity_sent,
                        'quantity_received': job_work.quantity_received,
                        'total_value': job_work.total_cost
                    },
                    'material_journey': [],
                    'vendor_timeline': [],
                    'quality_checkpoints': [],
                    'cost_breakdown': {},
                    'efficiency_metrics': {}
                }
                
                # Build material journey from batch movements
                for batch in job_batches:
                    # Get location history for this batch
                    location_history = JobWorkLocationHistory.query.filter_by(
                        jobwork_batch_id=batch.id
                    ).order_by(JobWorkLocationHistory.timestamp).all()
                    
                    journey_steps = []
                    for history in location_history:
                        step = {
                            'timestamp': history.timestamp.isoformat(),
                            'from_location': history.from_location,
                            'to_location': history.to_location,
                            'vendor_name': history.vendor_name,
                            'notes': history.notes,
                            'duration_at_location': None
                        }
                        journey_steps.append(step)
                    
                    # Calculate duration at each location
                    for i, step in enumerate(journey_steps):
                        if i < len(journey_steps) - 1:
                            current_time = datetime.fromisoformat(step['timestamp'])
                            next_time = datetime.fromisoformat(journey_steps[i + 1]['timestamp'])
                            duration = (next_time - current_time).total_seconds() / 3600  # hours
                            step['duration_at_location'] = round(duration, 2)
                    
                    flow_data['material_journey'].append({
                        'batch_id': batch.id,
                        'quantity': batch.quantity_issued,
                        'process_sequence': batch.process_sequence,
                        'journey_steps': journey_steps
                    })
                
                # Build vendor timeline
                vendor_timeline = AdvancedReportingService._build_vendor_timeline(job_work, job_batches)
                flow_data['vendor_timeline'] = vendor_timeline
                
                # Get quality checkpoints
                quality_checkpoints = AdvancedReportingService._get_quality_checkpoints(job_batches)
                flow_data['quality_checkpoints'] = quality_checkpoints
                
                # Calculate cost breakdown
                cost_breakdown = AdvancedReportingService._calculate_job_cost_breakdown(job_work)
                flow_data['cost_breakdown'] = cost_breakdown
                
                # Calculate efficiency metrics
                efficiency_metrics = AdvancedReportingService._calculate_material_efficiency(job_work, job_batches)
                flow_data['efficiency_metrics'] = efficiency_metrics
                
                material_flows.append(flow_data)
            
            # Generate summary statistics
            summary_stats = AdvancedReportingService._calculate_flow_summary_stats(material_flows)
            
            report = {
                'report_info': {
                    'generated_at': datetime.utcnow().isoformat(),
                    'period': {
                        'start_date': filters['start_date'].isoformat(),
                        'end_date': filters['end_date'].isoformat()
                    },
                    'filters_applied': filters
                },
                'summary_statistics': summary_stats,
                'material_flows': material_flows,
                'insights_and_recommendations': AdvancedReportingService._generate_flow_insights(material_flows)
            }
            
            return {'success': True, 'report': report}
            
        except Exception as e:
            logger.error(f"Error generating material flow report: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _build_vendor_timeline(job_work, job_batches):
        """Build detailed vendor timeline for job work"""
        try:
            timeline_events = []
            
            for batch in job_batches:
                # Add initial issuance event
                timeline_events.append({
                    'event_type': 'material_issued',
                    'timestamp': batch.created_at.isoformat(),
                    'vendor': batch.vendor_name,
                    'process': batch.process_name,
                    'quantity': batch.quantity_issued,
                    'status': 'issued',
                    'batch_id': batch.id
                })
                
                # Add location change events
                location_history = JobWorkLocationHistory.query.filter_by(
                    jobwork_batch_id=batch.id
                ).order_by(JobWorkLocationHistory.timestamp).all()
                
                for history in location_history:
                    timeline_events.append({
                        'event_type': 'location_change',
                        'timestamp': history.timestamp.isoformat(),
                        'vendor': history.vendor_name,
                        'from_location': history.from_location,
                        'to_location': history.to_location,
                        'notes': history.notes,
                        'batch_id': batch.id
                    })
                
                # Add quality inspection events
                quality_inspections = QualityInspection.query.filter_by(job_batch_id=batch.id).all()
                for inspection in quality_inspections:
                    timeline_events.append({
                        'event_type': 'quality_inspection',
                        'timestamp': inspection.inspection_date.isoformat(),
                        'vendor': batch.vendor_name,
                        'inspector': inspection.inspector_name,
                        'result': inspection.overall_status,
                        'pass_percentage': inspection.pass_percentage,
                        'batch_id': batch.id
                    })
                
                # Add completion event if applicable
                if batch.return_date:
                    timeline_events.append({
                        'event_type': 'material_returned',
                        'timestamp': batch.return_date.isoformat(),
                        'vendor': batch.vendor_name,
                        'quantity_produced': batch.quantity_produced,
                        'quantity_scrap': batch.quantity_scrap,
                        'status': batch.status,
                        'batch_id': batch.id
                    })
            
            # Sort timeline by timestamp
            timeline_events.sort(key=lambda x: x['timestamp'])
            
            return timeline_events
            
        except Exception as e:
            logger.error(f"Error building vendor timeline: {str(e)}")
            return []
    
    @staticmethod
    def _get_quality_checkpoints(job_batches):
        """Get quality checkpoint data for batches"""
        try:
            quality_data = []
            
            for batch in job_batches:
                inspections = QualityInspection.query.filter_by(job_batch_id=batch.id).all()
                
                for inspection in inspections:
                    checkpoint_data = {
                        'batch_id': batch.id,
                        'vendor': batch.vendor_name,
                        'process': batch.process_name,
                        'inspection_id': inspection.id,
                        'inspection_date': inspection.inspection_date.isoformat(),
                        'inspector': inspection.inspector_name,
                        'overall_status': inspection.overall_status,
                        'pass_percentage': inspection.pass_percentage,
                        'quantity_inspected': inspection.quantity_inspected,
                        'quantity_passed': inspection.quantity_passed,
                        'quantity_rejected': inspection.quantity_rejected,
                        'defect_categories': inspection.defect_categories,
                        'checkpoint_results': []
                    }
                    
                    # Get individual checkpoint results
                    from models.quality import QualityResult
                    results = QualityResult.query.filter_by(inspection_id=inspection.id).all()
                    
                    for result in results:
                        checkpoint_data['checkpoint_results'].append({
                            'checkpoint_name': result.checkpoint.checkpoint_name,
                            'result_status': result.result_status,
                            'measured_value': result.measured_value,
                            'defect_severity': result.defect_severity,
                            'notes': result.notes
                        })
                    
                    quality_data.append(checkpoint_data)
            
            return quality_data
            
        except Exception as e:
            logger.error(f"Error getting quality checkpoints: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_job_cost_breakdown(job_work):
        """Calculate detailed cost breakdown for job work"""
        try:
            # Get comprehensive cost data using CostingService
            costing_result = CostingService.calculate_job_work_cost(job_work.id)
            
            if costing_result['success']:
                breakdown = costing_result['cost_breakdown']
                
                # Add additional analysis
                breakdown['cost_per_unit'] = breakdown['total_cost'] / job_work.quantity_sent if job_work.quantity_sent > 0 else 0
                breakdown['cost_efficiency'] = (job_work.quantity_received / job_work.quantity_sent) * 100 if job_work.quantity_sent > 0 else 0
                
                # Calculate cost categories as percentages
                if breakdown['total_cost'] > 0:
                    breakdown['cost_percentages'] = {
                        'material': (breakdown['material_cost'] / breakdown['total_cost']) * 100,
                        'labor': (breakdown['labor_cost'] / breakdown['total_cost']) * 100,
                        'overhead': (breakdown['overhead_cost'] / breakdown['total_cost']) * 100,
                        'vendor': (breakdown['vendor_cost'] / breakdown['total_cost']) * 100,
                        'scrap_wastage': ((breakdown['scrap_cost'] + breakdown['wastage_cost']) / breakdown['total_cost']) * 100
                    }
                
                return breakdown
            
            return {}
            
        except Exception as e:
            logger.error(f"Error calculating cost breakdown: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_material_efficiency(job_work, job_batches):
        """Calculate material efficiency metrics"""
        try:
            metrics = {
                'material_utilization': 0,
                'yield_percentage': 0,
                'scrap_percentage': 0,
                'processing_efficiency': 0,
                'time_efficiency': 0,
                'quality_efficiency': 0
            }
            
            if not job_batches:
                return metrics
            
            # Material utilization
            total_issued = sum(batch.quantity_issued for batch in job_batches)
            total_produced = sum(batch.quantity_produced or 0 for batch in job_batches)
            total_scrap = sum(batch.quantity_scrap or 0 for batch in job_batches)
            
            if total_issued > 0:
                metrics['material_utilization'] = (total_produced / total_issued) * 100
                metrics['yield_percentage'] = ((total_produced) / total_issued) * 100
                metrics['scrap_percentage'] = (total_scrap / total_issued) * 100
            
            # Processing efficiency (compare actual vs expected time)
            if job_work.expected_return and job_work.sent_date and job_work.received_date:
                expected_days = (job_work.expected_return - job_work.sent_date).days
                actual_days = (job_work.received_date - job_work.sent_date).days
                
                if expected_days > 0:
                    metrics['time_efficiency'] = (expected_days / actual_days) * 100
            
            # Quality efficiency (based on inspection results)
            quality_inspections = []
            for batch in job_batches:
                inspections = QualityInspection.query.filter_by(job_batch_id=batch.id).all()
                quality_inspections.extend(inspections)
            
            if quality_inspections:
                avg_pass_rate = sum(i.pass_percentage or 0 for i in quality_inspections) / len(quality_inspections)
                metrics['quality_efficiency'] = avg_pass_rate
            
            # Overall processing efficiency
            efficiency_factors = [
                metrics['material_utilization'],
                metrics['time_efficiency'] if metrics['time_efficiency'] > 0 else 100,
                metrics['quality_efficiency'] if metrics['quality_efficiency'] > 0 else 100
            ]
            
            metrics['processing_efficiency'] = sum(efficiency_factors) / len(efficiency_factors)
            
            # Round all metrics
            for key in metrics:
                metrics[key] = round(metrics[key], 2)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating material efficiency: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_flow_summary_stats(material_flows):
        """Calculate summary statistics for material flow report"""
        try:
            if not material_flows:
                return {}
            
            summary = {
                'total_job_works': len(material_flows),
                'total_materials_processed': 0,
                'total_value': 0,
                'average_efficiency': 0,
                'vendor_performance': {},
                'process_performance': {},
                'quality_summary': {
                    'total_inspections': 0,
                    'average_pass_rate': 0,
                    'rejection_rate': 0
                },
                'time_analysis': {
                    'average_processing_time': 0,
                    'on_time_completion_rate': 0
                }
            }
            
            total_efficiency = 0
            total_inspections = 0
            total_pass_percentage = 0
            total_rejections = 0
            processing_times = []
            on_time_completions = 0
            
            vendor_stats = {}
            process_stats = {}
            
            for flow in material_flows:
                job_work = flow['job_work']
                efficiency = flow['efficiency_metrics']
                quality_checkpoints = flow['quality_checkpoints']
                
                # Aggregate totals
                summary['total_materials_processed'] += job_work['quantity_sent']
                summary['total_value'] += job_work['total_value']
                
                if efficiency.get('processing_efficiency'):
                    total_efficiency += efficiency['processing_efficiency']
                
                # Vendor performance
                vendor = job_work['vendor']
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {'jobs': 0, 'total_efficiency': 0, 'total_value': 0}
                
                vendor_stats[vendor]['jobs'] += 1
                vendor_stats[vendor]['total_efficiency'] += efficiency.get('processing_efficiency', 0)
                vendor_stats[vendor]['total_value'] += job_work['total_value']
                
                # Process performance
                process = job_work['process']
                if process not in process_stats:
                    process_stats[process] = {'jobs': 0, 'total_efficiency': 0, 'avg_time': 0}
                
                process_stats[process]['jobs'] += 1
                process_stats[process]['total_efficiency'] += efficiency.get('processing_efficiency', 0)
                
                # Quality analysis
                for checkpoint in quality_checkpoints:
                    total_inspections += 1
                    if checkpoint['pass_percentage']:
                        total_pass_percentage += checkpoint['pass_percentage']
                    if checkpoint['overall_status'] == 'rejected':
                        total_rejections += 1
                
                # Time analysis
                if efficiency.get('time_efficiency'):
                    processing_times.append(efficiency['time_efficiency'])
                    if efficiency['time_efficiency'] >= 100:  # On time or early
                        on_time_completions += 1
            
            # Calculate averages
            if summary['total_job_works'] > 0:
                summary['average_efficiency'] = round(total_efficiency / summary['total_job_works'], 2)
            
            # Vendor performance summary
            for vendor, stats in vendor_stats.items():
                summary['vendor_performance'][vendor] = {
                    'job_count': stats['jobs'],
                    'average_efficiency': round(stats['total_efficiency'] / stats['jobs'], 2) if stats['jobs'] > 0 else 0,
                    'total_value': round(stats['total_value'], 2),
                    'value_percentage': round((stats['total_value'] / summary['total_value']) * 100, 2) if summary['total_value'] > 0 else 0
                }
            
            # Process performance summary
            for process, stats in process_stats.items():
                summary['process_performance'][process] = {
                    'job_count': stats['jobs'],
                    'average_efficiency': round(stats['total_efficiency'] / stats['jobs'], 2) if stats['jobs'] > 0 else 0
                }
            
            # Quality summary
            if total_inspections > 0:
                summary['quality_summary']['total_inspections'] = total_inspections
                summary['quality_summary']['average_pass_rate'] = round(total_pass_percentage / total_inspections, 2)
                summary['quality_summary']['rejection_rate'] = round((total_rejections / total_inspections) * 100, 2)
            
            # Time analysis
            if processing_times:
                summary['time_analysis']['average_processing_time'] = round(sum(processing_times) / len(processing_times), 2)
                summary['time_analysis']['on_time_completion_rate'] = round((on_time_completions / len(processing_times)) * 100, 2)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error calculating summary stats: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_flow_insights(material_flows):
        """Generate insights and recommendations from material flow analysis"""
        try:
            insights = {
                'efficiency_insights': [],
                'quality_insights': [],
                'cost_insights': [],
                'vendor_insights': [],
                'process_insights': [],
                'recommendations': []
            }
            
            if not material_flows:
                return insights
            
            # Analyze efficiency patterns
            low_efficiency_jobs = [f for f in material_flows if f['efficiency_metrics'].get('processing_efficiency', 0) < 70]
            if low_efficiency_jobs:
                insights['efficiency_insights'].append(f"{len(low_efficiency_jobs)} jobs have efficiency below 70%")
                insights['recommendations'].append("Investigate low-efficiency jobs and implement process improvements")
            
            # Analyze quality patterns
            quality_issues = []
            for flow in material_flows:
                for checkpoint in flow['quality_checkpoints']:
                    if checkpoint['overall_status'] == 'rejected':
                        quality_issues.append(checkpoint)
            
            if quality_issues:
                insights['quality_insights'].append(f"{len(quality_issues)} quality rejections found")
                
                # Group by vendor
                vendor_rejections = {}
                for issue in quality_issues:
                    vendor = issue['vendor']
                    vendor_rejections[vendor] = vendor_rejections.get(vendor, 0) + 1
                
                worst_vendor = max(vendor_rejections.items(), key=lambda x: x[1]) if vendor_rejections else None
                if worst_vendor:
                    insights['vendor_insights'].append(f"{worst_vendor[0]} has highest rejection count: {worst_vendor[1]}")
                    insights['recommendations'].append(f"Conduct quality audit with {worst_vendor[0]}")
            
            # Analyze cost efficiency
            high_cost_jobs = [f for f in material_flows if f['cost_breakdown'].get('cost_per_unit', 0) > 100]  # Threshold
            if high_cost_jobs:
                insights['cost_insights'].append(f"{len(high_cost_jobs)} jobs have high cost per unit")
                insights['recommendations'].append("Review pricing with high-cost vendors")
            
            # Analyze vendor performance
            vendor_performance = {}
            for flow in material_flows:
                vendor = flow['job_work']['vendor']
                if vendor not in vendor_performance:
                    vendor_performance[vendor] = {'jobs': 0, 'avg_efficiency': 0, 'efficiency_sum': 0}
                
                vendor_performance[vendor]['jobs'] += 1
                efficiency = flow['efficiency_metrics'].get('processing_efficiency', 0)
                vendor_performance[vendor]['efficiency_sum'] += efficiency
            
            # Calculate average efficiency per vendor
            for vendor, data in vendor_performance.items():
                if data['jobs'] > 0:
                    data['avg_efficiency'] = data['efficiency_sum'] / data['jobs']
            
            # Find best and worst performers
            best_vendor = max(vendor_performance.items(), key=lambda x: x[1]['avg_efficiency']) if vendor_performance else None
            worst_vendor = min(vendor_performance.items(), key=lambda x: x[1]['avg_efficiency']) if vendor_performance else None
            
            if best_vendor:
                insights['vendor_insights'].append(f"Best performer: {best_vendor[0]} ({best_vendor[1]['avg_efficiency']:.1f}% efficiency)")
            
            if worst_vendor:
                insights['vendor_insights'].append(f"Needs improvement: {worst_vendor[0]} ({worst_vendor[1]['avg_efficiency']:.1f}% efficiency)")
                insights['recommendations'].append(f"Develop improvement plan for {worst_vendor[0]}")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating flow insights: {str(e)}")
            return {}
    
    @staticmethod
    def generate_efficiency_yield_report(analysis_period_days=90):
        """Generate comprehensive efficiency and yield analysis report"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=analysis_period_days)
            
            # Get all completed job works in the period
            completed_jobs = JobWork.query.filter(
                JobWork.status == 'completed',
                JobWork.received_date >= start_date,
                JobWork.received_date <= end_date
            ).all()
            
            report = {
                'report_info': {
                    'generated_at': datetime.utcnow().isoformat(),
                    'analysis_period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'duration_days': analysis_period_days
                    }
                },
                'overall_metrics': {},
                'vendor_analysis': {},
                'process_analysis': {},
                'item_analysis': {},
                'trends_analysis': {},
                'benchmarking': {},
                'improvement_opportunities': []
            }
            
            if not completed_jobs:
                return {'success': True, 'report': report}
            
            # Calculate overall metrics
            overall_metrics = AdvancedReportingService._calculate_overall_efficiency_metrics(completed_jobs)
            report['overall_metrics'] = overall_metrics
            
            # Vendor-wise analysis
            vendor_analysis = AdvancedReportingService._analyze_vendor_efficiency(completed_jobs)
            report['vendor_analysis'] = vendor_analysis
            
            # Process-wise analysis
            process_analysis = AdvancedReportingService._analyze_process_efficiency(completed_jobs)
            report['process_analysis'] = process_analysis
            
            # Item-wise analysis
            item_analysis = AdvancedReportingService._analyze_item_efficiency(completed_jobs)
            report['item_analysis'] = item_analysis
            
            # Trends analysis
            trends_analysis = AdvancedReportingService._analyze_efficiency_trends(start_date, end_date)
            report['trends_analysis'] = trends_analysis
            
            # Benchmarking
            benchmarking = AdvancedReportingService._perform_efficiency_benchmarking(vendor_analysis, process_analysis)
            report['benchmarking'] = benchmarking
            
            # Improvement opportunities
            opportunities = AdvancedReportingService._identify_improvement_opportunities(
                vendor_analysis, process_analysis, overall_metrics
            )
            report['improvement_opportunities'] = opportunities
            
            return {'success': True, 'report': report}
            
        except Exception as e:
            logger.error(f"Error generating efficiency yield report: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_overall_efficiency_metrics(completed_jobs):
        """Calculate overall efficiency metrics across all jobs"""
        try:
            metrics = {
                'total_jobs': len(completed_jobs),
                'total_material_processed': 0,
                'total_material_output': 0,
                'overall_yield': 0,
                'average_scrap_rate': 0,
                'material_utilization': 0,
                'cost_efficiency': 0,
                'time_efficiency': 0
            }
            
            total_sent = sum(job.quantity_sent for job in completed_jobs)
            total_received = sum(job.quantity_received for job in completed_jobs)
            total_cost = sum(job.total_cost for job in completed_jobs)
            
            time_efficiencies = []
            scrap_rates = []
            
            for job in completed_jobs:
                # Time efficiency
                if job.expected_return and job.sent_date and job.received_date:
                    expected_days = (job.expected_return - job.sent_date).days
                    actual_days = (job.received_date - job.sent_date).days
                    if expected_days > 0 and actual_days > 0:
                        time_efficiency = min((expected_days / actual_days) * 100, 200)  # Cap at 200%
                        time_efficiencies.append(time_efficiency)
                
                # Scrap rate from batches
                job_batches = JobWorkBatch.query.filter_by(job_work_id=job.id).all()
                total_scrap = sum(batch.quantity_scrap or 0 for batch in job_batches)
                if job.quantity_sent > 0:
                    scrap_rate = (total_scrap / job.quantity_sent) * 100
                    scrap_rates.append(scrap_rate)
            
            metrics['total_material_processed'] = total_sent
            metrics['total_material_output'] = total_received
            
            if total_sent > 0:
                metrics['overall_yield'] = round((total_received / total_sent) * 100, 2)
                metrics['material_utilization'] = round((total_received / total_sent) * 100, 2)
            
            if scrap_rates:
                metrics['average_scrap_rate'] = round(sum(scrap_rates) / len(scrap_rates), 2)
            
            if time_efficiencies:
                metrics['time_efficiency'] = round(sum(time_efficiencies) / len(time_efficiencies), 2)
            
            if total_sent > 0 and total_cost > 0:
                cost_per_unit = total_cost / total_sent
                # Cost efficiency relative to baseline (lower cost = higher efficiency)
                baseline_cost = 100  # Define baseline cost per unit
                metrics['cost_efficiency'] = round(max(0, (baseline_cost / cost_per_unit) * 100), 2)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating overall efficiency metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _analyze_vendor_efficiency(completed_jobs):
        """Analyze efficiency metrics by vendor"""
        try:
            vendor_metrics = {}
            
            for job in completed_jobs:
                vendor = job.customer_name
                
                if vendor not in vendor_metrics:
                    vendor_metrics[vendor] = {
                        'job_count': 0,
                        'total_sent': 0,
                        'total_received': 0,
                        'total_cost': 0,
                        'yield_rates': [],
                        'time_efficiencies': [],
                        'scrap_rates': [],
                        'quality_scores': []
                    }
                
                vendor_data = vendor_metrics[vendor]
                vendor_data['job_count'] += 1
                vendor_data['total_sent'] += job.quantity_sent
                vendor_data['total_received'] += job.quantity_received
                vendor_data['total_cost'] += job.total_cost
                
                # Yield rate
                if job.quantity_sent > 0:
                    yield_rate = (job.quantity_received / job.quantity_sent) * 100
                    vendor_data['yield_rates'].append(yield_rate)
                
                # Time efficiency
                if job.expected_return and job.sent_date and job.received_date:
                    expected_days = (job.expected_return - job.sent_date).days
                    actual_days = (job.received_date - job.sent_date).days
                    if expected_days > 0 and actual_days > 0:
                        time_efficiency = (expected_days / actual_days) * 100
                        vendor_data['time_efficiencies'].append(time_efficiency)
                
                # Quality scores
                job_batches = JobWorkBatch.query.filter_by(job_work_id=job.id).all()
                for batch in job_batches:
                    inspections = QualityInspection.query.filter_by(job_batch_id=batch.id).all()
                    for inspection in inspections:
                        if inspection.pass_percentage:
                            vendor_data['quality_scores'].append(inspection.pass_percentage)
            
            # Calculate summary metrics for each vendor
            for vendor, data in vendor_metrics.items():
                summary = {
                    'job_count': data['job_count'],
                    'average_yield': round(sum(data['yield_rates']) / len(data['yield_rates']), 2) if data['yield_rates'] else 0,
                    'average_time_efficiency': round(sum(data['time_efficiencies']) / len(data['time_efficiencies']), 2) if data['time_efficiencies'] else 0,
                    'average_quality_score': round(sum(data['quality_scores']) / len(data['quality_scores']), 2) if data['quality_scores'] else 0,
                    'cost_per_unit': round(data['total_cost'] / data['total_sent'], 2) if data['total_sent'] > 0 else 0,
                    'total_value': round(data['total_cost'], 2)
                }
                
                # Overall efficiency score (composite)
                efficiency_components = [
                    summary['average_yield'],
                    summary['average_time_efficiency'],
                    summary['average_quality_score']
                ]
                
                valid_components = [c for c in efficiency_components if c > 0]
                summary['overall_efficiency_score'] = round(sum(valid_components) / len(valid_components), 2) if valid_components else 0
                
                vendor_metrics[vendor] = summary
            
            return vendor_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing vendor efficiency: {str(e)}")
            return {}
    
    @staticmethod
    def _analyze_process_efficiency(completed_jobs):
        """Analyze efficiency metrics by process"""
        try:
            process_metrics = {}
            
            for job in completed_jobs:
                process = job.process
                
                if process not in process_metrics:
                    process_metrics[process] = {
                        'job_count': 0,
                        'total_sent': 0,
                        'total_received': 0,
                        'yield_rates': [],
                        'processing_times': [],
                        'quality_scores': [],
                        'vendors': set()
                    }
                
                process_data = process_metrics[process]
                process_data['job_count'] += 1
                process_data['total_sent'] += job.quantity_sent
                process_data['total_received'] += job.quantity_received
                process_data['vendors'].add(job.customer_name)
                
                # Yield rate
                if job.quantity_sent > 0:
                    yield_rate = (job.quantity_received / job.quantity_sent) * 100
                    process_data['yield_rates'].append(yield_rate)
                
                # Processing time
                if job.sent_date and job.received_date:
                    processing_days = (job.received_date - job.sent_date).days
                    process_data['processing_times'].append(processing_days)
            
            # Calculate summary metrics for each process
            for process, data in process_metrics.items():
                summary = {
                    'job_count': data['job_count'],
                    'vendor_count': len(data['vendors']),
                    'average_yield': round(sum(data['yield_rates']) / len(data['yield_rates']), 2) if data['yield_rates'] else 0,
                    'average_processing_time': round(sum(data['processing_times']) / len(data['processing_times']), 2) if data['processing_times'] else 0,
                    'total_volume': data['total_sent'],
                    'complexity_score': len(data['vendors'])  # More vendors = more complex process
                }
                
                process_metrics[process] = summary
            
            return process_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing process efficiency: {str(e)}")
            return {}
    
    @staticmethod
    def _analyze_item_efficiency(completed_jobs):
        """Analyze efficiency metrics by item/material"""
        try:
            item_metrics = {}
            
            for job in completed_jobs:
                item_id = job.item_id
                item_name = job.item.name
                
                if item_id not in item_metrics:
                    item_metrics[item_id] = {
                        'item_name': item_name,
                        'item_code': job.item.code,
                        'job_count': 0,
                        'total_sent': 0,
                        'total_received': 0,
                        'yield_rates': [],
                        'processes': set(),
                        'vendors': set()
                    }
                
                item_data = item_metrics[item_id]
                item_data['job_count'] += 1
                item_data['total_sent'] += job.quantity_sent
                item_data['total_received'] += job.quantity_received
                item_data['processes'].add(job.process)
                item_data['vendors'].add(job.customer_name)
                
                # Yield rate
                if job.quantity_sent > 0:
                    yield_rate = (job.quantity_received / job.quantity_sent) * 100
                    item_data['yield_rates'].append(yield_rate)
            
            # Calculate summary metrics for each item
            for item_id, data in item_metrics.items():
                summary = {
                    'item_name': data['item_name'],
                    'item_code': data['item_code'],
                    'job_count': data['job_count'],
                    'process_count': len(data['processes']),
                    'vendor_count': len(data['vendors']),
                    'average_yield': round(sum(data['yield_rates']) / len(data['yield_rates']), 2) if data['yield_rates'] else 0,
                    'total_volume': data['total_sent'],
                    'utilization_score': data['job_count']  # Frequency of use
                }
                
                item_metrics[item_id] = summary
            
            return item_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing item efficiency: {str(e)}")
            return {}
    
    @staticmethod
    def _analyze_efficiency_trends(start_date, end_date):
        """Analyze efficiency trends over time"""
        try:
            trends = {
                'weekly_trends': [],
                'monthly_trends': [],
                'overall_trend': 'stable'
            }
            
            # Weekly trends
            current_week = start_date
            while current_week <= end_date:
                week_end = min(current_week + timedelta(days=6), end_date)
                
                week_jobs = JobWork.query.filter(
                    JobWork.status == 'completed',
                    JobWork.received_date >= current_week,
                    JobWork.received_date <= week_end
                ).all()
                
                if week_jobs:
                    total_sent = sum(job.quantity_sent for job in week_jobs)
                    total_received = sum(job.quantity_received for job in week_jobs)
                    yield_rate = (total_received / total_sent) * 100 if total_sent > 0 else 0
                    
                    trends['weekly_trends'].append({
                        'week_start': current_week.isoformat(),
                        'week_end': week_end.isoformat(),
                        'job_count': len(week_jobs),
                        'yield_rate': round(yield_rate, 2),
                        'volume_processed': total_sent
                    })
                
                current_week = week_end + timedelta(days=1)
            
            # Determine overall trend
            if len(trends['weekly_trends']) >= 2:
                first_half_avg = sum(w['yield_rate'] for w in trends['weekly_trends'][:len(trends['weekly_trends'])//2])
                second_half_avg = sum(w['yield_rate'] for w in trends['weekly_trends'][len(trends['weekly_trends'])//2:])
                
                first_half_avg /= len(trends['weekly_trends'])//2
                second_half_avg /= len(trends['weekly_trends']) - len(trends['weekly_trends'])//2
                
                if second_half_avg > first_half_avg + 2:
                    trends['overall_trend'] = 'improving'
                elif second_half_avg < first_half_avg - 2:
                    trends['overall_trend'] = 'declining'
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing efficiency trends: {str(e)}")
            return {}
    
    @staticmethod
    def _perform_efficiency_benchmarking(vendor_analysis, process_analysis):
        """Perform benchmarking analysis"""
        try:
            benchmarks = {
                'top_performers': {
                    'vendors': [],
                    'processes': []
                },
                'industry_standards': {
                    'target_yield': 95.0,
                    'target_time_efficiency': 100.0,
                    'target_quality_score': 98.0
                },
                'performance_gaps': []
            }
            
            # Top performing vendors
            if vendor_analysis:
                sorted_vendors = sorted(
                    vendor_analysis.items(),
                    key=lambda x: x[1].get('overall_efficiency_score', 0),
                    reverse=True
                )
                
                benchmarks['top_performers']['vendors'] = [
                    {
                        'vendor': vendor,
                        'efficiency_score': data['overall_efficiency_score'],
                        'yield': data['average_yield']
                    }
                    for vendor, data in sorted_vendors[:5]  # Top 5
                ]
            
            # Top performing processes
            if process_analysis:
                sorted_processes = sorted(
                    process_analysis.items(),
                    key=lambda x: x[1].get('average_yield', 0),
                    reverse=True
                )
                
                benchmarks['top_performers']['processes'] = [
                    {
                        'process': process,
                        'yield': data['average_yield'],
                        'processing_time': data['average_processing_time']
                    }
                    for process, data in sorted_processes[:5]  # Top 5
                ]
            
            # Identify performance gaps
            for vendor, data in vendor_analysis.items():
                if data['average_yield'] < benchmarks['industry_standards']['target_yield']:
                    gap = benchmarks['industry_standards']['target_yield'] - data['average_yield']
                    benchmarks['performance_gaps'].append({
                        'type': 'vendor_yield',
                        'entity': vendor,
                        'current_value': data['average_yield'],
                        'target_value': benchmarks['industry_standards']['target_yield'],
                        'gap': round(gap, 2),
                        'improvement_potential': f"{gap:.1f}% yield improvement"
                    })
            
            return benchmarks
            
        except Exception as e:
            logger.error(f"Error performing benchmarking: {str(e)}")
            return {}
    
    @staticmethod
    def _identify_improvement_opportunities(vendor_analysis, process_analysis, overall_metrics):
        """Identify specific improvement opportunities"""
        try:
            opportunities = []
            
            # Low-performing vendors
            for vendor, data in vendor_analysis.items():
                if data.get('overall_efficiency_score', 0) < 70:
                    opportunities.append({
                        'category': 'Vendor Performance',
                        'priority': 'High',
                        'description': f"{vendor} has low efficiency score ({data['overall_efficiency_score']:.1f}%)",
                        'recommended_action': 'Conduct performance review and implement improvement plan',
                        'potential_impact': 'High',
                        'estimated_benefit': f"Potential 15-25% efficiency improvement"
                    })
            
            # Process optimization
            for process, data in process_analysis.items():
                if data.get('average_yield', 0) < 85:
                    opportunities.append({
                        'category': 'Process Optimization',
                        'priority': 'Medium',
                        'description': f"{process} process has low yield ({data['average_yield']:.1f}%)",
                        'recommended_action': 'Analyze process bottlenecks and optimize workflow',
                        'potential_impact': 'Medium',
                        'estimated_benefit': f"Potential 10-15% yield improvement"
                    })
            
            # Overall efficiency
            if overall_metrics.get('overall_yield', 0) < 90:
                opportunities.append({
                    'category': 'Overall Efficiency',
                    'priority': 'High',
                    'description': f"Overall yield is below target ({overall_metrics['overall_yield']:.1f}% vs 90% target)",
                    'recommended_action': 'Implement comprehensive quality and efficiency program',
                    'potential_impact': 'High',
                    'estimated_benefit': 'Potential 5-10% overall efficiency improvement'
                })
            
            # Material utilization
            if overall_metrics.get('average_scrap_rate', 0) > 5:
                opportunities.append({
                    'category': 'Material Utilization',
                    'priority': 'Medium',
                    'description': f"High scrap rate ({overall_metrics['average_scrap_rate']:.1f}% vs 5% target)",
                    'recommended_action': 'Implement scrap reduction program and improve process controls',
                    'potential_impact': 'Medium',
                    'estimated_benefit': 'Potential 2-5% cost reduction'
                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error identifying improvement opportunities: {str(e)}")
            return []