"""
Automatic Journal Entry Generation Service
Integrates accounting with existing factory operations
"""
from app import db
from models.accounting import (Account, AccountGroup, Voucher, VoucherType, JournalEntry, 
                             Invoice, InvoiceItem, TaxMaster)
from models import (PurchaseOrder, SalesOrder, FactoryExpense, Production, Supplier, Item,
                   Employee, SalaryRecord, CompanySettings)
from models.grn import GRN, GRNLineItem
from datetime import datetime, date
from decimal import Decimal

class AccountingAutomation:
    """Service for automatic journal entry generation"""
    
    @staticmethod
    def setup_default_accounts():
        """Create default chart of accounts"""
        try:
            # Create default account groups if they don't exist
            default_groups = [
                {'name': 'Current Assets', 'code': 'CA', 'group_type': 'assets'},
                {'name': 'Fixed Assets', 'code': 'FA', 'group_type': 'assets'},
                {'name': 'Current Liabilities', 'code': 'CL', 'group_type': 'liabilities'},
                {'name': 'Long Term Liabilities', 'code': 'LTL', 'group_type': 'liabilities'},
                {'name': 'Capital & Reserves', 'code': 'CR', 'group_type': 'equity'},
                {'name': 'Sales & Income', 'code': 'SI', 'group_type': 'income'},
                {'name': 'Direct Expenses', 'code': 'DE', 'group_type': 'expenses'},
                {'name': 'Indirect Expenses', 'code': 'IE', 'group_type': 'expenses'},
            ]
            
            for group_data in default_groups:
                existing_group = AccountGroup.query.filter_by(code=group_data['code']).first()
                if not existing_group:
                    group = AccountGroup(**group_data)
                    db.session.add(group)
            
            db.session.flush()
            
            # Create sub-groups
            sub_groups = [
                {'name': 'Inventory', 'code': 'INV', 'group_type': 'assets', 'parent': 'Current Assets'},
                {'name': 'Sundry Debtors', 'code': 'SD', 'group_type': 'assets', 'parent': 'Current Assets'},
                {'name': 'Cash & Bank', 'code': 'CB', 'group_type': 'assets', 'parent': 'Current Assets'},
                {'name': 'Sundry Creditors', 'code': 'SC', 'group_type': 'liabilities', 'parent': 'Current Liabilities'},
                {'name': 'Duties & Taxes', 'code': 'DT', 'group_type': 'liabilities', 'parent': 'Current Liabilities'},
            ]
            
            for sub_group_data in sub_groups:
                existing_sub_group = AccountGroup.query.filter_by(code=sub_group_data['code']).first()
                if not existing_sub_group:
                    parent = AccountGroup.query.filter_by(name=sub_group_data['parent']).first()
                    if parent:
                        sub_group = AccountGroup(
                            name=sub_group_data['name'],
                            code=sub_group_data['code'],
                            group_type=sub_group_data['group_type'],
                            parent_group_id=parent.id
                        )
                        db.session.add(sub_group)
            
            db.session.flush()
            
            # Create default accounts
            default_accounts = [
                # Assets
                {'name': 'Raw Material Inventory', 'code': 'RM_INV', 'group': 'Inventory', 'type': 'current_asset'},
                {'name': 'Work in Progress', 'code': 'WIP_INV', 'group': 'Inventory', 'type': 'current_asset'},
                {'name': 'Finished Goods Inventory', 'code': 'FG_INV', 'group': 'Inventory', 'type': 'current_asset'},
                {'name': 'Scrap Inventory', 'code': 'SCRAP_INV', 'group': 'Inventory', 'type': 'current_asset'},
                {'name': 'Cash Account', 'code': 'CASH', 'group': 'Cash & Bank', 'type': 'current_asset', 'is_cash': True},
                
                # Liabilities
                {'name': 'CGST Payable', 'code': 'CGST_PAY', 'group': 'Duties & Taxes', 'type': 'current_liability'},
                {'name': 'SGST Payable', 'code': 'SGST_PAY', 'group': 'Duties & Taxes', 'type': 'current_liability'},
                {'name': 'IGST Payable', 'code': 'IGST_PAY', 'group': 'Duties & Taxes', 'type': 'current_liability'},
                
                # Income
                {'name': 'Sales Revenue', 'code': 'SALES', 'group': 'Sales & Income', 'type': 'revenue'},
                {'name': 'Job Work Income', 'code': 'JW_INCOME', 'group': 'Sales & Income', 'type': 'revenue'},
                {'name': 'Scrap Sales', 'code': 'SCRAP_SALES', 'group': 'Sales & Income', 'type': 'revenue'},
                
                # Expenses
                {'name': 'Cost of Goods Sold', 'code': 'COGS', 'group': 'Direct Expenses', 'type': 'cost_of_goods_sold'},
                {'name': 'Purchase Expenses', 'code': 'PURCHASE', 'group': 'Direct Expenses', 'type': 'expense'},
                {'name': 'Job Work Charges', 'code': 'JW_CHARGES', 'group': 'Direct Expenses', 'type': 'expense'},
                {'name': 'Wages & Salaries', 'code': 'WAGES', 'group': 'Direct Expenses', 'type': 'expense'},
                {'name': 'Factory Overhead', 'code': 'OVERHEAD', 'group': 'Indirect Expenses', 'type': 'expense'},
                {'name': 'Transportation', 'code': 'TRANSPORT', 'group': 'Indirect Expenses', 'type': 'expense'},
            ]
            
            for account_data in default_accounts:
                existing_account = Account.query.filter_by(code=account_data['code']).first()
                if not existing_account:
                    group = AccountGroup.query.filter_by(name=account_data['group']).first()
                    if group:
                        account = Account(
                            name=account_data['name'],
                            code=account_data['code'],
                            account_group_id=group.id,
                            account_type=account_data['type'],
                            is_cash_account=account_data.get('is_cash', False),
                            is_bank_account=account_data.get('is_bank', False)
                        )
                        db.session.add(account)
            
            # Create default voucher types
            default_voucher_types = [
                {'name': 'Purchase Voucher', 'code': 'PUR'},
                {'name': 'Sales Voucher', 'code': 'SAL'},
                {'name': 'Payment Voucher', 'code': 'PAY'},
                {'name': 'Receipt Voucher', 'code': 'REC'},
                {'name': 'Journal Voucher', 'code': 'JOU'},
                {'name': 'Contra Voucher', 'code': 'CON'},
            ]
            
            for vt_data in default_voucher_types:
                existing_vt = VoucherType.query.filter_by(code=vt_data['code']).first()
                if not existing_vt:
                    vt = VoucherType(**vt_data)
                    db.session.add(vt)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error setting up default accounts: {str(e)}")
            return False
    
    @staticmethod
    def create_purchase_voucher(purchase_order):
        """Create journal entries for purchase order"""
        try:
            # Get purchase voucher type
            voucher_type = VoucherType.query.filter_by(code='PUR').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('PUR'),
                voucher_type_id=voucher_type.id,
                transaction_date=purchase_order.order_date or date.today(),
                reference_number=purchase_order.po_number,
                narration=f"Purchase from {purchase_order.supplier.name}",
                party_id=purchase_order.supplier_id,
                party_type='supplier',
                total_amount=purchase_order.total_amount,
                tax_amount=purchase_order.tax_amount or 0,
                is_gst_applicable=True,
                created_by=purchase_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            inventory_account = Account.query.filter_by(code='RM_INV').first()
            gst_account = Account.query.filter_by(code='CGST_PAY').first()
            supplier_account = AccountingAutomation.get_or_create_party_account(purchase_order.supplier)
            
            if not all([inventory_account, supplier_account]):
                return False
            
            # Debit inventory (raw materials)
            inventory_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=inventory_account.id,
                entry_type='debit',
                amount=purchase_order.subtotal,
                narration=f"Purchase of raw materials - {purchase_order.po_number}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(inventory_entry)
            
            # Debit GST if applicable
            if purchase_order.tax_amount and purchase_order.tax_amount > 0 and gst_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_account.id,
                    entry_type='debit',
                    amount=purchase_order.tax_amount,
                    narration=f"GST on purchases - {purchase_order.po_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='purchase_order',
                    reference_id=purchase_order.id
                )
                db.session.add(gst_entry)
            
            # Credit supplier account
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='credit',
                amount=purchase_order.total_amount,
                narration=f"Purchase from {purchase_order.supplier.name}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(supplier_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating purchase voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_sales_voucher(sales_order):
        """Create journal entries for sales order"""
        try:
            # Get sales voucher type
            voucher_type = VoucherType.query.filter_by(code='SAL').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('SAL'),
                voucher_type_id=voucher_type.id,
                transaction_date=sales_order.order_date or date.today(),
                reference_number=sales_order.so_number,
                narration=f"Sales to {sales_order.customer.name}",
                party_id=sales_order.customer_id,
                party_type='customer',
                total_amount=sales_order.total_amount,
                tax_amount=sales_order.tax_amount or 0,
                is_gst_applicable=True,
                created_by=sales_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            sales_account = Account.query.filter_by(code='SALES').first()
            gst_account = Account.query.filter_by(code='CGST_PAY').first()
            customer_account = AccountingAutomation.get_or_create_party_account(sales_order.customer)
            
            if not all([sales_account, customer_account]):
                return False
            
            # Debit customer account
            customer_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='debit',
                amount=sales_order.total_amount,
                narration=f"Sales to {sales_order.customer.name}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(customer_entry)
            
            # Credit sales account
            sales_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=sales_account.id,
                entry_type='credit',
                amount=sales_order.subtotal,
                narration=f"Sales revenue - {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(sales_entry)
            
            # Credit GST if applicable
            if sales_order.tax_amount and sales_order.tax_amount > 0 and gst_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_account.id,
                    entry_type='credit',
                    amount=sales_order.tax_amount,
                    narration=f"GST on sales - {sales_order.so_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='sales_order',
                    reference_id=sales_order.id
                )
                db.session.add(gst_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sales voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_grn_voucher(grn):
        """Create journal entries for GRN using proper 3-step workflow with clearing account"""
        try:
            # Import here to avoid circular imports
            from services.grn_workflow_automation import GRNWorkflowService
            
            # Use the proper 3-step workflow service
            return GRNWorkflowService.create_grn_material_receipt_voucher(grn)
            
        except Exception as e:
            print(f"Error creating GRN voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_vendor_invoice_voucher(vendor_invoice):
        """Step 2: Create voucher when vendor invoice is received"""
        try:
            # Get purchase voucher type
            voucher_type = VoucherType.query.filter_by(code='PUR').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('VINV'),
                voucher_type_id=voucher_type.id,
                transaction_date=vendor_invoice.invoice_date or date.today(),
                reference_number=vendor_invoice.invoice_number,
                narration=f"Vendor invoice from {vendor_invoice.vendor.name}",
                party_id=vendor_invoice.vendor_id,
                party_type='supplier',
                total_amount=vendor_invoice.total_amount,
                tax_amount=vendor_invoice.gst_amount or 0,
                is_gst_applicable=True,
                created_by=vendor_invoice.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            grn_clearing_account = Account.query.filter_by(code='2150').first()
            gst_input_account = Account.query.filter_by(code='1180').first()
            supplier_account = AccountingAutomation.get_or_create_party_account(vendor_invoice.vendor)
            
            if not all([grn_clearing_account, supplier_account]):
                return False
            
            # Dr. GRN Clearing Account (clear the liability)
            clearing_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=grn_clearing_account.id,
                entry_type='debit',
                amount=vendor_invoice.subtotal,
                narration=f"Clear GRN liability - {vendor_invoice.invoice_number}",
                transaction_date=voucher.transaction_date,
                reference_type='vendor_invoice',
                reference_id=vendor_invoice.id
            )
            db.session.add(clearing_entry)
            
            # Dr. GST Input Tax (if applicable)
            if vendor_invoice.gst_amount and vendor_invoice.gst_amount > 0 and gst_input_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_input_account.id,
                    entry_type='debit',
                    amount=vendor_invoice.gst_amount,
                    narration=f"GST Input Tax - {vendor_invoice.invoice_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='vendor_invoice',
                    reference_id=vendor_invoice.id
                )
                db.session.add(gst_entry)
            
            # Cr. Supplier Account (create payable)
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='credit',
                amount=vendor_invoice.total_amount,
                narration=f"Vendor invoice - {vendor_invoice.invoice_number}",
                transaction_date=voucher.transaction_date,
                reference_type='vendor_invoice',
                reference_id=vendor_invoice.id
            )
            db.session.add(supplier_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating vendor invoice voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_payment_voucher(payment):
        """Step 3: Create voucher when payment is made to vendor"""
        try:
            # Get payment voucher type
            voucher_type = VoucherType.query.filter_by(code='PAY').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('PAY'),
                voucher_type_id=voucher_type.id,
                transaction_date=payment.payment_date or date.today(),
                reference_number=payment.payment_reference,
                narration=f"Payment to {payment.vendor.name}",
                party_id=payment.vendor_id,
                party_type='supplier',
                total_amount=payment.amount,
                created_by=payment.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            supplier_account = AccountingAutomation.get_or_create_party_account(payment.vendor)
            bank_account = Account.query.filter_by(code=payment.payment_account_code).first()
            
            if not bank_account:
                bank_account = Account.query.filter_by(is_cash_account=True).first()
            
            if not all([supplier_account, bank_account]):
                return False
            
            # Dr. Supplier Account (clear payable)
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='debit',
                amount=payment.amount,
                narration=f"Payment to vendor - {payment.payment_reference}",
                transaction_date=voucher.transaction_date,
                reference_type='payment',
                reference_id=payment.id
            )
            db.session.add(supplier_entry)
            
            # Cr. Bank/Cash Account
            bank_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=bank_account.id,
                entry_type='credit',
                amount=payment.amount,
                narration=f"Payment to vendor - {payment.payment_reference}",
                transaction_date=voucher.transaction_date,
                reference_type='payment',
                reference_id=payment.id
            )
            db.session.add(bank_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating payment voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_expense_voucher(factory_expense):
        """Create journal entries for factory expenses"""
        try:
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JOU').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('EXP'),
                voucher_type_id=voucher_type.id,
                transaction_date=factory_expense.expense_date or date.today(),
                reference_number=factory_expense.expense_number,
                narration=factory_expense.description,
                total_amount=factory_expense.total_amount,
                created_by=factory_expense.requested_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get appropriate EXPENSE account based on category (TALLY-LIKE)
            if factory_expense.category == 'salary':
                expense_account = Account.query.filter_by(name='Wages & Salaries').first()
            elif factory_expense.category == 'materials':
                expense_account = Account.query.filter_by(name='Purchase Expenses').first()
            elif factory_expense.category == 'transport':
                expense_account = Account.query.filter_by(name='Transportation').first()
            elif factory_expense.category in ['utilities', 'maintenance', 'overhead']:
                expense_account = Account.query.filter_by(name='Factory Overhead').first()
            else:
                # Default to Factory Overhead for other expenses
                expense_account = Account.query.filter_by(name='Factory Overhead').first()
            
            cash_account = Account.query.filter_by(is_cash_account=True).first()
            
            # If expense account not found, create it in Direct Expenses group
            if not expense_account:
                expense_group = AccountGroup.query.filter_by(name='Direct Expenses').first()
                if expense_group and factory_expense.category == 'salary':
                    expense_account = Account(
                        name='Wages & Salaries',
                        code='WAGES',
                        account_group_id=expense_group.id,
                        account_type='expense'
                    )
                    db.session.add(expense_account)
                    db.session.flush()
            
            if not all([expense_account, cash_account]):
                return False
            
            # Debit expense account
            expense_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=expense_account.id,
                entry_type='debit',
                amount=factory_expense.total_amount,
                narration=factory_expense.description,
                transaction_date=voucher.transaction_date,
                reference_type='factory_expense',
                reference_id=factory_expense.id
            )
            db.session.add(expense_entry)
            
            # Credit cash/bank account based on payment mode
            if factory_expense.payment_mode == 'cash':
                credit_account = cash_account
            else:
                # For now, use cash account; in future, implement bank account selection
                credit_account = cash_account
            
            cash_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=credit_account.id,
                entry_type='credit',
                amount=factory_expense.total_amount,
                narration=f"Expense payment - {factory_expense.payment_mode}",
                transaction_date=voucher.transaction_date,
                reference_type='factory_expense',
                reference_id=factory_expense.id
            )
            db.session.add(cash_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating expense voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_salary_voucher(salary_record):
        """Create journal entries for salary payments"""
        try:
            # Get payment voucher type
            voucher_type = VoucherType.query.filter_by(code='PAY').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('SAL'),
                voucher_type_id=voucher_type.id,
                transaction_date=salary_record.payment_date or date.today(),
                reference_number=salary_record.salary_number,
                narration=f"Salary payment to {salary_record.employee.name}",
                total_amount=salary_record.net_salary,
                created_by=1  # System user
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            wages_account = Account.query.filter_by(code='WAGES').first()
            cash_account = Account.query.filter_by(is_cash_account=True).first()
            
            if not all([wages_account, cash_account]):
                return False
            
            # Debit wages account
            wages_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=wages_account.id,
                entry_type='debit',
                amount=salary_record.net_salary,
                narration=f"Salary to {salary_record.employee.name} for {salary_record.pay_period_start} to {salary_record.pay_period_end}",
                transaction_date=voucher.transaction_date,
                reference_type='salary_record',
                reference_id=salary_record.id
            )
            db.session.add(wages_entry)
            
            # Credit cash account
            cash_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=cash_account.id,
                entry_type='credit',
                amount=salary_record.net_salary,
                narration=f"Salary payment to {salary_record.employee.name}",
                transaction_date=voucher.transaction_date,
                reference_type='salary_record',
                reference_id=salary_record.id
            )
            db.session.add(cash_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating salary voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_job_work_cost_entry(job_work_rate):
        """Create cost accounting entry for job work rate updates"""
        try:
            # Get journal voucher type for cost allocation
            voucher_type = VoucherType.query.filter_by(code='JNL').first()
            if not voucher_type:
                return False
            
            # Create voucher for cost allocation
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('JWR'),
                voucher_type_id=voucher_type.id,
                transaction_date=date.today(),
                reference_number=f'JWR-{job_work_rate.id}',
                narration=f"Job work rate allocation for {job_work_rate.item.name}",
                total_amount=job_work_rate.rate_per_unit,
                created_by=job_work_rate.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get cost accounts
            work_in_process_account = Account.query.filter_by(code='WIP_INV').first()
            job_work_charges_account = Account.query.filter_by(code='JW_CHARGES').first()
            
            if not all([work_in_process_account, job_work_charges_account]):
                return False
            
            # Debit WIP account for job work allocation
            wip_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=work_in_process_account.id,
                entry_type='debit',
                amount=job_work_rate.rate_per_unit,
                narration=f"Job work allocation for {job_work_rate.item.name}",
                transaction_date=voucher.transaction_date,
                reference_type='job_work_rate',
                reference_id=job_work_rate.id
            )
            db.session.add(wip_entry)
            
            # Credit job work charges account
            charges_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=job_work_charges_account.id,
                entry_type='credit',
                amount=job_work_rate.rate_per_unit,
                narration=f"Standard rate for {job_work_rate.item.name} - {job_work_rate.process_type or 'General'}",
                transaction_date=voucher.transaction_date,
                reference_type='job_work_rate',
                reference_id=job_work_rate.id
            )
            db.session.add(charges_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating job work cost entry: {str(e)}")
            return False
    
    @staticmethod
    def get_or_create_party_account(party):
        """Get or create account for supplier/customer"""
        try:
            # Try to find existing account
            account = Account.query.filter_by(name=party.name).first()
            
            if not account:
                # Determine account group based on party type
                if party.is_supplier:
                    group = AccountGroup.query.filter_by(name='Sundry Creditors').first()
                    account_type = 'current_liability'
                    code_prefix = 'SUP'
                else:
                    group = AccountGroup.query.filter_by(name='Sundry Debtors').first()
                    account_type = 'current_asset'
                    code_prefix = 'CUS'
                
                if group:
                    account = Account(
                        name=party.name,
                        code=f"{code_prefix}_{party.id}",
                        account_group_id=group.id,
                        account_type=account_type
                    )
                    db.session.add(account)
                    db.session.flush()
            
            return account
            
        except Exception as e:
            print(f"Error creating party account: {str(e)}")
            return None
    
    @staticmethod
    def create_cogs_entry(production):
        """Create Cost of Goods Sold entry for production"""
        try:
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JOU').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('PROD'),
                voucher_type_id=voucher_type.id,
                transaction_date=production.production_date or date.today(),
                reference_number=production.production_number,
                narration=f"Production of {production.item.name}",
                total_amount=production.total_cost or 0,
                created_by=production.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            wip_account = Account.query.filter_by(code='WIP_INV').first()
            fg_account = Account.query.filter_by(code='FG_INV').first()
            rm_account = Account.query.filter_by(code='RM_INV').first()
            
            if not all([wip_account, fg_account, rm_account]):
                return False
            
            # Transfer from Raw Materials to WIP
            if production.bom and production.bom.items:
                total_material_cost = sum(
                    (bom_item.qty_required or 0) * (bom_item.unit_cost or 0) 
                    for bom_item in production.bom.items
                )
                
                if total_material_cost > 0:
                    # Debit WIP
                    wip_entry = JournalEntry(
                        voucher_id=voucher.id,
                        account_id=wip_account.id,
                        entry_type='debit',
                        amount=total_material_cost,
                        narration=f"Material consumption for {production.item.name}",
                        transaction_date=voucher.transaction_date,
                        reference_type='production',
                        reference_id=production.id
                    )
                    db.session.add(wip_entry)
                    
                    # Credit Raw Materials
                    rm_entry = JournalEntry(
                        voucher_id=voucher.id,
                        account_id=rm_account.id,
                        entry_type='credit',
                        amount=total_material_cost,
                        narration=f"Material issued for production",
                        transaction_date=voucher.transaction_date,
                        reference_type='production',
                        reference_id=production.id
                    )
                    db.session.add(rm_entry)
            
            # Transfer from WIP to Finished Goods when completed
            if production.status == 'completed' and production.total_cost:
                # Debit Finished Goods
                fg_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=fg_account.id,
                    entry_type='debit',
                    amount=production.total_cost,
                    narration=f"Completed production of {production.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='production',
                    reference_id=production.id
                )
                db.session.add(fg_entry)
                
                # Credit WIP
                wip_completion_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=wip_account.id,
                    entry_type='credit',
                    amount=production.total_cost,
                    narration=f"Production completion transfer",
                    transaction_date=voucher.transaction_date,
                    reference_type='production',
                    reference_id=production.id
                )
                db.session.add(wip_completion_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating production voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_purchase_order_voucher(purchase_order):
        """Create purchase commitment voucher when PO is confirmed"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account
            
            # Get or create purchase order voucher type
            voucher_type = VoucherType.query.filter_by(code='POV').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Purchase Order Voucher',
                    code='POV',
                    description='Purchase Order Commitments'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('POV'),
                voucher_type_id=voucher_type.id,
                transaction_date=purchase_order.order_date,
                reference_number=purchase_order.po_number,
                narration=f"Purchase Order commitment - {purchase_order.po_number}",
                party_id=purchase_order.supplier_id,
                party_type='supplier',
                total_amount=purchase_order.total_amount,
                created_by=purchase_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get or create accounts (TALLY-LIKE ACCOUNTING)
            supplier_account = AccountingAutomation.get_or_create_party_account(purchase_order.supplier)
            
            # Use proper PURCHASE EXPENSE account (expense) - NOT liability commitment
            purchase_expense_account = Account.query.filter_by(name='Purchase Expenses').first()
            
            if not purchase_expense_account:
                # Create Purchase Expense account in Expenses group
                expense_group = AccountGroup.query.filter_by(name='Direct Expenses').first()
                if expense_group:
                    purchase_expense_account = Account(
                        name='Purchase Expenses',
                        code='PURCHASE_EXP',
                        account_group_id=expense_group.id,
                        account_type='expense'
                    )
                    db.session.add(purchase_expense_account)
                    db.session.flush()
            
            if not all([supplier_account, purchase_expense_account]):
                return False
            
            # Create journal entries (PROPER TALLY-LIKE DOUBLE ENTRY)
            # Debit Purchase Expenses (Expense increases)
            purchase_expense_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=purchase_expense_account.id,
                entry_type='debit',
                amount=purchase_order.total_amount,
                narration=f"Purchase expense - {purchase_order.po_number}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(purchase_expense_entry)
            
            # Credit Supplier Account (Liability increases)
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='credit',
                amount=purchase_order.total_amount,
                narration=f"Purchase from {purchase_order.supplier.name} - {purchase_order.po_number}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(supplier_entry)
            
            # Update PO with accounting references
            purchase_order.supplier_account_id = supplier_account.id
            purchase_order.purchase_commitment_voucher_id = voucher.id
            purchase_order.accounting_status = 'expense_recognized'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating purchase order voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_advance_payment_voucher(purchase_order, amount, payment_account_id, notes=None):
        """Create advance payment voucher for PO"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account
            
            # Get payment voucher type
            voucher_type = VoucherType.query.filter_by(code='PAY').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('APV'),
                voucher_type_id=voucher_type.id,
                transaction_date=datetime.now().date(),
                reference_number=f"ADV-{purchase_order.po_number}",
                narration=f"Advance payment for PO {purchase_order.po_number}",
                party_id=purchase_order.supplier_id,
                party_type='supplier',
                total_amount=amount,
                created_by=purchase_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            supplier_account = Account.query.get(purchase_order.supplier_account_id)
            payment_account = Account.query.get(payment_account_id)
            
            if not all([supplier_account, payment_account]):
                return False
            
            # Create journal entries
            # Debit Supplier Account (reduce liability)
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='debit',
                amount=amount,
                narration=f"Advance payment to {purchase_order.supplier.name}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(supplier_entry)
            
            # Credit Bank/Cash Account
            payment_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=payment_account.id,
                entry_type='credit',
                amount=amount,
                narration=f"Advance payment for PO {purchase_order.po_number}",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(payment_entry)
            
            # Update PO
            purchase_order.advance_payment_voucher_id = voucher.id
            purchase_order.advance_amount_paid += amount
            if purchase_order.advance_amount_paid > 0:
                purchase_order.accounting_status = 'advance_paid'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating advance payment voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_sales_order_voucher(sales_order):
        """Create sales booking voucher when SO is confirmed"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account, AccountGroup
            
            # Get or create sales order voucher type
            voucher_type = VoucherType.query.filter_by(code='SOV').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Sales Order Voucher',
                    code='SOV',
                    description='Sales Order Bookings'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('SOV'),
                voucher_type_id=voucher_type.id,
                transaction_date=sales_order.order_date,
                reference_number=sales_order.so_number,
                narration=f"Sales Order booking - {sales_order.so_number}",
                party_id=sales_order.customer_id,
                party_type='customer',
                total_amount=sales_order.total_amount,
                created_by=sales_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get or create accounts (TALLY-LIKE ACCOUNTING)
            customer_account = AccountingAutomation.get_or_create_party_account(sales_order.customer)
            
            # Use proper SALES REVENUE account (income) - NOT asset booking
            sales_revenue_account = Account.query.filter_by(name='Sales Revenue').first()
            
            if not sales_revenue_account:
                # Create Sales Revenue account in Income group
                income_group = AccountGroup.query.filter_by(name='Sales & Income').first()
                if income_group:
                    sales_revenue_account = Account(
                        name='Sales Revenue',
                        code='SALES_REV',
                        account_group_id=income_group.id,
                        account_type='income'
                    )
                    db.session.add(sales_revenue_account)
                    db.session.flush()
            
            if not all([customer_account, sales_revenue_account]):
                return False
            
            # Create journal entries (PROPER TALLY-LIKE DOUBLE ENTRY)
            # Debit Customer Account (Sundry Debtors) - Asset increases
            customer_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='debit',
                amount=sales_order.total_amount,
                narration=f"Sales to {sales_order.customer.name} - {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(customer_entry)
            
            # Credit Sales Revenue Account (Income) - Revenue increases
            sales_revenue_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=sales_revenue_account.id,
                entry_type='credit',
                amount=sales_order.total_amount,
                narration=f"Sales revenue - {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(sales_revenue_entry)
            
            # Update SO with accounting references
            sales_order.customer_account_id = customer_account.id
            sales_order.sales_booking_voucher_id = voucher.id
            sales_order.accounting_status = 'revenue_recognized'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sales order voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_advance_receipt_voucher(sales_order, amount, receipt_account_id, notes=None):
        """Create advance receipt voucher for SO"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account
            
            # Get receipt voucher type
            voucher_type = VoucherType.query.filter_by(code='REC').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('ARV'),
                voucher_type_id=voucher_type.id,
                transaction_date=datetime.now().date(),
                reference_number=f"ADV-{sales_order.so_number}",
                narration=f"Advance receipt for SO {sales_order.so_number}",
                party_id=sales_order.customer_id,
                party_type='customer',
                total_amount=amount,
                created_by=sales_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            customer_account = Account.query.get(sales_order.customer_account_id)
            receipt_account = Account.query.get(receipt_account_id)
            
            if not all([customer_account, receipt_account]):
                return False
            
            # Create journal entries
            # Debit Bank/Cash Account
            receipt_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=receipt_account.id,
                entry_type='debit',
                amount=amount,
                narration=f"Advance receipt for SO {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(receipt_entry)
            
            # Credit Customer Account (reduce asset)
            customer_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='credit',
                amount=amount,
                narration=f"Advance from {sales_order.customer.name}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(customer_entry)
            
            # Update SO
            sales_order.advance_receipt_voucher_id = voucher.id
            sales_order.advance_amount_received += amount
            if sales_order.advance_amount_received > 0:
                sales_order.accounting_status = 'advance_received'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating advance receipt voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_sales_delivery_voucher(sales_order):
        """Create sales voucher when SO is delivered (revenue recognition)"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account, AccountGroup
            
            # Get sales voucher type
            voucher_type = VoucherType.query.filter_by(code='SAL').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('SAL'),
                voucher_type_id=voucher_type.id,
                transaction_date=datetime.now().date(),
                reference_number=sales_order.so_number,
                narration=f"Sales delivery - {sales_order.so_number}",
                party_id=sales_order.customer_id,
                party_type='customer',
                total_amount=sales_order.total_amount,
                created_by=sales_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            customer_account = Account.query.get(sales_order.customer_account_id)
            sales_account = Account.query.filter_by(code='SALES').first()
            gst_output_account = Account.query.filter_by(code='GST_OUTPUT').first()
            booking_account = Account.query.filter_by(code='SO_BOOKING').first()
            
            if not all([customer_account, sales_account, booking_account]):
                return False
            
            # Create journal entries
            # Debit Sales Booking Account (reverse booking)
            booking_reverse_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=booking_account.id,
                entry_type='debit',
                amount=sales_order.total_amount,
                narration=f"Reverse sales booking - {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(booking_reverse_entry)
            
            # Credit Sales Account (Revenue recognition)
            sales_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=sales_account.id,
                entry_type='credit',
                amount=sales_order.subtotal,
                narration=f"Sales revenue - {sales_order.so_number}",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(sales_entry)
            
            # Credit GST Output (if applicable)
            if sales_order.gst_amount > 0 and gst_output_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_output_account.id,
                    entry_type='credit',
                    amount=sales_order.gst_amount,
                    narration=f"Output GST - {sales_order.so_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='sales_order',
                    reference_id=sales_order.id
                )
                db.session.add(gst_entry)
            
            # Update SO
            sales_order.sales_voucher_id = voucher.id
            sales_order.accounting_status = 'delivered'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sales delivery voucher: {str(e)}")
            return False
    
    @staticmethod
    def close_purchase_order_voucher(purchase_order):
        """Close PO accounting entries when PO is completed"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account
            
            if not purchase_order.purchase_commitment_voucher_id:
                return True  # No commitment to close
            
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JOU').first()
            if not voucher_type:
                return False
            
            # Create closing voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('JOU'),
                voucher_type_id=voucher_type.id,
                transaction_date=datetime.now().date(),
                reference_number=f"CLOSE-{purchase_order.po_number}",
                narration=f"Close PO commitment - {purchase_order.po_number}",
                party_id=purchase_order.supplier_id,
                party_type='supplier',
                total_amount=purchase_order.total_amount,
                created_by=purchase_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            supplier_account = Account.query.get(purchase_order.supplier_account_id)
            commitment_account = Account.query.filter_by(code='PO_COMMIT').first()
            
            if not all([supplier_account, commitment_account]):
                return False
            
            # Reverse the commitment entries
            # Credit Purchase Commitments
            commitment_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=commitment_account.id,
                entry_type='credit',
                amount=purchase_order.total_amount,
                narration=f"Close purchase commitment",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(commitment_entry)
            
            # Debit Supplier Account
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='debit',
                amount=purchase_order.total_amount,
                narration=f"Close supplier commitment",
                transaction_date=voucher.transaction_date,
                reference_type='purchase_order',
                reference_id=purchase_order.id
            )
            db.session.add(supplier_entry)
            
            # Update PO status
            purchase_order.accounting_status = 'closed'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error closing purchase order voucher: {str(e)}")
            return False
    
    @staticmethod
    def close_sales_order_voucher(sales_order):
        """Close SO accounting entries when SO is completed"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account
            
            if not sales_order.sales_booking_voucher_id:
                return True  # No booking to close
            
            # If already delivered, just update status
            if sales_order.accounting_status == 'delivered':
                sales_order.accounting_status = 'closed'
                db.session.commit()
                return True
            
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JOU').first()
            if not voucher_type:
                return False
            
            # Create closing voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('JOU'),
                voucher_type_id=voucher_type.id,
                transaction_date=datetime.now().date(),
                reference_number=f"CLOSE-{sales_order.so_number}",
                narration=f"Close SO booking - {sales_order.so_number}",
                party_id=sales_order.customer_id,
                party_type='customer',
                total_amount=sales_order.total_amount,
                created_by=sales_order.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            customer_account = Account.query.get(sales_order.customer_account_id)
            booking_account = Account.query.filter_by(code='SO_BOOKING').first()
            
            if not all([customer_account, booking_account]):
                return False
            
            # Reverse the booking entries
            # Debit Sales Booking Account
            booking_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=booking_account.id,
                entry_type='debit',
                amount=sales_order.total_amount,
                narration=f"Close sales booking",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(booking_entry)
            
            # Credit Customer Account
            customer_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='credit',
                amount=sales_order.total_amount,
                narration=f"Close customer booking",
                transaction_date=voucher.transaction_date,
                reference_type='sales_order',
                reference_id=sales_order.id
            )
            db.session.add(customer_entry)
            
            # Update SO status
            sales_order.accounting_status = 'closed'
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error closing sales order voucher: {str(e)}")
            return False
    
    @staticmethod
    def create_sales_invoice_entry(invoice):
        """Create accounting entries for sales invoice"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account, AccountGroup
            
            # Get or create sales voucher type
            voucher_type = VoucherType.query.filter_by(code='SAL').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Sales Invoice',
                    code='SAL',
                    description='Sales Invoice Entries'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('SAL'),
                voucher_type_id=voucher_type.id,
                transaction_date=invoice.invoice_date,
                reference_number=invoice.invoice_number,
                narration=f"Sales invoice - {invoice.invoice_number}",
                party_id=invoice.party_id,
                party_type='customer',
                total_amount=invoice.total_amount,
                created_by=invoice.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get or create accounts
            customer_account = AccountingAutomation.get_or_create_party_account(invoice.party)
            sales_account = Account.query.filter_by(code='SALES').first()
            gst_output_account = Account.query.filter_by(code='GST_OUTPUT').first()
            
            if not sales_account:
                # Create sales account
                income_group = AccountGroup.query.filter_by(name='Sales & Income').first()
                if income_group:
                    sales_account = Account(
                        name='Sales Account',
                        code='SALES',
                        account_group_id=income_group.id,
                        account_type='income'
                    )
                    db.session.add(sales_account)
                    db.session.flush()
            
            if not gst_output_account and invoice.total_tax > 0:
                # Create GST output account
                liability_group = AccountGroup.query.filter_by(name='Duties & Taxes').first()
                if liability_group:
                    gst_output_account = Account(
                        name='GST Output',
                        code='GST_OUTPUT',
                        account_group_id=liability_group.id,
                        account_type='current_liability'
                    )
                    db.session.add(gst_output_account)
                    db.session.flush()
            
            if not all([customer_account, sales_account]):
                return False
            
            # Create journal entries
            # Debit Customer Account (Accounts Receivable)
            customer_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=customer_account.id,
                entry_type='debit',
                amount=invoice.total_amount,
                narration=f"Sales to {invoice.party_name}",
                transaction_date=voucher.transaction_date,
                reference_type='invoice',
                reference_id=invoice.id
            )
            db.session.add(customer_entry)
            
            # Credit Sales Account
            sales_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=sales_account.id,
                entry_type='credit',
                amount=invoice.subtotal,
                narration=f"Sales revenue - {invoice.invoice_number}",
                transaction_date=voucher.transaction_date,
                reference_type='invoice',
                reference_id=invoice.id
            )
            db.session.add(sales_entry)
            
            # Credit GST Output Account (if applicable)
            if invoice.total_tax > 0 and gst_output_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_output_account.id,
                    entry_type='credit',
                    amount=invoice.total_tax,
                    narration=f"Output GST - {invoice.invoice_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='invoice',
                    reference_id=invoice.id
                )
                db.session.add(gst_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sales invoice entry: {str(e)}")
            return False
    
    @staticmethod
    def create_purchase_invoice_entry(invoice):
        """Create accounting entries for purchase invoice"""
        try:
            from models.accounting import VoucherType, Voucher, JournalEntry, Account, AccountGroup
            
            # Get or create purchase voucher type
            voucher_type = VoucherType.query.filter_by(code='PUR').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Purchase Invoice',
                    code='PUR',
                    description='Purchase Invoice Entries'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('PUR'),
                voucher_type_id=voucher_type.id,
                transaction_date=invoice.invoice_date,
                reference_number=invoice.invoice_number,
                narration=f"Purchase invoice - {invoice.invoice_number}",
                party_id=invoice.party_id,
                party_type='supplier',
                total_amount=invoice.total_amount,
                created_by=invoice.created_by
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get or create accounts
            supplier_account = AccountingAutomation.get_or_create_party_account(invoice.party)
            purchase_account = Account.query.filter_by(code='PURCHASES').first()
            gst_input_account = Account.query.filter_by(code='GST_INPUT').first()
            
            if not purchase_account:
                # Create purchase account
                expense_group = AccountGroup.query.filter_by(name='Direct Expenses').first()
                if expense_group:
                    purchase_account = Account(
                        name='Purchase Account',
                        code='PURCHASES',
                        account_group_id=expense_group.id,
                        account_type='expense'
                    )
                    db.session.add(purchase_account)
                    db.session.flush()
            
            if not gst_input_account and invoice.total_tax > 0:
                # Create GST input account
                asset_group = AccountGroup.query.filter_by(name='Current Assets').first()
                if asset_group:
                    gst_input_account = Account(
                        name='GST Input',
                        code='GST_INPUT',
                        account_group_id=asset_group.id,
                        account_type='current_asset'
                    )
                    db.session.add(gst_input_account)
                    db.session.flush()
            
            if not all([supplier_account, purchase_account]):
                return False
            
            # Create journal entries
            # Debit Purchase Account
            purchase_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=purchase_account.id,
                entry_type='debit',
                amount=invoice.subtotal,
                narration=f"Purchase from {invoice.party_name}",
                transaction_date=voucher.transaction_date,
                reference_type='invoice',
                reference_id=invoice.id
            )
            db.session.add(purchase_entry)
            
            # Debit GST Input Account (if applicable)
            if invoice.total_tax > 0 and gst_input_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_input_account.id,
                    entry_type='debit',
                    amount=invoice.total_tax,
                    narration=f"Input GST - {invoice.invoice_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='invoice',
                    reference_id=invoice.id
                )
                db.session.add(gst_entry)
            
            # Credit Supplier Account (Accounts Payable)
            supplier_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=supplier_account.id,
                entry_type='credit',
                amount=invoice.total_amount,
                narration=f"Purchase from {invoice.party_name}",
                transaction_date=voucher.transaction_date,
                reference_type='invoice',
                reference_id=invoice.id
            )
            db.session.add(supplier_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating purchase invoice entry: {str(e)}")
            return False
    
    @staticmethod
    def create_inventory_valuation_entry(item, quantity_change, valuation_change, movement_type):
        """Create inventory valuation entry for stock movements"""
        try:
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JNL').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('INV'),
                voucher_type_id=voucher_type.id,
                transaction_date=date.today(),
                reference_number=f'INV-{item.code}',
                narration=f"Inventory {movement_type} for {item.name}",
                total_amount=abs(valuation_change),
                created_by=1  # System user
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get inventory accounts based on item state
            raw_material_account = Account.query.filter_by(code='RM_INV').first()
            wip_account = Account.query.filter_by(code='WIP_INV').first()
            finished_goods_account = Account.query.filter_by(code='FG_INV').first()
            scrap_account = Account.query.filter_by(code='SCRAP_INV').first()
            cogs_account = Account.query.filter_by(code='COGS').first()
            
            # Determine which inventory account to use
            inventory_account = raw_material_account  # Default
            if hasattr(item, 'item_type') and item.item_type:
                if item.item_type in ['finished_goods', 'finished']:
                    inventory_account = finished_goods_account
                elif item.item_type in ['work_in_progress', 'wip']:
                    inventory_account = wip_account
                elif item.item_type in ['scrap']:
                    inventory_account = scrap_account
            
            if not all([inventory_account, cogs_account]):
                return False
            
            # Create journal entries based on movement type
            if movement_type in ['receipt', 'production', 'adjustment_in']:
                # Debit inventory, Credit COGS (for positive adjustments)
                inventory_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=inventory_account.id,
                    entry_type='debit',
                    amount=abs(valuation_change),
                    narration=f"{movement_type.title()} - {item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='inventory_movement',
                    reference_id=item.id
                )
                db.session.add(inventory_entry)
                
                cogs_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=cogs_account.id,
                    entry_type='credit',
                    amount=abs(valuation_change),
                    narration=f"Inventory increase - {item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='inventory_movement',
                    reference_id=item.id
                )
                db.session.add(cogs_entry)
                
            elif movement_type in ['issue', 'consumption', 'adjustment_out']:
                # Credit inventory, Debit COGS (for negative adjustments)
                cogs_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=cogs_account.id,
                    entry_type='debit',
                    amount=abs(valuation_change),
                    narration=f"{movement_type.title()} - {item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='inventory_movement',
                    reference_id=item.id
                )
                db.session.add(cogs_entry)
                
                inventory_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=inventory_account.id,
                    entry_type='credit',
                    amount=abs(valuation_change),
                    narration=f"Inventory decrease - {item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='inventory_movement',
                    reference_id=item.id
                )
                db.session.add(inventory_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating inventory valuation entry: {str(e)}")
            return False
    
    @staticmethod
    def create_bom_cost_allocation_entry(bom):
        """Create cost allocation entries for BOM calculations"""
        try:
            # Get journal voucher type
            voucher_type = VoucherType.query.filter_by(code='JNL').first()
            if not voucher_type:
                return False
            
            # Create voucher
            voucher = Voucher(
                voucher_number=Voucher.generate_voucher_number('BOM'),
                voucher_type_id=voucher_type.id,
                transaction_date=date.today(),
                reference_number=f'BOM-{bom.id}',
                narration=f"BOM cost allocation for {bom.item.name}",
                total_amount=bom.total_cost_per_unit or 0,
                created_by=1  # System user
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Get cost accounts
            material_cost_account = Account.query.filter_by(code='RM_INV').first()
            labor_cost_account = Account.query.filter_by(code='WAGES').first()
            overhead_account = Account.query.filter_by(code='OVERHEAD').first()
            wip_account = Account.query.filter_by(code='WIP_INV').first()
            
            if not all([material_cost_account, wip_account]):
                return False
            
            # Material cost allocation
            if bom.material_cost_per_unit and bom.material_cost_per_unit > 0:
                material_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=wip_account.id,
                    entry_type='debit',
                    amount=bom.material_cost_per_unit,
                    narration=f"Material cost allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(material_entry)
                
                material_credit = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=material_cost_account.id,
                    entry_type='credit',
                    amount=bom.material_cost_per_unit,
                    narration=f"Material cost allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(material_credit)
            
            # Labor cost allocation
            if bom.labor_cost_per_unit and bom.labor_cost_per_unit > 0 and labor_cost_account:
                labor_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=wip_account.id,
                    entry_type='debit',
                    amount=bom.labor_cost_per_unit,
                    narration=f"Labor cost allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(labor_entry)
                
                labor_credit = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=labor_cost_account.id,
                    entry_type='credit',
                    amount=bom.labor_cost_per_unit,
                    narration=f"Labor cost allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(labor_credit)
            
            # Overhead allocation
            if bom.overhead_cost_per_unit and bom.overhead_cost_per_unit > 0 and overhead_account:
                overhead_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=wip_account.id,
                    entry_type='debit',
                    amount=bom.overhead_cost_per_unit,
                    narration=f"Overhead allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(overhead_entry)
                
                overhead_credit = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=overhead_account.id,
                    entry_type='credit',
                    amount=bom.overhead_cost_per_unit,
                    narration=f"Overhead allocation - {bom.item.name}",
                    transaction_date=voucher.transaction_date,
                    reference_type='bom',
                    reference_id=bom.id
                )
                db.session.add(overhead_credit)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating BOM cost allocation entry: {str(e)}")
            return False