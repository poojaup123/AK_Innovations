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
    """Unified price change history - All price changes in one place"""
    from datetime import datetime, timedelta
    
    page = request.args.get('page', 1, type=int)
    price_category = request.args.get('price_category', '')  # material, jobwork, labor, all
    price_type = request.args.get('price_type', '')
    batch_number = request.args.get('batch_number', '')  # New batch filtering
    date_range = request.args.get('date_range', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # Collect all price changes from different sources
    all_price_changes = []
    
    # 1. Material Price History (existing)
    material_query = ItemPriceHistory.query.join(Item)
    
    # Apply filters to material query
    if price_type and price_category in ('', 'material'):
        material_query = material_query.filter(ItemPriceHistory.price_type == price_type)
    
    if date_range:
        today = datetime.now()
        if date_range == '6months':
            start_filter = today - timedelta(days=180)
        elif date_range == '1year':
            start_filter = today - timedelta(days=365)
        elif date_range == '2years':
            start_filter = today - timedelta(days=730)
        elif date_range == '5years':
            start_filter = today - timedelta(days=1825)
        else:
            start_filter = None
            
        if start_filter:
            material_query = material_query.filter(ItemPriceHistory.created_at >= start_filter)
    
    if start_date:
        try:
            start_filter = datetime.strptime(start_date, '%Y-%m-%d')
            material_query = material_query.filter(ItemPriceHistory.created_at >= start_filter)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_filter = datetime.strptime(end_date, '%Y-%m-%d')
            end_filter = end_filter + timedelta(days=1)
            material_query = material_query.filter(ItemPriceHistory.created_at < end_filter)
        except ValueError:
            pass
    
    # Get material price changes
    if price_category in ('', 'material'):
        material_history = material_query.order_by(ItemPriceHistory.created_at.desc()).all()
        
        for record in material_history:
            all_price_changes.append({
                'type': 'material',
                'category': 'Material Price',
                'item_name': record.item.name if record.item else 'Unknown',
                'item_code': record.item.code if record.item else '',
                'price': record.price,
                'price_type': record.price_type or 'standard',
                'source': record.source or 'Manual',
                'date': record.created_at,
                'updated_by': getattr(record, 'updated_by', 'System'),
                'details': f"Material: {record.item.name if record.item else 'Unknown'}",
                'vendor_name': '-',
                'batch_number': '-'  # No batch for regular material prices
            })
    
    # 1b. BOM-Calculated Prices (manufactured product costs)
    if price_category in ('', 'material', 'bom'):
        try:
            from models import BOM
            
            # Find BOMs with recent cost calculations
            bom_query = BOM.query.join(Item, BOM.product_id == Item.id)
            
            # Apply date filters for BOM cost updates
            if date_range:
                today = datetime.now()
                if date_range == '6months':
                    start_filter = today - timedelta(days=180)
                elif date_range == '1year':
                    start_filter = today - timedelta(days=365)
                elif date_range == '2years':
                    start_filter = today - timedelta(days=730)
                elif date_range == '5years':
                    start_filter = today - timedelta(days=1825)
                else:
                    start_filter = None
                    
                if start_filter:
                    bom_query = bom_query.filter(BOM.updated_at >= start_filter)
            
            # Get BOMs and their calculated costs
            boms = bom_query.order_by(BOM.updated_at.desc()).all()
            
            for bom in boms:
                if bom.total_cost and bom.total_cost > 0:
                    all_price_changes.append({
                        'type': 'bom_calculated',
                        'category': 'BOM Cost',
                        'item_name': bom.item.name if bom.item else 'Unknown',
                        'item_code': bom.item.code if bom.item else '',
                        'price': bom.total_cost,
                        'price_type': 'manufactured',
                        'source': 'BOM Calculation',
                        'date': bom.updated_at or bom.created_at,
                        'updated_by': 'System',
                        'details': f"BOM: {len(bom.items or [])} components | Material: ₹{bom.material_cost or 0:.2f} | Labor: ₹{bom.labor_cost or 0:.2f}",
                        'vendor_name': 'Manufacturing',
                        'batch_number': '-'
                    })
        except (ImportError, AttributeError) as e:
            print(f"BOM cost tracking not available: {str(e)}")
            pass
    
    # 1c. Batch Price History (new - batch-specific pricing)
    if price_category in ('', 'material', 'batch'):
        try:
            from models.batch import BatchPriceHistory, InventoryBatch
            
            # Build batch price query with joins
            batch_price_query = BatchPriceHistory.query\
                .join(InventoryBatch, BatchPriceHistory.batch_id == InventoryBatch.id)\
                .join(Item, InventoryBatch.item_id == Item.id)
            
            # Apply batch number filter if specified
            if batch_number:
                batch_price_query = batch_price_query.filter(InventoryBatch.batch_code.ilike(f'%{batch_number}%'))
            
            # Apply date filters to batch prices
            if date_range:
                today = datetime.now()
                if date_range == '6months':
                    start_filter = today - timedelta(days=180)
                elif date_range == '1year':
                    start_filter = today - timedelta(days=365)
                elif date_range == '2years':
                    start_filter = today - timedelta(days=730)
                elif date_range == '5years':
                    start_filter = today - timedelta(days=1825)
                else:
                    start_filter = None
                    
                if start_filter:
                    batch_price_query = batch_price_query.filter(BatchPriceHistory.effective_date >= start_filter)
            
            if start_date:
                try:
                    start_filter = datetime.strptime(start_date, '%Y-%m-%d')
                    batch_price_query = batch_price_query.filter(BatchPriceHistory.effective_date >= start_filter)
                except ValueError:
                    pass
            
            if end_date:
                try:
                    end_filter = datetime.strptime(end_date, '%Y-%m-%d')
                    end_filter = end_filter + timedelta(days=1)
                    batch_price_query = batch_price_query.filter(BatchPriceHistory.effective_date < end_filter)
                except ValueError:
                    pass
            
            # Get batch price history
            batch_price_history = batch_price_query.order_by(BatchPriceHistory.effective_date.desc()).all()
            
            for record in batch_price_history:
                batch = record.batch
                item = batch.item if batch else None
                
                all_price_changes.append({
                    'type': 'batch_price',
                    'category': 'Batch Price',
                    'item_name': item.name if item else 'Unknown',
                    'item_code': item.code if item else '',
                    'price': record.new_price,
                    'price_type': record.price_type or 'batch',
                    'source': record.source or 'Batch Update',
                    'date': record.effective_date,
                    'updated_by': getattr(record, 'updated_by', 'System'),
                    'details': f"Batch: {batch.batch_code if batch else 'Unknown'} | Previous: ₹{record.previous_price or 0:.2f}",
                    'vendor_name': getattr(batch, 'supplier_batch_no', '-') if batch else '-',
                    'batch_number': batch.batch_code if batch else '-'
                })
        except (ImportError, AttributeError) as e:
            print(f"Batch price history not available: {str(e)}")
            pass
    
    # 2. Job Work Rates History
    if price_category in ('', 'jobwork'):
        try:
            from models import JobWorkRate
            jobwork_rates = JobWorkRate.query.join(Item, JobWorkRate.item_id == Item.id).all()
            
            for rate in jobwork_rates:
                # Apply date filters if any
                should_include = True
                if start_date:
                    try:
                        start_filter = datetime.strptime(start_date, '%Y-%m-%d')
                        if rate.created_at < start_filter:
                            should_include = False
                    except (ValueError, AttributeError):
                        pass
                
                if should_include and end_date:
                    try:
                        end_filter = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                        if rate.created_at >= end_filter:
                            should_include = False
                    except (ValueError, AttributeError):
                        pass
                
                if should_include and date_range:
                    today = datetime.now()
                    if date_range == '6months' and rate.created_at < (today - timedelta(days=180)):
                        should_include = False
                    elif date_range == '1year' and rate.created_at < (today - timedelta(days=365)):
                        should_include = False
                    elif date_range == '2years' and rate.created_at < (today - timedelta(days=730)):
                        should_include = False
                    elif date_range == '5years' and rate.created_at < (today - timedelta(days=1825)):
                        should_include = False
                
                if should_include:
                    all_price_changes.append({
                        'type': 'jobwork',
                        'category': 'Job Work Rate',
                        'item_name': rate.item.name if rate.item else 'Unknown',
                        'item_code': rate.item.code if rate.item else '',
                        'price': rate.rate_per_unit,
                        'price_type': rate.process_type or 'general',
                        'source': 'Job Work Rate',
                        'date': rate.created_at or rate.updated_at,
                        'updated_by': 'Admin',
                        'details': f"Process: {rate.process_type or 'General'} | Vendor: {rate.vendor_name or 'Any'}",
                        'vendor_name': rate.vendor_name or '-',
                        'batch_number': '-'  # No batch for job work rates
                    })
        except ImportError:
            pass  # JobWorkRate model not available
    
    # 3. Job Work Order Rates (actual rates used in orders)
    if price_category in ('', 'jobwork'):
        try:
            from models import JobWork
            job_works = JobWork.query.join(Item, JobWork.item_id == Item.id).all()
            
            for job in job_works:
                # Apply date filters
                should_include = True
                job_date = job.created_at or job.sent_date
                
                if start_date:
                    try:
                        start_filter = datetime.strptime(start_date, '%Y-%m-%d')
                        if job_date < start_filter:
                            should_include = False
                    except (ValueError, AttributeError):
                        pass
                
                if should_include and end_date:
                    try:
                        end_filter = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                        if job_date >= end_filter:
                            should_include = False
                    except (ValueError, AttributeError):
                        pass
                
                if should_include and date_range:
                    today = datetime.now()
                    if date_range == '6months' and job_date < (today - timedelta(days=180)):
                        should_include = False
                    elif date_range == '1year' and job_date < (today - timedelta(days=365)):
                        should_include = False
                    elif date_range == '2years' and job_date < (today - timedelta(days=730)):
                        should_include = False
                    elif date_range == '5years' and job_date < (today - timedelta(days=1825)):
                        should_include = False
                
                if should_include and job.rate_per_unit > 0:
                    all_price_changes.append({
                        'type': 'jobwork_order',
                        'category': 'Job Work Order',
                        'item_name': job.item.name if job.item else 'Unknown',
                        'item_code': job.item.code if job.item else '',
                        'price': job.rate_per_unit,
                        'price_type': job.process or 'general',
                        'source': 'Job Work Order',
                        'date': job_date,
                        'updated_by': 'System',
                        'details': f"Job: {job.job_number} | Process: {job.process or 'General'} | Qty: {job.quantity_sent}",
                        'vendor_name': job.customer_name or '-',
                        'batch_number': '-'  # No batch for job work orders
                    })
        except ImportError:
            pass
    
    # Sort all price changes by date (newest first)
    all_price_changes.sort(key=lambda x: x['date'] or datetime.min, reverse=True)
    
    # Calculate price changes and add indicators
    def calculate_price_change_indicators(price_changes):
        """Calculate price change indicators (up/down arrows) and percentages"""
        # Group by item_name for price change calculation
        item_groups = {}
        for record in price_changes:
            item_key = record['item_name']
            if item_key not in item_groups:
                item_groups[item_key] = []
            item_groups[item_key].append(record)
        
        # Calculate changes for each item group
        for item_name, records in item_groups.items():
            # Sort by date (newest first) to get proper price progression
            sorted_records = sorted(records, key=lambda x: x['date'] or datetime.min, reverse=True)
            
            for i, record in enumerate(sorted_records):
                # Compare with previous price (next in list since sorted newest first)
                if i < len(sorted_records) - 1:
                    current_price = record['price'] or 0
                    previous_price = sorted_records[i + 1]['price'] or 0
                    
                    if previous_price > 0:
                        price_diff = current_price - previous_price
                        percentage_change = (price_diff / previous_price) * 100
                        
                        if price_diff > 0:
                            record['price_change'] = 'increase'
                            record['change_icon'] = '↗️'
                            record['change_color'] = 'success'
                            record['change_percentage'] = f'+₹{price_diff:.2f} (+{percentage_change:.1f}%)'
                        elif price_diff < 0:
                            record['price_change'] = 'decrease'
                            record['change_icon'] = '↘️'
                            record['change_color'] = 'danger'
                            record['change_percentage'] = f'₹{price_diff:.2f} ({percentage_change:.1f}%)'
                        else:
                            record['price_change'] = 'same'
                            record['change_icon'] = '➡️'
                            record['change_color'] = 'secondary'
                            record['change_percentage'] = '₹0.00 (0.0%)'
                    else:
                        record['price_change'] = 'new'
                        record['change_icon'] = '🆕'
                        record['change_color'] = 'primary'
                        record['change_percentage'] = 'New'
                else:
                    # This is the oldest/first price record
                    record['price_change'] = 'first'
                    record['change_icon'] = '⭐'
                    record['change_color'] = 'info'
                    record['change_percentage'] = 'Initial'
        
        return price_changes
    
    # Add price change indicators
    all_price_changes = calculate_price_change_indicators(all_price_changes)
    
    # Pagination for consolidated results
    per_page = 50
    total = len(all_price_changes)
    start = (page - 1) * per_page
    end = start + per_page
    current_page_items = all_price_changes[start:end]
    
    # Create pagination object manually
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.prev_num = page - 1 if page > 1 else None
            self.next_num = page + 1 if page < self.pages else None
            self.has_prev = page > 1
            self.has_next = page < self.pages
    
    history = SimplePagination(current_page_items, page, per_page, total)
    
    # Get available price types and categories
    price_types = list(set([item['price_type'] for item in all_price_changes if item['price_type']]))
    price_types.sort()
    
    price_categories = [
        ('', 'All Categories'),
        ('material', 'Material Prices'),
        ('bom', 'BOM Costs'),
        ('batch', 'Batch Prices'),
        ('jobwork', 'Job Work Rates')
    ]
    
    # Get available batch numbers for dropdown
    batch_numbers = []
    try:
        from models.batch import InventoryBatch
        unique_batches = InventoryBatch.query.with_entities(InventoryBatch.batch_code)\
            .distinct().order_by(InventoryBatch.batch_code).all()
        batch_numbers = [batch[0] for batch in unique_batches if batch[0]]
    except (ImportError, AttributeError):
        batch_numbers = []
    
    return render_template('price_management/price_history.html', 
                         history=history, 
                         price_types=price_types,
                         price_categories=price_categories,
                         batch_numbers=batch_numbers,
                         current_price_type=price_type,
                         current_price_category=price_category,
                         current_batch_number=batch_number,
                         current_date_range=date_range,
                         current_start_date=start_date,
                         current_end_date=end_date,
                         is_unified=True)

@bp.route('/dashboard')
@login_required
def dashboard():
    """Unified Price management dashboard with comprehensive history"""
    # Get filtering parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    price_type = request.args.get('price_type', '')
    price_category = request.args.get('price_category', '')
    batch_number = request.args.get('batch_number', '')
    date_range = request.args.get('date_range', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    from datetime import datetime, timedelta
    
    # Recent price changes for summary cards
    recent_changes = ItemPriceHistory.query\
        .join(Item)\
        .order_by(ItemPriceHistory.created_at.desc())\
        .limit(10).all()
    
    # Items with significant price changes (>10% in last 30 days)
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
    
    # COMPREHENSIVE PRICE HISTORY LOGIC (merged from price_history route)
    # Comprehensive price changes from all sources
    all_price_changes = []
    
    # 1. Item price history (materials)
    item_price_query = ItemPriceHistory.query.join(Item)
    if price_type:
        item_price_query = item_price_query.filter(ItemPriceHistory.price_type == price_type)
    
    item_price_history = item_price_query.order_by(ItemPriceHistory.created_at.desc()).all()
    
    for record in item_price_history:
        change_data = {
            'item_name': record.item.name if record.item else 'Unknown Item',
            'item_code': record.item.code if record.item else 'N/A',
            'date': record.created_at,
            'price': record.price,
            'price_type': record.price_type or 'standard',
            'vendor_name': record.source or 'Manual',
            'details': f"Material: {record.item.name if record.item else 'Unknown'}",
            'updated_by': record.creator.username if record.creator else 'System',
            'category': 'Material Price',
            'batch_number': '-'
        }
        all_price_changes.append(change_data)
    
    # 2. BOM cost changes (manufactured items)
    try:
        bom_records = BOM.query.filter(BOM.is_active == True).all()
        for bom in bom_records:
            if hasattr(bom, 'last_updated') and bom.last_updated:
                change_data = {
                    'item_name': f"{bom.item.name if bom.item else 'Unknown'} (BOM)",
                    'item_code': bom.bom_code,
                    'date': bom.last_updated,
                    'price': getattr(bom, 'total_material_cost', 0) + getattr(bom, 'total_labor_cost', 0) + getattr(bom, 'total_overhead_cost', 0),
                    'price_type': 'manufactured',
                    'vendor_name': 'BOM Calculation',
                    'details': f"BOM Cost: Materials + Labor + Overhead",
                    'updated_by': 'System',
                    'category': 'BOM Cost',
                    'batch_number': '-'
                }
                all_price_changes.append(change_data)
    except Exception:
        pass
    
    # Apply date filtering
    if date_range:
        cutoff_date = None
        if date_range == '6months':
            cutoff_date = datetime.now() - timedelta(days=180)
        elif date_range == '1year':
            cutoff_date = datetime.now() - timedelta(days=365)
        elif date_range == '2years':
            cutoff_date = datetime.now() - timedelta(days=730)
        elif date_range == '5years':
            cutoff_date = datetime.now() - timedelta(days=1825)
        
        if cutoff_date:
            all_price_changes = [change for change in all_price_changes if change['date'] >= cutoff_date]
    
    # Apply custom date range
    if start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        all_price_changes = [change for change in all_price_changes if change['date'] >= start_dt]
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        all_price_changes = [change for change in all_price_changes if change['date'] <= end_dt]
    
    # Apply category filtering
    if price_category:
        if price_category == 'material':
            all_price_changes = [change for change in all_price_changes if change['category'] == 'Material Price']
        elif price_category == 'bom':
            all_price_changes = [change for change in all_price_changes if change['category'] == 'BOM Cost']
    
    # Sort by date
    all_price_changes.sort(key=lambda x: x['date'], reverse=True)
    
    # Simple pagination
    total = len(all_price_changes)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_page_items = all_price_changes[start_idx:end_idx]
    
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.prev_num = page - 1 if page > 1 else None
            self.next_num = page + 1 if page < self.pages else None
            self.has_prev = page > 1
            self.has_next = page < self.pages
        
        def iter_pages(self):
            for num in range(1, self.pages + 1):
                yield num
    
    history = SimplePagination(current_page_items, page, per_page, total)
    
    # Get available price types and categories
    price_types = list(set([item['price_type'] for item in all_price_changes if item['price_type']]))
    price_types.sort()
    
    price_categories = [
        ('', 'All Categories'),
        ('material', 'Material Prices'),
        ('bom', 'BOM Costs'),
        ('batch', 'Batch Prices'),
        ('jobwork', 'Job Work Rates')
    ]
    
    # Get available batch numbers for dropdown
    batch_numbers = []
    try:
        from models.batch import InventoryBatch
        unique_batches = InventoryBatch.query.with_entities(InventoryBatch.batch_code)\
            .distinct().order_by(InventoryBatch.batch_code).all()
        batch_numbers = [batch[0] for batch in unique_batches if batch[0]]
    except (ImportError, AttributeError):
        batch_numbers = []
    
    return render_template('price_management/dashboard.html',
                         recent_changes=recent_changes,
                         significant_changes=significant_changes,
                         stale_items=stale_items,
                         history=history,
                         price_types=price_types,
                         price_categories=price_categories,
                         batch_numbers=batch_numbers,
                         current_price_type=price_type,
                         current_price_category=price_category,
                         current_batch_number=batch_number,
                         current_date_range=date_range,
                         current_start_date=start_date,
                         current_end_date=end_date,
                         is_unified=True)