"""
Price Management Routes - Advanced pricing functionality
Handles price updates, cascading, and impact analysis
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Item, BOM, BOMItem, ItemPriceHistory
from services.price_cascading import PriceCascadingService
from datetime import datetime, date
import json

bp = Blueprint('price_management', __name__, url_prefix='/price-management')

@bp.route('/impact-analysis')
@login_required
def impact_analysis():
    """Price impact analysis page"""
    items = Item.query.filter(Item.unit_price.isnot(None)).order_by(Item.name).all()
    return render_template('price_management/impact_analysis.html', items=items)

@bp.route('/api/price-impact/<int:item_id>')
@login_required
def api_price_impact(item_id):
    """API endpoint for price impact analysis"""
    try:
        new_price = float(request.args.get('new_price', 0))
        if new_price <= 0:
            return jsonify({'error': 'Invalid price'}), 400
        
        impact = PriceCascadingService.get_price_impact_analysis(item_id, new_price)
        validation = PriceCascadingService.validate_price_change(item_id, new_price)
        
        return jsonify({
            'impact': impact,
            'validation': validation
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/update-price', methods=['POST'])
@login_required
def api_update_price():
    """API endpoint to update price with cascading"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        new_price = float(data.get('new_price', 0))
        price_type = data.get('price_type', 'purchase')
        notes = data.get('notes', '')
        force_update = data.get('force_update', False)
        
        if not item_id or new_price <= 0:
            return jsonify({'error': 'Invalid parameters'}), 400
        
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        # Validate price change
        validation = PriceCascadingService.validate_price_change(item_id, new_price)
        if not validation['valid'] and not force_update:
            return jsonify({
                'error': 'Price validation failed',
                'validation': validation
            }), 400
        
        # Get impact analysis
        impact = PriceCascadingService.get_price_impact_analysis(item_id, new_price)
        
        # Update price with cascading
        success = item.update_price(
            new_price=new_price,
            price_type=price_type,
            effective_date=date.today(),
            source='Manual Update',
            source_reference='Price Management Interface',
            notes=notes,
            user_id=current_user.id,
            cascade_update=True
        )
        
        if success:
            db.session.commit()
            
            # Get cascade results
            cascade_result = PriceCascadingService.cascade_price_update(
                item_id=item_id,
                new_price=new_price,
                price_type=price_type,
                user_id=current_user.id
            )
            
            return jsonify({
                'success': True,
                'message': f'Price updated successfully for {item.name}',
                'impact': impact,
                'cascade_result': cascade_result
            })
        else:
            return jsonify({'error': 'Failed to update price'}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/cascade-results/<int:item_id>')
@login_required
def cascade_results(item_id):
    """Show cascading results for a price update"""
    item = Item.query.get_or_404(item_id)
    
    # Get recent price history for this item
    recent_changes = ItemPriceHistory.query.filter_by(item_id=item_id)\
        .order_by(ItemPriceHistory.created_at.desc())\
        .limit(5).all()
    
    # Find items that were updated due to this item's price change
    affected_items = []
    for change in recent_changes:
        if change.source and 'Material:' in change.source:
            # This was a cascaded update
            affected_items.append(change)
    
    return render_template('price_management/cascade_results.html', 
                         item=item, 
                         recent_changes=recent_changes,
                         affected_items=affected_items)

@bp.route('/bulk-update')
@login_required
def bulk_update():
    """Bulk price update interface"""
    materials = Item.query.filter_by(item_type='material')\
        .filter(Item.unit_price.isnot(None))\
        .order_by(Item.name).all()
    
    return render_template('price_management/bulk_update.html', materials=materials)

@bp.route('/api/bulk-update', methods=['POST'])
@login_required
def api_bulk_update():
    """API endpoint for bulk price updates"""
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        
        if not updates:
            return jsonify({'error': 'No updates provided'}), 400
        
        results = []
        total_cascaded_items = 0
        total_cascaded_boms = 0
        
        for update in updates:
            item_id = update.get('item_id')
            new_price = float(update.get('new_price', 0))
            notes = update.get('notes', '')
            
            if not item_id or new_price <= 0:
                continue
            
            item = Item.query.get(item_id)
            if not item:
                continue
            
            # Update price with cascading
            success = item.update_price(
                new_price=new_price,
                price_type='purchase',
                effective_date=date.today(),
                source='Bulk Update',
                source_reference='Bulk Price Management',
                notes=notes,
                user_id=current_user.id,
                cascade_update=True
            )
            
            if success:
                # Get cascade statistics
                cascade_result = PriceCascadingService.cascade_price_update(
                    item_id=item_id,
                    new_price=new_price,
                    user_id=current_user.id
                )
                
                results.append({
                    'item_name': item.name,
                    'old_price': item.unit_price,
                    'new_price': new_price,
                    'cascade_result': cascade_result
                })
                
                if cascade_result.get('success'):
                    total_cascaded_items += cascade_result.get('items_updated', 0)
                    total_cascaded_boms += cascade_result.get('boms_updated', 0)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Bulk update completed: {len(results)} items updated, {total_cascaded_items} cascaded items, {total_cascaded_boms} BOMs updated',
            'results': results,
            'summary': {
                'items_updated': len(results),
                'cascaded_items': total_cascaded_items,
                'cascaded_boms': total_cascaded_boms
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/history')
@login_required
def price_history():
    """Price change history with cascading information"""
    page = request.args.get('page', 1, type=int)
    
    # Get price history with cascading information
    history = ItemPriceHistory.query\
        .join(Item)\
        .order_by(ItemPriceHistory.created_at.desc())\
        .paginate(page=page, per_page=50, error_out=False)
    
    return redirect(url_for('reports.dashboard'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Price management dashboard"""
    # Recent price changes
    recent_changes = ItemPriceHistory.query\
        .join(Item)\
        .order_by(ItemPriceHistory.created_at.desc())\
        .limit(10).all()
    
    # Items with significant price changes (>10% in last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    significant_changes = db.session.query(ItemPriceHistory)\
        .join(Item)\
        .filter(ItemPriceHistory.created_at >= thirty_days_ago)\
        .order_by(ItemPriceHistory.created_at.desc()).all()
    
    # Items without recent price updates (>90 days)
    ninety_days_ago = datetime.now() - timedelta(days=90)
    stale_items = db.session.query(Item)\
        .outerjoin(ItemPriceHistory)\
        .filter(
            db.or_(
                ItemPriceHistory.created_at < ninety_days_ago,
                ItemPriceHistory.id.is_(None)
            )
        )\
        .filter(Item.item_type == 'material')\
        .limit(20).all()
    
    return render_template('price_management/dashboard.html',
                         recent_changes=recent_changes,
                         significant_changes=significant_changes,
                         stale_items=stale_items)