"""
Vendor Performance Analytics Service
Comprehensive vendor performance tracking, KPIs, and benchmarking
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import JobWork, Supplier
from models.batch import JobWorkBatch, JobWorkLocationHistory
from models.quality import QualityInspection, QualityKPI
import logging

logger = logging.getLogger(__name__)

class VendorAnalyticsService:
    """Comprehensive vendor performance analytics and benchmarking"""
    
    @staticmethod
    def calculate_vendor_performance_kpis(vendor_id=None, start_date=None, end_date=None):
        """Calculate comprehensive vendor performance KPIs"""
        try:
            current_date = datetime.utcnow().date()
            
            # Default date range (last 90 days)
            if not end_date:
                end_date = current_date
            if not start_date:
                start_date = end_date - timedelta(days=90)
            
            # Get vendor filter
            vendor_filter = []
            if vendor_id:
                vendor = Supplier.query.get(vendor_id)
                if not vendor:
                    return {'success': False, 'error': 'Vendor not found'}
                vendor_filter = [JobWork.customer_name == vendor.name]
            
            # Base query for job works in date range
            base_query = JobWork.query.filter(
                JobWork.created_at >= start_date,
                JobWork.created_at <= end_date,
                *vendor_filter
            )
            
            job_works = base_query.all()
            
            if not job_works:
                return {
                    'success': True,
                    'vendor_performance': {
                        'summary': {'total_jobs': 0},
                        'vendors': {}
                    }
                }
            
            # Group by vendor
            vendor_performance = {}
            
            for job_work in job_works:
                vendor_name = job_work.customer_name
                
                if vendor_name not in vendor_performance:
                    vendor_performance[vendor_name] = {
                        'summary': {
                            'total_jobs': 0,
                            'completed_jobs': 0,
                            'active_jobs': 0,
                            'total_value': 0,
                            'completion_rate': 0
                        },
                        'delivery_performance': {
                            'on_time_deliveries': 0,
                            'delayed_deliveries': 0,
                            'average_delay_days': 0,
                            'delivery_reliability': 0
                        },
                        'quality_performance': {
                            'quality_pass_rate': 0,
                            'rejection_rate': 0,
                            'rework_rate': 0,
                            'quality_score': 0
                        },
                        'cost_performance': {
                            'cost_per_unit': 0,
                            'cost_variance': 0,
                            'total_penalties': 0,
                            'cost_efficiency': 0
                        },
                        'process_breakdown': {},
                        'monthly_trends': []
                    }
                
                vendor_data = vendor_performance[vendor_name]
                
                # Update summary
                vendor_data['summary']['total_jobs'] += 1
                vendor_data['summary']['total_value'] += job_work.total_cost
                
                if job_work.status == 'completed':
                    vendor_data['summary']['completed_jobs'] += 1
                    
                    # Delivery performance
                    if job_work.expected_return and job_work.received_date:
                        if job_work.received_date <= job_work.expected_return:
                            vendor_data['delivery_performance']['on_time_deliveries'] += 1
                        else:
                            vendor_data['delivery_performance']['delayed_deliveries'] += 1
                            delay_days = (job_work.received_date - job_work.expected_return).days
                            vendor_data['delivery_performance']['average_delay_days'] += delay_days
                else:
                    vendor_data['summary']['active_jobs'] += 1
                
                # Process breakdown
                process = job_work.process
                if process not in vendor_data['process_breakdown']:
                    vendor_data['process_breakdown'][process] = {
                        'job_count': 0,
                        'completion_rate': 0,
                        'average_lead_time': 0
                    }
                
                vendor_data['process_breakdown'][process]['job_count'] += 1
            
            # Calculate final metrics for each vendor
            for vendor_name, vendor_data in vendor_performance.items():
                summary = vendor_data['summary']
                delivery = vendor_data['delivery_performance']
                
                # Completion rate
                if summary['total_jobs'] > 0:
                    summary['completion_rate'] = round(
                        (summary['completed_jobs'] / summary['total_jobs']) * 100, 2
                    )
                
                # Delivery reliability
                total_deliveries = delivery['on_time_deliveries'] + delivery['delayed_deliveries']
                if total_deliveries > 0:
                    delivery['delivery_reliability'] = round(
                        (delivery['on_time_deliveries'] / total_deliveries) * 100, 2
                    )
                    
                    if delivery['delayed_deliveries'] > 0:
                        delivery['average_delay_days'] = round(
                            delivery['average_delay_days'] / delivery['delayed_deliveries'], 1
                        )
                
                # Quality performance
                quality_data = VendorAnalyticsService._calculate_vendor_quality_metrics(
                    vendor_name, start_date, end_date
                )
                vendor_data['quality_performance'].update(quality_data)
                
                # Cost performance
                cost_data = VendorAnalyticsService._calculate_vendor_cost_metrics(
                    vendor_name, start_date, end_date
                )
                vendor_data['cost_performance'].update(cost_data)
                
                # Monthly trends
                trends_data = VendorAnalyticsService._calculate_vendor_trends(
                    vendor_name, start_date, end_date
                )
                vendor_data['monthly_trends'] = trends_data
            
            # Overall summary
            total_jobs = sum(v['summary']['total_jobs'] for v in vendor_performance.values())
            total_completed = sum(v['summary']['completed_jobs'] for v in vendor_performance.values())
            
            overall_summary = {
                'total_vendors': len(vendor_performance),
                'total_jobs': total_jobs,
                'total_completed': total_completed,
                'overall_completion_rate': round((total_completed / total_jobs) * 100, 2) if total_jobs > 0 else 0,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
            return {
                'success': True,
                'vendor_performance': {
                    'summary': overall_summary,
                    'vendors': vendor_performance
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating vendor performance KPIs: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_vendor_quality_metrics(vendor_name, start_date, end_date):
        """Calculate quality metrics for a vendor"""
        try:
            # Get quality inspections for this vendor
            quality_inspections = db.session.query(QualityInspection).join(
                JobWorkBatch
            ).filter(
                JobWorkBatch.vendor_name == vendor_name,
                QualityInspection.inspection_date >= start_date,
                QualityInspection.inspection_date <= end_date
            ).all()
            
            if not quality_inspections:
                return {
                    'quality_pass_rate': 0,
                    'rejection_rate': 0,
                    'rework_rate': 0,
                    'quality_score': 0
                }
            
            total_inspections = len(quality_inspections)
            passed = len([i for i in quality_inspections if i.overall_status == 'passed'])
            rejected = len([i for i in quality_inspections if i.overall_status == 'rejected'])
            rework = len([i for i in quality_inspections if i.overall_status == 'rework_needed'])
            
            # Calculate average quality score
            total_score = sum(i.pass_percentage or 0 for i in quality_inspections)
            avg_quality_score = total_score / total_inspections if total_inspections > 0 else 0
            
            return {
                'quality_pass_rate': round((passed / total_inspections) * 100, 2),
                'rejection_rate': round((rejected / total_inspections) * 100, 2),
                'rework_rate': round((rework / total_inspections) * 100, 2),
                'quality_score': round(avg_quality_score, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics for {vendor_name}: {str(e)}")
            return {'quality_pass_rate': 0, 'rejection_rate': 0, 'rework_rate': 0, 'quality_score': 0}
    
    @staticmethod
    def _calculate_vendor_cost_metrics(vendor_name, start_date, end_date):
        """Calculate cost performance metrics for a vendor"""
        try:
            # Get job works for this vendor
            vendor_jobs = JobWork.query.filter(
                JobWork.customer_name == vendor_name,
                JobWork.created_at >= start_date,
                JobWork.created_at <= end_date
            ).all()
            
            if not vendor_jobs:
                return {
                    'cost_per_unit': 0,
                    'cost_variance': 0,
                    'total_penalties': 0,
                    'cost_efficiency': 0
                }
            
            total_cost = sum(job.total_cost for job in vendor_jobs)
            total_quantity = sum(job.quantity_sent for job in vendor_jobs)
            
            cost_per_unit = total_cost / total_quantity if total_quantity > 0 else 0
            
            # Calculate cost variance (compare with other vendors for same processes)
            cost_variance = VendorAnalyticsService._calculate_cost_variance(
                vendor_name, vendor_jobs
            )
            
            # Calculate penalties (quality failures, delays)
            total_penalties = VendorAnalyticsService._calculate_vendor_penalties(vendor_jobs)
            
            # Cost efficiency score (lower cost with high quality = higher efficiency)
            quality_score = VendorAnalyticsService._get_vendor_quality_score(vendor_name, start_date, end_date)
            cost_efficiency = quality_score / (cost_per_unit + 1) * 100  # Simplified efficiency calculation
            
            return {
                'cost_per_unit': round(cost_per_unit, 2),
                'cost_variance': round(cost_variance, 2),
                'total_penalties': round(total_penalties, 2),
                'cost_efficiency': round(cost_efficiency, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating cost metrics for {vendor_name}: {str(e)}")
            return {'cost_per_unit': 0, 'cost_variance': 0, 'total_penalties': 0, 'cost_efficiency': 0}
    
    @staticmethod
    def _calculate_cost_variance(vendor_name, vendor_jobs):
        """Calculate cost variance compared to market average"""
        try:
            # Get average cost for same processes from other vendors
            process_costs = {}
            for job in vendor_jobs:
                process = job.process
                if process not in process_costs:
                    process_costs[process] = []
                process_costs[process].append(job.rate_per_unit)
            
            total_variance = 0
            process_count = 0
            
            for process, costs in process_costs.items():
                vendor_avg_cost = sum(costs) / len(costs)
                
                # Get market average for this process
                market_jobs = JobWork.query.filter(
                    JobWork.process == process,
                    JobWork.customer_name != vendor_name
                ).all()
                
                if market_jobs:
                    market_avg_cost = sum(job.rate_per_unit for job in market_jobs) / len(market_jobs)
                    variance = ((vendor_avg_cost - market_avg_cost) / market_avg_cost) * 100
                    total_variance += abs(variance)
                    process_count += 1
            
            return total_variance / process_count if process_count > 0 else 0
            
        except Exception as e:
            logger.error(f"Error calculating cost variance: {str(e)}")
            return 0
    
    @staticmethod
    def _calculate_vendor_penalties(vendor_jobs):
        """Calculate total penalties for quality failures and delays"""
        try:
            total_penalties = 0
            
            for job in vendor_jobs:
                # Delay penalties
                if job.expected_return and job.received_date and job.received_date > job.expected_return:
                    delay_days = (job.received_date - job.expected_return).days
                    # Assume 1% penalty per day delayed
                    delay_penalty = job.total_cost * 0.01 * delay_days
                    total_penalties += delay_penalty
                
                # Quality penalties (from quality returns and rework)
                from models.quality import QualityReturn, QualityRework
                
                job_batches = JobWorkBatch.query.filter_by(job_work_id=job.id).all()
                for batch in job_batches:
                    # Return penalties
                    returns = QualityReturn.query.filter_by(job_batch_id=batch.id).all()
                    total_penalties += sum(r.vendor_penalty for r in returns)
                    
                    # Rework costs
                    reworks = QualityRework.query.filter_by(job_batch_id=batch.id).all()
                    total_penalties += sum(r.actual_rework_cost for r in reworks)
            
            return total_penalties
            
        except Exception as e:
            logger.error(f"Error calculating vendor penalties: {str(e)}")
            return 0
    
    @staticmethod
    def _get_vendor_quality_score(vendor_name, start_date, end_date):
        """Get average quality score for vendor"""
        try:
            quality_inspections = db.session.query(QualityInspection).join(
                JobWorkBatch
            ).filter(
                JobWorkBatch.vendor_name == vendor_name,
                QualityInspection.inspection_date >= start_date,
                QualityInspection.inspection_date <= end_date
            ).all()
            
            if not quality_inspections:
                return 0
            
            total_score = sum(i.pass_percentage or 0 for i in quality_inspections)
            return total_score / len(quality_inspections)
            
        except Exception as e:
            logger.error(f"Error getting quality score: {str(e)}")
            return 0
    
    @staticmethod
    def _calculate_vendor_trends(vendor_name, start_date, end_date):
        """Calculate monthly performance trends for vendor"""
        try:
            trends = []
            current_date = start_date
            
            while current_date <= end_date:
                month_end = min(
                    current_date.replace(day=28) + timedelta(days=4),  # Next month
                    end_date
                )
                month_end = month_end.replace(day=1) - timedelta(days=1)  # Last day of current month
                
                # Get jobs for this month
                month_jobs = JobWork.query.filter(
                    JobWork.customer_name == vendor_name,
                    JobWork.created_at >= current_date,
                    JobWork.created_at <= month_end
                ).all()
                
                if month_jobs:
                    completed_jobs = len([j for j in month_jobs if j.status == 'completed'])
                    total_jobs = len(month_jobs)
                    completion_rate = (completed_jobs / total_jobs) * 100 if total_jobs > 0 else 0
                    
                    # Calculate average delivery time for completed jobs
                    delivery_times = []
                    for job in month_jobs:
                        if job.status == 'completed' and job.sent_date and job.received_date:
                            delivery_time = (job.received_date - job.sent_date).days
                            delivery_times.append(delivery_time)
                    
                    avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
                    
                    trends.append({
                        'month': current_date.strftime('%Y-%m'),
                        'total_jobs': total_jobs,
                        'completed_jobs': completed_jobs,
                        'completion_rate': round(completion_rate, 2),
                        'average_delivery_time': round(avg_delivery_time, 1)
                    })
                
                # Move to next month
                current_date = month_end + timedelta(days=1)
                if current_date.day != 1:
                    current_date = current_date.replace(day=1)
            
            return trends
            
        except Exception as e:
            logger.error(f"Error calculating vendor trends: {str(e)}")
            return []
    
    @staticmethod
    def generate_vendor_scorecard(vendor_id, period_months=6):
        """Generate comprehensive vendor scorecard"""
        try:
            vendor = Supplier.query.get(vendor_id)
            if not vendor:
                return {'success': False, 'error': 'Vendor not found'}
            
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=period_months * 30)
            
            # Get performance KPIs
            performance_result = VendorAnalyticsService.calculate_vendor_performance_kpis(
                vendor_id, start_date, end_date
            )
            
            if not performance_result['success']:
                return performance_result
            
            vendor_data = performance_result['vendor_performance']['vendors'].get(vendor.name, {})
            
            # Calculate overall vendor score
            scores = {
                'delivery_score': vendor_data.get('delivery_performance', {}).get('delivery_reliability', 0),
                'quality_score': vendor_data.get('quality_performance', {}).get('quality_score', 0),
                'cost_score': 100 - min(vendor_data.get('cost_performance', {}).get('cost_variance', 0), 100),
                'reliability_score': vendor_data.get('summary', {}).get('completion_rate', 0)
            }
            
            # Weighted overall score
            weights = {'delivery_score': 0.3, 'quality_score': 0.3, 'cost_score': 0.2, 'reliability_score': 0.2}
            overall_score = sum(scores[key] * weights[key] for key in scores.keys())
            
            # Performance rating
            if overall_score >= 90:
                rating = 'Excellent'
                rating_class = 'success'
            elif overall_score >= 80:
                rating = 'Good'
                rating_class = 'primary'
            elif overall_score >= 70:
                rating = 'Satisfactory'
                rating_class = 'warning'
            else:
                rating = 'Needs Improvement'
                rating_class = 'danger'
            
            # Generate recommendations
            recommendations = VendorAnalyticsService._generate_vendor_recommendations(vendor_data, scores)
            
            scorecard = {
                'vendor_info': {
                    'id': vendor.id,
                    'name': vendor.name,
                    'contact_person': vendor.contact_person,
                    'phone': vendor.phone,
                    'email': vendor.email
                },
                'evaluation_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'duration_months': period_months
                },
                'performance_summary': vendor_data,
                'scores': scores,
                'overall_score': round(overall_score, 2),
                'rating': rating,
                'rating_class': rating_class,
                'recommendations': recommendations,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            return {'success': True, 'scorecard': scorecard}
            
        except Exception as e:
            logger.error(f"Error generating vendor scorecard: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _generate_vendor_recommendations(vendor_data, scores):
        """Generate specific recommendations for vendor improvement"""
        recommendations = []
        
        # Delivery performance recommendations
        if scores['delivery_score'] < 80:
            recommendations.append({
                'category': 'Delivery',
                'priority': 'High',
                'issue': 'Poor delivery reliability',
                'recommendation': 'Implement delivery tracking system and penalize late deliveries',
                'expected_improvement': '15-20% improvement in on-time delivery'
            })
        
        # Quality recommendations
        if scores['quality_score'] < 75:
            recommendations.append({
                'category': 'Quality',
                'priority': 'High',
                'issue': 'Quality issues affecting production',
                'recommendation': 'Conduct quality audit and provide training on quality standards',
                'expected_improvement': '10-15% reduction in rejection rate'
            })
        
        # Cost recommendations
        if scores['cost_score'] < 70:
            recommendations.append({
                'category': 'Cost',
                'priority': 'Medium',
                'issue': 'Cost variance above market average',
                'recommendation': 'Renegotiate pricing or find alternative vendors for comparison',
                'expected_improvement': '5-10% cost reduction potential'
            })
        
        # Process-specific recommendations
        process_breakdown = vendor_data.get('process_breakdown', {})
        for process, data in process_breakdown.items():
            if data.get('completion_rate', 0) < 80:
                recommendations.append({
                    'category': 'Process',
                    'priority': 'Medium',
                    'issue': f'Low completion rate in {process} process',
                    'recommendation': f'Review {process} process capabilities and provide additional support',
                    'expected_improvement': 'Improved process efficiency'
                })
        
        return recommendations
    
    @staticmethod
    def compare_vendors(vendor_ids, comparison_metrics=None):
        """Compare multiple vendors across key metrics"""
        try:
            if not comparison_metrics:
                comparison_metrics = [
                    'delivery_reliability', 'quality_score', 'cost_per_unit', 
                    'completion_rate', 'overall_score'
                ]
            
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=90)
            
            vendor_comparison = {
                'comparison_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'vendors': [],
                'best_performers': {},
                'ranking': []
            }
            
            vendor_scores = []
            
            for vendor_id in vendor_ids:
                vendor = Supplier.query.get(vendor_id)
                if not vendor:
                    continue
                
                # Get vendor performance data
                performance_result = VendorAnalyticsService.calculate_vendor_performance_kpis(
                    vendor_id, start_date, end_date
                )
                
                if performance_result['success']:
                    vendor_data = performance_result['vendor_performance']['vendors'].get(vendor.name, {})
                    
                    # Extract metrics for comparison
                    metrics = {
                        'vendor_id': vendor_id,
                        'vendor_name': vendor.name,
                        'delivery_reliability': vendor_data.get('delivery_performance', {}).get('delivery_reliability', 0),
                        'quality_score': vendor_data.get('quality_performance', {}).get('quality_score', 0),
                        'cost_per_unit': vendor_data.get('cost_performance', {}).get('cost_per_unit', 0),
                        'completion_rate': vendor_data.get('summary', {}).get('completion_rate', 0),
                        'total_jobs': vendor_data.get('summary', {}).get('total_jobs', 0)
                    }
                    
                    # Calculate overall score
                    metrics['overall_score'] = (
                        metrics['delivery_reliability'] * 0.3 +
                        metrics['quality_score'] * 0.3 +
                        (100 - min(metrics['cost_per_unit'], 100)) * 0.2 +  # Lower cost = higher score
                        metrics['completion_rate'] * 0.2
                    )
                    
                    vendor_comparison['vendors'].append(metrics)
                    vendor_scores.append((vendor.name, metrics['overall_score']))
            
            # Rank vendors by overall score
            vendor_scores.sort(key=lambda x: x[1], reverse=True)
            vendor_comparison['ranking'] = [
                {'rank': i+1, 'vendor_name': name, 'score': score}
                for i, (name, score) in enumerate(vendor_scores)
            ]
            
            # Identify best performers for each metric
            if vendor_comparison['vendors']:
                for metric in comparison_metrics:
                    if metric == 'cost_per_unit':
                        # For cost, lower is better
                        best_vendor = min(vendor_comparison['vendors'], key=lambda x: x.get(metric, float('inf')))
                    else:
                        # For other metrics, higher is better
                        best_vendor = max(vendor_comparison['vendors'], key=lambda x: x.get(metric, 0))
                    
                    vendor_comparison['best_performers'][metric] = {
                        'vendor_name': best_vendor['vendor_name'],
                        'value': best_vendor.get(metric, 0)
                    }
            
            return {'success': True, 'comparison': vendor_comparison}
            
        except Exception as e:
            logger.error(f"Error comparing vendors: {str(e)}")
            return {'success': False, 'error': str(e)}