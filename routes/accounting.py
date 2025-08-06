from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from app import db
from models.accounting import (AccountGroup, Account, VoucherType, Voucher, JournalEntry, 
                             Invoice, InvoiceItem, TaxMaster, BankAccount, InventoryValuation)
from models import Supplier, Item, PurchaseOrder, SalesOrder, FactoryExpense, CompanySettings
from services.inventory_valuation import InventoryValuationService
from forms_accounting import (AccountGroupForm, AccountForm, VoucherForm, JournalEntryForm,
                            InvoiceForm, InvoiceItemForm, TaxMasterForm, BankAccountForm,
                            PaymentForm, ReceiptForm, ReportFilterForm, GSATReportForm)
from sqlalchemy import func, and_, or_, desc, extract
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import calendar

accounting_bp = Blueprint('accounting', __name__)

def calculate_inventory_valuation():
    """Calculate current inventory valuation across all items"""
    try:
        # Get all items with current stock
        items_with_stock = Item.query.filter(Item.current_stock > 0).all()
        
        total_raw_material = 0
        total_wip = 0
        total_finished_goods = 0
        total_scrap = 0
        
        for item in items_with_stock:
            if item.current_stock and item.current_stock > 0:
                item_value = float(item.current_stock) * float(item.unit_price or 0)
                
                if item.item_type == 'raw_material':
                    total_raw_material += item_value
                elif item.item_type == 'work_in_progress':
                    total_wip += item_value
                elif item.item_type in ['finished_good', 'semi_finished_good']:
                    total_finished_goods += item_value
                elif item.item_type == 'scrap':
                    total_scrap += item_value
        
        return {
            'raw_material': total_raw_material,
            'wip': total_wip,
            'finished_goods': total_finished_goods,
            'scrap': total_scrap,
            'total': total_raw_material + total_wip + total_finished_goods + total_scrap
        }
        
    except Exception as e:
        print(f"Error calculating inventory valuation: {str(e)}")
        return {
            'raw_material': 0,
            'wip': 0,
            'finished_goods': 0,
            'scrap': 0,
            'total': 0
        }

@accounting_bp.route('/dashboard')
@login_required
def dashboard():
    """Accounting Dashboard"""
    # Initialize default values
    total_assets = 0
    total_liabilities = 0
    total_income = 0
    total_expenses = 0
    monthly_vouchers = 0
    outstanding_receivables = 0
    outstanding_payables = 0
    recent_vouchers = []
    bank_accounts = []
    monthly_trend = []
    
    try:
        # Current month financial summary
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Account balances by type - using proper balance calculation
        asset_accounts = Account.query.join(AccountGroup).filter(AccountGroup.group_type == 'assets').all()
        liability_accounts = Account.query.join(AccountGroup).filter(AccountGroup.group_type == 'liabilities').all()
        income_accounts = Account.query.join(AccountGroup).filter(AccountGroup.group_type == 'income').all()
        expense_accounts = Account.query.join(AccountGroup).filter(AccountGroup.group_type == 'expenses').all()
        
        # ✅ FIXED: Use current_balance field with proper liability calculation
        total_assets = sum(abs(float(account.current_balance or 0)) for account in asset_accounts if account.current_balance and account.current_balance != 0)
        
        # For liabilities, take positive balances (amounts we owe)
        total_liabilities = sum(float(account.current_balance or 0) for account in liability_accounts if account.current_balance and account.current_balance > 0)
        
        total_income = sum(abs(float(account.current_balance or 0)) for account in income_accounts if account.current_balance and account.current_balance != 0)
        total_expenses = sum(abs(float(account.current_balance or 0)) for account in expense_accounts if account.current_balance and account.current_balance != 0)
        
        # Current month transactions
        month_start = datetime(current_year, current_month, 1).date()
        if current_month == 12:
            month_end = datetime(current_year + 1, 1, 1).date() - timedelta(days=1)
        else:
            month_end = datetime(current_year, current_month + 1, 1).date() - timedelta(days=1)
        
        # Count all vouchers created this month (including drafts)
        monthly_vouchers = Voucher.query.filter(
            Voucher.created_at >= datetime(current_year, current_month, 1),
            Voucher.created_at < datetime(current_year, current_month + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1)
        ).count()
        
        # Outstanding amounts - using proper vendor invoice tracking
        from models.grn import VendorInvoice
        
        # Outstanding receivables (sales orders and invoices not yet collected)
        outstanding_receivables = db.session.query(func.sum(Voucher.total_amount)).filter(
            Voucher.status == 'posted',
            Voucher.voucher_type_id.in_(
                db.session.query(VoucherType.id).filter(VoucherType.code.in_(['SAL', 'SOV']))
            )
        ).scalar() or 0
        
        # ✅ FIXED: Outstanding payables from vendor invoices (unpaid amounts)
        outstanding_payables = db.session.query(func.sum(VendorInvoice.outstanding_amount)).filter(
            VendorInvoice.outstanding_amount > 0
        ).scalar() or 0
        
        # Recent transactions
        recent_vouchers = Voucher.query.filter_by(status='posted').order_by(desc(Voucher.created_at)).limit(10).all()
        
        # Bank balances
        bank_accounts = BankAccount.query.filter_by(is_active=True).all()
        
        # Monthly expense trend
        monthly_trend = []
        for i in range(6):
            month_date = datetime.now().replace(day=1)
            if i > 0:
                month_date = month_date.replace(month=month_date.month - i)
                if month_date.month <= 0:
                    month_date = month_date.replace(month=month_date.month + 12, year=month_date.year - 1)
            
            month_total = db.session.query(func.sum(JournalEntry.amount)).join(Account).join(AccountGroup).filter(
                AccountGroup.group_type == 'expenses',
                JournalEntry.entry_type == 'debit',
                extract('month', JournalEntry.transaction_date) == month_date.month,
                extract('year', JournalEntry.transaction_date) == month_date.year
            ).scalar() or 0
            
            monthly_trend.append({
                'month': calendar.month_name[month_date.month],
                'year': month_date.year,
                'total': float(month_total)
            })
        
        monthly_trend.reverse()
        
        # Calculate inventory valuation
        inventory_valuation = calculate_inventory_valuation()
        
        stats = {
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'monthly_vouchers': monthly_vouchers,
            'outstanding_receivables': outstanding_receivables,
            'outstanding_payables': outstanding_payables,
            'net_worth': total_assets - total_liabilities,
            'profit_loss': total_income - total_expenses,
            'inventory_valuation': inventory_valuation
        }
        
        return render_template('accounting/dashboard.html',
                             stats=stats,
                             recent_vouchers=recent_vouchers,
                             bank_accounts=bank_accounts,
                             monthly_trend=monthly_trend)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        
    # Create stats dictionary with all required fields  
    inventory_valuation = calculate_inventory_valuation()  # Calculate for fallback case too
    stats = {
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_worth': total_assets - total_liabilities,
        'profit_loss': total_income - total_expenses,
        'monthly_vouchers': monthly_vouchers,
        'outstanding_receivables': outstanding_receivables,
        'outstanding_payables': outstanding_payables,
        'inventory_valuation': inventory_valuation
    }
    
    return render_template('accounting/dashboard.html', 
                         stats=stats, 
                         recent_vouchers=recent_vouchers, 
                         bank_accounts=bank_accounts,
                         monthly_trend=monthly_trend)

# Chart of Accounts Management
@accounting_bp.route('/accounts')
@login_required
def list_accounts():
    """List all accounts grouped by account groups"""
    account_groups = AccountGroup.query.filter_by(is_active=True).order_by(AccountGroup.group_type, AccountGroup.name).all()
    return render_template('accounting/accounts_list.html', account_groups=account_groups)

@accounting_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    """Add new account"""
    form = AccountForm()
    
    # Populate account groups
    form.account_group_id.choices = [(g.id, g.name) for g in AccountGroup.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            account = Account(
                name=form.name.data,
                code=form.code.data.upper(),
                account_group_id=form.account_group_id.data,
                account_type=form.account_type.data,
                opening_balance=form.opening_balance.data or 0.0,
                current_balance=form.opening_balance.data or 0.0,
                is_gst_applicable=form.is_gst_applicable.data,
                gst_rate=form.gst_rate.data or 0.0,
                hsn_sac_code=form.hsn_sac_code.data,
                is_bank_account=form.is_bank_account.data,
                is_cash_account=form.is_cash_account.data
            )
            
            db.session.add(account)
            db.session.commit()
            
            flash(f'Account "{account.name}" created successfully!', 'success')
            return redirect(url_for('accounting.list_accounts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
    
    return render_template('accounting/account_form.html', form=form, title='Add Account')

@accounting_bp.route('/accounts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    """Edit account"""
    account = Account.query.get_or_404(id)
    form = AccountForm(obj=account)
    
    # Populate account groups
    form.account_group_id.choices = [(g.id, g.name) for g in AccountGroup.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(account)
            db.session.commit()
            
            flash(f'Account "{account.name}" updated successfully!', 'success')
            return redirect(url_for('accounting.list_accounts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating account: {str(e)}', 'error')
    
    return render_template('accounting/account_form.html', form=form, account=account, title='Edit Account')

# Voucher Management
@accounting_bp.route('/vouchers')
@login_required
def list_vouchers():
    """List vouchers with filters"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    voucher_type = request.args.get('type', '', type=str)
    
    query = Voucher.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if voucher_type:
        query = query.join(VoucherType).filter(VoucherType.code == voucher_type)
    
    vouchers = query.order_by(desc(Voucher.created_at)).paginate(
        page=page, per_page=20, error_out=False)
    
    voucher_types = VoucherType.query.filter_by(is_active=True).all()
    
    return render_template('accounting/vouchers_list.html', 
                         vouchers=vouchers, 
                         voucher_types=voucher_types,
                         status_filter=status_filter,
                         voucher_type=voucher_type)

@accounting_bp.route('/vouchers/add', methods=['GET', 'POST'])
@login_required
def add_voucher():
    """Add new voucher"""
    form = VoucherForm()
    
    # Populate choices
    form.voucher_type_id.choices = [(vt.id, vt.name) for vt in VoucherType.query.filter_by(is_active=True).all()]
    form.party_id.choices = [('', 'Select Party')] + [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            voucher_type = VoucherType.query.get(form.voucher_type_id.data)
            voucher_number = Voucher.generate_voucher_number(voucher_type.code)
            
            voucher = Voucher(
                voucher_number=voucher_number,
                voucher_type_id=form.voucher_type_id.data,
                transaction_date=form.transaction_date.data,
                reference_number=form.reference_number.data,
                narration=form.narration.data,
                party_id=form.party_id.data if form.party_id.data else None,
                party_type=form.party_type.data if form.party_type.data else None,
                total_amount=form.total_amount.data,
                tax_amount=form.tax_amount.data or 0.0,
                discount_amount=form.discount_amount.data or 0.0,
                is_gst_applicable=form.is_gst_applicable.data,
                created_by=current_user.id
            )
            
            db.session.add(voucher)
            db.session.commit()
            
            flash(f'Voucher "{voucher.voucher_number}" created successfully!', 'success')
            return redirect(url_for('accounting.edit_voucher', id=voucher.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating voucher: {str(e)}', 'error')
    
    return render_template('accounting/voucher_form.html', form=form, title='Add Voucher')

@accounting_bp.route('/vouchers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_voucher(id):
    """Edit voucher and manage journal entries"""
    voucher = Voucher.query.get_or_404(id)
    
    if voucher.status == 'posted':
        flash('Cannot edit posted voucher', 'error')
        return redirect(url_for('accounting.view_voucher', id=id))
    
    form = VoucherForm(obj=voucher)
    
    # Populate choices
    form.voucher_type_id.choices = [(vt.id, vt.name) for vt in VoucherType.query.filter_by(is_active=True).all()]
    form.party_id.choices = [('', 'Select Party')] + [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(voucher)
            db.session.commit()
            
            flash(f'Voucher "{voucher.voucher_number}" updated successfully!', 'success')
            return redirect(url_for('accounting.edit_voucher', id=voucher.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating voucher: {str(e)}', 'error')
    
    # Get existing journal entries
    journal_entries = JournalEntry.query.filter_by(voucher_id=voucher.id).all()
    
    return render_template('accounting/voucher_form.html', 
                         form=form, 
                         voucher=voucher, 
                         journal_entries=journal_entries,
                         title='Edit Voucher')

@accounting_bp.route('/vouchers/<int:id>')
@login_required
def view_voucher(id):
    """View voucher details"""
    voucher = Voucher.query.get_or_404(id)
    journal_entries = JournalEntry.query.filter_by(voucher_id=voucher.id).all()
    
    return render_template('accounting/voucher_view.html', 
                         voucher=voucher, 
                         journal_entries=journal_entries)

@accounting_bp.route('/vouchers/<int:id>/post', methods=['POST'])
@login_required
def post_voucher(id):
    """Post voucher to update account balances"""
    voucher = Voucher.query.get_or_404(id)
    
    if voucher.status == 'posted':
        flash('Voucher is already posted', 'warning')
        return redirect(url_for('accounting.view_voucher', id=id))
    
    # Validate journal entries balance
    total_debit = sum(je.amount for je in voucher.journal_entries if je.entry_type == 'debit')
    total_credit = sum(je.amount for je in voucher.journal_entries if je.entry_type == 'credit')
    
    if abs(total_debit - total_credit) > 0.01:
        flash('Journal entries do not balance. Cannot post voucher.', 'error')
        return redirect(url_for('accounting.edit_voucher', id=id))
    
    try:
        voucher.post_voucher(current_user.id)
        flash(f'Voucher "{voucher.voucher_number}" posted successfully!', 'success')
    except Exception as e:
        flash(f'Error posting voucher: {str(e)}', 'error')
    
    return redirect(url_for('accounting.view_voucher', id=id))

# Journal Entry Management
@accounting_bp.route('/vouchers/<int:voucher_id>/journal-entries/add', methods=['POST'])
@login_required
def add_journal_entry(voucher_id):
    """Add journal entry to voucher"""
    voucher = Voucher.query.get_or_404(voucher_id)
    
    if voucher.status == 'posted':
        return jsonify({'success': False, 'message': 'Cannot modify posted voucher'})
    
    try:
        data = request.get_json()
        
        journal_entry = JournalEntry(
            voucher_id=voucher_id,
            account_id=data['account_id'],
            entry_type=data['entry_type'],
            amount=Decimal(str(data['amount'])),
            narration=data.get('narration', ''),
            transaction_date=voucher.transaction_date,
            reference_type=data.get('reference_type'),
            reference_id=data.get('reference_id')
        )
        
        db.session.add(journal_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Journal entry added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Payment and Receipt Forms
@accounting_bp.route('/payments/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    """Quick payment voucher"""
    form = PaymentForm()
    
    # Populate choices
    form.party_id.choices = [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).all()]
    form.bank_account_id.choices = [('', 'Cash Payment')] + [(ba.id, f"{ba.bank_name} - {ba.account_number}") 
                                                           for ba in BankAccount.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            # Get payment voucher type
            payment_voucher_type = VoucherType.query.filter_by(code='PAY').first()
            if not payment_voucher_type:
                flash('Payment voucher type not found. Please create it first.', 'error')
                return redirect(url_for('accounting.add_payment'))
            
            voucher_number = Voucher.generate_voucher_number('PAY')
            
            voucher = Voucher(
                voucher_number=voucher_number,
                voucher_type_id=payment_voucher_type.id,
                transaction_date=form.payment_date.data,
                reference_number=form.reference_number.data,
                narration=form.narration.data,
                party_id=form.party_id.data,
                party_type='supplier',
                total_amount=form.amount.data,
                created_by=current_user.id
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            party = Supplier.query.get(form.party_id.data)
            party_account = Account.query.filter_by(name=party.name).first()
            
            if not party_account:
                # Create party account if doesn't exist
                creditors_group = AccountGroup.query.filter_by(name='Sundry Creditors').first()
                if creditors_group:
                    party_account = Account(
                        name=party.name,
                        code=f"SUP_{party.id}",
                        account_group_id=creditors_group.id,
                        account_type='current_liability'
                    )
                    db.session.add(party_account)
                    db.session.flush()
            
            # Debit party account (reduce liability)
            debit_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=party_account.id,
                entry_type='debit',
                amount=form.amount.data,
                narration=f"Payment to {party.name}",
                transaction_date=form.payment_date.data
            )
            db.session.add(debit_entry)
            
            # Credit cash/bank account
            if form.payment_mode.data == 'cash':
                cash_account = Account.query.filter_by(is_cash_account=True).first()
                if not cash_account:
                    flash('Cash account not found. Please create it first.', 'error')
                    return redirect(url_for('accounting.add_payment'))
                credit_account_id = cash_account.id
            else:
                bank_account = BankAccount.query.get(form.bank_account_id.data)
                credit_account_id = bank_account.account_id
            
            credit_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=credit_account_id,
                entry_type='credit',
                amount=form.amount.data,
                narration=f"Payment to {party.name} via {form.payment_mode.data}",
                transaction_date=form.payment_date.data
            )
            db.session.add(credit_entry)
            
            db.session.commit()
            
            flash(f'Payment voucher "{voucher.voucher_number}" created successfully!', 'success')
            return redirect(url_for('accounting.view_voucher', id=voucher.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating payment: {str(e)}', 'error')
    
    return render_template('accounting/payment_form.html', form=form, title='Add Payment')

# Reports
@accounting_bp.route('/reports')
@login_required
def reports_dashboard():
    """Financial reports dashboard"""
    return render_template('accounting/reports_dashboard.html')

@accounting_bp.route('/reports/day-book')
@login_required
def day_book():
    """Day Book Report - All journal entries"""
    form = ReportFilterForm()
    
    if request.method == 'GET':
        # Default to current month
        form.from_date.data = date.today().replace(day=1)
        form.to_date.data = date.today()
    
    journal_entries = []
    
    if form.validate_on_submit() or request.method == 'GET':
        from_date = form.from_date.data if form.from_date.data else date.today().replace(day=1)
        to_date = form.to_date.data if form.to_date.data else date.today()
        
        journal_entries = JournalEntry.query.filter(
            JournalEntry.transaction_date >= from_date,
            JournalEntry.transaction_date <= to_date
        ).order_by(JournalEntry.transaction_date.desc(), JournalEntry.id.desc()).all()
    
    return render_template('accounting/day_book.html', 
                         form=form,
                         journal_entries=journal_entries,
                         title='Day Book Report')

@accounting_bp.route('/reports/account-ledgers')
@login_required
def account_ledgers():
    """Account Ledgers Report"""
    accounts = Account.query.filter_by(is_active=True).order_by(Account.name).all()
    return render_template('accounting/account_ledgers.html', 
                         accounts=accounts,
                         title='Account Ledgers')

@accounting_bp.route('/reports/outstanding-payables')
@login_required
def outstanding_payables():
    """Outstanding Payables Report"""
    # Get outstanding amounts owed to suppliers
    payables = db.session.execute(text("""
        SELECT 
            s.name as supplier_name,
            SUM(je.amount) as outstanding_amount
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN suppliers s ON v.party_id = s.id
        WHERE je.entry_type = 'credit' 
        AND v.party_type = 'supplier'
        AND v.status = 'posted'
        GROUP BY s.id, s.name
        HAVING SUM(je.amount) > 0
        ORDER BY SUM(je.amount) DESC
    """)).fetchall()
    
    return render_template('accounting/outstanding_payables.html', 
                         payables=payables,
                         title='Outstanding Payables')

@accounting_bp.route('/reports/outstanding-receivables')
@login_required
def outstanding_receivables():
    """Outstanding Receivables Report"""
    # Get outstanding amounts from customers
    receivables = db.session.execute(text("""
        SELECT 
            s.name as customer_name,
            SUM(je.amount) as outstanding_amount
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN suppliers s ON v.party_id = s.id
        WHERE je.entry_type = 'debit' 
        AND v.party_type = 'customer'
        AND v.status = 'posted'
        GROUP BY s.id, s.name
        HAVING SUM(je.amount) > 0
        ORDER BY SUM(je.amount) DESC
    """)).fetchall()
    
    return render_template('accounting/outstanding_receivables.html', 
                         receivables=receivables,
                         title='Outstanding Receivables')

@accounting_bp.route('/reports/account-ledger/<int:account_id>')
@login_required
def account_ledger_detail(account_id):
    """Individual Account Ledger Detail"""
    account = Account.query.get_or_404(account_id)
    form = ReportFilterForm()
    
    if request.method == 'GET':
        form.from_date.data = date.today().replace(day=1)
        form.to_date.data = date.today()
    
    journal_entries = []
    
    if form.validate_on_submit() or request.method == 'GET':
        from_date = form.from_date.data if form.from_date.data else date.today().replace(day=1)
        to_date = form.to_date.data if form.to_date.data else date.today()
        
        journal_entries = JournalEntry.query.filter(
            JournalEntry.account_id == account_id,
            JournalEntry.transaction_date >= from_date,
            JournalEntry.transaction_date <= to_date
        ).order_by(JournalEntry.transaction_date, JournalEntry.id).all()
    
    return render_template('accounting/account_ledger_detail.html', 
                         account=account,
                         form=form,
                         journal_entries=journal_entries,
                         title=f'Ledger - {account.name}')

@accounting_bp.route('/reports/gstr1')
@login_required
def gstr1_report():
    """GSTR-1 Report"""
    form = GSATReportForm()
    return render_template('accounting/gstr1_report.html', 
                         form=form,
                         title='GSTR-1 Report')

@accounting_bp.route('/reports/gstr3b')
@login_required
def gstr3b_report():
    """GSTR-3B Report"""
    form = GSATReportForm()
    return render_template('accounting/gstr3b_report.html', 
                         form=form,
                         title='GSTR-3B Report')

@accounting_bp.route('/receipts/add', methods=['GET', 'POST'])
@login_required
def add_receipt():
    """Add receipt voucher"""
    form = ReceiptForm()
    
    # Populate choices
    form.party_id.choices = [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).all()]
    form.bank_account_id.choices = [('', 'Select Bank Account')] + [(ba.id, f"{ba.bank_name} - {ba.account_number}") for ba in BankAccount.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        try:
            # Create receipt voucher
            voucher_type = VoucherType.query.filter_by(code='RV').first()
            voucher_number = Voucher.generate_voucher_number('RV')
            
            voucher = Voucher(
                voucher_number=voucher_number,
                voucher_type_id=voucher_type.id,
                transaction_date=form.receipt_date.data,
                reference_number=form.reference_number.data,
                narration=form.narration.data,
                party_id=form.party_id.data,
                party_type='customer',
                total_amount=form.amount.data,
                created_by=current_user.id
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            party = Supplier.query.get(form.party_id.data)
            
            # Debit entry for Cash/Bank
            if form.receipt_mode.data == 'cash':
                cash_account = Account.query.filter_by(is_cash_account=True).first()
                debit_account_id = cash_account.id
            else:
                bank_account = BankAccount.query.get(form.bank_account_id.data)
                debit_account_id = bank_account.account_id
            
            debit_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=debit_account_id,
                entry_type='debit',
                amount=form.amount.data,
                narration=f"Receipt from {party.name} via {form.receipt_mode.data}",
                transaction_date=form.receipt_date.data
            )
            db.session.add(debit_entry)
            
            # Credit entry for Customer
            customer_account = Account.query.filter_by(name__ilike=f'%{party.name}%').first()
            if not customer_account:
                # Create customer account if doesn't exist
                accounts_receivable_group = AccountGroup.query.filter_by(code='AR').first()
                customer_account = Account(
                    name=f'{party.name} - Customer',
                    code=f'CUST-{party.id}',
                    account_group_id=accounts_receivable_group.id,
                    account_type='current_asset'
                )
                db.session.add(customer_account)
                db.session.flush()
            
            credit_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='credit',
                amount=form.amount.data,
                narration=f"Receipt from {party.name} via {form.receipt_mode.data}",
                transaction_date=form.receipt_date.data
            )
            db.session.add(credit_entry)
            
            db.session.commit()
            
            flash(f'Receipt voucher "{voucher.voucher_number}" created successfully!', 'success')
            return redirect(url_for('accounting.view_voucher', id=voucher.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating receipt: {str(e)}', 'error')
    
    return render_template('accounting/receipt_form.html', form=form, title='Add Receipt')

@accounting_bp.route('/reports/gst-summary')
@login_required
def gst_summary():
    """GST Summary Report"""
    return render_template('accounting/gst_summary.html', 
                         title='GST Summary Report')

@accounting_bp.route('/reports/inventory-valuation')
@login_required
def inventory_valuation():
    """Inventory Valuation Report"""
    return render_template('accounting/inventory_valuation.html', 
                         title='Inventory Valuation Report')

@accounting_bp.route('/reports/cogs')
@login_required
def cogs_report():
    """Cost of Goods Sold Report"""
    return render_template('accounting/cogs_report.html', 
                         title='Cost of Goods Sold Report')

@accounting_bp.route('/reports/trial-balance')
@login_required
def trial_balance():
    """Trial Balance Report"""
    form = ReportFilterForm()
    
    if request.method == 'GET':
        # Default to current month
        form.from_date.data = date.today().replace(day=1)
        form.to_date.data = date.today()
    
    # Populate choices
    form.account_group_id.choices = [('', 'All Groups')] + [(g.id, g.name) for g in AccountGroup.query.filter_by(is_active=True).all()]
    
    accounts_data = []
    total_debit = 0
    total_credit = 0
    
    if form.validate_on_submit() or request.method == 'GET':
        # Get all accounts with their balances
        accounts = Account.query.filter_by(is_active=True).all()
        
        for account in accounts:
            balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
            
            if balance != 0:
                if account.balance_type == 'debit':
                    debit_balance = balance if balance > 0 else 0
                    credit_balance = -balance if balance < 0 else 0
                else:
                    credit_balance = balance if balance > 0 else 0
                    debit_balance = -balance if balance < 0 else 0
                
                accounts_data.append({
                    'account': account,
                    'debit_balance': debit_balance,
                    'credit_balance': credit_balance
                })
                
                total_debit += debit_balance
                total_credit += credit_balance
    
    return render_template('accounting/trial_balance.html', 
                         form=form, 
                         accounts_data=accounts_data,
                         total_debit=total_debit,
                         total_credit=total_credit)

@accounting_bp.route('/reports/profit-loss')
@login_required
def profit_loss():
    """Profit & Loss Statement"""
    form = ReportFilterForm()
    
    if request.method == 'GET':
        # Default to current month
        form.from_date.data = date.today().replace(day=1)
        form.to_date.data = date.today()
    
    income_accounts = []
    expense_accounts = []
    
    if form.validate_on_submit() or request.method == 'GET':
        # Get income accounts
        income_groups = AccountGroup.query.filter_by(group_type='income', is_active=True).all()
        for group in income_groups:
            for account in group.accounts:
                if account.is_active:
                    balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
                    if balance != 0:
                        income_accounts.append({
                            'account': account,
                            'balance': balance
                        })
        
        # Get expense accounts
        expense_groups = AccountGroup.query.filter_by(group_type='expenses', is_active=True).all()
        for group in expense_groups:
            for account in group.accounts:
                if account.is_active:
                    balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
                    if balance != 0:
                        expense_accounts.append({
                            'account': account,
                            'balance': balance
                        })
    
    total_income = sum(acc['balance'] for acc in income_accounts)
    total_expenses = sum(acc['balance'] for acc in expense_accounts)
    net_profit = total_income - total_expenses
    
    return render_template('accounting/profit_loss.html',
                         form=form,
                         income_accounts=income_accounts,
                         expense_accounts=expense_accounts,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         net_profit=net_profit)

@accounting_bp.route('/reports/balance-sheet')
@login_required
def balance_sheet():
    """Balance Sheet Report"""
    form = ReportFilterForm()
    
    if request.method == 'GET':
        # Default to current date
        form.to_date.data = date.today()
    
    assets = []
    liabilities = []
    equity = []
    
    if form.validate_on_submit() or request.method == 'GET':
        # Get asset accounts
        asset_groups = AccountGroup.query.filter_by(group_type='assets', is_active=True).all()
        for group in asset_groups:
            group_accounts = []
            for account in group.accounts:
                if account.is_active:
                    balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
                    if balance != 0:
                        group_accounts.append({
                            'account': account,
                            'balance': balance
                        })
            if group_accounts:
                assets.append({
                    'group': group,
                    'accounts': group_accounts,
                    'total': sum(acc['balance'] for acc in group_accounts)
                })
        
        # Get liability accounts
        liability_groups = AccountGroup.query.filter_by(group_type='liabilities', is_active=True).all()
        for group in liability_groups:
            group_accounts = []
            for account in group.accounts:
                if account.is_active:
                    balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
                    if balance != 0:
                        group_accounts.append({
                            'account': account,
                            'balance': balance
                        })
            if group_accounts:
                liabilities.append({
                    'group': group,
                    'accounts': group_accounts,
                    'total': sum(acc['balance'] for acc in group_accounts)
                })
        
        # Get equity accounts
        equity_groups = AccountGroup.query.filter_by(group_type='equity', is_active=True).all()
        for group in equity_groups:
            group_accounts = []
            for account in group.accounts:
                if account.is_active:
                    balance = account.calculate_balance(form.to_date.data if form.to_date.data else date.today())
                    if balance != 0:
                        group_accounts.append({
                            'account': account,
                            'balance': balance
                        })
            if group_accounts:
                equity.append({
                    'group': group,
                    'accounts': group_accounts,
                    'total': sum(acc['balance'] for acc in group_accounts)
                })
    
    total_assets = sum(group['total'] for group in assets)
    total_liabilities = sum(group['total'] for group in liabilities)
    total_equity = sum(group['total'] for group in equity)
    
    return render_template('accounting/balance_sheet.html',
                         form=form,
                         assets=assets,
                         liabilities=liabilities,
                         equity=equity,
                         total_assets=total_assets,
                         total_liabilities=total_liabilities,
                         total_equity=total_equity)

@accounting_bp.route('/integration-flowchart')
@login_required
def integration_flowchart():
    """Display the accounting integration flow chart"""
    return render_template('accounting/integration_flowchart.html')

@accounting_bp.route('/reports/cash-flow')
@login_required
def cash_flow():
    """Cash Flow Statement"""
    form = ReportFilterForm()
    
    if request.method == 'GET':
        # Default to current month
        form.from_date.data = date.today().replace(day=1)
        form.to_date.data = date.today()
    
    operating_activities = []
    investing_activities = []
    financing_activities = []
    
    if form.validate_on_submit() or request.method == 'GET':
        from_date = form.from_date.data if form.from_date.data else date.today().replace(day=1)
        to_date = form.to_date.data if form.to_date.data else date.today()
        
        # Get cash movements for the period
        cash_accounts = Account.query.filter_by(is_cash_account=True, is_active=True).all()
        bank_accounts = Account.query.filter_by(is_bank_account=True, is_active=True).all()
        
        cash_and_bank_accounts = cash_accounts + bank_accounts
        
        for account in cash_and_bank_accounts:
            entries = JournalEntry.query.filter(
                JournalEntry.account_id == account.id,
                JournalEntry.transaction_date >= from_date,
                JournalEntry.transaction_date <= to_date
            ).all()
            
            for entry in entries:
                activity_type = 'operating'  # Default classification
                
                # Classify based on voucher type or narration
                if entry.voucher.voucher_type.code in ['SAL', 'PUR']:
                    activity_type = 'operating'
                elif 'investment' in entry.narration.lower() or 'asset' in entry.narration.lower():
                    activity_type = 'investing'
                elif 'loan' in entry.narration.lower() or 'capital' in entry.narration.lower():
                    activity_type = 'financing'
                
                activity_data = {
                    'description': entry.narration,
                    'amount': entry.amount if entry.entry_type == 'debit' else -entry.amount,
                    'date': entry.transaction_date,
                    'voucher': entry.voucher
                }
                
                if activity_type == 'operating':
                    operating_activities.append(activity_data)
                elif activity_type == 'investing':
                    investing_activities.append(activity_data)
                else:
                    financing_activities.append(activity_data)
    
    net_operating = sum(act['amount'] for act in operating_activities)
    net_investing = sum(act['amount'] for act in investing_activities)
    net_financing = sum(act['amount'] for act in financing_activities)
    net_cash_flow = net_operating + net_investing + net_financing
    
    return render_template('accounting/cash_flow.html',
                         form=form,
                         operating_activities=operating_activities,
                         investing_activities=investing_activities,
                         financing_activities=financing_activities,
                         net_operating=net_operating,
                         net_investing=net_investing,
                         net_financing=net_financing,
                         net_cash_flow=net_cash_flow)

# API Endpoints
@accounting_bp.route('/api/accounts')
@login_required
def api_accounts():
    """Get accounts for dropdowns"""
    group_id = request.args.get('group_id', type=int)
    
    query = Account.query.filter_by(is_active=True)
    if group_id:
        query = query.filter_by(account_group_id=group_id)
    
    accounts = query.all()
    
    return jsonify([{
        'id': account.id,
        'name': account.name,
        'code': account.code,
        'balance': account.calculate_balance()
    } for account in accounts])

@accounting_bp.route('/api/party-accounts/<int:party_id>')
@login_required
def api_party_account(party_id):
    """Get or create party account"""
    party = Supplier.query.get_or_404(party_id)
    
    # Try to find existing account
    account = Account.query.filter_by(name=party.name).first()
    
    if not account:
        # Create party account
        if party.is_supplier:
            group = AccountGroup.query.filter_by(name='Sundry Creditors').first()
        else:
            group = AccountGroup.query.filter_by(name='Sundry Debtors').first()
        
        if group:
            account = Account(
                name=party.name,
                code=f"{'SUP' if party.is_supplier else 'CUS'}_{party.id}",
                account_group_id=group.id,
                account_type='current_liability' if party.is_supplier else 'current_asset'
            )
            db.session.add(account)
            db.session.commit()
    
    return jsonify({
        'id': account.id if account else None,
        'name': account.name if account else party.name,
        'balance': account.calculate_balance() if account else 0
    })

# Invoice Management Routes
@accounting_bp.route('/invoices')
@login_required
def list_invoices():
    """List all invoices"""
    page = request.args.get('page', 1, type=int)
    invoice_type = request.args.get('type', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = Invoice.query
    if invoice_type:
        query = query.filter_by(invoice_type=invoice_type)
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    invoices = query.order_by(desc(Invoice.created_at)).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('accounting/invoices_list.html', 
                         invoices=invoices,
                         invoice_type=invoice_type,
                         status_filter=status_filter)

@accounting_bp.route('/invoices/add', methods=['GET', 'POST'])
@login_required
def add_invoice():
    """Add new invoice"""
    form = InvoiceForm()
    
    # Populate party choices
    form.party_id.choices = [(s.id, f"{s.name} ({s.partner_type})") for s in Supplier.query.all()]
    
    if form.validate_on_submit():
        try:
            # Generate invoice number
            invoice_number = Invoice.generate_invoice_number(form.invoice_type.data)
            
            # Get party details
            party = Supplier.query.get(form.party_id.data)
            
            invoice = Invoice(
                invoice_number=invoice_number,
                invoice_type=form.invoice_type.data,
                party_id=form.party_id.data,
                party_name=party.name,
                party_gst=party.gst_number,
                party_address=party.address,
                invoice_date=form.invoice_date.data,
                due_date=form.due_date.data,
                place_of_supply=form.place_of_supply.data,
                reference_type=form.reference_type.data,
                reference_id=form.reference_id.data,
                subtotal=0,  # Will be calculated when items are added
                total_amount=0,
                created_by=current_user.id
            )
            
            db.session.add(invoice)
            db.session.commit()
            
            flash(f'Invoice "{invoice.invoice_number}" created successfully!', 'success')
            return redirect(url_for('accounting.edit_invoice', id=invoice.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invoice: {str(e)}', 'error')
    
    return render_template('accounting/invoice_form.html', form=form, title='Create Invoice')

@accounting_bp.route('/invoices/<int:id>')
@login_required
def view_invoice(id):
    """View invoice details"""
    invoice = Invoice.query.get_or_404(id)
    return render_template('accounting/invoice_detail.html', invoice=invoice)

@accounting_bp.route('/invoices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(id):
    """Edit invoice and manage line items"""
    invoice = Invoice.query.get_or_404(id)
    form = InvoiceForm(obj=invoice)
    
    # Populate party choices
    form.party_id.choices = [(s.id, f"{s.name} ({s.partner_type})") for s in Supplier.query.all()]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(invoice)
            
            # Recalculate totals
            invoice.calculate_tax()
            
            db.session.commit()
            
            flash(f'Invoice "{invoice.invoice_number}" updated successfully!', 'success')
            return redirect(url_for('accounting.view_invoice', id=invoice.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating invoice: {str(e)}', 'error')
    
    # Get all items for dropdown
    items = Item.query.all()
    
    return render_template('accounting/invoice_edit.html', 
                         form=form, 
                         invoice=invoice, 
                         items=items,
                         title='Edit Invoice')

@accounting_bp.route('/invoices/<int:invoice_id>/items/add', methods=['POST'])
@login_required
def add_invoice_item(invoice_id):
    """Add item to invoice via AJAX"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    try:
        data = request.get_json()
        
        # Get item details if item_id provided
        item = None
        if data.get('item_id'):
            item = Item.query.get(data['item_id'])
        
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            item_id=data.get('item_id'),
            item_name=data.get('item_name') or (item.name if item else ''),
            item_code=data.get('item_code') or (item.code if item else ''),
            hsn_code=data.get('hsn_code') or (item.hsn_code if item else ''),
            quantity=float(data['quantity']),
            unit=data.get('unit') or (item.unit_of_measure if item else 'Nos'),
            rate=float(data['rate']),
            line_total=float(data['quantity']) * float(data['rate']),
            gst_rate=float(data.get('gst_rate', 0))
        )
        
        db.session.add(invoice_item)
        
        # Recalculate invoice totals
        invoice.calculate_tax()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item added successfully',
            'item_id': invoice_item.id,
            'subtotal': float(invoice.subtotal),
            'total_tax': float(invoice.total_tax),
            'total_amount': float(invoice.total_amount)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@accounting_bp.route('/invoices/items/<int:item_id>/delete', methods=['DELETE'])
@login_required
def delete_invoice_item(item_id):
    """Delete invoice item via AJAX"""
    try:
        invoice_item = InvoiceItem.query.get_or_404(item_id)
        invoice = invoice_item.invoice
        
        db.session.delete(invoice_item)
        
        # Recalculate invoice totals
        invoice.calculate_tax()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item deleted successfully',
            'subtotal': float(invoice.subtotal),
            'total_tax': float(invoice.total_tax),
            'total_amount': float(invoice.total_amount)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@accounting_bp.route('/invoices/<int:id>/finalize', methods=['POST'])
@login_required
def finalize_invoice(id):
    """Finalize invoice and create accounting entries"""
    invoice = Invoice.query.get_or_404(id)
    
    if invoice.status != 'draft':
        flash('Invoice is already finalized', 'warning')
        return redirect(url_for('accounting.view_invoice', id=id))
    
    try:
        # Update invoice status
        invoice.status = 'sent'
        
        # Create accounting entries
        from services.accounting_automation import AccountingAutomation
        
        if invoice.invoice_type == 'sales':
            AccountingAutomation.create_sales_invoice_entry(invoice)
        else:
            AccountingAutomation.create_purchase_invoice_entry(invoice)
        
        db.session.commit()
        
        flash(f'Invoice "{invoice.invoice_number}" finalized and accounting entries created!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error finalizing invoice: {str(e)}', 'error')
    
    return redirect(url_for('accounting.view_invoice', id=id))

@accounting_bp.route('/invoices/<int:id>/print')
@login_required
def print_invoice(id):
    """Print invoice"""
    invoice = Invoice.query.get_or_404(id)
    
    # Get company details
    company = CompanySettings.query.first()
    
    return render_template('accounting/invoice_print.html', 
                         invoice=invoice, 
                         company=company)