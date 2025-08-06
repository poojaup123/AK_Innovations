from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Item
from models.uom import UnitOfMeasure, UOMConversion, ItemUOMConversion, UOMConversionLog
from forms_uom import UnitOfMeasureForm, UOMConversionForm, ItemUOMConversionForm, UOMCalculatorForm
from decimal import Decimal

uom_bp = Blueprint('uom', __name__)

@uom_bp.route('/dashboard')
@login_required
def dashboard():
    """UOM management dashboard"""
    # Statistics
    total_units = UnitOfMeasure.query.count()
    total_conversions = UOMConversion.query.filter_by(is_active=True).count()
    items_with_conversions = ItemUOMConversion.query.count()
    conversion_logs_count = UOMConversionLog.query.count()
    
    # Recent items with conversions
    recent_item_conversions = ItemUOMConversion.query.join(Item).order_by(ItemUOMConversion.updated_at.desc()).limit(5).all()
    
    # Items without conversions (potential issues)
    items_without_conversions = Item.query.outerjoin(ItemUOMConversion).filter(ItemUOMConversion.id.is_(None)).limit(10).all()
    
    # Unit categories
    unit_categories = db.session.query(UnitOfMeasure.category, db.func.count(UnitOfMeasure.id)).group_by(UnitOfMeasure.category).all()
    
    return render_template('uom/dashboard.html',
                         total_units=total_units,
                         total_conversions=total_conversions,
                         items_with_conversions=items_with_conversions,
                         conversion_logs_count=conversion_logs_count,
                         recent_item_conversions=recent_item_conversions,
                         items_without_conversions=items_without_conversions,
                         unit_categories=unit_categories)

@uom_bp.route('/units')
@login_required
def units_list():
    """List all units of measure"""
    units = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
    return render_template('uom/units_list.html', units=units)

@uom_bp.route('/units/add', methods=['GET', 'POST'])
@login_required
def add_unit():
    """Add new unit of measure"""
    form = UnitOfMeasureForm()
    
    if form.validate_on_submit():
        unit = UnitOfMeasure(
            name=form.name.data,
            symbol=form.symbol.data,
            category=form.category.data,
            is_base_unit=form.is_base_unit.data,
            description=form.description.data
        )
        
        try:
            db.session.add(unit)
            db.session.commit()
            flash(f'Unit "{unit.name}" created successfully!', 'success')
            return redirect(url_for('uom.units_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating unit: {str(e)}', 'error')
    
    return render_template('uom/unit_form.html', form=form, title='Add Unit of Measure')

@uom_bp.route('/units/edit/<int:unit_id>', methods=['GET', 'POST'])
@login_required
def edit_unit(unit_id):
    """Edit unit of measure"""
    unit = UnitOfMeasure.query.get_or_404(unit_id)
    form = UnitOfMeasureForm(obj=unit)
    
    if form.validate_on_submit():
        form.populate_obj(unit)
        
        try:
            db.session.commit()
            flash(f'Unit "{unit.name}" updated successfully!', 'success')
            return redirect(url_for('uom.units_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating unit: {str(e)}', 'error')
    
    return render_template('uom/unit_form.html', form=form, title='Edit Unit of Measure', unit=unit)

@uom_bp.route('/conversions')
@login_required
def conversions_list():
    """List all UOM conversions"""
    conversions = UOMConversion.query.join(UnitOfMeasure, UOMConversion.from_unit_id == UnitOfMeasure.id)\
                                   .add_columns(UnitOfMeasure.name.label('from_name'), UnitOfMeasure.symbol.label('from_symbol'))\
                                   .join(UnitOfMeasure, UOMConversion.to_unit_id == UnitOfMeasure.id, aliased=True)\
                                   .add_columns(UnitOfMeasure.name.label('to_name'), UnitOfMeasure.symbol.label('to_symbol'))\
                                   .filter(UOMConversion.is_active == True)\
                                   .order_by(UOMConversion.created_at.desc()).all()
    
    return render_template('uom/conversions_list.html', conversions=conversions)

@uom_bp.route('/conversions/add', methods=['GET', 'POST'])
@login_required
def add_conversion():
    """Add new UOM conversion"""
    form = UOMConversionForm()
    
    if form.validate_on_submit():
        # Check if conversion already exists
        existing = UOMConversion.query.filter_by(
            from_unit_id=form.from_unit.data,
            to_unit_id=form.to_unit.data
        ).first()
        
        if existing:
            flash('Conversion between these units already exists!', 'error')
            return render_template('uom/conversion_form.html', form=form, title='Add UOM Conversion')
        
        conversion = UOMConversion(
            from_unit_id=form.from_unit.data,
            to_unit_id=form.to_unit.data,
            conversion_factor=form.conversion_factor.data,
            notes=form.notes.data
        )
        
        try:
            db.session.add(conversion)
            db.session.commit()
            flash('UOM conversion created successfully!', 'success')
            return redirect(url_for('uom.conversions_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating conversion: {str(e)}', 'error')
    
    return render_template('uom/conversion_form.html', form=form, title='Add UOM Conversion')

@uom_bp.route('/item-conversions')
@login_required
def item_conversions_list():
    """List all item-specific UOM conversions"""
    item_conversions = ItemUOMConversion.query.join(Item).order_by(Item.name).all()
    return render_template('uom/item_conversions_list.html', item_conversions=item_conversions)

@uom_bp.route('/item-conversions/add', methods=['GET', 'POST'])
@login_required
def add_item_conversion():
    """Add new item-specific UOM conversion"""
    form = ItemUOMConversionForm()
    
    if form.validate_on_submit():
        # Check if item already has conversion
        existing = ItemUOMConversion.query.filter_by(item_id=form.item.data).first()
        if existing:
            flash('This item already has UOM conversion configured!', 'error')
            return render_template('uom/item_conversion_form.html', form=form, title='Add Item UOM Conversion')
        
        # Calculate derived values
        purchase_to_sale = None
        if form.pieces_per_kg.data and form.weight_per_piece.data:
            # Validate that pieces_per_kg and weight_per_piece are consistent
            calculated_weight = 1.0 / float(form.pieces_per_kg.data)
            if abs(calculated_weight - float(form.weight_per_piece.data)) > 0.001:
                flash('Warning: Weight per piece and pieces per Kg values are inconsistent!', 'warning')
        
        # Calculate purchase to sale conversion if not provided
        purchase_to_sale = float(form.purchase_to_inventory.data) * float(form.inventory_to_sale.data)
        
        item_conversion = ItemUOMConversion(
            item_id=form.item.data,
            purchase_unit_id=form.purchase_unit.data,
            sale_unit_id=form.sale_unit.data,
            inventory_unit_id=form.inventory_unit.data,
            purchase_to_inventory=form.purchase_to_inventory.data,
            inventory_to_sale=form.inventory_to_sale.data,
            purchase_to_sale=purchase_to_sale,
            weight_per_piece=form.weight_per_piece.data,
            pieces_per_kg=form.pieces_per_kg.data,
            notes=form.notes.data
        )
        
        try:
            db.session.add(item_conversion)
            db.session.commit()
            flash('Item UOM conversion created successfully!', 'success')
            return redirect(url_for('uom.item_conversions_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating item conversion: {str(e)}', 'error')
    
    return render_template('uom/item_conversion_form.html', form=form, title='Add Item UOM Conversion')

@uom_bp.route('/item-conversions/edit/<int:conversion_id>', methods=['GET', 'POST'])
@login_required
def edit_item_conversion(conversion_id):
    """Edit item-specific UOM conversion"""
    conversion = ItemUOMConversion.query.get_or_404(conversion_id)
    form = ItemUOMConversionForm()
    
    if request.method == 'GET':
        # Manually populate form fields for GET request
        form.item.data = conversion.item_id
        form.purchase_unit.data = conversion.purchase_unit_id
        form.inventory_unit.data = conversion.inventory_unit_id
        form.sale_unit.data = conversion.sale_unit_id
        form.purchase_to_inventory.data = conversion.purchase_to_inventory
        form.inventory_to_sale.data = conversion.inventory_to_sale
        form.weight_per_piece.data = conversion.weight_per_piece
        form.pieces_per_kg.data = conversion.pieces_per_kg
        form.notes.data = conversion.notes
    
    if form.validate_on_submit():
        # Manually update fields to avoid SQLAlchemy relationship issues
        conversion.item_id = form.item.data
        conversion.purchase_unit_id = form.purchase_unit.data
        conversion.inventory_unit_id = form.inventory_unit.data
        conversion.sale_unit_id = form.sale_unit.data
        conversion.purchase_to_inventory = form.purchase_to_inventory.data
        conversion.inventory_to_sale = form.inventory_to_sale.data
        conversion.weight_per_piece = form.weight_per_piece.data
        conversion.pieces_per_kg = form.pieces_per_kg.data
        conversion.notes = form.notes.data
        
        # Recalculate purchase to sale conversion
        conversion.purchase_to_sale = float(conversion.purchase_to_inventory) * float(conversion.inventory_to_sale)
        
        try:
            db.session.commit()
            flash('Item UOM conversion updated successfully!', 'success')
            return redirect(url_for('uom.item_conversions_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating conversion: {str(e)}', 'error')
    
    return render_template('uom/item_conversion_form.html', form=form, title='Edit Item UOM Conversion', conversion=conversion)

@uom_bp.route('/calculator', methods=['GET', 'POST'])
@login_required
def calculator():
    """UOM calculator for quick conversions"""
    form = UOMCalculatorForm()
    result = None
    
    if form.validate_on_submit():
        item = Item.query.get(form.item.data)
        item_conversion = ItemUOMConversion.query.filter_by(item_id=form.item.data).first()
        
        if not item_conversion:
            flash('No UOM conversion configured for this item!', 'error')
            return render_template('uom/calculator.html', form=form, result=result)
        
        quantity = float(form.quantity.data)
        from_unit = UnitOfMeasure.query.get(form.from_unit.data)
        to_unit = UnitOfMeasure.query.get(form.to_unit.data)
        
        try:
            # Determine conversion path
            converted_qty = None
            conversion_path = ""
            
            if from_unit.id == item_conversion.purchase_unit_id and to_unit.id == item_conversion.inventory_unit_id:
                converted_qty = item_conversion.convert_purchase_to_inventory(quantity)
                conversion_path = f"Purchase → Inventory (×{item_conversion.purchase_to_inventory})"
            elif from_unit.id == item_conversion.inventory_unit_id and to_unit.id == item_conversion.sale_unit_id:
                converted_qty = item_conversion.convert_inventory_to_sale(quantity)
                conversion_path = f"Inventory → Sale (×{item_conversion.inventory_to_sale})"
            elif from_unit.id == item_conversion.sale_unit_id and to_unit.id == item_conversion.inventory_unit_id:
                converted_qty = item_conversion.convert_sale_to_inventory(quantity)
                conversion_path = f"Sale → Inventory (÷{item_conversion.inventory_to_sale})"
            elif from_unit.id == item_conversion.purchase_unit_id and to_unit.id == item_conversion.sale_unit_id:
                converted_qty = item_conversion.convert_purchase_to_sale(quantity)
                conversion_path = f"Purchase → Sale (×{item_conversion.purchase_to_sale})"
            else:
                flash('No conversion path available between selected units for this item!', 'error')
                return render_template('uom/calculator.html', form=form, result=result)
            
            result = {
                'item': item,
                'original_qty': quantity,
                'from_unit': from_unit,
                'converted_qty': round(converted_qty, 6),
                'to_unit': to_unit,
                'conversion_path': conversion_path
            }
            
            # Log the conversion
            log_entry = UOMConversionLog(
                item_id=item.id,
                transaction_type='calculation',
                original_quantity=quantity,
                original_unit_id=from_unit.id,
                converted_quantity=converted_qty,
                converted_unit_id=to_unit.id,
                conversion_factor=converted_qty / quantity if quantity > 0 else 0,
                created_by=current_user.id
            )
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            flash(f'Error calculating conversion: {str(e)}', 'error')
    
    return render_template('uom/calculator.html', form=form, result=result)

@uom_bp.route('/api/item-uom-info/<int:item_id>')
@login_required
def get_item_uom_info(item_id):
    """API endpoint to get UOM information for an item"""
    item_conversion = ItemUOMConversion.query.filter_by(item_id=item_id).first()
    
    if not item_conversion:
        return jsonify({'has_conversion': False})
    
    return jsonify({
        'has_conversion': True,
        'purchase_unit': {
            'id': item_conversion.purchase_unit.id,
            'name': item_conversion.purchase_unit.name,
            'symbol': item_conversion.purchase_unit.symbol
        },
        'inventory_unit': {
            'id': item_conversion.inventory_unit.id,
            'name': item_conversion.inventory_unit.name,
            'symbol': item_conversion.inventory_unit.symbol
        },
        'sale_unit': {
            'id': item_conversion.sale_unit.id,
            'name': item_conversion.sale_unit.name,
            'symbol': item_conversion.sale_unit.symbol
        },
        'purchase_to_inventory': float(item_conversion.purchase_to_inventory),
        'inventory_to_sale': float(item_conversion.inventory_to_sale),
        'purchase_to_sale': float(item_conversion.purchase_to_sale or 0),
        'weight_per_piece': float(item_conversion.weight_per_piece or 0),
        'pieces_per_kg': float(item_conversion.pieces_per_kg or 0)
    })

@uom_bp.route('/api/convert-quantity', methods=['POST'])
@login_required
def convert_quantity():
    """API endpoint for quantity conversion"""
    data = request.get_json()
    item_id = data.get('item_id')
    quantity = float(data.get('quantity', 0))
    from_unit_id = data.get('from_unit_id')
    to_unit_id = data.get('to_unit_id')
    
    item_conversion = ItemUOMConversion.query.filter_by(item_id=item_id).first()
    
    if not item_conversion:
        return jsonify({'error': 'No UOM conversion configured for this item'}), 400
    
    try:
        converted_qty = None
        
        if from_unit_id == item_conversion.purchase_unit_id and to_unit_id == item_conversion.inventory_unit_id:
            converted_qty = item_conversion.convert_purchase_to_inventory(quantity)
        elif from_unit_id == item_conversion.inventory_unit_id and to_unit_id == item_conversion.sale_unit_id:
            converted_qty = item_conversion.convert_inventory_to_sale(quantity)
        elif from_unit_id == item_conversion.sale_unit_id and to_unit_id == item_conversion.inventory_unit_id:
            converted_qty = item_conversion.convert_sale_to_inventory(quantity)
        elif from_unit_id == item_conversion.purchase_unit_id and to_unit_id == item_conversion.sale_unit_id:
            converted_qty = item_conversion.convert_purchase_to_sale(quantity)
        else:
            return jsonify({'error': 'No conversion path available between these units'}), 400
        
        return jsonify({
            'converted_quantity': round(converted_qty, 6),
            'original_quantity': quantity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500