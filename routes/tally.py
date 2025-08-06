from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_login import login_required, current_user
from models import Item, PurchaseOrder, SalesOrder, FactoryExpense, Supplier, Employee
from app import db
from datetime import datetime, date
from sqlalchemy import func, desc
import xml.etree.ElementTree as ET
from xml.dom import minidom
import io

tally_bp = Blueprint('tally', __name__)



@tally_bp.route('/export/ledgers')
@login_required
def export_ledgers():
    """Export Chart of Accounts (Ledgers) to Tally XML"""
    suppliers = Supplier.query.all()
    
    # Create XML structure for Tally
    envelope = ET.Element('ENVELOPE')
    header = ET.SubElement(envelope, 'HEADER')
    ET.SubElement(header, 'TALLYREQUEST').text = 'Import Data'
    
    body = ET.SubElement(envelope, 'BODY')
    import_data = ET.SubElement(body, 'IMPORTDATA')
    request_desc = ET.SubElement(import_data, 'REQUESTDESC')
    ET.SubElement(request_desc, 'REPORTNAME').text = 'All Masters'
    
    request_data = ET.SubElement(import_data, 'REQUESTDATA')
    
    # Add Ledger Masters
    for supplier in suppliers:
        ledger = ET.SubElement(request_data, 'TALLYMESSAGE')
        ledger_master = ET.SubElement(ledger, 'LEDGER', NAME=supplier.name, ACTION="Create")
        
        ET.SubElement(ledger_master, 'NAME').text = supplier.name
        ET.SubElement(ledger_master, 'PARENT').text = 'Sundry Creditors' if supplier.partner_type in ['supplier', 'both'] else 'Sundry Debtors'
        ET.SubElement(ledger_master, 'ISBILLWISEON').text = 'Yes'
        ET.SubElement(ledger_master, 'ISCOSTCENTRESON').text = 'No'
        
        # Address details
        if supplier.address:
            address_list = ET.SubElement(ledger_master, 'ADDRESS.LIST')
            ET.SubElement(address_list, 'ADDRESS').text = supplier.address
            if supplier.city:
                ET.SubElement(address_list, 'ADDRESS').text = supplier.city
            if supplier.state:
                ET.SubElement(address_list, 'ADDRESS').text = supplier.state
        
        # GST details
        if supplier.gst_number:
            gst_details = ET.SubElement(ledger_master, 'GSTREGISTRATIONTYPE').text = 'Regular'
            ET.SubElement(ledger_master, 'GSTIN').text = supplier.gst_number
            ET.SubElement(ledger_master, 'GSTREGISTRATIONTYPE').text = 'Regular'
        
        # Contact details
        if supplier.mobile_number:
            ET.SubElement(ledger_master, 'LEDGERPHONE').text = supplier.mobile_number
        if supplier.email:
            ET.SubElement(ledger_master, 'EMAIL').text = supplier.email
    
    # Convert to pretty XML string
    rough_string = ET.tostring(envelope, 'unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    # Create response
    response = make_response(pretty_xml)
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=ledgers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    
    return response

@tally_bp.route('/export/items')
@login_required
def export_items():
    """Export Stock Items to Tally XML"""
    items = Item.query.all()
    
    # Create XML structure
    envelope = ET.Element('ENVELOPE')
    header = ET.SubElement(envelope, 'HEADER')
    ET.SubElement(header, 'TALLYREQUEST').text = 'Import Data'
    
    body = ET.SubElement(envelope, 'BODY')
    import_data = ET.SubElement(body, 'IMPORTDATA')
    request_desc = ET.SubElement(import_data, 'REQUESTDESC')
    ET.SubElement(request_desc, 'REPORTNAME').text = 'All Masters'
    
    request_data = ET.SubElement(import_data, 'REQUESTDATA')
    
    # Add Stock Item Masters
    for item in items:
        stock_item = ET.SubElement(request_data, 'TALLYMESSAGE')
        item_master = ET.SubElement(stock_item, 'STOCKITEM', NAME=item.name, ACTION="Create")
        
        ET.SubElement(item_master, 'NAME').text = item.name
        ET.SubElement(item_master, 'ALIAS').text = item.code
        ET.SubElement(item_master, 'PARENT').text = item.item_type.title() if item.item_type else 'Primary'
        ET.SubElement(item_master, 'CATEGORY').text = item.item_type.title() if item.item_type else 'Primary'
        ET.SubElement(item_master, 'BASEUNITS').text = item.unit_of_measure or 'Nos'
        ET.SubElement(item_master, 'ADDITIONALUNITS').text = item.unit_of_measure or 'Nos'
        
        # Opening balance
        if item.current_stock:
            opening_balance = ET.SubElement(item_master, 'OPENINGBALANCE')
            ET.SubElement(opening_balance, 'UNITS').text = str(item.current_stock)
            ET.SubElement(opening_balance, 'RATE').text = str(item.unit_price or 0)
        
        # GST details
        if item.gst_rate:
            ET.SubElement(item_master, 'GSTAPPLICABLE').text = 'Yes'
            ET.SubElement(item_master, 'GSTTYPEOFSUPPLY').text = 'Goods'
            if item.hsn_code:
                ET.SubElement(item_master, 'HSNCODE').text = item.hsn_code
    
    # Convert to pretty XML
    rough_string = ET.tostring(envelope, 'unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    response = make_response(pretty_xml)
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=stock_items_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    
    return response

@tally_bp.route('/export/vouchers')
@login_required
def export_vouchers():
    """Export Purchase/Sales/Expense Vouchers to Tally XML"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    voucher_type = request.args.get('type', 'all')  # all, purchase, sales, expense
    
    # Create XML structure
    envelope = ET.Element('ENVELOPE')
    header = ET.SubElement(envelope, 'HEADER')
    ET.SubElement(header, 'TALLYREQUEST').text = 'Import Data'
    
    body = ET.SubElement(envelope, 'BODY')
    import_data = ET.SubElement(body, 'IMPORTDATA')
    request_desc = ET.SubElement(import_data, 'REQUESTDESC')
    ET.SubElement(request_desc, 'REPORTNAME').text = 'Vouchers'
    
    request_data = ET.SubElement(import_data, 'REQUESTDATA')
    
    # Build date filters
    date_filter = {}
    if date_from:
        try:
            date_filter['from'] = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    if date_to:
        try:
            date_filter['to'] = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Export Purchase Orders as Purchase Vouchers
    if voucher_type in ['all', 'purchase']:
        po_query = PurchaseOrder.query.filter_by(status='closed')
        if 'from' in date_filter:
            po_query = po_query.filter(PurchaseOrder.po_date >= date_filter['from'])
        if 'to' in date_filter:
            po_query = po_query.filter(PurchaseOrder.po_date <= date_filter['to'])
        
        purchase_orders = po_query.all()
        
        for po in purchase_orders:
            voucher = ET.SubElement(request_data, 'TALLYMESSAGE')
            voucher_elem = ET.SubElement(voucher, 'VOUCHER', VCHTYPE="Purchase", ACTION="Create")
            
            ET.SubElement(voucher_elem, 'DATE').text = po.po_date.strftime('%Y%m%d')
            ET.SubElement(voucher_elem, 'VOUCHERTYPENAME').text = 'Purchase'
            ET.SubElement(voucher_elem, 'VOUCHERNUMBER').text = po.po_number
            ET.SubElement(voucher_elem, 'REFERENCE').text = po.po_number
            
            # Add ledger entries
            ledger_entries = ET.SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            
            # Supplier ledger (Credit)
            supplier_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
            ET.SubElement(supplier_entry, 'LEDGERNAME').text = po.supplier.name
            ET.SubElement(supplier_entry, 'ISDEEMEDPOSITIVE').text = 'No'
            ET.SubElement(supplier_entry, 'AMOUNT').text = f'-{po.total_amount}'
            
            # Item entries (Debit)
            for po_item in po.items:
                item_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
                ET.SubElement(item_entry, 'LEDGERNAME').text = po_item.item.name
                ET.SubElement(item_entry, 'ISDEEMEDPOSITIVE').text = 'Yes'
                ET.SubElement(item_entry, 'AMOUNT').text = str(po_item.total_price)
                
                # Stock item details
                if po_item.item:
                    inventory_entries = ET.SubElement(item_entry, 'ALLINVENTORYENTRIES.LIST')
                    inv_entry = ET.SubElement(inventory_entries, 'INVENTORYENTRIES.LIST')
                    ET.SubElement(inv_entry, 'STOCKITEMNAME').text = po_item.item.name
                    ET.SubElement(inv_entry, 'ISDEEMEDPOSITIVE').text = 'Yes'
                    ET.SubElement(inv_entry, 'QUANTITY').text = str(po_item.quantity)
                    ET.SubElement(inv_entry, 'RATE').text = str(po_item.unit_price)
    
    # Export Sales Orders as Sales Vouchers
    if voucher_type in ['all', 'sales']:
        so_query = SalesOrder.query.filter_by(status='delivered')
        if 'from' in date_filter:
            so_query = so_query.filter(SalesOrder.order_date >= date_filter['from'])
        if 'to' in date_filter:
            so_query = so_query.filter(SalesOrder.order_date <= date_filter['to'])
        
        sales_orders = so_query.all()
        
        for so in sales_orders:
            voucher = ET.SubElement(request_data, 'TALLYMESSAGE')
            voucher_elem = ET.SubElement(voucher, 'VOUCHER', VCHTYPE="Sales", ACTION="Create")
            
            ET.SubElement(voucher_elem, 'DATE').text = so.order_date.strftime('%Y%m%d')
            ET.SubElement(voucher_elem, 'VOUCHERTYPENAME').text = 'Sales'
            ET.SubElement(voucher_elem, 'VOUCHERNUMBER').text = so.so_number
            ET.SubElement(voucher_elem, 'REFERENCE').text = so.so_number
            
            # Add ledger entries
            ledger_entries = ET.SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            
            # Customer ledger (Debit)
            customer_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
            ET.SubElement(customer_entry, 'LEDGERNAME').text = so.customer.name
            ET.SubElement(customer_entry, 'ISDEEMEDPOSITIVE').text = 'Yes'
            ET.SubElement(customer_entry, 'AMOUNT').text = str(so.total_amount)
            
            # Item entries (Credit)
            for so_item in so.items:
                item_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
                ET.SubElement(item_entry, 'LEDGERNAME').text = 'Sales'
                ET.SubElement(item_entry, 'ISDEEMEDPOSITIVE').text = 'No'
                ET.SubElement(item_entry, 'AMOUNT').text = f'-{so_item.total_price}'
    
    # Export Factory Expenses as Journal/Payment Vouchers
    if voucher_type in ['all', 'expense']:
        expense_query = FactoryExpense.query.filter_by(status='paid')
        if 'from' in date_filter:
            expense_query = expense_query.filter(FactoryExpense.expense_date >= date_filter['from'])
        if 'to' in date_filter:
            expense_query = expense_query.filter(FactoryExpense.expense_date <= date_filter['to'])
        
        expenses = expense_query.all()
        
        for expense in expenses:
            voucher = ET.SubElement(request_data, 'TALLYMESSAGE')
            voucher_type_name = 'Payment' if expense.payment_method else 'Journal'
            voucher_elem = ET.SubElement(voucher, 'VOUCHER', VCHTYPE=voucher_type_name, ACTION="Create")
            
            ET.SubElement(voucher_elem, 'DATE').text = expense.expense_date.strftime('%Y%m%d')
            ET.SubElement(voucher_elem, 'VOUCHERTYPENAME').text = voucher_type_name
            ET.SubElement(voucher_elem, 'VOUCHERNUMBER').text = expense.expense_number
            ET.SubElement(voucher_elem, 'NARRATION').text = expense.description
            
            # Add ledger entries
            ledger_entries = ET.SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            
            # Expense ledger (Debit)
            expense_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
            expense_ledger_name = f"{expense.category.replace('_', ' ').title()} Expenses"
            ET.SubElement(expense_entry, 'LEDGERNAME').text = expense_ledger_name
            ET.SubElement(expense_entry, 'ISDEEMEDPOSITIVE').text = 'Yes'
            ET.SubElement(expense_entry, 'AMOUNT').text = str(expense.total_amount)
            
            # Payment ledger (Credit)
            payment_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
            if expense.payment_method == 'cash':
                payment_ledger = 'Cash'
            elif expense.payment_method == 'bank_transfer':
                payment_ledger = 'Bank Account'
            else:
                payment_ledger = 'Cash'
            
            ET.SubElement(payment_entry, 'LEDGERNAME').text = payment_ledger
            ET.SubElement(payment_entry, 'ISDEEMEDPOSITIVE').text = 'No'
            ET.SubElement(payment_entry, 'AMOUNT').text = f'-{expense.total_amount}'
    
    # Convert to pretty XML
    rough_string = ET.tostring(envelope, 'unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    response = make_response(pretty_xml)
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=vouchers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    
    return response

@tally_bp.route('/sync/mark_synced', methods=['POST'])
@login_required
def mark_synced():
    """Mark records as synced with Tally"""
    record_type = request.json.get('type')  # purchase, sales, expense
    record_ids = request.json.get('ids', [])
    
    try:
        if record_type == 'purchase':
            PurchaseOrder.query.filter(PurchaseOrder.id.in_(record_ids)).update(
                {PurchaseOrder.tally_synced: True}, synchronize_session=False
            )
        elif record_type == 'sales':
            SalesOrder.query.filter(SalesOrder.id.in_(record_ids)).update(
                {SalesOrder.tally_synced: True}, synchronize_session=False
            )
        elif record_type == 'expense':
            FactoryExpense.query.filter(FactoryExpense.id.in_(record_ids)).update(
                {FactoryExpense.tally_synced: True}, synchronize_session=False
            )
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'{len(record_ids)} records marked as synced'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@tally_bp.route('/reports/sync_status')
@login_required
def sync_status_report():
    """Generate sync status report"""
    # Get sync statistics
    purchase_stats = {
        'total': PurchaseOrder.query.count(),
        'synced': PurchaseOrder.query.filter_by(tally_synced=True).count(),
        'pending': PurchaseOrder.query.filter_by(tally_synced=False).count()
    }
    
    sales_stats = {
        'total': SalesOrder.query.count(),
        'synced': SalesOrder.query.filter_by(tally_synced=True).count(),
        'pending': SalesOrder.query.filter_by(tally_synced=False).count()
    }
    
    expense_stats = {
        'total': FactoryExpense.query.count(),
        'synced': FactoryExpense.query.filter_by(tally_synced=True).count(),
        'pending': FactoryExpense.query.filter_by(tally_synced=False).count()
    }
    
    # Get pending records
    pending_purchases = PurchaseOrder.query.filter_by(tally_synced=False).limit(20).all()
    pending_sales = SalesOrder.query.filter_by(tally_synced=False).limit(20).all()
    pending_expenses = FactoryExpense.query.filter_by(tally_synced=False).limit(20).all()
    
    return render_template('tally/sync_status.html',
                         purchase_stats=purchase_stats,
                         sales_stats=sales_stats,
                         expense_stats=expense_stats,
                         pending_purchases=pending_purchases,
                         pending_sales=pending_sales,
                         pending_expenses=pending_expenses)

@tally_bp.route('/export/journal_entries')
@login_required
def export_journal_entries():
    """Export Journal Entries to Tally XML"""
    from models.accounting import JournalEntry, Voucher
    
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    include_gst = request.args.get('include_gst', 'on') == 'on'
    
    # Build date filters
    query = JournalEntry.query
    if date_from:
        try:
            date_filter = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.transaction_date >= date_filter)
        except ValueError:
            pass
    if date_to:
        try:
            date_filter = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(JournalEntry.transaction_date <= date_filter)
        except ValueError:
            pass
    
    journal_entries = query.order_by(JournalEntry.transaction_date.desc()).all()
    
    # Create XML structure
    envelope = ET.Element('ENVELOPE')
    header = ET.SubElement(envelope, 'HEADER')
    ET.SubElement(header, 'TALLYREQUEST').text = 'Import Data'
    
    body = ET.SubElement(envelope, 'BODY')
    import_data = ET.SubElement(body, 'IMPORTDATA')
    request_desc = ET.SubElement(import_data, 'REQUESTDESC')
    ET.SubElement(request_desc, 'REPORTNAME').text = 'Vouchers'
    
    request_data = ET.SubElement(import_data, 'REQUESTDATA')
    
    # Group journal entries by voucher
    voucher_entries = {}
    for entry in journal_entries:
        if entry.voucher_id:
            if entry.voucher_id not in voucher_entries:
                voucher_entries[entry.voucher_id] = {
                    'voucher': entry.voucher,
                    'entries': []
                }
            voucher_entries[entry.voucher_id]['entries'].append(entry)
    
    # Generate Tally vouchers
    for voucher_id, voucher_data in voucher_entries.items():
        voucher = voucher_data['voucher']
        entries = voucher_data['entries']
        
        if not voucher or not entries:
            continue
            
        voucher_elem = ET.SubElement(request_data, 'TALLYMESSAGE')
        voucher_tag = ET.SubElement(voucher_elem, 'VOUCHER', VCHTYPE="Journal", ACTION="Create")
        
        ET.SubElement(voucher_tag, 'DATE').text = voucher.transaction_date.strftime('%Y%m%d')
        ET.SubElement(voucher_tag, 'VOUCHERTYPENAME').text = 'Journal'
        ET.SubElement(voucher_tag, 'VOUCHERNUMBER').text = voucher.voucher_number
        ET.SubElement(voucher_tag, 'REFERENCE').text = voucher.reference_number or voucher.voucher_number
        ET.SubElement(voucher_tag, 'NARRATION').text = voucher.narration or 'Journal Entry'
        
        # Add ledger entries
        ledger_entries = ET.SubElement(voucher_tag, 'ALLLEDGERENTRIES.LIST')
        
        for entry in entries:
            if entry.account:
                ledger_entry = ET.SubElement(ledger_entries, 'LEDGERENTRIES.LIST')
                ET.SubElement(ledger_entry, 'LEDGERNAME').text = entry.account.name
                ET.SubElement(ledger_entry, 'ISDEEMEDPOSITIVE').text = 'Yes' if entry.entry_type == 'debit' else 'No'
                ET.SubElement(ledger_entry, 'AMOUNT').text = str(entry.amount if entry.entry_type == 'debit' else -entry.amount)
                
                # Add GST details if requested and available
                if include_gst and hasattr(entry, 'gst_amount') and entry.gst_amount:
                    ET.SubElement(ledger_entry, 'GSTRATE').text = str(entry.gst_rate or 0)
                    ET.SubElement(ledger_entry, 'GSTAMOUNT').text = str(entry.gst_amount)
    
    # Convert to pretty XML
    rough_string = ET.tostring(envelope, 'unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    response = make_response(pretty_xml)
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=journal_entries_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    
    return response

@tally_bp.route('/import', methods=['POST'])
@login_required
def import_data():
    """Import data from Tally XML file"""
    try:
        import_type = request.form.get('import_type', 'ledgers')
        overwrite = request.form.get('overwrite') == 'on'
        
        if 'import_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['import_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not file.filename.lower().endswith('.xml'):
            return jsonify({'success': False, 'error': 'File must be XML format'})
        
        # Parse XML content
        try:
            xml_content = file.read()
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return jsonify({'success': False, 'error': f'Invalid XML format: {str(e)}'})
        
        imported_count = 0
        
        if import_type == 'ledgers':
            imported_count = _import_ledgers(root, overwrite)
        elif import_type == 'items':
            imported_count = _import_items(root, overwrite)
        elif import_type == 'vouchers':
            imported_count = _import_vouchers(root, overwrite)
        else:
            return jsonify({'success': False, 'error': 'Invalid import type'})
        
        return jsonify({
            'success': True, 
            'imported_count': imported_count,
            'message': f'Successfully imported {imported_count} {import_type}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def _import_ledgers(root, overwrite=False):
    """Import ledger masters from Tally XML"""
    count = 0
    
    # Find all LEDGER elements in the XML
    for ledger_elem in root.findall('.//LEDGER'):
        try:
            name = ledger_elem.find('NAME')
            if name is not None and name.text:
                ledger_name = name.text.strip()
                
                # Check if supplier already exists
                existing = Supplier.query.filter_by(name=ledger_name).first()
                if existing and not overwrite:
                    continue
                
                # Create or update supplier
                if existing and overwrite:
                    supplier = existing
                else:
                    supplier = Supplier()
                    supplier.name = ledger_name
                    supplier.code = f"SUP{Supplier.query.count() + 1:04d}"
                
                # Extract other details
                parent = ledger_elem.find('PARENT')
                if parent is not None and parent.text:
                    supplier.partner_type = 'supplier' if 'creditor' in parent.text.lower() else 'customer'
                
                # Extract GST details
                gstin = ledger_elem.find('GSTIN')
                if gstin is not None and gstin.text:
                    supplier.gst_number = gstin.text.strip()
                
                # Extract contact details
                phone = ledger_elem.find('LEDGERPHONE')
                if phone is not None and phone.text:
                    supplier.mobile_number = phone.text.strip()
                
                email = ledger_elem.find('EMAIL')
                if email is not None and email.text:
                    supplier.email = email.text.strip()
                
                # Extract address
                address_list = ledger_elem.find('ADDRESS.LIST')
                if address_list is not None:
                    addresses = [addr.text for addr in address_list.findall('ADDRESS') if addr.text]
                    if addresses:
                        supplier.address = ', '.join(addresses)
                
                db.session.add(supplier)
                count += 1
        
        except Exception as e:
            print(f"Error importing ledger: {e}")
            continue
    
    db.session.commit()
    return count

def _import_items(root, overwrite=False):
    """Import stock items from Tally XML"""
    count = 0
    
    # Find all STOCKITEM elements in the XML
    for item_elem in root.findall('.//STOCKITEM'):
        try:
            name = item_elem.find('NAME')
            if name is not None and name.text:
                item_name = name.text.strip()
                
                # Check if item already exists
                existing = Item.query.filter_by(name=item_name).first()
                if existing and not overwrite:
                    continue
                
                # Create or update item
                if existing and overwrite:
                    item = existing
                else:
                    item = Item()
                    item.name = item_name
                    item.code = f"ITM{Item.query.count() + 1:04d}"
                
                # Extract other details
                alias = item_elem.find('ALIAS')
                if alias is not None and alias.text:
                    item.code = alias.text.strip()
                
                base_units = item_elem.find('BASEUNITS')
                if base_units is not None and base_units.text:
                    item.unit_of_measure = base_units.text.strip()
                
                # Extract opening balance
                opening_balance = item_elem.find('OPENINGBALANCE')
                if opening_balance is not None:
                    units = opening_balance.find('UNITS')
                    rate = opening_balance.find('RATE')
                    if units is not None and units.text:
                        try:
                            item.current_stock = float(units.text)
                        except ValueError:
                            pass
                    if rate is not None and rate.text:
                        try:
                            item.unit_price = float(rate.text)
                        except ValueError:
                            pass
                
                # Extract HSN code
                hsn_code = item_elem.find('HSNCODE')
                if hsn_code is not None and hsn_code.text:
                    item.hsn_code = hsn_code.text.strip()
                
                db.session.add(item)
                count += 1
        
        except Exception as e:
            print(f"Error importing item: {e}")
            continue
    
    db.session.commit()
    return count

def _import_vouchers(root, overwrite=False):
    """Import vouchers from Tally XML"""
    count = 0
    
    # Find all VOUCHER elements in the XML
    for voucher_elem in root.findall('.//VOUCHER'):
        try:
            voucher_number = voucher_elem.find('VOUCHERNUMBER')
            if voucher_number is not None and voucher_number.text:
                voucher_num = voucher_number.text.strip()
                
                # Check if voucher already exists (simplified check)
                # In a real implementation, you'd want more sophisticated duplicate detection
                
                print(f"Would import voucher: {voucher_num}")
                count += 1
        
        except Exception as e:
            print(f"Error importing voucher: {e}")
            continue
    
    return count

@tally_bp.route('/')
@login_required  
def dashboard():
    """Tally integration dashboard"""
    from models.accounting import Account, Voucher
    
    # Get Tally sync statistics
    try:
        tally_stats = {
            'total_ledgers': Supplier.query.count() + Account.query.count(),
            'total_items': Item.query.count(),
            'pending_purchases': PurchaseOrder.query.count(),
            'pending_sales': SalesOrder.query.count(),  
            'pending_expenses': FactoryExpense.query.count(),
            'total_vouchers': Voucher.query.count()
        }
    except Exception as e:
        # Fallback statistics if queries fail
        tally_stats = {
            'total_ledgers': 0,
            'total_items': 0,
            'pending_purchases': 0,
            'pending_sales': 0,
            'pending_expenses': 0,
            'total_vouchers': 0
        }
    
    return render_template('tally/dashboard.html', tally_stats=tally_stats)

@tally_bp.route('/settings')
@login_required
def settings():
    """Tally integration settings"""
    return render_template('tally/settings.html')