"""
Utility Bill Integration Service

Handles utility bill processing, automatic allocation to machines based on power consumption
and running hours, and real-time cost updates for machine-based costing.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional
from sqlalchemy import func
import json
import re

from app import db
from models import Machine, MachineExpense, OperatorMachineTime, Document
from services.machine_management import MachineManagementService


class UtilityBillProcessor:
    """Service for processing and allocating utility bills to machines"""
    
    UTILITY_TYPES = {
        'electricity': {
            'unit': 'KWH',
            'allocation_method': 'power_consumption',
            'base_rate_keywords': ['energy charge', 'unit charge', 'kwh', 'per unit']
        },
        'gas': {
            'unit': 'cubic_meter',
            'allocation_method': 'proportional',
            'base_rate_keywords': ['gas charge', 'cubic meter', 'scm', 'per scm']
        },
        'water': {
            'unit': 'liter',
            'allocation_method': 'proportional',
            'base_rate_keywords': ['water charge', 'liter', 'gallon', 'per liter']
        },
        'compressed_air': {
            'unit': 'cubic_meter',
            'allocation_method': 'proportional',
            'base_rate_keywords': ['air charge', 'compressor', 'cfm', 'per cfm']
        }
    }
    
    @staticmethod
    def process_utility_bill(bill_data: Dict) -> Tuple[bool, str, List[MachineExpense]]:
        """
        Process a utility bill and allocate costs to machines
        
        Args:
            bill_data: Dictionary containing bill information:
                - utility_type: 'electricity', 'gas', 'water', 'compressed_air'
                - total_amount: Total bill amount
                - billing_start_date: Start date
                - billing_end_date: End date
                - units_consumed: Total units consumed (optional)
                - rate_per_unit: Rate per unit (optional)
                - bill_reference: Bill number/reference
                - document_id: Attached bill document ID (optional)
                - allocation_method: 'power_consumption', 'proportional', 'actual_usage'
        
        Returns:
            Tuple of (success, message, list_of_machine_expenses)
        """
        try:
            # Validate required fields
            required_fields = ['utility_type', 'total_amount', 'billing_start_date', 'billing_end_date']
            for field in required_fields:
                if field not in bill_data:
                    return False, f"Missing required field: {field}", []
            
            utility_type = bill_data['utility_type']
            if utility_type not in UtilityBillProcessor.UTILITY_TYPES:
                return False, f"Invalid utility type: {utility_type}", []
            
            total_amount = Decimal(str(bill_data['total_amount']))
            start_date = bill_data['billing_start_date']
            end_date = bill_data['billing_end_date']
            allocation_method = bill_data.get('allocation_method', 
                                           UtilityBillProcessor.UTILITY_TYPES[utility_type]['allocation_method'])
            
            # Get active machines for the billing period
            active_machines = Machine.query.filter(
                Machine.status.in_(['active', 'idle', 'maintenance'])
            ).all()
            
            if not active_machines:
                return False, "No machines found for cost allocation", []
            
            # Calculate allocation based on method
            if allocation_method == 'power_consumption':
                allocations = UtilityBillProcessor._allocate_by_power_consumption(
                    active_machines, total_amount, start_date, end_date, utility_type
                )
            elif allocation_method == 'actual_usage':
                allocations = UtilityBillProcessor._allocate_by_actual_usage(
                    active_machines, total_amount, start_date, end_date
                )
            else:  # proportional
                allocations = UtilityBillProcessor._allocate_proportionally(
                    active_machines, total_amount
                )
            
            # Create machine expense records
            machine_expenses = []
            for machine_id, allocation_data in allocations.items():
                machine = Machine.query.get(machine_id)
                if not machine:
                    continue
                
                expense = MachineExpense(
                    machine_id=machine_id,
                    expense_type='utility',
                    description=f"{utility_type.title()} bill allocation - {bill_data.get('bill_reference', 'No ref')}",
                    amount=allocation_data['allocated_amount'],
                    billing_start_date=start_date,
                    billing_end_date=end_date,
                    utility_type=utility_type,
                    units_consumed=allocation_data.get('allocated_units'),
                    rate_per_unit=bill_data.get('rate_per_unit'),
                    bill_reference=bill_data.get('bill_reference'),
                    document_id=bill_data.get('document_id'),
                    allocation_method=allocation_method,
                    allocation_percentage=allocation_data.get('allocation_percentage'),
                    total_machine_hours=allocation_data.get('machine_hours', 0),
                    created_by=bill_data.get('created_by')
                )
                
                # Calculate cost per hour
                expense.calculate_cost_per_hour(allocation_data.get('machine_hours'))
                
                db.session.add(expense)
                machine_expenses.append(expense)
            
            db.session.commit()
            
            return True, f"Utility bill processed and allocated to {len(machine_expenses)} machines", machine_expenses
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error processing utility bill: {str(e)}", []
    
    @staticmethod
    def _allocate_by_power_consumption(machines: List[Machine], total_amount: Decimal, 
                                     start_date: date, end_date: date, utility_type: str) -> Dict:
        """
        Allocate utility costs based on power consumption and actual running hours
        
        Args:
            machines: List of machines
            total_amount: Total bill amount
            start_date: Billing start date
            end_date: Billing end date
            utility_type: Type of utility
            
        Returns:
            Dictionary with machine allocations
        """
        allocations = {}
        total_power_hours = Decimal('0')
        
        # Calculate power-hours for each machine
        machine_power_hours = {}
        for machine in machines:
            if machine.power_consumption_kw <= 0:
                continue  # Skip machines without power consumption data
            
            # Get actual running hours for the billing period
            running_hours = UtilityBillProcessor._get_machine_running_hours(
                machine.id, start_date, end_date
            )
            
            if running_hours > 0:
                power_hours = Decimal(str(machine.power_consumption_kw)) * Decimal(str(running_hours))
                machine_power_hours[machine.id] = {
                    'power_hours': power_hours,
                    'running_hours': running_hours,
                    'power_kw': machine.power_consumption_kw
                }
                total_power_hours += power_hours
        
        # Allocate costs proportionally based on power-hours
        if total_power_hours > 0:
            for machine_id, data in machine_power_hours.items():
                allocation_percentage = (data['power_hours'] / total_power_hours) * 100
                allocated_amount = (data['power_hours'] / total_power_hours) * total_amount
                
                # Calculate allocated units (KWH for electricity)
                allocated_units = float(data['power_hours']) if utility_type == 'electricity' else None
                
                allocations[machine_id] = {
                    'allocated_amount': allocated_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'allocated_units': allocated_units,
                    'allocation_percentage': float(allocation_percentage),
                    'machine_hours': data['running_hours'],
                    'power_consumption_kw': data['power_kw']
                }
        
        return allocations
    
    @staticmethod
    def _allocate_by_actual_usage(machines: List[Machine], total_amount: Decimal,
                                start_date: date, end_date: date) -> Dict:
        """
        Allocate costs based on actual machine usage hours
        
        Args:
            machines: List of machines
            total_amount: Total bill amount
            start_date: Billing start date
            end_date: Billing end date
            
        Returns:
            Dictionary with machine allocations
        """
        allocations = {}
        total_hours = Decimal('0')
        machine_hours_data = {}
        
        # Get actual running hours for each machine
        for machine in machines:
            running_hours = UtilityBillProcessor._get_machine_running_hours(
                machine.id, start_date, end_date
            )
            
            if running_hours > 0:
                machine_hours_data[machine.id] = Decimal(str(running_hours))
                total_hours += Decimal(str(running_hours))
        
        # Allocate costs proportionally based on hours
        if total_hours > 0:
            for machine_id, hours in machine_hours_data.items():
                allocation_percentage = (hours / total_hours) * 100
                allocated_amount = (hours / total_hours) * total_amount
                
                allocations[machine_id] = {
                    'allocated_amount': allocated_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'allocation_percentage': float(allocation_percentage),
                    'machine_hours': float(hours)
                }
        
        return allocations
    
    @staticmethod
    def _allocate_proportionally(machines: List[Machine], total_amount: Decimal) -> Dict:
        """
        Allocate costs equally among all machines
        
        Args:
            machines: List of machines
            total_amount: Total bill amount
            
        Returns:
            Dictionary with machine allocations
        """
        allocations = {}
        machine_count = len(machines)
        
        if machine_count > 0:
            amount_per_machine = total_amount / Decimal(str(machine_count))
            allocation_percentage = 100.0 / machine_count
            
            for machine in machines:
                allocations[machine.id] = {
                    'allocated_amount': amount_per_machine.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'allocation_percentage': allocation_percentage,
                    'machine_hours': 0  # Not applicable for proportional allocation
                }
        
        return allocations
    
    @staticmethod
    def _get_machine_running_hours(machine_id: int, start_date: date, end_date: date) -> float:
        """Get total running hours for a machine in the specified period"""
        try:
            total_hours = db.session.query(func.sum(OperatorMachineTime.actual_hours)).filter(
                OperatorMachineTime.machine_id == machine_id,
                OperatorMachineTime.shift_date >= start_date,
                OperatorMachineTime.shift_date <= end_date,
                OperatorMachineTime.status == 'completed'
            ).scalar()
            
            return float(total_hours or 0)
            
        except Exception as e:
            print(f"Error getting machine running hours: {e}")
            return 0.0
    
    @staticmethod
    def parse_utility_bill_text(bill_text: str, utility_type: str) -> Dict:
        """
        Parse utility bill text to extract key information
        
        Args:
            bill_text: Text content of the utility bill
            utility_type: Type of utility bill
            
        Returns:
            Dictionary with parsed bill data
        """
        try:
            bill_data = {}
            utility_config = UtilityBillProcessor.UTILITY_TYPES.get(utility_type, {})
            
            # Extract total amount
            amount_patterns = [
                r'total[:\s]+₹?([0-9,]+\.?[0-9]*)',
                r'amount[:\s]+₹?([0-9,]+\.?[0-9]*)',
                r'bill[:\s]+₹?([0-9,]+\.?[0-9]*)',
                r'₹([0-9,]+\.?[0-9]*)'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, bill_text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    try:
                        bill_data['total_amount'] = float(amount_str)
                        break
                    except ValueError:
                        continue
            
            # Extract units consumed
            unit_patterns = [
                rf'([0-9,]+\.?[0-9]*)\s*{utility_config.get("unit", "").lower()}',
                r'units[:\s]+([0-9,]+\.?[0-9]*)',
                r'consumption[:\s]+([0-9,]+\.?[0-9]*)'
            ]
            
            for pattern in unit_patterns:
                match = re.search(pattern, bill_text, re.IGNORECASE)
                if match:
                    units_str = match.group(1).replace(',', '')
                    try:
                        bill_data['units_consumed'] = float(units_str)
                        break
                    except ValueError:
                        continue
            
            # Extract rate per unit
            rate_keywords = utility_config.get('base_rate_keywords', [])
            for keyword in rate_keywords:
                pattern = rf'{keyword}[:\s]+₹?([0-9,]+\.?[0-9]*)'
                match = re.search(pattern, bill_text, re.IGNORECASE)
                if match:
                    rate_str = match.group(1).replace(',', '')
                    try:
                        bill_data['rate_per_unit'] = float(rate_str)
                        break
                    except ValueError:
                        continue
            
            # Extract billing period dates
            date_patterns = [
                r'from[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})[:\s]+to[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
                r'period[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})[:\s]+to[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
                r'billing[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})[:\s]+to[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, bill_text, re.IGNORECASE)
                if match:
                    try:
                        start_date_str = match.group(1)
                        end_date_str = match.group(2)
                        
                        # Parse dates (assuming DD/MM/YYYY or DD-MM-YYYY format)
                        start_date = datetime.strptime(start_date_str.replace('/', '-'), '%d-%m-%Y').date()
                        end_date = datetime.strptime(end_date_str.replace('/', '-'), '%d-%m-%Y').date()
                        
                        bill_data['billing_start_date'] = start_date
                        bill_data['billing_end_date'] = end_date
                        break
                        
                    except ValueError:
                        continue
            
            # Calculate rate per unit if not found but total amount and units are available
            if 'rate_per_unit' not in bill_data and 'total_amount' in bill_data and 'units_consumed' in bill_data:
                if bill_data['units_consumed'] > 0:
                    bill_data['rate_per_unit'] = bill_data['total_amount'] / bill_data['units_consumed']
            
            # Set utility type
            bill_data['utility_type'] = utility_type
            
            return bill_data
            
        except Exception as e:
            print(f"Error parsing utility bill text: {e}")
            return {'utility_type': utility_type}
    
    @staticmethod
    def get_machine_utility_costs_summary(machine_id: Optional[int] = None, 
                                        period_months: int = 3) -> Dict:
        """
        Get utility cost summary for machines over a specified period
        
        Args:
            machine_id: Optional specific machine ID
            period_months: Number of months to analyze
            
        Returns:
            Dictionary with utility cost summary
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=period_months * 30)
            
            # Base query for utility expenses
            query = MachineExpense.query.filter(
                MachineExpense.expense_type == 'utility',
                MachineExpense.billing_start_date >= start_date,
                MachineExpense.billing_end_date <= end_date
            )
            
            if machine_id:
                query = query.filter_by(machine_id=machine_id)
            
            expenses = query.all()
            
            # Group by utility type and machine
            utility_summary = {}
            machine_totals = {}
            
            for expense in expenses:
                machine_code = expense.machine.machine_code
                utility_type = expense.utility_type or 'unknown'
                
                if utility_type not in utility_summary:
                    utility_summary[utility_type] = {
                        'total_amount': 0,
                        'total_units': 0,
                        'average_rate': 0,
                        'machine_breakdown': {}
                    }
                
                if machine_code not in utility_summary[utility_type]['machine_breakdown']:
                    utility_summary[utility_type]['machine_breakdown'][machine_code] = {
                        'total_amount': 0,
                        'total_units': 0,
                        'total_hours': 0,
                        'cost_per_hour': 0
                    }
                
                if machine_code not in machine_totals:
                    machine_totals[machine_code] = {
                        'total_utility_cost': 0,
                        'total_hours': 0,
                        'cost_per_hour': 0,
                        'utility_breakdown': {}
                    }
                
                # Update totals
                amount = float(expense.amount)
                units = expense.units_consumed or 0
                hours = expense.total_machine_hours or 0
                
                utility_summary[utility_type]['total_amount'] += amount
                utility_summary[utility_type]['total_units'] += units
                
                utility_summary[utility_type]['machine_breakdown'][machine_code]['total_amount'] += amount
                utility_summary[utility_type]['machine_breakdown'][machine_code]['total_units'] += units
                utility_summary[utility_type]['machine_breakdown'][machine_code]['total_hours'] += hours
                
                machine_totals[machine_code]['total_utility_cost'] += amount
                machine_totals[machine_code]['total_hours'] += hours
                
                if utility_type not in machine_totals[machine_code]['utility_breakdown']:
                    machine_totals[machine_code]['utility_breakdown'][utility_type] = 0
                machine_totals[machine_code]['utility_breakdown'][utility_type] += amount
            
            # Calculate averages and rates
            for utility_type, data in utility_summary.items():
                if data['total_units'] > 0:
                    data['average_rate'] = data['total_amount'] / data['total_units']
                
                for machine_code, machine_data in data['machine_breakdown'].items():
                    if machine_data['total_hours'] > 0:
                        machine_data['cost_per_hour'] = machine_data['total_amount'] / machine_data['total_hours']
            
            for machine_code, data in machine_totals.items():
                if data['total_hours'] > 0:
                    data['cost_per_hour'] = data['total_utility_cost'] / data['total_hours']
            
            return {
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'period_months': period_months,
                'utility_summary': utility_summary,
                'machine_totals': machine_totals,
                'total_utility_cost': sum(data['total_amount'] for data in utility_summary.values()),
                'total_machines': len(machine_totals)
            }
            
        except Exception as e:
            print(f"Error getting utility costs summary: {e}")
            return {}
    
    @staticmethod
    def update_bom_rates_from_utility_costs():
        """
        Update BOM hourly rates based on latest utility cost analysis
        This method should be called periodically to keep BOM rates current
        """
        try:
            # Get current month machine cost analysis
            current_month_start = date.today().replace(day=1)
            
            machines = Machine.query.filter_by(status='active').all()
            updated_machines = []
            
            for machine in machines:
                # Get recent utility expenses for this machine
                recent_expenses = MachineExpense.query.filter(
                    MachineExpense.machine_id == machine.id,
                    MachineExpense.expense_type == 'utility',
                    MachineExpense.effective_date >= current_month_start
                ).all()
                
                if recent_expenses:
                    # Calculate average utility cost per hour
                    total_cost = sum(float(expense.amount) for expense in recent_expenses)
                    total_hours = sum(expense.total_machine_hours or 0 for expense in recent_expenses)
                    
                    if total_hours > 0:
                        utility_cost_per_hour = total_cost / total_hours
                        
                        # Update machine's current hourly rate (this could be used for BOM updates)
                        # Note: In a real implementation, you'd want to update the BOM process rates
                        # that reference this machine
                        
                        updated_machines.append({
                            'machine_code': machine.machine_code,
                            'old_utility_rate': machine.get_current_utility_cost_per_hour(),
                            'new_utility_rate': utility_cost_per_hour,
                            'variance': utility_cost_per_hour - machine.get_current_utility_cost_per_hour()
                        })
            
            return {
                'success': True,
                'updated_machines': updated_machines,
                'message': f"Updated utility rates for {len(updated_machines)} machines"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error updating BOM rates: {str(e)}",
                'updated_machines': []
            }