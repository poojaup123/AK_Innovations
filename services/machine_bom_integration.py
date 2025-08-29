"""
Machine-BOM Integration Service

Integrates machine-based real-time costing with BOM calculations,
providing accurate manufacturing costs based on actual machine and operator costs.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from sqlalchemy import func

from app import db
from models import (
    BOM, BOMProcess, Machine, MachineOperator, MachineExpense, 
    OperatorMachineTime, MachineCostAnalysis
)
from services.machine_management import MachineManagementService
from services.utility_bill_integration import UtilityBillProcessor


class MachineBOMIntegration:
    """Service for integrating machine-based costs with BOM calculations"""
    
    @staticmethod
    def calculate_machine_based_bom_costs(bom_id: int, use_real_time_costs: bool = True) -> Dict:
        """
        Calculate BOM costs using machine-based real-time costing
        
        Args:
            bom_id: ID of the BOM
            use_real_time_costs: If True, use current machine costs; if False, use standard rates
            
        Returns:
            Dictionary with detailed cost breakdown
        """
        try:
            bom = BOM.query.get(bom_id)
            if not bom:
                return {'error': 'BOM not found'}
            
            # Get all processes with machine assignments
            processes = BOMProcess.query.filter_by(bom_id=bom_id).order_by(BOMProcess.step_number).all()
            
            cost_breakdown = {
                'bom_id': bom_id,
                'bom_code': bom.bom_code,
                'product_name': bom.product.name if bom.product else 'Unknown',
                'output_quantity': bom.output_quantity or 1.0,
                'processes': [],
                'totals': {
                    'material_cost': 0.0,
                    'machine_cost': 0.0,
                    'operator_cost': 0.0,
                    'utility_cost': 0.0,
                    'setup_cost': 0.0,
                    'overhead_cost': 0.0,
                    'total_cost': 0.0
                },
                'per_unit_costs': {},
                'machine_utilization': {},
                'cost_comparison': {}
            }
            
            # Calculate material costs (existing logic)
            material_cost = sum(item.qty_required * (item.unit_cost or 0) for item in bom.items)
            cost_breakdown['totals']['material_cost'] = material_cost
            
            # Calculate process costs with machine integration
            for process in processes:
                process_cost_data = MachineBOMIntegration._calculate_process_machine_costs(
                    process, bom.output_quantity, use_real_time_costs
                )
                
                cost_breakdown['processes'].append(process_cost_data)
                
                # Aggregate totals
                cost_breakdown['totals']['machine_cost'] += process_cost_data['machine_cost']
                cost_breakdown['totals']['operator_cost'] += process_cost_data['operator_cost']
                cost_breakdown['totals']['utility_cost'] += process_cost_data['utility_cost']
                cost_breakdown['totals']['setup_cost'] += process_cost_data['setup_cost']
            
            # Calculate overhead (percentage of total manufacturing cost)
            manufacturing_cost = (
                cost_breakdown['totals']['machine_cost'] +
                cost_breakdown['totals']['operator_cost'] +
                cost_breakdown['totals']['utility_cost']
            )
            
            overhead_percentage = bom.overhead_percentage or 15.0  # Default 15%
            cost_breakdown['totals']['overhead_cost'] = manufacturing_cost * (overhead_percentage / 100)
            
            # Calculate total cost
            cost_breakdown['totals']['total_cost'] = (
                cost_breakdown['totals']['material_cost'] +
                cost_breakdown['totals']['machine_cost'] +
                cost_breakdown['totals']['operator_cost'] +
                cost_breakdown['totals']['utility_cost'] +
                cost_breakdown['totals']['setup_cost'] +
                cost_breakdown['totals']['overhead_cost']
            )
            
            # Calculate per-unit costs
            output_qty = bom.output_quantity or 1.0
            for cost_type, total_cost in cost_breakdown['totals'].items():
                cost_breakdown['per_unit_costs'][cost_type] = total_cost / output_qty
            
            # Add cost comparison with standard BOM rates
            cost_breakdown['cost_comparison'] = MachineBOMIntegration._compare_with_standard_bom_costs(bom, cost_breakdown)
            
            # Add machine utilization summary
            cost_breakdown['machine_utilization'] = MachineBOMIntegration._get_machine_utilization_summary(processes)
            
            return cost_breakdown
            
        except Exception as e:
            return {'error': f'Error calculating machine-based BOM costs: {str(e)}'}
    
    @staticmethod
    def _calculate_process_machine_costs(process: BOMProcess, output_quantity: float, use_real_time_costs: bool) -> Dict:
        """Calculate costs for a single process with machine integration"""
        process_data = {
            'step_number': process.step_number,
            'process_name': process.process_name,
            'process_code': process.process_code,
            'machine_id': process.machine_id,
            'machine_code': None,
            'is_outsourced': process.is_outsourced,
            'setup_time_minutes': process.setup_time_minutes or 0,
            'run_time_minutes': process.run_time_minutes or 0,
            'total_time_minutes': (process.setup_time_minutes or 0) + (process.run_time_minutes or 0),
            'machine_cost': 0.0,
            'operator_cost': 0.0,
            'utility_cost': 0.0,
            'setup_cost': 0.0,
            'total_process_cost': 0.0,
            'cost_source': 'standard',
            'machine_efficiency': 100.0,
            'operator_skill_level': 'intermediate'
        }
        
        if process.is_outsourced:
            # For outsourced processes, use the standard cost_per_unit
            process_data['total_process_cost'] = (process.cost_per_unit or 0) * output_quantity
            process_data['cost_source'] = 'outsourced'
            return process_data
        
        # Machine-based cost calculation
        if process.machine_id and use_real_time_costs:
            machine = Machine.query.get(process.machine_id)
            if machine:
                process_data['machine_code'] = machine.machine_code
                
                # Calculate time-based costs
                total_hours = process_data['total_time_minutes'] / 60.0
                
                # Machine costs (current hourly rate including utilities)
                machine_hourly_cost = machine.current_hourly_cost
                process_data['machine_cost'] = machine_hourly_cost * total_hours * output_quantity
                
                # Get primary operator for this machine
                primary_operator = MachineOperator.query.filter_by(
                    machine_id=machine.id,
                    is_primary=True,
                    status='active'
                ).first()
                
                if primary_operator:
                    # Operator costs with efficiency factor
                    operator_hourly_cost = primary_operator.effective_hourly_cost
                    process_data['operator_cost'] = operator_hourly_cost * total_hours * output_quantity
                    process_data['operator_skill_level'] = primary_operator.skill_level
                    process_data['machine_efficiency'] = primary_operator.efficiency_multiplier * 100
                else:
                    # Fallback to process labor rate
                    if process.labor_rate_per_hour:
                        process_data['operator_cost'] = process.labor_rate_per_hour * total_hours * output_quantity
                
                # Utility costs (from recent machine expenses)
                utility_cost_per_hour = machine.get_current_utility_cost_per_hour()
                process_data['utility_cost'] = utility_cost_per_hour * total_hours * output_quantity
                
                # Setup costs (one-time per batch, not per unit)
                setup_hours = (process.setup_time_minutes or 0) / 60.0
                if setup_hours > 0:
                    setup_cost_total = (machine_hourly_cost + (primary_operator.hourly_rate if primary_operator else 0)) * setup_hours
                    process_data['setup_cost'] = float(setup_cost_total)  # One-time cost, not per unit
                
                process_data['cost_source'] = 'machine_realtime'
        
        else:
            # Fallback to standard BOM process costs
            if process.cost_per_unit:
                process_data['total_process_cost'] = process.cost_per_unit * output_quantity
            elif process.labor_rate_per_hour and process_data['total_time_minutes'] > 0:
                total_hours = process_data['total_time_minutes'] / 60.0
                process_data['operator_cost'] = process.labor_rate_per_hour * total_hours * output_quantity
            
            process_data['cost_source'] = 'standard'
        
        # Calculate total process cost
        process_data['total_process_cost'] = (
            process_data['machine_cost'] +
            process_data['operator_cost'] +
            process_data['utility_cost'] +
            process_data['setup_cost']
        )
        
        return process_data
    
    @staticmethod
    def _compare_with_standard_bom_costs(bom: BOM, machine_cost_breakdown: Dict) -> Dict:
        """Compare machine-based costs with standard BOM costs"""
        try:
            # Calculate standard BOM costs
            standard_material_cost = sum(item.qty_required * (item.unit_cost or 0) for item in bom.items)
            standard_labor_cost = (bom.labor_cost_per_unit or 0) * (bom.output_quantity or 1.0)
            standard_overhead_cost = (bom.overhead_cost_per_unit or 0) * (bom.output_quantity or 1.0)
            standard_total_cost = standard_material_cost + standard_labor_cost + standard_overhead_cost
            
            # Machine-based costs
            machine_total_cost = machine_cost_breakdown['totals']['total_cost']
            machine_labor_cost = (
                machine_cost_breakdown['totals']['machine_cost'] +
                machine_cost_breakdown['totals']['operator_cost'] +
                machine_cost_breakdown['totals']['utility_cost']
            )
            
            # Calculate variances
            variance_amount = machine_total_cost - standard_total_cost
            variance_percentage = (variance_amount / standard_total_cost * 100) if standard_total_cost > 0 else 0
            
            labor_variance = machine_labor_cost - standard_labor_cost
            labor_variance_percentage = (labor_variance / standard_labor_cost * 100) if standard_labor_cost > 0 else 0
            
            return {
                'standard_costs': {
                    'material_cost': standard_material_cost,
                    'labor_cost': standard_labor_cost,
                    'overhead_cost': standard_overhead_cost,
                    'total_cost': standard_total_cost
                },
                'machine_costs': {
                    'material_cost': machine_cost_breakdown['totals']['material_cost'],
                    'labor_cost': machine_labor_cost,
                    'overhead_cost': machine_cost_breakdown['totals']['overhead_cost'],
                    'total_cost': machine_total_cost
                },
                'variances': {
                    'total_variance_amount': variance_amount,
                    'total_variance_percentage': variance_percentage,
                    'labor_variance_amount': labor_variance,
                    'labor_variance_percentage': labor_variance_percentage
                },
                'cost_accuracy_improvement': abs(variance_percentage),
                'recommendation': 'update_bom' if abs(variance_percentage) > 10 else 'acceptable_variance'
            }
            
        except Exception as e:
            return {'error': f'Error comparing costs: {str(e)}'}
    
    @staticmethod
    def _get_machine_utilization_summary(processes: List[BOMProcess]) -> Dict:
        """Get machine utilization summary for BOM processes"""
        try:
            machine_utilization = {}
            
            for process in processes:
                if process.machine_id:
                    machine = Machine.query.get(process.machine_id)
                    if machine:
                        # Get current utilization rate
                        utilization_rate = machine.utilization_rate
                        efficiency_rating = machine.current_efficiency
                        
                        machine_utilization[machine.machine_code] = {
                            'machine_id': machine.id,
                            'machine_name': machine.name,
                            'machine_type': machine.machine_type,
                            'utilization_rate': utilization_rate,
                            'efficiency_rating': efficiency_rating,
                            'current_status': machine.status,
                            'hourly_cost': machine.current_hourly_cost,
                            'processes_used': machine_utilization.get(machine.machine_code, {}).get('processes_used', []) + [process.process_name]
                        }
            
            return machine_utilization
            
        except Exception as e:
            print(f"Error getting machine utilization summary: {e}")
            return {}
    
    @staticmethod
    def update_bom_with_machine_costs(bom_id: int, auto_update_item_price: bool = True) -> Tuple[bool, str, Dict]:
        """
        Update BOM with current machine-based costs
        
        Args:
            bom_id: ID of the BOM to update
            auto_update_item_price: Whether to automatically update finished product price
            
        Returns:
            Tuple of (success, message, cost_data)
        """
        try:
            bom = BOM.query.get(bom_id)
            if not bom:
                return False, "BOM not found", {}
            
            # Calculate machine-based costs
            cost_data = MachineBOMIntegration.calculate_machine_based_bom_costs(bom_id, use_real_time_costs=True)
            
            if 'error' in cost_data:
                return False, cost_data['error'], {}
            
            # Update BOM with new cost calculations
            per_unit_costs = cost_data['per_unit_costs']
            
            # Update labor cost with machine + operator costs
            total_labor_per_unit = per_unit_costs['machine_cost'] + per_unit_costs['operator_cost']
            bom.labor_cost_per_unit = total_labor_per_unit
            bom.calculated_labor_cost_per_unit = total_labor_per_unit
            
            # Update overhead cost
            bom.overhead_cost_per_unit = per_unit_costs['overhead_cost']
            
            # Update labor hours (total time from all processes)
            total_hours = sum(process['total_time_minutes'] for process in cost_data['processes']) / 60.0
            bom.labor_hours_per_unit = total_hours / (bom.output_quantity or 1.0)
            
            # Set effective labor rate (weighted average)
            if total_hours > 0:
                total_labor_cost = per_unit_costs['operator_cost'] * (bom.output_quantity or 1.0)
                bom.labor_rate_per_hour = total_labor_cost / total_hours
            
            # Add notes about machine-based calculation
            machine_codes = [process['machine_code'] for process in cost_data['processes'] if process['machine_code']]
            cost_notes = f"Machine-based calculation using: {', '.join(machine_codes)}"
            bom.remarks = f"{bom.remarks or ''}\n{cost_notes}".strip()
            
            db.session.commit()
            
            # Update finished product price if requested
            if auto_update_item_price and bom.product:
                try:
                    total_cost_per_unit = per_unit_costs['total_cost']
                    
                    # Apply markup if specified
                    if bom.markup_percentage and bom.markup_percentage > 0:
                        markup_amount = total_cost_per_unit * (bom.markup_percentage / 100)
                        total_cost_per_unit += markup_amount
                    
                    # Update item price
                    bom.product.update_price(
                        new_price=total_cost_per_unit,
                        price_type='machine_based',
                        effective_date=date.today(),
                        source='Machine-BOM Integration',
                        source_reference=f'BOM-{bom.bom_code}',
                        notes=f'Machine-based BOM calculation: Total cost per unit ₹{total_cost_per_unit:.2f}',
                        user_id=1  # System user
                    )
                    
                except Exception as e:
                    print(f"Warning: Could not update item price: {e}")
            
            variance_info = ""
            if 'cost_comparison' in cost_data and 'variances' in cost_data['cost_comparison']:
                variance = cost_data['cost_comparison']['variances']['total_variance_percentage']
                variance_info = f" | Variance from standard: {variance:+.1f}%"
            
            return True, f"BOM updated with machine-based costs{variance_info}", cost_data
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error updating BOM with machine costs: {str(e)}", {}
    
    @staticmethod
    def get_machine_bom_recommendations(bom_id: int) -> Dict:
        """
        Get recommendations for optimizing machine utilization and costs in BOM
        
        Args:
            bom_id: ID of the BOM
            
        Returns:
            Dictionary with optimization recommendations
        """
        try:
            cost_data = MachineBOMIntegration.calculate_machine_based_bom_costs(bom_id, use_real_time_costs=True)
            
            if 'error' in cost_data:
                return {'error': cost_data['error']}
            
            recommendations = {
                'cost_optimization': [],
                'machine_utilization': [],
                'operator_efficiency': [],
                'process_improvements': []
            }
            
            # Analyze each process for recommendations
            for process in cost_data['processes']:
                if not process['machine_id']:
                    recommendations['process_improvements'].append({
                        'type': 'machine_assignment',
                        'process': process['process_name'],
                        'issue': 'No machine assigned to process',
                        'recommendation': 'Assign appropriate machine for accurate costing',
                        'priority': 'medium'
                    })
                    continue
                
                # Check machine efficiency
                if process['machine_efficiency'] < 85:
                    recommendations['machine_utilization'].append({
                        'type': 'efficiency',
                        'process': process['process_name'],
                        'machine_code': process['machine_code'],
                        'current_efficiency': process['machine_efficiency'],
                        'recommendation': 'Consider operator training or machine maintenance',
                        'priority': 'high'
                    })
                
                # Check operator skill level vs process requirements
                if process['operator_skill_level'] == 'beginner' and 'complex' in process['process_name'].lower():
                    recommendations['operator_efficiency'].append({
                        'type': 'skill_mismatch',
                        'process': process['process_name'],
                        'current_skill': process['operator_skill_level'],
                        'recommendation': 'Assign experienced operator for complex processes',
                        'priority': 'medium'
                    })
                
                # Check for high setup costs
                setup_percentage = (process['setup_cost'] / process['total_process_cost'] * 100) if process['total_process_cost'] > 0 else 0
                if setup_percentage > 25:
                    recommendations['cost_optimization'].append({
                        'type': 'setup_cost',
                        'process': process['process_name'],
                        'setup_percentage': setup_percentage,
                        'recommendation': 'Consider batch processing to reduce setup cost impact',
                        'priority': 'medium'
                    })
            
            # Overall cost variance recommendations
            if 'cost_comparison' in cost_data:
                variance = cost_data['cost_comparison']['variances']['total_variance_percentage']
                if abs(variance) > 15:
                    recommendations['cost_optimization'].append({
                        'type': 'cost_variance',
                        'variance_percentage': variance,
                        'recommendation': 'Significant cost variance detected - review and update standard BOM rates',
                        'priority': 'high'
                    })
            
            # Machine utilization recommendations
            for machine_code, util_data in cost_data['machine_utilization'].items():
                if util_data['utilization_rate'] < 50:
                    recommendations['machine_utilization'].append({
                        'type': 'low_utilization',
                        'machine_code': machine_code,
                        'utilization_rate': util_data['utilization_rate'],
                        'recommendation': 'Consider scheduling optimization or machine reassignment',
                        'priority': 'low'
                    })
                elif util_data['utilization_rate'] > 90:
                    recommendations['machine_utilization'].append({
                        'type': 'high_utilization',
                        'machine_code': machine_code,
                        'utilization_rate': util_data['utilization_rate'],
                        'recommendation': 'Consider additional capacity or load balancing',
                        'priority': 'high'
                    })
            
            return recommendations
            
        except Exception as e:
            return {'error': f'Error generating recommendations: {str(e)}'}
    
    @staticmethod
    def sync_all_boms_with_machine_costs(filter_active_only: bool = True) -> Dict:
        """
        Bulk update all BOMs with current machine costs
        
        Args:
            filter_active_only: Only update active BOMs
            
        Returns:
            Dictionary with update results
        """
        try:
            # Get BOMs to update
            query = BOM.query
            if filter_active_only:
                query = query.filter_by(is_active=True, status='active')
            
            boms = query.all()
            
            results = {
                'total_boms': len(boms),
                'updated_successfully': 0,
                'failed_updates': 0,
                'skipped': 0,
                'details': []
            }
            
            for bom in boms:
                # Check if BOM has machine-assigned processes
                machine_processes = BOMProcess.query.filter(
                    BOMProcess.bom_id == bom.id,
                    BOMProcess.machine_id.isnot(None)
                ).count()
                
                if machine_processes == 0:
                    results['skipped'] += 1
                    results['details'].append({
                        'bom_code': bom.bom_code,
                        'status': 'skipped',
                        'reason': 'No machine-assigned processes'
                    })
                    continue
                
                # Update BOM with machine costs
                success, message, cost_data = MachineBOMIntegration.update_bom_with_machine_costs(
                    bom.id, auto_update_item_price=True
                )
                
                if success:
                    results['updated_successfully'] += 1
                    variance = 0
                    if cost_data and 'cost_comparison' in cost_data:
                        variance = cost_data['cost_comparison']['variances']['total_variance_percentage']
                    
                    results['details'].append({
                        'bom_code': bom.bom_code,
                        'product_name': bom.product.name if bom.product else 'Unknown',
                        'status': 'updated',
                        'variance_percentage': variance,
                        'message': message
                    })
                else:
                    results['failed_updates'] += 1
                    results['details'].append({
                        'bom_code': bom.bom_code,
                        'status': 'failed',
                        'error': message
                    })
            
            return results
            
        except Exception as e:
            return {'error': f'Error syncing BOMs with machine costs: {str(e)}'}


class MachineProcessOptimizer:
    """Optimizer for machine process assignments and scheduling"""
    
    @staticmethod
    def suggest_machine_assignments(bom_id: int) -> Dict:
        """
        Suggest optimal machine assignments for BOM processes
        
        Args:
            bom_id: ID of the BOM
            
        Returns:
            Dictionary with assignment suggestions
        """
        try:
            bom = BOM.query.get(bom_id)
            if not bom:
                return {'error': 'BOM not found'}
            
            processes = BOMProcess.query.filter_by(bom_id=bom_id).order_by(BOMProcess.step_number).all()
            machines = Machine.query.filter_by(status='active').all()
            
            suggestions = []
            
            for process in processes:
                if process.machine_id:
                    continue  # Already has machine assigned
                
                # Find suitable machines based on process requirements
                suitable_machines = []
                
                for machine in machines:
                    # Match machine type with process requirements
                    if process.process_name.lower() in machine.machine_type.lower():
                        # Calculate suitability score
                        score = MachineProcessOptimizer._calculate_suitability_score(machine, process)
                        suitable_machines.append({
                            'machine': machine,
                            'score': score,
                            'reasons': MachineProcessOptimizer._get_suitability_reasons(machine, process, score)
                        })
                
                # Sort by suitability score
                suitable_machines.sort(key=lambda x: x['score'], reverse=True)
                
                if suitable_machines:
                    top_suggestions = suitable_machines[:3]  # Top 3 suggestions
                    
                    suggestions.append({
                        'process_name': process.process_name,
                        'process_id': process.id,
                        'step_number': process.step_number,
                        'suggestions': [{
                            'machine_id': s['machine'].id,
                            'machine_code': s['machine'].machine_code,
                            'machine_name': s['machine'].name,
                            'suitability_score': s['score'],
                            'hourly_cost': s['machine'].current_hourly_cost,
                            'utilization_rate': s['machine'].utilization_rate,
                            'efficiency_rating': s['machine'].current_efficiency,
                            'reasons': s['reasons']
                        } for s in top_suggestions]
                    })
            
            return {
                'bom_code': bom.bom_code,
                'total_processes': len(processes),
                'unassigned_processes': len(suggestions),
                'assignment_suggestions': suggestions
            }
            
        except Exception as e:
            return {'error': f'Error suggesting machine assignments: {str(e)}'}
    
    @staticmethod
    def _calculate_suitability_score(machine: Machine, process: BOMProcess) -> float:
        """Calculate suitability score for machine-process pairing"""
        score = 0.0
        
        # Base score for machine type match
        if process.process_name.lower() in machine.machine_type.lower():
            score += 50.0
        
        # Efficiency rating (0-50 points)
        score += (machine.current_efficiency / 100.0) * 50.0
        
        # Utilization rate (prefer moderately utilized machines)
        utilization = machine.utilization_rate
        if 40 <= utilization <= 70:
            score += 30.0  # Sweet spot
        elif 70 < utilization <= 85:
            score += 20.0
        elif utilization < 40:
            score += 15.0  # Under-utilized
        else:
            score += 5.0   # Over-utilized
        
        # Machine status
        if machine.status == 'active':
            score += 20.0
        elif machine.status == 'idle':
            score += 25.0  # Prefer idle machines
        else:
            score -= 20.0  # Maintenance or breakdown
        
        # Cost efficiency (lower cost gets higher score)
        if machine.current_hourly_cost > 0:
            # Normalize cost score (assuming max reasonable cost is 500/hour)
            cost_score = max(0, (500 - machine.current_hourly_cost) / 500 * 20)
            score += cost_score
        
        return min(100.0, score)  # Cap at 100
    
    @staticmethod
    def _get_suitability_reasons(machine: Machine, process: BOMProcess, score: float) -> List[str]:
        """Get human-readable reasons for machine suitability"""
        reasons = []
        
        if process.process_name.lower() in machine.machine_type.lower():
            reasons.append("Machine type matches process requirements")
        
        if machine.current_efficiency >= 90:
            reasons.append("High efficiency rating")
        elif machine.current_efficiency < 70:
            reasons.append("Lower efficiency - may need maintenance")
        
        utilization = machine.utilization_rate
        if 40 <= utilization <= 70:
            reasons.append("Optimal utilization rate")
        elif utilization < 40:
            reasons.append("Under-utilized - good availability")
        elif utilization > 85:
            reasons.append("High utilization - may cause delays")
        
        if machine.status == 'idle':
            reasons.append("Currently idle and available")
        elif machine.status != 'active':
            reasons.append(f"Currently {machine.status}")
        
        if machine.current_hourly_cost < 200:
            reasons.append("Cost-effective hourly rate")
        elif machine.current_hourly_cost > 400:
            reasons.append("High hourly cost")
        
        return reasons