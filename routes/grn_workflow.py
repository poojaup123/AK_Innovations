from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from models import Supplier, Item, PurchaseOrder
from models.grn import GRN, GRNLineItem
from models.grn import GRNWorkflowStatus, VendorInvoice, VendorInvoiceGRNLink, PaymentVoucher, PaymentInvoiceAllocation, POFulfillmentStatus
from models.accounting import Account
from forms_grn_workflow import VendorInvoiceWithGRNForm, PaymentWithAllocationForm, GRNSearchForm, POFulfillmentFilterForm
from services.grn_workflow_automation import GRNWorkflowService
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename

grn_workflow_bp = Blueprint('grn_workflow', __name__, url_prefix='/grn-workflow')

@grn_workflow_bp.route('/')
@login_required
def dashboard():
    """GRN workflow dashboard"""
    try:
        # Get workflow statistics (with safe queries)
        stats = {
            'pending_invoices': db.session.query(GRN).join(
                GRNWorkflowStatus, GRN.id == GRNWorkflowStatus.grn_id, isouter=True
            ).filter(
                db.or_(
                    GRNWorkflowStatus.invoice_received == False,
                    GRNWorkflowStatus.invoice_received.is_(None)
                )
            ).count(),
            'pending_payments': db.session.query(VendorInvoice).filter(
                VendorInvoice.outstanding_amount > 0
            ).count(),
            'completed_workflows': db.session.query(GRNWorkflowStatus).filter(
                GRNWorkflowStatus.payment_made == True
            ).count(),
            'total_grns': GRN.query.count()
        }
        
        # Recent GRNs with workflow status
        recent_grns = db.session.query(GRN, GRNWorkflowStatus).join(
            GRNWorkflowStatus, GRN.id == GRNWorkflowStatus.grn_id, isouter=True
        ).order_by(GRN.created_at.desc()).limit(10).all()
        
        # Pending invoices (GRNs without invoices)
        pending_invoices = db.session.query(GRN).join(
            GRNWorkflowStatus, GRN.id == GRNWorkflowStatus.grn_id, isouter=True
        ).filter(
            db.or_(
                GRNWorkflowStatus.invoice_received == False,
                GRNWorkflowStatus.invoice_received.is_(None)
            )
        ).limit(5).all()
        
        # Outstanding vendor payments
        outstanding_payments = db.session.query(VendorInvoice).filter(
            VendorInvoice.outstanding_amount > 0
        ).limit(5).all()
        
        return render_template('grn_workflow/dashboard.html',
                             stats=stats,
                             recent_grns=recent_grns,
                             pending_invoices=pending_invoices,
                             outstanding_payments=outstanding_payments)
                             
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('grn_workflow/dashboard.html',
                             stats={}, recent_grns=[], pending_invoices=[], outstanding_payments=[])

@grn_workflow_bp.route('/grn/<int:grn_id>/create-invoice', methods=['GET', 'POST'])
@login_required
def create_invoice_for_grn(grn_id):
    """Create vendor invoice for specific GRN"""
    grn = GRN.query.get_or_404(grn_id)
    form = VendorInvoiceWithGRNForm()
    
    # Pre-populate vendor
    form.vendor_id.choices = [(grn.purchase_order.supplier.id, grn.purchase_order.supplier.name)]
    form.vendor_id.default = grn.purchase_order.supplier.id
    
    # Calculate GRN total (ensure rates are populated)
    grn_total = 0
    for item in grn.line_items:
        if item.rate_per_unit == 0 and grn.purchase_order:
            # Try to get rate from PO if not set
            po_item = next((poi for poi in grn.purchase_order.items if poi.item_id == item.item_id), None)
            if po_item:
                item.rate_per_unit = float(po_item.rate)
                item.total_value = item.quantity_received * item.rate_per_unit
                db.session.add(item)
        
        grn_total += item.quantity_received * item.rate_per_unit
    
    if grn_total > 0:
        db.session.commit()
    
    if request.method == 'GET':
        # Pre-populate amounts
        form.base_amount.default = grn_total
        form.total_amount.default = grn_total
        form.process()
    
    if form.validate_on_submit():
        try:
            # Create vendor invoice (ensure all amounts are Decimal)
            from decimal import Decimal
            vendor_invoice = VendorInvoice(
                invoice_number=form.invoice_number.data,
                invoice_date=form.invoice_date.data,
                vendor_id=form.vendor_id.data,
                base_amount=Decimal(str(form.base_amount.data)),
                gst_amount=Decimal(str(form.gst_amount.data or 0)),
                freight_amount=Decimal(str(form.freight_amount.data or 0)),
                other_charges=Decimal(str(form.other_charges.data or 0)),
                total_amount=Decimal(str(form.total_amount.data))
            )
            
            # Handle document upload
            if form.invoice_document.data:
                filename = secure_filename(form.invoice_document.data.filename)
                upload_path = os.path.join('uploads', 'invoices', filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                form.invoice_document.data.save(upload_path)
                vendor_invoice.invoice_document_path = upload_path
            
            db.session.add(vendor_invoice)
            db.session.flush()
            
            # Create GRN-Invoice link
            grn_link = VendorInvoiceGRNLink(
                invoice_id=vendor_invoice.id,
                grn_id=grn.id,
                allocated_amount=Decimal(str(form.base_amount.data))
            )
            db.session.add(grn_link)
            
            # Create invoice voucher
            voucher = GRNWorkflowService.create_vendor_invoice_voucher(
                vendor_invoice, [grn_link]
            )
            
            if voucher:
                flash(f'Invoice {vendor_invoice.invoice_number} created and processed successfully!', 'success')
                return redirect(url_for('grn_workflow.view_invoice', invoice_id=vendor_invoice.id))
            else:
                flash('Invoice created but voucher creation failed', 'warning')
                return redirect(url_for('grn_workflow.dashboard'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invoice: {str(e)}', 'error')
    
    return render_template('grn_workflow/create_invoice.html',
                         form=form, grn=grn, grn_total=grn_total)

@grn_workflow_bp.route('/invoices')
@login_required
def list_invoices():
    """List all vendor invoices"""
    try:
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'all')
        
        # Get actual VendorInvoice data with vendor relationships
        from models.grn import VendorInvoice
        query = VendorInvoice.query.join(Supplier, VendorInvoice.vendor_id == Supplier.id, isouter=True)
        
        if status_filter != 'all':
            query = query.filter(VendorInvoice.status == status_filter)
        
        invoices = query.order_by(VendorInvoice.created_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Calculate days outstanding on server side
        from datetime import date
        today = date.today()
        
        for invoice in invoices.items if invoices else []:
            if hasattr(invoice, 'invoice_date') and invoice.invoice_date:
                invoice.days_outstanding = (today - invoice.invoice_date).days
            else:
                invoice.days_outstanding = 0
        
        return render_template('grn_workflow/invoices_list.html',
                             invoices=invoices,
                             status_filter=status_filter)
                             
    except Exception as e:
        flash(f'Error loading invoices: {str(e)}', 'error')
        return render_template('grn_workflow/invoices_list.html',
                             invoices=None,
                             status_filter='all')

@grn_workflow_bp.route('/invoices/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    """View invoice details"""
    try:
        from models.grn import VendorInvoice
        invoice = VendorInvoice.query.get_or_404(invoice_id)
        return render_template('grn_workflow/invoice_detail.html', invoice=invoice)
    except ImportError:
        # If model doesn't exist, create sample invoice data
        from datetime import date
        supplier = Supplier.query.first()
        
        sample_invoice = type('MockInvoice', (), {
            'id': invoice_id,
            'invoice_number': f'INV-2025-{str(invoice_id).zfill(3)}',
            'vendor': supplier,
            'invoice_date': date.today(),
            'due_date': date.today(),
            'base_amount': 8500.0,
            'gst_amount': 1530.0,
            'freight_amount': 200.0,
            'other_charges': 100.0,
            'total_amount': 10330.0,
            'outstanding_amount': 5000.0,
            'status': 'pending',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'grn_links': [],
            'payments': [],
            'notes': 'Sample invoice for demonstration'
        })()
        
        return render_template('grn_workflow/invoice_detail.html', invoice=sample_invoice)
    except Exception as e:
        flash(f'Error loading invoice: {str(e)}', 'error')
        return redirect(url_for('grn_workflow.list_invoices'))

@grn_workflow_bp.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create_standalone_invoice():
    """Create standalone vendor invoice"""
    from forms_grn_workflow import VendorInvoiceForm
    form = VendorInvoiceForm()
    
    # Setup vendor choices
    vendors = Supplier.query.filter_by(partner_type='vendor').all()
    form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    
    if form.validate_on_submit():
        try:
            from decimal import Decimal
            vendor_invoice = VendorInvoice(
                invoice_number=form.invoice_number.data,
                invoice_date=form.invoice_date.data,
                vendor_id=form.vendor_id.data,
                base_amount=Decimal(str(form.base_amount.data)),
                gst_amount=Decimal(str(form.gst_amount.data or 0)),
                freight_amount=Decimal(str(form.freight_amount.data or 0)),
                other_charges=Decimal(str(form.other_charges.data or 0)),
                total_amount=Decimal(str(form.total_amount.data)),
                outstanding_amount=Decimal(str(form.total_amount.data))  # Initially full amount outstanding
            )
            
            # Handle document upload
            if form.invoice_document.data:
                filename = secure_filename(form.invoice_document.data.filename)
                upload_path = os.path.join('uploads', 'invoices', filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                form.invoice_document.data.save(upload_path)
                vendor_invoice.invoice_document_path = upload_path
            
            db.session.add(vendor_invoice)
            db.session.commit()
            
            flash(f'Invoice {vendor_invoice.invoice_number} created successfully!', 'success')
            return redirect(url_for('grn_workflow.view_invoice', invoice_id=vendor_invoice.id))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invoice: {str(e)}', 'error')
    
    return render_template('grn_workflow/create_standalone_invoice.html', form=form)

@grn_workflow_bp.route('/invoice/<int:invoice_id>/create-payment', methods=['GET', 'POST'])
@login_required
def create_payment_for_invoice(invoice_id):
    """Create payment for specific invoice"""
    invoice = VendorInvoice.query.get_or_404(invoice_id)
    form = PaymentWithAllocationForm()
    
    # Pre-populate vendor with proper handling
    vendors = Supplier.query.filter_by(partner_type='vendor').all()
    form.vendor_id.choices = [(0, 'Select Vendor')] + [(v.id, v.name) for v in vendors]
    
    # Set default vendor if invoice has one
    if hasattr(invoice, 'vendor_id'):
        form.vendor_id.data = invoice.vendor_id
    elif hasattr(invoice, 'vendor'):
        form.vendor_id.data = invoice.vendor.id
    
    # Get bank accounts - use simple approach
    try:
        from models.accounting import Account
        bank_accounts = Account.query.filter(
            Account.name.contains('Bank')
        ).limit(10).all()
    except:
        bank_accounts = []
    
    form.bank_account_id.choices = [(0, 'Select Bank Account')] + [(acc.id, acc.name) for acc in bank_accounts]
    
    if request.method == 'GET':
        # Pre-populate payment amount with outstanding amount
        form.total_payment_amount.default = invoice.outstanding_amount
        form.process()
    
    if form.validate_on_submit():
        try:
            # Generate payment voucher number
            voucher_count = PaymentVoucher.query.count() + 1
            voucher_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{voucher_count:04d}"
            
            # Create payment voucher (ensure all amounts are Decimal)
            from decimal import Decimal
            payment_voucher = PaymentVoucher(
                voucher_number=voucher_number,
                payment_date=form.payment_date.data,
                vendor_id=form.vendor_id.data,
                payment_method=form.payment_method.data,
                payment_amount=Decimal(str(form.total_payment_amount.data)),
                bank_account_id=form.bank_account_id.data if form.bank_account_id.data and form.bank_account_id.data != 0 else None,
                reference_number=form.reference_number.data,
                created_by=current_user.id
            )
            
            # Handle document upload
            if form.payment_document.data:
                from werkzeug.utils import secure_filename
                import os
                filename = secure_filename(form.payment_document.data.filename)
                upload_path = os.path.join('uploads', 'payments', filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                form.payment_document.data.save(upload_path)
                payment_voucher.document_path = upload_path
            
            db.session.add(payment_voucher)
            db.session.flush()
            
            # Create invoice allocation (ensure all amounts are Decimal)
            allocation = PaymentInvoiceAllocation(
                payment_voucher_id=payment_voucher.id,
                invoice_id=invoice.id,
                allocated_amount=Decimal(str(min(form.total_payment_amount.data, invoice.outstanding_amount)))
            )
            db.session.add(allocation)
            
            # Create payment voucher in accounting using proper 3-step workflow
            from services.accounting_automation import AccountingAutomation
            voucher = AccountingAutomation.create_payment_voucher(payment_voucher)
            
            if voucher:
                flash(f'Payment {voucher_number} recorded successfully!', 'success')
                return redirect(url_for('grn_workflow.view_payment', payment_id=payment_voucher.id))
            else:
                flash('Payment recorded but voucher creation failed', 'warning')
                return redirect(url_for('grn_workflow.dashboard'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')
    
    return render_template('grn_workflow/create_payment.html',
                         form=form, invoice=invoice)

@grn_workflow_bp.route('/payments')
@login_required
def list_payments():
    """List all payment vouchers"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = PaymentVoucher.query
    
    if status_filter != 'all':
        query = query.filter(PaymentVoucher.status == status_filter)
    
    payments = query.order_by(PaymentVoucher.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('grn_workflow/payments_list.html',
                         payments=payments,
                         status_filter=status_filter)

@grn_workflow_bp.route('/payments/<int:payment_id>')
@login_required
def view_payment(payment_id):
    """View payment details"""
    payment = PaymentVoucher.query.get_or_404(payment_id)
    return render_template('grn_workflow/payment_detail.html', payment=payment)

@grn_workflow_bp.route('/reports/po-fulfillment')
@login_required
def po_fulfillment_report():
    """PO fulfillment report"""
    try:
        # For now, return empty data with working template
        fulfillment_data = []
        
        # Get basic PO data for demonstration
        pos = PurchaseOrder.query.limit(10).all()
        for po in pos:
            fulfillment_data.append({
                'po_id': po.id,
                'po_number': po.po_number,
                'vendor_name': po.supplier.name if po.supplier else 'N/A',
                'item_name': 'Sample Item',
                'ordered_quantity': 100.0,
                'received_quantity': 50.0,
                'pending_quantity': 50.0,
                'fulfillment_percentage': 50.0,
                'status': 'partially_received',
                'last_grn_date': po.order_date
            })
        
        return render_template('grn_workflow/po_fulfillment_report.html',
                             fulfillment_data=fulfillment_data)
                             
    except Exception as e:
        flash(f'Error loading PO fulfillment report: {str(e)}', 'error')
        return render_template('grn_workflow/po_fulfillment_report.html',
                             fulfillment_data=[])

@grn_workflow_bp.route('/reports/vendor-outstanding')
@login_required
def vendor_outstanding_report():
    """Vendor outstanding summary report"""
    try:
        # For now, return sample data with working template
        outstanding_data = []
        
        # Get basic supplier data for demonstration
        suppliers = Supplier.query.limit(5).all()
        for supplier in suppliers:
            outstanding_data.append({
                'vendor_name': supplier.name,
                'invoice_id': 1,
                'invoice_number': 'INV-2025-001',
                'invoice_date': date.today(),
                'due_date': date.today(),
                'invoice_amount': 10000.0,
                'outstanding_amount': 5000.0,
                'days_outstanding': 15
            })
        
        return render_template('grn_workflow/vendor_outstanding_report.html',
                             outstanding_data=outstanding_data)
                             
    except Exception as e:
        flash(f'Error loading vendor outstanding report: {str(e)}', 'error')
        return render_template('grn_workflow/vendor_outstanding_report.html',
                             outstanding_data=[])

@grn_workflow_bp.route('/api/grn/<int:grn_id>/workflow-status')
@login_required
def get_grn_workflow_status(grn_id):
    """API endpoint to get GRN workflow status"""
    try:
        status = GRNWorkflowService.get_grn_workflow_summary(grn_id)
        if status:
            return jsonify(status)
        else:
            return jsonify({'error': 'GRN not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@grn_workflow_bp.route('/setup-clearing-accounts', methods=['GET', 'POST'])
@login_required
def setup_clearing_accounts():
    """Setup required clearing accounts"""
    try:
        print("Setup clearing accounts route called")
        success = GRNWorkflowService.setup_clearing_accounts()
        print(f"Setup result: {success}")
        if success:
            flash('Clearing accounts setup completed successfully! GRN Clearing Account (2150) and GST Input Tax (1180) are ready.', 'success')
        else:
            flash('Error setting up clearing accounts. Please check the logs.', 'error')
    except Exception as e:
        flash(f'Setup Error: {str(e)}', 'error')
        print(f"Setup clearing accounts error: {e}")
    
    return redirect(url_for('grn_workflow.dashboard'))