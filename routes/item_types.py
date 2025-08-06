from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import ItemType
from app import db
from wtforms import Form, StringField, TextAreaField, BooleanField, validators

item_types_bp = Blueprint('item_types', __name__, url_prefix='/item-types')

class ItemTypeForm(Form):
    name = StringField('Type Name', [validators.DataRequired(), validators.Length(max=50)])
    description = TextAreaField('Description', [validators.Length(max=200)])
    is_active = BooleanField('Active', default=True)

@item_types_bp.route('/')
@login_required
def list_item_types():
    """List all item types"""
    item_types = ItemType.query.order_by(ItemType.name).all()
    return render_template('item_types/list.html', item_types=item_types)

@item_types_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_item_type():
    """Add new item type"""
    if not current_user.is_admin():
        flash('Only administrators can manage item types', 'error')
        return redirect(url_for('item_types.list_item_types'))
    
    form = ItemTypeForm(request.form)
    
    if request.method == 'POST' and form.validate():
        # Check if name already exists
        existing = ItemType.query.filter_by(name=form.name.data).first()
        if existing:
            flash('Item type with this name already exists', 'error')
            return render_template('item_types/form.html', form=form, title='Add Item Type')
        
        item_type = ItemType(
            name=form.name.data,
            description=form.description.data,
            is_active=form.is_active.data,
            created_by=current_user.id
        )
        db.session.add(item_type)
        db.session.commit()
        flash('Item type added successfully', 'success')
        return redirect(url_for('item_types.list_item_types'))
    
    return render_template('item_types/form.html', form=form, title='Add Item Type')

@item_types_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_item_type(id):
    """Edit existing item type"""
    if not current_user.is_admin():
        flash('Only administrators can manage item types', 'error')
        return redirect(url_for('item_types.list_item_types'))
    
    item_type = ItemType.query.get_or_404(id)
    form = ItemTypeForm(request.form, obj=item_type)
    
    if request.method == 'POST' and form.validate():
        # Check if name already exists (excluding current record)
        existing = ItemType.query.filter(ItemType.name == form.name.data, ItemType.id != id).first()
        if existing:
            flash('Item type with this name already exists', 'error')
            return render_template('item_types/form.html', form=form, title='Edit Item Type', item_type=item_type)
        
        item_type.name = form.name.data
        item_type.description = form.description.data
        item_type.is_active = form.is_active.data
        
        db.session.commit()
        flash('Item type updated successfully', 'success')
        return redirect(url_for('item_types.list_item_types'))
    
    return render_template('item_types/form.html', form=form, title='Edit Item Type', item_type=item_type)

@item_types_bp.route('/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_item_type(id):
    """Toggle item type active status"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    item_type = ItemType.query.get_or_404(id)
    item_type.is_active = not item_type.is_active
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'is_active': item_type.is_active,
        'message': f'Item type {"activated" if item_type.is_active else "deactivated"}'
    })

@item_types_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_item_type(id):
    """Delete item type (only if no items use it)"""
    if not current_user.is_admin():
        flash('Only administrators can manage item types', 'error')
        return redirect(url_for('item_types.list_item_types'))
    
    item_type = ItemType.query.get_or_404(id)
    
    # Check if any items use this type
    if item_type.items:
        flash(f'Cannot delete item type "{item_type.name}" - it is used by {len(item_type.items)} items', 'error')
        return redirect(url_for('item_types.list_item_types'))
    
    db.session.delete(item_type)
    db.session.commit()
    flash('Item type deleted successfully', 'success')
    return redirect(url_for('item_types.list_item_types'))