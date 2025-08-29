"""
Machine Management Routes

Web interface for machine-based real-time costing system including
machine operations, cost tracking, and BOM integration.
"""

from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from models import Machine, MachineOperator, MachineExpense, OperatorMachineTime, Employee, BOM, BOMProcess
# Import services conditionally to avoid circular imports
try:
    from services.machine_management import MachineManagementService
    from services.utility_bill_integration import UtilityBillProcessor
    from services.machine_bom_integration import MachineBOMIntegration
    from services.machine_cost_analysis import MachineKPIAnalyzer, MachineFinancialAnalyzer
except ImportError as e:
    print(f"Warning: Some machine services not available: {e}")
    # Define fallback classes
    class MachineManagementService:
        @staticmethod
        def get_machine_dashboard_data():
            return {}
        @staticmethod
        def get_real_time_machine_costs():
            return []
        @staticmethod
        def create_machine(data):
            return None, "Machine services not available"
        @staticmethod
        def assign_operator_to_machine(machine_id, employee_id, data):
            return False, "Machine services not available"
        @staticmethod
        def start_machine_operation(machine_id, operator_id, job_card_id, process_name, units_planned):
            return False, "Machine services not available", None
        @staticmethod
        def end_machine_operation(operation_id, units_produced, units_good, units_scrap, notes):
            return False, "Machine services not available", None
        @staticmethod
        def record_machine_expense(machine_id, expense_data):
            return False, "Machine services not available", None
    
    class UtilityBillProcessor:
        @staticmethod
        def process_utility_bill(bill_data):
            return False, "Utility services not available", []
        @staticmethod
        def get_machine_utility_costs_summary(machine_id, months):
            return {}
    
    class MachineBOMIntegration:
        @staticmethod
        def calculate_machine_based_bom_costs(bom_id, use_real_time_costs=True):
            return {'error': 'Machine BOM services not available'}
        @staticmethod
        def update_bom_with_machine_costs(bom_id, auto_update_price):
            return False, "Machine BOM services not available", {}
        @staticmethod
        def sync_all_boms_with_machine_costs(filter_active_only=True):
            return {'error': 'Machine BOM services not available'}
    
    class MachineKPIAnalyzer:
        @staticmethod
        def calculate_machine_oee(machine_id, start_date, end_date):
            return {}
        @staticmethod
        def analyze_cost_trends(machine_id, months):
            return {}
        @staticmethod
        def benchmark_machine_performance(machine_id, days):
            return {}
    
    class MachineFinancialAnalyzer:
        @staticmethod
        def calculate_machine_roi(machine_id, months):
            return {}

# Create Blueprint
machine_bp = Blueprint('machine', __name__, url_prefix='/machine')


@machine_bp.route('/')
@login_required
def dashboard():
    """Machine management dashboard"""
    try:
        # Get dashboard data
        dashboard_data = MachineManagementService.get_machine_dashboard_data()
        
        # Get real-time machine costs
        real_time_costs = MachineManagementService.get_real_time_machine_costs()
        
        return render_template('machine/dashboard.html',
                             dashboard_data=dashboard_data,
                             real_time_costs=real_time_costs,
                             title="Machine Management Dashboard")
    
    except Exception as e:
        flash(f"Error loading machine dashboard: {str(e)}", 'error')
        return render_template('machine/dashboard.html',
                             dashboard_data={},
                             real_time_costs=[],
                             title="Machine Management Dashboard")


@machine_bp.route('/list')
@login_required
def machine_list():
    """List all machines"""
    machines = Machine.query.order_by(Machine.machine_code).all()
    return render_template('machine/list.html',
                         machines=machines,
                         title="Machine List")


@machine_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_machine():
    """Create new machine"""
    if request.method == 'POST':
        try:
            machine_data = {
                'machine_code': request.form.get('machine_code'),
                'name': request.form.get('name'),
                'machine_type': request.form.get('machine_type'),
                'hourly_rate': float(request.form.get('hourly_rate', 0)),
                'power_consumption_kw': float(request.form.get('power_consumption_kw', 0)),
                'efficiency_rating': float(request.form.get('efficiency_rating', 100)),
                'location': request.form.get('location', 'Production Floor')
            }
            
            machine, message = MachineManagementService.create_machine(machine_data)
            
            if machine:
                flash(message, 'success')
                return redirect(url_for('machine.machine_detail', machine_id=machine.id))
            else:
                flash(message, 'error')
        
        except Exception as e:
            flash(f"Error creating machine: {str(e)}", 'error')
    
    return render_template('machine/create.html', title="Create Machine")


@machine_bp.route('/<int:machine_id>')
@login_required
def machine_detail(machine_id):
    """Machine detail page"""
    machine = Machine.query.get_or_404(machine_id)
    
    # Get current month operations
    start_of_month = datetime.now().replace(day=1)
    month_operations = OperatorMachineTime.query.filter(
        OperatorMachineTime.machine_id == machine_id,
        OperatorMachineTime.start_time >= start_of_month,
        OperatorMachineTime.status == 'completed'
    ).all()
    
    # Get recent expenses
    recent_expenses = MachineExpense.query.filter_by(machine_id=machine_id)\
                                         .order_by(MachineExpense.created_at.desc())\
                                         .limit(10).all()
    
    # Get assigned operators
    operators = MachineOperator.query.filter_by(machine_id=machine_id, status='active').all()
    
    return render_template('machine/detail.html',
                         machine=machine,
                         month_operations=month_operations,
                         recent_expenses=recent_expenses,
                         operators=operators,
                         title=f"Machine: {machine.machine_code}")


@machine_bp.route('/<int:machine_id>/assign_operator', methods=['POST'])
@login_required
def assign_operator(machine_id):
    """Assign operator to machine"""
    try:
        employee_id = request.form.get('employee_id')
        assignment_data = {
            'hourly_rate': float(request.form.get('hourly_rate', 0)),
            'skill_level': request.form.get('skill_level', 'intermediate'),
            'efficiency_multiplier': float(request.form.get('efficiency_multiplier', 1.0)),
            'is_primary': request.form.get('is_primary') == 'on'
        }
        
        success, message = MachineManagementService.assign_operator_to_machine(
            machine_id, int(employee_id), assignment_data
        )
        
        flash(message, 'success' if success else 'error')
    
    except Exception as e:
        flash(f"Error assigning operator: {str(e)}", 'error')
    
    return redirect(url_for('machine.machine_detail', machine_id=machine_id))


@machine_bp.route('/<int:machine_id>/start_operation', methods=['POST'])
@login_required
def start_operation(machine_id):
    """Start machine operation"""
    try:
        operator_id = request.form.get('operator_id')
        job_card_id = request.form.get('job_card_id') or None
        process_name = request.form.get('process_name')
        units_planned = float(request.form.get('units_planned', 0))
        
        success, message, operation = MachineManagementService.start_machine_operation(
            machine_id, int(operator_id), job_card_id, process_name, units_planned
        )
        
        flash(message, 'success' if success else 'error')
        
        if success:
            return jsonify({
                'success': True,
                'operation_id': operation.id,
                'message': message
            })
    
    except Exception as e:
        flash(f"Error starting operation: {str(e)}", 'error')
    
    return jsonify({'success': False, 'message': 'Failed to start operation'})


@machine_bp.route('/operation/<int:operation_id>/end', methods=['POST'])
@login_required
def end_operation(operation_id):
    """End machine operation"""
    try:
        units_produced = float(request.form.get('units_produced', 0))
        units_good = float(request.form.get('units_good', 0))
        units_scrap = float(request.form.get('units_scrap', 0))
        notes = request.form.get('notes', '')
        
        success, message, cost_summary = MachineManagementService.end_machine_operation(
            operation_id, units_produced, units_good, units_scrap, notes
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'cost_summary': cost_summary
            })
        else:
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error ending operation: {str(e)}'})


@machine_bp.route('/<int:machine_id>/expenses/add', methods=['POST'])
@login_required
def add_expense(machine_id):
    """Add machine expense"""
    try:
        expense_data = {
            'expense_type': request.form.get('expense_type'),
            'description': request.form.get('description'),
            'amount': float(request.form.get('amount')),
            'billing_start_date': datetime.strptime(request.form.get('billing_start_date'), '%Y-%m-%d').date(),
            'billing_end_date': datetime.strptime(request.form.get('billing_end_date'), '%Y-%m-%d').date(),
            'utility_type': request.form.get('utility_type'),
            'units_consumed': float(request.form.get('units_consumed', 0)) or None,
            'rate_per_unit': float(request.form.get('rate_per_unit', 0)) or None,
            'bill_reference': request.form.get('bill_reference'),
            'created_by': current_user.id
        }
        
        success, message, expense = MachineManagementService.record_machine_expense(machine_id, expense_data)
        
        flash(message, 'success' if success else 'error')
    
    except Exception as e:
        flash(f"Error adding expense: {str(e)}", 'error')
    
    return redirect(url_for('machine.machine_detail', machine_id=machine_id))


@machine_bp.route('/utility_bills/process', methods=['POST'])
@login_required
def process_utility_bill():
    """Process utility bill and allocate to machines"""
    try:
        bill_data = {
            'utility_type': request.form.get('utility_type'),
            'total_amount': float(request.form.get('total_amount')),
            'billing_start_date': datetime.strptime(request.form.get('billing_start_date'), '%Y-%m-%d').date(),
            'billing_end_date': datetime.strptime(request.form.get('billing_end_date'), '%Y-%m-%d').date(),
            'units_consumed': float(request.form.get('units_consumed', 0)) or None,
            'rate_per_unit': float(request.form.get('rate_per_unit', 0)) or None,
            'bill_reference': request.form.get('bill_reference'),
            'allocation_method': request.form.get('allocation_method', 'power_consumption'),
            'created_by': current_user.id
        }
        
        success, message, expenses = UtilityBillProcessor.process_utility_bill(bill_data)
        
        if success:
            flash(f"{message} - {len(expenses)} machine expenses created", 'success')
        else:
            flash(message, 'error')
    
    except Exception as e:
        flash(f"Error processing utility bill: {str(e)}", 'error')
    
    return redirect(url_for('machine.dashboard'))


@machine_bp.route('/bom/<int:bom_id>/machine_costs')
@login_required
def bom_machine_costs(bom_id):
    """Calculate machine-based costs for BOM"""
    try:
        cost_data = MachineBOMIntegration.calculate_machine_based_bom_costs(bom_id, use_real_time_costs=True)
        
        if 'error' in cost_data:
            flash(cost_data['error'], 'error')
            return redirect(url_for('bom.view', bom_id=bom_id))
        
        return render_template('machine/bom_costs.html',
                             cost_data=cost_data,
                             title=f"Machine Costs - BOM {cost_data['bom_code']}")
    
    except Exception as e:
        flash(f"Error calculating BOM machine costs: {str(e)}", 'error')
        return redirect(url_for('bom.view', bom_id=bom_id))


@machine_bp.route('/bom/<int:bom_id>/update_costs', methods=['POST'])
@login_required
def update_bom_costs(bom_id):
    """Update BOM with machine-based costs"""
    try:
        auto_update_price = request.form.get('auto_update_price') == 'on'
        
        success, message, cost_data = MachineBOMIntegration.update_bom_with_machine_costs(
            bom_id, auto_update_price
        )
        
        flash(message, 'success' if success else 'error')
    
    except Exception as e:
        flash(f"Error updating BOM costs: {str(e)}", 'error')
    
    return redirect(url_for('machine.bom_machine_costs', bom_id=bom_id))


@machine_bp.route('/<int:machine_id>/analytics')
@login_required
def machine_analytics(machine_id):
    """Machine analytics dashboard"""
    try:
        machine = Machine.query.get_or_404(machine_id)
        
        # Calculate OEE for last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        oee_data = MachineKPIAnalyzer.calculate_machine_oee(machine_id, start_date, end_date)
        
        # Cost trends for last 6 months
        cost_trends = MachineKPIAnalyzer.analyze_cost_trends(machine_id, 6)
        
        # Benchmark analysis
        benchmark_data = MachineKPIAnalyzer.benchmark_machine_performance(machine_id, 30)
        
        # ROI analysis
        roi_data = MachineFinancialAnalyzer.calculate_machine_roi(machine_id, 12)
        
        return render_template('machine/analytics.html',
                             machine=machine,
                             oee_data=oee_data,
                             cost_trends=cost_trends,
                             benchmark_data=benchmark_data,
                             roi_data=roi_data,
                             title=f"Analytics - {machine.machine_code}")
    
    except Exception as e:
        flash(f"Error loading machine analytics: {str(e)}", 'error')
        return redirect(url_for('machine.machine_detail', machine_id=machine_id))


@machine_bp.route('/api/real_time_costs')
@login_required
def api_real_time_costs():
    """API endpoint for real-time machine costs"""
    try:
        costs = MachineManagementService.get_real_time_machine_costs()
        return jsonify({
            'success': True,
            'data': costs,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@machine_bp.route('/api/utility_summary')
@login_required
def api_utility_summary():
    """API endpoint for utility cost summary"""
    try:
        machine_id = request.args.get('machine_id')
        months = int(request.args.get('months', 3))
        
        machine_id = int(machine_id) if machine_id else None
        
        summary = UtilityBillProcessor.get_machine_utility_costs_summary(machine_id, months)
        
        return jsonify({
            'success': True,
            'data': summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@machine_bp.route('/sync_all_boms', methods=['GET', 'POST'])
@login_required
def sync_all_boms():
    """Sync all BOMs with current machine costs"""
    try:
        results = MachineBOMIntegration.sync_all_boms_with_machine_costs(filter_active_only=True)
        
        if 'error' in results:
            flash(results['error'], 'error')
        else:
            flash(f"Updated {results['updated_successfully']} BOMs with machine costs", 'success')
            if results['failed_updates'] > 0:
                flash(f"{results['failed_updates']} updates failed", 'warning')
    
    except Exception as e:
        flash(f"Error syncing BOMs: {str(e)}", 'error')
    
    return redirect(url_for('machine.dashboard'))


# Helper functions for templates
@machine_bp.app_template_filter('format_currency')
def format_currency_filter(value):
    """Format currency for templates"""
    if value is None:
        return "₹0.00"
    return f"₹{float(value):,.2f}"


@machine_bp.app_template_filter('format_hours')
def format_hours_filter(value):
    """Format hours for templates"""
    if value is None:
        return "0.0h"
    return f"{float(value):.1f}h"


@machine_bp.app_template_filter('format_percentage')
def format_percentage_filter(value):
    """Format percentage for templates"""
    if value is None:
        return "0.0%"
    return f"{float(value):.1f}%"