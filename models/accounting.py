from app import db
from datetime import datetime
from sqlalchemy import func
from decimal import Decimal

class AccountGroup(db.Model):
    """Chart of Accounts Groups (Assets, Liabilities, Income, Expenses)"""
    __tablename__ = 'account_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    group_type = db.Column(db.String(20), nullable=False)  # assets, liabilities, income, expenses
    parent_group_id = db.Column(db.Integer, db.ForeignKey('account_groups.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_group = db.relationship('AccountGroup', remote_side=[id], backref='sub_groups')
    accounts = db.relationship('Account', backref='group', lazy=True)
    
    def __repr__(self):
        return f'<AccountGroup {self.name}>'

class Account(db.Model):
    """General Ledger Accounts"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True)
    account_group_id = db.Column(db.Integer, db.ForeignKey('account_groups.id'), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)  # current_asset, fixed_asset, current_liability, etc.
    
    # Tax and compliance
    is_gst_applicable = db.Column(db.Boolean, default=False)
    gst_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    hsn_sac_code = db.Column(db.String(20))
    
    # Balance tracking
    opening_balance = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    current_balance = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    
    # Flags
    is_active = db.Column(db.Boolean, default=True)
    is_bank_account = db.Column(db.Boolean, default=False)
    is_cash_account = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    journal_entries = db.relationship('JournalEntry', backref='account', lazy=True)
    
    @property
    def balance_type(self):
        """Determine if account normally has debit or credit balance"""
        debit_types = ['assets', 'expenses']
        credit_types = ['liabilities', 'income', 'equity']
        
        if self.group.group_type in debit_types:
            return 'debit'
        return 'credit'
    
    def calculate_balance(self, as_of_date=None):
        """Calculate account balance as of a specific date"""
        try:
            query = JournalEntry.query.filter_by(account_id=self.id)
            if as_of_date:
                query = query.filter(JournalEntry.transaction_date <= as_of_date)
            
            debit_total = query.filter_by(entry_type='debit').with_entities(func.sum(JournalEntry.amount)).scalar() or 0
            credit_total = query.filter_by(entry_type='credit').with_entities(func.sum(JournalEntry.amount)).scalar() or 0
            
            # Ensure proper numeric conversion
            opening_bal = float(self.opening_balance or 0)
            debit_val = float(debit_total or 0)
            credit_val = float(credit_total or 0)
            
            if self.balance_type == 'debit':
                return opening_bal + debit_val - credit_val
            else:
                return opening_bal + credit_val - debit_val
        except Exception as e:
            # Return opening balance if calculation fails
            return float(self.opening_balance or 0)
    
    def __repr__(self):
        return f'<Account {self.name}>'

class VoucherType(db.Model):
    """Voucher Types (Purchase, Sales, Payment, Receipt, Journal, Contra)"""
    __tablename__ = 'voucher_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    vouchers = db.relationship('Voucher', backref='voucher_type', lazy=True)
    
    def __repr__(self):
        return f'<VoucherType {self.name}>'

class Voucher(db.Model):
    """Main voucher table for all transactions"""
    __tablename__ = 'vouchers'
    
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), nullable=False, unique=True)
    voucher_type_id = db.Column(db.Integer, db.ForeignKey('voucher_types.id'), nullable=False)
    
    # Transaction details
    transaction_date = db.Column(db.Date, nullable=False)
    reference_number = db.Column(db.String(100))  # PO number, SO number, etc.
    narration = db.Column(db.Text)
    
    # Party details
    party_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))  # Supplier/Customer
    party_type = db.Column(db.String(20))  # supplier, customer, employee
    
    # Amounts
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(15, 2), default=0.0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0.0)
    
    # Status and workflow
    status = db.Column(db.String(20), default='draft')  # draft, posted, cancelled
    is_gst_applicable = db.Column(db.Boolean, default=False)
    
    # Audit trail
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_at = db.Column(db.DateTime)
    
    # Relationships
    party = db.relationship('Supplier', backref='vouchers')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_vouchers')
    poster = db.relationship('User', foreign_keys=[posted_by], backref='posted_vouchers')
    journal_entries = db.relationship('JournalEntry', backref='voucher', lazy=True, cascade='all, delete-orphan')
    
    @classmethod
    def generate_voucher_number(cls, voucher_type_code):
        """Generate next voucher number"""
        current_year = datetime.now().year
        prefix = f"{voucher_type_code}-{current_year}-"
        
        latest_voucher = cls.query.filter(
            cls.voucher_number.like(f'{prefix}%')
        ).order_by(cls.voucher_number.desc()).first()
        
        if latest_voucher:
            last_sequence = int(latest_voucher.voucher_number.split('-')[-1])
            next_sequence = last_sequence + 1
        else:
            next_sequence = 1
        
        return f'{prefix}{next_sequence:04d}'
    
    def post_voucher(self, posted_by_id):
        """Post voucher and update account balances"""
        if self.status == 'posted':
            return False
        
        self.status = 'posted'
        self.posted_by = posted_by_id
        self.posted_at = datetime.utcnow()
        
        # Update account balances (safe Decimal arithmetic)
        from decimal import Decimal
        for entry in self.journal_entries:
            account = entry.account
            # Ensure all values are Decimal to avoid type conflicts
            current_balance = Decimal(str(account.current_balance or 0))
            entry_amount = Decimal(str(entry.amount or 0))
            
            if entry.entry_type == 'debit':
                if account.balance_type == 'debit':
                    account.current_balance = current_balance + entry_amount
                else:
                    account.current_balance = current_balance - entry_amount
            else:  # credit
                if account.balance_type == 'credit':
                    account.current_balance = current_balance + entry_amount
                else:
                    account.current_balance = current_balance - entry_amount
        
        db.session.commit()
        return True
    
    def __repr__(self):
        return f'<Voucher {self.voucher_number}>'

class JournalEntry(db.Model):
    """Journal entries for double-entry bookkeeping"""
    __tablename__ = 'journal_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Entry details
    entry_type = db.Column(db.String(10), nullable=False)  # debit, credit
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    narration = db.Column(db.Text)
    
    # Transaction details
    transaction_date = db.Column(db.Date, nullable=False)
    
    # Reference details for tracking
    reference_type = db.Column(db.String(50))  # purchase_order, sales_order, production, etc.
    reference_id = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<JournalEntry {self.entry_type} {self.amount} to {self.account.name}>'

class Invoice(db.Model):
    """GST-compliant invoice generation"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True)
    invoice_type = db.Column(db.String(20), nullable=False)  # sales, purchase
    
    # Party details
    party_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    party_name = db.Column(db.String(200), nullable=False)
    party_gst = db.Column(db.String(50))
    party_address = db.Column(db.Text)
    
    # Invoice details
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    place_of_supply = db.Column(db.String(100))
    
    # Reference
    reference_type = db.Column(db.String(50))  # sales_order, purchase_order
    reference_id = db.Column(db.Integer)
    
    # Amounts
    subtotal = db.Column(db.Numeric(15, 2), nullable=False)
    cgst_amount = db.Column(db.Numeric(15, 2), default=0.0)
    sgst_amount = db.Column(db.Numeric(15, 2), default=0.0)
    igst_amount = db.Column(db.Numeric(15, 2), default=0.0)
    total_tax = db.Column(db.Numeric(15, 2), default=0.0)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, cancelled
    
    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    party = db.relationship('Supplier', backref='invoices')
    creator = db.relationship('User', backref='created_invoices')
    invoice_items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    
    @classmethod
    def generate_invoice_number(cls, invoice_type):
        """Generate next invoice number"""
        current_year = datetime.now().year
        prefix = f"{'SAL' if invoice_type == 'sales' else 'PUR'}-{current_year}-"
        
        latest_invoice = cls.query.filter(
            cls.invoice_number.like(f'{prefix}%')
        ).order_by(cls.invoice_number.desc()).first()
        
        if latest_invoice:
            last_sequence = int(latest_invoice.invoice_number.split('-')[-1])
            next_sequence = last_sequence + 1
        else:
            next_sequence = 1
        
        return f'{prefix}{next_sequence:04d}'
    
    def calculate_tax(self):
        """Calculate GST amounts based on invoice items"""
        self.subtotal = sum(item.line_total for item in self.invoice_items)
        
        # Determine GST type based on party state
        from models import CompanySettings
        company = CompanySettings.query.first()
        
        if company and self.party and company.state == self.party.state:
            # Intra-state: CGST + SGST
            total_gst_rate = sum(item.gst_rate for item in self.invoice_items if item.gst_rate)
            self.cgst_amount = (self.subtotal * total_gst_rate / 2) / 100
            self.sgst_amount = (self.subtotal * total_gst_rate / 2) / 100
            self.igst_amount = 0
        else:
            # Inter-state: IGST
            total_gst_rate = sum(item.gst_rate for item in self.invoice_items if item.gst_rate)
            self.igst_amount = (self.subtotal * total_gst_rate) / 100
            self.cgst_amount = 0
            self.sgst_amount = 0
        
        self.total_tax = self.cgst_amount + self.sgst_amount + self.igst_amount
        self.total_amount = self.subtotal + self.total_tax
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'

class InvoiceItem(db.Model):
    """Invoice line items"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    
    # Item details
    item_name = db.Column(db.String(200), nullable=False)
    item_code = db.Column(db.String(50))
    hsn_code = db.Column(db.String(20))
    
    # Quantity and rates
    quantity = db.Column(db.Numeric(15, 4), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    rate = db.Column(db.Numeric(15, 2), nullable=False)
    line_total = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Tax details
    gst_rate = db.Column(db.Numeric(5, 2), default=0.0)
    
    # Relationships
    item = db.relationship('Item', backref='invoice_items')
    
    def __repr__(self):
        return f'<InvoiceItem {self.item_name} x {self.quantity}>'

class TaxMaster(db.Model):
    """Master data for tax rates and HSN/SAC codes"""
    __tablename__ = 'tax_master'
    
    id = db.Column(db.Integer, primary_key=True)
    hsn_sac_code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=False)
    
    # Tax rates
    cgst_rate = db.Column(db.Numeric(5, 2), default=0.0)
    sgst_rate = db.Column(db.Numeric(5, 2), default=0.0)
    igst_rate = db.Column(db.Numeric(5, 2), default=0.0)
    
    # Category
    tax_category = db.Column(db.String(50))  # goods, services
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def total_gst_rate(self):
        """Calculate total GST rate"""
        return float(self.cgst_rate + self.sgst_rate + self.igst_rate)
    
    def __repr__(self):
        return f'<TaxMaster {self.hsn_sac_code}>'

class BankAccount(db.Model):
    """Bank account management"""
    __tablename__ = 'bank_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Bank details
    bank_name = db.Column(db.String(200), nullable=False)
    branch_name = db.Column(db.String(200))
    account_number = db.Column(db.String(50), nullable=False)
    ifsc_code = db.Column(db.String(20), nullable=False)
    
    # Account details
    account_type = db.Column(db.String(50), default='current')  # current, savings
    opening_balance = db.Column(db.Numeric(15, 2), default=0.0)
    current_balance = db.Column(db.Numeric(15, 2), default=0.0)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account', backref='bank_details')
    
    def __repr__(self):
        return f'<BankAccount {self.bank_name} - {self.account_number}>'

from app import db
from datetime import datetime
from sqlalchemy import text

class AdvancedAccountingSettings(db.Model):
    """Advanced accounting configuration settings"""
    __tablename__ = 'advanced_accounting_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Auto voucher settings
    auto_jv_posting = db.Column(db.Boolean, default=True)
    auto_grn_voucher = db.Column(db.Boolean, default=True)
    auto_sales_voucher = db.Column(db.Boolean, default=True)
    auto_production_voucher = db.Column(db.Boolean, default=True)
    auto_expense_voucher = db.Column(db.Boolean, default=True)
    auto_salary_voucher = db.Column(db.Boolean, default=True)
    
    # Rounding rules
    amount_rounding_places = db.Column(db.Integer, default=2)
    rounding_method = db.Column(db.String(20), default='normal')  # normal, up, down
    
    # Inventory valuation
    inventory_valuation_method = db.Column(db.String(20), default='moving_average')  # fifo, lifo, moving_average, standard_cost
    
    # Default accounts
    default_cash_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_bank_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_purchase_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_sales_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_inventory_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    default_cogs_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    
    # GST settings
    gst_number = db.Column(db.String(50))
    place_of_business = db.Column(db.String(100))
    default_gst_rate = db.Column(db.Numeric(5, 2), default=18.0)
    
    # Payment modes
    enable_upi_payments = db.Column(db.Boolean, default=True)
    enable_credit_payments = db.Column(db.Boolean, default=True)
    default_credit_days = db.Column(db.Integer, default=30)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    default_cash_account = db.relationship('Account', foreign_keys=[default_cash_account_id])
    default_bank_account = db.relationship('Account', foreign_keys=[default_bank_account_id])
    default_purchase_account = db.relationship('Account', foreign_keys=[default_purchase_account_id])
    default_sales_account = db.relationship('Account', foreign_keys=[default_sales_account_id])
    default_inventory_account = db.relationship('Account', foreign_keys=[default_inventory_account_id])
    default_cogs_account = db.relationship('Account', foreign_keys=[default_cogs_account_id])
    
    @classmethod
    def get_settings(cls):
        """Get or create advanced accounting settings"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

class CostCenter(db.Model):
    """Cost centers for department-wise expense tracking"""
    __tablename__ = 'cost_centers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    # Hierarchy
    parent_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'))
    
    # Budgeting
    monthly_budget = db.Column(db.Numeric(15, 2), default=0.0)
    yearly_budget = db.Column(db.Numeric(15, 2), default=0.0)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_center = db.relationship('CostCenter', remote_side=[id], backref='sub_centers')
    
    def __repr__(self):
        return f'<CostCenter {self.name}>'

class LedgerMapping(db.Model):
    """Automatic ledger mapping for different categories"""
    __tablename__ = 'ledger_mappings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Mapping rules
    entity_type = db.Column(db.String(50), nullable=False)  # supplier, customer, item_category, department
    entity_id = db.Column(db.Integer)  # Reference to the entity
    entity_name = db.Column(db.String(200))  # For generic mappings
    
    # Account mappings
    receivable_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    payable_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    expense_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    income_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    
    # Cost center
    cost_center_id = db.Column(db.Integer, db.ForeignKey('cost_centers.id'))
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    receivable_account = db.relationship('Account', foreign_keys=[receivable_account_id])
    payable_account = db.relationship('Account', foreign_keys=[payable_account_id])
    expense_account = db.relationship('Account', foreign_keys=[expense_account_id])
    income_account = db.relationship('Account', foreign_keys=[income_account_id])
    cost_center = db.relationship('CostCenter')

class PaymentMethod(db.Model):
    """Payment methods configuration"""
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    method_type = db.Column(db.String(20), nullable=False)  # cash, bank, upi, credit_card, cheque
    
    # Account mapping
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Configuration
    requires_reference = db.Column(db.Boolean, default=False)  # For cheque numbers, UPI IDs
    auto_reconcile = db.Column(db.Boolean, default=False)
    processing_fee_rate = db.Column(db.Numeric(5, 2), default=0.0)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account')
    
    def __repr__(self):
        return f'<PaymentMethod {self.name}>'

class InventoryValuation(db.Model):
    """Inventory valuation tracking for different methods"""
    __tablename__ = 'inventory_valuations'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'))
    
    # Valuation data
    valuation_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    
    # Different valuation methods
    fifo_rate = db.Column(db.Numeric(15, 2))
    lifo_rate = db.Column(db.Numeric(15, 2))
    moving_avg_rate = db.Column(db.Numeric(15, 2))
    standard_cost_rate = db.Column(db.Numeric(15, 2))
    
    # Current method value
    current_rate = db.Column(db.Numeric(15, 2), nullable=False)
    total_value = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Transaction reference
    transaction_type = db.Column(db.String(50))  # grn, production, sales, adjustment
    transaction_id = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item')
    batch = db.relationship('ItemBatch')
    
    @classmethod
    def calculate_moving_average(cls, item_id, new_quantity, new_rate):
        """Calculate moving average rate for an item"""
        latest = cls.query.filter_by(item_id=item_id).order_by(cls.created_at.desc()).first()
        
        if not latest or latest.quantity == 0:
            return new_rate
        
        current_value = latest.quantity * latest.moving_avg_rate
        new_value = new_quantity * new_rate
        total_quantity = latest.quantity + new_quantity
        
        if total_quantity == 0:
            return new_rate
        
        return (current_value + new_value) / total_quantity
    
    def __repr__(self):
        return f'<InventoryValuation {self.item.name if self.item else "N/A"} - {self.quantity}>'