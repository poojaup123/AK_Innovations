from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db
from models import Item, Supplier
from models.grn import GRN, GRNLineItem, GRNWorkflowStatus
from models.job_card import JobCard
from forms_grn import GRNForm
import logging

grn_job_card_bp = Blueprint('grn_job_card', __name__, url_prefix='/grn-job-card')

@grn_job_card_bp.route('/create/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def create_grn_for_job_card(job_card_id):
    """Create a new GRN for an outsourced job card"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    if job_card.grn_id:
        flash('This job card already has a GRN created.', 'warning')
        return redirect(url_for('grn_job_card.view_grn_for_job_card', job_card_id=job_card_id))
    
    # Check if this is an outsourced job card
    if not hasattr(job_card, 'job_type') or job_card.job_type != 'outsourced':
        # Alternative check: see if it has outsource_quantity
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
            # Create GRN
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
            grn.status = 'received'
            grn.remarks = form.remarks.data
            
            db.session.add(grn)
            db.session.flush()  # Get the GRN ID
            
            # Link job card to GRN
            job_card.grn_id = grn.id
            job_card.status = 'completed'  # Mark job card as completed
            
            # Create GRN line item for the component
            if job_card.item:
                line_item = GRNLineItem()
                line_item.grn_id = grn.id
                line_item.item_id = job_card.item_id
                line_item.quantity_received = job_card.planned_quantity
                line_item.quantity_passed = job_card.planned_quantity
                line_item.quantity_rejected = 0
                line_item.unit_of_measure = job_card.item.unit_of_measure if job_card.item else 'PCS'
                line_item.inspection_status = 'passed'
                line_item.remarks = f"Received from outsourced process: {job_card.process_name}"
                
                db.session.add(line_item)
            
            db.session.commit()
            
            flash(f'GRN {grn.grn_number} created successfully for job card {job_card.job_card_number}!', 'success')
            return redirect(url_for('grn_job_card.view_grn_for_job_card', job_card_id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating GRN: {str(e)}', 'error')
    
    return render_template('grn_job_card/create_grn.html',
                         title='Create GRN for Outsourced Job Card',
                         form=form,
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