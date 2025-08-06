from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms import CompanySettingsForm, NotificationSettingsForm
from models import User, CompanySettings, NotificationSettings, PurchaseOrder, SalesOrder, Item, JobWork, Production, MaterialInspection, QualityIssue, FactoryExpense, Employee, SalaryRecord, EmployeeAdvance, Supplier
from models.accounting import Account, AccountGroup, Voucher, VoucherType, JournalEntry
from models.permissions import Permission, UserPermission, DEFAULT_PERMISSIONS, init_permissions
from app import db
from services.notifications import notification_service
import os

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/dashboard')
@login_required
def dashboard():
    """Settings dashboard page"""
    settings = CompanySettings.get_settings()
    
    # Removed Tally statistics - now handled in Tally dashboard
    
    # Import csrf token function
    from flask_wtf.csrf import generate_csrf
    return render_template('settings/dashboard.html',
                         settings=settings,
                         csrf_token=generate_csrf())

@settings_bp.route('/company', methods=['GET', 'POST'])
@login_required
def company_settings():
    """Company settings page for managing business information"""
    settings = CompanySettings.get_settings()
    form = CompanySettingsForm(obj=settings)
    
    if form.validate_on_submit():
        settings.company_name = form.company_name.data
        settings.address_line1 = form.address_line1.data
        settings.address_line2 = form.address_line2.data
        settings.city = form.city.data
        settings.state = form.state.data
        settings.pin_code = form.pin_code.data
        settings.phone = form.phone.data
        settings.email = form.email.data
        settings.gst_number = form.gst_number.data
        settings.arn_number = form.arn_number.data
        settings.website = form.website.data
        
        db.session.commit()
        flash('Company settings updated successfully', 'success')
        return redirect(url_for('settings.company_settings'))
    
    return render_template('settings/company.html', form=form, settings=settings)

@settings_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notification_settings():
    """Notification settings page"""
    # Get or create notification settings
    settings = NotificationSettings.query.first()
    if not settings:
        settings = NotificationSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = NotificationSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        # Update settings from form
        form.populate_obj(settings)
        db.session.commit()
        flash('Notification settings updated successfully!', 'success')
        return redirect(url_for('settings.notification_settings'))
    
    return render_template('settings/notifications.html', form=form, settings=settings)

@settings_bp.route('/test_notification', methods=['POST'])
@login_required
def test_notification():
    """Test notification endpoints"""
    data = request.get_json()
    notification_type = data.get('type')
    recipient = data.get('recipient')
    
    if notification_type == 'email':
        success = notification_service.send_email(
            recipient, 
            "Test Email from AK Factory", 
            "This is a test email to verify your email notification settings."
        )
    elif notification_type == 'sms':
        success = notification_service.send_sms(
            recipient, 
            "Test SMS from AK Factory: Your SMS notifications are working correctly!"
        )
    elif notification_type == 'whatsapp':
        success = notification_service.send_whatsapp(
            recipient, 
            "Test WhatsApp from AK Factory: Your WhatsApp notifications are working correctly!"
        )
    else:
        return jsonify({'success': False, 'message': 'Invalid notification type'})
    
    return jsonify({
        'success': success,
        'message': f'Test {notification_type} sent successfully!' if success else f'Failed to send test {notification_type}'
    })

@settings_bp.route('/notification_templates')
@login_required
def notification_templates():
    """Notification template management page"""
    return render_template('settings/notification_templates.html')

@settings_bp.route('/save_notification_template', methods=['POST'])
@login_required
def save_notification_template():
    """Save notification template configuration"""
    data = request.get_json()
    template_type = data.get('template_type')
    template_data = data.get('data')
    
    # In a real implementation, you would save this to database
    # For now, we'll just return success
    return jsonify({
        'success': True,
        'message': f'{template_type} template saved successfully'
    })

@settings_bp.route('/test_notification_template', methods=['POST'])
@login_required
def test_notification_template():
    """Send test notification using template"""
    data = request.get_json()
    template_type = data.get('template_type')
    recipient = data.get('recipient')
    template_data = data.get('data')
    
    # Create test message based on template
    if '@' in recipient:
        # Email test
        success = notification_service.send_email(
            recipient,
            f"Test: {template_data.get('email_subject', 'Test Subject')}",
            f"This is a test message from your {template_type} template."
        )
    else:
        # SMS test
        success = notification_service.send_sms(
            recipient,
            f"Test: {template_data.get('sms_message', 'Test SMS message')}"
        )
    
    return jsonify({
        'success': success,
        'message': 'Test notification sent' if success else 'Failed to send test notification'
    })

@settings_bp.route('/users')
@login_required
def user_management():
    """User management page (admin only)"""
    if not current_user.role == 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get all users
    users = User.query.order_by(User.created_at.desc()).all()
    
    return render_template('settings/users.html', users=users)

@settings_bp.route('/users/create', methods=['POST'])
@login_required
def create_user():
    """Create new user (admin only)"""
    if not current_user.role == 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        
        # Validation
        if not all([username, email, password, role]):
            flash('All fields are required', 'danger')
            return redirect(url_for('settings.user_management'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('settings.user_management'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('settings.user_management'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Create new user
        from werkzeug.security import generate_password_hash
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User {username} created successfully', 'success')
        return redirect(url_for('settings.user_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'danger')
        return redirect(url_for('settings.user_management'))

@settings_bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    """Reset user password (admin only)"""
    if not current_user.role == 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Don't allow resetting own password
        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Cannot reset your own password'})
        
        # Get request data
        data = request.get_json() or {}
        reset_type = data.get('reset_type', 'generate')
        custom_password = data.get('custom_password')
        
        if reset_type == 'custom' and custom_password:
            # Validate custom password
            if len(custom_password) < 6:
                return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
            
            new_password = custom_password
            display_password = "Custom password set successfully"
        else:
            # Generate random password
            import string
            import random
            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            display_password = new_password
        
        # Update password
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Password reset successfully',
            'new_password': display_password,
            'is_custom': reset_type == 'custom'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error resetting password: {str(e)}'})

@settings_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user (admin only)"""
    if not current_user.role == 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Don't allow deleting own account
        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Cannot delete your own account'})
        
        # Don't delete if this is the only admin
        if user.role == 'admin':
            admin_count = User.query.filter_by(role='admin').count()
            if admin_count <= 1:
                return jsonify({'success': False, 'message': 'Cannot delete the last admin user'})
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'})

@settings_bp.route('/change_username', methods=['POST'])
@login_required
def change_username():
    """Change current user's username"""
    try:
        new_username = request.form.get('new_username')
        
        if not new_username:
            flash('Username is required', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Check if username already exists (excluding current user)
        existing_user = User.query.filter(
            User.username == new_username, 
            User.id != current_user.id
        ).first()
        
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Update username
        current_user.username = new_username
        db.session.commit()
        
        flash('Username updated successfully', 'success')
        return redirect(url_for('settings.user_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating username: {str(e)}', 'danger')
        return redirect(url_for('settings.user_management'))

@settings_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change current user's password"""
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')
        
        # Validation
        if not all([current_password, new_password, confirm_new_password]):
            flash('All fields are required', 'danger')
            return redirect(url_for('settings.user_management'))
        
        if new_password != confirm_new_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('settings.user_management'))
        
        if len(new_password) < 6:
            flash('New password must be at least 6 characters', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Verify current password
        from werkzeug.security import check_password_hash, generate_password_hash
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('settings.user_management'))
        
        # Update password
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        flash('Password updated successfully', 'success')
        return redirect(url_for('settings.user_management'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating password: {str(e)}', 'danger')
        return redirect(url_for('settings.user_management'))

@settings_bp.route('/permissions')
@login_required
def user_permissions():
    """User permissions management page (admin only)"""
    if not current_user.role == 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Initialize permissions if they don't exist
    init_permissions()
    
    # Get all users (exclude admins for permission assignment)
    users = User.query.order_by(User.username).all()
    
    # Get selected user
    selected_user_id = request.args.get('user_id')
    selected_user = None
    user_permissions = set()
    
    if selected_user_id:
        selected_user = User.query.get(selected_user_id)
        if selected_user and selected_user.role != 'admin':
            # Get user's current permissions
            user_perms = UserPermission.query.filter_by(
                user_id=selected_user.id,
                granted=True
            ).join(Permission).all()
            user_permissions = {up.permission.code for up in user_perms}
    
    # Group permissions by category
    permissions_by_category = {}
    for category, perms in DEFAULT_PERMISSIONS.items():
        permissions_by_category[category] = Permission.query.filter_by(category=category).all()
    
    # Category icons
    category_icons = {
        'inventory': 'boxes',
        'purchase': 'shopping-cart',
        'sales': 'chart-line',
        'production': 'industry',
        'jobwork': 'tools',
        'quality': 'award',
        'employees': 'users',
        'expenses': 'receipt',
        'reports': 'chart-bar',
        'settings': 'cog',
        'admin': 'crown'
    }
    
    return render_template('settings/permissions.html',
                         users=users,
                         selected_user=selected_user,
                         user_permissions=user_permissions,
                         permissions_by_category=permissions_by_category,
                         category_icons=category_icons)

@settings_bp.route('/permissions/<int:user_id>', methods=['POST'])
@login_required
def update_user_permissions(user_id):
    """Update user permissions (admin only)"""
    if not current_user.role == 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        if user.role == 'admin':
            flash('Cannot modify permissions for admin users', 'warning')
            return redirect(url_for('settings.user_permissions', user_id=user_id))
        
        # Get selected permissions
        selected_permissions = request.form.getlist('permissions')
        
        # Get all available permissions
        all_permissions = Permission.query.all()
        
        # Update permissions
        for permission in all_permissions:
            if permission.code in selected_permissions:
                user.grant_permission(permission.code, current_user.id)
            else:
                user.revoke_permission(permission.code)
        
        db.session.commit()
        flash(f'Permissions updated successfully for {user.username}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating permissions: {str(e)}', 'danger')
    
    return redirect(url_for('settings.user_permissions', user_id=user_id))

@settings_bp.route('/reset_database', methods=['POST'])
@login_required
def reset_database():
    """Selective database reset based on user choices (Admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('settings.dashboard'))
    
    try:
        # Get user selections - debug print form data
        print("Form data received:", request.form)
        
        reset_purchase_sales = 'reset_purchase_sales' in request.form
        reset_inventory = 'reset_inventory' in request.form
        reset_production = 'reset_production' in request.form
        reset_inspections = 'reset_inspections' in request.form
        reset_expenses = 'reset_expenses' in request.form
        reset_employees = 'reset_employees' in request.form
        reset_documents = 'reset_documents' in request.form
        reset_accounting = 'reset_accounting' in request.form
        reset_grn = 'reset_grn' in request.form
        reset_batches = 'reset_batches' in request.form
        
        print("Reset flags:", {
            'purchase_sales': reset_purchase_sales,
            'inventory': reset_inventory, 
            'production': reset_production,
            'inspections': reset_inspections,
            'expenses': reset_expenses,
            'employees': reset_employees,
            'documents': reset_documents,
            'accounting': reset_accounting,
            'grn': reset_grn,
            'batches': reset_batches
        })
        
        deleted_items = []
        
        # Delete in order to respect foreign key constraints
        # CRITICAL: Delete child records first, then parent records
        
        # Get counts before deletion (with error handling for schema mismatches)
        counts = {}
        
        try:
            counts['material_inspections'] = MaterialInspection.query.count() if reset_inspections else 0
        except Exception as e:
            print(f"Error counting material inspections: {e}")
            counts['material_inspections'] = 0
            
        try:
            counts['quality_issues'] = QualityIssue.query.count() if reset_inspections else 0
        except Exception as e:
            print(f"Error counting quality issues: {e}")
            counts['quality_issues'] = 0
            
        try:
            counts['productions'] = Production.query.count() if reset_production else 0
        except Exception as e:
            print(f"Error counting productions: {e}")
            counts['productions'] = 0
            
        try:
            counts['job_works'] = JobWork.query.count() if reset_production else 0
        except Exception as e:
            print(f"Error counting job works: {e}")
            counts['job_works'] = 0
            
        try:
            counts['factory_expenses'] = FactoryExpense.query.count() if reset_expenses else 0
        except Exception as e:
            print(f"Error counting factory expenses: {e}")
            counts['factory_expenses'] = 0
            
        try:
            counts['salary_records'] = SalaryRecord.query.count() if reset_employees else 0
        except Exception as e:
            print(f"Error counting salary records: {e}")
            counts['salary_records'] = 0
            
        try:
            counts['employee_advances'] = EmployeeAdvance.query.count() if reset_employees else 0
        except Exception as e:
            print(f"Error counting employee advances: {e}")
            counts['employee_advances'] = 0
            
        try:
            counts['employees'] = Employee.query.count() if reset_employees else 0
        except Exception as e:
            print(f"Error counting employees: {e}")
            counts['employees'] = 0
            
        try:
            counts['sales_orders'] = SalesOrder.query.count() if reset_purchase_sales else 0
        except Exception as e:
            print(f"Error counting sales orders: {e}")
            counts['sales_orders'] = 0
            
        try:
            counts['purchase_orders'] = PurchaseOrder.query.count() if reset_purchase_sales else 0
        except Exception as e:
            print(f"Error counting purchase orders: {e}")
            counts['purchase_orders'] = 0
            
        try:
            counts['items'] = Item.query.count() if reset_inventory else 0
        except Exception as e:
            print(f"Error counting items: {e}")
            counts['items'] = 0
        
        # Delete all child tables first to avoid foreign key violations
        if reset_inspections or reset_production or reset_purchase_sales or reset_inventory:
            print("Deleting all related child records first...")
            
            # List of child tables to delete in correct order (batch tables first)
            child_tables = [
                "jobwork_batches",           # Job work batch tracking
                "batch_traceability",        # Batch traceability records  
                "batch_movements",           # Batch movement history
                "item_batches",              # Main batch inventory data
                "grn_line_items",
                "grn", 
                "daily_job_work_entries",
                "job_work_processes",
                "job_work_rates",
                "purchase_order_items",
                "sales_order_items",
                "bom_items",
                "boms",
                "item_uom_conversions",
                "material_inspections"
            ]
            
            # Delete each table with error handling
            for table in child_tables:
                try:
                    db.session.execute(db.text(f"DELETE FROM {table}"))
                    print(f"Deleted from {table}")
                except Exception as e:
                    print(f"Error deleting from {table}: {e}")
                    # Continue with next table even if one fails
                    
            print("Child records deletion completed")
        
        # Now delete parent records in safe order
        if reset_inspections:
            print(f"Deleting {counts['material_inspections']} material inspections and {counts['quality_issues']} quality issues")
            try:
                db.session.execute(db.text("DELETE FROM quality_issues"))
                print("Deleted quality issues")
            except Exception as e:
                print(f"Error deleting quality issues: {e}")
            deleted_items.append(f"Material Inspections ({counts['material_inspections']}) & Quality Issues ({counts['quality_issues']})")
        
        if reset_production:
            print(f"Deleting {counts['productions']} productions and {counts['job_works']} job works")
            try:
                db.session.execute(db.text("DELETE FROM productions"))
                print("Deleted productions")
            except Exception as e:
                print(f"Error deleting productions: {e}")
            try:
                db.session.execute(db.text("DELETE FROM job_works"))
                print("Deleted job works")
            except Exception as e:
                print(f"Error deleting job works: {e}")
            deleted_items.append(f"Production Orders ({counts['productions']}) & Job Work ({counts['job_works']})")
        
        if reset_expenses:
            print(f"Deleting {counts['factory_expenses']} factory expenses")
            try:
                db.session.execute(db.text("DELETE FROM factory_expenses"))
                print("Deleted factory expenses")
            except Exception as e:
                print(f"Error deleting factory expenses: {e}")
            deleted_items.append(f"Factory Expenses ({counts['factory_expenses']})")
        
        if reset_employees:
            print(f"Deleting {counts['employees']} employees, {counts['salary_records']} salary records, {counts['employee_advances']} advances")
            try:
                db.session.execute(db.text("DELETE FROM salary_records"))
                print("Deleted salary records")
            except Exception as e:
                print(f"Error deleting salary records: {e}")
            try:
                db.session.execute(db.text("DELETE FROM employee_advances"))
                print("Deleted employee advances")
            except Exception as e:
                print(f"Error deleting employee advances: {e}")
            try:
                db.session.execute(db.text("DELETE FROM employees"))
                print("Deleted employees")
            except Exception as e:
                print(f"Error deleting employees: {e}")
            deleted_items.append(f"Employee Records ({counts['employees']}) & Payroll ({counts['salary_records'] + counts['employee_advances']})")
        
        if reset_purchase_sales:
            print(f"Deleting {counts['purchase_orders']} purchase orders and {counts['sales_orders']} sales orders")
            try:
                db.session.execute(db.text("DELETE FROM sales_orders"))
                print("Deleted sales orders")
            except Exception as e:
                print(f"Error deleting sales orders: {e}")
            try:
                db.session.execute(db.text("DELETE FROM purchase_orders"))
                print("Deleted purchase orders")
            except Exception as e:
                print(f"Error deleting purchase orders: {e}")
            deleted_items.append(f"Purchase Orders ({counts['purchase_orders']}) & Sales Orders ({counts['sales_orders']})")
        
        if reset_inventory:
            print(f"Deleting {counts['items']} inventory items")
            try:
                # Use TRUNCATE with CASCADE to properly handle foreign keys
                db.session.execute(db.text("TRUNCATE TABLE items RESTART IDENTITY CASCADE"))
                print("Truncated inventory items table with CASCADE")
            except Exception as e:
                print(f"Error deleting inventory items: {e}")
                # Don't rollback here, continue with other operations
            deleted_items.append(f"Inventory Items ({counts['items']})")
        
        if reset_accounting:
            print("Resetting accounting and finance records")
            try:
                # Reset all account balances to zero first
                result = db.session.execute(db.text("UPDATE accounts SET current_balance = 0, opening_balance = 0"))
                print(f"Reset {result.rowcount} account balances to zero")
                
                # Use TRUNCATE with CASCADE for better foreign key handling
                try:
                    db.session.execute(db.text("TRUNCATE TABLE vouchers RESTART IDENTITY CASCADE"))
                    print("Cleared vouchers with CASCADE")
                except Exception as ve:
                    print(f"Vouchers clear failed: {ve}")
                
                try:
                    db.session.execute(db.text("TRUNCATE TABLE journal_entries RESTART IDENTITY CASCADE"))
                    print("Cleared journal entries with CASCADE") 
                except Exception as je:
                    print(f"Journal entries clear failed: {je}")
                
                deleted_items.append('Accounting & Finance Records (All Balances Reset)')
            except Exception as e:
                print(f"Error resetting accounting records: {e}")
                # Don't rollback here, continue with other operations
        
        if reset_grn:
            print("Deleting GRN (Goods Receipt Note) records")
            try:
                # GRN line items should already be deleted in child tables section
                db.session.execute(db.text("DELETE FROM grn"))
                print("Deleted GRN records")
                deleted_items.append('GRN & Receipt Records')
            except Exception as e:
                print(f"Error deleting GRN records: {e}")
        
        if reset_batches:
            print("Deleting batch tracking records")
            try:
                # Batch related tables should already be deleted in child tables section
                # This ensures any remaining batch data is cleared
                db.session.execute(db.text("DELETE FROM inventory_batches"))
                print("Deleted inventory batches")
                deleted_items.append('Batch Tracking Records')
            except Exception as e:
                print(f"Error deleting batch records: {e}")
        
        if reset_documents:
            # Clear uploads directory
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
            if os.path.exists(uploads_dir):
                import shutil
                shutil.rmtree(uploads_dir)
                os.makedirs(uploads_dir, exist_ok=True)
            deleted_items.append('Uploaded Documents')
        
        print("Committing database changes...")
        try:
            db.session.commit()
            print("Database changes committed successfully")
            
            if deleted_items:
                # Check if batch data was cleared
                try:
                    batch_count = db.session.execute(db.text("SELECT COUNT(*) FROM item_batches")).scalar() or 0
                except:
                    batch_count = 0
                    
                success_msg = f'Database reset successful! Cleared: {", ".join(deleted_items)}'
                if batch_count == 0:
                    success_msg += ", Batch Data (All cleared)"
                else:
                    success_msg += f", Batch Data ({batch_count} records remaining)"
                    
                print(f"Success message: {success_msg}")
                flash(success_msg, 'success')
            else:
                flash('No items were selected for reset.', 'info')
                
        except Exception as commit_error:
            print(f"Commit error: {commit_error}")
            db.session.rollback()
            flash(f'Error committing changes: {str(commit_error)}', 'danger')
        
    except Exception as e:
        print(f"General error: {e}")
        db.session.rollback()
        flash(f'Error resetting database: {str(e)}', 'danger')
    
    return redirect(url_for('settings.dashboard'))