from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from datetime import datetime
from models import db, PurchaseOrder, Production, SalesOrder, User
from utils import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/approvals')
@login_required
@admin_required
def approvals_dashboard():
    """Admin dashboard showing all pending approval requests"""
    
    # Get pending purchase orders - either 'draft' status or no approved_by but has prepared_by
    pending_pos = PurchaseOrder.query.filter(
        or_(
            PurchaseOrder.status == 'draft',
            and_(
                PurchaseOrder.status.in_(['sent', 'partial']),
                or_(
                    PurchaseOrder.approved_by.is_(None),
                    PurchaseOrder.approved_by == ''
                ),
                PurchaseOrder.prepared_by.isnot(None),
                PurchaseOrder.prepared_by != ''
            )
        )
    ).order_by(PurchaseOrder.created_at.desc()).all()
    
    # Get pending production orders - status 'planned' indicates pending approval
    pending_productions = Production.query.filter(
        Production.status == 'planned'
    ).order_by(Production.created_at.desc()).all()
    
    # Get pending sales orders with draft status or needing approval
    pending_sales = SalesOrder.query.filter(
        or_(
            SalesOrder.status == 'draft',
            and_(
                SalesOrder.status == 'pending',
                or_(
                    SalesOrder.approved_by.is_(None),
                    SalesOrder.approved_by == ''
                )
            )
        )
    ).order_by(SalesOrder.created_at.desc()).all()
    
    # Get pending job work orders that need approval
    try:
        from models import JobWork
        pending_jobwork = JobWork.query.filter(
            or_(
                JobWork.status == 'pending',
                JobWork.status == 'draft'
            )
        ).order_by(JobWork.created_at.desc()).all()
    except:
        pending_jobwork = []
    
    # Get pending expenses
    try:
        from models import FactoryExpense
        pending_expenses = FactoryExpense.query.filter_by(status='pending').order_by(FactoryExpense.created_at.desc()).all()
    except:
        pending_expenses = []
    
    # Get recent approval activity (last 10 approvals)
    recent_approvals = []
    
    # Get recently approved POs
    recently_approved_pos = PurchaseOrder.query.filter(
        and_(
            PurchaseOrder.approved_by.isnot(None),
            PurchaseOrder.approved_by != ''
        )
    ).order_by(PurchaseOrder.created_at.desc()).limit(5).all()
    
    for po in recently_approved_pos:
        recent_approvals.append({
            'order_type': 'Purchase Order',
            'order_number': po.po_number,
            'action': 'approved',
            'approved_by': po.approved_by,
            'timestamp': po.created_at  # You might want to add approved_at field
        })
    
    return render_template('admin/approvals_dashboard.html',
                         pending_pos=pending_pos,
                         pending_productions=pending_productions,
                         pending_sales=pending_sales,
                         pending_jobwork=pending_jobwork,
                         pending_expenses=pending_expenses,
                         recent_approvals=recent_approvals[:10])

@admin_bp.route('/approval/approve', methods=['POST'])
@login_required
@admin_required
def approve_order():
    """Approve a specific order"""
    data = request.get_json()
    order_type = data.get('order_type')
    order_id = data.get('order_id')
    comments = data.get('comments', '')
    
    try:
        if order_type == 'purchase':
            order = PurchaseOrder.query.get_or_404(order_id)
            order.approved_by = current_user.username
            order.status = 'approved'
            flash(f'Purchase Order {order.po_number} has been approved.', 'success')
            
        elif order_type == 'production':
            order = Production.query.get_or_404(order_id)
            order.status = 'approved'
            # You might want to add approved_by field to Production model
            flash(f'Production Order {order.production_number} has been approved.', 'success')
            
        elif order_type == 'sales':
            order = SalesOrder.query.get_or_404(order_id)
            order.approved_by = current_user.username
            order.status = 'approved'
            flash(f'Sales Order {order.so_number} has been approved.', 'success')
            
        elif order_type == 'jobwork':
            from models import JobWork
            order = JobWork.query.get_or_404(order_id)
            order.status = 'approved'
            # Add approved_by field if needed
            flash(f'Job Work {order.jobwork_number} has been approved.', 'success')
            
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order approved successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/approval/reject', methods=['POST'])
@login_required
@admin_required
def reject_order():
    """Reject a specific order"""
    data = request.get_json()
    order_type = data.get('order_type')
    order_id = data.get('order_id')
    comments = data.get('comments', '')
    
    try:
        if order_type == 'purchase':
            order = PurchaseOrder.query.get_or_404(order_id)
            order.status = 'rejected'
            # You might want to add rejection_reason field
            flash(f'Purchase Order {order.po_number} has been rejected.', 'warning')
            
        elif order_type == 'production':
            order = Production.query.get_or_404(order_id)
            order.status = 'rejected'
            flash(f'Production Order {order.production_number} has been rejected.', 'warning')
            
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order rejected successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/pending-summary')
@login_required
@admin_required
def pending_summary():
    """API endpoint to get summary of pending approvals for dashboard widgets"""
    
    pending_pos_count = PurchaseOrder.query.filter(
        and_(
            PurchaseOrder.prepared_by.isnot(None),
            PurchaseOrder.prepared_by != '',
            or_(
                PurchaseOrder.approved_by.is_(None),
                PurchaseOrder.approved_by == ''
            )
        )
    ).count()
    
    pending_productions_count = Production.query.filter(
        Production.status == 'planned'
    ).count()
    
    return jsonify({
        'pending_purchase_orders': pending_pos_count,
        'pending_productions': pending_productions_count,
        'total_pending': pending_pos_count + pending_productions_count
    })