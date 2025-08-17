"""
Enhanced Batch Tracking Routes
Provides comprehensive batch tracking dashboard and management
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_

from app import db
from models import Item, User
from models.batch import InventoryBatch, BatchMovement, BatchTraceability, BatchMovementLedger
from services.unified_batch_tracking import UnifiedBatchTrackingService
from services.batch_integration_service import BatchIntegrationService
from services.optimized_batch_queries import OptimizedBatchQueries

enhanced_batch_bp = Blueprint('enhanced_batch', __name__, url_prefix='/enhanced-batch')

@enhanced_batch_bp.route('/dashboard')
@login_required
def unified_dashboard():
    """Redirect to the new unified batch tracking dashboard"""
    return redirect(url_for('batch_tracking.dashboard'))

@enhanced_batch_bp.route('/batch/<int:batch_id>/traceability')
@login_required
def batch_traceability(batch_id):
    """Complete traceability view for a specific batch"""
    
    batch = InventoryBatch.query.get_or_404(batch_id)
    traceability_data = UnifiedBatchTrackingService.get_batch_traceability(batch_id)
    
    return render_template('batch_tracking/batch_traceability.html',
                         batch=batch,
                         traceability=traceability_data)

@enhanced_batch_bp.route('/item/<int:item_id>/batches')
@login_required  
def item_batch_overview(item_id):
    """Overview of all batches for a specific item"""
    
    item = Item.query.get_or_404(item_id)
    batch_data = BatchIntegrationService.get_batch_availability_for_item(item_id)
    
    # Get batch movements for this item
    movements = BatchMovement.query.filter_by(item_id=item_id).order_by(
        desc(BatchMovement.timestamp)
    ).limit(50).all()
    
    return render_template('batch_tracking/item_batch_overview.html',
                         item=item,
                         batch_data=batch_data,
                         movements=movements)

@enhanced_batch_bp.route('/batch/<int:batch_id>/inspect', methods=['POST'])
@login_required
def approve_batch_inspection(batch_id):
    """Approve or reject batch inspection"""
    
    try:
        approved_qty = float(request.form.get('approved_qty', 0))
        rejected_qty = float(request.form.get('rejected_qty', 0))
        notes = request.form.get('notes', '')
        
        success = UnifiedBatchTrackingService.approve_inspection(
            batch_id, approved_qty, rejected_qty, current_user.id
        )
        
        if success:
            flash(f'Inspection completed: {approved_qty} approved, {rejected_qty} rejected', 'success')
        else:
            flash('Failed to complete inspection', 'error')
    
    except ValueError:
        flash('Invalid quantity values', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('enhanced_batch.batch_traceability', batch_id=batch_id))

@enhanced_batch_bp.route('/batch/<int:batch_id>/transfer', methods=['POST'])
@login_required
def transfer_batch_location(batch_id):
    """Transfer batch to different location"""
    
    try:
        to_location = request.form.get('to_location')
        transfer_qty = request.form.get('transfer_qty')
        
        if not to_location:
            flash('Destination location is required', 'error')
            return redirect(url_for('enhanced_batch.batch_traceability', batch_id=batch_id))
        
        batch = InventoryBatch.query.get_or_404(batch_id)
        from_location = batch.location
        
        if transfer_qty:
            transfer_qty = float(transfer_qty)
        else:
            transfer_qty = batch.total_quantity
        
        success = BatchIntegrationService.transfer_batch_between_locations(
            batch_id, from_location, to_location, transfer_qty, current_user.id
        )
        
        if success:
            flash(f'Batch transferred from {from_location} to {to_location}', 'success')
        else:
            flash('Failed to transfer batch', 'error')
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('enhanced_batch.batch_traceability', batch_id=batch_id))

@enhanced_batch_bp.route('/reports/consumption')
@login_required
def consumption_report():
    """Batch consumption report with efficiency metrics"""
    
    # Get date range
    date_from = request.args.get('date_from', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))
    
    try:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
    except:
        date_from_obj = date.today() - timedelta(days=30)
        date_to_obj = date.today()
    
    report_data = BatchIntegrationService.generate_batch_consumption_report(
        date_from_obj, date_to_obj
    )
    
    return render_template('batch_tracking/consumption_report.html',
                         report=report_data,
                         date_from=date_from,
                         date_to=date_to)

@enhanced_batch_bp.route('/api/batch-search')
@login_required
def api_batch_search():
    """API endpoint for batch search with autocomplete"""
    
    query = request.args.get('q', '').strip()
    item_id = request.args.get('item_id', type=int)
    state = request.args.get('state', 'all')
    
    batch_query = InventoryBatch.query
    
    if query:
        batch_query = batch_query.filter(
            or_(
                InventoryBatch.batch_code.ilike(f'%{query}%'),
                InventoryBatch.supplier_batch_no.ilike(f'%{query}%')
            )
        )
    
    if item_id:
        batch_query = batch_query.filter(InventoryBatch.item_id == item_id)
    
    if state != 'all':
        if state == 'available':
            batch_query = batch_query.filter(
                (InventoryBatch.qty_raw > 0) |
                (InventoryBatch.qty_finished > 0)
            )
        elif state in ['raw', 'wip', 'finished', 'scrap']:
            qty_field = getattr(InventoryBatch, f'qty_{state}', None)
            if qty_field:
                batch_query = batch_query.filter(qty_field > 0)
    
    batches = batch_query.limit(20).all()
    
    return jsonify([
        {
            'id': batch.id,
            'batch_code': batch.batch_code,
            'item_name': batch.item.name if batch.item else 'Unknown',
            'qty_raw': batch.qty_raw or 0,
            'qty_wip': batch.qty_wip or 0,
            'qty_finished': batch.qty_finished or 0,
            'total_available': batch.available_quantity,
            'location': batch.location,
            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
            'is_expired': batch.is_expired
        } for batch in batches
    ])

@enhanced_batch_bp.route('/api/item/<int:item_id>/batch-availability')
@login_required
def api_item_batch_availability(item_id):
    """API endpoint for getting item batch availability"""
    
    batch_data = BatchIntegrationService.get_batch_availability_for_item(item_id)
    
    return jsonify(batch_data)

@enhanced_batch_bp.route('/batch/consolidate', methods=['POST'])
@login_required
def consolidate_batches():
    """Consolidate multiple batches into one"""
    
    try:
        target_batch_id_str = request.form.get('target_batch_id')
        source_batch_ids_str = request.form.getlist('source_batch_ids')
        
        if not target_batch_id_str or not source_batch_ids_str:
            flash('Target batch and source batches are required', 'error')
            return redirect(url_for('enhanced_batch.unified_dashboard'))
        
        target_batch_id = int(target_batch_id_str)
        source_batch_ids = [int(bid) for bid in source_batch_ids_str if bid.isdigit()]
        
        success = UnifiedBatchTrackingService.consolidate_batches(
            source_batch_ids, target_batch_id, current_user.id
        )
        
        if success:
            flash(f'Successfully consolidated {len(source_batch_ids)} batches', 'success')
        else:
            flash('Failed to consolidate batches', 'error')
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('enhanced_batch.unified_dashboard'))

@enhanced_batch_bp.route('/movements/live')
@login_required
def live_movements():
    """Live view of batch movements"""
    
    # Get movements from the last hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    
    live_movements = BatchMovement.query.filter(
        BatchMovement.timestamp >= one_hour_ago
    ).order_by(desc(BatchMovement.timestamp)).limit(50).all()
    
    return render_template('batch_tracking/live_movements.html',
                         movements=live_movements)

@enhanced_batch_bp.route('/quality/pending-inspection')
@login_required
def pending_inspection():
    """View of all batches pending quality inspection"""
    
    pending_batches = InventoryBatch.query.filter(
        InventoryBatch.qty_inspection > 0,
        InventoryBatch.inspection_status == 'pending'
    ).order_by(InventoryBatch.created_at).all()
    
    return render_template('batch_tracking/pending_inspection.html',
                         batches=pending_batches)