"""
Comprehensive Batch Tracking Dashboard and Management Routes
Provides complete visibility into batch movements, states, and traceability
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models import Item, JobWork
from models.batch import InventoryBatch, BatchMovement
from utils.batch_tracking import BatchTracker, BatchValidator
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta

batch_tracking_bp = Blueprint('batch_tracking', __name__)

@batch_tracking_bp.route('/reset_batch_data')
@login_required
def reset_batch_data():
    """Reset batch data - create sample batches for testing"""
    try:
        from datetime import date
        
        # Clear existing batches
        InventoryBatch.query.delete()
        
        # Get first available item
        item = Item.query.first()
        if not item:
            flash('No items found. Please create items first.', 'error')
            return redirect(url_for('batch_tracking.dashboard'))
        
        # Create sample batches
        batch1 = InventoryBatch(
            item_id=item.id,
            batch_code='B25001-RESET',
            qty_raw=100.0,
            qty_finished=0.0,
            qty_scrap=5.0,
            location='MAIN-STORE',
            inspection_status='passed'
        )
        
        batch2 = InventoryBatch(
            item_id=item.id,
            batch_code='B25002-RESET',
            qty_raw=0.0,
            qty_finished=50.0,
            qty_scrap=2.0,
            location='FINISHED-GOODS',
            inspection_status='passed'
        )
        
        db.session.add(batch1)
        db.session.add(batch2)
        db.session.commit()
        
        flash('Batch data has been reset with sample data.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting batch data: {str(e)}', 'error')
    
    return redirect(url_for('batch_tracking.dashboard'))

@batch_tracking_bp.route('/dashboard')
@login_required
def dashboard():
    """Comprehensive batch tracking dashboard"""
    
    # Get filter parameters
    item_filter = request.args.get('item_id', type=int)
    state_filter = request.args.get('state', '')
    location_filter = request.args.get('location', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build base query - use outerjoin to handle missing items
    query = InventoryBatch.query.outerjoin(Item)
    
    # Apply filters
    if item_filter:
        query = query.filter(InventoryBatch.item_id == item_filter)
    
    if state_filter:
        if state_filter == 'raw':
            query = query.filter(InventoryBatch.qty_raw > 0)
        elif state_filter == 'finished':
            query = query.filter(InventoryBatch.qty_finished > 0)
        elif state_filter == 'scrap':
            query = query.filter(InventoryBatch.qty_scrap > 0)
        elif state_filter == 'inspection':
            query = query.filter(InventoryBatch.qty_inspection > 0)
        elif state_filter == 'wip':
            query = query.filter(InventoryBatch.qty_wip > 0)
    
    if location_filter:
        query = query.filter(InventoryBatch.location.ilike(f'%{location_filter}%'))
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(InventoryBatch.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(InventoryBatch.created_at <= to_date)
        except ValueError:
            pass
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    batches = query.order_by(desc(InventoryBatch.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate dashboard statistics
    stats = {
        'total_batches': InventoryBatch.query.count(),
        'active_batches': InventoryBatch.query.filter(
            or_(
                InventoryBatch.qty_raw > 0,
                InventoryBatch.qty_wip > 0,
                InventoryBatch.qty_finished > 0,
                InventoryBatch.qty_inspection > 0
            )
        ).count(),
        'expired_batches': InventoryBatch.query.filter(
            InventoryBatch.expiry_date < datetime.now().date()
        ).count() if InventoryBatch.query.filter(InventoryBatch.expiry_date != None).count() > 0 else 0,
        'pending_inspection': InventoryBatch.query.filter(
            InventoryBatch.qty_inspection > 0
        ).count(),
        'total_raw_quantity': db.session.query(func.sum(InventoryBatch.qty_raw)).scalar() or 0,
        'total_wip_quantity': db.session.query(func.sum(InventoryBatch.qty_wip)).scalar() or 0,
        'total_finished_quantity': db.session.query(func.sum(InventoryBatch.qty_finished)).scalar() or 0
    }
    
    # Get process-wise inventory summary
    process_summary = BatchTracker.get_process_wise_inventory_summary()
    
    # Get items for filter dropdown
    items = Item.query.join(InventoryBatch).order_by(Item.name).distinct().all()
    
    # Get unique storage locations
    storage_locations = db.session.query(InventoryBatch.location).distinct().all()
    locations = [loc[0] for loc in storage_locations if loc[0]]
    
    return render_template(
        'batch_tracking/dashboard.html',
        batches=batches,
        stats=stats,
        process_summary=process_summary,
        items=items,
        locations=locations,
        current_filters={
            'item_id': item_filter,
            'state': state_filter,
            'location': location_filter,
            'date_from': date_from,
            'date_to': date_to
        }
    )

@batch_tracking_bp.route('/batch/<int:batch_id>')
@login_required
def batch_detail(batch_id):
    """Detailed view of a specific batch with complete traceability"""
    batch = InventoryBatch.query.get_or_404(batch_id)
    
    # Simple traceability data for now
    traceability_data = {
        'batch': batch,
        'movements': batch.movements if hasattr(batch, 'movements') else [],
        'total_quantity': batch.total_quantity,
        'available_quantity': batch.available_quantity
    }
    
    # Get related job work batches (if the model exists)
    job_work_batches = []
    
    return render_template(
        'batch_tracking/batch_detail.html',
        batch=batch,
        traceability_data=traceability_data,
        job_work_batches=job_work_batches
    )

@batch_tracking_bp.route('/process-view')
@login_required
def process_view():
    """Process-wise view of inventory with batch tracking"""
    
    # Get process summary
    process_summary = BatchTracker.get_process_wise_inventory_summary()
    
    # Get process filter
    process_filter = request.args.get('process', '')
    
    if process_filter:
        # Filter batches by process state
        if process_filter == 'raw':
            batches = InventoryBatch.query.filter(InventoryBatch.qty_raw > 0).all()
        elif process_filter == 'finished':
            batches = InventoryBatch.query.filter(InventoryBatch.qty_finished > 0).all()
        elif process_filter == 'wip':
            batches = InventoryBatch.query.filter(InventoryBatch.qty_wip > 0).all()
        elif process_filter == 'inspection':
            batches = InventoryBatch.query.filter(InventoryBatch.qty_inspection > 0).all()
        else:
            batches = []
    else:
        batches = []
    
    processes = ['cutting', 'bending', 'welding', 'zinc', 'painting', 'assembly', 'machining', 'polishing']
    
    return render_template(
        'batch_tracking/process_view.html',
        process_summary=process_summary,
        batches=batches,
        processes=processes,
        current_process=process_filter
    )

@batch_tracking_bp.route('/traceability')
@login_required
def traceability_report():
    """Comprehensive traceability reports"""
    
    report_type = request.args.get('type', 'batch')
    
    if report_type == 'batch':
        # Batch-wise traceability
        batch_id = request.args.get('batch_id', type=int)
        if batch_id:
            batch = InventoryBatch.query.get_or_404(batch_id)
            # Get movement history from BatchMovementLedger
            from models.batch_movement import BatchMovementLedger
            movements = BatchMovementLedger.query.filter_by(batch_id=batch_id).order_by(
                BatchMovementLedger.movement_date.desc(),
                BatchMovementLedger.created_at.desc()
            ).all()
            
            traceability_data = {
                'batch': batch,
                'movements': movements,
                'total_quantity': batch.total_quantity,
                'available_quantity': batch.available_quantity
            }
            return render_template(
                'batch_tracking/traceability_batch.html',
                traceability_data=traceability_data,
                batch_id=batch_id
            )
    
    elif report_type == 'item':
        # Item-wise traceability
        item_id = request.args.get('item_id', type=int)
        if item_id:
            item = Item.query.get_or_404(item_id)
            batches = InventoryBatch.query.filter_by(item_id=item_id).order_by(
                desc(InventoryBatch.created_at)
            ).all()
            
            return render_template(
                'batch_tracking/traceability_item.html',
                item=item,
                batches=batches
            )
    
    # Default: Show traceability options
    items = Item.query.join(InventoryBatch).order_by(Item.name).all()
    recent_batches = InventoryBatch.query.order_by(desc(InventoryBatch.created_at)).limit(20).all()
    
    return render_template(
        'batch_tracking/traceability_options.html',
        items=items,
        recent_batches=recent_batches
    )

@batch_tracking_bp.route('/movements')
@login_required
def batch_movements():
    """Track batch movements across processes"""
    
    # Get recent batch movements from JobWorkBatch
    movements = db.session.query(JobWorkBatch).join(JobWork).order_by(
        desc(JobWorkBatch.created_at)
    ).limit(50).all()
    
    # Group movements by date
    movements_by_date = {}
    for movement in movements:
        date_key = movement.created_at.date()
        if date_key not in movements_by_date:
            movements_by_date[date_key] = []
        movements_by_date[date_key].append(movement)
    
    return render_template(
        'batch_tracking/batch_movements.html',
        movements=movements
    )

@batch_tracking_bp.route('/quality-control')
@login_required
def quality_control():
    """Quality control dashboard for batch tracking"""
    
    # Get filter from request
    status_filter = request.args.get('status')
    
    # Get batches based on filter
    if status_filter:
        batches = InventoryBatch.query.filter(
            InventoryBatch.inspection_status == status_filter
        ).order_by(desc(InventoryBatch.created_at)).all()
    else:
        batches = InventoryBatch.query.order_by(desc(InventoryBatch.created_at)).limit(50).all()
    
    # Calculate quality statistics
    total_batches = InventoryBatch.query.count()
    pending_count = InventoryBatch.query.filter(InventoryBatch.inspection_status == 'pending').count()
    approved_count = InventoryBatch.query.filter(InventoryBatch.inspection_status == 'passed').count()
    rejected_count = InventoryBatch.query.filter(InventoryBatch.inspection_status == 'failed').count()
    
    approval_rate = (approved_count / total_batches * 100) if total_batches > 0 else 0
    
    quality_stats = {
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'approval_rate': round(approval_rate, 1)
    }
    
    return render_template(
        'batch_tracking/quality_control.html',
        batches=batches,
        quality_stats=quality_stats
    )

# API Endpoints for Batch Tracking Dashboard

@batch_tracking_bp.route('/api/batch/<int:batch_id>/update-quality', methods=['POST'])
@login_required
def api_update_batch_quality(batch_id):
    """Update batch quality status"""
    try:
        print(f"API called for batch_id: {batch_id}")
        batch = InventoryBatch.query.get_or_404(batch_id)
        
        # Accept both JSON and FormData
        if request.is_json:
            data = request.json
            print(f"Request JSON data: {data}")
        else:
            data = request.form.to_dict()
            print(f"Request Form data: {data}")
        
        # Accept both quality_status and inspection_status keys
        new_status = data.get('quality_status') or data.get('inspection_status')
        quality_notes = data.get('quality_notes', '')
        
        print(f"Received status: {new_status}")
        
        # Map quality status values
        status_mapping = {
            'approved': 'passed',
            'rejected': 'failed', 
            'pending': 'pending',
            'on_hold': 'quarantine',
            'defective': 'failed',  # Add defective mapping
            'passed': 'passed',
            'failed': 'failed'
        }
        
        if new_status in status_mapping:
            new_status = status_mapping[new_status]
        
        print(f"Final mapped status: {new_status}")
        
        # Ensure we have a valid status
        if not new_status or new_status not in ['passed', 'failed', 'pending', 'quarantine']:
            print(f"Invalid status: {new_status}")
            return jsonify({'success': False, 'error': f'Invalid inspection status: {new_status}. Valid options: passed, failed, pending, quarantine'}), 400
        
        batch.inspection_status = new_status
        batch.updated_at = datetime.utcnow()
        
        # Automatic quantity movement for approved batches
        if new_status == 'passed' and batch.qty_inspection > 0:
            qty_to_move = batch.qty_inspection
            batch.qty_inspection = 0.0
            batch.qty_raw += qty_to_move
            print(f"Auto-moved {qty_to_move} units from inspection to raw for approved batch {batch.batch_code}")
        
        print(f"About to commit status change to: {new_status}")
        db.session.commit()
        print(f"Successfully committed status change")
        
        response_data = {
            'success': True,
            'message': f'Batch {batch.batch_code} inspection status updated to {new_status}',
            'new_status': new_status,
            'batch_id': batch_id
        }
        print(f"Sending response: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Exception in api_update_batch_quality: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_tracking_bp.route('/batch/<int:batch_id>/update-quality-direct', methods=['POST'])
@login_required
def update_batch_quality_direct(batch_id):
    """Direct form-based quality status update (non-AJAX)"""
    try:
        batch = InventoryBatch.query.get_or_404(batch_id)
        
        new_status = request.form.get('quality_status')
        quality_notes = request.form.get('quality_notes', '')
        
        print(f"Direct update - Batch: {batch_id}, Status: {new_status}")
        
        if new_status not in ['passed', 'failed', 'pending', 'quarantine']:
            flash(f'Invalid quality status: {new_status}', 'error')
            return redirect(url_for('batch_tracking.batch_detail', batch_id=batch_id))
        
        # Update batch
        batch.inspection_status = new_status
        batch.updated_at = datetime.utcnow()
        
        # Automatic quantity movement for approved batches
        if new_status == 'passed' and batch.qty_inspection > 0:
            qty_to_move = batch.qty_inspection
            batch.qty_inspection = 0.0
            batch.qty_raw += qty_to_move
            print(f"Auto-moved {qty_to_move} units from inspection to raw for approved batch {batch.batch_code}")
        
        db.session.commit()
        
        status_names = {
            'passed': 'Approved',
            'failed': 'Rejected', 
            'pending': 'Pending',
            'quarantine': 'On Hold'
        }
        
        flash(f'Batch {batch.batch_code} quality status updated to {status_names.get(new_status, new_status)}', 'success')
        return redirect(url_for('batch_tracking.batch_detail', batch_id=batch_id))
        
    except Exception as e:
        print(f"Exception in update_batch_quality_direct: {str(e)}")
        db.session.rollback()
        flash(f'Error updating quality status: {str(e)}', 'error')
        return redirect(url_for('batch_tracking.batch_detail', batch_id=batch_id))

@batch_tracking_bp.route('/quality-dashboard')
@login_required 
def quality_dashboard():
    """Quality control dashboard showing batch inspection statistics"""
    # Quality statistics from batch inspections
    total_batches = InventoryBatch.query.count()
    pending_batches = InventoryBatch.query.filter_by(inspection_status='pending').count()
    approved_batches = InventoryBatch.query.filter_by(inspection_status='passed').count()
    rejected_batches = InventoryBatch.query.filter_by(inspection_status='failed').count()
    quarantine_batches = InventoryBatch.query.filter_by(inspection_status='quarantine').count()
    
    # Calculate approval rate
    approval_rate = 0
    if total_batches > 0:
        approval_rate = (approved_batches / total_batches) * 100
    
    stats = {
        'total_batches': total_batches,
        'pending_review': pending_batches,
        'approved': approved_batches,
        'rejected': rejected_batches,
        'approval_rate': approval_rate
    }
    
    # Recent batch inspections with filters
    status_filter = request.args.get('status', 'all')
    query = InventoryBatch.query
    
    if status_filter == 'pending':
        query = query.filter_by(inspection_status='pending')
    elif status_filter == 'approved':
        query = query.filter_by(inspection_status='passed')  
    elif status_filter == 'rejected':
        query = query.filter_by(inspection_status='failed')
    
    batches = query.order_by(desc(InventoryBatch.updated_at)).all()
    
    return render_template('batch_tracking/quality_control.html',
                         stats=stats,
                         batches=batches,
                         status_filter=status_filter,
                         title='Quality Control Dashboard')

@batch_tracking_bp.route('/api/batch/<int:batch_id>/update-location', methods=['POST'])
@login_required
def api_update_batch_location(batch_id):
    """Update batch storage location"""
    try:
        batch = InventoryBatch.query.get_or_404(batch_id)
        data = request.json
        
        new_location = data.get('location', '').strip()
        if not new_location:
            return jsonify({'success': False, 'error': 'Location is required'}), 400
        
        old_location = batch.location
        batch.location = new_location
        batch.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Batch {batch.batch_code} moved from {old_location} to {new_location}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_tracking_bp.route('/api/batch-summary')
@login_required
def api_batch_summary():
    """Get batch summary statistics for dashboard widgets"""
    try:
        summary = {
            'total_batches': InventoryBatch.query.count(),
            'active_batches': InventoryBatch.query.filter(
                or_(
                    InventoryBatch.qty_raw > 0,
                    InventoryBatch.qty_wip > 0,
                    InventoryBatch.qty_finished > 0,
                    InventoryBatch.qty_inspection > 0
                )
            ).count(),
            'quality_issues': InventoryBatch.query.filter(InventoryBatch.inspection_status == 'failed').count(),
            'pending_inspection': InventoryBatch.query.filter(InventoryBatch.inspection_status == 'pending').count(),
            'process_breakdown': {}
        }
        
        # Add quantities by state
        summary['process_breakdown']['inspection'] = float(db.session.query(func.sum(InventoryBatch.qty_inspection)).scalar() or 0)
        summary['process_breakdown']['raw'] = float(db.session.query(func.sum(InventoryBatch.qty_raw)).scalar() or 0)
        summary['process_breakdown']['wip'] = float(db.session.query(func.sum(InventoryBatch.qty_wip)).scalar() or 0)
        summary['process_breakdown']['finished'] = float(db.session.query(func.sum(InventoryBatch.qty_finished)).scalar() or 0)
        summary['process_breakdown']['scrap'] = float(db.session.query(func.sum(InventoryBatch.qty_scrap)).scalar() or 0)
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@batch_tracking_bp.route('/api/search-batches')
@login_required
def api_search_batches():
    """Search batches by various criteria"""
    try:
        query_text = request.args.get('q', '').strip()
        limit = request.args.get('limit', 20, type=int)
        
        if not query_text:
            return jsonify({'batches': []})
        
        # Search in batch code, item name, and supplier batch
        batches = InventoryBatch.query.join(Item).filter(
            or_(
                InventoryBatch.batch_code.ilike(f'%{query_text}%'),
                Item.name.ilike(f'%{query_text}%'),
                Item.code.ilike(f'%{query_text}%'),
                InventoryBatch.supplier_batch_no.ilike(f'%{query_text}%')
            )
        ).limit(limit).all()
        
        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': batch.id,
                'batch_code': batch.batch_code,
                'item_name': batch.item.name if batch.item else 'Unknown',
                'item_code': batch.item.code if batch.item else 'N/A',
                'total_quantity': batch.total_quantity,
                'available_quantity': batch.available_quantity,
                'inspection_status': batch.inspection_status,
                'location': batch.location,
                'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else None
            })
        
        return jsonify({'batches': batch_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500