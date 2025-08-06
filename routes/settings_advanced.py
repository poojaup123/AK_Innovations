"""
Advanced Centralized Settings Routes
Handles multi-company settings and system configuration
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models.settings import (
    Company, UserCompanyAccess, SystemSettings, InventorySettings, 
    AccountingSettings, ProductionSettings, JobWorkSettings, DEFAULT_SETTINGS
)
from models import User
from models.accounting import Account

settings_advanced_bp = Blueprint('settings_advanced', __name__, url_prefix='/settings')

@settings_advanced_bp.route('/advanced')
@login_required
def settings_dashboard():
    """Centralized settings dashboard"""
    # Temporarily remove admin check for testing
    # if not current_user.is_admin():
    #     flash('Admin access required', 'error')
    #     return redirect(url_for('main.dashboard'))
    
    # Get statistics
    stats = {
        'total_companies': Company.query.count(),
        'active_companies': Company.query.filter_by(is_active=True).count(),
        'total_users': User.query.count(),
        'settings_count': SystemSettings.query.count()
    }
    
    # Get recent settings changes
    recent_changes = SystemSettings.query.order_by(
        SystemSettings.updated_at.desc()
    ).limit(10).all()
    
    return render_template('settings/dashboard_advanced.html', 
                         stats=stats, 
                         recent_changes=recent_changes)

# Company Management Routes
@settings_advanced_bp.route('/companies')
@login_required
def company_management():
    """Company management interface"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    companies = Company.query.order_by(Company.name).all()
    return render_template('settings/companies.html', companies=companies)

@settings_advanced_bp.route('/companies/new', methods=['GET', 'POST'])
@login_required
def add_company():
    """Add new company"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            company = Company(
                name=request.form.get('name'),
                code=request.form.get('code'),
                address_line1=request.form.get('address_line1'),
                address_line2=request.form.get('address_line2'),
                city=request.form.get('city'),
                state=request.form.get('state'),
                pin_code=request.form.get('pin_code'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                gst_number=request.form.get('gst_number'),
                arn_number=request.form.get('arn_number'),
                pan_number=request.form.get('pan_number'),
                website=request.form.get('website')
            )
            
            db.session.add(company)
            db.session.commit()
            
            # Create default settings for the company
            _create_default_company_settings(company.id)
            
            flash(f'Company {company.name} added successfully', 'success')
            return redirect(url_for('settings_advanced.company_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding company: {str(e)}', 'error')
    
    return render_template('settings/company_form.html')

@settings_advanced_bp.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_company(company_id):
    """Edit company"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        try:
            company.name = request.form.get('name')
            company.code = request.form.get('code')
            company.address_line1 = request.form.get('address_line1')
            company.address_line2 = request.form.get('address_line2')
            company.city = request.form.get('city')
            company.state = request.form.get('state')
            company.pin_code = request.form.get('pin_code')
            company.phone = request.form.get('phone')
            company.email = request.form.get('email')
            company.gst_number = request.form.get('gst_number')
            company.arn_number = request.form.get('arn_number')
            company.pan_number = request.form.get('pan_number')
            company.website = request.form.get('website')
            company.is_active = 'is_active' in request.form
            
            db.session.commit()
            flash(f'Company {company.name} updated successfully', 'success')
            return redirect(url_for('settings_advanced.company_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating company: {str(e)}', 'error')
    
    return render_template('settings/company_form.html', company=company)

@settings_advanced_bp.route('/companies/<int:company_id>/set-default', methods=['POST'])
@login_required
def set_default_company(company_id):
    """Set default company"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    if Company.set_default_company(company_id):
        return jsonify({'success': True, 'message': 'Default company updated'})
    else:
        return jsonify({'success': False, 'message': 'Company not found'})

# User-Company Assignment Routes
@settings_advanced_bp.route('/companies/<int:company_id>/users')
@login_required
def company_users(company_id):
    """Manage users for a company"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    company = Company.query.get_or_404(company_id)
    
    # Get assigned users
    assigned_users = db.session.query(User, UserCompanyAccess).join(
        UserCompanyAccess, User.id == UserCompanyAccess.user_id
    ).filter(
        UserCompanyAccess.company_id == company_id,
        UserCompanyAccess.is_active == True
    ).all()
    
    # Get unassigned users
    assigned_user_ids = [user.id for user, _ in assigned_users]
    unassigned_users = User.query.filter(~User.id.in_(assigned_user_ids)).all()
    
    return render_template('settings/company_users.html', 
                         company=company,
                         assigned_users=assigned_users,
                         unassigned_users=unassigned_users)

@settings_advanced_bp.route('/companies/<int:company_id>/users/assign', methods=['POST'])
@login_required
def assign_user_to_company(company_id):
    """Assign user to company"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    user_id = request.json.get('user_id')
    
    try:
        # Check if assignment already exists
        existing = UserCompanyAccess.query.filter_by(
            user_id=user_id, 
            company_id=company_id
        ).first()
        
        if existing:
            existing.is_active = True
        else:
            assignment = UserCompanyAccess(
                user_id=user_id,
                company_id=company_id,
                assigned_by=current_user.id
            )
            db.session.add(assignment)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'User assigned to company'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@settings_advanced_bp.route('/companies/<int:company_id>/users/remove', methods=['POST'])
@login_required
def remove_user_from_company(company_id):
    """Remove user from company"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    user_id = request.json.get('user_id')
    
    try:
        assignment = UserCompanyAccess.query.filter_by(
            user_id=user_id, 
            company_id=company_id
        ).first()
        
        if assignment:
            assignment.is_active = False
            db.session.commit()
            return jsonify({'success': True, 'message': 'User removed from company'})
        else:
            return jsonify({'success': False, 'message': 'Assignment not found'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Settings Configuration Routes
@settings_advanced_bp.route('/inventory')
@login_required
def inventory_settings():
    """Inventory settings configuration"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    companies = Company.query.filter_by(is_active=True).all()
    selected_company_id = request.args.get('company_id', type=int)
    
    if selected_company_id:
        settings = InventorySettings.query.filter_by(company_id=selected_company_id).first()
    else:
        settings = None
    
    return render_template('settings/inventory.html', 
                         companies=companies,
                         selected_company_id=selected_company_id,
                         settings=settings)

@settings_advanced_bp.route('/inventory/save', methods=['POST'])
@login_required
def save_inventory_settings():
    """Save inventory settings"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    company_id = request.json.get('company_id')
    
    try:
        settings = InventorySettings.query.filter_by(company_id=company_id).first()
        if not settings:
            settings = InventorySettings(company_id=company_id)
            db.session.add(settings)
        
        # Update settings from request
        settings.shared_inventory = request.json.get('shared_inventory', False)
        settings.stock_valuation_method = request.json.get('stock_valuation_method', 'FIFO')
        settings.enable_multi_uom = request.json.get('enable_multi_uom', True)
        settings.enable_batch_tracking = request.json.get('enable_batch_tracking', True)
        settings.warn_negative_stock = request.json.get('warn_negative_stock', True)
        settings.auto_generate_batch = request.json.get('auto_generate_batch', True)
        settings.minimum_stock_alert = request.json.get('minimum_stock_alert', True)
        settings.reorder_level_alert = request.json.get('reorder_level_alert', True)
        settings.expiry_alert_days = request.json.get('expiry_alert_days', 30)
        settings.updated_by = current_user.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Inventory settings saved'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@settings_advanced_bp.route('/accounting')
@login_required
def accounting_settings():
    """Accounting settings configuration"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    companies = Company.query.filter_by(is_active=True).all()
    accounts = Account.query.filter_by(is_active=True).all()
    selected_company_id = request.args.get('company_id', type=int)
    
    if selected_company_id:
        settings = AccountingSettings.query.filter_by(company_id=selected_company_id).first()
    else:
        settings = None
    
    return render_template('settings/accounting.html', 
                         companies=companies,
                         accounts=accounts,
                         selected_company_id=selected_company_id,
                         settings=settings)

@settings_advanced_bp.route('/production')
@login_required
def production_settings():
    """Production settings configuration"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    companies = Company.query.filter_by(is_active=True).all()
    selected_company_id = request.args.get('company_id', type=int)
    
    if selected_company_id:
        settings = ProductionSettings.query.filter_by(company_id=selected_company_id).first()
    else:
        settings = None
    
    return render_template('settings/production.html', 
                         companies=companies,
                         selected_company_id=selected_company_id,
                         settings=settings)

@settings_advanced_bp.route('/jobwork')
@login_required
def jobwork_settings():
    """Job work settings configuration"""
    if not current_user.is_admin():
        flash('Admin access required', 'error')
        return redirect(url_for('main.dashboard'))
    
    companies = Company.query.filter_by(is_active=True).all()
    selected_company_id = request.args.get('company_id', type=int)
    
    if selected_company_id:
        settings = JobWorkSettings.query.filter_by(company_id=selected_company_id).first()
    else:
        settings = None
    
    return render_template('settings/jobwork.html', 
                         companies=companies,
                         selected_company_id=selected_company_id,
                         settings=settings)

# API Routes for settings
@settings_advanced_bp.route('/api/setting/<category>/<key>')
@login_required
def get_setting_api(category, key):
    """API to get a setting value"""
    company_id = request.args.get('company_id', type=int)
    default = request.args.get('default')
    
    value = SystemSettings.get_setting(category, key, company_id, default)
    return jsonify({'value': value})

@settings_advanced_bp.route('/api/setting/<category>/<key>', methods=['POST'])
@login_required
def set_setting_api(category, key):
    """API to set a setting value"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    data = request.json
    value = data.get('value')
    data_type = data.get('data_type', 'string')
    company_id = data.get('company_id')
    description = data.get('description')
    
    try:
        SystemSettings.set_setting(
            category, key, value, data_type, 
            company_id, current_user.id, description
        )
        return jsonify({'success': True, 'message': 'Setting updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def _create_default_company_settings(company_id):
    """Create default settings for a new company"""
    try:
        # Create inventory settings
        inventory_settings = InventorySettings(company_id=company_id)
        db.session.add(inventory_settings)
        
        # Create accounting settings
        accounting_settings = AccountingSettings(company_id=company_id)
        db.session.add(accounting_settings)
        
        # Create production settings
        production_settings = ProductionSettings(company_id=company_id)
        db.session.add(production_settings)
        
        # Create job work settings
        jobwork_settings = JobWorkSettings(company_id=company_id)
        db.session.add(jobwork_settings)
        
        # Create system settings from defaults
        for category, settings in DEFAULT_SETTINGS.items():
            for key, (value, data_type, description) in settings.items():
                SystemSettings.set_setting(
                    category, key, value, data_type, 
                    company_id, None, description
                )
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e