from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms_department import DepartmentForm
from models.department import Department
from models import Employee
from app import db
from sqlalchemy import desc, func

department_bp = Blueprint('department', __name__)

@department_bp.route('/dashboard')
@login_required
def dashboard():
    """Department management dashboard"""
    # Statistics
    total_departments = Department.query.count()
    active_departments = Department.query.filter_by(is_active=True).count()
    inactive_departments = total_departments - active_departments
    
    # Employees by department
    dept_employee_counts = db.session.query(
        Department.name,
        func.count(Employee.id).label('employee_count')
    ).outerjoin(Employee, Employee.department == Department.code)\
     .filter(Department.is_active == True)\
     .group_by(Department.id, Department.name)\
     .order_by(desc('employee_count')).all()
    
    # Recent departments
    recent_departments = Department.query.order_by(desc(Department.created_at)).limit(5).all()
    
    return render_template('settings/department_dashboard.html',
                         total_departments=total_departments,
                         active_departments=active_departments,
                         inactive_departments=inactive_departments,
                         dept_employee_counts=dept_employee_counts,
                         recent_departments=recent_departments)

@department_bp.route('/list')
@login_required
def list_departments():
    """List all departments"""
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')
    
    query = Department.query
    
    if search:
        query = query.filter(Department.name.ilike(f'%{search}%'))
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    departments = query.order_by(Department.name).all()
    
    return render_template('settings/department_list.html', 
                         departments=departments,
                         search=search,
                         status_filter=status_filter)

@department_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_department():
    """Add new department"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('department.list_departments'))
    
    form = DepartmentForm()
    
    if form.validate_on_submit():
        department = Department(
            name=form.name.data,
            code=form.code.data,
            description=form.description.data,
            is_active=form.is_active.data
        )
        
        db.session.add(department)
        db.session.commit()
        
        flash(f'Department "{department.name}" added successfully!', 'success')
        return redirect(url_for('department.list_departments'))
    
    return render_template('settings/department_form.html', 
                         form=form, 
                         title='Add Department')

@department_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_department(id):
    """Edit existing department"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('department.list_departments'))
    
    department = Department.query.get_or_404(id)
    form = DepartmentForm(department_id=id, obj=department)
    
    if form.validate_on_submit():
        department.name = form.name.data
        department.code = form.code.data
        department.description = form.description.data
        department.is_active = form.is_active.data
        
        db.session.commit()
        
        flash(f'Department "{department.name}" updated successfully!', 'success')
        return redirect(url_for('department.list_departments'))
    
    return render_template('settings/department_form.html', 
                         form=form, 
                         title='Edit Department',
                         department=department)

@department_bp.route('/toggle_status/<int:id>')
@login_required
def toggle_status(id):
    """Toggle department active/inactive status"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('department.list_departments'))
    
    department = Department.query.get_or_404(id)
    
    # Check if department has employees before deactivating
    if department.is_active:
        employee_count = Employee.query.filter_by(department=department.code).count()
        if employee_count > 0:
            flash(f'Cannot deactivate department "{department.name}" as it has {employee_count} active employees.', 'warning')
            return redirect(url_for('department.list_departments'))
    
    department.is_active = not department.is_active
    db.session.commit()
    
    status = 'activated' if department.is_active else 'deactivated'
    flash(f'Department "{department.name}" {status} successfully!', 'success')
    
    return redirect(url_for('department.list_departments'))

@department_bp.route('/delete/<int:id>')
@login_required
def delete_department(id):
    """Delete department (soft delete by deactivating)"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('department.list_departments'))
    
    department = Department.query.get_or_404(id)
    
    # Check if department has employees
    employee_count = Employee.query.filter_by(department=department.code).count()
    if employee_count > 0:
        flash(f'Cannot delete department "{department.name}" as it has {employee_count} employees assigned to it.', 'danger')
        return redirect(url_for('department.list_departments'))
    
    # Soft delete by deactivating
    department.is_active = False
    db.session.commit()
    
    flash(f'Department "{department.name}" deleted successfully!', 'success')
    return redirect(url_for('department.list_departments'))

@department_bp.route('/api/choices')
@login_required
def api_choices():
    """API endpoint for department choices"""
    departments = Department.get_choices()
    return jsonify(departments)