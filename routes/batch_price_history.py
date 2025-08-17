"""
Batch-wise Price History Routes
Provides comprehensive batch price tracking and history
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_

from app import db
from models import Item, User
from models.batch import InventoryBatch, BatchPriceHistory, BatchMovement

batch_price_bp = Blueprint('batch_price', __name__, url_prefix='/batch-price')

@batch_price_bp.route('/history')
@login_required
def batch_price_history():
    """Show batch-wise price history with filtering"""
    
    # Get filter parameters
    item_id = request.args.get('item_id', type=int)
    batch_id = request.args.get('batch_id', type=int)
    price_type = request.args.get('price_type', '')
    days = request.args.get('days', 30, type=int)
    
    # Calculate date filter
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    # Base query for batch price history
    query = BatchPriceHistory.query.filter(
        BatchPriceHistory.effective_date >= cutoff_date
    ).join(InventoryBatch).join(Item).order_by(BatchPriceHistory.effective_date.desc())
    
    # Apply filters
    if item_id:
        query = query.filter(BatchPriceHistory.item_id == item_id)
    if batch_id:
        query = query.filter(BatchPriceHistory.batch_id == batch_id)
    if price_type:
        query = query.filter(BatchPriceHistory.price_type == price_type)
    
    price_history_records = query.limit(100).all()  # Limit for performance
    
    # Calculate statistics
    stats = {
        'total_updates': len(price_history_records),
        'batches_with_changes': len(set(record.batch_id for record in price_history_records)),
        'from_grns': len([r for r in price_history_records if r.source == 'grn_creation']),
        'manual_updates': len([r for r in price_history_records if r.source == 'manual_update']),
        'market_adjustments': len([r for r in price_history_records if r.source == 'market_adjustment'])
    }
    
    # Get filter options
    items = Item.query.order_by(Item.name).all()
    batches = InventoryBatch.query.join(Item).order_by(Item.name, InventoryBatch.batch_code).all()
    price_types = ['purchase', 'standard', 'actual', 'market']
    
    return render_template('inventory/batch_price_history.html',
                         title='Batch Price History',
                         price_history=price_history_records,
                         stats=stats,
                         items=items,
                         batches=batches,
                         price_types=price_types)

@batch_price_bp.route('/batch/<int:batch_id>/price-details')
@login_required
def batch_price_details(batch_id):
    """Show detailed price information for a specific batch"""
    
    batch = InventoryBatch.query.get_or_404(batch_id)
    
    # Get complete price history for this batch
    price_history = BatchPriceHistory.query.filter_by(batch_id=batch_id).order_by(
        BatchPriceHistory.effective_date.desc()
    ).all()
    
    # Group by price type for better display
    price_by_type = {}
    for record in price_history:
        if record.price_type not in price_by_type:
            price_by_type[record.price_type] = []
        price_by_type[record.price_type].append(record)
    
    # Calculate current valuations
    current_valuation = {
        'purchase_value': batch.total_quantity * (batch.purchase_rate or 0),
        'standard_value': batch.total_quantity * (batch.standard_cost or 0),
        'actual_value': batch.total_quantity * (batch.actual_cost or 0)
    }
    
    return render_template('inventory/batch_price_details.html',
                         title=f'Batch Price Details - {batch.batch_code}',
                         batch=batch,
                         price_history=price_history,
                         price_by_type=price_by_type,
                         current_valuation=current_valuation)

@batch_price_bp.route('/update-price', methods=['POST'])
@login_required
def update_batch_price():
    """Update price for a specific batch"""
    
    try:
        batch_id = request.form.get('batch_id', type=int)
        price_type = request.form.get('price_type')
        new_price = request.form.get('new_price', type=float)
        notes = request.form.get('notes', '')
        
        if not all([batch_id, price_type, new_price is not None]):
            flash('Missing required fields', 'error')
            return redirect(request.referrer or url_for('batch_price.batch_price_history'))
        
        batch = InventoryBatch.query.get_or_404(batch_id)
        
        # Create price history record
        BatchPriceHistory.create_price_update(
            batch=batch,
            price_type=price_type,
            new_price=new_price,
            source='manual_update',
            notes=notes,
            user_id=current_user.id
        )
        
        db.session.commit()
        flash(f'Price updated successfully for batch {batch.batch_code}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating price: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('batch_price.batch_price_history'))

@batch_price_bp.route('/api/batch-price-chart/<int:batch_id>')
@login_required
def batch_price_chart_data(batch_id):
    """API endpoint for batch price chart data"""
    
    # Get price history for chart
    price_history = BatchPriceHistory.query.filter_by(batch_id=batch_id).order_by(
        BatchPriceHistory.effective_date.asc()
    ).all()
    
    # Format data for chart
    chart_data = {
        'labels': [],
        'datasets': {}
    }
    
    # Group by price type
    for record in price_history:
        date_str = record.effective_date.strftime('%Y-%m-%d')
        if date_str not in chart_data['labels']:
            chart_data['labels'].append(date_str)
        
        if record.price_type not in chart_data['datasets']:
            chart_data['datasets'][record.price_type] = {
                'label': record.price_type.title(),
                'data': [],
                'borderColor': {
                    'purchase': 'rgb(75, 192, 192)',
                    'standard': 'rgb(255, 99, 132)',
                    'actual': 'rgb(54, 162, 235)',
                    'market': 'rgb(255, 206, 86)'
                }.get(record.price_type, 'rgb(153, 102, 255)'),
                'tension': 0.1
            }
        
        chart_data['datasets'][record.price_type]['data'].append({
            'x': date_str,
            'y': float(record.new_price)
        })
    
    return jsonify(chart_data)

@batch_price_bp.route('/api/price-comparison')
@login_required
def price_comparison_api():
    """API for comparing prices across batches of same item"""
    
    item_id = request.args.get('item_id', type=int)
    if not item_id:
        return jsonify({'error': 'Item ID required'}), 400
    
    # Get all batches for this item with current prices
    batches = InventoryBatch.query.filter_by(item_id=item_id).all()
    
    comparison_data = []
    for batch in batches:
        # Get latest price for each type
        latest_prices = {}
        for price_type in ['purchase', 'standard', 'actual']:
            latest_record = BatchPriceHistory.query.filter_by(
                batch_id=batch.id,
                price_type=price_type
            ).order_by(BatchPriceHistory.effective_date.desc()).first()
            
            latest_prices[price_type] = latest_record.new_price if latest_record else 0
        
        comparison_data.append({
            'batch_code': batch.batch_code,
            'total_quantity': batch.total_quantity,
            'purchase_rate': latest_prices['purchase'],
            'standard_cost': latest_prices['standard'],
            'actual_cost': latest_prices['actual'],
            'supplier_batch': batch.supplier_batch_no,
            'mfg_date': batch.mfg_date.isoformat() if batch.mfg_date else None,
            'location': batch.location
        })
    
    return jsonify(comparison_data)