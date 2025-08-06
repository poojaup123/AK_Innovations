"""
Enhanced Manufacturing Intelligence Service
Real-time analytics, bottleneck detection, and predictive insights
"""
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from sqlalchemy import func, and_, or_

logger = logging.getLogger(__name__)

class ManufacturingIntelligence:
    """Advanced manufacturing analytics and intelligence system"""
    
    def __init__(self):
        self.bottleneck_threshold = 0.7  # 70% capacity utilization threshold
        self.efficiency_alert_threshold = 75.0  # Alert if efficiency drops below 75%
        
    def analyze_process_bottlenecks(self, time_period_days=7):
        """
        Identify bottlenecks across all manufacturing processes
        
        Args:
            time_period_days: Analysis period in days
            
        Returns:
            Dict with bottleneck analysis
        """
        try:
            from models import JobWork, JobWorkProcess
            from models.intelligence import ProcessEfficiencyMetric
            
            start_date = datetime.utcnow() - timedelta(days=time_period_days)
            
            # Analyze each process
            processes = ['cutting', 'bending', 'welding', 'zinc', 'painting', 'assembly', 'machining', 'polishing']
            process_analysis = []
            
            for process_name in processes:
                # Get active job work processes
                active_processes = JobWorkProcess.query.join(JobWork).filter(
                    JobWorkProcess.process_name == process_name,
                    JobWork.created_at >= start_date,
                    JobWorkProcess.status.in_(['pending', 'in_progress'])
                ).all()
                
                # Calculate metrics
                total_jobs = len(active_processes)
                in_progress_jobs = len([p for p in active_processes if p.status == 'in_progress'])
                pending_jobs = len([p for p in active_processes if p.status == 'pending'])
                
                # Get efficiency metrics
                efficiency_metrics = ProcessEfficiencyMetric.query.filter(
                    ProcessEfficiencyMetric.process_name == process_name,
                    ProcessEfficiencyMetric.recorded_at >= start_date
                ).all()
                
                avg_efficiency = 0
                avg_throughput = 0
                if efficiency_metrics:
                    avg_efficiency = sum(m.efficiency_percentage or 0 for m in efficiency_metrics) / len(efficiency_metrics)
                    throughputs = [m.throughput_per_hour for m in efficiency_metrics if m.throughput_per_hour]
                    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
                
                # Calculate capacity utilization
                capacity_utilization = (in_progress_jobs / max(total_jobs, 1)) * 100 if total_jobs > 0 else 0
                
                # Determine bottleneck status
                is_bottleneck = (
                    capacity_utilization > self.bottleneck_threshold * 100 or
                    pending_jobs > in_progress_jobs * 2 or
                    avg_efficiency < self.efficiency_alert_threshold
                )
                
                process_analysis.append({
                    'process_name': process_name,
                    'total_jobs': total_jobs,
                    'in_progress_jobs': in_progress_jobs,
                    'pending_jobs': pending_jobs,
                    'capacity_utilization': capacity_utilization,
                    'average_efficiency': avg_efficiency,
                    'average_throughput': avg_throughput,
                    'is_bottleneck': is_bottleneck,
                    'bottleneck_severity': self._calculate_bottleneck_severity(
                        capacity_utilization, pending_jobs, avg_efficiency
                    ),
                    'recommended_actions': self._generate_bottleneck_recommendations(
                        process_name, capacity_utilization, pending_jobs, avg_efficiency
                    )
                })
            
            # Sort by bottleneck severity
            process_analysis.sort(key=lambda x: x['bottleneck_severity'], reverse=True)
            
            # Summary statistics
            bottlenecks = [p for p in process_analysis if p['is_bottleneck']]
            
            return {
                'analysis_period_days': time_period_days,
                'total_processes': len(processes),
                'processes_with_bottlenecks': len(bottlenecks),
                'most_critical_bottleneck': bottlenecks[0]['process_name'] if bottlenecks else None,
                'average_capacity_utilization': sum(p['capacity_utilization'] for p in process_analysis) / max(len(process_analysis), 1),
                'processes': process_analysis,
                'bottlenecks': bottlenecks,
                'recommendations': self._generate_system_recommendations(process_analysis)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing process bottlenecks: {e}")
            return {'error': f'Bottleneck analysis failed: {str(e)}'}
    
    def get_real_time_material_flow(self):
        """
        Get real-time material flow across all manufacturing stages
        """
        try:
            from models import Item, JobWork, Production
            from models.grn import GRN
            from app import db
            
            # Get material states
            material_states = []
            
            # Raw materials ready for production
            raw_materials = Item.query.filter(Item.qty_raw > 0).all()
            
            # WIP materials in different processes
            wip_processes = [
                ('cutting', 'qty_wip_cutting'),
                ('bending', 'qty_wip_bending'),
                ('welding', 'qty_wip_welding'),
                ('zinc', 'qty_wip_zinc'),
                ('painting', 'qty_wip_painting'),
                ('assembly', 'qty_wip_assembly'),
                ('machining', 'qty_wip_machining'),
                ('polishing', 'qty_wip_polishing')
            ]
            
            process_wip = {}
            for process_name, wip_field in wip_processes:
                total_wip = db.session.query(func.sum(getattr(Item, wip_field))).scalar() or 0
                items_in_process = Item.query.filter(getattr(Item, wip_field) > 0).count()
                
                process_wip[process_name] = {
                    'total_quantity': total_wip,
                    'items_count': items_in_process,
                    'process_name': process_name.title()
                }
            
            # Finished goods ready for dispatch
            finished_goods = db.session.query(func.sum(Item.qty_finished)).scalar() or 0
            finished_items_count = Item.query.filter(Item.qty_finished > 0).count()
            
            # Active job works by status
            job_work_flow = {}
            job_statuses = ['sent', 'partial_received', 'completed']
            for status in job_statuses:
                count = JobWork.query.filter_by(status=status).count()
                job_work_flow[status] = count
            
            # Recent GRN activities (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_grns = GRN.query.filter(GRN.created_at >= yesterday).count()
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'raw_materials': {
                    'total_quantity': sum(item.qty_raw for item in raw_materials),
                    'items_count': len(raw_materials),
                    'ready_for_production': True
                },
                'wip_by_process': process_wip,
                'finished_goods': {
                    'total_quantity': finished_goods,
                    'items_count': finished_items_count,
                    'ready_for_dispatch': True
                },
                'job_work_flow': job_work_flow,
                'recent_grn_activity': recent_grns,
                'flow_velocity': self._calculate_flow_velocity(),
                'bottleneck_processes': self._identify_current_bottlenecks(process_wip)
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time material flow: {e}")
            return {'error': f'Material flow analysis failed: {str(e)}'}
    
    def generate_predictive_alerts(self):
        """
        Generate predictive alerts based on manufacturing patterns
        """
        try:
            from models import Item, JobWork, Supplier
            from models.intelligence import SupplierPerformanceMetric, ManufacturingAlert
            from app import db
            
            alerts = []
            
            # 1. Low stock predictions
            for item in Item.query.all():
                consumption_rate = self._calculate_consumption_rate(item.id)
                if consumption_rate > 0:
                    days_until_stockout = item.available_stock / consumption_rate
                    if days_until_stockout <= 7:  # Alert if stockout within 7 days
                        alert = ManufacturingAlert(
                            alert_type='material_shortage',
                            severity='high' if days_until_stockout <= 3 else 'medium',
                            title=f'Predicted Stock-out: {item.name}',
                            description=f'Item {item.name} will run out of stock in approximately {days_until_stockout:.1f} days based on current consumption rate.',
                            item_id=item.id,
                            threshold_value=7.0,
                            actual_value=days_until_stockout,
                            recommended_action=f'Reorder {item.name} immediately. Suggested quantity: {consumption_rate * 30:.0f} {item.unit_of_measure}'
                        )
                        alerts.append(alert)
            
            # 2. Quality deterioration alerts
            poor_performers = SupplierPerformanceMetric.query.filter(
                SupplierPerformanceMetric.quality_pass_rate < 90
            ).all()
            
            for metric in poor_performers:
                alert = ManufacturingAlert(
                    alert_type='quality_issue',
                    severity='medium',
                    title=f'Supplier Quality Decline: {metric.supplier.name}',
                    description=f'Supplier {metric.supplier.name} quality pass rate has dropped to {metric.quality_pass_rate:.1f}%',
                    supplier_id=metric.supplier_id,
                    threshold_value=90.0,
                    actual_value=metric.quality_pass_rate,
                    recommended_action='Review supplier quality processes and consider alternative suppliers'
                )
                alerts.append(alert)
            
            # 3. Process efficiency alerts
            efficiency_metrics = ProcessEfficiencyMetric.query.filter(
                ProcessEfficiencyMetric.recorded_at >= datetime.utcnow() - timedelta(days=7),
                ProcessEfficiencyMetric.efficiency_percentage < self.efficiency_alert_threshold
            ).all()
            
            process_efficiencies = defaultdict(list)
            for metric in efficiency_metrics:
                process_efficiencies[metric.process_name].append(metric.efficiency_percentage)
            
            for process_name, efficiencies in process_efficiencies.items():
                avg_efficiency = sum(efficiencies) / len(efficiencies)
                alert = ManufacturingAlert(
                    alert_type='efficiency_drop',
                    severity='medium',
                    title=f'Process Efficiency Drop: {process_name.title()}',
                    description=f'{process_name.title()} process efficiency has dropped to {avg_efficiency:.1f}% (below {self.efficiency_alert_threshold}% threshold)',
                    threshold_value=self.efficiency_alert_threshold,
                    actual_value=avg_efficiency,
                    recommended_action=f'Investigate {process_name} process for equipment issues, training needs, or workflow optimization'
                )
                alerts.append(alert)
            
            # Save new alerts to database
            for alert in alerts:
                # Check if similar alert already exists
                existing = ManufacturingAlert.query.filter(
                    ManufacturingAlert.alert_type == alert.alert_type,
                    ManufacturingAlert.item_id == alert.item_id,
                    ManufacturingAlert.supplier_id == alert.supplier_id,
                    ManufacturingAlert.status == 'active',
                    ManufacturingAlert.created_at >= datetime.utcnow() - timedelta(hours=24)
                ).first()
                
                if not existing:
                    db.session.add(alert)
            
            db.session.commit()
            
            return {
                'total_alerts_generated': len(alerts),
                'alerts_by_type': {
                    'material_shortage': len([a for a in alerts if a.alert_type == 'material_shortage']),
                    'quality_issue': len([a for a in alerts if a.alert_type == 'quality_issue']),
                    'efficiency_drop': len([a for a in alerts if a.alert_type == 'efficiency_drop'])
                },
                'alerts': [
                    {
                        'type': alert.alert_type,
                        'severity': alert.severity,
                        'title': alert.title,
                        'description': alert.description,
                        'recommended_action': alert.recommended_action
                    } for alert in alerts
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating predictive alerts: {e}")
            return {'error': f'Alert generation failed: {str(e)}'}
    
    def _calculate_bottleneck_severity(self, capacity_utilization, pending_jobs, efficiency):
        """Calculate bottleneck severity score (0-100)"""
        severity = 0
        
        # Capacity utilization factor (0-40 points)
        severity += min(40, capacity_utilization * 0.4)
        
        # Pending jobs factor (0-30 points)
        severity += min(30, pending_jobs * 3)
        
        # Efficiency factor (0-30 points) - inverse relationship
        efficiency_penalty = max(0, (100 - efficiency) * 0.3)
        severity += efficiency_penalty
        
        return min(100, severity)
    
    def _generate_bottleneck_recommendations(self, process_name, capacity_util, pending_jobs, efficiency):
        """Generate specific recommendations for bottleneck resolution"""
        recommendations = []
        
        if capacity_util > 80:
            recommendations.append(f"Consider adding additional {process_name} capacity or equipment")
        
        if pending_jobs > 5:
            recommendations.append(f"Prioritize {process_name} jobs or reassign workers from other processes")
        
        if efficiency < 70:
            recommendations.append(f"Investigate {process_name} process for equipment maintenance or training needs")
        
        if not recommendations:
            recommendations.append(f"{process_name} process is operating within normal parameters")
        
        return recommendations
    
    def _generate_system_recommendations(self, process_analysis):
        """Generate system-wide recommendations"""
        bottlenecks = [p for p in process_analysis if p['is_bottleneck']]
        
        if not bottlenecks:
            return ["Manufacturing system is operating smoothly with no critical bottlenecks detected"]
        
        recommendations = []
        
        # Most critical bottleneck
        critical = bottlenecks[0]
        recommendations.append(f"Address {critical['process_name']} bottleneck as top priority")
        
        # Multiple bottlenecks
        if len(bottlenecks) > 2:
            recommendations.append("Multiple bottlenecks detected - consider workflow rebalancing")
        
        # Low overall efficiency
        efficient_processes = [p for p in process_analysis if p['average_efficiency'] > 0]
        if efficient_processes:
            avg_efficiency = sum(p['average_efficiency'] for p in efficient_processes) / len(efficient_processes)
        else:
            avg_efficiency = 0
        
        if avg_efficiency < 75:
            recommendations.append("Overall process efficiency is below target - review training and equipment maintenance")
        
        return recommendations
    
    def _calculate_flow_velocity(self):
        """Calculate overall material flow velocity"""
        try:
            from models import GRN
            
            # Calculate average time from raw material to finished goods
            recent_grns = GRN.query.filter(
                GRN.created_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            return {
                'recent_completions': recent_grns,
                'velocity_trend': 'stable'  # Could be enhanced with more complex calculations
            }
        except:
            return {'recent_completions': 0, 'velocity_trend': 'unknown'}
    
    def _identify_current_bottlenecks(self, process_wip):
        """Identify current bottleneck processes based on WIP levels"""
        if not process_wip:
            return []
        
        max_wip = max(p['total_quantity'] for p in process_wip.values())
        if max_wip == 0:
            return []
        
        bottlenecks = []
        for process_name, data in process_wip.items():
            if data['total_quantity'] > max_wip * 0.7:  # 70% of maximum
                bottlenecks.append(process_name)
        
        return bottlenecks
    
    def _calculate_consumption_rate(self, item_id, days_period=30):
        """Calculate average daily consumption rate for an item"""
        try:
            from models import JobWork, Production, MaterialInspection
            
            # Calculate consumption from job works and productions
            # This is a simplified calculation - could be enhanced with more data sources
            start_date = datetime.utcnow() - timedelta(days=days_period)
            
            # Job work consumption
            job_work_consumption = 0
            job_works = JobWork.query.filter(
                JobWork.item_id == item_id,
                JobWork.created_at >= start_date
            ).all()
            
            for jw in job_works:
                job_work_consumption += jw.quantity_sent or 0
            
            # Calculate daily rate
            daily_rate = job_work_consumption / days_period if days_period > 0 else 0
            
            return daily_rate
            
        except Exception as e:
            logger.error(f"Error calculating consumption rate for item {item_id}: {e}")
            return 0