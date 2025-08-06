from app import db
from datetime import datetime
from utils import generate_next_number


class GRN(db.Model):
    """Goods Receipt Note - Parent table for tracking material receipts from job works and purchase orders"""
    __tablename__ = 'grn'
    
    id = db.Column(db.Integer, primary_key=True)
    grn_number = db.Column(db.String(50), unique=True, nullable=False)  # GRN-YYYY-0001
    # Foreign Keys (either job_work_id OR purchase_order_id should be set)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    received_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    received_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Quality control fields
    inspection_required = db.Column(db.Boolean, default=True)
    inspection_status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, failed
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    inspected_at = db.Column(db.DateTime)
    
    # Overall GRN status
    status = db.Column(db.String(20), default='draft')  # draft, received, inspected, completed
    
    # Reference information
    delivery_note = db.Column(db.String(100))  # Vendor's delivery note number
    transporter_name = db.Column(db.String(100))
    vehicle_number = db.Column(db.String(20))
    
    # Inventory management
    add_to_inventory = db.Column(db.Boolean, default=True)  # Whether to add received quantities to inventory
    
    # Notes and remarks
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_order = db.relationship('PurchaseOrder', backref='grn_receipts_po')
    receiver = db.relationship('User', foreign_keys=[received_by], backref='received_grns')
    inspector = db.relationship('User', foreign_keys=[inspected_by], backref='inspected_grns')
    line_items = db.relationship('GRNLineItem', backref='grn_parent', lazy=True, cascade='all, delete-orphan')
    
    @property
    def source_document(self):
        """Get the source document (either job work or purchase order)"""
        if self.job_work_id:
            return self.job_work
        elif self.purchase_order_id:
            return self.purchase_order
        return None
    
    @property
    def source_type(self):
        """Get the type of source document"""
        if self.job_work_id:
            return 'job_work'
        elif self.purchase_order_id:
            return 'purchase_order'
        return None
    
    @staticmethod
    def generate_grn_number():
        """Generate next GRN number in format GRN-YYYY-0001"""
        return generate_next_number('GRN', 'grn', 'grn_number')
    
    @property
    def total_quantity_received(self):
        """Calculate total quantity received across all line items"""
        return sum(item.quantity_received for item in self.line_items)
    
    @property
    def total_quantity_passed(self):
        """Calculate total quantity passed inspection"""
        return sum(item.quantity_passed for item in self.line_items)
    
    @property
    def total_quantity_rejected(self):
        """Calculate total quantity rejected during inspection"""
        return sum(item.quantity_rejected for item in self.line_items)
    
    @property
    def acceptance_rate(self):
        """Calculate acceptance rate percentage"""
        total = self.total_quantity_received
        if total > 0:
            return (self.total_quantity_passed / total) * 100
        return 0
    
    @property
    def is_fully_inspected(self):
        """Check if all received items have been inspected"""
        return all(item.inspection_status in ['passed', 'rejected', 'partial'] for item in self.line_items)
    
    @property
    def total_amount(self):
        """Calculate total amount from all line items"""
        if not self.line_items:
            return 0
        
        total = 0
        for item in self.line_items:
            qty = float(item.quantity_received or 0)
            rate = float(item.rate_per_unit or 0)
            total += qty * rate
        return total

    def __repr__(self):
        return f'<GRN {self.grn_number}>'


class GRNLineItem(db.Model):
    """GRN Line Items - Individual items received in a GRN"""
    __tablename__ = 'grn_line_items'
    
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Quantity tracking
    quantity_received = db.Column(db.Float, nullable=False)
    quantity_passed = db.Column(db.Float, default=0.0)
    quantity_rejected = db.Column(db.Float, default=0.0)
    
    # Unit information
    unit_of_measure = db.Column(db.String(20))
    unit_weight = db.Column(db.Float, default=0.0)
    
    # Quality control
    inspection_status = db.Column(db.String(20), default='pending')  # pending, passed, rejected, partial
    rejection_reason = db.Column(db.String(500))
    quality_grade = db.Column(db.String(10))  # A, B, C grade or Pass/Fail
    
    # Process information (for multi-process job works)
    process_name = db.Column(db.String(100))  # Which process this item came from
    process_stage = db.Column(db.String(50))  # Stage in the process
    
    # Cost tracking
    rate_per_unit = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    
    # Material classification for inventory
    material_classification = db.Column(db.String(50), default='finished_goods')  # finished_goods, semi_finished, raw_material
    
    # Notes and tracking
    remarks = db.Column(db.Text)
    batch_number = db.Column(db.String(50))
    serial_numbers = db.Column(db.Text)  # JSON or comma-separated for tracking individual items
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    grn = db.relationship('GRN')
    item = db.relationship('Item', backref='grn_line_items')
    
    @property
    def acceptance_rate(self):
        """Calculate acceptance rate for this line item"""
        if self.quantity_received > 0:
            return (self.quantity_passed / self.quantity_received) * 100
        return 0
    
    @property
    def pending_inspection(self):
        """Calculate quantity pending inspection"""
        return self.quantity_received - (self.quantity_passed + self.quantity_rejected)
    
    @property
    def is_fully_inspected(self):
        """Check if this line item is fully inspected"""
        return (self.quantity_passed + self.quantity_rejected) >= self.quantity_received
    
    def __repr__(self):
        return f'<GRNLineItem {self.grn.grn_number}-{self.item.code}>'

from app import db
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import func

class GRNWorkflowStatus(db.Model):
    """Track GRN workflow status through the 3-step process"""
    __tablename__ = 'grn_workflow_status'
    
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'), nullable=False)
    
    # Workflow stages
    material_received = db.Column(db.Boolean, default=False)
    grn_voucher_created = db.Column(db.Boolean, default=False)
    invoice_received = db.Column(db.Boolean, default=False)
    invoice_voucher_created = db.Column(db.Boolean, default=False)
    payment_made = db.Column(db.Boolean, default=False)
    payment_voucher_created = db.Column(db.Boolean, default=False)
    
    # Timestamps
    material_received_date = db.Column(db.DateTime)
    invoice_received_date = db.Column(db.DateTime)
    payment_made_date = db.Column(db.DateTime)
    
    # References
    grn_clearing_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    invoice_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    payment_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    grn = db.relationship('GRN', backref='workflow_status')
    grn_clearing_voucher = db.relationship('Voucher', foreign_keys=[grn_clearing_voucher_id])
    invoice_voucher = db.relationship('Voucher', foreign_keys=[invoice_voucher_id])
    payment_voucher = db.relationship('Voucher', foreign_keys=[payment_voucher_id])

class VendorInvoice(db.Model):
    """Vendor invoices linked to GRNs"""
    __tablename__ = 'vendor_invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(100), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    
    # Vendor details
    vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    # Invoice amounts
    base_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    gst_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    freight_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    other_charges = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    total_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    
    # Payment status
    paid_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    outstanding_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, processed, paid
    
    # Document reference
    invoice_document_path = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Supplier', backref='vendor_invoices')
    
    def update_outstanding(self):
        """Update outstanding amount (safe Decimal arithmetic)"""
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.paid_amount or 0))
        self.outstanding_amount = total - paid
        
        if self.outstanding_amount <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'

class VendorInvoiceGRNLink(db.Model):
    """Link vendor invoices to specific GRNs"""
    __tablename__ = 'vendor_invoice_grn_links'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('vendor_invoices.id'), nullable=False)
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'), nullable=False)
    
    # Amount allocation
    allocated_amount = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = db.relationship('VendorInvoice', backref='grn_links')
    grn = db.relationship('GRN', backref='invoice_links')

class PaymentVoucher(db.Model):
    """Payment vouchers for vendor payments"""
    __tablename__ = 'payment_vouchers'
    
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    
    # Vendor details
    vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    # Payment details
    payment_method = db.Column(db.String(50), nullable=False)  # cash, bank, upi, cheque
    payment_amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Bank details (for non-cash payments)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    reference_number = db.Column(db.String(100))  # cheque number, UPI ref, etc.
    
    # Document reference
    document_path = db.Column(db.String(500))  # path to uploaded supporting document
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, posted, cancelled
    
    # Accounting reference
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    vendor = db.relationship('Supplier', backref='vendor_payments')
    bank_account = db.relationship('Account')
    voucher = db.relationship('Voucher')
    created_by_user = db.relationship('User')

class PaymentInvoiceAllocation(db.Model):
    """Allocate payments to specific invoices"""
    __tablename__ = 'payment_invoice_allocations'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_voucher_id = db.Column(db.Integer, db.ForeignKey('payment_vouchers.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('vendor_invoices.id'), nullable=False)
    
    allocated_amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payment_voucher = db.relationship('PaymentVoucher', backref='invoice_allocations')
    invoice = db.relationship('VendorInvoice', backref='payment_allocations')

class POFulfillmentStatus(db.Model):
    """Track PO fulfillment status"""
    __tablename__ = 'po_fulfillment_status'
    
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    po_item_id = db.Column(db.Integer, db.ForeignKey('purchase_order_items.id'), nullable=False)
    
    # Quantities
    ordered_quantity = db.Column(db.Numeric(15, 3), nullable=False)
    received_quantity = db.Column(db.Numeric(15, 3), nullable=False, default=Decimal('0.000'))
    pending_quantity = db.Column(db.Numeric(15, 3), nullable=False, default=Decimal('0.000'))
    
    # Values
    ordered_value = db.Column(db.Numeric(15, 2), nullable=False)
    received_value = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    pending_value = db.Column(db.Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    
    # Status
    fulfillment_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    status = db.Column(db.String(20), default='pending')  # pending, partial, complete
    
    last_grn_date = db.Column(db.Date)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    po = db.relationship('PurchaseOrder', backref='fulfillment_status')
    po_item = db.relationship('PurchaseOrderItem', backref='fulfillment_status')
    
    def update_status(self):
        """Update fulfillment status based on quantities"""
        if self.ordered_quantity > 0:
            self.fulfillment_percentage = (self.received_quantity / self.ordered_quantity) * 100
            
            if self.received_quantity >= self.ordered_quantity:
                self.status = 'complete'
                self.pending_quantity = 0
                self.pending_value = 0
            elif self.received_quantity > 0:
                self.status = 'partial'
                self.pending_quantity = self.ordered_quantity - self.received_quantity
                # Calculate pending value proportionally
                if self.ordered_value > 0:
                    unit_rate = self.ordered_value / self.ordered_quantity
                    self.pending_value = self.pending_quantity * unit_rate
            else:
                self.status = 'pending'
                self.pending_quantity = self.ordered_quantity
                self.pending_value = self.ordered_value