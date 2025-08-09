"""
Unified Job Work + GRN Routes
Handles both in-house and outsourced job work through a single GRN interface with conditional logic.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from models import JobWork, Item, Production, User
from models.grn import GRN, GRNLineItem
from models.grn import GRNWorkflowStatus, VendorInvoice
from services.unified_jobwork_grn import UnifiedJobWorkGRNService
from app import db
from datetime import datetime, date
import json

unified_jobwork_grn_bp = Blueprint('unified_jobwork_grn', __name__)

@unified_jobwork_grn_bp.route('/job-work/<int:job_work_id>/create-grn')
@login_required
def create_grn_form(job_work_id):
    """Display form for creating GRN from job work completion"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    # Check if user can receive this job work
    if job_work.status not in ['sent', 'partial_received']:
        flash('This job work is not available for receiving materials.', 'warning')
        return redirect(url_for('jobwork.list_job_works'))
    
    # Get remaining quantity to receive
    remaining_quantity = job_work.quantity_sent - (job_work.quantity_received or 0)
    
    # Get item details
    item = Item.query.get(job_work.item_id)
    
    return render_template('unified_jobwork_grn/create_grn.html',
                         title=f'Receive Materials - {job_work.job_number}',
                         job_work=job_work,
                         item=item,
                         remaining_quantity=remaining_quantity)

@unified_jobwork_grn_bp.route('/job-work/<int:job_work_id>/create-grn', methods=['POST'])
@login_required
def create_grn(job_work_id):
    """Create GRN from job work completion"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    try:
        # Get form data
        quantity_received = float(request.form.get('quantity_received', 0))
        quantity_passed = float(request.form.get('quantity_passed', quantity_received))
        quantity_rejected = float(request.form.get('quantity_rejected', 0))
        quality_status = request.form.get('quality_status', 'passed')
        remarks = request.form.get('remarks', '')
        
        # Validate quantities
        if quantity_received <= 0:
            flash('Received quantity must be greater than zero.', 'error')
            return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))
        
        if quantity_passed + quantity_rejected != quantity_received:
            flash('Passed + Rejected quantities must equal received quantity.', 'error')
            return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))
        
        remaining_quantity = job_work.quantity_sent - (job_work.quantity_received or 0)
        if quantity_received > remaining_quantity:
            flash(f'Cannot receive more than remaining quantity: {remaining_quantity}', 'error')
            return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))
        
        # Prepare received data
        received_data = [{
            'item_id': job_work.item_id,
            'quantity_received': quantity_received,
            'quantity_passed': quantity_passed,
            'quantity_rejected': quantity_rejected,
            'quality_status': quality_status,
            'unit_of_measure': 'pcs',  # Default, can be enhanced
            'material_classification': 'finished_goods',
            'remarks': remarks
        }]
        
        # Create GRN through unified service
        result = UnifiedJobWorkGRNService.create_grn_from_job_work(
            job_work_id=job_work_id,
            received_data=received_data,
            received_by_user_id=current_user.id
        )
        
        if result['success']:
            flash(result['message'], 'success')
            return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=result['grn'].id))
        else:
            flash(result['message'], 'error')
            return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))
            
    except ValueError as e:
        flash('Invalid quantity values entered.', 'error')
        return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))
    except Exception as e:
        flash(f'Error creating GRN: {str(e)}', 'error')
        return redirect(url_for('unified_jobwork_grn.create_grn_form', job_work_id=job_work_id))

@unified_jobwork_grn_bp.route('/grn/<int:grn_id>')
@login_required
def view_grn(grn_id):
    """View GRN details with job work integration"""
    grn = GRN.query.get_or_404(grn_id)
    
    # Get workflow status
    workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn_id).first()
    
    # Get job work if this is a job work GRN
    job_work = None
    if grn.job_work_id:
        job_work = JobWork.query.get(grn.job_work_id)
    
    # Get related production records for in-house work
    related_productions = []
    if job_work and job_work.work_type == 'in_house' and job_work.bom_id:
        related_productions = Production.query.filter_by(bom_id=job_work.bom_id).all()
    
    # Get next actions based on work type and workflow status
    next_actions = []
    if job_work:
        if job_work.work_type == 'outsourced' and workflow_status:
            if workflow_status.grn_voucher_created and not workflow_status.invoice_received:
                next_actions.append({
                    'action': 'receive_invoice',
                    'description': 'Receive vendor invoice',
                    'url': url_for('unified_jobwork_grn.receive_invoice', grn_id=grn_id)
                })
            elif workflow_status.invoice_received and not workflow_status.payment_made:
                next_actions.append({
                    'action': 'make_payment',
                    'description': 'Make payment to vendor',
                    'url': url_for('unified_jobwork_grn.make_payment', grn_id=grn_id)
                })
    
    return render_template('unified_jobwork_grn/view_grn.html',
                         title=f'GRN - {grn.grn_number}',
                         grn=grn,
                         job_work=job_work,
                         workflow_status=workflow_status,
                         related_productions=related_productions,
                         next_actions=next_actions)

@unified_jobwork_grn_bp.route('/grn/<int:grn_id>/receive-invoice')
@login_required
def receive_invoice(grn_id):
    """Form to receive vendor invoice for outsourced job work"""
    grn = GRN.query.get_or_404(grn_id)
    
    # Verify this is for outsourced work
    if not grn.job_work_id:
        abort(404)
    
    job_work = JobWork.query.get(grn.job_work_id)
    if job_work.work_type != 'outsourced':
        flash('Invoice receipt is only for outsourced job work.', 'warning')
        return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=grn_id))
    
    workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn_id).first()
    if not workflow_status or not workflow_status.grn_voucher_created:
        flash('GRN voucher must be created before receiving invoice.', 'warning')
        return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=grn_id))
    
    if workflow_status.invoice_received:
        flash('Invoice has already been received for this GRN.', 'info')
        return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=grn_id))
    
    return render_template('unified_jobwork_grn/receive_invoice.html',
                         title=f'Receive Invoice - {grn.grn_number}',
                         grn=grn,
                         job_work=job_work)

@unified_jobwork_grn_bp.route('/grn/<int:grn_id>/make-payment')
@login_required
def make_payment(grn_id):
    """Placeholder for payment processing - to be implemented"""
    flash('Payment processing feature coming soon.', 'info')
    return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=grn_id))

@unified_jobwork_grn_bp.route('/grn/<int:grn_id>/receive-invoice', methods=['POST'])
@login_required
def process_invoice(grn_id):
    """Process vendor invoice receipt"""
    grn = GRN.query.get_or_404(grn_id)
    job_work = JobWork.query.get(grn.job_work_id)
    
    try:
        invoice_number = request.form.get('invoice_number', '').strip()
        invoice_date_str = request.form.get('invoice_date', '')
        base_amount = float(request.form.get('base_amount', 0))
        gst_amount = float(request.form.get('gst_amount', 0))
        total_amount = float(request.form.get('total_amount', 0))
        
        if not invoice_number:
            flash('Invoice number is required.', 'error')
            return redirect(url_for('unified_jobwork_grn.receive_invoice', grn_id=grn_id))
        
        if base_amount <= 0:
            flash('Invoice amount must be greater than zero.', 'error')
            return redirect(url_for('unified_jobwork_grn.receive_invoice', grn_id=grn_id))
        
        # Parse invoice date
        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
        
        # Create vendor invoice
        vendor_invoice = VendorInvoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            vendor_id=1,  # This should be linked to job work vendor
            base_amount=base_amount,
            gst_amount=gst_amount,
            total_amount=total_amount,
            outstanding_amount=total_amount,
            status='pending'
        )
        
        db.session.add(vendor_invoice)
        db.session.flush()
        
        # Update workflow status
        workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn_id).first()
        workflow_status.invoice_received = True
        workflow_status.invoice_received_date = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Invoice {invoice_number} received successfully.', 'success')
        return redirect(url_for('unified_jobwork_grn.view_grn', grn_id=grn_id))
        
    except ValueError:
        flash('Invalid amount values entered.', 'error')
        return redirect(url_for('unified_jobwork_grn.receive_invoice', grn_id=grn_id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing invoice: {str(e)}', 'error')
        return redirect(url_for('unified_jobwork_grn.receive_invoice', grn_id=grn_id))

@unified_jobwork_grn_bp.route('/job-work/<int:job_work_id>/status')
@login_required
def job_work_status(job_work_id):
    """Comprehensive status view for job work through GRN workflow"""
    result = UnifiedJobWorkGRNService.get_job_work_grn_status(job_work_id)
    
    if not result['success']:
        flash(result['message'], 'error')
        return redirect(url_for('jobwork.list_job_works'))
    
    status_info = result['status']
    
    return render_template('unified_jobwork_grn/job_work_status.html',
                         title=f'Status - {status_info["job_work"].job_number}',
                         status=status_info)

@unified_jobwork_grn_bp.route('/api/job-work/<int:job_work_id>/grn-options')
@login_required
def api_grn_options(job_work_id):
    """API endpoint to get GRN creation options for job work"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    remaining_quantity = job_work.quantity_sent - (job_work.quantity_received or 0)
    
    return jsonify({
        'success': True,
        'job_work_id': job_work_id,
        'job_number': job_work.job_number,
        'work_type': job_work.work_type,
        'process': job_work.process,
        'item_name': job_work.item.name,
        'quantity_sent': job_work.quantity_sent,
        'quantity_received': job_work.quantity_received or 0,
        'remaining_quantity': remaining_quantity,
        'can_receive': remaining_quantity > 0 and job_work.status in ['sent', 'partial_received'],
        'rate_per_unit': job_work.rate_per_unit
    })

@unified_jobwork_grn_bp.route('/dashboard')
@login_required
def unified_dashboard():
    """Unified dashboard showing both job work and GRN status"""
    
    # Get statistics
    stats = {
        'active_job_works': JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received'])).count(),
        'in_house_active': JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received']), JobWork.work_type == 'in_house').count(),
        'outsourced_active': JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received']), JobWork.work_type == 'outsourced').count(),
        'pending_grns': GRN.query.filter(GRN.status == 'received').count(),
        'pending_invoices': GRNWorkflowStatus.query.filter(GRNWorkflowStatus.grn_voucher_created == True, GRNWorkflowStatus.invoice_received == False).count(),
        'pending_payments': GRNWorkflowStatus.query.filter(GRNWorkflowStatus.invoice_received == True, GRNWorkflowStatus.payment_made == False).count()
    }
    
    # Get recent activities
    recent_grns = GRN.query.filter(GRN.job_work_id.isnot(None)).order_by(GRN.created_at.desc()).limit(10).all()
    
    # Get active job works needing attention
    active_job_works = JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received'])).order_by(JobWork.id.desc()).limit(20).all()
    
    # Get workflow status that needs action - simplified query
    pending_actions = db.session.query(GRNWorkflowStatus).filter(
        db.or_(
            db.and_(GRNWorkflowStatus.grn_voucher_created == True, GRNWorkflowStatus.invoice_received == False),
            db.and_(GRNWorkflowStatus.invoice_received == True, GRNWorkflowStatus.payment_made == False)
        )
    ).all()
    
    return render_template('unified_jobwork_grn/dashboard.html',
                         title='Unified Job Work + GRN Dashboard',
                         stats=stats,
                         recent_grns=recent_grns,
                         active_job_works=active_job_works,
                         pending_actions=pending_actions)