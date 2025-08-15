from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Item, PurchaseOrder, SalesOrder, Employee, JobWork, Production
from models.dashboard import DashboardModule, UserDashboardPreference, get_user_dashboard_modules, init_user_default_preferences
from models.job_card import JobCard
from sqlalchemy import func
from app import db
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

# Add redirect routes for common URL mistakes
@main_bp.route('/items/add')
@login_required
def items_add_redirect():
    """Redirect from /items/add to correct inventory add route"""
    return redirect(url_for('inventory.add_item'))

@main_bp.route('/items')
@main_bp.route('/items/')
@login_required
def items_list_redirect():
    """Redirect from /items to correct inventory list route"""
    return redirect(url_for('inventory.list_items'))

@main_bp.route('/')
@login_required
def dashboard():
    # Initialize user preferences if they don't exist
    init_user_default_preferences(current_user.id)
    
    # Get user's customized dashboard modules
    user_modules = get_user_dashboard_modules(current_user.id)
    
    # Role-based data collection
    current_time = datetime.now()
    
    # Basic stats for all users
    stats = {
        'total_items': Item.query.count(),
        'low_stock_items': Item.query.filter(Item.current_stock <= Item.minimum_stock).count(),
        'open_purchase_orders': PurchaseOrder.query.filter_by(status='open').count(),
        'pending_sales_orders': SalesOrder.query.filter_by(status='pending').count(),
        'active_employees': Employee.query.filter_by(is_active=True).count(),
        'open_job_works': JobWork.query.filter_by(status='sent').count(),
        'planned_productions': Production.query.filter_by(status='planned').count()
    }
    
    # Role-specific data
    operator_job_cards = []
    active_jobs_count = 0
    pending_orders_count = Production.query.filter_by(status='planned').count()
    today_completion_rate = 0
    issues_count = 0
    notifications = []
    
    try:
        # Simplified job card data to avoid complex queries that might fail
        active_jobs_count = 0
        try:
            if hasattr(current_user, 'is_operator') and current_user.is_operator():
                # Get basic count for operators
                active_jobs_count = JobCard.query.filter(
                    JobCard.assigned_worker_id == current_user.id
                ).filter(
                    JobCard.status.in_(['planned', 'in_progress'])
                ).count()
            else:
                # For supervisors/managers/admins
                active_jobs_count = JobCard.query.filter(
                    JobCard.status.in_(['planned', 'in_progress'])
                ).count()
        except:
            active_jobs_count = 0
        
        # Calculate today's completion rate
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_completed = 0
        today_total = 0
        
        try:
            today_completed = JobCard.query.filter(
                JobCard.status == 'completed'
            ).count()
            
            today_total = JobCard.query.count()
            
            if today_total > 0:
                today_completion_rate = round((today_completed / today_total) * 100, 1)
        except:
            today_completion_rate = 0
        
        # Count issues (overdue jobs, low stock, etc.)
        try:
            low_stock_count = Item.query.filter(Item.current_stock <= Item.minimum_stock).count()
            issues_count = low_stock_count
        except:
            issues_count = 0
        
    except Exception as e:
        # Handle any database errors gracefully
        print(f"Dashboard data error: {e}")
        active_jobs_count = 0
        today_completion_rate = 0
        issues_count = 0
    
    # Recent activities
    recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).limit(5).all()
    recent_sos = SalesOrder.query.order_by(SalesOrder.created_at.desc()).limit(5).all()
    low_stock_items = Item.query.filter(Item.current_stock <= Item.minimum_stock).limit(10).all()
    
    # Validate URLs for each module to prevent build errors
    for user_module in user_modules:
        module = user_module['module']
        try:
            # Try to build the URL to check if endpoint exists
            module.valid_url = url_for(module.url_endpoint)
        except:
            # If endpoint doesn't exist, set as None for fallback
            module.valid_url = None
    
    # Use the simplified user-friendly template
    return render_template('dashboard/simple_user_dashboard.html', 
                         stats=stats, 
                         recent_pos=recent_pos, 
                         recent_sos=recent_sos,
                         low_stock_items=low_stock_items,
                         user_modules=user_modules,
                         current_time=current_time,
                         operator_job_cards=operator_job_cards,
                         active_jobs_count=active_jobs_count,
                         pending_orders_count=pending_orders_count,
                         today_completion_rate=today_completion_rate,
                         issues_count=issues_count,
                         notifications=notifications)

@main_bp.route('/my-job-cards')
@login_required
def my_job_cards():
    """Quick action: View operator's assigned job cards"""
    if not current_user.is_operator():
        flash('Access denied. This page is for operators only.', 'error')
        return redirect(url_for('main.dashboard'))
    
    job_cards = JobCard.query.filter_by(
        assigned_worker_id=current_user.id
    ).order_by(JobCard.target_completion_date.asc()).all()
    
    breadcrumb_items = [
        {'title': 'My Job Cards', 'icon': 'tasks'}
    ]
    
    return render_template('job_cards/my_job_cards.html', 
                         job_cards=job_cards, 
                         breadcrumb_items=breadcrumb_items)

@main_bp.route('/quick-update-progress')
@login_required
def quick_update_progress():
    """Quick action: Update job progress (simplified form)"""
    if not (current_user.is_operator() or current_user.is_supervisor()):
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get active job cards for this user or all if supervisor
    if current_user.is_operator():
        job_cards = JobCard.query.filter_by(
            assigned_worker_id=current_user.id,
            status='in_progress'
        ).all()
    else:
        job_cards = JobCard.query.filter_by(status='in_progress').limit(20).all()
    
    breadcrumb_items = [
        {'title': 'Update Progress', 'icon': 'chart-line'}
    ]
    
    return render_template('job_cards/quick_update_progress.html', 
                         job_cards=job_cards, 
                         breadcrumb_items=breadcrumb_items)

@main_bp.route('/report-issue')
@login_required
def report_issue():
    """Quick action: Report an issue (simplified form)"""
    breadcrumb_items = [
        {'title': 'Report Issue', 'icon': 'exclamation-triangle'}
    ]
    
    return render_template('issues/report_issue.html', 
                         breadcrumb_items=breadcrumb_items)

@main_bp.route('/update-bom-prices')
@login_required
def update_bom_prices():
    """Update all item prices based on BOM calculations"""
    if not (current_user.is_admin() or current_user.is_manager()):
        flash('Access denied. Only administrators and managers can update BOM prices.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models import BOM
        updated_items = BOM.update_all_item_prices_from_bom()
        
        if updated_items:
            flash(f'Successfully updated prices for {len(updated_items)} items based on BOM calculations.', 'success')
            
            # Log the updates for transparency
            for item in updated_items:
                print(f"Updated {item['item_code']} ({item['item_name']}): ₹{item['old_price']} → ₹{item['new_price']}")
        else:
            flash('All item prices are already up to date with their BOM calculations.', 'info')
            
    except Exception as e:
        flash(f'Error updating BOM prices: {str(e)}', 'error')
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/customize_dashboard')
@login_required
def customize_dashboard():
    """Dashboard customization page"""
    # Get all available modules
    all_modules = DashboardModule.query.filter_by(is_active=True).all()
    
    # Get user's current preferences
    user_preferences = {}
    preferences = UserDashboardPreference.query.filter_by(user_id=current_user.id).all()
    for pref in preferences:
        user_preferences[pref.module_id] = {
            'is_visible': pref.is_visible,
            'position': pref.position,
            'size': pref.size
        }
    
    return render_template('dashboard_customize.html', 
                         all_modules=all_modules,
                         user_preferences=user_preferences)

@main_bp.route('/save_dashboard_preferences', methods=['POST'])
@login_required
def save_dashboard_preferences():
    """Save user's dashboard preferences"""
    try:
        preferences_data = request.get_json()
        
        # Clear existing preferences
        UserDashboardPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Save new preferences
        for pref_data in preferences_data:
            preference = UserDashboardPreference(
                user_id=current_user.id,
                module_id=pref_data['module_id'],
                is_visible=pref_data['is_visible'],
                position=pref_data['position'],
                size=pref_data.get('size', 'medium')
            )
            db.session.add(preference)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Dashboard preferences saved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error saving preferences: {str(e)}'
        }), 400

@main_bp.route('/reset_dashboard_preferences', methods=['POST'])
@login_required
def reset_dashboard_preferences():
    """Reset dashboard to default layout"""
    try:
        # Clear existing preferences
        UserDashboardPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Reinitialize default preferences
        init_user_default_preferences(current_user.id)
        
        flash('Dashboard reset to default layout successfully!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting dashboard: {str(e)}', 'danger')
        return redirect(url_for('main.customize_dashboard'))
