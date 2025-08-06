"""
Routes for Batch-wise Job Work Management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import and_, or_
from app import db
from models import Item, JobWork
from models.batch import InventoryBatch, BatchMovement, JobWorkBatch, BatchTraceability
from forms_batch import (BatchJobWorkIssueForm, BatchJobWorkReturnForm, BatchInventoryForm, 
                        BatchTransferForm, BatchSearchForm)

batch_bp = Blueprint('batch', __name__, url_prefix='/batch')

@batch_bp.route('/')
@login_required
def dashboard():
    """Batch management dashboard with overview"""
    
    # Get batch statistics
    total_batches = InventoryBatch.query.count()
    active_batches = InventoryBatch.query.filter(
        or_(InventoryBatch.qty_raw > 0, InventoryBatch.qty_wip > 0, 
            InventoryBatch.qty_finished > 0, InventoryBatch.qty_scrap > 0)
    ).count()
    
    # Expired batches
    expired_batches = InventoryBatch.query.filter(
        and_(InventoryBatch.expiry_date < date.today(), 
             InventoryBatch.expiry_date.isnot(None),
             or_(InventoryBatch.qty_raw > 0, InventoryBatch.qty_finished > 0))
    ).count()
    
    # Expiring soon (within 30 days)
    from datetime import timedelta
    expiring_soon = InventoryBatch.query.filter(
        and_(InventoryBatch.expiry_date <= date.today() + timedelta(days=30),
             InventoryBatch.expiry_date > date.today(),
             or_(InventoryBatch.qty_raw > 0, InventoryBatch.qty_finished > 0))
    ).count()
    
    # Recent batch movements
    recent_movements = BatchMovement.query.order_by(BatchMovement.timestamp.desc()).limit(10).all()
    
    # Outstanding job work batches
    outstanding_jobwork = JobWorkBatch.query.filter_by(status='issued').count()
    
    stats = {
        'total_batches': total_batches,
        'active_batches': active_batches,
        'expired_batches': expired_batches,
        'expiring_soon': expiring_soon,
        'outstanding_jobwork': outstanding_jobwork
    }
    
    return render_template('batch/dashboard.html', stats=stats, recent_movements=recent_movements)

@batch_bp.route('/inventory')
@login_required 
def inventory():
    """View all inventory batches with filtering"""
    
    form = BatchSearchForm()
    
    # Build query based on filters
    query = InventoryBatch.query.join(Item)
    
    if form.validate_on_submit():
        if form.item_id.data and form.item_id.data != 0:
            query = query.filter(InventoryBatch.item_id == form.item_id.data)
        
        if form.batch_code.data:
            query = query.filter(InventoryBatch.batch_code.ilike(f'%{form.batch_code.data}%'))
        
        if form.location.data:
            query = query.filter(InventoryBatch.location.ilike(f'%{form.location.data}%'))
        
        if form.mfg_date_from.data:
            query = query.filter(InventoryBatch.mfg_date >= form.mfg_date_from.data)
        
        if form.mfg_date_to.data:
            query = query.filter(InventoryBatch.mfg_date <= form.mfg_date_to.data)
        
        # State filters
        state_filters = []
        if form.show_raw.data == 'yes':
            state_filters.append(InventoryBatch.qty_raw > 0)
        elif form.show_raw.data == 'no':
            state_filters.append(InventoryBatch.qty_raw == 0)
            
        if form.show_wip.data == 'yes':
            state_filters.append(InventoryBatch.qty_wip > 0)
        elif form.show_wip.data == 'no':
            state_filters.append(InventoryBatch.qty_wip == 0)
            
        if form.show_finished.data == 'yes':
            state_filters.append(InventoryBatch.qty_finished > 0)
        elif form.show_finished.data == 'no':
            state_filters.append(InventoryBatch.qty_finished == 0)
            
        if form.show_scrap.data == 'yes':
            state_filters.append(InventoryBatch.qty_scrap > 0)
        elif form.show_scrap.data == 'no':
            state_filters.append(InventoryBatch.qty_scrap == 0)
        
        if state_filters:
            query = query.filter(or_(*state_filters))
        
        # Expiry status filter
        if form.expiry_status.data == 'expired':
            query = query.filter(and_(InventoryBatch.expiry_date < date.today(),
                                    InventoryBatch.expiry_date.isnot(None)))
        elif form.expiry_status.data == 'expiring_soon':
            from datetime import timedelta
            query = query.filter(and_(InventoryBatch.expiry_date <= date.today() + timedelta(days=30),
                                    InventoryBatch.expiry_date > date.today()))
        elif form.expiry_status.data == 'valid':
            query = query.filter(or_(InventoryBatch.expiry_date > date.today() + timedelta(days=30),
                                   InventoryBatch.expiry_date.is_(None)))
    
    # Order by creation date descending
    batches = query.order_by(InventoryBatch.created_at.desc()).all()
    
    return render_template('batch/inventory.html', batches=batches, form=form)

@batch_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_batch():
    """Create a new inventory batch"""
    
    form = BatchInventoryForm()
    
    if form.validate_on_submit():
        try:
            # Create new batch
            batch = InventoryBatch(
                item_id=form.item_id.data,
                batch_code=form.batch_code.data,
                uom=form.uom.data,
                mfg_date=form.mfg_date.data,
                expiry_date=form.expiry_date.data,
                supplier_batch_no=form.supplier_batch_no.data,
                purchase_rate=form.purchase_rate.data or 0.0,
                location=form.location.data or 'Default',
                source_type=form.source_type.data,
                grn_id=form.grn_id.data if form.grn_id.data != 0 else None
            )
            
            # Set initial quantity in the specified state
            if form.initial_state.data == 'raw':
                batch.qty_raw = form.quantity.data
            elif form.initial_state.data == 'finished':
                batch.qty_finished = form.quantity.data
            
            db.session.add(batch)
            db.session.flush()  # Get the batch ID
            
            # Create initial movement record
            movement = BatchMovement(
                batch_id=batch.id,
                item_id=batch.item_id,
                quantity=form.quantity.data,
                from_state=None,  # New batch
                to_state=form.initial_state.data,
                movement_type='receipt',
                ref_type=form.source_type.data,
                ref_id=form.grn_id.data if form.grn_id.data != 0 else None,
                notes=form.notes.data,
                user_id=current_user.id
            )
            db.session.add(movement)
            
            db.session.commit()
            flash(f'Batch {batch.batch_code} created successfully!', 'success')
            return redirect(url_for('batch.inventory'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating batch: {str(e)}', 'error')
    
    return render_template('batch/create.html', form=form)

@batch_bp.route('/jobwork/issue', methods=['GET', 'POST'])
@login_required
def issue_jobwork():
    """Issue materials to job work with batch tracking"""
    
    form = BatchJobWorkIssueForm()
    
    if form.validate_on_submit():
        try:
            # Get the selected batch
            batch = InventoryBatch.query.get(form.input_batch_id.data)
            if not batch:
                flash('Selected batch not found', 'error')
                return redirect(url_for('batch.issue_jobwork'))
            
            # Check available quantity in raw state
            if batch.qty_raw < form.quantity_issued.data:
                flash(f'Insufficient raw material in batch {batch.batch_code}. Available: {batch.qty_raw}', 'error')
                return redirect(url_for('batch.issue_jobwork'))
            
            # Create job work batch record
            jobwork_batch = JobWorkBatch(
                job_work_id=form.job_work_id.data,
                input_batch_id=form.input_batch_id.data,
                input_item_id=form.input_item_id.data,
                quantity_issued=form.quantity_issued.data,
                issue_date=form.issue_date.data,
                process_name=form.process_name.data,
                vendor_name=form.vendor_name.data,
                rate_per_unit=form.rate_per_unit.data or 0.0,
                status='issued',
                notes=form.notes.data
            )
            db.session.add(jobwork_batch)
            
            # Move quantity from raw to WIP in the batch
            success = batch.move_quantity(
                quantity=form.quantity_issued.data,
                from_state='raw',
                to_state='wip',
                ref_type='jobwork',
                ref_id=form.job_work_id.data,
                notes=f'Issued for job work: {form.process_name.data}'
            )
            
            if not success:
                flash('Failed to move batch quantity to WIP', 'error')
                return redirect(url_for('batch.issue_jobwork'))
            
            db.session.commit()
            flash(f'Material issued successfully! Batch {batch.batch_code}: {form.quantity_issued.data} units sent for {form.process_name.data}', 'success')
            return redirect(url_for('batch.jobwork_tracking'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error issuing material: {str(e)}', 'error')
    
    return render_template('batch/jobwork_issue.html', form=form)

@batch_bp.route('/jobwork/return', methods=['GET', 'POST'])
@login_required
def return_jobwork():
    """Process job work returns with batch tracking"""
    
    form = BatchJobWorkReturnForm()
    
    if form.validate_on_submit():
        try:
            # Get the job work batch record
            jobwork_batch = JobWorkBatch.query.filter_by(
                job_work_id=form.job_work_id.data,
                status='issued'
            ).first()
            
            if not jobwork_batch:
                flash('No issued job work batch found for this job work', 'error')
                return redirect(url_for('batch.return_jobwork'))
            
            # Create output batch for finished products
            output_batch = InventoryBatch(
                item_id=form.output_item_id.data,
                batch_code=form.output_batch_code.data,
                qty_finished=form.quantity_passed.data,
                qty_scrap=form.quantity_rejected.data,
                uom=jobwork_batch.input_batch.uom,
                location=form.output_location.data or 'Default',
                mfg_date=form.output_mfg_date.data,
                expiry_date=form.output_expiry_date.data,
                source_type='production',
                source_ref_id=jobwork_batch.job_work_id
            )
            db.session.add(output_batch)
            db.session.flush()  # Get the output batch ID
            
            # Update job work batch record
            jobwork_batch.output_batch_id = output_batch.id
            jobwork_batch.output_item_id = form.output_item_id.data
            jobwork_batch.quantity_produced = form.quantity_produced.data
            jobwork_batch.quantity_scrap = form.quantity_scrap.data
            jobwork_batch.quantity_returned_unused = form.quantity_returned_unused.data
            jobwork_batch.return_date = form.return_date.data
            jobwork_batch.status = 'returned'
            jobwork_batch.notes = form.return_notes.data
            
            # Move WIP quantity from input batch
            input_batch = jobwork_batch.input_batch
            if input_batch:
                # Move WIP back to different states based on return
                if form.quantity_returned_unused.data > 0:
                    # Return unused material to raw state
                    input_batch.move_quantity(
                        quantity=form.quantity_returned_unused.data,
                        from_state='wip',
                        to_state='raw',
                        ref_type='jobwork_return',
                        ref_id=jobwork_batch.id,
                        notes='Unused material returned from job work'
                    )
                
                # Remove processed quantity from WIP (it's now converted to output)
                processed_qty = jobwork_batch.quantity_issued - (form.quantity_returned_unused.data or 0)
                if processed_qty > 0:
                    # Create movement record for processed material (WIP -> consumed)
                    movement = BatchMovement(
                        batch_id=input_batch.id,
                        item_id=input_batch.item_id,
                        quantity=processed_qty,
                        from_state='wip',
                        to_state=None,  # Consumed/converted
                        movement_type='consumption',
                        ref_type='jobwork_return',
                        ref_id=jobwork_batch.id,
                        notes=f'Consumed in job work process: {jobwork_batch.process_name}',
                        user_id=current_user.id
                    )
                    db.session.add(movement)
                    
                    # Update input batch WIP quantity
                    input_batch.qty_wip = (input_batch.qty_wip or 0) - processed_qty
            
            # Create traceability record
            if form.quantity_passed.data > 0:
                traceability = BatchTraceability(
                    source_batch_id=jobwork_batch.input_batch_id,
                    source_item_id=jobwork_batch.input_item_id,
                    dest_batch_id=output_batch.id,
                    dest_item_id=form.output_item_id.data,
                    transformation_type='jobwork',
                    transformation_ref_id=jobwork_batch.id,
                    quantity_consumed=jobwork_batch.quantity_issued - (form.quantity_returned_unused.data or 0),
                    quantity_produced=form.quantity_passed.data,
                    process_date=form.return_date.data
                )
                db.session.add(traceability)
            
            # Create movement records for output batch
            if form.quantity_passed.data > 0:
                movement = BatchMovement(
                    batch_id=output_batch.id,
                    item_id=form.output_item_id.data,
                    quantity=form.quantity_passed.data,
                    from_state=None,  # New production
                    to_state='finished',
                    movement_type='production',
                    ref_type='jobwork_return',
                    ref_id=jobwork_batch.id,
                    notes=f'Produced from job work: {jobwork_batch.process_name}',
                    user_id=current_user.id
                )
                db.session.add(movement)
            
            if form.quantity_rejected.data > 0:
                movement = BatchMovement(
                    batch_id=output_batch.id,
                    item_id=form.output_item_id.data,
                    quantity=form.quantity_rejected.data,
                    from_state=None,
                    to_state='scrap',
                    movement_type='production',
                    ref_type='jobwork_return',
                    ref_id=jobwork_batch.id,
                    notes=f'Rejected in job work: {jobwork_batch.process_name}. QC Notes: {form.qc_notes.data}',
                    user_id=current_user.id
                )
                db.session.add(movement)
            
            db.session.commit()
            flash(f'Job work return processed successfully! Output batch {output_batch.batch_code} created with {form.quantity_passed.data} units.', 'success')
            return redirect(url_for('batch.jobwork_tracking'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing job work return: {str(e)}', 'error')
    
    return render_template('batch/jobwork_return.html', form=form)

@batch_bp.route('/jobwork/tracking')
@login_required
def jobwork_tracking():
    """View all job work batch records"""
    
    # Get all job work batches with related data
    jobwork_batches = JobWorkBatch.query.order_by(JobWorkBatch.created_at.desc()).all()
    
    return render_template('batch/jobwork_tracking.html', jobwork_batches=jobwork_batches)

@batch_bp.route('/api/batches-by-item/<int:item_id>')
@login_required
def get_batches_by_item(item_id):
    """API endpoint to get available batches for an item"""
    
    batches = InventoryBatch.query.filter_by(item_id=item_id).filter(
        InventoryBatch.qty_raw > 0  # Only batches with raw material available
    ).all()
    
    batch_data = []
    for batch in batches:
        batch_data.append({
            'id': batch.id,
            'batch_code': batch.batch_code,
            'available_qty': batch.qty_raw,
            'location': batch.location,
            'mfg_date': batch.mfg_date.isoformat() if batch.mfg_date else None,
            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
            'is_expired': batch.is_expired,
            'age_days': batch.age_days
        })
    
    return jsonify({'batches': batch_data})

@batch_bp.route('/batch/<int:batch_id>')
@login_required
def batch_details(batch_id):
    """View detailed information about a specific batch"""
    
    batch = InventoryBatch.query.get_or_404(batch_id)
    
    # Get movement history
    movements = BatchMovement.query.filter_by(batch_id=batch_id).order_by(BatchMovement.timestamp.desc()).all()
    
    # Get job work history
    jobwork_issues = JobWorkBatch.query.filter_by(input_batch_id=batch_id).all()
    jobwork_returns = JobWorkBatch.query.filter_by(output_batch_id=batch_id).all()
    
    # Get traceability
    trace_from = BatchTraceability.query.filter_by(source_batch_id=batch_id).all()
    trace_to = BatchTraceability.query.filter_by(dest_batch_id=batch_id).all()
    
    return render_template('batch/details.html', 
                         batch=batch, 
                         movements=movements,
                         jobwork_issues=jobwork_issues,
                         jobwork_returns=jobwork_returns,
                         trace_from=trace_from,
                         trace_to=trace_to)

@batch_bp.route('/transfer/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def transfer_batch(batch_id):
    """Transfer quantities between states within a batch"""
    
    batch = InventoryBatch.query.get_or_404(batch_id)
    form = BatchTransferForm()
    form.batch_id.data = batch_id
    
    if form.validate_on_submit():
        try:
            success = batch.move_quantity(
                quantity=form.quantity.data,
                from_state=form.from_state.data,
                to_state=form.to_state.data,
                ref_type='manual_transfer',
                notes=form.notes.data
            )
            
            if success:
                db.session.commit()
                flash(f'Successfully transferred {form.quantity.data} units from {form.from_state.data} to {form.to_state.data}', 'success')
                return redirect(url_for('batch.batch_details', batch_id=batch_id))
            else:
                flash('Insufficient quantity in source state', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error transferring batch quantity: {str(e)}', 'error')
    
    return render_template('batch/transfer.html', batch=batch, form=form)

@batch_bp.route('/reports')
@login_required
def reports():
    """Batch-wise reports dashboard"""
    
    # Get report data
    from sqlalchemy import func
    
    # Batch ageing report
    batch_age_data = db.session.query(
        InventoryBatch.age_days,
        func.count(InventoryBatch.id).label('batch_count'),
        func.sum(InventoryBatch.qty_raw + InventoryBatch.qty_finished).label('total_qty')
    ).filter(
        or_(InventoryBatch.qty_raw > 0, InventoryBatch.qty_finished > 0)
    ).group_by(InventoryBatch.age_days).all()
    
    # Yield analysis by process
    yield_data = db.session.query(
        JobWorkBatch.process_name,
        func.avg(JobWorkBatch.quantity_produced / JobWorkBatch.quantity_issued * 100).label('avg_yield'),
        func.avg(JobWorkBatch.quantity_scrap / JobWorkBatch.quantity_issued * 100).label('avg_scrap'),
        func.count(JobWorkBatch.id).label('job_count')
    ).filter(
        JobWorkBatch.status == 'returned',
        JobWorkBatch.quantity_issued > 0
    ).group_by(JobWorkBatch.process_name).all()
    
    # Vendor performance
    vendor_performance = db.session.query(
        JobWorkBatch.vendor_name,
        func.avg(JobWorkBatch.quantity_produced / JobWorkBatch.quantity_issued * 100).label('avg_yield'),
        func.count(JobWorkBatch.id).label('job_count'),
        func.sum(JobWorkBatch.quantity_issued * JobWorkBatch.rate_per_unit).label('total_value')
    ).filter(
        JobWorkBatch.status == 'returned',
        JobWorkBatch.quantity_issued > 0
    ).group_by(JobWorkBatch.vendor_name).all()
    
    return render_template('batch/reports.html',
                         batch_age_data=batch_age_data,
                         yield_data=yield_data,
                         vendor_performance=vendor_performance)