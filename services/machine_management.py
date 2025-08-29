"""
Machine Management Service

Handles machine operations, operator assignments, time tracking, and real-time cost calculations
for the machine-based costing system.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Tuple
from sqlalchemy import func
from app import db
from models import (
    Machine, MachineOperator, MachineExpense, OperatorMachineTime, 
    MachineCostAnalysis, Employee, JobCard
)


class MachineManagementService:
    """Service for managing machines, operators, and real-time cost calculations"""
    
    @staticmethod
    def create_machine(data: dict) -> Tuple[Machine, str]:
        """
        Create a new machine with initial configuration
        
        Args:
            data: Dictionary with machine details
            
        Returns:
            Tuple of (Machine object, message)
        """
        try:
            # Validate required fields
            if not data.get('machine_code') or not data.get('name'):
                return None, "Machine code and name are required"
            
            # Check for duplicate machine code
            existing = Machine.query.filter_by(machine_code=data['machine_code']).first()
            if existing:
                return None, f"Machine code '{data['machine_code']}' already exists"
            
            machine = Machine(
                machine_code=data['machine_code'],
                name=data['name'],
                machine_type=data.get('machine_type', 'General'),
                hourly_rate=Decimal(str(data.get('hourly_rate', 0))),
                depreciation_per_hour=Decimal(str(data.get('depreciation_per_hour', 0))),
                maintenance_cost_per_hour=Decimal(str(data.get('maintenance_cost_per_hour', 0))),
                power_consumption_kw=float(data.get('power_consumption_kw', 0)),
                efficiency_rating=float(data.get('efficiency_rating', 100)),
                max_capacity_per_hour=float(data.get('max_capacity_per_hour', 0)),
                location=data.get('location', 'Production Floor'),
                installation_date=data.get('installation_date')
            )
            
            db.session.add(machine)
            db.session.commit()
            
            return machine, f"Machine '{machine.machine_code}' created successfully"
            
        except Exception as e:
            db.session.rollback()
            return None, f"Error creating machine: {str(e)}"
    
    @staticmethod
    def assign_operator_to_machine(machine_id: int, employee_id: int, data: dict) -> Tuple[bool, str]:
        """
        Assign an operator to a machine with skill level and rates
        
        Args:
            machine_id: ID of the machine
            employee_id: ID of the employee
            data: Dictionary with assignment details
            
        Returns:
            Tuple of (success, message)
        """
        try:
            machine = Machine.query.get(machine_id)
            employee = Employee.query.get(employee_id)
            
            if not machine:
                return False, "Machine not found"
            if not employee:
                return False, "Employee not found"
            
            # Check if assignment already exists
            existing = MachineOperator.query.filter_by(
                machine_id=machine_id,
                employee_id=employee_id
            ).first()
            
            if existing and existing.status == 'active':
                return False, "Operator already assigned to this machine"
            
            # Create or update assignment
            if existing:
                # Reactivate existing assignment
                existing.status = 'active'
                existing.assigned_date = date.today()
                existing.end_date = None
                existing.hourly_rate = Decimal(str(data.get('hourly_rate', 0)))
                existing.skill_level = data.get('skill_level', 'intermediate')
                existing.efficiency_multiplier = float(data.get('efficiency_multiplier', 1.0))
                existing.is_primary = data.get('is_primary', False)
                assignment = existing
            else:
                assignment = MachineOperator(
                    machine_id=machine_id,
                    employee_id=employee_id,
                    hourly_rate=Decimal(str(data.get('hourly_rate', 0))),
                    skill_level=data.get('skill_level', 'intermediate'),
                    efficiency_multiplier=float(data.get('efficiency_multiplier', 1.0)),
                    is_primary=data.get('is_primary', False)
                )
                db.session.add(assignment)
            
            # If this is primary, unset other primary operators for this machine
            if data.get('is_primary', False):
                MachineOperator.query.filter(
                    MachineOperator.machine_id == machine_id,
                    MachineOperator.id != (assignment.id if existing else 0)
                ).update({'is_primary': False})
            
            db.session.commit()
            
            return True, f"Operator '{employee.name}' assigned to machine '{machine.machine_code}'"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error assigning operator: {str(e)}"
    
    @staticmethod
    def start_machine_operation(machine_id: int, operator_id: int, job_card_id: Optional[int] = None, 
                               process_name: Optional[str] = None, units_planned: float = 0) -> Tuple[bool, str, Optional[OperatorMachineTime]]:
        """
        Start tracking machine operation time
        
        Args:
            machine_id: ID of the machine
            operator_id: ID of the machine operator
            job_card_id: Optional job card ID
            process_name: Name of the process
            units_planned: Planned units for this operation
            
        Returns:
            Tuple of (success, message, OperatorMachineTime object)
        """
        try:
            machine = Machine.query.get(machine_id)
            operator = MachineOperator.query.get(operator_id)
            
            if not machine:
                return False, "Machine not found", None
            if not operator:
                return False, "Operator assignment not found", None
            
            # Check if machine is available
            if machine.status == 'breakdown':
                return False, f"Machine {machine.machine_code} is under breakdown", None
            if machine.status == 'maintenance':
                return False, f"Machine {machine.machine_code} is under maintenance", None
            
            # Check if there's already an active operation for this machine
            active_operation = OperatorMachineTime.query.filter(
                OperatorMachineTime.machine_id == machine_id,
                OperatorMachineTime.status == 'active'
            ).first()
            
            if active_operation:
                return False, f"Machine {machine.machine_code} is already in use", None
            
            # Create new operation tracking record
            operation = OperatorMachineTime(
                operator_id=operator_id,
                machine_id=machine_id,
                job_card_id=job_card_id,
                process_name=process_name,
                units_planned=units_planned,
                shift_date=date.today()
            )
            
            operation.start_operation()
            
            # Update machine status
            machine.status = 'active'
            
            db.session.add(operation)
            db.session.commit()
            
            return True, f"Started operation on machine {machine.machine_code}", operation
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error starting operation: {str(e)}", None
    
    @staticmethod
    def end_machine_operation(operation_id: int, units_produced: float = 0, units_good: float = 0, 
                             units_scrap: float = 0, notes: str = '') -> Tuple[bool, str, Dict]:
        """
        End machine operation and calculate costs
        
        Args:
            operation_id: ID of the operation to end
            units_produced: Total units produced
            units_good: Good quality units
            units_scrap: Scrap units
            notes: Operation notes
            
        Returns:
            Tuple of (success, message, cost_summary_dict)
        """
        try:
            operation = OperatorMachineTime.query.get(operation_id)
            
            if not operation:
                return False, "Operation not found", {}
            
            if operation.status != 'active':
                return False, "Operation is not active", {}
            
            # End the operation
            operation.end_operation(units_produced, units_good, units_scrap, notes)
            
            # Update machine status to idle if no other operations
            active_ops = OperatorMachineTime.query.filter(
                OperatorMachineTime.machine_id == operation.machine_id,
                OperatorMachineTime.status == 'active'
            ).count()
            
            if active_ops == 0:
                operation.machine.status = 'idle'
            
            # Update operator performance metrics
            if operation.operator:
                MachineManagementService._update_operator_performance(operation.operator, operation)
            
            # Update machine performance metrics
            MachineManagementService._update_machine_performance(operation.machine, operation)
            
            db.session.commit()
            
            # Prepare cost summary
            cost_summary = {
                'operation_id': operation.id,
                'machine_code': operation.machine.machine_code,
                'operator_name': operation.operator.employee.name if operation.operator and operation.operator.employee else 'Unknown',
                'actual_hours': operation.actual_hours,
                'units_produced': units_produced,
                'units_good': units_good,
                'units_scrap': units_scrap,
                'operator_cost': float(operation.operator_cost or 0),
                'machine_cost': float(operation.machine_cost or 0),
                'utility_cost': float(operation.utility_cost or 0),
                'total_cost': float(operation.total_cost or 0),
                'cost_per_unit': operation.cost_per_unit,
                'efficiency_achieved': operation.efficiency_achieved,
                'quality_percentage': operation.quality_percentage
            }
            
            return True, f"Operation completed successfully", cost_summary
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error ending operation: {str(e)}", {}
    
    @staticmethod
    def _update_operator_performance(operator: MachineOperator, operation: OperatorMachineTime):
        """Update operator performance metrics"""
        try:
            # Update total hours and units
            operator.total_hours_operated = (operator.total_hours_operated or 0) + (operation.actual_hours or 0)
            operator.total_units_produced = (operator.total_units_produced or 0) + (operation.units_good or 0)
            
            # Recalculate average efficiency
            recent_operations = OperatorMachineTime.query.filter(
                OperatorMachineTime.operator_id == operator.id,
                OperatorMachineTime.status == 'completed'
            ).order_by(OperatorMachineTime.created_at.desc()).limit(10).all()
            
            if recent_operations:
                avg_efficiency = sum(op.efficiency_achieved or 100 for op in recent_operations) / len(recent_operations)
                operator.average_efficiency = avg_efficiency
                
                avg_quality = sum(op.quality_percentage for op in recent_operations) / len(recent_operations)
                operator.quality_score = avg_quality
        
        except Exception as e:
            print(f"Warning: Could not update operator performance: {e}")
    
    @staticmethod
    def _update_machine_performance(machine: Machine, operation: OperatorMachineTime):
        """Update machine performance metrics"""
        try:
            # Update total running hours and production units
            machine.total_running_hours = (machine.total_running_hours or 0) + (operation.actual_hours or 0)
            machine.total_production_units = (machine.total_production_units or 0) + (operation.units_good or 0)
            
        except Exception as e:
            print(f"Warning: Could not update machine performance: {e}")
    
    @staticmethod
    def record_machine_expense(machine_id: int, expense_data: dict) -> Tuple[bool, str, Optional[MachineExpense]]:
        """
        Record machine expense (utility bills, maintenance, etc.)
        
        Args:
            machine_id: ID of the machine
            expense_data: Dictionary with expense details
            
        Returns:
            Tuple of (success, message, MachineExpense object)
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return False, "Machine not found", None
            
            expense = MachineExpense(
                machine_id=machine_id,
                expense_type=expense_data['expense_type'],
                description=expense_data['description'],
                amount=Decimal(str(expense_data['amount'])),
                billing_start_date=expense_data['billing_start_date'],
                billing_end_date=expense_data['billing_end_date'],
                utility_type=expense_data.get('utility_type'),
                units_consumed=expense_data.get('units_consumed'),
                rate_per_unit=Decimal(str(expense_data.get('rate_per_unit', 0))) if expense_data.get('rate_per_unit') else None,
                bill_reference=expense_data.get('bill_reference'),
                allocation_method=expense_data.get('allocation_method', 'actual_usage'),
                allocation_percentage=expense_data.get('allocation_percentage'),
                created_by=expense_data.get('created_by')
            )
            
            # Calculate cost per hour based on machine usage
            machine_hours = MachineManagementService._get_machine_hours_for_period(
                machine_id, expense_data['billing_start_date'], expense_data['billing_end_date']
            )
            
            expense.calculate_cost_per_hour(machine_hours)
            
            db.session.add(expense)
            db.session.commit()
            
            return True, f"Expense recorded for machine {machine.machine_code}", expense
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error recording expense: {str(e)}", None
    
    @staticmethod
    def _get_machine_hours_for_period(machine_id: int, start_date: date, end_date: date) -> float:
        """Get total machine hours for a specific period"""
        try:
            total_hours = db.session.query(func.sum(OperatorMachineTime.actual_hours)).filter(
                OperatorMachineTime.machine_id == machine_id,
                OperatorMachineTime.shift_date >= start_date,
                OperatorMachineTime.shift_date <= end_date,
                OperatorMachineTime.status == 'completed'
            ).scalar()
            
            return float(total_hours or 0)
            
        except Exception as e:
            print(f"Error calculating machine hours: {e}")
            return 0.0
    
    @staticmethod
    def get_real_time_machine_costs() -> List[Dict]:
        """
        Get real-time cost data for all active machines
        
        Returns:
            List of dictionaries with machine cost data
        """
        try:
            machines = Machine.query.filter_by(status='active').all()
            machine_costs = []
            
            for machine in machines:
                # Get current month data
                start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                # Current month operations
                month_operations = OperatorMachineTime.query.filter(
                    OperatorMachineTime.machine_id == machine.id,
                    OperatorMachineTime.start_time >= start_of_month,
                    OperatorMachineTime.status == 'completed'
                ).all()
                
                # Calculate current month metrics
                total_hours = sum(op.actual_hours or 0 for op in month_operations)
                total_cost = sum(float(op.total_cost or 0) for op in month_operations)
                total_units = sum(op.units_good or 0 for op in month_operations)
                
                # Get active operation if any
                active_operation = OperatorMachineTime.query.filter(
                    OperatorMachineTime.machine_id == machine.id,
                    OperatorMachineTime.status == 'active'
                ).first()
                
                machine_data = {
                    'machine_id': machine.id,
                    'machine_code': machine.machine_code,
                    'machine_name': machine.name,
                    'machine_type': machine.machine_type,
                    'status': machine.status,
                    'current_hourly_cost': machine.current_hourly_cost,
                    'efficiency_rating': machine.current_efficiency,
                    'utilization_rate': machine.utilization_rate,
                    'month_total_hours': total_hours,
                    'month_total_cost': total_cost,
                    'month_total_units': total_units,
                    'month_cost_per_hour': total_cost / total_hours if total_hours > 0 else 0,
                    'month_cost_per_unit': total_cost / total_units if total_units > 0 else 0,
                    'active_operation': {
                        'operator_name': active_operation.operator.employee.name if active_operation and active_operation.operator and active_operation.operator.employee else None,
                        'process_name': active_operation.process_name if active_operation else None,
                        'start_time': active_operation.start_time.isoformat() if active_operation and active_operation.start_time else None,
                        'units_planned': active_operation.units_planned if active_operation else 0
                    } if active_operation else None
                }
                
                machine_costs.append(machine_data)
            
            return machine_costs
            
        except Exception as e:
            print(f"Error getting real-time machine costs: {e}")
            return []
    
    @staticmethod
    def generate_machine_cost_analysis(machine_id: int, start_date: date, end_date: date) -> Tuple[bool, str, Optional[MachineCostAnalysis]]:
        """
        Generate comprehensive cost analysis for a machine over a period
        
        Args:
            machine_id: ID of the machine
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Tuple of (success, message, MachineCostAnalysis object)
        """
        try:
            analysis = MachineCostAnalysis.generate_analysis(machine_id, start_date, end_date)
            
            if not analysis:
                return False, "No data available for analysis period", None
            
            db.session.add(analysis)
            db.session.commit()
            
            machine = Machine.query.get(machine_id)
            return True, f"Cost analysis generated for machine {machine.machine_code}", analysis
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error generating analysis: {str(e)}", None
    
    @staticmethod
    def get_machine_dashboard_data(machine_id: Optional[int] = None) -> Dict:
        """
        Get dashboard data for machines
        
        Args:
            machine_id: Optional specific machine ID, if None returns data for all machines
            
        Returns:
            Dictionary with dashboard data
        """
        try:
            # Base query
            query = Machine.query
            if machine_id:
                query = query.filter_by(id=machine_id)
            
            machines = query.all()
            
            # Calculate aggregate metrics
            total_machines = len(machines)
            active_machines = len([m for m in machines if m.status == 'active'])
            idle_machines = len([m for m in machines if m.status == 'idle'])
            maintenance_machines = len([m for m in machines if m.status == 'maintenance'])
            breakdown_machines = len([m for m in machines if m.status == 'breakdown'])
            
            # Get current month operations
            start_of_month = datetime.now().replace(day=1)
            
            month_operations = OperatorMachineTime.query.filter(
                OperatorMachineTime.start_time >= start_of_month,
                OperatorMachineTime.status == 'completed'
            )
            
            if machine_id:
                month_operations = month_operations.filter_by(machine_id=machine_id)
            
            operations = month_operations.all()
            
            total_hours = sum(op.actual_hours or 0 for op in operations)
            total_cost = sum(float(op.total_cost or 0) for op in operations)
            total_units = sum(op.units_good or 0 for op in operations)
            
            # Machine utilization data
            machine_utilization = []
            for machine in machines:
                utilization = machine.utilization_rate
                efficiency = machine.current_efficiency
                
                machine_utilization.append({
                    'machine_code': machine.machine_code,
                    'utilization_rate': utilization,
                    'efficiency_rating': efficiency,
                    'hourly_cost': machine.current_hourly_cost,
                    'status': machine.status
                })
            
            # Top cost machines
            machine_costs = []
            for machine in machines:
                machine_ops = [op for op in operations if op.machine_id == machine.id]
                machine_total_cost = sum(float(op.total_cost or 0) for op in machine_ops)
                machine_hours = sum(op.actual_hours or 0 for op in machine_ops)
                
                if machine_hours > 0:
                    machine_costs.append({
                        'machine_code': machine.machine_code,
                        'total_cost': machine_total_cost,
                        'total_hours': machine_hours,
                        'cost_per_hour': machine_total_cost / machine_hours,
                        'units_produced': sum(op.units_good or 0 for op in machine_ops)
                    })
            
            # Sort by total cost
            machine_costs.sort(key=lambda x: x['total_cost'], reverse=True)
            
            return {
                'summary': {
                    'total_machines': total_machines,
                    'active_machines': active_machines,
                    'idle_machines': idle_machines,
                    'maintenance_machines': maintenance_machines,
                    'breakdown_machines': breakdown_machines,
                    'month_total_hours': total_hours,
                    'month_total_cost': total_cost,
                    'month_total_units': total_units,
                    'average_cost_per_hour': total_cost / total_hours if total_hours > 0 else 0,
                    'average_cost_per_unit': total_cost / total_units if total_units > 0 else 0
                },
                'machine_utilization': machine_utilization[:10],  # Top 10
                'top_cost_machines': machine_costs[:10],  # Top 10
                'status_distribution': {
                    'active': active_machines,
                    'idle': idle_machines,
                    'maintenance': maintenance_machines,
                    'breakdown': breakdown_machines
                }
            }
            
        except Exception as e:
            print(f"Error getting machine dashboard data: {e}")
            return {}
    
    @staticmethod
    def update_machine_status(machine_id: int, new_status: str, notes: str = '') -> Tuple[bool, str]:
        """
        Update machine status (active, idle, maintenance, breakdown)
        
        Args:
            machine_id: ID of the machine
            new_status: New status
            notes: Optional notes
            
        Returns:
            Tuple of (success, message)
        """
        try:
            machine = Machine.query.get(machine_id)
            if not machine:
                return False, "Machine not found"
            
            valid_statuses = ['active', 'idle', 'maintenance', 'breakdown']
            if new_status not in valid_statuses:
                return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            
            old_status = machine.status
            machine.status = new_status
            
            # If switching to maintenance, update maintenance date
            if new_status == 'maintenance':
                machine.last_maintenance_date = date.today()
                machine.maintenance_count = (machine.maintenance_count or 0) + 1
            
            # If switching to breakdown, increment breakdown count
            if new_status == 'breakdown':
                machine.breakdown_count = (machine.breakdown_count or 0) + 1
            
            # End any active operations if machine is going to maintenance or breakdown
            if new_status in ['maintenance', 'breakdown']:
                active_operations = OperatorMachineTime.query.filter(
                    OperatorMachineTime.machine_id == machine_id,
                    OperatorMachineTime.status == 'active'
                ).all()
                
                for operation in active_operations:
                    operation.status = 'cancelled'
                    operation.end_time = datetime.now()
                    operation.notes = f"Operation cancelled due to machine {new_status}" + (f": {notes}" if notes else "")
            
            db.session.commit()
            
            return True, f"Machine {machine.machine_code} status changed from {old_status} to {new_status}"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error updating machine status: {str(e)}"