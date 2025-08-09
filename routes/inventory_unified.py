"""
Unified Inventory Routes
Implements the clean parent-child architecture per user requirements
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from services.unified_inventory import UnifiedInventoryService
from models import Item
from app import db

inventory_unified_bp = Blueprint('inventory_unified', __name__)

@inventory_unified_bp.route('/api/batch-tracking-data')
@login_required
def api_batch_tracking_data():
    """API endpoint for batch tracking data per user requirements"""
    try:
        batch_data = UnifiedInventoryService.get_batch_tracking_view()
        return jsonify({
            'success': True,
            'data': batch_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/api/movement-history')
@login_required
def api_movement_history():
    """API endpoint for movement transaction history"""
    batch_id = request.args.get('batch_id', type=int)
    item_id = request.args.get('item_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    
    try:
        movements = UnifiedInventoryService.get_movement_history(
            batch_id=batch_id, 
            item_id=item_id, 
            limit=limit
        )
        return jsonify({
            'success': True,
            'movements': movements
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/api/available-batches/<int:item_id>')
@login_required
def api_available_batches(item_id):
    """Get available batches for material issue"""
    required_qty = request.args.get('required_qty', 0, type=float)
    from_state = request.args.get('from_state', 'raw')
    
    try:
        batches, sufficient = UnifiedInventoryService.get_available_batches_for_issue(
            item_id, required_qty, from_state
        )
        return jsonify({
            'success': True,
            'batches': batches,
            'sufficient_quantity': sufficient,
            'total_available': sum(b['available_qty'] for b in batches)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/api/create-batch', methods=['POST'])
@login_required
def api_create_batch():
    """Create new batch with proper naming convention"""
    data = request.get_json()
    
    required_fields = ['item_id', 'quantity']
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'error': 'Missing required fields: item_id, quantity'
        }), 400
    
    try:
        batch = UnifiedInventoryService.create_batch(
            item_id=data['item_id'],
            quantity=data['quantity'],
            source_type=data.get('source_type', 'manual'),
            source_ref_id=data.get('source_ref_id'),
            supplier_batch_no=data.get('supplier_batch_no'),
            purchase_rate=data.get('purchase_rate', 0.0),
            location=data.get('location', 'Raw Store')
        )
        
        if batch:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Batch {batch.batch_code} created successfully',
                'batch_id': batch.id,
                'batch_code': batch.batch_code
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create batch'
            }), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/api/move-batch-quantity', methods=['POST'])
@login_required
def api_move_batch_quantity():
    """Move quantity between states with proper logging"""
    data = request.get_json()
    
    required_fields = ['batch_id', 'quantity', 'from_state', 'to_state']
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'error': 'Missing required fields: batch_id, quantity, from_state, to_state'
        }), 400
    
    try:
        success, message = UnifiedInventoryService.move_batch_quantity(
            batch_id=data['batch_id'],
            quantity=data['quantity'],
            from_state=data['from_state'],
            to_state=data['to_state'],
            ref_type=data.get('ref_type'),
            ref_id=data.get('ref_id'),
            notes=data.get('notes')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/dashboard-data')
@login_required
def dashboard_data():
    """Get unified dashboard statistics"""
    try:
        stats = UnifiedInventoryService.get_inventory_dashboard_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_unified_bp.route('/batch-tracking-table')
@login_required
def batch_tracking_table():
    """Render batch tracking table per user requirements"""
    try:
        batch_data = UnifiedInventoryService.get_batch_tracking_view()
        return render_template('inventory/batch_tracking_table.html', 
                             batch_data=batch_data)
    except Exception as e:
        flash(f'Error loading batch tracking data: {str(e)}', 'error')
        return redirect(url_for('inventory.dashboard'))