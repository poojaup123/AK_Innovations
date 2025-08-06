from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from models import MaterialInspection, PurchaseOrder, JobWork, Item, User, PurchaseOrderItem, DailyJobWorkEntry
from models.uom import ItemUOMConversion, UnitOfMeasure
from forms import MaterialInspectionForm
from datetime import datetime
from utils import generate_next_number

material_inspection = Blueprint('material_inspection', __name__)

@material_inspection.route('/dashboard')
@login_required
def dashboard():
    """Material Inspection Dashboard with filtering"""
    # Get filter parameters
    search = request.args.get('search', '').strip()
    customer_filter = request.args.get('customer', '').strip()
    status_filter = request.args.get('status', '').strip()
    type_filter = request.args.get('type', '').strip()
    
    # Build base query for POs
    po_query = PurchaseOrder.query.filter(
        PurchaseOrder.status != 'cancelled',
        PurchaseOrder.inspection_required == True
    ).filter(
        # Include partial status POs (may need additional inspections) OR POs with incomplete inspection
        (PurchaseOrder.status == 'partial') |
        (PurchaseOrder.inspection_status.in_(['pending', 'in_progress', 'failed']))
    )
    
    # Apply filters to PO query
    if search:
        po_query = po_query.filter(PurchaseOrder.po_number.ilike(f'%{search}%'))
    if customer_filter:
        from models import Supplier
        po_query = po_query.join(Supplier).filter(
            Supplier.name.ilike(f'%{customer_filter}%')
        )
    if status_filter:
        po_query = po_query.filter(PurchaseOrder.status == status_filter)
    
    # Get filtered POs
    all_pos_with_items = po_query.all() if type_filter != 'job' else []
    pending_po_inspections = [po for po in all_pos_with_items if po.items]
    
    # Build base query for Job Works
    job_query = JobWork.query.filter(
        JobWork.work_type.in_(['outsourced', 'multi_process']),  # Include multi-process job works for inspection
        JobWork.inspection_required == True
    ).filter(
        # Include partial_received status jobs (may need additional inspections) OR jobs with incomplete inspection
        (JobWork.status == 'partial_received') |
        (JobWork.inspection_status.in_(['pending', 'in_progress', 'failed']))
    )
    
    # Apply filters to Job Work query
    if search:
        job_query = job_query.filter(JobWork.job_number.ilike(f'%{search}%'))
    if customer_filter:
        job_query = job_query.filter(JobWork.customer_name.ilike(f'%{customer_filter}%'))
    if status_filter:
        job_query = job_query.filter(JobWork.status == status_filter)
    
    # Get filtered Job Works
    pending_job_inspections = job_query.all() if type_filter != 'po' else []
    
    # Get in-house job works with daily entries that need inspection (if available)
    try:
        pending_daily_entries = DailyJobWorkEntry.query.join(JobWork).filter(
            JobWork.work_type == 'in_house',
            DailyJobWorkEntry.inspection_status == 'pending'
        ).order_by(DailyJobWorkEntry.work_date.desc()).limit(10).all()
    except:
        pending_daily_entries = []
    
    # Get recent inspections
    recent_inspections = MaterialInspection.query.order_by(
        MaterialInspection.inspection_date.desc()
    ).limit(10).all()
    
    # Calculate statistics
    total_pending = len(pending_po_inspections) + len(pending_job_inspections) + len(pending_daily_entries)
    
    # Get inspections this month
    this_month = datetime.now().replace(day=1)
    this_month_inspections = MaterialInspection.query.filter(
        MaterialInspection.inspection_date >= this_month
    ).all()
    
    # Calculate damage rate
    total_inspected = sum(i.inspected_quantity for i in this_month_inspections)
    total_damaged = sum(i.damaged_quantity for i in this_month_inspections)
    damage_rate = (total_damaged / total_inspected * 100) if total_inspected > 0 else 0
    
    stats = {
        'pending_inspections': total_pending,
        'this_month_inspections': len(this_month_inspections),
        'damage_rate': round(damage_rate, 1),
        'acceptance_rate': round(100 - damage_rate, 1)
    }
    
    return render_template('material_inspection/dashboard.html',
                         title='Material Inspection Dashboard',
                         pending_po_inspections=pending_po_inspections,
                         pending_job_inspections=pending_job_inspections,
                         pending_daily_entries=pending_daily_entries,
                         recent_inspections=recent_inspections,
                         stats=stats)


@material_inspection.route('/inspect/daily-entry/<int:entry_id>')
@login_required
def inspect_daily_entry(entry_id):
    """Inspect a Daily Job Work Entry for in-house work"""
    daily_entry = DailyJobWorkEntry.query.get_or_404(entry_id)
    
    # Verify this is from an in-house job work
    if daily_entry.job_work.work_type != 'in_house':
        flash('This daily entry is not from an in-house job work.', 'error')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Check if already inspected
    if daily_entry.inspection_status == 'passed':
        flash('This daily entry has already been inspected and passed.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    return render_template('material_inspection/daily_entry_inspection.html',
                         title=f'Inspect Daily Entry - {daily_entry.job_work.job_number}',
                         daily_entry=daily_entry)

@material_inspection.route('/approve-daily-entry/<int:entry_id>', methods=['POST'])
@login_required
def approve_daily_entry(entry_id):
    """Approve a Daily Job Work Entry inspection"""
    daily_entry = DailyJobWorkEntry.query.get_or_404(entry_id)
    
    # Get inspection notes and material classification from form
    inspection_notes = request.form.get('inspection_notes', '')
    material_classification = request.form.get('material_classification', 'production_use')
    
    # Update inspection status
    daily_entry.inspection_status = 'passed'
    daily_entry.inspection_notes = inspection_notes
    daily_entry.material_classification = material_classification
    daily_entry.inspected_by = current_user.id
    daily_entry.inspected_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Daily entry for {daily_entry.worker_name} on {daily_entry.work_date.strftime("%d/%m/%Y")} has been approved with classification: {material_classification.replace("_", " ").title()}!', 'success')
    return redirect(url_for('material_inspection.dashboard'))

@material_inspection.route('/reject-daily-entry/<int:entry_id>', methods=['POST'])
@login_required
def reject_daily_entry(entry_id):
    """Reject a Daily Job Work Entry inspection"""
    daily_entry = DailyJobWorkEntry.query.get_or_404(entry_id)
    
    # Get inspection notes and material classification from form
    inspection_notes = request.form.get('inspection_notes', '')
    material_classification = request.form.get('material_classification', 'production_use')
    
    # Update inspection status
    daily_entry.inspection_status = 'failed'
    daily_entry.inspection_notes = inspection_notes
    daily_entry.material_classification = material_classification
    daily_entry.inspected_by = current_user.id
    daily_entry.inspected_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Daily entry for {daily_entry.worker_name} has been rejected. Classification: {material_classification.replace("_", " ").title()}. Inspection notes: {inspection_notes}', 'warning')
    return redirect(url_for('material_inspection.dashboard'))

@material_inspection.route('/inspect/po/<int:po_id>')
@login_required
def inspect_purchase_order(po_id):
    """Start inspection for a Purchase Order"""
    po = PurchaseOrder.query.get_or_404(po_id)
    
    # Check if inspection is required
    if not po.inspection_required:
        flash('This Purchase Order does not require inspection.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Check if already inspected
    if po.inspection_status == 'completed':
        flash('This Purchase Order has already been inspected.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Update inspection status to in progress
    po.inspection_status = 'in_progress'
    po.inspected_by = current_user.id
    db.session.commit()
    
    # Enhance PO items with correct purchase unit information from UOM conversions
    for po_item in po.items:
        # Get UOM conversion for this item
        uom_conversion = ItemUOMConversion.query.filter_by(item_id=po_item.item.id).first()
        if uom_conversion:
            # Get purchase unit symbol
            purchase_unit = UnitOfMeasure.query.get(uom_conversion.purchase_unit_id)
            if purchase_unit:
                po_item.purchase_unit = purchase_unit.symbol
            else:
                po_item.purchase_unit = po_item.item.unit_of_measure
        else:
            po_item.purchase_unit = po_item.item.unit_of_measure
    
    return render_template('material_inspection/po_inspection.html',
                         title=f'Inspect Purchase Order {po.po_number}',
                         po=po)

@material_inspection.route('/inspect/job/<int:job_id>')
@login_required
def inspect_job_work(job_id):
    """Start inspection for a Job Work (outsourced only)"""
    job_work = JobWork.query.get_or_404(job_id)
    
    # Check if this is an in-house job work
    if job_work.work_type == 'in_house':
        flash('In-house job works use Daily Work Entries for inspection. Please use the Daily Entry inspection workflow.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Continue with traditional inspection for outsourced job works
    job_work = JobWork.query.get_or_404(job_id)
    
    # Check if inspection is required
    if not job_work.inspection_required:
        flash('This Job Work does not require inspection.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Check if already inspected
    if job_work.inspection_status == 'completed':
        flash('This Job Work has already been inspected.', 'info')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Update inspection status to in progress
    job_work.inspection_status = 'in_progress'
    job_work.inspected_by = current_user.id
    db.session.commit()
    
    return render_template('material_inspection/job_inspection.html',
                         title=f'Inspect Job Work {job_work.job_number}',
                         job_work=job_work)

@material_inspection.route('/inspect/process/<int:process_id>')
@login_required
def inspect_process(process_id):
    """Inspect a specific process from a multi-process job work"""
    from models import JobWorkProcess
    process = JobWorkProcess.query.get_or_404(process_id)
    job_work = process.job_work
    
    # Verify this is a multi-process job work
    if job_work.work_type != 'multi_process':
        flash('This is not a multi-process job work.', 'error')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Create a form for CSRF protection
    form = MaterialInspectionForm()
    
    return render_template('material_inspection/process_inspection.html',
                         title=f'Inspect Process: {process.process_name} - {job_work.job_number}',
                         process=process,
                         job_work=job_work,
                         form=form)

@material_inspection.route('/inspect/process/<int:process_id>/submit', methods=['POST'])
@login_required
def submit_process_inspection(process_id):
    """Submit inspection results for a specific process"""
    from models import JobWorkProcess
    process = JobWorkProcess.query.get_or_404(process_id)
    job_work = process.job_work
    
    # Get form data
    received_quantity = float(request.form.get('received_quantity', 0))
    inspected_quantity = float(request.form.get('inspected_quantity', 0))
    passed_quantity = float(request.form.get('passed_quantity', 0))
    rejected_quantity = inspected_quantity - passed_quantity
    material_classification = request.form.get('material_classification')
    inspection_date_str = request.form.get('inspection_date')
    if inspection_date_str:
        inspection_date = datetime.strptime(inspection_date_str, '%Y-%m-%d').date()
    else:
        inspection_date = datetime.now().date()
    inspection_notes = request.form.get('inspection_notes', '')
    
    # Validate quantities
    if received_quantity > process.quantity_input:
        flash(f'Received quantity cannot exceed input quantity ({process.quantity_input})', 'error')
        return redirect(url_for('material_inspection.inspect_process', process_id=process_id))
    
    if inspected_quantity > received_quantity:
        flash('Inspected quantity cannot exceed received quantity', 'error')
        return redirect(url_for('material_inspection.inspect_process', process_id=process_id))
    
    if passed_quantity > inspected_quantity:
        flash('Passed quantity cannot exceed inspected quantity', 'error')
        return redirect(url_for('material_inspection.inspect_process', process_id=process_id))
    
    # Create material inspection record
    inspection_number = generate_next_number('MaterialInspection')
    
    inspection = MaterialInspection(
        inspection_number=inspection_number,
        inspection_date=inspection_date,
        inspection_type='job_work_process',
        job_work_id=job_work.id,
        process_id=process_id,
        item_id=job_work.item_id,
        received_quantity=received_quantity,
        inspected_quantity=inspected_quantity,
        passed_quantity=passed_quantity,
        damaged_quantity=rejected_quantity,
        rejected_quantity=rejected_quantity,
        acceptance_rate=round((passed_quantity / inspected_quantity * 100) if inspected_quantity > 0 else 0, 2),
        material_classification=material_classification,
        inspection_notes=inspection_notes,
        inspector_id=current_user.id
    )
    
    db.session.add(inspection)
    
    # Update process status and output quantity
    process.quantity_output = received_quantity
    process.status = 'completed' if received_quantity == process.quantity_input else 'partial_received'
    
    # Add passed materials back to inventory
    item = job_work.item
    if passed_quantity > 0:
        if material_classification == 'finished_goods':
            item.qty_finished = (item.qty_finished or 0) + passed_quantity
        elif material_classification == 'production_use':
            item.qty_wip = (item.qty_wip or 0) + passed_quantity
        else:  # raw_material
            item.qty_raw = (item.qty_raw or 0) + passed_quantity
    
    # Add rejected materials to scrap
    if rejected_quantity > 0:
        item.qty_scrap = (item.qty_scrap or 0) + rejected_quantity
    
    db.session.commit()
    
    classification_display = material_classification.replace("_", " ") if material_classification else "inventory"
    flash(f'Process inspection completed! {passed_quantity} {item.unit_of_measure} added to {classification_display} inventory. {rejected_quantity} {item.unit_of_measure} moved to scrap.', 'success')
    return redirect(url_for('material_inspection.log_inspection', job_id=job_work.id))

@material_inspection.route('/log', methods=['GET', 'POST'])
@login_required
def log_inspection():
    """Log material inspection results"""
    # Check if po_id or job_id is provided for pre-population
    po_id = request.args.get('po_id', type=int)
    job_id = request.args.get('job_id', type=int)
    
    # Debug logging
    print(f"DEBUG: po_id = {po_id}, job_id = {job_id}, method = {request.method}")
    
    # Create form instance
    form = MaterialInspectionForm()
    
    # Pre-populate form if po_id or job_id provided
    if request.method == 'GET':
        if po_id:
            print(f"DEBUG: Setting PO ID to {po_id}")
            # Get the specific PO to verify its status
            target_po = PurchaseOrder.query.get(po_id)
            if target_po:
                print(f"DEBUG: Target PO found: {target_po.po_number}, status: {target_po.status}, inspection_status: {target_po.inspection_status}")
                # Add the specific PO to choices if it's not already there
                current_choices = list(form.purchase_order_id.choices)
                if po_id not in [choice[0] for choice in current_choices]:
                    current_choices.append((target_po.id, f"{target_po.po_number} - {target_po.supplier.name}"))
                    form.purchase_order_id.choices = current_choices
                    print(f"DEBUG: Added PO to choices")
            
            # Verify the PO exists in the choices
            po_choices = form.purchase_order_id.choices
            print(f"DEBUG: Available PO choices: {po_choices}")
            form.purchase_order_id.data = po_id
            form.job_work_id.data = 0  # Clear job work selection
            print(f"DEBUG: Form PO data set to: {form.purchase_order_id.data}")
        elif job_id:
            print(f"DEBUG: Setting Job ID to {job_id}")
            # Get the specific Job Work to verify its status
            target_job = JobWork.query.get(job_id)
            if target_job:
                print(f"DEBUG: Target Job found: {target_job.job_number}, inspection_status: {target_job.inspection_status}")
                # Add the specific Job Work to choices if it's not already there
                current_choices = list(form.job_work_id.choices)
                if job_id not in [choice[0] for choice in current_choices]:
                    current_choices.append((target_job.id, f"{target_job.job_number} - {target_job.customer_name}"))
                    form.job_work_id.choices = current_choices
                    print(f"DEBUG: Added Job Work to choices")
            
            form.job_work_id.data = job_id
            form.purchase_order_id.data = 0  # Clear purchase order selection
            
            # For multi-process job works, we need special handling
            if target_job and target_job.work_type == 'multi_process':
                # Get individual processes for this multi-process job work
                from models import JobWorkProcess
                processes = JobWorkProcess.query.filter_by(job_work_id=job_id).all()
                print(f"DEBUG: Multi-process job has {len(processes)} processes: {[p.process_name for p in processes]}")
                return render_template('material_inspection/multi_process_inspection.html',
                                     title=f'Inspect Multi-Process Job Work {target_job.job_number}',
                                     job_work=target_job,
                                     processes=processes,
                                     form=form)
    
    # Handle POST requests - ensure Job Work choices include the target when job_id provided
    if request.method == 'POST' and job_id:
        target_job = JobWork.query.get(job_id)
        if target_job:
            current_choices = list(form.job_work_id.choices)
            if job_id not in [choice[0] for choice in current_choices]:
                current_choices.append((target_job.id, f"{target_job.job_number} - {target_job.customer_name}"))
                form.job_work_id.choices = current_choices
                print(f"DEBUG POST: Added Job Work to choices for validation")
            # Ensure the form data is set correctly
            form.job_work_id.data = job_id
            print(f"DEBUG POST: Job Work data set to {form.job_work_id.data}")
            print(f"DEBUG POST: Available Job Work choices: {form.job_work_id.choices}")
    
    # Handle POST requests - ensure PO choices include the target when po_id provided  
    if request.method == 'POST' and po_id:
        target_po = PurchaseOrder.query.get(po_id)
        if target_po:
            current_choices = list(form.purchase_order_id.choices)
            if po_id not in [choice[0] for choice in current_choices]:
                current_choices.append((target_po.id, f"{target_po.po_number} - {target_po.supplier.name}"))
                form.purchase_order_id.choices = current_choices
                print(f"DEBUG POST: Added PO to choices for validation")
            form.purchase_order_id.data = po_id
    
    if form.validate_on_submit():
        # Generate inspection number
        inspection_number = generate_next_number('INSPECT', 'material_inspections', 'inspection_number')
        
        # Calculate acceptance rate
        passed_qty = form.passed_quantity.data or 0.0
        inspected_qty = form.inspected_quantity.data or 0.0
        acceptance_rate = (passed_qty / inspected_qty * 100) if inspected_qty > 0 else 0
        
        inspection = MaterialInspection(
            inspection_number=inspection_number,
            purchase_order_id=form.purchase_order_id.data if form.purchase_order_id.data else None,
            job_work_id=form.job_work_id.data if form.job_work_id.data else None,
            item_id=form.item_id.data,
            material_classification=form.material_classification.data,
            received_quantity=form.received_quantity.data,
            inspected_quantity=form.inspected_quantity.data,
            passed_quantity=form.passed_quantity.data,
            damaged_quantity=0.0,  # Not used anymore, only rejected_quantity matters
            rejected_quantity=form.rejected_quantity.data,
            acceptance_rate=acceptance_rate,
            damage_types='',  # Not used anymore
            rejection_reasons=form.rejection_reasons.data,
            inspection_notes=form.inspection_notes.data,
            inspector_id=current_user.id
        )
        
        db.session.add(inspection)
        
        # Update related PO or Job Work
        if form.purchase_order_id.data:
            po = PurchaseOrder.query.get(form.purchase_order_id.data)
            if po:
                po.inspection_status = 'completed'
                po.inspected_at = datetime.utcnow()
            
                # Automatically update PO status based on completion
                if po.status in ['draft', 'open']:
                    # Check if all materials are inspected and received
                    total_ordered = sum((item.qty or 0.0) for item in po.items if item.qty)
                    passed_quantity = form.passed_quantity.data or 0.0
                    total_received = sum((inspection.passed_quantity or 0.0) for inspection in po.material_inspections if inspection.passed_quantity) + passed_quantity
                    
                    if total_received >= total_ordered:
                        po.status = 'closed'  # All materials received
                    elif total_received > 0:
                        po.status = 'partial'  # Some materials received
                    # else status remains 'open' if nothing received yet
            
                # Update inventory with passed quantity and material classification
                item = Item.query.get(form.item_id.data)
                if item:
                    if item.current_stock is None:
                        item.current_stock = 0.0
                    passed_quantity = form.passed_quantity.data or 0.0
                    item.current_stock += passed_quantity
                    # Update the item's material classification based on inspection
                    item.material_classification = form.material_classification.data
                
        elif form.job_work_id.data:
            job_work = JobWork.query.get(form.job_work_id.data)
            if job_work:
                job_work.inspection_status = 'completed'
                job_work.inspected_at = datetime.utcnow()
                
                # Update Job Work status based on received quantity
                passed_quantity = form.passed_quantity.data or 0.0
                total_received = sum((inspection.passed_quantity or 0.0) for inspection in job_work.material_inspections if inspection.passed_quantity) + passed_quantity
                job_work.quantity_received = total_received
                
                if total_received >= job_work.quantity_sent:
                    job_work.status = 'completed'  # All materials received
                elif total_received > 0:
                    job_work.status = 'partial_received'  # Some materials received
                # else status remains 'sent' if nothing received yet
            
                # Update inventory with multi-state tracking for job work completion
                item = Item.query.get(job_work.item_id)
                if item:
                    # Calculate scrap from inspection (received - passed = scrap)
                    scrap_quantity = (form.received_quantity.data or 0.0) - passed_quantity
                    
                    # Receive materials back from WIP to finished/scrap
                    if item.receive_from_wip(passed_quantity, scrap_quantity):
                        # Update the item's material classification based on inspection
                        item.material_classification = form.material_classification.data
                        # Log the inventory movement
                        job_work.notes = (job_work.notes or '') + f"\n[{datetime.utcnow().strftime('%d/%m/%Y %H:%M')}] Inspection completed: {passed_quantity} finished, {scrap_quantity} scrap returned from WIP"
                    else:
                        # Fallback to legacy method if WIP tracking fails
                        if item.current_stock is None:
                            item.current_stock = 0.0
                        item.current_stock += passed_quantity
                        item.material_classification = form.material_classification.data
        
        db.session.commit()
        flash(f'Material inspection {inspection_number} logged successfully!', 'success')
        return redirect(url_for('material_inspection.dashboard'))
    
    # Set appropriate title based on context
    if job_id:
        target_job = JobWork.query.get(job_id)
        if target_job:
            title = f'Log Inspection - Job Work {target_job.job_number}'
        else:
            title = 'Log Job Work Inspection'
    elif po_id:
        target_po = PurchaseOrder.query.get(po_id)
        if target_po:
            title = f'Log Inspection - Purchase Order {target_po.po_number}'
        else:
            title = 'Log Purchase Order Inspection'
    else:
        title = 'Log Material Inspection'
    
    return render_template('material_inspection/log_form.html',
                         title=title,
                         form=form)

@material_inspection.route('/list')
@login_required
def list_inspections():
    """List all material inspections"""
    inspections = MaterialInspection.query.order_by(
        MaterialInspection.inspection_date.desc()
    ).all()
    
    return render_template('material_inspection/list.html',
                         title='Material Inspections',
                         inspections=inspections)

@material_inspection.route('/view/<int:inspection_id>')
@login_required
def view_inspection(inspection_id):
    """View inspection details"""
    inspection = MaterialInspection.query.get_or_404(inspection_id)
    
    return render_template('material_inspection/detail.html',
                         title=f'Inspection {inspection.inspection_number}',
                         inspection=inspection)

@material_inspection.route('/api/po_items/<int:po_id>')
@login_required
def get_po_items(po_id):
    """Get items from a Purchase Order for inspection"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        items = []
        
        for po_item in po.items:
            # Use the UOM from the purchase order item directly (already converted during PO creation)
            unit_display = po_item.uom if po_item.uom else po_item.item.unit_of_measure
                
            items.append({
                'item_id': po_item.item.id,
                'item_code': po_item.item.code,
                'item_name': po_item.item.name,
                'quantity': float(po_item.qty if po_item.qty else po_item.quantity_ordered),
                'unit': unit_display
            })
        
        return jsonify({
            'success': True,
            'items': items,
            'po_number': po.po_number
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@material_inspection.route('/api/job_items/<int:job_id>')
@login_required
def get_job_items(job_id):
    """Get items from a Job Work for inspection"""
    try:
        job = JobWork.query.get_or_404(job_id)
        items = []
        
        # JobWork has a single item, not multiple items like PurchaseOrder
        if job.item:
            items.append({
                'item_id': job.item.id,
                'item_code': job.item.code,
                'item_name': job.item.name,
                'quantity': float(job.quantity_sent),
                'unit': job.item.unit_of_measure
            })
        
        return jsonify({
            'success': True,
            'items': items,
            'job_number': job.job_number
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@material_inspection.route('/api/job_progress/<int:job_id>')
@login_required
def get_job_progress(job_id):
    """Get inspection progress data for a Job Work"""
    try:
        job = JobWork.query.get_or_404(job_id)
        
        # Calculate already inspected quantity from material inspections
        total_inspected = 0.0
        inspections = MaterialInspection.query.filter_by(job_work_id=job_id).all()
        for inspection in inspections:
            if inspection.passed_quantity:
                total_inspected += inspection.passed_quantity
        
        # Calculate remaining to inspect
        total_sent = float(job.quantity_sent)
        remaining_to_inspect = max(0, total_sent - total_inspected)
        
        # Calculate inspection percentage
        inspection_percentage = (total_inspected / total_sent * 100) if total_sent > 0 else 0
        
        progress_data = {
            'total_sent': total_sent,
            'already_inspected': total_inspected,
            'remaining_to_inspect': remaining_to_inspect,
            'inspection_percentage': round(inspection_percentage, 1),
            'unit': job.item.unit_of_measure if job.item else 'pcs',
            'job_number': job.job_number,
            'customer_name': job.customer_name
        }
        
        return jsonify({
            'success': True,
            'progress': progress_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })