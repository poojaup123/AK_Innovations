from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db
from models import Item, Supplier
from models.grn import GRN, GRNLineItem, GRNWorkflowStatus
from models.job_card import JobCard
from forms_grn import GRNForm, GRNLineItemForm
import logging

grn_job_card_bp = Blueprint('grn_job_card', __name__, url_prefix='/grn-job-card')

# =================== STEP 1: CREATE GRN HEADER ===================
@grn_job_card_bp.route('/create/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def create_grn_for_job_card(job_card_id):
    """Step 1: Create GRN header for outsourced job card (same as PO workflow)"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    if job_card.grn_id:
        flash('This job card already has a GRN created.', 'warning')
        return redirect(url_for('grn_job_card.add_line_items', grn_id=job_card.grn_id))
    
    # Check if this is an outsourced job card
    if not hasattr(job_card, 'job_type') or job_card.job_type != 'outsourced':
        if not hasattr(job_card, 'outsource_quantity') or not job_card.outsource_quantity:
            flash('Only outsourced job cards can have GRNs created.', 'error')
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
    
    form = GRNForm()
    
    # Pre-populate form with job card data
    if not form.grn_number.data:
        latest_grn = GRN.query.order_by(GRN.id.desc()).first()
        next_number = 1 if not latest_grn else int(latest_grn.grn_number.split('-')[-1]) + 1
        form.grn_number.data = f"GRN-JC-{date.today().year}-{str(next_number).zfill(4)}"
    
    if request.method == 'GET':
        form.received_date.data = date.today()
        form.delivery_note.data = f"Receipt for outsourced job card {job_card.job_card_number}"
        form.remarks.data = f"Material received from {job_card.assigned_vendor.name if job_card.assigned_vendor else 'vendor'} for {job_card.process_name}"
    
    if form.validate_on_submit():
        try:
            # Create GRN header only
            grn = GRN()
            grn.grn_number = form.grn_number.data
            grn.job_work_id = None
            grn.purchase_order_id = None
            grn.received_date = form.received_date.data
            grn.received_by = current_user.id
            grn.delivery_note = form.delivery_note.data
            grn.transporter_name = form.transporter_name.data
            grn.vehicle_number = form.vehicle_number.data
            grn.inspection_required = form.inspection_required.data
            grn.status = 'draft'  # Start as draft, same as PO workflow
            grn.remarks = form.remarks.data
            
            db.session.add(grn)
            db.session.flush()
            
            # Link job card to GRN
            job_card.grn_id = grn.id
            
            # Create workflow status tracking
            workflow_status = GRNWorkflowStatus()
            workflow_status.grn_id = grn.id
            workflow_status.material_received = True
            workflow_status.material_received_date = datetime.now()
            workflow_status.material_received_by = current_user.id
            
            db.session.add(workflow_status)
            db.session.commit()
            
            flash(f'GRN {grn.grn_number} created successfully! Now add line items.', 'success')
            return redirect(url_for('grn_job_card.add_line_items', grn_id=grn.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating GRN: {str(e)}', 'error')
    
    return render_template('grn_job_card/create_grn.html',
                         title='Step 1: Create GRN for Outsourced Job Card',
                         form=form,
                         job_card=job_card)

# =================== STEP 2: ADD LINE ITEMS ===================
@grn_job_card_bp.route('/add-line-items/<int:grn_id>', methods=['GET', 'POST'])
@login_required
def add_line_items(grn_id):
    """Step 2: Add line items to GRN (same as PO workflow)"""
    grn = GRN.query.get_or_404(grn_id)
    
    # Find the associated job card
    job_card = JobCard.query.filter_by(grn_id=grn_id).first()
    if not job_card:
        flash('Associated job card not found for this GRN.', 'error')
        return redirect(url_for('grn.dashboard'))
    
    form = GRNLineItemForm()
    
    # Pre-populate with job card item
    if request.method == 'GET' and job_card.item:
        form.item_id.data = job_card.item_id
        form.quantity_received.data = job_card.planned_quantity
        form.unit_of_measure.data = job_card.item.unit_of_measure
        form.remarks.data = f"Outsourced {job_card.process_name} - Job Card: {job_card.job_card_number}"
    
    if form.validate_on_submit():
        try:
            # Create line item
            line_item = GRNLineItem()
            line_item.grn_id = grn.id
            line_item.item_id = form.item_id.data
            line_item.quantity_received = form.quantity_received.data
            line_item.quantity_passed = 0  # Will be set in inspection step
            line_item.quantity_rejected = 0
            line_item.unit_of_measure = form.unit_of_measure.data
            line_item.inspection_status = 'pending'  # Requires inspection
            line_item.remarks = form.remarks.data
            
            db.session.add(line_item)
            
            # Update GRN status to received
            grn.status = 'received'
            
            db.session.commit()
            
            flash('Line item added successfully! Proceed to inspection.', 'success')
            return redirect(url_for('grn_job_card.inspection', grn_id=grn.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding line item: {str(e)}', 'error')
    
    return render_template('grn_job_card/add_line_items.html',
                         title='Step 2: Add Line Items to GRN',
                         form=form,
                         grn=grn,
                         job_card=job_card)

# =================== STEP 3: INSPECTION & FINALIZATION ===================
@grn_job_card_bp.route('/inspection/<int:grn_id>', methods=['GET', 'POST'])
@login_required
def inspection(grn_id):
    """Step 3: Inspection and finalization (same as PO workflow)"""
    grn = GRN.query.get_or_404(grn_id)
    job_card = JobCard.query.filter_by(grn_id=grn_id).first()
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            line_item_updates = data.get('line_items', [])
            
            for update in line_item_updates:
                line_item = GRNLineItem.query.get(update['id'])
                if line_item and line_item.grn_id == grn.id:
                    line_item.quantity_passed = float(update.get('quantity_passed', 0))
                    line_item.quantity_rejected = float(update.get('quantity_rejected', 0))
                    line_item.inspection_status = update.get('inspection_status', 'passed')
                    line_item.inspection_notes = update.get('inspection_notes', '')
            
            # Update GRN workflow status
            workflow = GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first()
            if workflow:
                workflow.inspection_completed = True
                workflow.inspection_completed_date = datetime.now()
                workflow.inspection_completed_by = current_user.id
            
            # Finalize GRN
            grn.status = 'completed'
            
            # Update job card status
            if job_card:
                total_passed = sum(item.quantity_passed for item in grn.line_items)
                job_card.grn_received_quantity = total_passed
                job_card.grn_received_date = date.today()
                job_card.status = 'completed'
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Inspection completed and GRN finalized!'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    return render_template('grn_job_card/inspection.html',
                         title='Step 3: Inspection & Finalization',
                         grn=grn,
                         job_card=job_card)

@grn_job_card_bp.route('/view/<int:job_card_id>')
@login_required
def view_grn_for_job_card(job_card_id):
    """View GRN details for outsourced job card"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    if not job_card.grn_id:
        flash('No GRN found for this job card', 'error')
        return redirect(url_for('job_cards.view_job_card', id=job_card_id))
    
    grn = GRN.query.get_or_404(job_card.grn_id)
    
    return render_template('grn_job_card/view_grn.html', 
                         grn=grn, 
                         job_card=job_card)