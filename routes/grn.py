from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from models import JobWork, Item, User, PurchaseOrder, PurchaseOrderItem, JobWorkProcess, ItemBatch
from models.grn import GRN, GRNLineItem
from models.batch import BatchMovementLedger, BatchConsumptionReport
from forms_grn import GRNForm, GRNLineItemForm, QuickReceiveForm, QuickReceivePOForm, GRNSearchForm, MultiProcessQuickReceiveForm
from services.batch_management import BatchManager, BatchValidator
from utils.documents import DocumentUploadManager, save_uploaded_documents
from models.document import create_document_record
from services.authentic_accounting_integration import AuthenticAccountingIntegration
from services.accounting_automation import AccountingAutomation
from datetime import datetime, date
from utils import generate_next_number
from sqlalchemy import func, and_, or_


def update_po_status_based_on_grn(purchase_order_id):
    """Automatically update Purchase Order status based on GRN activities"""
    try:
        po = PurchaseOrder.query.get(purchase_order_id)
        if not po:
            return
            
        # Get all GRNs for this PO
        po_grns = GRN.query.filter_by(purchase_order_id=purchase_order_id).all()
        
        if not po_grns:
            # No GRNs yet, keep as 'sent'
            if po.status not in ['cancelled']:
                po.status = 'sent'
            return
            
        # Calculate total ordered vs received quantities
        total_ordered = {}
        total_received = {}
        
        # Sum ordered quantities by item
        for po_item in po.items:
            item_id = po_item.item_id
            total_ordered[item_id] = total_ordered.get(item_id, 0) + po_item.qty
            
        # Sum received quantities by item from all GRNs
        for grn in po_grns:
            for line_item in grn.line_items:
                item_id = line_item.item_id
                total_received[item_id] = total_received.get(item_id, 0) + line_item.quantity_received
        
        # Update quantity_received in PO items for dashboard display
        for po_item in po.items:
            item_id = po_item.item_id
            received_qty = total_received.get(item_id, 0)
            po_item.quantity_received = received_qty
                
        # Determine new status
        all_items_fully_received = True
        any_items_partially_received = False
        
        for item_id, ordered_qty in total_ordered.items():
            received_qty = total_received.get(item_id, 0)
            
            if received_qty < ordered_qty:
                all_items_fully_received = False
                
            if received_qty > 0:
                any_items_partially_received = True
                
        # Update PO status
        if all_items_fully_received:
            po.status = 'closed'
        elif any_items_partially_received:
            po.status = 'partial'
        else:
            po.status = 'sent'
            
        db.session.commit()
        
    except Exception as e:
        print(f"Error updating PO status: {str(e)}")
        db.session.rollback()


def create_batch_from_grn_line_item(grn, line_item):
    """Create batch during GRN line item processing for complete traceability"""
    try:
        # Generate batch number based on GRN and supplier info
        supplier_code = grn.supplier.supplier_code[:3] if grn.supplier else "SUP"
        grn_date = grn.received_date.strftime("%Y%m%d") if grn.received_date else datetime.now().strftime("%Y%m%d")
        
        # Create unique batch number: SUP-YYYYMMDD-GRN###-ITEM###
        batch_number = f"{supplier_code}-{grn_date}-{grn.grn_number.split('-')[-1]}-{line_item.item.item_code[:3]}"
        
        # Check if batch already exists for this line item
        existing_batch = ItemBatch.query.filter_by(
            item_id=line_item.item_id,
            batch_number=batch_number
        ).first()
        
        if existing_batch:
            # Update existing batch quantity
            existing_batch.qty_raw += line_item.quantity_received
            existing_batch.purchase_rate = line_item.unit_rate or 0
            existing_batch.updated_at = datetime.utcnow()
            return existing_batch
        
        # Create new batch
        new_batch = ItemBatch(
            item_id=line_item.item_id,
            batch_number=batch_number,
            supplier_batch=line_item.supplier_batch_number or "",
            manufacture_date=line_item.manufacture_date or grn.received_date,
            expiry_date=line_item.expiry_date,
            qty_raw=line_item.quantity_received,
            purchase_rate=line_item.unit_rate or 0,
            storage_location='Default',
            grn_id=grn.id,
            quality_status='pending_inspection',
            created_by=current_user.id,
            quality_notes=f"Received via GRN {grn.grn_number} from {grn.supplier.name if grn.supplier else 'Unknown Supplier'}"
        )
        
        db.session.add(new_batch)
        return new_batch
        
    except Exception as e:
        print(f"Error creating batch from GRN line item: {str(e)}")
        return None


def update_inventory_with_batch_tracking(grn):
    """Update inventory with comprehensive batch tracking during GRN processing"""
    try:
        add_to_inventory = getattr(grn, 'add_to_inventory', True)
        
        for line_item in grn.line_items:
            # Create batch using the BatchManager service with proper inventory flag
            batch, message = BatchManager.create_batch_from_grn(line_item, add_to_inventory=add_to_inventory)
            
            if batch:
                # Store batch reference in line item for traceability
                line_item.batch_id = batch.id
                
                # Update item's main inventory quantities ONLY if add_to_inventory is True
                if add_to_inventory:
                    item = line_item.item
                    
                    # Calculate quantities to add
                    quantity_passed = line_item.quantity_passed or line_item.quantity_received
                    quantity_rejected = line_item.quantity_rejected or 0
                    
                    # Add passed quantity to appropriate inventory state
                    if hasattr(item, 'qty_raw'):
                        item.qty_raw = (item.qty_raw or 0) + quantity_passed
                    elif hasattr(item, 'qty_stock'):
                        item.qty_stock = (item.qty_stock or 0) + quantity_passed
                    
                    # Add rejected quantity to scrap
                    if quantity_rejected > 0:
                        item.qty_scrap = (item.qty_scrap or 0) + quantity_rejected
                        
                    # Sync current_stock with multi-state inventory
                    if hasattr(item, 'sync_stock'):
                        item.sync_stock()
                else:
                    # When add_to_inventory is False, items stay in inspection area
                    # The batch will have qty_inspection > 0 and qty_raw = 0
                    pass
                
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"Error updating inventory with batch tracking: {str(e)}")
        db.session.rollback()
        return False

def process_grn_with_batch_tracking(grn, add_to_inventory=True):
    """Process GRN completion with comprehensive batch tracking"""
    try:
        # Set GRN inspection status based on line items
        if hasattr(grn, 'line_items') and grn.line_items:
            # Get inspection status from the first line item (they should all be the same)
            line_item_status = grn.line_items[0].inspection_status
            grn.inspection_status = line_item_status
            
        # CORRECTED WORKFLOW: When add_to_inventory=True, bypass inspection completely
        if add_to_inventory:
            # Force inspection status to passed for add_to_inventory workflow
            grn.inspection_status = 'passed'
            for line_item in grn.line_items:
                line_item.inspection_status = 'passed'
            
            # Move directly to inventory with batch tracking
            success = update_inventory_with_batch_tracking(grn)
            if not success:
                return False, "Failed to update inventory with batch tracking"
        else:
            # Create batches but keep them in receiving/inspection area (qty_inspection)
            success = create_inspection_batches(grn)
            if not success:
                return False, "Failed to create inspection batches"
        
        # Mark GRN as completed based on add_to_inventory flag and inspection status
        if add_to_inventory and grn.inspection_status == 'passed':
            grn.status = 'completed'  # Material in inventory
            grn.inspected_by = current_user.id
            grn.inspected_at = datetime.utcnow()
        elif grn.inspection_status in ['passed', 'failed']:
            grn.status = 'completed'
            grn.inspected_by = current_user.id
            grn.inspected_at = datetime.utcnow()
        else:
            grn.status = 'received'  # Received but awaiting inspection
        
        grn.add_to_inventory = add_to_inventory
        
        # Update job work status if applicable
        if grn.job_work:
            update_job_work_status_from_grn(grn)
        
        # Update purchase order status if applicable  
        if grn.purchase_order:
            update_po_status_based_on_grn(grn.purchase_order_id)
        
        # GRN processing complete - accounting entries handled separately via 3-step workflow
        # The 3-step GRN workflow handles: GRN → Invoice → Payment cycle with proper clearing accounts
        
        # Auto-create workflow status for new GRNs
        from models.grn import GRNWorkflowStatus
        workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first()
        if not workflow_status:
            workflow_status = GRNWorkflowStatus(
                grn_id=grn.id,
                material_received=True,
                material_received_date=grn.received_date or datetime.utcnow(),
                invoice_received=False,
                payment_made=False
            )
            db.session.add(workflow_status)
        
        db.session.commit()
        return True, "GRN processed successfully with batch tracking and accounting entries"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error processing GRN: {str(e)}"

def create_inspection_batches(grn):
    """Create batches for materials in inspection area (not yet in inventory)"""
    try:
        for line_item in grn.line_items:
            # Use BatchManager to create inspection batches (NOT added to inventory)
            batch, message = BatchManager.create_batch_from_grn(line_item, add_to_inventory=False)
            
            if batch:
                # Store batch reference in line item for traceability
                line_item.batch_id = batch.id
            else:
                print(f"Failed to create inspection batch: {message}")
                return False
            
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"Error creating inspection batches: {str(e)}")
        db.session.rollback()
        return False

def update_job_work_status_from_grn(grn):
    """Update job work status based on GRN receipt with batch tracking"""
    if not grn.job_work:
        return
    
    job_work = grn.job_work
    
    # Calculate total received vs expected quantities
    total_received = sum(line_item.quantity_received for line_item in grn.line_items)
    expected_quantity = job_work.quantity_sent
    
    if total_received >= expected_quantity:
        job_work.status = 'completed'
    else:
        job_work.status = 'partial_received'
    
    # Add GRN reference to job work notes
    completion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] GRN {grn.grn_number} - {total_received} units received with batch tracking"
    
    if job_work.notes:
        job_work.notes += f"\n{completion_note}"
    else:
        job_work.notes = completion_note

def approve_inspection_and_move_to_inventory(batch_id, inspection_result='passed'):
    """Move batch from inspection area to inventory after inspection approval"""
    try:
        from models.batch import InventoryBatch
        
        batch = InventoryBatch.query.get(batch_id)
        if not batch:
            return False, "Batch not found"
        
        if batch.inspection_status != 'pending':
            return False, f"Batch already inspected with status: {batch.inspection_status}"
        
        if inspection_result == 'passed':
            # Move from inspection to raw materials inventory
            batch.qty_raw = batch.qty_inspection
            batch.qty_inspection = 0.0
            batch.inspection_status = 'passed'
            batch.location = 'MAIN-STORE'
            
            # Update item's inventory quantities
            item = batch.item
            if hasattr(item, 'qty_raw'):
                item.qty_raw = (item.qty_raw or 0) + batch.qty_raw
            item.sync_stock()
            
        elif inspection_result == 'failed':
            # Move to scrap or quarantine
            batch.qty_scrap = batch.qty_inspection
            batch.qty_inspection = 0.0
            batch.inspection_status = 'failed'
            batch.location = 'QUARANTINE'
            
        elif inspection_result == 'quarantine':
            # Keep in inspection but mark as quarantined
            batch.inspection_status = 'quarantine'
            batch.location = 'QUARANTINE'
        
        db.session.commit()
        return True, f"Batch inspection completed: {inspection_result}"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error approving inspection: {str(e)}"


grn_bp = Blueprint('grn', __name__)

@grn_bp.route('/grn/<int:grn_id>/batches')
@login_required 
def view_grn_batches(grn_id):
    """View batches created from a specific GRN"""
    grn = GRN.query.get_or_404(grn_id)
    
    # Get all batches created from this GRN
    created_batches = []
    for line_item in grn.line_items:
        if hasattr(line_item, 'created_batches'):
            created_batches.extend(line_item.created_batches)
    
    # Alternative: find batches by GRN reference
    if not created_batches:
        batches = ItemBatch.query.filter(
            ItemBatch.ref_type == 'GRN',
            ItemBatch.ref_id == grn_id
        ).all()
        created_batches = batches
    
    return render_template('grn/batch_view.html',
                         title=f'Batches Created from GRN {grn.grn_number}',
                         grn=grn,
                         batches=created_batches)

@grn_bp.route('/dashboard')
@login_required
def dashboard():
    """GRN Dashboard with Parent-Child structure matching Batch Tracking Dashboard"""
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    source_type_filter = request.args.get('source_type', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Calculate statistics
    stats = {
        'total_grns': GRN.query.count(),
        'pending_inspection': GRN.query.filter(GRN.inspection_status == 'pending').count(),
        'completed_today': GRN.query.filter(
            GRN.received_date == date.today(),
            GRN.status == 'completed'
        ).count(),
        'pending_grns': GRN.query.filter(GRN.status.in_(['draft', 'received'])).count()
    }
    
    # Parent-Child Structure: Get Parent orders with their associated GRNs
    parent_child_data = []
    
    # 1. Purchase Orders as Parents
    purchase_orders = PurchaseOrder.query.filter(
        PurchaseOrder.grn_receipts_po.any()
    ).order_by(PurchaseOrder.created_at.desc()).all()
    
    for po in purchase_orders:
        # Calculate totals for this PO
        total_qty = sum(item.qty for item in po.items)
        grn_count = len(po.grn_receipts_po)
        
        # Use actual PO status from database (more accurate than GRN status logic)
        if po.status == 'closed':
            po_status = 'Completed'
        elif po.status == 'partial':
            po_status = 'Partial'
        else:
            po_status = 'Pending'
        
        # Build child GRNs with details
        child_grns = []
        for grn in po.grn_receipts_po:
            # Get item details for this GRN
            item_details = []
            total_received = 0
            total_scrap = 0
            
            for line_item in grn.line_items:
                item_details.append(f"{line_item.item.name} ({line_item.quantity_received} {line_item.unit_of_measure})")
                total_received += line_item.quantity_received or 0
                total_scrap += line_item.quantity_rejected or 0
            
            child_grns.append({
                'grn_number': grn.grn_number,
                'grn_date': grn.received_date,
                'item_details': ', '.join(item_details),
                'received_qty': total_received,
                'scrap_qty': total_scrap,
                'status': grn.status.title(),
                'grn_id': grn.id,
                'source_type': 'Purchase Order',
                'source_document': po.po_number,
                'inspection_status': grn.inspection_status.title() if grn.inspection_status else 'Pending',
                'inventory_updated': grn.add_to_inventory if hasattr(grn, 'add_to_inventory') else True
            })
        
        parent_child_data.append({
            'type': 'Purchase Order',
            'parent_doc': po.po_number,
            'date': po.created_at.date(),
            'vendor_customer': po.supplier.name if po.supplier else 'N/A',
            'status': po_status,
            'total_qty': total_qty,
            'grn_count': grn_count,
            'child_grns': child_grns,
            'parent_id': f'po_{po.id}'
        })
    
    # 2. Job Works as Parents
    job_works = JobWork.query.filter(
        JobWork.grn_receipts.any()
    ).order_by(JobWork.created_at.desc()).all()
    
    for jw in job_works:
        # Calculate totals for this Job Work - use quantity_sent as the total
        total_qty = getattr(jw, 'quantity_sent', 0)
        grn_count = len(jw.grn_receipts)
        
        # Use JobWork status logic - check if completion is tracked
        if hasattr(jw, 'status'):
            if jw.status == 'completed':
                jw_status = 'Completed'
            elif jw.status == 'partial':
                jw_status = 'Partial'
            else:
                jw_status = 'Pending'
        else:
            # Fallback to GRN completion logic for JobWork
            if all(grn.status == 'completed' for grn in jw.grn_receipts):
                jw_status = 'Completed'
            elif any(grn.status in ['received', 'inspected'] for grn in jw.grn_receipts):
                jw_status = 'Partial'
            else:
                jw_status = 'Pending'
        
        # Build child GRNs with details
        child_grns = []
        for grn in jw.grn_receipts:
            # Get item details for this GRN
            item_details = []
            total_received = 0
            total_scrap = 0
            
            for line_item in grn.line_items:
                item_details.append(f"{line_item.item.name} ({line_item.quantity_received} {line_item.unit_of_measure})")
                total_received += line_item.quantity_received or 0
                total_scrap += line_item.quantity_rejected or 0
            
            child_grns.append({
                'grn_number': grn.grn_number,
                'grn_date': grn.received_date,
                'item_details': ', '.join(item_details),
                'received_qty': total_received,
                'scrap_qty': total_scrap,
                'status': grn.status.title(),
                'grn_id': grn.id,
                'source_type': 'Job Work',
                'source_document': jw.job_number,
                'inspection_status': grn.inspection_status.title() if grn.inspection_status else 'Pending',
                'inventory_updated': grn.add_to_inventory if hasattr(grn, 'add_to_inventory') else True
            })
        
        parent_child_data.append({
            'type': 'Job Work',
            'parent_doc': jw.job_number,
            'date': jw.created_at.date(),
            'vendor_customer': getattr(jw.vendor, 'name', 'In-House') if hasattr(jw, 'vendor') and jw.vendor else 'In-House',
            'status': jw_status,
            'total_qty': total_qty,
            'grn_count': grn_count,
            'child_grns': child_grns,
            'parent_id': f'jw_{jw.id}'
        })
    
    # Get job works pending GRN creation - including unified jobs with outsourced processes
    pending_job_works = JobWork.query.filter(
        JobWork.status.in_(['sent', 'partial_received']),
        or_(
            JobWork.work_type.in_(['outsourced', 'multi_process', 'vendor']),
            # Include unified jobs that have outsourced processes
            and_(
                JobWork.work_type == 'unified',
                JobWork.id.in_(
                    db.session.query(JobWorkProcess.job_work_id).filter(
                        JobWorkProcess.work_type == 'outsourced'
                    ).distinct()
                )
            )
        )
    ).order_by(JobWork.sent_date.desc()).limit(20).all()
    
    # Get purchase orders pending GRN creation
    pending_purchase_orders = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_(['sent', 'partial'])
    ).order_by(PurchaseOrder.order_date.desc()).limit(20).all()
    
    # Update PO quantities to ensure they're current
    for po in pending_purchase_orders:
        update_po_status_based_on_grn(po.id)
    
    # Commit any changes and refresh data
    db.session.commit()
    
    # Filter POs that actually have pending quantities
    pending_purchase_orders = [po for po in pending_purchase_orders 
                             if any(item.pending_quantity > 0 for item in po.items)]
    
    # Calculate monthly trends
    current_month = date.today().replace(day=1)
    monthly_grns = GRN.query.filter(GRN.received_date >= current_month).count()
    
    return render_template('grn/dashboard.html',
                         title='GRN Dashboard',
                         parent_child_data=parent_child_data,
                         stats=stats,
                         pending_job_works=pending_job_works,
                         pending_purchase_orders=pending_purchase_orders,
                         monthly_grns=monthly_grns)


@grn_bp.route('/create/job_work/<int:job_work_id>')
@login_required
def create_grn(job_work_id):
    """Create a new GRN for a job work"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    # Check if user can create GRN for this job work
    if job_work.status not in ['sent', 'partial_received']:
        flash('Cannot create GRN for this job work. Invalid status.', 'error')
        return redirect(url_for('jobwork.detail', id=job_work_id))
    
    form = GRNForm()
    if not form.grn_number.data:
        form.grn_number.data = GRN.generate_grn_number()
    form.job_work_id.data = job_work_id
    
    if form.validate_on_submit():
        try:
            # Create GRN
            grn = GRN(
                grn_number=form.grn_number.data,
                job_work_id=job_work_id,
                received_date=form.received_date.data,
                received_by=current_user.id,
                delivery_note=form.delivery_note.data,
                transporter_name=form.transporter_name.data,
                vehicle_number=form.vehicle_number.data,
                inspection_required=form.inspection_required.data,
                status='received',  # Automatically set to received
                remarks=form.remarks.data
            )
            
            db.session.add(grn)
            db.session.commit()
            
            # Send GRN created notification
            from services.comprehensive_notifications import comprehensive_notification_service
            try:
                comprehensive_notification_service.notify_grn_created(grn)
            except Exception as e:
                print(f"GRN notification error: {e}")
            
            flash(f'GRN {grn.grn_number} created successfully!', 'success')
            return redirect(url_for('grn.add_line_items', grn_id=grn.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating GRN: {str(e)}', 'error')
    
    return render_template('grn/create.html',
                         title='Create GRN',
                         form=form,
                         job_work=job_work)


@grn_bp.route('/create/purchase_order/<int:purchase_order_id>', methods=['GET', 'POST'])
@login_required
def create_grn_for_po(purchase_order_id):
    """Create a new GRN for a purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(purchase_order_id)
    
    # Check if user can create GRN for this PO
    if purchase_order.status not in ['sent', 'partial']:
        flash('Cannot create GRN for this purchase order. Invalid status.', 'error')
        return redirect(url_for('purchase.detail', id=purchase_order_id))
    
    form = GRNForm()
    if not form.grn_number.data:
        form.grn_number.data = GRN.generate_grn_number()
    form.purchase_order_id.data = purchase_order_id
    
    if form.validate_on_submit():
        try:
            # Create GRN for PO
            grn = GRN(
                grn_number=form.grn_number.data,
                purchase_order_id=purchase_order_id,
                received_date=form.received_date.data,
                received_by=current_user.id,
                delivery_note=form.delivery_note.data,
                transporter_name=form.transporter_name.data,
                vehicle_number=form.vehicle_number.data,
                inspection_required=form.inspection_required.data,
                status='received',  # Automatically set to received
                remarks=form.remarks.data
            )
            
            db.session.add(grn)
            db.session.commit()
            
            # Update PO status automatically based on GRN creation
            update_po_status_based_on_grn(purchase_order_id)
            
            flash(f'GRN {grn.grn_number} created successfully for PO {purchase_order.po_number}!', 'success')
            return redirect(url_for('grn.add_line_items', grn_id=grn.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating GRN: {str(e)}', 'error')
    
    return render_template('grn/create.html',
                         title='Create GRN for Purchase Order',
                         form=form,
                         purchase_order=purchase_order)


@grn_bp.route('/quick_receive/<int:job_work_id>', methods=['GET', 'POST'])
@login_required
def quick_receive(job_work_id):
    """Quick receive form for simple material receipt"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    # Redirect multi-process jobs to specialized form
    if job_work.work_type in ['multi_process', 'unified']:
        return redirect(url_for('grn.quick_receive_multi_process', job_work_id=job_work_id))
    
    form = QuickReceiveForm()
    form.job_work_id.data = job_work_id
    
    if form.validate_on_submit():
        try:
            # Create GRN automatically
            grn = GRN(
                grn_number=GRN.generate_grn_number(),
                job_work_id=job_work_id,
                received_date=form.received_date.data,
                received_by=current_user.id,
                delivery_note=form.delivery_note.data,
                inspection_required=True,
                status='received',
                remarks=form.remarks.data
            )
            db.session.add(grn)
            db.session.flush()  # To get the GRN ID
            
            # Auto-calculate passed quantity
            quantity_passed = form.quantity_received.data - (form.quantity_rejected.data or 0)
            
            # Create line item
            line_item = GRNLineItem(
                grn_id=grn.id,
                item_id=job_work.item_id,
                quantity_received=form.quantity_received.data,
                quantity_passed=quantity_passed,
                quantity_rejected=form.quantity_rejected.data or 0,
                unit_of_measure=job_work.item.unit_of_measure,
                inspection_status=form.inspection_status.data,
                rejection_reason=form.rejection_reason.data,
                remarks=form.remarks.data
            )
            db.session.add(line_item)
            
            # Update job work quantities
            job_work.quantity_received = (job_work.quantity_received or 0) + form.quantity_received.data
            
            # Update job work status and add notes
            if job_work.quantity_received >= job_work.quantity_sent:
                job_work.status = 'completed'
                # Add completion note
                completion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Completed via GRN {grn.grn_number} - All {job_work.quantity_sent} {job_work.item.unit_of_measure} received"
            else:
                job_work.status = 'partial_received'
                # Add partial receipt note
                completion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Partial receipt via GRN {grn.grn_number} - {form.quantity_received.data} {job_work.item.unit_of_measure} received, {job_work.pending_quantity} {job_work.item.unit_of_measure} pending"
            
            # Add note to job work
            if job_work.notes:
                job_work.notes += f"\n{completion_note}"
            else:
                job_work.notes = completion_note
            
            # Update inventory if adding to stock
            if form.add_to_inventory.data and quantity_passed > 0:
                # For BOM-based jobs, add materials to the final output product instead of input material
                if job_work.bom_id and job_work.production_quantity:
                    # Find the final output product from BOM processes
                    final_output_item = None
                    if job_work.processes:
                        # Get the last process's output item
                        sorted_processes = sorted(job_work.processes, key=lambda x: x.sequence_number or 0)
                        if sorted_processes and sorted_processes[-1].output_item:
                            final_output_item = sorted_processes[-1].output_item
                    
                    if final_output_item:
                        # Add to final output product (e.g., Mounted Plate)
                        final_output_item.qty_finished = (final_output_item.qty_finished or 0) + quantity_passed
                        # Add rejected quantity to final output product's scrap
                        if form.quantity_rejected.data and form.quantity_rejected.data > 0:
                            final_output_item.qty_scrap = (final_output_item.qty_scrap or 0) + form.quantity_rejected.data
                    else:
                        # Fallback to input material if no output item found
                        job_work.item.qty_finished = (job_work.item.qty_finished or 0) + quantity_passed
                        if form.quantity_rejected.data and form.quantity_rejected.data > 0:
                            job_work.item.qty_scrap = (job_work.item.qty_scrap or 0) + form.quantity_rejected.data
                else:
                    # Regular job work - add to input material
                    job_work.item.qty_finished = (job_work.item.qty_finished or 0) + quantity_passed
                    # Add rejected quantity to scrap if any
                    if form.quantity_rejected.data and form.quantity_rejected.data > 0:
                        job_work.item.qty_scrap = (job_work.item.qty_scrap or 0) + form.quantity_rejected.data
                
                grn.add_to_inventory = True  # Set the flag to True when inventory is updated
            else:
                grn.add_to_inventory = False  # Set the flag to False when inventory is not updated
            
            # Handle document uploads
            uploaded_documents = []
            if hasattr(form, 'supporting_documents') and form.supporting_documents.data:
                try:
                    # Process uploaded documents
                    doc_manager = DocumentUploadManager('grn')
                    uploaded_files = doc_manager.process_form_files(form)
                    
                    for file_info in uploaded_files:
                        if file_info.get('success'):
                            document = create_document_record(
                                file_info=file_info,
                                module_name='grn',
                                reference_type='grn',
                                reference_id=grn.id,
                                document_type='supporting_document',
                                description=form.document_description.data if hasattr(form, 'document_description') else None,
                                user_id=current_user.id
                            )
                            if document:
                                uploaded_documents.append(document)
                except Exception as e:
                    print(f"Error processing documents: {e}")
            
            # Process GRN with comprehensive batch tracking
            if form.inspection_status.data in ['passed', 'rejected']:
                add_to_inventory = form.add_to_inventory.data if hasattr(form, 'add_to_inventory') else True
                success, message = process_grn_with_batch_tracking(grn, add_to_inventory)
                
                if not success:
                    flash(f'Error processing GRN: {message}', 'error')
                    return redirect(url_for('grn.dashboard'))
            else:
                db.session.commit()
            
            success_message = f'Materials received successfully! GRN {grn.grn_number} created with batch tracking.'
            if uploaded_documents:
                success_message += f' {len(uploaded_documents)} document(s) uploaded.'
            
            flash(success_message, 'success')
            return redirect(url_for('jobwork.detail', id=job_work_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error receiving materials: {str(e)}', 'error')
    
    return render_template('grn/quick_receive.html',
                         title='Quick Receive Materials',
                         form=form,
                         job_work=job_work)


@grn_bp.route('/quick_receive_multi_process/<int:job_work_id>', methods=['GET', 'POST'])
@login_required
def quick_receive_multi_process(job_work_id):
    """Specialized quick receive form for multi-process job works"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    # Ensure this is a multi-process or unified job work
    if job_work.work_type not in ['multi_process', 'unified']:
        flash('This function is only for multi-process job works.', 'error')
        return redirect(url_for('grn.quick_receive', job_work_id=job_work_id))
    
    # Get all processes for this job work
    processes = JobWorkProcess.query.filter_by(job_work_id=job_work_id).all()
    if not processes:
        flash('No processes found for this multi-process job work.', 'error')
        return redirect(url_for('multi_process_jobwork.detail', id=job_work_id))
    
    form = MultiProcessQuickReceiveForm()
    form.job_work_id.data = job_work_id
    
    # Get sequential process information for better understanding
    processes_ordered = sorted(processes, key=lambda x: x.sequence_number)
    
    # Populate process choices with sequential flow information
    form.process_selection.choices = []
    for p in processes_ordered:
        # Determine input source for this process
        if p.sequence_number == 1:
            input_source = job_work.item.name  # First process uses raw material
        else:
            # Find previous process
            prev_process = next((pr for pr in processes if pr.sequence_number == p.sequence_number - 1), None)
            if prev_process and prev_process.output_item_id:
                input_source = prev_process.output_item.name
            else:
                input_source = job_work.item.name
        
        # Create descriptive choice text showing sequential flow
        if p.output_item_id:
            flow_info = f" | {input_source} → {p.output_item.name} ({p.output_quantity} {p.output_item.unit_of_measure})"
        else:
            flow_info = f" | {input_source} → Same as input"
        
        form.process_selection.choices.append((p.id, f"Seq {p.sequence_number}: {p.process_name} - {p.work_type} ({p.status}){flow_info}"))
    
    if form.validate_on_submit():
        try:
            # Get selected process
            selected_process = JobWorkProcess.query.get(form.process_selection.data)
            if not selected_process:
                flash('Selected process not found.', 'error')
                return redirect(request.url)
            
            # Create GRN automatically
            grn = GRN(
                grn_number=GRN.generate_grn_number(),
                job_work_id=job_work_id,
                received_date=form.received_date.data,
                received_by=current_user.id,
                delivery_note=form.delivery_note.data,
                inspection_required=True,
                status='received',
                remarks=f"Multi-process receipt from {selected_process.process_name} process. {form.remarks.data or ''}"
            )
            db.session.add(grn)
            db.session.flush()  # To get the GRN ID
            
            # Auto-calculate passed quantity
            quantity_passed = form.quantity_received.data - (form.quantity_rejected.data or 0)
            
            # Determine which item is being received (output item or original item)
            receiving_item_id = selected_process.output_item_id if selected_process.output_item_id else job_work.item_id
            receiving_item = Item.query.get(receiving_item_id)
            
            # Create line item with process information
            line_item = GRNLineItem(
                grn_id=grn.id,
                item_id=receiving_item_id,
                quantity_received=form.quantity_received.data,
                quantity_passed=quantity_passed,
                quantity_rejected=form.quantity_rejected.data or 0,
                unit_of_measure=receiving_item.unit_of_measure,
                inspection_status=form.inspection_status.data,
                rejection_reason=form.rejection_reason.data,
                process_name=selected_process.process_name,
                process_stage=form.process_stage.data or selected_process.process_name
            )
            db.session.add(line_item)
            
            # Update inventory if requested and materials passed inspection
            if form.add_to_inventory.data and quantity_passed > 0:
                # Add to the output item's finished inventory (multi-state system)
                receiving_item.qty_finished = (receiving_item.qty_finished or 0) + quantity_passed
                # Add rejected quantity to scrap if any
                if form.quantity_rejected.data and form.quantity_rejected.data > 0:
                    receiving_item.qty_scrap = (receiving_item.qty_scrap or 0) + form.quantity_rejected.data
                grn.add_to_inventory = True
            else:
                grn.add_to_inventory = False
            
            # Process individual process scrap tracking
            process_scrap_updates = {}
            scrap_update_notes = []
            for key, value in request.form.items():
                if key.startswith('scrap_process_') and value:
                    try:
                        sequence_number = int(key.replace('scrap_process_', ''))
                        scrap_quantity = float(value)
                        if scrap_quantity > 0:
                            process_scrap_updates[sequence_number] = scrap_quantity
                    except (ValueError, TypeError):
                        continue
            
            # Update individual process scrap quantities
            for seq_num, scrap_qty in process_scrap_updates.items():
                process = JobWorkProcess.query.filter_by(
                    job_work_id=job_work_id,
                    sequence_number=seq_num
                ).first()
                if process:
                    old_scrap = process.quantity_scrap or 0
                    process.quantity_scrap = scrap_qty
                    scrap_update_notes.append(
                        f"Process {seq_num} ({process.process_name}): {old_scrap} → {scrap_qty} kg scrap"
                    )
            
            # Update process completion status
            if form.inspection_status.data == 'passed':
                selected_process.quantity_output = (selected_process.quantity_output or 0) + quantity_passed
                # Add rejected quantity to current process scrap only if no individual scrap tracking was done
                if selected_process.sequence_number not in process_scrap_updates:
                    selected_process.quantity_scrap = (selected_process.quantity_scrap or 0) + (form.quantity_rejected.data or 0)
                if selected_process.quantity_output >= selected_process.quantity_input:
                    selected_process.status = 'completed'
                    selected_process.actual_completion = datetime.utcnow()
            
            # Mark GRN as completed if no further inspection needed
            if form.inspection_status.data in ['passed', 'rejected']:
                grn.status = 'completed'
                grn.inspection_status = 'completed'
                grn.inspected_by = current_user.id
                grn.inspected_at = datetime.utcnow()
            
            # Update job work status and quantity_received based on completion
            # For multi-process jobs, we need to check if all expected outputs have been received
            total_expected_output = sum(p.output_quantity or 0 for p in processes if p.output_item_id)
            total_received_output = sum(gli.quantity_passed for grn_item in GRN.query.filter_by(job_work_id=job_work_id).all() 
                                      for gli in grn_item.line_items if gli.item_id != job_work.item_id)  # Exclude input material
            
            if total_received_output >= total_expected_output and total_expected_output > 0:
                # All expected output received - mark job as completed
                job_work.status = 'completed'
                job_work.quantity_received = job_work.quantity_sent  # Mark input as fully processed
                
                # Remove input material from WIP since it's been transformed
                # Use the Item model's receive_from_wip method to properly clear WIP from the correct process
                if processes:
                    # For multi-process jobs, clear from first process
                    first_process = min(processes, key=lambda p: p.sequence_number)
                    process_name = first_process.process_name.lower()
                    job_work.item.receive_from_wip(0, 0, process=process_name)  # Just clear WIP, no finished/scrap added here
                    # Manually adjust to only clear the WIP amount without adding to finished (since output products were already added)
                    if process_name == 'cutting':
                        job_work.item.qty_wip_cutting = max(0, (job_work.item.qty_wip_cutting or 0) - job_work.quantity_sent)
                    elif process_name == 'bending':
                        job_work.item.qty_wip_bending = max(0, (job_work.item.qty_wip_bending or 0) - job_work.quantity_sent)
                    elif process_name == 'welding':
                        job_work.item.qty_wip_welding = max(0, (job_work.item.qty_wip_welding or 0) - job_work.quantity_sent)
                    elif process_name == 'zinc':
                        job_work.item.qty_wip_zinc = max(0, (job_work.item.qty_wip_zinc or 0) - job_work.quantity_sent)
                    elif process_name == 'painting':
                        job_work.item.qty_wip_painting = max(0, (job_work.item.qty_wip_painting or 0) - job_work.quantity_sent)
                    elif process_name == 'assembly':
                        job_work.item.qty_wip_assembly = max(0, (job_work.item.qty_wip_assembly or 0) - job_work.quantity_sent)
                    elif process_name == 'machining':
                        job_work.item.qty_wip_machining = max(0, (job_work.item.qty_wip_machining or 0) - job_work.quantity_sent)
                    elif process_name == 'polishing':
                        job_work.item.qty_wip_polishing = max(0, (job_work.item.qty_wip_polishing or 0) - job_work.quantity_sent)
                
                completion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Completed via GRN {grn.grn_number} - All expected output materials received"
            else:
                # Partial completion
                job_work.status = 'partial_received'
                completion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Partial receipt via GRN {grn.grn_number} - {quantity_passed} {receiving_item.unit_of_measure} received"
            
            # Add completion note to job work
            if job_work.notes:
                job_work.notes += f"\n{completion_note}"
            else:
                job_work.notes = completion_note
            
            db.session.commit()
            
            # Create success message with scrap tracking info
            success_message = f'Materials received from {selected_process.process_name} process! GRN {grn.grn_number} created.'
            if scrap_update_notes:
                success_message += f' Individual process scrap updated: {"; ".join(scrap_update_notes)}.'
            
            flash(success_message, 'success')
            return redirect(url_for('multi_process_jobwork.detail', id=job_work_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error receiving materials: {str(e)}', 'error')
    
    return render_template('grn/quick_receive_multi_process.html',
                         title='Receive Multi-Process Materials',
                         form=form,
                         job_work=job_work,
                         processes=processes)


@grn_bp.route('/quick_receive_po/<int:purchase_order_id>/<int:item_id>', methods=['GET', 'POST'])
@login_required
def quick_receive_po(purchase_order_id, item_id):
    """Quick receive form for purchase order items"""
    purchase_order = PurchaseOrder.query.get_or_404(purchase_order_id)
    item = Item.query.get_or_404(item_id)
    
    # Get the specific PO item
    po_item = None
    for pi in purchase_order.items:
        if pi.item_id == item_id:
            po_item = pi
            break
    
    if not po_item:
        flash('Item not found in this purchase order.', 'error')
        return redirect(url_for('grn.dashboard'))
    
    form = QuickReceivePOForm()
    form.purchase_order_id.data = purchase_order_id
    form.item_id.data = item_id
    

    if form.validate_on_submit():
        try:
            # Create GRN automatically
            grn = GRN()
            grn.grn_number = GRN.generate_grn_number()
            grn.purchase_order_id = purchase_order_id
            grn.received_date = form.received_date.data
            grn.received_by = current_user.id
            grn.delivery_note = form.delivery_note.data
            grn.inspection_required = True
            grn.status = 'received'
            grn.remarks = form.remarks.data
            db.session.add(grn)
            db.session.flush()  # To get the GRN ID
            
            # Auto-calculate passed quantity
            quantity_passed = form.quantity_received.data - (form.quantity_rejected.data or 0)
            
            # Determine inspection status based on add_to_inventory checkbox
            if form.add_to_inventory.data:
                inspection_status = 'passed'  # Force passed when adding to inventory
            else:
                inspection_status = form.inspection_status.data or 'pending'
            
            # Create line item with automatic rate population from PO
            line_item = GRNLineItem()
            line_item.grn_id = grn.id
            line_item.item_id = item_id
            line_item.quantity_received = form.quantity_received.data
            line_item.quantity_passed = quantity_passed
            line_item.quantity_rejected = form.quantity_rejected.data or 0
            line_item.unit_of_measure = po_item.uom or item.unit_of_measure
            line_item.inspection_status = inspection_status
            line_item.rejection_reason = form.rejection_reason.data
            line_item.material_classification = 'raw_material'
            line_item.remarks = form.remarks.data
            
            # ✅ AUTO-POPULATE RATE FROM PURCHASE ORDER
            line_item.rate_per_unit = float(po_item.rate or 0)
            line_item.total_value = line_item.quantity_received * line_item.rate_per_unit
            
            db.session.add(line_item)
            
            # Set the add_to_inventory flag and inspection status BEFORE batch processing
            grn.add_to_inventory = form.add_to_inventory.data
            if form.add_to_inventory.data:
                grn.inspection_status = 'passed'  # Force passed when adding to inventory
            else:
                grn.inspection_status = form.inspection_status.data or 'pending'
            
            # Commit the GRN changes before batch processing
            db.session.commit()
            
            # Handle document uploads
            uploaded_documents = []
            if hasattr(form, 'supporting_documents') and form.supporting_documents.data:
                try:
                    # Process uploaded documents
                    doc_manager = DocumentUploadManager('grn')
                    uploaded_files = doc_manager.process_form_files(form)
                    
                    for file_info in uploaded_files:
                        if file_info.get('success'):
                            document = create_document_record(
                                file_info=file_info,
                                module_name='grn',
                                reference_type='grn',
                                reference_id=grn.id,
                                document_type='supporting_document',
                                description=form.document_description.data if hasattr(form, 'document_description') else None,
                                user_id=current_user.id
                            )
                            if document:
                                uploaded_documents.append(document)
                except Exception as e:
                    print(f"Error processing documents: {e}")
            
            # ✅ AUTO-CREATE WORKFLOW STATUS FOR TRACKING
            from models.grn import GRNWorkflowStatus
            workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first()
            if not workflow_status:
                workflow_status = GRNWorkflowStatus(
                    grn_id=grn.id,
                    material_received=True,
                    material_received_date=grn.received_date,
                    invoice_received=False,
                    payment_made=False
                )
                db.session.add(workflow_status)
                db.session.flush()
            
            # Process GRN with comprehensive batch tracking  
            add_to_inventory = form.add_to_inventory.data if hasattr(form, 'add_to_inventory') else True
            success, message = process_grn_with_batch_tracking(grn, add_to_inventory)
            
            if not success:
                flash(f'Error processing GRN: {message}', 'error')
                return redirect(url_for('grn.dashboard'))
            
            success_message = f'Materials received successfully! GRN {grn.grn_number} created for PO {purchase_order.po_number} with batch tracking.'
            if uploaded_documents:
                success_message += f' {len(uploaded_documents)} document(s) uploaded.'
            
            flash(success_message, 'success')
            return redirect(url_for('grn.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error receiving materials: {str(e)}', 'error')
    
    return render_template('grn/quick_receive_po.html',
                         title='Quick Receive Materials',
                         form=form,
                         purchase_order=purchase_order,
                         item=item,
                         po_item=po_item)


@grn_bp.route('/list')
@login_required
def list_grns():
    """List all GRNs with filtering"""
    form = GRNSearchForm()
    
    # Build query
    query = GRN.query.join(JobWork)
    
    # Apply filters
    if request.args.get('search'):
        search_term = request.args.get('search')
        query = query.filter(
            or_(
                GRN.grn_number.ilike(f'%{search_term}%'),
                JobWork.job_number.ilike(f'%{search_term}%'),
                JobWork.customer_name.ilike(f'%{search_term}%')
            )
        )
    
    if request.args.get('status'):
        query = query.filter(GRN.status == request.args.get('status'))
    
    if request.args.get('inspection_status'):
        query = query.filter(GRN.inspection_status == request.args.get('inspection_status'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    grns = query.order_by(GRN.received_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('grn/list.html',
                         title='All GRNs',
                         grns=grns,
                         form=form)


@grn_bp.route('/detail/<int:grn_id>')
@login_required
def detail(grn_id):
    """View GRN details"""
    grn = GRN.query.get_or_404(grn_id)
    
    return render_template('grn/detail.html',
                         title=f'GRN {grn.grn_number}',
                         grn=grn)


@grn_bp.route('/add_line_items/<int:grn_id>', methods=['GET', 'POST'])
@login_required
def add_line_items(grn_id):
    """Add line items to a GRN"""
    grn = GRN.query.get_or_404(grn_id)
    
    if grn.status == 'completed':
        flash('Cannot modify completed GRN', 'error')
        return redirect(url_for('grn.detail', grn_id=grn_id))
    
    form = GRNLineItemForm()
    form.grn_id.data = grn_id
    if grn.job_work_id and grn.job_work:
        form.item_id.data = grn.job_work.item_id
    
    # Pre-fill form with job work or PO item details
    if grn.job_work_id and grn.job_work and not form.unit_of_measure.data:
        form.unit_of_measure.data = grn.job_work.item.unit_of_measure
    elif grn.purchase_order_id and grn.purchase_order and grn.purchase_order.items:
        # For PO-based GRNs, populate with PO items for selection
        form.item_id.choices = [(item.item.id, f"{item.item.name} ({item.qty} {item.item.unit_of_measure})") 
                               for item in grn.purchase_order.items]
    
    if form.validate_on_submit():
        try:
            line_item = GRNLineItem(
                grn_id=grn_id,
                item_id=form.item_id.data,
                quantity_received=form.quantity_received.data,
                quantity_passed=form.quantity_passed.data,
                quantity_rejected=form.quantity_rejected.data,
                unit_of_measure=form.unit_of_measure.data,
                unit_weight=form.unit_weight.data,
                inspection_status=form.inspection_status.data,
                rejection_reason=form.rejection_reason.data,
                quality_grade=form.quality_grade.data,
                process_name=form.process_name.data,
                process_stage=form.process_stage.data,

                batch_number=form.batch_number.data,
                serial_numbers=form.serial_numbers.data,
                remarks=form.remarks.data
            )
            
            db.session.add(line_item)
            db.session.commit()
            
            flash('Line item added successfully!', 'success')
            return redirect(url_for('grn.detail', grn_id=grn_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding line item: {str(e)}', 'error')
    
    return render_template('grn/add_line_items.html',
                         title='Add Line Items',
                         form=form,
                         grn=grn)


# API Endpoints for AJAX functionality

@grn_bp.route('/api/job_work/<int:job_work_id>/pending_quantity')
@login_required
def api_pending_quantity(job_work_id):
    """API to get pending quantity for a job work"""
    job_work = JobWork.query.get_or_404(job_work_id)
    
    return jsonify({
        'success': True,
        'quantity_sent': job_work.quantity_sent,
        'quantity_received': job_work.quantity_received or 0,
        'pending_quantity': job_work.pending_quantity,
        'completion_percentage': job_work.completion_percentage,
        'unit_of_measure': job_work.item.unit_of_measure
    })


@grn_bp.route('/api/grn/<int:grn_id>/summary')
@login_required
def api_grn_summary(grn_id):
    """API to get GRN summary data"""
    grn = GRN.query.get_or_404(grn_id)
    
    return jsonify({
        'success': True,
        'grn_number': grn.grn_number,
        'total_received': grn.total_quantity_received,
        'total_passed': grn.total_quantity_passed,
        'total_rejected': grn.total_quantity_rejected,
        'acceptance_rate': grn.acceptance_rate,
        'is_fully_inspected': grn.is_fully_inspected,
        'status': grn.status,
        'inspection_status': grn.inspection_status
    })