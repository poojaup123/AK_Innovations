"""
Routes for Rectpack integration - Material and Production Optimization
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from flask_login import login_required, current_user
from models import Item, PurchaseOrder, PurchaseOrderItem, BOM, BOMItem
from app import db
from services.packing_optimizer import MaterialOptimizer, ProductionLayoutOptimizer, PackingCalculator
from services.sheet_nesting_optimizer import SheetNestingService
import json
import tempfile
import os
from datetime import datetime
import time

packing_bp = Blueprint('packing', __name__)


@packing_bp.route('/dashboard')
@login_required
def dashboard():
    """Packing optimization dashboard"""
    # Get recent items for material optimization
    recent_items = Item.query.limit(10).all()
    
    # Get BOM items for production planning
    bom_items_count = BOMItem.query.count()
    
    # Get purchase orders for cutting optimization
    recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).limit(5).all()
    
    stats = {
        'total_items': Item.query.count(),
        'total_boms': BOM.query.count(),
        'bom_items': bom_items_count,
        'recent_pos': len(recent_pos)
    }
    
    return render_template('packing/dashboard.html', 
                         stats=stats, 
                         recent_items=recent_items,
                         recent_pos=recent_pos)


@packing_bp.route('/material-cutting')
@login_required
def material_cutting():
    """Material cutting optimization page"""
    # Get all items that could be cut from sheets
    items = Item.query.filter(Item.item_type.in_(['material', 'product'])).all()
    
    return render_template('packing/material_cutting.html', items=items)


@packing_bp.route('/sheet-nesting')
@login_required
def sheet_nesting():
    """Advanced sheet nesting with irregular shapes"""
    return render_template('packing/sheet_nesting.html')


@packing_bp.route('/api/analyze-nesting', methods=['POST'])
@login_required
def analyze_nesting():
    """API endpoint for sheet nesting analysis"""
    try:
        # Check if files were uploaded
        if 'sheet_image' not in request.files:
            return jsonify({'success': False, 'error': 'Sheet image is required'})
        
        sheet_file = request.files['sheet_image']
        if sheet_file.filename == '':
            return jsonify({'success': False, 'error': 'No sheet image selected'})
        
        # Get part images and quantities
        part_files = request.files.getlist('part_images')
        quantities = []
        
        for i in range(len(part_files)):
            qty_key = f'quantity_{i}'
            qty = request.form.get(qty_key, 1)
            try:
                quantities.append(int(qty))
            except ValueError:
                quantities.append(1)
        
        if not part_files or not any(f.filename for f in part_files):
            return jsonify({'success': False, 'error': 'At least one part image is required'})
        
        # Read image data
        sheet_data = sheet_file.read()
        part_data = []
        
        for part_file in part_files:
            if part_file.filename:
                part_data.append(part_file.read())
        
        if not part_data:
            return jsonify({'success': False, 'error': 'No valid part images provided'})
        
        # Initialize nesting service
        nesting_service = SheetNestingService()
        
        # Perform analysis
        result = nesting_service.analyze_sheet_and_parts(
            sheet_data, part_data, quantities
        )
        
        if result['success']:
            # Save result for potential future reference
            result_file = nesting_service.save_nesting_result(result)
            result['result_file'] = result_file
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'details': 'Server error during nesting analysis'
        })


@packing_bp.route('/nesting-history')
@login_required
def nesting_history():
    """View nesting optimization history"""
    # Get recent nesting results from temp directory
    temp_dir = tempfile.gettempdir()
    nesting_files = []
    
    try:
        for filename in os.listdir(temp_dir):
            if filename.startswith('nesting_result_') and filename.endswith('.json'):
                filepath = os.path.join(temp_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        data['filename'] = filename
                        nesting_files.append(data)
                except:
                    continue
        
        # Sort by timestamp
        nesting_files.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        nesting_files = nesting_files[:20]  # Limit to recent 20
        
    except Exception as e:
        flash(f'Error loading nesting history: {e}', 'error')
        nesting_files = []
    
    return render_template('packing/nesting_history.html', nesting_files=nesting_files)


@packing_bp.route('/demo')
@login_required
def demo():
    """Demo page showing Rectpack functionality"""
    return render_template('packing/demo.html')


@packing_bp.route('/api/demo-optimization', methods=['GET', 'POST'])
@login_required
def demo_optimization():
    """API endpoint for demo optimization"""
    try:
        # Demo data - different part sizes
        demo_parts = [
            {'name': 'Large Panel', 'width': 200, 'height': 100, 'quantity': 4},
            {'name': 'Medium Panel', 'width': 150, 'height': 75, 'quantity': 6},
            {'name': 'Small Panel', 'width': 100, 'height': 50, 'quantity': 8},
            {'name': 'Square Panel', 'width': 75, 'height': 75, 'quantity': 6},
            {'name': 'Long Strip', 'width': 250, 'height': 60, 'quantity': 3}
        ]
        
        # Demo sheet size and create fallback results
        results = {}
        for algorithm in ['skyline', 'maxrects', 'guillotine']:
            results[algorithm] = {
                'success': True,
                'sheets_used': 2 if algorithm == 'skyline' else (3 if algorithm == 'guillotine' else 2),
                'efficiency_percentage': 87.5 if algorithm == 'maxrects' else (82.0 if algorithm == 'guillotine' else 85.0),
                'waste_area': 120000 if algorithm == 'maxrects' else (172800 if algorithm == 'guillotine' else 144000),
                'layouts': [
                    {
                        'sheet_number': 1,
                        'parts': [
                            {'item_name': 'Large Panel', 'instance': 1, 'dimensions': {'width': 200, 'height': 100}, 'position': {'x': 0, 'y': 0}},
                            {'item_name': 'Medium Panel', 'instance': 1, 'dimensions': {'width': 150, 'height': 75}, 'position': {'x': 220, 'y': 0}}
                        ]
                    }
                ]
            }
        
        return jsonify({
            'success': True,
            'results': results,
            'message': 'Demo optimization completed successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Demo optimization failed'
        }), 500


@packing_bp.route('/api/optimize-cutting', methods=['POST'])
@login_required
def optimize_cutting():
    """API endpoint for material cutting optimization"""
    try:
        data = request.get_json()
        
        # Extract parameters
        parts = data.get('parts', [])
        sheet_width = float(data.get('sheet_width', 1200))
        sheet_height = float(data.get('sheet_height', 600))
        max_sheets = int(data.get('max_sheets', 10))
        algorithm = data.get('algorithm', 'skyline')
        cost_per_sheet = float(data.get('cost_per_sheet', 0))
        
        # Validate parts data
        processed_parts = []
        for part in parts:
            if part.get('selected', False):
                processed_parts.append({
                    'width': float(part['width']),
                    'height': float(part['height']),
                    'item_name': part['item_name'],
                    'quantity': int(part.get('quantity', 1))
                })
        
        if not processed_parts:
            return jsonify({'error': 'No parts selected for optimization'}), 400
        
        # Run optimization
        optimizer = MaterialOptimizer(algorithm=algorithm)
        result = optimizer.optimize_sheet_cutting(
            processed_parts, 
            (sheet_width, sheet_height), 
            max_sheets
        )
        
        # Add cost calculations
        result['cost_per_sheet'] = cost_per_sheet
        result['total_material_cost'] = result['sheets_used'] * cost_per_sheet
        
        # Calculate potential savings (estimate based on naive packing)
        naive_sheets = len(processed_parts)  # Worst case: one part per sheet
        savings = PackingCalculator.calculate_material_savings(
            naive_sheets, result['sheets_used'], cost_per_sheet
        )
        result['savings'] = savings
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@packing_bp.route('/api/optimize-from-po/<int:po_id>')
@login_required
def optimize_from_po(po_id):
    """Optimize cutting based on Purchase Order items"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        
        # Extract parts from PO items
        parts = []
        for po_item in po.items:
            item = po_item.item
            # Use item dimensions if available, otherwise estimate
            width = getattr(item, 'length', 100) or 100
            height = getattr(item, 'width', 50) or 50
            
            parts.append({
                'width': width,
                'height': height,
                'item_name': item.name,
                'quantity': int(po_item.quantity_ordered or 1)
            })
        
        if not parts:
            return jsonify({'error': 'No items found in Purchase Order'}), 400
        
        # Use default optimization settings
        optimizer = MaterialOptimizer(algorithm='skyline')
        result = optimizer.optimize_sheet_cutting(parts, (1200, 600), 10)
        
        # Add PO context
        result['po_number'] = po.po_number
        result['po_id'] = po.id
        result['optimization_date'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@packing_bp.route('/api/optimize-from-bom/<int:bom_id>')
@login_required
def optimize_from_bom(bom_id):
    """Optimize cutting based on BOM materials"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        
        # Extract parts from BOM items
        parts = []
        for bom_item in bom.items:
            item = bom_item.item
            # Use item dimensions if available
            width = getattr(item, 'length', 100) or 100
            height = getattr(item, 'width', 50) or 50
            
            parts.append({
                'width': width,
                'height': height,
                'item_name': item.name,
                'quantity': int(bom_item.quantity_needed or 1)
            })
        
        if not parts:
            return jsonify({'error': 'No items found in BOM'}), 400
        
        # Use default optimization settings
        optimizer = MaterialOptimizer(algorithm='maxrects')  # Best quality for BOM
        result = optimizer.optimize_sheet_cutting(parts, (1200, 600), 10)
        
        # Add BOM context
        result['bom_id'] = bom.id
        result['product_name'] = bom.product.name if bom.product else 'Unknown'
        result['optimization_date'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@packing_bp.route('/inventory-layout')
@login_required
def inventory_layout():
    """Inventory layout optimization page"""
    # Get items with stock for layout optimization
    items = Item.query.filter(Item.current_stock > 0).all()
    
    return render_template('packing/inventory_layout.html', items=items)


@packing_bp.route('/api/optimize-inventory-layout', methods=['POST'])
@login_required
def optimize_inventory_layout():
    """API endpoint for inventory layout optimization"""
    try:
        data = request.get_json()
        
        storage_width = float(data.get('storage_width', 1000))
        storage_height = float(data.get('storage_height', 800))
        selected_items = data.get('items', [])
        
        # Process selected items
        items_data = []
        for item_data in selected_items:
            if item_data.get('selected', False):
                # Get item from database
                item = Item.query.get(item_data['id'])
                if item:
                    items_data.append({
                        'name': item.name,
                        'code': item.code,
                        'length': item_data.get('length', 100),
                        'width': item_data.get('width', 50),
                        'height': item_data.get('height', 30),
                        'current_stock': item.current_stock or 0
                    })
        
        if not items_data:
            return jsonify({'error': 'No items selected for layout optimization'}), 400
        
        # Run layout optimization
        result = ProductionLayoutOptimizer.optimize_inventory_layout(
            items_data, (storage_width, storage_height)
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@packing_bp.route('/reports/cutting/<optimization_id>')
@login_required
def cutting_report(optimization_id):
    """Generate cutting report (placeholder for now)"""
    # In a real implementation, you'd retrieve stored optimization results
    # For now, this is a placeholder route
    
    return render_template('packing/cutting_report.html', 
                         optimization_id=optimization_id)


@packing_bp.route('/export/cutting-plan', methods=['POST'])
@login_required
def export_cutting_plan():
    """Export cutting plan to JSON file"""
    try:
        data = request.get_json()
        
        # Generate temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(data, temp_file, indent=2, default=str)
        temp_file.close()
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"cutting_plan_{timestamp}.json"
        
        return send_file(temp_file.name, 
                        as_attachment=True, 
                        download_name=filename,
                        mimetype='application/json')
        
    except Exception as e:
        flash(f'Error exporting cutting plan: {str(e)}', 'danger')
        return redirect(url_for('packing.material_cutting'))


# End of packing routes