from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms import EmployeeForm, SalaryRecordForm, EmployeeAdvanceForm, AttendanceForm, BulkAttendanceForm
from models import Employee, SalaryRecord, EmployeeAdvance, EmployeeAttendance, FactoryExpense
from app import db
from sqlalchemy import func, desc
from utils import generate_employee_code
from utils.documents import save_uploaded_documents, get_documents_for_transaction
from services.hr_accounting_integration import HRAccountingIntegration
from datetime import datetime, date
from calendar import monthrange
import os

hr_bp = Blueprint('hr', __name__)

@hr_bp.route('/dashboard')
@login_required
def dashboard():
    # HR statistics
    from datetime import date
    today = date.today()
    
    stats = {
        'total_employees': Employee.query.count(),
        'active_employees': Employee.query.filter_by(is_active=True).count(),
        'daily_rate_employees': Employee.query.filter_by(salary_type='daily', is_active=True).count(),
        'monthly_salary_employees': Employee.query.filter_by(salary_type='monthly', is_active=True).count(),
        'piece_rate_employees': Employee.query.filter_by(salary_type='piece_rate', is_active=True).count(),
        'pending_salaries': SalaryRecord.query.filter_by(status='pending').count(),
        'pending_advances': EmployeeAdvance.query.filter_by(status='pending').count(),
        'total_monthly_advances': db.session.query(func.sum(EmployeeAdvance.remaining_amount)).filter_by(status='active').scalar() or 0,
        'today_attendance': EmployeeAttendance.query.filter_by(attendance_date=today).count(),
        'today_present': EmployeeAttendance.query.filter_by(attendance_date=today, status='present').count(),
        'today_absent': EmployeeAttendance.query.filter_by(attendance_date=today, status='absent').count(),
        'today_on_leave': EmployeeAttendance.query.filter_by(attendance_date=today, status='leave').count()
    }
    
    # Recent employees
    recent_employees = Employee.query.filter_by(is_active=True).order_by(Employee.joining_date.desc()).limit(10).all()
    
    # Department summary
    dept_stats = db.session.query(
        Employee.department, 
        func.count(Employee.id).label('emp_count')
    ).filter_by(is_active=True).group_by(Employee.department).all()
    
    # Salary type distribution
    salary_type_stats = db.session.query(
        Employee.salary_type, 
        func.count(Employee.id).label('emp_count')
    ).filter_by(is_active=True).group_by(Employee.salary_type).all()
    
    return render_template('hr/dashboard.html', 
                         stats=stats, 
                         recent_employees=recent_employees,
                         dept_stats=dept_stats,
                         salary_type_stats=salary_type_stats)

@hr_bp.route('/employees')
@login_required
def list_employees():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    department_filter = request.args.get('department', '', type=str)
    status_filter = request.args.get('status', 'active', type=str)
    
    query = Employee.query
    
    if search:
        query = query.filter(Employee.name.contains(search) | Employee.employee_code.contains(search))
    
    if department_filter:
        query = query.filter_by(department=department_filter)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    employees = query.order_by(Employee.name).paginate(
        page=page, per_page=20, error_out=False)
    
    # Get departments for filter dropdown
    departments = db.session.query(Employee.department).distinct().filter(Employee.department.isnot(None)).all()
    departments = [dept[0] for dept in departments if dept[0]]
    
    return render_template('hr/employees.html', 
                         employees=employees, 
                         search=search,
                         department_filter=department_filter,
                         status_filter=status_filter,
                         departments=departments)

@hr_bp.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    form = EmployeeForm()
    
    # Auto-generate employee code for GET request
    if request.method == 'GET':
        form.employee_code.data = generate_employee_code()
    
    if form.validate_on_submit():
        # Check if employee code already exists
        existing_employee = Employee.query.filter_by(employee_code=form.employee_code.data).first()
        if existing_employee:
            flash('Employee code already exists', 'danger')
            return render_template('hr/employee_form.html', form=form, title='Add Employee', get_documents_for_transaction=get_documents_for_transaction)
        
        employee = Employee(
            employee_code=form.employee_code.data,
            name=form.name.data,
            designation=form.designation.data,
            department=form.department.data,
            salary_type=form.salary_type.data,
            rate=form.rate.data,
            phone=form.phone.data,
            address=form.address.data,
            joining_date=form.joining_date.data
        )
        db.session.add(employee)
        db.session.commit()
        
        # Handle document uploads
        documents_uploaded = 0
        if form.documents.data:
            files = request.files.getlist('documents')
            documents_uploaded = save_uploaded_documents(files, 'employee', employee.id)
        
        success_message = f'Employee added successfully'
        if documents_uploaded > 0:
            success_message += f' with {documents_uploaded} document(s) uploaded'
        flash(success_message, 'success')
        return redirect(url_for('hr.list_employees'))
    
    return render_template('hr/employee_form.html', form=form, title='Add Employee', get_documents_for_transaction=get_documents_for_transaction)

@hr_bp.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    employee = Employee.query.get_or_404(id)
    form = EmployeeForm(obj=employee)
    
    if form.validate_on_submit():
        # Check if employee code already exists (excluding current employee)
        existing_employee = Employee.query.filter(
            Employee.employee_code == form.employee_code.data, 
            Employee.id != id
        ).first()
        if existing_employee:
            flash('Employee code already exists', 'danger')
            return render_template('hr/employee_form.html', form=form, title='Edit Employee', employee=employee, get_documents_for_transaction=get_documents_for_transaction)
        
        employee.employee_code = form.employee_code.data
        employee.name = form.name.data
        employee.designation = form.designation.data
        employee.department = form.department.data
        employee.salary_type = form.salary_type.data
        employee.rate = form.rate.data
        employee.phone = form.phone.data
        employee.address = form.address.data
        employee.joining_date = form.joining_date.data
        
        # Handle document uploads
        documents_uploaded = 0
        if form.documents.data:
            files = request.files.getlist('documents')
            documents_uploaded = save_uploaded_documents(files, 'employee', employee.id)
        
        db.session.commit()
        success_message = f'Employee updated successfully'
        if documents_uploaded > 0:
            success_message += f' with {documents_uploaded} new document(s) uploaded'
        flash(success_message, 'success')
        return redirect(url_for('hr.list_employees'))
    
    return render_template('hr/employee_form.html', form=form, title='Edit Employee', employee=employee, get_documents_for_transaction=get_documents_for_transaction)

@hr_bp.route('/employees/toggle_status/<int:id>')
@login_required
def toggle_employee_status(id):
    if not current_user.is_admin():
        flash('Only administrators can change employee status', 'danger')
        return redirect(url_for('hr.list_employees'))
    
    employee = Employee.query.get_or_404(id)
    employee.is_active = not employee.is_active
    db.session.commit()
    
    status = 'activated' if employee.is_active else 'deactivated'
    flash(f'Employee {status} successfully', 'success')
    return redirect(url_for('hr.list_employees'))

@hr_bp.route('/employees/detail/<int:id>')
@login_required
def employee_detail(id):
    """View employee details with salary and advance history"""
    employee = Employee.query.get_or_404(id)
    
    # Get recent salary records
    recent_salaries = SalaryRecord.query.filter_by(employee_id=id).order_by(desc(SalaryRecord.created_at)).limit(5).all()
    
    # Get recent advances
    recent_advances = EmployeeAdvance.query.filter_by(employee_id=id).order_by(desc(EmployeeAdvance.created_at)).limit(5).all()
    
    # Calculate advance summary
    total_advances = db.session.query(func.sum(EmployeeAdvance.amount)).filter_by(employee_id=id).scalar() or 0
    remaining_advances = db.session.query(func.sum(EmployeeAdvance.remaining_amount)).filter_by(employee_id=id, status='active').scalar() or 0
    
    return render_template('hr/employee_detail.html', 
                         employee=employee,
                         recent_salaries=recent_salaries,
                         recent_advances=recent_advances,
                         total_advances=total_advances,
                         remaining_advances=remaining_advances)

# ============ SALARY RECORDS MANAGEMENT ============

@hr_bp.route('/salaries')
@login_required
def salary_list():
    """List all salary records"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    month = request.args.get('month', '', type=str)
    
    query = SalaryRecord.query.join(Employee)
    
    if search:
        query = query.filter(Employee.name.contains(search) | Employee.employee_code.contains(search))
    
    if status:
        query = query.filter(SalaryRecord.status == status)
    
    if month:
        try:
            month_start = datetime.strptime(month, '%Y-%m').date()
            month_end = date(month_start.year, month_start.month, monthrange(month_start.year, month_start.month)[1])
            query = query.filter(SalaryRecord.pay_period_start >= month_start, SalaryRecord.pay_period_end <= month_end)
        except ValueError:
            pass
    
    salaries = query.order_by(desc(SalaryRecord.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate totals for current filter
    total_gross = query.with_entities(func.sum(SalaryRecord.gross_amount)).scalar() or 0
    total_net = query.with_entities(func.sum(SalaryRecord.net_amount)).scalar() or 0
    
    return render_template('hr/salary_list.html', 
                         salaries=salaries, 
                         search=search, 
                         status=status, 
                         month=month,
                         total_gross=total_gross,
                         total_net=total_net)

@hr_bp.route('/api/employee/<int:employee_id>/hire-date')
@login_required
def get_employee_hire_date(employee_id):
    """Get employee hire date for salary form"""
    try:
        employee = Employee.query.get_or_404(employee_id)
        return jsonify({
            'success': True,
            'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else None,
            'name': employee.name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@hr_bp.route('/salaries/add', methods=['GET', 'POST'])
@login_required
def add_salary():
    """Add new salary record with attendance-based calculation"""
    form = SalaryRecordForm()
    form.salary_number.data = SalaryRecord.generate_salary_number()
    
    # Handle attendance calculation button
    if form.calculate_attendance.data and form.employee_id.data and form.pay_period_start.data and form.pay_period_end.data and form.daily_rate.data:
        # Create temporary salary record to calculate attendance
        temp_salary = SalaryRecord(
            employee_id=form.employee_id.data,
            pay_period_start=form.pay_period_start.data,
            pay_period_end=form.pay_period_end.data,
            daily_rate=form.daily_rate.data,
            overtime_rate=form.overtime_rate.data or 0
        )
        
        # Calculate attendance-based values
        attendance_data = temp_salary.calculate_attendance_based_salary()
        
        # Update form fields with calculated values
        form.expected_working_days.data = attendance_data['expected_working_days']
        form.actual_days_worked.data = attendance_data['actual_days_worked']
        form.basic_amount.data = attendance_data['basic_amount']
        form.overtime_hours.data = attendance_data['overtime_hours']
        
        flash(f'Attendance calculated: {attendance_data["actual_days_worked"]} days worked out of {attendance_data["expected_working_days"]} expected days', 'info')
    
    if form.validate_on_submit() and not form.calculate_attendance.data:
        try:
            # Create salary record with attendance-based data
            salary = SalaryRecord(
                salary_number=form.salary_number.data,
                employee_id=form.employee_id.data,
                pay_period_start=form.pay_period_start.data,
                pay_period_end=form.pay_period_end.data,
                daily_rate=form.daily_rate.data,
                expected_working_days=form.expected_working_days.data or 0,
                actual_days_worked=form.actual_days_worked.data or 0,
                basic_amount=form.basic_amount.data or 0,
                overtime_hours=form.overtime_hours.data or 0,
                overtime_rate=form.overtime_rate.data or 0,
                bonus_amount=form.bonus_amount.data or 0,
                deduction_amount=form.deduction_amount.data or 0,
                advance_deduction=form.advance_deduction.data or 0,
                payment_method=form.payment_method.data,
                notes=form.notes.data,
                created_by=current_user.id
            )
            
            # Calculate overtime and gross amounts
            salary.overtime_amount = salary.overtime_hours * salary.overtime_rate
            salary.gross_amount = salary.basic_amount + salary.overtime_amount + salary.bonus_amount
            salary.net_amount = salary.gross_amount - salary.deduction_amount - salary.advance_deduction
            
            db.session.add(salary)
            db.session.commit()
            
            # Send HR notification for salary record creation
            try:
                from services.hr_notifications import send_hr_notification
                
                employee = Employee.query.get(salary.employee_id)
                if employee:
                    send_hr_notification(
                        'salary_payment',
                        employee_id=employee.id,
                        employee_name=employee.name,
                        salary_amount=salary.net_amount,
                        month_year=f"{salary.pay_period_start.strftime('%B %Y')}",
                        payment_date=datetime.now()
                    )
            except Exception as e:
                # Don't fail salary creation if notification fails
                print(f"HR notification failed: {str(e)}")
            
            flash(f'Salary record {salary.salary_number} created successfully with attendance-based calculation!', 'success')
            return redirect(url_for('hr.salary_detail', id=salary.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating salary record: {str(e)}', 'danger')
    
    return render_template('hr/salary_form.html', form=form, title='Add Salary Record')

@hr_bp.route('/salaries/detail/<int:id>')
@login_required
def salary_detail(id):
    """View salary record details"""
    salary = SalaryRecord.query.get_or_404(id)
    return render_template('hr/salary_detail.html', salary=salary)

@hr_bp.route('/salaries/approve/<int:id>')
@login_required
def approve_salary(id):
    """Approve salary record (Admin only)"""
    if not current_user.is_admin():
        flash('Only administrators can approve salary records', 'danger')
        return redirect(url_for('hr.salary_list'))
    
    salary = SalaryRecord.query.get_or_404(id)
    
    if salary.status != 'pending':
        flash('Salary record is not pending approval', 'warning')
        return redirect(url_for('hr.salary_detail', id=id))
    
    salary.status = 'approved'
    salary.approved_by = current_user.id
    salary.approved_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'Salary record {salary.salary_number} approved successfully!', 'success')
    return redirect(url_for('hr.salary_detail', id=id))

@hr_bp.route('/salaries/mark-paid/<int:id>')
@login_required
def mark_salary_paid(id):
    """Mark salary as paid and create factory expense record"""
    if not current_user.is_admin():
        flash('Only administrators can mark salaries as paid', 'danger')
        return redirect(url_for('hr.salary_list'))
    
    salary = SalaryRecord.query.get_or_404(id)
    
    if salary.status != 'approved':
        flash('Salary must be approved before marking as paid', 'warning')
        return redirect(url_for('hr.salary_detail', id=id))
    
    try:
        # Update salary status
        salary.status = 'paid'
        salary.payment_date = date.today()
        
        # Create accounting entry using HR integration service
        voucher = HRAccountingIntegration.create_salary_payment_entry(salary)
        
        if voucher:
            # Create corresponding factory expense record
            expense = FactoryExpense(
                expense_number=FactoryExpense.generate_expense_number(),
                expense_date=date.today(),
                category='salary',  # Salaries & Benefits category
                subcategory='Employee Salary',
                description=f'Salary Payment - {salary.employee.name} ({salary.salary_number}) for period {salary.pay_period_start.strftime("%b %d")} - {salary.pay_period_end.strftime("%b %d, %Y")}',
                amount=float(salary.net_amount),
                tax_amount=0.0,
                total_amount=float(salary.net_amount),
                payment_method=salary.payment_method,
                paid_by=f'Admin - {current_user.username}',
                vendor_name=salary.employee.name,
                vendor_contact=salary.employee.phone or 'N/A',
                invoice_number=salary.salary_number,
                invoice_date=salary.pay_period_start,
                status='paid',  # Mark as paid immediately
                requested_by_id=current_user.id,
                approved_by_id=current_user.id,
                approval_date=datetime.utcnow(),
                payment_date=date.today(),
                voucher_id=voucher.id,  # Link to accounting entry
                notes=f'Auto-created from Salary Record: {salary.salary_number}\nBasic: ₹{salary.basic_amount}\nOvertime: ₹{salary.overtime_amount}\nBonus: ₹{salary.bonus_amount}\nDeductions: ₹{salary.deduction_amount}\nAdvance Deduction: ₹{salary.advance_deduction}\nNet Amount: ₹{salary.net_amount}'
            )
            
            db.session.add(expense)
            db.session.commit()
            
            # Send HR notification for salary payment completion
            try:
                from services.hr_notifications import send_hr_notification
                
                send_hr_notification(
                    'salary_payment',
                    employee_id=salary.employee.id,
                    employee_name=salary.employee.name,
                    salary_amount=salary.net_amount,
                    month_year=f"{salary.pay_period_start.strftime('%B %Y')}",
                    payment_date=salary.payment_date or datetime.now().date()
                )
            except Exception as e:
                # Don't fail payment process if notification fails
                print(f"HR notification failed: {str(e)}")
            
            flash(f'Salary {salary.salary_number} marked as paid, accounting entry created, and expense record {expense.expense_number} generated!', 'success')
        else:
            # Fallback: still create expense record even if accounting entry fails
            expense = FactoryExpense(
                expense_number=FactoryExpense.generate_expense_number(),
                expense_date=date.today(),
                category='salary',
                subcategory='Employee Salary',
                description=f'Salary Payment - {salary.employee.name} ({salary.salary_number})',
                amount=float(salary.net_amount),
                tax_amount=0.0,
                total_amount=float(salary.net_amount),
                payment_method=salary.payment_method,
                paid_by=f'Admin - {current_user.username}',
                status='paid',
                requested_by_id=current_user.id,
                approved_by_id=current_user.id,
                approval_date=datetime.utcnow(),
                payment_date=date.today()
            )
            
            db.session.add(expense)
            db.session.commit()
            
            flash(f'Salary {salary.salary_number} marked as paid and expense record {expense.expense_number} created. Note: Accounting entry creation failed.', 'warning')
        
        return redirect(url_for('hr.salary_detail', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing salary payment: {str(e)}', 'danger')
        return redirect(url_for('hr.salary_detail', id=id))

# ============ EMPLOYEE ADVANCES MANAGEMENT ============

@hr_bp.route('/advances')
@login_required
def advance_list():
    """List all employee advances"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    
    query = EmployeeAdvance.query.join(Employee)
    
    if search:
        query = query.filter(Employee.name.contains(search) | Employee.employee_code.contains(search))
    
    if status:
        query = query.filter(EmployeeAdvance.status == status)
    
    advances = query.order_by(desc(EmployeeAdvance.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate totals
    total_amount = query.with_entities(func.sum(EmployeeAdvance.amount)).scalar() or 0
    total_remaining = query.with_entities(func.sum(EmployeeAdvance.remaining_amount)).scalar() or 0
    
    return render_template('hr/advance_list.html', 
                         advances=advances, 
                         search=search, 
                         status=status,
                         total_amount=total_amount,
                         total_remaining=total_remaining)

@hr_bp.route('/advances/add', methods=['GET', 'POST'])
@login_required
def add_advance():
    """Add new employee advance"""
    form = EmployeeAdvanceForm()
    form.advance_number.data = EmployeeAdvance.generate_advance_number()
    
    if form.validate_on_submit():
        try:
            # Calculate monthly deduction
            monthly_deduction = form.amount.data / form.repayment_months.data
            
            advance = EmployeeAdvance(
                advance_number=form.advance_number.data,
                employee_id=form.employee_id.data,
                amount=form.amount.data,
                remaining_amount=form.amount.data,  # Initially full amount
                reason=form.reason.data,
                advance_date=form.advance_date.data,
                repayment_months=form.repayment_months.data,
                monthly_deduction=monthly_deduction,
                payment_method=form.payment_method.data,
                notes=form.notes.data,
                requested_by=current_user.id
            )
            
            db.session.add(advance)
            db.session.commit()
            
            flash(f'Advance request {advance.advance_number} created successfully!', 'success')
            return redirect(url_for('hr.advance_detail', id=advance.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating advance request: {str(e)}', 'danger')
    
    return render_template('hr/advance_form.html', form=form, title='Add Employee Advance')

@hr_bp.route('/advances/detail/<int:id>')
@login_required
def advance_detail(id):
    """View advance details"""
    advance = EmployeeAdvance.query.get_or_404(id)
    return render_template('hr/advance_detail.html', advance=advance)

@hr_bp.route('/advances/approve/<int:id>')
@login_required
def approve_advance(id):
    """Approve employee advance (Admin only)"""
    if not current_user.is_admin():
        flash('Only administrators can approve advances', 'danger')
        return redirect(url_for('hr.advance_list'))
    
    advance = EmployeeAdvance.query.get_or_404(id)
    
    if advance.status != 'pending':
        flash('Advance is not pending approval', 'warning')
        return redirect(url_for('hr.advance_detail', id=id))
    
    advance.status = 'approved'
    advance.approved_by = current_user.id
    advance.approved_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'Advance {advance.advance_number} approved successfully!', 'success')
    return redirect(url_for('hr.advance_detail', id=id))

@hr_bp.route('/advances/mark-paid/<int:id>')
@login_required
def mark_advance_paid(id):
    """Mark advance as paid and create factory expense record"""
    if not current_user.is_admin():
        flash('Only administrators can mark advances as paid', 'danger')
        return redirect(url_for('hr.advance_list'))
    
    advance = EmployeeAdvance.query.get_or_404(id)
    
    if advance.status not in ['approved', 'active']:
        flash('Advance must be approved before marking as paid', 'warning')
        return redirect(url_for('hr.advance_detail', id=id))
    
    try:
        # Update advance status
        advance.status = 'active'  # Active means money has been paid out
        
        # Create corresponding factory expense record
        expense = FactoryExpense(
            expense_number=FactoryExpense.generate_expense_number(),
            expense_date=date.today(),
            category='salary',  # Salaries & Benefits category
            subcategory='Employee Advance',
            description=f'Employee Advance Payment - {advance.employee.name} ({advance.advance_number}): {advance.reason}',
            amount=float(advance.amount),
            tax_amount=0.0,
            total_amount=float(advance.amount),
            payment_method=advance.payment_method,
            paid_by=f'Admin - {current_user.username}',
            vendor_name=advance.employee.name,
            vendor_contact=advance.employee.mobile_number or 'N/A',
            invoice_number=advance.advance_number,
            invoice_date=advance.advance_date,
            status='paid',  # Mark as paid immediately
            requested_by_id=current_user.id,
            approved_by_id=current_user.id,
            approval_date=datetime.utcnow(),
            payment_date=date.today(),
            notes=f'Auto-created from Employee Advance: {advance.advance_number}\nReason: {advance.reason}\nRepayment Period: {advance.repayment_months} months'
        )
        
        db.session.add(expense)
        db.session.commit()
        
        # Send HR notification for advance payment
        try:
            from services.hr_notifications import send_hr_notification
            
            send_hr_notification(
                'advance_payment',
                employee_id=advance.employee.id,
                employee_name=advance.employee.name,
                advance_amount=advance.amount,
                reason=advance.reason,
                payment_date=datetime.now().date()
            )
        except Exception as e:
            # Don't fail advance payment if notification fails
            print(f"HR advance notification failed: {str(e)}")
        
        flash(f'Advance {advance.advance_number} marked as paid and expense record {expense.expense_number} created!', 'success')
        return redirect(url_for('hr.advance_detail', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing advance payment: {str(e)}', 'danger')
        return redirect(url_for('hr.advance_detail', id=id))

# ===== ATTENDANCE MANAGEMENT ROUTES =====

@hr_bp.route('/attendance')
@login_required
def attendance_list():
    page = request.args.get('page', 1, type=int)
    employee_id = request.args.get('employee_id', None, type=int)
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)
    status = request.args.get('status', '', type=str)
    
    # Build query
    query = EmployeeAttendance.query.join(Employee)
    
    if employee_id:
        query = query.filter(EmployeeAttendance.employee_id == employee_id)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(EmployeeAttendance.attendance_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(EmployeeAttendance.attendance_date <= to_date)
        except ValueError:
            pass
    
    if status:
        query = query.filter(EmployeeAttendance.status == status)
    
    attendance_records = query.order_by(EmployeeAttendance.attendance_date.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    # Get all employees for filter dropdown
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    
    return render_template('hr/attendance_list.html', 
                         attendance_records=attendance_records,
                         employees=employees,
                         employee_id=employee_id,
                         date_from=date_from,
                         date_to=date_to,
                         status=status)

@hr_bp.route('/attendance/add', methods=['GET', 'POST'])
@login_required
def add_attendance():
    form = AttendanceForm()
    
    # Pre-select employee if coming from employee detail page
    employee_id = request.args.get('employee_id', type=int)
    if employee_id and request.method == 'GET':
        form.employee_id.data = employee_id
    
    if form.validate_on_submit():
        # Check if attendance already exists for this employee and date
        existing = EmployeeAttendance.query.filter_by(
            employee_id=form.employee_id.data,
            attendance_date=form.attendance_date.data
        ).first()
        
        if existing:
            flash('Attendance already marked for this employee on this date!', 'warning')
            return render_template('hr/attendance_form.html', form=form, title='Mark Attendance')
        
        attendance = EmployeeAttendance(
            employee_id=form.employee_id.data,
            attendance_date=form.attendance_date.data,
            check_in_time=form.check_in_time.data,
            check_out_time=form.check_out_time.data,
            overtime_hours=form.overtime_hours.data or 0.0,
            status=form.status.data,
            leave_type=form.leave_type.data if form.leave_type.data else None,
            notes=form.notes.data,
            marked_by=current_user.id
        )
        
        # Set flag if overtime was manually entered 
        if form.overtime_hours.data and form.overtime_hours.data > 0:
            attendance._manual_overtime_set = True
        
        # Calculate hours worked if check-in and check-out times are provided
        attendance.calculate_hours_worked()
        
        db.session.add(attendance)
        db.session.commit()
        
        flash(f'Attendance marked successfully for {attendance.employee.name}!', 'success')
        return redirect(url_for('hr.attendance_list'))
    
    return render_template('hr/attendance_form.html', form=form, title='Mark Attendance')

@hr_bp.route('/attendance/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_attendance(id):
    attendance = EmployeeAttendance.query.get_or_404(id)
    form = AttendanceForm(obj=attendance)
    
    if form.validate_on_submit():
        # Check if changing date and attendance already exists for new date
        if (form.attendance_date.data != attendance.attendance_date or 
            form.employee_id.data != attendance.employee_id):
            existing = EmployeeAttendance.query.filter_by(
                employee_id=form.employee_id.data,
                attendance_date=form.attendance_date.data
            ).filter(EmployeeAttendance.id != id).first()
            
            if existing:
                flash('Attendance already exists for this employee on this date!', 'warning')
                return render_template('hr/attendance_form.html', form=form, title='Edit Attendance', attendance=attendance)
        
        form.populate_obj(attendance)
        attendance.leave_type = form.leave_type.data if form.leave_type.data else None
        attendance.overtime_hours = form.overtime_hours.data or 0.0
        
        # Set flag if overtime was manually entered 
        if form.overtime_hours.data and form.overtime_hours.data > 0:
            attendance._manual_overtime_set = True
        
        # Recalculate hours worked
        attendance.calculate_hours_worked()
        
        db.session.commit()
        flash('Attendance updated successfully!', 'success')
        return redirect(url_for('hr.attendance_list'))
    
    return render_template('hr/attendance_form.html', form=form, title='Edit Attendance', attendance=attendance)

@hr_bp.route('/attendance/detail/<int:id>')
@login_required
def attendance_detail(id):
    attendance = EmployeeAttendance.query.get_or_404(id)
    return render_template('hr/attendance_detail.html', attendance=attendance)

@hr_bp.route('/attendance/delete/<int:id>')
@login_required
def delete_attendance(id):
    if not current_user.is_admin():
        flash('Only administrators can delete attendance records.', 'danger')
        return redirect(url_for('hr.attendance_list'))
        
    attendance = EmployeeAttendance.query.get_or_404(id)
    employee_name = attendance.employee.name
    attendance_date = attendance.attendance_date
    
    db.session.delete(attendance)
    db.session.commit()
    
    flash(f'Attendance record for {employee_name} on {attendance_date} deleted successfully!', 'success')
    return redirect(url_for('hr.attendance_list'))

@hr_bp.route('/attendance/bulk', methods=['GET', 'POST'])
@login_required
def bulk_attendance():
    form = BulkAttendanceForm()
    
    if form.validate_on_submit():
        try:
            attendance_date = form.attendance_date.data
            marked_count = 0
            skipped_count = 0
            
            # Get all active employees
            employees = Employee.query.filter_by(is_active=True).all()
            
            for employee in employees:
                # Check if attendance already exists for this employee and date
                existing = EmployeeAttendance.query.filter_by(
                    employee_id=employee.id,
                    attendance_date=attendance_date
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create attendance record with default present status
                attendance = EmployeeAttendance(
                    employee_id=employee.id,
                    attendance_date=attendance_date,
                    status='present',
                    marked_by=current_user.id
                )
                
                db.session.add(attendance)
                marked_count += 1
            
            db.session.commit()
            
            if marked_count > 0:
                flash(f'Bulk attendance marked successfully! {marked_count} employees marked as present. {skipped_count} employees skipped (already marked).', 'success')
            else:
                flash('No new attendance records created. All employees already have attendance marked for this date.', 'info')
                
            return redirect(url_for('hr.attendance_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error marking bulk attendance: {str(e)}', 'danger')
    
    # Get active employees for preview
    active_employees = Employee.query.filter_by(is_active=True).all()
    return render_template('hr/bulk_attendance_form.html', form=form, active_employees=active_employees)
