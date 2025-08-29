"""
Machine Cost Analysis Service

Advanced analytics and reporting for machine-based costing system,
providing insights for cost optimization and performance monitoring.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from sqlalchemy import func, and_, or_
import statistics

from app import db
from models import (
    Machine, MachineOperator, MachineExpense, OperatorMachineTime, 
    MachineCostAnalysis, BOM, BOMProcess, Item
)
from services.machine_management import MachineManagementService
from services.machine_bom_integration import MachineBOMIntegration


class MachineKPIAnalyzer:
    """Advanced KPI analysis for machine performance and costing"""
    
    @staticmethod
    def calculate_machine_oee(machine_id: int, start_date: date, end_date: date) -> Dict:
        """
        Calculate Overall Equipment Effectiveness (OEE) for a machine
        
        Args:
            machine_id: ID of the machine
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary with OEE metrics
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return {'error': 'Machine not found'}
            
            # Get all operations for the period
            operations = OperatorMachineTime.query.filter(
                OperatorMachineTime.machine_id == machine_id,
                OperatorMachineTime.shift_date >= start_date,
                OperatorMachineTime.shift_date <= end_date,
                OperatorMachineTime.status == 'completed'
            ).all()
            
            if not operations:
                return {
                    'machine_code': machine.machine_code,
                    'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                    'oee_score': 0,
                    'availability': 0,
                    'performance': 0,
                    'quality': 0,
                    'message': 'No operations data available for period'
                }
            
            # Calculate period days and theoretical available time
            period_days = (end_date - start_date).days + 1
            theoretical_hours = period_days * 24  # 24 hours per day
            planned_hours = period_days * 16      # 16 hours planned operation per day
            
            # Calculate Availability
            total_actual_hours = sum(op.actual_hours or 0 for op in operations)
            total_downtime_hours = sum(op.downtime_hours or 0 for op in operations)
            productive_hours = total_actual_hours - total_downtime_hours
            
            availability = (productive_hours / planned_hours) * 100 if planned_hours > 0 else 0
            availability = min(100, availability)  # Cap at 100%
            
            # Calculate Performance (vs ideal cycle time)
            total_units_produced = sum(op.units_produced or 0 for op in operations)
            total_units_planned = sum(op.units_planned or 0 for op in operations)
            
            performance = (total_units_produced / total_units_planned) * 100 if total_units_planned > 0 else 0
            performance = min(100, performance)  # Cap at 100%
            
            # Calculate Quality
            total_good_units = sum(op.units_good or 0 for op in operations)
            quality = (total_good_units / total_units_produced) * 100 if total_units_produced > 0 else 0
            
            # Calculate Overall OEE
            oee_score = (availability * performance * quality) / 10000  # Divide by 10000 since all are percentages
            
            return {
                'machine_code': machine.machine_code,
                'machine_name': machine.name,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': period_days
                },
                'oee_score': round(oee_score, 2),
                'components': {
                    'availability': round(availability, 2),
                    'performance': round(performance, 2),
                    'quality': round(quality, 2)
                },
                'metrics': {
                    'total_operations': len(operations),
                    'total_actual_hours': round(total_actual_hours, 2),
                    'productive_hours': round(productive_hours, 2),
                    'downtime_hours': round(total_downtime_hours, 2),
                    'units_produced': total_units_produced,
                    'units_planned': total_units_planned,
                    'units_good': total_good_units,
                    'scrap_rate': round((total_units_produced - total_good_units) / total_units_produced * 100, 2) if total_units_produced > 0 else 0
                },
                'oee_rating': MachineKPIAnalyzer._get_oee_rating(oee_score)
            }
            
        except Exception as e:
            return {'error': f'Error calculating OEE: {str(e)}'}
    
    @staticmethod
    def _get_oee_rating(oee_score: float) -> str:
        """Get OEE rating based on score"""
        if oee_score >= 85:
            return 'World Class'
        elif oee_score >= 70:
            return 'Good'
        elif oee_score >= 55:
            return 'Fair'
        elif oee_score >= 40:
            return 'Poor'
        else:
            return 'Unacceptable'
    
    @staticmethod
    def analyze_cost_trends(machine_id: int, months: int = 6) -> Dict:
        """
        Analyze cost trends for a machine over time
        
        Args:
            machine_id: ID of the machine
            months: Number of months to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return {'error': 'Machine not found'}
            
            end_date = date.today()
            start_date = end_date - timedelta(days=months * 30)
            
            # Get monthly cost data
            monthly_data = []
            current_date = start_date
            
            while current_date <= end_date:
                month_start = current_date.replace(day=1)
                if current_date.month == 12:
                    month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
                
                # Get operations for this month
                month_operations = OperatorMachineTime.query.filter(
                    OperatorMachineTime.machine_id == machine_id,
                    OperatorMachineTime.shift_date >= month_start,
                    OperatorMachineTime.shift_date <= month_end,
                    OperatorMachineTime.status == 'completed'
                ).all()
                
                # Calculate monthly metrics
                total_hours = sum(op.actual_hours or 0 for op in month_operations)
                total_cost = sum(float(op.total_cost or 0) for op in month_operations)
                total_units = sum(op.units_good or 0 for op in month_operations)
                
                # Get utility expenses for this month
                utility_expenses = MachineExpense.query.filter(
                    MachineExpense.machine_id == machine_id,
                    MachineExpense.expense_type == 'utility',
                    MachineExpense.billing_start_date >= month_start,
                    MachineExpense.billing_end_date <= month_end
                ).all()
                
                utility_cost = sum(float(expense.amount) for expense in utility_expenses)
                
                monthly_data.append({
                    'month': month_start.strftime('%Y-%m'),
                    'month_name': month_start.strftime('%B %Y'),
                    'total_hours': total_hours,
                    'total_cost': total_cost,
                    'utility_cost': utility_cost,
                    'total_units': total_units,
                    'cost_per_hour': total_cost / total_hours if total_hours > 0 else 0,
                    'cost_per_unit': total_cost / total_units if total_units > 0 else 0,
                    'operations_count': len(month_operations)
                })
                
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            # Calculate trends
            trends = MachineKPIAnalyzer._calculate_trends(monthly_data)
            
            # Calculate averages
            recent_3_months = monthly_data[-3:] if len(monthly_data) >= 3 else monthly_data
            recent_avg_cost_per_hour = statistics.mean([m['cost_per_hour'] for m in recent_3_months if m['cost_per_hour'] > 0]) if recent_3_months else 0
            
            return {
                'machine_code': machine.machine_code,
                'machine_name': machine.name,
                'analysis_period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'months': months
                },
                'monthly_data': monthly_data,
                'trends': trends,
                'summary': {
                    'recent_avg_cost_per_hour': round(recent_avg_cost_per_hour, 2),
                    'current_cost_per_hour': round(machine.current_hourly_cost, 2),
                    'total_data_points': len(monthly_data),
                    'trend_direction': trends['cost_per_hour']['direction'],
                    'trend_strength': trends['cost_per_hour']['strength']
                }
            }
            
        except Exception as e:
            return {'error': f'Error analyzing cost trends: {str(e)}'}
    
    @staticmethod
    def _calculate_trends(monthly_data: List[Dict]) -> Dict:
        """Calculate trend direction and strength for various metrics"""
        trends = {}
        
        metrics = ['cost_per_hour', 'cost_per_unit', 'total_hours', 'utility_cost']
        
        for metric in metrics:
            values = [month[metric] for month in monthly_data if month[metric] > 0]
            
            if len(values) < 2:
                trends[metric] = {'direction': 'insufficient_data', 'strength': 0, 'change_percentage': 0}
                continue
            
            # Calculate linear trend
            n = len(values)
            x = list(range(n))
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_x2 = sum(xi ** 2 for xi in x)
            
            # Linear regression slope
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
            
            # Determine direction and strength
            if abs(slope) < 0.1:
                direction = 'stable'
                strength = 'low'
            elif slope > 0:
                direction = 'increasing'
                strength = 'high' if slope > 1 else 'medium'
            else:
                direction = 'decreasing'
                strength = 'high' if slope < -1 else 'medium'
            
            # Calculate percentage change from first to last
            change_percentage = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
            
            trends[metric] = {
                'direction': direction,
                'strength': strength,
                'slope': slope,
                'change_percentage': round(change_percentage, 2)
            }
        
        return trends
    
    @staticmethod
    def benchmark_machine_performance(machine_id: int, benchmark_period_days: int = 30) -> Dict:
        """
        Benchmark machine performance against fleet average and industry standards
        
        Args:
            machine_id: ID of the machine to benchmark
            benchmark_period_days: Period for benchmarking analysis
            
        Returns:
            Dictionary with benchmark analysis
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return {'error': 'Machine not found'}
            
            end_date = date.today()
            start_date = end_date - timedelta(days=benchmark_period_days)
            
            # Get target machine data
            target_data = MachineKPIAnalyzer._get_machine_performance_data(machine_id, start_date, end_date)
            
            # Get fleet data (all machines of same type)
            fleet_machines = Machine.query.filter(
                Machine.machine_type == machine.machine_type,
                Machine.id != machine_id,
                Machine.status.in_(['active', 'idle'])
            ).all()
            
            fleet_data = []
            for fleet_machine in fleet_machines:
                fleet_machine_data = MachineKPIAnalyzer._get_machine_performance_data(
                    fleet_machine.id, start_date, end_date
                )
                if fleet_machine_data['total_operations'] > 0:
                    fleet_data.append(fleet_machine_data)
            
            # Calculate fleet averages
            fleet_averages = {}
            if fleet_data:
                metrics = ['cost_per_hour', 'cost_per_unit', 'efficiency', 'utilization', 'quality_score']
                for metric in metrics:
                    values = [data[metric] for data in fleet_data if data[metric] is not None and data[metric] > 0]
                    fleet_averages[metric] = statistics.mean(values) if values else 0
            
            # Industry benchmarks (typical values for manufacturing)
            industry_benchmarks = {
                'oee_score': 65,  # Industry average OEE
                'utilization': 75,  # Target utilization rate
                'efficiency': 85,   # Target efficiency
                'quality_score': 95,  # Target quality score
                'cost_per_hour': 150,  # Varies by industry
                'downtime_percentage': 10  # Target downtime
            }
            
            # Calculate comparisons
            comparisons = {}
            
            # Fleet comparison
            if fleet_averages:
                for metric, fleet_avg in fleet_averages.items():
                    target_value = target_data.get(metric, 0)
                    if fleet_avg > 0:
                        comparison_percentage = ((target_value - fleet_avg) / fleet_avg) * 100
                        comparisons[f'fleet_{metric}'] = {
                            'target_value': target_value,
                            'fleet_average': fleet_avg,
                            'difference_percentage': round(comparison_percentage, 2),
                            'performance': 'above' if comparison_percentage > 5 else 'below' if comparison_percentage < -5 else 'at_par'
                        }
            
            # Industry benchmark comparison
            for metric, benchmark in industry_benchmarks.items():
                target_value = target_data.get(metric, 0)
                if benchmark > 0 and target_value > 0:
                    comparison_percentage = ((target_value - benchmark) / benchmark) * 100
                    comparisons[f'industry_{metric}'] = {
                        'target_value': target_value,
                        'industry_benchmark': benchmark,
                        'difference_percentage': round(comparison_percentage, 2),
                        'performance': 'above' if comparison_percentage > 0 else 'below'
                    }
            
            return {
                'machine_code': machine.machine_code,
                'machine_name': machine.name,
                'machine_type': machine.machine_type,
                'benchmark_period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': benchmark_period_days
                },
                'target_machine_data': target_data,
                'fleet_size': len(fleet_data),
                'fleet_averages': fleet_averages,
                'industry_benchmarks': industry_benchmarks,
                'comparisons': comparisons,
                'recommendations': MachineKPIAnalyzer._generate_benchmark_recommendations(comparisons)
            }
            
        except Exception as e:
            return {'error': f'Error benchmarking machine performance: {str(e)}'}
    
    @staticmethod
    def _get_machine_performance_data(machine_id: int, start_date: date, end_date: date) -> Dict:
        """Get aggregated performance data for a machine over a period"""
        operations = OperatorMachineTime.query.filter(
            OperatorMachineTime.machine_id == machine_id,
            OperatorMachineTime.shift_date >= start_date,
            OperatorMachineTime.shift_date <= end_date,
            OperatorMachineTime.status == 'completed'
        ).all()
        
        if not operations:
            return {'total_operations': 0}
        
        total_hours = sum(op.actual_hours or 0 for op in operations)
        total_cost = sum(float(op.total_cost or 0) for op in operations)
        total_units = sum(op.units_produced or 0 for op in operations)
        total_good_units = sum(op.units_good or 0 for op in operations)
        total_downtime = sum(op.downtime_hours or 0 for op in operations)
        
        return {
            'total_operations': len(operations),
            'total_hours': total_hours,
            'total_cost': total_cost,
            'total_units': total_units,
            'cost_per_hour': total_cost / total_hours if total_hours > 0 else 0,
            'cost_per_unit': total_cost / total_units if total_units > 0 else 0,
            'efficiency': statistics.mean([op.efficiency_achieved or 100 for op in operations]),
            'utilization': (total_hours - total_downtime) / total_hours * 100 if total_hours > 0 else 0,
            'quality_score': total_good_units / total_units * 100 if total_units > 0 else 0,
            'downtime_percentage': total_downtime / total_hours * 100 if total_hours > 0 else 0
        }
    
    @staticmethod
    def _generate_benchmark_recommendations(comparisons: Dict) -> List[Dict]:
        """Generate recommendations based on benchmark comparisons"""
        recommendations = []
        
        # Fleet comparison recommendations
        for key, comparison in comparisons.items():
            if not key.startswith('fleet_'):
                continue
                
            metric = key.replace('fleet_', '')
            performance = comparison['performance']
            difference = comparison['difference_percentage']
            
            if performance == 'below' and abs(difference) > 10:
                if metric == 'cost_per_hour':
                    recommendations.append({
                        'type': 'cost_optimization',
                        'priority': 'high',
                        'metric': metric,
                        'issue': f'Cost per hour is {abs(difference):.1f}% higher than fleet average',
                        'recommendation': 'Review utility costs, operator efficiency, and maintenance schedules'
                    })
                elif metric == 'efficiency':
                    recommendations.append({
                        'type': 'efficiency_improvement',
                        'priority': 'medium',
                        'metric': metric,
                        'issue': f'Efficiency is {abs(difference):.1f}% below fleet average',
                        'recommendation': 'Consider operator training or equipment calibration'
                    })
                elif metric == 'utilization':
                    recommendations.append({
                        'type': 'utilization_improvement',
                        'priority': 'medium',
                        'metric': metric,
                        'issue': f'Utilization is {abs(difference):.1f}% below fleet average',
                        'recommendation': 'Optimize scheduling and reduce setup times'
                    })
        
        # Industry benchmark recommendations
        for key, comparison in comparisons.items():
            if not key.startswith('industry_'):
                continue
                
            metric = key.replace('industry_', '')
            if comparison['performance'] == 'below':
                if metric == 'oee_score':
                    recommendations.append({
                        'type': 'oee_improvement',
                        'priority': 'high',
                        'metric': metric,
                        'issue': 'OEE below industry benchmark',
                        'recommendation': 'Focus on availability, performance, and quality improvements'
                    })
        
        return recommendations


class MachineFinancialAnalyzer:
    """Financial analysis and ROI calculations for machines"""
    
    @staticmethod
    def calculate_machine_roi(machine_id: int, analysis_period_months: int = 12) -> Dict:
        """
        Calculate Return on Investment (ROI) for a machine
        
        Args:
            machine_id: ID of the machine
            analysis_period_months: Period for ROI analysis
            
        Returns:
            Dictionary with ROI analysis
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return {'error': 'Machine not found'}
            
            end_date = date.today()
            start_date = end_date - timedelta(days=analysis_period_months * 30)
            
            # Calculate total revenue contribution (from completed jobs)
            operations = OperatorMachineTime.query.filter(
                OperatorMachineTime.machine_id == machine_id,
                OperatorMachineTime.shift_date >= start_date,
                OperatorMachineTime.shift_date <= end_date,
                OperatorMachineTime.status == 'completed'
            ).all()
            
            # Calculate operational costs
            total_operational_cost = sum(float(op.total_cost or 0) for op in operations)
            
            # Calculate maintenance and utility costs
            expenses = MachineExpense.query.filter(
                MachineExpense.machine_id == machine_id,
                MachineExpense.billing_start_date >= start_date,
                MachineExpense.billing_end_date <= end_date
            ).all()
            
            maintenance_cost = sum(float(exp.amount) for exp in expenses if exp.expense_type == 'maintenance')
            utility_cost = sum(float(exp.amount) for exp in expenses if exp.expense_type == 'utility')
            other_costs = sum(float(exp.amount) for exp in expenses if exp.expense_type not in ['maintenance', 'utility'])
            
            total_costs = total_operational_cost + maintenance_cost + utility_cost + other_costs
            
            # Estimate revenue contribution (simplified - based on value-added through processes)
            total_units_produced = sum(op.units_good or 0 for op in operations)
            
            # Get average BOM value for items processed on this machine
            bom_processes = BOMProcess.query.filter_by(machine_id=machine_id).all()
            avg_value_added = 0
            
            if bom_processes:
                value_added_sum = 0
                value_count = 0
                
                for bom_process in bom_processes:
                    if bom_process.bom and bom_process.bom.product:
                        product_value = bom_process.bom.product.unit_price or 0
                        process_value_contribution = bom_process.cost_per_unit or 0
                        if product_value > 0:
                            value_added_sum += process_value_contribution
                            value_count += 1
                
                avg_value_added = value_added_sum / value_count if value_count > 0 else 0
            
            estimated_revenue = total_units_produced * avg_value_added
            
            # Calculate ROI metrics
            gross_profit = estimated_revenue - total_costs
            roi_percentage = (gross_profit / total_costs) * 100 if total_costs > 0 else 0
            
            # Calculate payback period (simplified)
            monthly_profit = gross_profit / analysis_period_months if analysis_period_months > 0 else 0
            machine_value = 500000  # Simplified - would come from asset register
            payback_months = machine_value / monthly_profit if monthly_profit > 0 else float('inf')
            
            return {
                'machine_code': machine.machine_code,
                'machine_name': machine.name,
                'analysis_period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'months': analysis_period_months
                },
                'financial_metrics': {
                    'estimated_revenue': round(estimated_revenue, 2),
                    'total_costs': round(total_costs, 2),
                    'gross_profit': round(gross_profit, 2),
                    'roi_percentage': round(roi_percentage, 2),
                    'payback_months': round(payback_months, 1) if payback_months != float('inf') else None
                },
                'cost_breakdown': {
                    'operational_cost': round(total_operational_cost, 2),
                    'maintenance_cost': round(maintenance_cost, 2),
                    'utility_cost': round(utility_cost, 2),
                    'other_costs': round(other_costs, 2)
                },
                'production_metrics': {
                    'total_operations': len(operations),
                    'total_units_produced': total_units_produced,
                    'avg_value_added_per_unit': round(avg_value_added, 2),
                    'total_hours': sum(op.actual_hours or 0 for op in operations)
                },
                'profitability_rating': MachineFinancialAnalyzer._get_profitability_rating(roi_percentage),
                'recommendations': MachineFinancialAnalyzer._get_financial_recommendations(roi_percentage, payback_months)
            }
            
        except Exception as e:
            return {'error': f'Error calculating machine ROI: {str(e)}'}
    
    @staticmethod
    def _get_profitability_rating(roi_percentage: float) -> str:
        """Get profitability rating based on ROI"""
        if roi_percentage >= 25:
            return 'Excellent'
        elif roi_percentage >= 15:
            return 'Good'
        elif roi_percentage >= 10:
            return 'Acceptable'
        elif roi_percentage >= 5:
            return 'Poor'
        else:
            return 'Unprofitable'
    
    @staticmethod
    def _get_financial_recommendations(roi_percentage: float, payback_months: float) -> List[str]:
        """Get financial recommendations based on ROI analysis"""
        recommendations = []
        
        if roi_percentage < 10:
            recommendations.append("ROI is below acceptable threshold - investigate cost reduction opportunities")
        
        if payback_months and payback_months > 36:
            recommendations.append("Long payback period - consider process optimization or alternative utilization")
        
        if roi_percentage > 25:
            recommendations.append("Excellent ROI - consider expanding capacity or similar investments")
        
        return recommendations