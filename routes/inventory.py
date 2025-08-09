from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms import ItemForm
from models import Item, ItemType, ItemBatch
from models.batch import BatchMovementLedger, BatchConsumptionReport
from services.batch_management import BatchManager, BatchValidator
from app import db
from sqlalchemy import func, desc, or_, and_
from utils import generate_item_code
from utils.export import export_inventory_items
from utils.batch_tracking import BatchTracker
from datetime import datetime, timedelta

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/dashboard')
@login_required
def dashboard():
    """Simplified inventory dashboard with safe database queries"""
    # Use simple stats to avoid transaction issues
    try:
        # Begin with basic safe queries
        db.session.rollback()  # Clear any pending transactions
        
        # Use basic counting without complex joins
        total_items = db.session.query(func.count(Item.id)).scalar() or 0
        
        # Try to get more detailed stats if possible
        try:
            raw_material_count = db.session.query(func.count(Item.id)).filter(Item.item_type == 'raw_material').scalar() or 0
            finished_goods_count = db.session.query(func.count(Item.id)).filter(Item.item_type == 'finished_good').scalar() or 0
            
            # Get recent items safely
            recent_items = db.session.query(Item).order_by(Item.id.desc()).limit(5).all()
            
            # Basic stock value calculation
            stock_value = db.session.query(func.sum(
                func.coalesce(Item.current_stock, 0) * func.coalesce(Item.unit_price, 0)
            )).scalar() or 0
            
        except:
            raw_material_count = 0
            finished_goods_count = 0
            recent_items = []
            stock_value = 0
        
        # Calculate actual statistics from database
        low_stock_count = Item.query.filter(Item.current_stock <= 0).count()  # Items with zero or negative stock
        out_of_stock_count = Item.query.filter(Item.current_stock == 0).count()  # Items with exactly zero stock
        wip_count = Item.query.filter(Item.item_type == 'work_in_progress').count()
        scrap_count = Item.query.filter(Item.item_type == 'scrap').count()
        
        stats = {
            'total_items': total_items,
            'low_stock_items': low_stock_count,
            'total_stock_value': stock_value,
            'out_of_stock_items': out_of_stock_count,
            'raw_material_items': raw_material_count,
            'finished_goods_items': finished_goods_count,
            'wip_items': wip_count,
            'scrap_items': scrap_count
        }
        
        # Get actual low stock items from database
        low_stock_items = Item.query.filter(Item.current_stock <= 0).all()
        
        # Get actual UOM distribution from database
        uom_stats = db.session.query(
            Item.unit_of_measure, 
            func.count(Item.id).label('count')
        ).group_by(Item.unit_of_measure).all() or []
        
    except Exception as e:
        # Ultimate fallback - completely static data
        stats = {
            'total_items': 0,
            'low_stock_items': 0,
            'total_stock_value': 0,
            'out_of_stock_items': 0,
            'raw_material_items': 0,
            'finished_goods_items': 0,
            'wip_items': 0,
            'scrap_items': 0
        }
        recent_items = []
        low_stock_items = []
        uom_stats = []
    
    return render_template('inventory/dashboard.html', 
                         stats=stats, 
                         recent_items=recent_items,
                         low_stock_items=low_stock_items,
                         uom_stats=uom_stats)

@inventory_bp.route('/batch-tracking')
@login_required
def batch_tracking_dashboard():
    """Redirect to the proper batch tracking dashboard"""
    return redirect(url_for('batch_tracking.dashboard'))

@inventory_bp.route('/batch/<int:batch_id>/traceability')
@login_required
def batch_traceability(batch_id):
    """View complete traceability for a specific batch"""
    traceability_data = BatchManager.get_batch_traceability(batch_id)
    
    if 'error' in traceability_data:
        flash(f'Error getting batch traceability: {traceability_data["error"]}', 'error')
        return redirect(url_for('inventory.batch_tracking_dashboard'))
    
    return render_template('inventory/batch_traceability.html',
                         title=f'Batch Traceability - {traceability_data["batch"]["batch_number"]}',
                         traceability=traceability_data)

@inventory_bp.route('/multi-state')
@login_required
def multi_state_view():
    """Multi-state inventory view showing all inventory stages"""
    try:
        # Get all items and calculate multi-state totals
        items = Item.query.all()
        inventory_data = []
        
        for item in items:
            # Calculate totals from batches
            batches = ItemBatch.query.filter_by(item_id=item.id).all()
            raw_qty = sum(b.quantity for b in batches if b.status == 'raw_material')
            wip_qty = sum(b.quantity for b in batches if b.status == 'wip')
            finished_qty = sum(b.quantity for b in batches if b.status == 'finished_goods')
            scrap_qty = sum(b.quantity for b in batches if b.status == 'scrap')
            
            # Set calculated values on the item object for template compatibility
            item.qty_raw = raw_qty
            item.total_wip = wip_qty
            item.qty_finished = finished_qty
            item.qty_scrap = scrap_qty
            item.total_stock = raw_qty + wip_qty + finished_qty + scrap_qty
            item.available_stock = finished_qty
            item.minimum_stock = getattr(item, 'minimum_stock', 0)
            
            inventory_data.append(item)
        
        # Calculate summary totals
        summary = {
            'total_items': len(inventory_data),
            'total_raw': sum(item.qty_raw for item in inventory_data),
            'total_wip': sum(item.total_wip for item in inventory_data),
            'total_finished': sum(item.qty_finished for item in inventory_data),
            'total_scrap': sum(item.qty_scrap for item in inventory_data),
            'total_available': sum(item.available_stock for item in inventory_data)
        }
        
        return render_template('inventory/multi_state_view.html', 
                             items=inventory_data,
                             summary=summary,
                             total_raw=summary['total_raw'],
                             total_wip=summary['total_wip'],
                             total_finished=summary['total_finished'],
                             total_scrap=summary['total_scrap'],
                             title='Multi-State Inventory Tracking')
        
    except Exception as e:
        flash(f'Error loading multi-state view: {str(e)}', 'error')
        return redirect(url_for('inventory.dashboard'))

@inventory_bp.route('/multi-state-legacy')
@login_required 
def multi_state_view_legacy():
    """Legacy multi-state view (backup)"""
    # Get all items and ensure multi-state fields are initialized
    items = Item.query.all()
    
    # Initialize multi-state inventory for items that haven't been set up
    for item in items:
        if hasattr(item, 'qty_raw') and item.qty_raw is None:
            item.qty_raw = item.current_stock or 0.0
            item.qty_wip = 0.0
            item.qty_finished = 0.0
            item.qty_scrap = 0.0
    
    db.session.commit()
    
    # Calculate totals
    total_raw = sum(item.qty_raw or 0 for item in items)
    total_wip = sum(item.total_wip or 0 for item in items)
    total_finished = sum(item.qty_finished or 0 for item in items)
    total_scrap = sum(item.qty_scrap or 0 for item in items)
    
    return render_template('inventory/multi_state_view.html',
                         title='Multi-State Inventory Tracking',
                         items=items,
                         total_raw=total_raw,
                         total_wip=total_wip,
                         total_finished=total_finished,
                         total_scrap=total_scrap)

@inventory_bp.route('/batch-wise')
@login_required
def batch_wise_view():
    """View inventory organized by batches with complete traceability"""
    
    # Get filter parameters
    item_filter = request.args.get('item_id', type=int)
    state_filter = request.args.get('state', '')
    location_filter = request.args.get('location', '')
    
    # Build base query - use ItemBatch instead of ItemBatch
    from models.batch import ItemBatch
    query = ItemBatch.query.join(Item)
    
    # Apply filters
    if item_filter:
        query = query.filter(ItemBatch.item_id == item_filter)
    
    if state_filter:
        if state_filter == 'raw':
            query = query.filter(ItemBatch.qty_raw > 0)
        elif state_filter == 'finished':
            query = query.filter(ItemBatch.qty_finished > 0)
        elif state_filter == 'scrap':
            query = query.filter(ItemBatch.qty_scrap > 0)
        elif state_filter == 'wip':
            query = query.filter(ItemBatch.qty_wip > 0)
        elif state_filter == 'inspection':
            query = query.filter(ItemBatch.qty_inspection > 0)
    
    if location_filter:
        query = query.filter(ItemBatch.location.ilike(f'%{location_filter}%'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    batches = query.order_by(desc(ItemBatch.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get process-wise summary
    process_summary = BatchTracker.get_process_wise_inventory_summary()
    
    # Prepare parent-child batch data for template
    from models.grn import GRN
    from models import PurchaseOrder
    parent_child_data = []
    
    # Group GRNs by their parent documents (Purchase Orders)
    purchase_orders = PurchaseOrder.query.join(GRN, GRN.purchase_order_id == PurchaseOrder.id).order_by(desc(PurchaseOrder.created_at)).limit(10).all()
    
    for idx, po in enumerate(purchase_orders):
        po_grns = GRN.query.filter_by(purchase_order_id=po.id).all()
        if po_grns:
            # Prepare child GRNs data
            child_grns = []
            total_qty = 0
            
            for grn in po_grns:
                grn_batches = ItemBatch.query.filter_by(grn_id=grn.id).all()
                if grn_batches:
                    grn_qty = sum(batch.total_quantity for batch in grn_batches)
                    total_qty += grn_qty
                    
                    child_grns.append({
                        'grn_id': grn.id,
                        'grn_number': grn.grn_number,
                        'grn_date': grn.created_at.date() if grn.created_at else None,
                        'status': grn.status,
                        'batch_numbers': [batch.batch_code for batch in grn_batches],
                        'item_name': grn_batches[0].item.name if grn_batches[0].item else 'Unknown Item',
                        'received_qty': grn_qty,
                        'scrap_qty': sum(batch.qty_scrap or 0 for batch in grn_batches)
                    })
            
            # Create parent data structure
            parent_data = {
                'parent_id': f'po_{po.id}',
                'parent_doc': po.po_number,
                'date': po.created_at.date() if po.created_at else None,
                'type': 'Purchase Order',
                'vendor_customer': po.supplier.name if po.supplier else 'Unknown Supplier',
                'status': po.status,
                'total_qty': total_qty,
                'grn_count': len(child_grns),
                'child_grns': child_grns
            }
            parent_child_data.append(parent_data)
    
    # Get recent batch movements
    from models.batch import BatchMovementLedger
    recent_movements = BatchMovementLedger.query.order_by(desc(BatchMovementLedger.created_at)).limit(10).all()
    
    # Get filter options
    items = Item.query.order_by(Item.name).all()
    storage_locations = db.session.query(ItemBatch.location).distinct().all()
    locations = [loc[0] for loc in storage_locations if loc[0]]
    
    # Calculate batch statistics
    batch_stats = {
        'total_batches': ItemBatch.query.count(),
        'active_batches': ItemBatch.query.filter(
            db.or_(
                ItemBatch.qty_raw > 0,
                ItemBatch.qty_wip > 0,
                ItemBatch.qty_finished > 0,
                ItemBatch.qty_inspection > 0
            )
        ).count(),
        'expired_batches': ItemBatch.query.filter(
            ItemBatch.expiry_date < datetime.now().date()
        ).count() if ItemBatch.query.filter(ItemBatch.expiry_date != None).count() > 0 else 0,
        'batches_expiring_soon': ItemBatch.query.filter(
            ItemBatch.expiry_date.between(
                datetime.now().date(),
                (datetime.now() + timedelta(days=30)).date()
            )
        ).count() if ItemBatch.query.filter(ItemBatch.expiry_date != None).count() > 0 else 0,
        'quality_issues': ItemBatch.query.filter(ItemBatch.inspection_status == 'failed').count()
    }
    
    return render_template('inventory/batch_tracking_dashboard_clean.html',
                         title='Batch-Wise Inventory Tracking',
                         batches=batches,
                         process_summary=process_summary,
                         stats=batch_stats,
                         parent_child_data=parent_child_data,
                         recent_movements=recent_movements,
                         items=items,
                         locations=locations,
                         current_filters={
                             'item_id': item_filter,
                             'state': state_filter,
                             'location': location_filter
                         })

@inventory_bp.route('/process-breakdown')
@login_required
def process_breakdown():
    """Show inventory breakdown by manufacturing processes"""
    
    # Get process-wise inventory summary
    process_summary = BatchTracker.get_process_wise_inventory_summary()
    
    # Calculate totals across all processes
    process_totals = {
        'raw': 0,
        'cutting': 0,
        'bending': 0,
        'welding': 0,
        'zinc': 0,
        'painting': 0,
        'assembly': 0,
        'machining': 0,
        'polishing': 0,
        'finished': 0,
        'scrap': 0
    }
    
    for item_id, item_data in process_summary.items():
        for process, qty in item_data['states'].items():
            if process in process_totals:
                process_totals[process] += qty
    
    # Get top items by process volume
    top_items_by_process = {}
    for process in process_totals.keys():
        if process_totals[process] > 0:
            # Get items with highest quantity in this process
            items_in_process = []
            for item_id, item_data in process_summary.items():
                qty = item_data['states'].get(process, 0)
                if qty > 0:
                    items_in_process.append({
                        'item_name': item_data['item_name'],
                        'item_code': item_data.get('item_code', item.code),
                        'quantity': qty,
                        'unit_of_measure': item_data['unit_of_measure']
                    })
            
            # Sort by quantity and take top 5
            items_in_process.sort(key=lambda x: x['quantity'], reverse=True)
            top_items_by_process[process] = items_in_process[:5]
    
    return render_template('inventory/process_breakdown.html',
                         title='Process-Wise Inventory Breakdown',
                         process_summary=process_summary,
                         process_totals=process_totals,
                         top_items_by_process=top_items_by_process)

# API Endpoints for Batch Integration

@inventory_bp.route('/api/item/<int:item_id>/batch-summary')
@login_required
def api_item_batch_summary(item_id):
    """Get batch summary for a specific item"""
    try:
        item = Item.query.get_or_404(item_id)
        batches = ItemBatch.query.filter_by(item_id=item_id).all()
        
        summary = {
            'item_id': item_id,
            'item_name': item.name,
            'item_code': item.code,
            'total_batches': len(batches),
            'states': {
                'raw': sum(b.qty_raw or 0 for b in batches),
                'cutting': sum(b.qty_wip_cutting or 0 for b in batches),
                'bending': sum(b.qty_wip_bending or 0 for b in batches),
                'welding': sum(b.qty_wip_welding or 0 for b in batches),
                'zinc': sum(b.qty_wip_zinc or 0 for b in batches),
                'painting': sum(b.qty_wip_painting or 0 for b in batches),
                'assembly': sum(b.qty_wip_assembly or 0 for b in batches),
                'machining': sum(b.qty_wip_machining or 0 for b in batches),
                'polishing': sum(b.qty_wip_polishing or 0 for b in batches),
                'finished': sum(b.qty_finished or 0 for b in batches),
                'scrap': sum(b.qty_scrap or 0 for b in batches)
            },
            'batches': []
        }
        
        for batch in batches:
            batch_info = {
                'id': batch.id,
                'batch_number': batch.batch_number,
                'total_quantity': batch.total_quantity,
                'available_quantity': batch.available_quantity,
                'quality_status': batch.quality_status,
                'storage_location': batch.storage_location,
                'wip_breakdown': batch.wip_breakdown
            }
            summary['batches'].append(batch_info)
        
        summary['total_quantity'] = sum(summary['states'].values())
        summary['available_quantity'] = summary['states']['raw'] + summary['states']['finished']
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/unified')
@login_required
def unified_view():
    """Unified inventory view combining standard and multi-state information"""
    # Get filter parameters
    search = request.args.get('search', '').strip()
    item_type_filter = request.args.get('item_type', '')
    stock_status = request.args.get('stock_status', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    # Base query
    query = Item.query
    
    # Apply filters
    if search:
        query = query.filter(
            (Item.name.ilike(f'%{search}%')) | 
            (Item.code.ilike(f'%{search}%'))
        )
    
    if item_type_filter:
        query = query.join(ItemType).filter(ItemType.name == item_type_filter)
    
    if min_price is not None:
        query = query.filter(Item.unit_price >= min_price)
    
    if max_price is not None:
        query = query.filter(Item.unit_price <= max_price)
    
    # Get all items
    items = query.order_by(Item.name).all()
    
    # Initialize multi-state inventory for items that haven't been set up
    for item in items:
        if item.qty_raw is None:
            item.qty_raw = item.current_stock or 0.0
            item.qty_wip = 0.0
            item.qty_finished = 0.0
            item.qty_scrap = 0.0
    
    db.session.commit()
    
    # Apply stock status filter after multi-state initialization
    if stock_status:
        if stock_status == 'low':
            items = [item for item in items if (item.available_stock or 0) <= (item.minimum_stock or 0) and (item.minimum_stock or 0) > 0]
        elif stock_status == 'out':
            items = [item for item in items if (item.available_stock or 0) == 0]
        elif stock_status == 'available':
            items = [item for item in items if (item.available_stock or 0) > 0]
    
    # Get item types for filter dropdown
    item_types = ItemType.query.filter_by(is_active=True).order_by(ItemType.name).all()
    
    return render_template('inventory/unified_view.html',
                         title='Unified Inventory View',
                         items=items,
                         item_types=item_types)

@inventory_bp.route('/list')
@login_required
def list_items():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    item_type_filter = request.args.get('item_type', '', type=str)
    stock_status_filter = request.args.get('stock_status', '', type=str)
    min_price = request.args.get('min_price', '', type=str)
    max_price = request.args.get('max_price', '', type=str)
    
    query = Item.query
    
    # Apply filters
    if search:
        query = query.filter(Item.name.contains(search) | Item.code.contains(search))
    
    if item_type_filter:
        query = query.filter_by(item_type=item_type_filter)
    
    if stock_status_filter:
        if stock_status_filter == 'low_stock':
            query = query.filter(func.coalesce(Item.current_stock, 0) <= func.coalesce(Item.minimum_stock, 0))
        elif stock_status_filter == 'in_stock':
            query = query.filter(func.coalesce(Item.current_stock, 0) > func.coalesce(Item.minimum_stock, 0))
        elif stock_status_filter == 'out_of_stock':
            query = query.filter(func.coalesce(Item.current_stock, 0) == 0)
    
    if min_price:
        try:
            min_price_val = float(min_price)
            query = query.filter(func.coalesce(Item.unit_price, 0) >= min_price_val)
        except ValueError:
            flash('Invalid minimum price', 'error')
    
    if max_price:
        try:
            max_price_val = float(max_price)
            query = query.filter(func.coalesce(Item.unit_price, 0) <= max_price_val)
        except ValueError:
            flash('Invalid maximum price', 'error')
    
    items = query.order_by(Item.name).paginate(
        page=page, per_page=20, error_out=False)
    
    # Get all items for the list
    material_items = query.order_by(Item.name).all()
    
    # Get total count
    total_items = Item.query.count()
    
    return render_template('inventory/list.html', 
                         items=items, 
                         material_items=material_items,
                         total_items=total_items,
                         search=search,
                         item_type_filter=item_type_filter,
                         stock_status_filter=stock_status_filter,
                         min_price=min_price,
                         max_price=max_price)

@inventory_bp.route('/export')
@login_required
def export_items():
    """Export inventory items to Excel"""
    # Get same filter parameters as list_items
    search = request.args.get('search', '')
    item_type_filter = request.args.get('item_type', '')
    stock_status_filter = request.args.get('stock_status', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    
    query = Item.query
    
    # Apply filters
    if search:
        query = query.filter(Item.name.ilike(f'%{search}%') | Item.code.ilike(f'%{search}%'))
    
    if item_type_filter:
        query = query.filter_by(item_type=item_type_filter)
    
    if stock_status_filter == 'low_stock':
        query = query.filter(func.coalesce(Item.current_stock, 0) <= func.coalesce(Item.minimum_stock, 0))
    elif stock_status_filter == 'out_of_stock':
        query = query.filter(func.coalesce(Item.current_stock, 0) == 0)
    elif stock_status_filter == 'in_stock':
        query = query.filter(func.coalesce(Item.current_stock, 0) > 0)
    
    if min_price:
        try:
            min_price_val = float(min_price)
            query = query.filter(Item.unit_price >= min_price_val)
        except ValueError:
            pass
    
    if max_price:
        try:
            max_price_val = float(max_price)
            query = query.filter(Item.unit_price <= max_price_val)
        except ValueError:
            pass
    
    items = query.order_by(Item.name).all()
    
    return export_inventory_items(items)

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    form = ItemForm()
    
    # Auto-generate item code if not provided
    if not form.code.data:
        form.code.data = generate_item_code()
    
    if form.validate_on_submit():
        # Check if item code already exists
        existing_item = Item.query.filter_by(code=form.code.data).first()
        if existing_item:
            flash('Item code already exists', 'danger')
            return render_template('inventory/form.html', form=form, title='Add Item')
        
        item_type_obj = ItemType.query.get(int(form.item_type.data))
        item = Item(
            code=form.code.data,
            name=form.name.data,
            description=form.description.data,
            unit_of_measure=form.unit_of_measure.data,
            hsn_code=form.hsn_code.data,
            gst_rate=form.gst_rate.data,
            current_stock=form.current_stock.data,
            minimum_stock=form.minimum_stock.data,
            unit_price=form.unit_price.data,
            unit_weight=form.unit_weight.data,
            item_type_id=int(form.item_type.data),
            item_type=item_type_obj.name.lower() if item_type_obj else 'material'
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added successfully', 'success')
        return redirect(url_for('inventory.list_items'))
    
    return render_template('inventory/form.html', form=form, title='Add Item')

@inventory_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_item(id):
    item = Item.query.get_or_404(id)
    form = ItemForm(obj=item)
    
    if form.validate_on_submit():
        # Check if item code already exists (excluding current item)
        existing_item = Item.query.filter(Item.code == form.code.data, Item.id != id).first()
        if existing_item:
            flash('Item code already exists', 'danger')
            return render_template('inventory/form.html', form=form, title='Edit Item')
        
        item_type_obj = ItemType.query.get(int(form.item_type.data))
        item.code = form.code.data
        item.name = form.name.data
        item.description = form.description.data
        item.unit_of_measure = form.unit_of_measure.data
        item.hsn_code = form.hsn_code.data
        item.gst_rate = form.gst_rate.data
        item.current_stock = form.current_stock.data
        item.minimum_stock = form.minimum_stock.data
        item.unit_price = form.unit_price.data
        item.unit_weight = form.unit_weight.data
        item.item_type_id = int(form.item_type.data)
        item.item_type = item_type_obj.name.lower() if item_type_obj else 'material'
        
        db.session.commit()
        flash('Item updated successfully', 'success')
        return redirect(url_for('inventory.list_items'))
    
    return render_template('inventory/form.html', form=form, title='Edit Item', item=item)

@inventory_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_item(id):
    if not current_user.is_admin():
        flash('Only administrators can delete items', 'danger')
        return redirect(url_for('inventory.list_items'))
    
    item = Item.query.get_or_404(id)
    
    # Check if item is used in any orders or BOM
    if item.purchase_order_items or item.sales_order_items or item.bom_items:
        flash('Cannot delete item. It is referenced in orders or BOM.', 'danger')
        return redirect(url_for('inventory.list_items'))
    
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully', 'success')
    return redirect(url_for('inventory.list_items'))


# API Endpoints
@inventory_bp.route('/inventory/api/item-stock/<int:item_id>')
@inventory_bp.route('/api/item-stock/<int:item_id>')
@login_required
def get_item_stock(item_id):
    """API endpoint to get item stock information with multi-state inventory"""
    try:
        item = Item.query.get_or_404(item_id)
        
        # Initialize multi-state fields if not set
        if item.qty_raw is None:
            item.qty_raw = item.current_stock or 0.0
            item.qty_wip = 0.0
            item.qty_finished = 0.0
            item.qty_scrap = 0.0
            db.session.commit()
        
        return jsonify({
            'success': True,
            'item_id': item.id,
            'item_name': item.name,
            'item_code': item.code,
            'current_stock': item.current_stock or 0,
            'qty_raw': item.qty_raw or 0,
            'qty_wip': item.qty_wip or 0,
            'qty_finished': item.qty_finished or 0,
            'qty_scrap': item.qty_scrap or 0,
            'total_stock': item.total_stock,
            'available_stock': item.available_stock,
            'minimum_stock': item.minimum_stock or 0,
            'unit_of_measure': item.unit_of_measure or 'units',
            'unit_price': float(item.unit_price or 0),
            'unit_weight': float(item.unit_weight or 0),
            'low_stock': (item.available_stock or 0) <= (item.minimum_stock or 0)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_bp.route('/api/item-batch-details/<item_code>')
@login_required
def api_item_batch_details(item_code):
    """API endpoint to get detailed batch information for parent-child table"""
    try:
        # Get item by code
        item = Item.query.filter_by(code=item_code).first()
        if not item:
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Get all batches for this item using ItemBatch model
        from models.batch import ItemBatch
        batches = ItemBatch.query.filter_by(item_id=item.id).all()
        print(f"Found {len(batches)} ItemBatch records for item {item.code}")
        
        batch_data = []
        for batch in batches:
            # Use ItemBatch field names
            # Determine batch status based on inspection_status and quantities
            if hasattr(batch, 'inspection_status') and batch.inspection_status:
                if batch.inspection_status == 'passed':
                    status = 'approved'
                elif batch.inspection_status == 'failed':
                    status = 'rejected'
                elif batch.inspection_status == 'pending':
                    status = 'pending'
                else:
                    status = batch.inspection_status
            elif batch.total_quantity > 0:
                status = 'active'
            else:
                status = 'empty'
            
            batch_info = {
                'batch_id': batch.id,
                'batch_code': batch.batch_code,
                'location': batch.location or 'Main Store',
                'qty_raw': float(batch.qty_raw or 0),
                'qty_wip': float(batch.qty_wip or 0),
                'qty_finished': float(batch.qty_finished or 0),
                'qty_scrap': float(batch.qty_scrap or 0),
                'total_qty': float(batch.total_quantity),
                'available_qty': float(batch.available_quantity),
                'uom': batch.uom,
                'purchase_rate': float(batch.purchase_rate or 0),
                'supplier_batch_no': batch.supplier_batch_no or 'N/A',
                'created_date': batch.created_at.strftime('%d/%m/%Y') if batch.created_at else 'N/A',
                'expiry_date': batch.expiry_date.strftime('%d/%m/%Y') if batch.expiry_date else 'N/A',
                'age_days': batch.age_days,
                'status': status
            }
            batch_data.append(batch_info)
        
        return jsonify({
            'success': True,
            'item_code': item_code,
            'item_name': item.name,
            'batches': batch_data
        })
        
    except Exception as e:
        print(f"Error in api_item_batch_details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Multi-state inventory export functionality
def export_multi_state_inventory_items(items):
    """Export unified multi-state inventory items to Excel"""
    from flask import make_response
    import io
    import csv
    from datetime import date
    
    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    header = [
        'Item Code', 'Item Name', 'Description', 'Type', 'UOM',
        'Raw Material', 'WIP', 'Finished', 'Scrap',
        'Total Stock', 'Available Stock', 'Min Stock',
        'Unit Price (₹)', 'Stock Value (₹)', 'Unit Weight (kg)',
        'HSN Code', 'GST Rate (%)', 'Created Date'
    ]
    writer.writerow(header)
    
    # Write data
    for item in items:
        total_stock = (item.get('qty_raw', 0) + item.get('qty_wip', 0) + 
                      item.get('qty_finished', 0) + item.get('qty_scrap', 0))
        available_stock = item.get('qty_raw', 0) + item.get('qty_finished', 0)
        stock_value = available_stock * (item.get('unit_price', 0) or 0)
        
        row = [
            item.get('code', ''),
            item.get('name', ''),
            item.get('description', ''),
            item.get('item_type', '').title(),
            item.get('unit_of_measure', ''),
            float(item.get('qty_raw', 0)),
            float(item.get('qty_wip', 0)),
            float(item.get('qty_finished', 0)),
            float(item.get('qty_scrap', 0)),
            float(total_stock),
            float(available_stock),
            float(item.get('minimum_stock', 0)),
            float(item.get('unit_price', 0)),
            float(stock_value),
            float(item.get('unit_weight', 0)),
            item.get('hsn_code', ''),
            float(item.get('gst_rate', 0)),
            item.get('created_at', '').strftime('%d/%m/%Y') if item.get('created_at') else '',
        ]
        writer.writerow(row)
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=unified_multi_state_inventory_{date.today()}.csv'
    
    return response


@inventory_bp.route('/api/items/finished-product/<int:input_material_id>')
@login_required
def get_finished_product(input_material_id):
    """Get the finished product version of an input material"""
    try:
        input_item = Item.query.get(input_material_id)
        if not input_item:
            return jsonify({'error': 'Input material not found'}), 404
        
        process = request.args.get('process', '')
        
        # Try to find existing finished goods version
        # Look for items with similar name but marked as finished_good
        base_name = input_item.name.replace('Raw Material', '').replace('RM', '').strip()
        
        # Search for finished goods with similar base name
        finished_product = Item.query.filter(
            Item.item_type == 'finished_good',
            or_(
                Item.name.contains(base_name),
                Item.description.contains(base_name)
            )
        ).first()
        
        if not finished_product:
            # Create a new finished goods item if it doesn't exist
            finished_name = f"{base_name} - Finished"
            finished_code = f"FG-{input_item.code.replace('RM-', '').replace('RAW-', '')}"
            
            # Check if code already exists
            existing = Item.query.filter_by(code=finished_code).first()
            if existing:
                finished_code = f"{finished_code}-{input_material_id}"
            
            finished_product = Item(
                code=finished_code,
                name=finished_name,
                description=f"Finished product from {input_item.name}",
                item_type='finished_good',
                unit_of_measure=input_item.unit_of_measure,
                unit_price=input_item.unit_price * 1.3 if input_item.unit_price else 0,  # Add 30% value addition
                category=input_item.category,
                current_stock=0
            )
            
            db.session.add(finished_product)
            db.session.commit()
        
        return jsonify({
            'product': {
                'id': finished_product.id,
                'code': finished_product.code,
                'name': finished_product.name,
                'uom': finished_product.unit_of_measure
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Error finding finished product: {str(e)}'}), 500


@inventory_bp.route('/api/items/wip-product/<int:input_material_id>')
@login_required
def get_wip_product(input_material_id):
    """Get or create WIP version of an input material for intermediate processes"""
    try:
        input_item = Item.query.get(input_material_id)
        if not input_item:
            return jsonify({'error': 'Input material not found'}), 404
        
        process = request.args.get('process', '')
        
        # Create WIP product name based on process
        base_name = input_item.name.replace('Raw Material', '').replace('RM', '').strip()
        wip_name = f"{base_name} - {process.title()} WIP"
        wip_code = f"WIP-{input_item.code.replace('RM-', '').replace('RAW-', '')}-{process.upper()[:3]}"
        
        # Check if WIP item already exists
        wip_product = Item.query.filter_by(code=wip_code).first()
        
        if not wip_product:
            # Create new WIP item
            wip_product = Item(
                code=wip_code,
                name=wip_name,
                description=f"Work in Progress: {input_item.name} after {process}",
                item_type='work_in_progress',
                unit_of_measure=input_item.unit_of_measure,
                unit_price=input_item.unit_price * 1.1 if input_item.unit_price else 0,  # Add 10% value
                category=input_item.category,
                current_stock=0
            )
            
            db.session.add(wip_product)
            db.session.commit()
        
        return jsonify({
            'product': {
                'id': wip_product.id,
                'code': wip_product.code,
                'name': wip_product.name,
                'uom': wip_product.unit_of_measure
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Error finding WIP product: {str(e)}'}), 500


@inventory_bp.route('/unified-batch-management')
@login_required
def unified_batch_management():
    """Unified batch management combining tracking and analysis"""
    
    # Get all batch data
    batches = ItemBatch.query.order_by(desc(ItemBatch.created_at)).all()
    
    # Get batch statistics
    batch_stats = {
        'total_batches': ItemBatch.query.count(),
        'active_batches': ItemBatch.query.filter(
            db.or_(
                ItemBatch.qty_raw > 0,
                ItemBatch.qty_wip > 0,
                ItemBatch.qty_finished > 0,
                ItemBatch.qty_inspection > 0
            )
        ).count(),
        'expired_batches': ItemBatch.query.filter(
            ItemBatch.expiry_date < datetime.now().date()
        ).count() if ItemBatch.query.filter(ItemBatch.expiry_date != None).count() > 0 else 0,
        'batches_expiring_soon': ItemBatch.query.filter(
            ItemBatch.expiry_date.between(
                datetime.now().date(),
                (datetime.now() + timedelta(days=30)).date()
            )
        ).count() if ItemBatch.query.filter(ItemBatch.expiry_date != None).count() > 0 else 0,
        'quality_issues': ItemBatch.query.filter(ItemBatch.inspection_status == 'failed').count(),
        'total_scrap_quantity': sum((batch.qty_scrap or 0) for batch in batches),
        'total_good_quantity': sum((batch.qty_raw or 0) + (batch.qty_finished or 0) for batch in batches)
    }
    
    # Get recent batch movements for tracking
    from models.batch import BatchMovementLedger
    recent_movements = BatchMovementLedger.query.order_by(desc(BatchMovementLedger.created_at)).limit(15).all()
    
    # Get filter options
    items = Item.query.order_by(Item.name).all()
    storage_locations = db.session.query(ItemBatch.location).distinct().all()
    locations = [loc[0] for loc in storage_locations if loc[0]]
    
    # Process summary by state
    process_summary = {}
    for batch in batches:
        if batch.qty_raw and batch.qty_raw > 0:
            process_summary['Raw Material'] = process_summary.get('Raw Material', 0) + batch.qty_raw
        if batch.qty_wip and batch.qty_wip > 0:
            process_summary['Work in Progress'] = process_summary.get('Work in Progress', 0) + batch.qty_wip
        if batch.qty_finished and batch.qty_finished > 0:
            process_summary['Finished Goods'] = process_summary.get('Finished Goods', 0) + batch.qty_finished
        if batch.qty_scrap and batch.qty_scrap > 0:
            process_summary['Scrap/Rejected'] = process_summary.get('Scrap/Rejected', 0) + batch.qty_scrap
        if batch.qty_inspection and batch.qty_inspection > 0:
            process_summary['Under Inspection'] = process_summary.get('Under Inspection', 0) + batch.qty_inspection
    
    return render_template('inventory/unified_batch_management.html',
                         title='Unified Batch Management',
                         batches=batches,
                         process_summary=process_summary,
                         stats=batch_stats,
                         recent_movements=recent_movements,
                         items=items,
                         locations=locations)
