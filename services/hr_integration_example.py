"""
HR Notification Integration Examples
Shows how to integrate HR notifications into your existing HR routes
"""

# Example of how to integrate HR notifications into your employee management routes

# In your employee routes (routes/employees.py), you would add:

"""
from services.hr_notifications import send_hr_notification
from datetime import datetime

# Example 1: When creating a new employee
@employees_bp.route('/add', methods=['POST'])
def add_employee():
    # ... your existing employee creation logic ...
    
    if employee_created_successfully:
        # Send HR notification for new employee joining
        send_hr_notification(
            'employee_joining',
            employee_id=new_employee.id,
            employee_name=new_employee.name,
            designation=new_employee.designation,
            department=new_employee.department,
            joining_date=new_employee.joining_date or datetime.now()
        )
    
    # ... rest of your route logic ...

# Example 2: When processing salary payment
@employees_bp.route('/salary/pay/<int:employee_id>', methods=['POST'])
def process_salary_payment(employee_id):
    # ... your existing salary processing logic ...
    
    if salary_processed_successfully:
        # Send HR notification for salary payment
        send_hr_notification(
            'salary_payment',
            employee_id=employee.id,
            employee_name=employee.name,
            salary_amount=salary_amount,
            month_year=payment_period,
            payment_date=datetime.now()
        )
    
    # ... rest of your route logic ...

# Example 3: When processing advance payment
@employees_bp.route('/advance/pay/<int:employee_id>', methods=['POST'])
def process_advance_payment(employee_id):
    # ... your existing advance processing logic ...
    
    if advance_processed_successfully:
        # Send HR notification for advance payment
        send_hr_notification(
            'advance_payment',
            employee_id=employee.id,
            employee_name=employee.name,
            advance_amount=advance_amount,
            reason=request.form.get('reason', 'General advance'),
            payment_date=datetime.now()
        )
    
    # ... rest of your route logic ...

# Example 4: When employee leaves
@employees_bp.route('/terminate/<int:employee_id>', methods=['POST'])
def terminate_employee(employee_id):
    # ... your existing termination logic ...
    
    if termination_processed_successfully:
        # Send HR notification for employee leaving
        send_hr_notification(
            'employee_leaving',
            employee_id=employee.id,
            employee_name=employee.name,
            last_working_day=last_working_date,
            reason=termination_reason
        )
    
    # ... rest of your route logic ...

# Example 5: When leave application is submitted
@employees_bp.route('/leave/apply', methods=['POST'])
def apply_leave():
    # ... your existing leave application logic ...
    
    if leave_application_created:
        # Send HR notification for leave application
        send_hr_notification(
            'leave_application',
            employee_id=employee.id,
            employee_name=employee.name,
            leave_type=leave_type,
            from_date=from_date,
            to_date=to_date,
            days=total_days,
            reason=leave_reason
        )
    
    # ... rest of your route logic ...

# Example 6: Attendance alerts (can be called from attendance processing)
def check_attendance_and_alert(employee_id, employee_name):
    # Check for attendance issues
    if has_attendance_issue:
        send_hr_notification(
            'attendance_alert',
            employee_id=employee_id,
            employee_name=employee_name,
            alert_type='Irregular Attendance',
            details='Employee has been absent for 3 consecutive days without leave application'
        )

# Example 7: Performance review completion
@employees_bp.route('/performance/submit/<int:employee_id>', methods=['POST'])
def submit_performance_review(employee_id):
    # ... your existing performance review logic ...
    
    if review_submitted_successfully:
        # Send HR notification for performance review
        send_hr_notification(
            'performance_review',
            employee_id=employee.id,
            employee_name=employee.name,
            review_period=review_period,
            reviewer=current_user.name,
            rating=performance_rating
        )
    
    # ... rest of your route logic ...

# Example 8: Overtime approval
@employees_bp.route('/overtime/approve/<int:overtime_id>', methods=['POST'])
def approve_overtime(overtime_id):
    # ... your existing overtime approval logic ...
    
    if overtime_approved:
        # Send HR notification for overtime approval
        send_hr_notification(
            'overtime_approval',
            employee_id=overtime_record.employee_id,
            employee_name=overtime_record.employee.name,
            overtime_hours=overtime_record.hours,
            date=overtime_record.date,
            reason=overtime_record.reason,
            approved_by=current_user.name
        )
    
    # ... rest of your route logic ...
"""

# Integration Notes:
# 1. Import the HR notification service: from services.hr_notifications import send_hr_notification
# 2. Call the appropriate notification function after successful operations
# 3. The notification service will automatically find HR recipients and send notifications via their preferred channels
# 4. All notifications are logged in the notification_logs table for tracking
# 5. Settings control whether notifications are sent (can be disabled globally or per event type)