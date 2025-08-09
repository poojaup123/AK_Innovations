from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms import PurchaseOrderForm, SupplierForm
from models import PurchaseOrder, PurchaseOrderItem, Supplier, Item, DeliverySchedule, CompanySettings, BOMItem, MaterialInspection
from models.uom import ItemUOMConversion, UnitOfMeasure
from models.accounting import Account, AccountGroup
from app import db
from utils.documents import get_documents_for_transaction
from sqlalchemy import func
from datetime import datetime
from utils import generate_po_number
from services.notification_helpers import send_email_notification, send_whatsapp_notification, send_email_with_attachment
from services.authentic_accounting_integration import AuthenticAccountingIntegration

purchase_bp = Blueprint('purchase', __name__)

def number_to_words(num):
    """Convert number to words for amounts"""
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", 
            "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    if num == 0:
        return "zero"
    
    if num < 20:
        return ones[num]
    elif num < 100:
        return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
    elif num < 1000:
        return ones[num // 100] + " hundred" + (" " + number_to_words(num % 100) if num % 100 != 0 else "")
    elif num < 100000:
        return number_to_words(num // 1000) + " thousand" + (" " + number_to_words(num % 1000) if num % 1000 != 0 else "")
    elif num < 10000000:
        return number_to_words(num // 100000) + " lakh" + (" " + number_to_words(num % 100000) if num % 100000 != 0 else "")
    else:
        return number_to_words(num // 10000000) + " crore" + (" " + number_to_words(num % 10000000) if num % 10000000 != 0 else "")

@purchase_bp.route('/dashboard')
@login_required
def dashboard():
    # Purchase statistics
    stats = {
        'total_pos': PurchaseOrder.query.count(),
        'draft_pos': PurchaseOrder.query.filter_by(status='draft').count(),
        'sent_pos': PurchaseOrder.query.filter_by(status='sent').count(),
        'partial_pos': PurchaseOrder.query.filter_by(status='partial').count(),
        'closed_pos': PurchaseOrder.query.filter_by(status='closed').count(),
        'cancelled_pos': PurchaseOrder.query.filter_by(status='cancelled').count(),
        'total_suppliers': Supplier.query.count()
    }
    
    # Get all active purchase orders (not just recent ones) for comprehensive status table
    # Include orders in sent, partial, and closed status for complete visibility
    recent_pos = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_(['sent', 'partial', 'closed'])
    ).order_by(PurchaseOrder.created_at.desc()).limit(20).all()
    
    # Top suppliers by order count
    top_suppliers = db.session.query(
        Supplier.name, 
        func.count(PurchaseOrder.id).label('order_count')
    ).join(PurchaseOrder).group_by(Supplier.id).order_by(func.count(PurchaseOrder.id).desc()).limit(5).all()
    
    return render_template('purchase/dashboard.html', 
                         stats=stats, 
                         recent_pos=recent_pos,
                         top_suppliers=top_suppliers)

@purchase_bp.route('/status-report')
@login_required
def status_report():
    """Purchase Order Delivery & Inspection Status Report"""
    # Get detailed PO status with inspection summary
    query = """
    SELECT 
        po.po_number,
        po.status,
        po.inspection_status,
        s.name as supplier_name,
        poi.item_id,
        i.name as item_name,
        poi.quantity_ordered,
        COALESCE(SUM(mi.received_quantity), 0) as total_received,
        COALESCE(SUM(mi.inspected_quantity), 0) as total_inspected,
        COALESCE(SUM(mi.passed_quantity), 0) as total_passed,
        COALESCE(SUM(mi.rejected_quantity), 0) as total_rejected,
        (poi.quantity_ordered - COALESCE(SUM(mi.received_quantity), 0)) as pending_quantity,
        ROUND((COALESCE(SUM(mi.received_quantity), 0) * 100.0 / poi.quantity_ordered)::numeric, 1) as delivery_percentage,
        ROUND((COALESCE(SUM(mi.passed_quantity), 0) * 100.0 / NULLIF(COALESCE(SUM(mi.inspected_quantity), 0), 0))::numeric, 1) as pass_percentage
    FROM purchase_orders po
    JOIN suppliers s ON po.supplier_id = s.id
    JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
    JOIN items i ON poi.item_id = i.id
    LEFT JOIN material_inspections mi ON po.id = mi.purchase_order_id AND poi.item_id = mi.item_id
    WHERE po.status != 'cancelled'
    GROUP BY po.po_number, po.status, po.inspection_status, s.name, poi.item_id, i.name, poi.quantity_ordered
    ORDER BY po.po_number
    """
    
    result = db.session.execute(db.text(query))
    po_details = [dict(row._mapping) for row in result]
    
    return render_template('purchase/status_report.html',
                         title='PO Delivery & Inspection Status',
                         po_details=po_details)

@purchase_bp.route('/list')
@login_required
def list_purchase_orders():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    supplier_filter = request.args.get('supplier', '', type=str)
    from_date = request.args.get('from_date', '', type=str)
    to_date = request.args.get('to_date', '', type=str)
    search_term = request.args.get('search', '', type=str)
    
    query = PurchaseOrder.query
    
    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
        
    if supplier_filter:
        query = query.filter_by(supplier_id=supplier_filter)
        
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            query = query.filter(PurchaseOrder.order_date >= from_date_obj)
        except ValueError:
            flash('Invalid from date format', 'error')
            
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            query = query.filter(PurchaseOrder.order_date <= to_date_obj)
        except ValueError:
            flash('Invalid to date format', 'error')
            
    if search_term:
        query = query.filter(PurchaseOrder.po_number.ilike(f'%{search_term}%'))
    
    # Order by date descending
    query = query.order_by(PurchaseOrder.order_date.desc())
    
    # Paginate results
    pos = query.paginate(page=page, per_page=20, error_out=False)
    
    # Get all suppliers for filter dropdown
    suppliers = Supplier.query.filter(Supplier.partner_type.in_(['supplier', 'both'])).order_by(Supplier.name).all()
    
    return render_template('purchase/list.html', 
                         pos=pos, 
                         status_filter=status_filter,
                         supplier_filter=supplier_filter,
                         from_date=from_date,
                         to_date=to_date,
                         search_term=search_term,
                         suppliers=suppliers)

@purchase_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_purchase_order():
    form = PurchaseOrderForm()
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.all()]
    
    # Check if coming from production suggestion
    from_suggestion = request.args.get('from_suggestion')
    production_id = request.args.get('production_id')
    suggested_item_id = request.args.get('item_id')
    suggested_quantity = request.args.get('quantity')
    suggested_materials = request.args.get('materials')  # Comma-separated material IDs
    suggested_quantities = request.args.get('quantities')  # Comma-separated quantities
    
    # Auto-generate PO number if not provided
    if not form.po_number.data:
        form.po_number.data = generate_po_number()
    
    if form.validate_on_submit():
        try:
            # Check if PO number already exists
            existing_po = PurchaseOrder.query.filter_by(po_number=form.po_number.data).first()
            if existing_po:
                flash('PO number already exists', 'danger')
                items = Item.query.all()
                return render_template('purchase/form_enhanced.html', form=form, title='Add Purchase Order', items=items)
            
            po = PurchaseOrder(
                po_number=form.po_number.data,
                supplier_id=form.supplier_id.data,
                order_date=form.po_date.data,
                expected_date=form.delivery_date.data,
                payment_terms=form.payment_terms.data,
                freight_terms=form.freight_terms.data,
                validity_months=form.validity_months.data,
                prepared_by=form.prepared_by.data,
                verified_by=form.verified_by.data,
                approved_by=form.approved_by.data,
                delivery_notes=form.delivery_notes.data,
                status='sent',  # New purchase orders automatically start as sent
                notes=form.notes.data,
                created_by=current_user.id
            )
            db.session.add(po)
            db.session.flush()  # Get the PO ID
            
            # Process enhanced PO items from form
            process_po_items(po, request.form)
            
            # Create accounting entries for PO commitment
            from services.accounting_automation import AccountingAutomation
            accounting_result = AccountingAutomation.create_purchase_order_voucher(po)
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating Purchase Order: {str(e)}', 'danger')
            items = Item.query.all()
            return render_template('purchase/form_enhanced.html', form=form, title='Add Purchase Order', items=items)
        
        # Send notifications
        from services.comprehensive_notifications import comprehensive_notification_service
        try:
            # Send to vendor if contact info available
            vendor_contact = {
                'email': po.supplier.email if hasattr(po.supplier, 'email') and po.supplier.email else None,
                'phone': po.supplier.phone if hasattr(po.supplier, 'phone') and po.supplier.phone else None
            }
            comprehensive_notification_service.notify_po_created(po, vendor_contact)
        except Exception as e:
            print(f"Notification error: {e}")
        
        if accounting_result:
            flash('Purchase Order created successfully with accounting entries', 'success')
        else:
            flash('Purchase Order created successfully but accounting integration failed', 'warning')
        
        return redirect(url_for('purchase.list_purchase_orders'))
    
    # Get items with BOM rates and UOM conversion data
    items_data = db.session.query(Item, BOMItem.unit_cost, ItemUOMConversion).outerjoin(
        BOMItem, Item.id == BOMItem.item_id
    ).outerjoin(
        ItemUOMConversion, Item.id == ItemUOMConversion.item_id
    ).all()
    
    items = []
    pre_filled_items = []
    
    for item, bom_rate, uom_conversion in items_data:
        # Set BOM rate as base rate
        base_rate = bom_rate if bom_rate is not None else item.unit_price
        
        # Calculate purchase unit rate if UOM conversion exists
        if uom_conversion:
            # Get unit symbols for better understanding
            purchase_unit = UnitOfMeasure.query.get(uom_conversion.purchase_unit_id)
            sale_unit = UnitOfMeasure.query.get(uom_conversion.sale_unit_id)
            
            # Check if we have a weight-to-count conversion (Kg to Pcs)
            if (uom_conversion.inventory_to_sale and uom_conversion.inventory_to_sale > 0 and 
                purchase_unit and sale_unit and purchase_unit.symbol == 'Kg' and sale_unit.symbol == 'Pcs'):
                # Convert piece price to kg price: ₹1/piece × 100 pieces/kg = ₹100/kg
                purchase_rate = base_rate * float(uom_conversion.inventory_to_sale)
                item.purchase_rate = purchase_rate
            else:
                item.purchase_rate = base_rate
                
            # Get purchase unit symbol for display
            item.purchase_unit = purchase_unit.symbol if purchase_unit else item.unit_of_measure
        else:
            item.purchase_rate = base_rate
            item.purchase_unit = item.unit_of_measure
            
        # Keep original fields for backward compatibility
        item.bom_rate = item.purchase_rate
        items.append(item)
    
    # Pre-fill items from suggestion parameters
    if from_suggestion:
        if suggested_item_id:
            # Single item from suggestion
            try:
                item_id = int(suggested_item_id)
                suggested_item = Item.query.get(item_id)
                if suggested_item:
                    quantity = float(suggested_quantity) if suggested_quantity else 1.0
                    pre_filled_items.append({
                        'item_id': item_id,
                        'item_code': suggested_item.code,
                        'item_name': suggested_item.name,
                        'quantity': quantity,
                        'unit': suggested_item.unit_of_measure,
                        'rate': suggested_item.unit_price or 0.0
                    })
            except (ValueError, TypeError):
                pass
                
        elif suggested_materials:
            # Multiple materials from suggestion
            try:
                material_ids = [int(mid) for mid in suggested_materials.split(',')]
                quantities = []
                if suggested_quantities:
                    quantities = [float(q) for q in suggested_quantities.split(',')]
                
                for i, material_id in enumerate(material_ids):
                    material = Item.query.get(material_id)
                    if material:
                        # Use actual shortage quantity if available, otherwise default to 1.0
                        quantity = quantities[i] if i < len(quantities) else 1.0
                        pre_filled_items.append({
                            'item_id': material_id,
                            'item_code': material.code,
                            'item_name': material.name,
                            'quantity': quantity,
                            'unit': material.unit_of_measure,
                            'rate': material.unit_price or 0.0
                        })
            except (ValueError, TypeError):
                pass
    
    return render_template('purchase/form_enhanced.html', 
                         form=form, 
                         title='Add Purchase Order', 
                         items=items,
                         pre_filled_items=pre_filled_items,
                         from_suggestion=from_suggestion,
                         production_id=production_id)

@purchase_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_purchase_order(id):
    po = PurchaseOrder.query.get_or_404(id)
    form = PurchaseOrderForm()
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.all()]
    
    # Populate form with existing data
    if request.method == 'GET':
        form.po_number.data = po.po_number
        form.supplier_id.data = po.supplier_id
        form.po_date.data = po.order_date
        form.delivery_date.data = po.expected_date
        form.payment_terms.data = po.payment_terms
        form.freight_terms.data = po.freight_terms
        form.validity_months.data = po.validity_months
        form.prepared_by.data = po.prepared_by
        form.verified_by.data = po.verified_by
        form.approved_by.data = po.approved_by
        form.delivery_notes.data = po.delivery_notes
        form.status.data = po.status
        form.notes.data = po.notes
    
    if form.validate_on_submit():
        # Check if PO number already exists (excluding current PO)
        existing_po = PurchaseOrder.query.filter(
            PurchaseOrder.po_number == form.po_number.data, 
            PurchaseOrder.id != id
        ).first()
        if existing_po:
            flash('PO number already exists', 'danger')
            po_items = PurchaseOrderItem.query.filter_by(purchase_order_id=id).all()
            # Get items with BOM rates where available
            items_data = db.session.query(Item, BOMItem.unit_cost).outerjoin(BOMItem, Item.id == BOMItem.item_id).all()
            items = []
            for item, bom_rate in items_data:
                item.bom_rate = bom_rate if bom_rate is not None else item.unit_price
                items.append(item)
            return render_template('purchase/form_enhanced.html', form=form, title='Edit Purchase Order', po=po, po_items=po_items, items=items)
        
        po.po_number = form.po_number.data
        po.supplier_id = form.supplier_id.data
        po.order_date = form.po_date.data
        po.expected_date = form.delivery_date.data
        po.payment_terms = form.payment_terms.data
        po.freight_terms = form.freight_terms.data
        po.validity_months = form.validity_months.data
        po.prepared_by = form.prepared_by.data
        po.verified_by = form.verified_by.data
        po.approved_by = form.approved_by.data
        po.delivery_notes = form.delivery_notes.data
        # Status is automatically managed by GRN system - don't allow manual changes except cancel
        if form.status.data == 'cancelled':
            po.status = 'cancelled'  # Only allow manual cancellation
        # All other status changes (sent/partial/closed) are automatic via GRN
        po.notes = form.notes.data
        
        # Process enhanced PO items from form
        process_po_items(po, request.form)
        
        db.session.commit()
        flash('Purchase Order updated successfully', 'success')
        return redirect(url_for('purchase.list_purchase_orders'))
    
    # Get PO items for display
    po_items = PurchaseOrderItem.query.filter_by(purchase_order_id=id).all()
    # Get items with BOM rates and UOM conversion data
    items_data = db.session.query(Item, BOMItem.unit_cost, ItemUOMConversion).outerjoin(
        BOMItem, Item.id == BOMItem.item_id
    ).outerjoin(
        ItemUOMConversion, Item.id == ItemUOMConversion.item_id
    ).all()
    
    items = []
    for item, bom_rate, uom_conversion in items_data:
        # Set BOM rate as base rate
        base_rate = bom_rate if bom_rate is not None else item.unit_price
        
        # Calculate purchase unit rate if UOM conversion exists
        if uom_conversion:
            # Get unit symbols for better understanding
            purchase_unit = UnitOfMeasure.query.get(uom_conversion.purchase_unit_id)
            sale_unit = UnitOfMeasure.query.get(uom_conversion.sale_unit_id)
            
            # Check if we have a weight-to-count conversion (Kg to Pcs)
            if (uom_conversion.inventory_to_sale and uom_conversion.inventory_to_sale > 0 and 
                purchase_unit and sale_unit and purchase_unit.symbol == 'Kg' and sale_unit.symbol == 'Pcs'):
                # Convert piece price to kg price: ₹1/piece × 100 pieces/kg = ₹100/kg
                purchase_rate = base_rate * float(uom_conversion.inventory_to_sale)
                item.purchase_rate = purchase_rate
            else:
                item.purchase_rate = base_rate
                
            # Get purchase unit symbol for display
            item.purchase_unit = purchase_unit.symbol if purchase_unit else item.unit_of_measure
        else:
            item.purchase_rate = base_rate
            item.purchase_unit = item.unit_of_measure
            
        # Keep original fields for backward compatibility
        item.bom_rate = item.purchase_rate
        items.append(item)
    
    return render_template('purchase/form_enhanced.html', 
                         form=form, 
                         title='Edit Purchase Order', 
                         po=po, 
                         po_items=po_items, 
                         items=items)

@purchase_bp.route('/suppliers')
@login_required
def list_suppliers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    query = Supplier.query
    if search:
        query = query.filter(Supplier.name.contains(search))
    
    suppliers = query.order_by(Supplier.name).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('purchase/suppliers.html', suppliers=suppliers, search=search)

@purchase_bp.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    form = SupplierForm()
    
    # Handle partner type from URL parameter (for sales integration)
    partner_type = request.args.get('partner_type', 'supplier')
    if not form.partner_type.data:
        form.partner_type.data = partner_type
    
    if form.validate_on_submit():
        supplier = Supplier(
            name=form.name.data,
            contact_person=form.contact_person.data,
            phone=form.phone.data,
            email=form.email.data,
            partner_type=form.partner_type.data,
            gst_number=form.gst_number.data,
            pan_number=form.pan_number.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            pin_code=form.pin_code.data,
            account_number=form.account_number.data,
            bank_name=form.bank_name.data,
            ifsc_code=form.ifsc_code.data,
            freight_rate_per_unit=form.freight_rate_per_unit.data or 0.0,
            freight_unit_type=form.freight_unit_type.data or 'per_km',
            remarks=form.remarks.data,
            is_active=form.is_active.data
        )
        db.session.add(supplier)
        db.session.flush()  # Get the ID before committing
        
        # Create accounting ledger entry for the business partner
        try:
            account = AuthenticAccountingIntegration.get_or_create_party_account(supplier)
            if account:
                flash(f'Business Partner "{supplier.name}" and accounting ledger account "{account.name}" created successfully!', 'success')
            else:
                flash(f'Business Partner "{supplier.name}" created successfully, but accounting ledger creation failed. Please check accounting setup.', 'warning')
        except Exception as e:
            flash(f'Business Partner "{supplier.name}" created successfully, but accounting integration error: {str(e)}', 'warning')
            
        db.session.commit()
        return redirect(url_for('purchase.list_suppliers'))
    
    return render_template('purchase/supplier_form.html', form=form, title='Add Supplier')

@purchase_bp.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    form = SupplierForm(obj=supplier)
    
    if form.validate_on_submit():
        # Store original name to check if it changed
        original_name = supplier.name
        
        supplier.name = form.name.data
        supplier.contact_person = form.contact_person.data
        supplier.phone = form.phone.data
        supplier.email = form.email.data
        supplier.partner_type = form.partner_type.data
        supplier.gst_number = form.gst_number.data
        supplier.pan_number = form.pan_number.data
        supplier.address = form.address.data
        supplier.city = form.city.data
        supplier.state = form.state.data
        supplier.pin_code = form.pin_code.data
        supplier.account_number = form.account_number.data
        supplier.bank_name = form.bank_name.data
        supplier.ifsc_code = form.ifsc_code.data
        supplier.freight_rate_per_unit = form.freight_rate_per_unit.data or 0.0
        supplier.freight_unit_type = form.freight_unit_type.data or 'per_km'
        supplier.remarks = form.remarks.data
        supplier.is_active = form.is_active.data
        
        # Update accounting ledger if name changed
        if original_name != supplier.name:
            try:
                # Find existing account and update name
                account = Account.query.filter_by(name=original_name).first()
                if account:
                    account.name = supplier.name
                    flash(f'Business Partner and accounting ledger account updated successfully!', 'success')
                else:
                    # Create new account if doesn't exist
                    account = AuthenticAccountingIntegration.get_or_create_party_account(supplier)
                    if account:
                        flash(f'Business Partner updated and new accounting ledger account created!', 'success')
                    else:
                        flash(f'Business Partner updated, but accounting ledger update failed.', 'warning')
            except Exception as e:
                flash(f'Business Partner updated, but accounting integration error: {str(e)}', 'warning')
        else:
            flash('Business Partner updated successfully', 'success')
        
        db.session.commit()
        return redirect(url_for('purchase.list_suppliers'))
    
    return render_template('purchase/supplier_form.html', form=form, title='Edit Supplier', supplier=supplier)

@purchase_bp.route('/suppliers/delete/<int:id>', methods=['POST', 'GET'])
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    
    # Check if supplier has any purchase orders
    if supplier.purchase_orders:
        flash('Cannot delete supplier with existing purchase orders', 'danger')
        return redirect(url_for('purchase.list_suppliers'))
    
    db.session.delete(supplier)
    db.session.commit()
    flash('Supplier deleted successfully', 'success')
    return redirect(url_for('purchase.list_suppliers'))

@purchase_bp.route('/print/<int:id>')
@login_required  
def print_purchase_order(id):
    po = PurchaseOrder.query.get_or_404(id)
    
    # Convert total amount to words (simple function)
    def number_to_words(num):
        ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", 
                "eighteen", "nineteen"]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        
        if num == 0:
            return "zero"
        
        if num < 20:
            return ones[num]
        elif num < 100:
            return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
        elif num < 1000:
            return ones[num // 100] + " hundred" + (" " + number_to_words(num % 100) if num % 100 != 0 else "")
        elif num < 100000:
            return number_to_words(num // 1000) + " thousand" + (" " + number_to_words(num % 1000) if num % 1000 != 0 else "")
        elif num < 10000000:
            return number_to_words(num // 100000) + " lakh" + (" " + number_to_words(num % 100000) if num % 100000 != 0 else "")
        else:
            return number_to_words(num // 10000000) + " crore" + (" " + number_to_words(num % 10000000) if num % 10000000 != 0 else "")
    
    amount_words = number_to_words(int(po.total_amount))
    company = CompanySettings.get_settings()
    
    return render_template('purchase/po_print_enhanced.html', po=po, amount_words=amount_words, company=company)

@purchase_bp.route('/send/<int:po_id>', methods=['GET', 'POST'])
@login_required
def send_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    
    if request.method == 'POST':
        send_type = request.form.get('send_type')
        recipient = request.form.get('recipient')
        message = request.form.get('message', '')
        
        # Get company info for email
        company = CompanySettings.query.first()
        
        # Create PO summary for message
        po_summary = f"""
Purchase Order: {po.po_number}
Supplier: {po.supplier.name}
Date: {po.order_date}
Expected Delivery: {po.expected_date}
Total Amount: ₹{po.total_amount or 0:.2f}

Items:
"""
        for item in po.items:
            po_summary += f"- {item.item.name}: {item.quantity_ordered} {item.item.unit_of_measure} @ ₹{item.unit_price:.2f}\n"
        
        po_summary += f"\n{message}"
        
        success = False
        if send_type == 'email':
            subject = f"Purchase Order {po.po_number} - {company.company_name if company else 'AK Innovations'}"
            
            # Generate PDF attachment
            from weasyprint import HTML, CSS
            from flask import render_template_string
            
            # Render PO as HTML for PDF conversion
            po_html = render_template('purchase/po_print_enhanced.html', 
                                    po=po, 
                                    amount_words=number_to_words(int(po.total_amount)) if po.total_amount else 'zero',
                                    company=company)
            
            # Convert to PDF
            pdf_bytes = HTML(string=po_html, base_url=request.url_root).write_pdf()
            
            # Send email with PDF attachment
            success = send_email_with_attachment(
                recipient, 
                subject, 
                po_summary,
                pdf_bytes,
                f"PO_{po.po_number}.pdf"
            )
        elif send_type == 'whatsapp':
            success = send_whatsapp_notification(recipient, po_summary)
        
        if success:
            flash(f'Purchase Order sent successfully via {send_type.title()}!', 'success')
            # Status updates are now automatic - PO starts as 'sent'
            # No need to update status when sending since it's already 'sent'
        else:
            flash(f'Failed to send Purchase Order via {send_type.title()}. Please check your notification settings.', 'danger')
        
        return redirect(url_for('purchase.list_purchase_orders'))
    
    return render_template('purchase/send.html', po=po, title=f'Send Purchase Order {po.po_number}')

@purchase_bp.route('/delete/<int:id>', methods=['POST', 'GET'])
@login_required
def delete_purchase_order(id):
    po = PurchaseOrder.query.get_or_404(id)
    
    # Check if user has permission (only admin or creator can delete)
    if not current_user.is_admin() and po.created_by != current_user.id:
        flash('You do not have permission to delete this purchase order', 'danger')
        return redirect(url_for('purchase.list_purchase_orders'))
    
    # Delete related items first
    PurchaseOrderItem.query.filter_by(purchase_order_id=id).delete()
    DeliverySchedule.query.filter_by(purchase_order_id=id).delete()
    
    db.session.delete(po)
    db.session.commit()
    flash('Purchase Order deleted successfully', 'success')
    return redirect(url_for('purchase.list_purchase_orders'))

@purchase_bp.route('/change_status/<int:po_id>', methods=['POST'])
@login_required
def change_po_status(po_id):
    # Only allow cancellation - all other status changes are automatic via GRN
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admins can cancel purchase orders'})
    
    po = PurchaseOrder.query.get_or_404(po_id)
    new_status = request.form.get('status')
    
    # Only allow cancellation
    if new_status != 'cancelled':
        return jsonify({'success': False, 'message': 'Only cancellation is allowed. Status updates are automatic via GRN system.'})
    
    old_status = po.status
    po.status = 'cancelled'
    
    # Close accounting entries when PO is cancelled
    from services.accounting_automation import AccountingAutomation
    accounting_result = AccountingAutomation.close_purchase_order_voucher(po)
    
    db.session.commit()
    
    message = f'Purchase Order {po.po_number} cancelled (was {old_status.title()})'
    if not accounting_result:
        message += ' - Warning: Accounting entries could not be closed'
    
    return jsonify({
        'success': True, 
        'message': message
    })

def process_po_items(po, form_data):
    """Process enhanced PO items with industrial-standard fields"""
    # Clear existing items
    PurchaseOrderItem.query.filter_by(purchase_order_id=po.id).delete()
    
    total_amount = 0
    item_counter = 1
    
    # Process items from form
    for key, value in form_data.items():
        if key.startswith('item_id_') and value and value != '':
            try:
                item_id = int(value)
                
                # Extract item suffix to get related fields
                if '_new_' in key:
                    item_suffix = key.split('_new_')[1]
                    prefix = f'new_{item_suffix}'
                else:
                    item_suffix = key.split('_')[2] if len(key.split('_')) > 2 else key.split('_')[1]
                    prefix = item_suffix
                
                # Get other fields for this item
                rm_code = form_data.get(f'rm_code_{prefix}', '')
                description = form_data.get(f'description_{prefix}', '')
                drawing_spec = form_data.get(f'drawing_spec_{prefix}', '')
                hsn_code = form_data.get(f'hsn_code_{prefix}', '')
                gst_rate = float(form_data.get(f'gst_rate_{prefix}', 18.0) or 18.0)
                material_destination = form_data.get(f'material_destination_{prefix}', 'raw_material')
                uom = form_data.get(f'uom_{prefix}', '')
                qty = float(form_data.get(f'qty_{prefix}', 0) or 0)
                rate = float(form_data.get(f'rate_{prefix}', 0) or 0)
                amount = float(form_data.get(f'amount_{prefix}', 0) or 0)
                
                if qty > 0 and rate > 0:
                    po_item = PurchaseOrderItem(
                        purchase_order_id=po.id,
                        item_id=item_id,
                        sr_no=item_counter,
                        rm_code=rm_code,
                        item_description=description,
                        drawing_spec_no=drawing_spec,
                        hsn_code=hsn_code,
                        gst_rate=gst_rate,
                        material_destination=material_destination,
                        uom=uom,
                        qty=qty,
                        rate=rate,
                        amount=amount,
                        # Legacy fields for compatibility
                        quantity_ordered=qty,
                        unit_price=rate,
                        total_price=amount
                    )
                    db.session.add(po_item)
                    total_amount += amount
                    item_counter += 1
            except (ValueError, TypeError):
                continue  # Skip invalid entries
    
    # Update PO total amount
    po.total_amount = total_amount
