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
    """Create GRN for outsourced job card when work returns"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Verify this is an outsourced job card
    if not job_card.parent_job_card_id or job_card.status != 'outsourced':
        flash('GRN can only be created for outsourced job cards', 'error')
        return redirect(url_for('job_cards.view_job_card', id=job_card_id))
    
    # Check if GRN already exists
    if job_card.grn_id:
        flash('GRN already exists for this outsourced job card', 'warning')
        return redirect(url_for('grn_job_card.view_grn_for_job_card', job_card_id=job_card_id))
    
    form = GRNForm()
    
    # Pre-populate supplier choices (vendor who did the outsourced work)
    if job_card.assigned_vendor:
        form.supplier_id.choices = [(job_card.assigned_vendor.id, job_card.assigned_vendor.name)]
        form.supplier_id.default = job_card.assigned_vendor.id
    
    if form.validate_on_submit():
        try:
            # Generate GRN number
            latest_grn = GRN.query.order_by(GRN.id.desc()).first()
            next_number = 1 if not latest_grn else int(latest_grn.grn_number.split('-')[-1]) + 1
            grn_number = f"GRN-JC-{date.today().year}-{str(next_number).zfill(4)}"
            
            # Create GRN for job card outsourcing
            grn = GRN(
                grn_number=grn_number,
                job_work_id=None,  # This is for outsourced job card, not traditional job work
                purchase_order_id=None,
                received_date=form.received_date.data,
                received_by=current_user.id,
                inspection_required=True,
                status='received',
                delivery_note=form.delivery_note.data,
                transporter_name=form.transporter_name.data,
                vehicle_number=form.vehicle_number.data,
                remarks=f"Outsourced work return for Job Card: {job_card.job_card_number}"
            )
            db.session.add(grn)
            db.session.flush()  # Get GRN ID
            
            # Create GRN line item for the outsourced work
            grn_line_item = GRNLineItem(
                grn_id=grn.id,
                item_id=job_card.item_id,
                quantity_received=form.quantity_received.data,
                quantity_passed=form.quantity_received.data,  # Assume all passed initially
                quantity_rejected=0.0,
                unit_of_measure=job_card.item.unit_of_measure if job_card.item else 'PCS',
                inspection_status='passed',
                process_name=job_card.process_name,
                process_stage='completed',
                material_classification='semi_finished',  # Outsourced work is typically semi-finished
                batch_number=f"BATCH-JC-{job_card.job_card_number}",
                remarks=f"Received from {job_card.assigned_vendor.name if job_card.assigned_vendor else 'Vendor'}"
            )
            db.session.add(grn_line_item)
            
            # Create workflow status for GRN
            workflow_status = GRNWorkflowStatus(
                grn_id=grn.id,
                material_received=True,
                material_received_date=datetime.now()
            )
            db.session.add(workflow_status)
            
            # Link GRN to job card and update quantities
            job_card.grn_id = grn.id
            job_card.grn_received_quantity = form.quantity_received.data
            job_card.grn_received_date = form.received_date.data
            job_card.status = 'received'  # Update status to received
            
            db.session.commit()
            
            flash(f'GRN {grn_number} created successfully for outsourced job card {job_card.job_card_number}', 'success')
            return redirect(url_for('grn_job_card.view_grn_for_job_card', job_card_id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating GRN: {str(e)}', 'error')
            logging.error(f"GRN creation error: {str(e)}")
    
    return render_template('grn_job_card/create_grn.html', 
                         form=form, 
                         job_card=job_card,
                         suggested_quantity=job_card.outsource_quantity)

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

@grn_job_card_bp.route('/update-inspection/<int:job_card_id>', methods=['POST'])
@login_required
def update_inspection_status(job_card_id):
    """Update inspection status for outsourced job card GRN"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    if not job_card.grn_id:
        return jsonify({'success': False, 'message': 'No GRN found'}), 400
    
    try:
        grn = GRN.query.get(job_card.grn_id)
        quantity_passed = float(request.json.get('quantity_passed', 0))
        quantity_rejected = float(request.json.get('quantity_rejected', 0))
        inspection_status = request.json.get('inspection_status', 'completed')
        
        # Update GRN line item
        line_item = grn.line_items[0] if grn.line_items else None
        if line_item:
            line_item.quantity_passed = quantity_passed
            line_item.quantity_rejected = quantity_rejected
            line_item.inspection_status = inspection_status
            
            # Update GRN status
            grn.inspection_status = inspection_status
            grn.inspected_by = current_user.id
            grn.inspected_at = datetime.now()
            
            if inspection_status == 'completed':
                grn.status = 'completed'
            
            # Update job card received quantity (only passed quantity)
            job_card.grn_received_quantity = quantity_passed
            
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Inspection updated - {quantity_passed} passed, {quantity_rejected} rejected'
            })
        
        return jsonify({'success': False, 'message': 'GRN line item not found'}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@grn_job_card_bp.route('/dashboard')
@login_required
def outsourced_grn_dashboard():
    """Dashboard for outsourced job card GRNs"""
    # Get outsourced job cards with their GRN status
    outsourced_jobs = JobCard.query.filter(
        JobCard.parent_job_card_id.isnot(None),
        JobCard.status.in_(['outsourced', 'received'])
    ).order_by(JobCard.created_at.desc()).limit(20).all()
    
    # Statistics
    stats = {
        'total_outsourced': JobCard.query.filter(JobCard.parent_job_card_id.isnot(None)).count(),
        'pending_grn': JobCard.query.filter(
            JobCard.parent_job_card_id.isnot(None),
            JobCard.grn_id.is_(None),
            JobCard.status == 'outsourced'
        ).count(),
        'received': JobCard.query.filter(
            JobCard.parent_job_card_id.isnot(None),
            JobCard.grn_id.isnot(None)
        ).count(),
        'in_inspection': GRN.query.join(JobCard, GRN.id == JobCard.grn_id).filter(
            GRN.inspection_status == 'pending'
        ).count()
    }
    
    return render_template('grn_job_card/dashboard.html', 
                         outsourced_jobs=outsourced_jobs,
                         stats=stats)