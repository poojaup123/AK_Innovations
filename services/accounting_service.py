"""Accounting Service for Job Work, GRN, and Production integration"""

from app import db
from models import CompanySettings
from models.accounting import JournalEntry, Account
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AccountingService:
    """Comprehensive accounting integration for manufacturing operations"""
    
    @staticmethod
    def create_grn_accounting_entries(grn):
        """Create accounting entries for GRN (Step 2: Invoice Processing)"""
        try:
            entries = []
            
            # Get or create required accounts
            accounts = AccountingService._get_required_accounts()
            
            if grn.receipt_type == 'job_work':
                # Job Work GRN Entries
                # Dr. GRN Clearing Account
                # Cr. Vendor Payable
                
                clearing_entry = JournalEntry(
                    entry_number=AccountingService._generate_entry_number('GRN'),
                    entry_date=grn.invoice_date or datetime.utcnow().date(),
                    entry_type='grn_job_work',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['grn_clearing'],
                    debit_amount=grn.final_amount,
                    credit_amount=0.0,
                    description=f"Job Work GRN - {grn.grn_number} - {grn.supplier.name}",
                    created_by=1  # System user
                )
                db.session.add(clearing_entry)
                entries.append(clearing_entry)
                
                payable_entry = JournalEntry(
                    entry_number=clearing_entry.entry_number,
                    entry_date=clearing_entry.entry_date,
                    entry_type='grn_job_work',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['vendor_payable'],
                    debit_amount=0.0,
                    credit_amount=grn.final_amount,
                    description=f"Vendor Payable - {grn.grn_number} - {grn.supplier.name}",
                    created_by=1
                )
                db.session.add(payable_entry)
                entries.append(payable_entry)
                
                # GST Input Tax Credit if applicable
                if grn.gst_amount > 0:
                    gst_entry = JournalEntry(
                        entry_number=AccountingService._generate_entry_number('GST'),
                        entry_date=clearing_entry.entry_date,
                        entry_type='gst_input',
                        reference_type='grn',
                        reference_id=grn.id,
                        account_id=accounts['gst_input'],
                        debit_amount=grn.gst_amount,
                        credit_amount=0.0,
                        description=f"GST Input Tax - {grn.grn_number}",
                        created_by=1
                    )
                    db.session.add(gst_entry)
                    entries.append(gst_entry)
            else:
                # Regular Purchase GRN
                # Dr. Inventory
                # Dr. GST Input (if applicable)
                # Cr. Vendor Payable
                
                inventory_entry = JournalEntry(
                    entry_number=AccountingService._generate_entry_number('GRN'),
                    entry_date=grn.invoice_date or datetime.utcnow().date(),
                    entry_type='grn_purchase',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['inventory'],
                    debit_amount=grn.total_value,
                    credit_amount=0.0,
                    description=f"Inventory Purchase - {grn.grn_number}",
                    created_by=1
                )
                db.session.add(inventory_entry)
                entries.append(inventory_entry)
                
                if grn.gst_amount > 0:
                    gst_entry = JournalEntry(
                        entry_number=inventory_entry.entry_number,
                        entry_date=inventory_entry.entry_date,
                        entry_type='grn_purchase',
                        reference_type='grn',
                        reference_id=grn.id,
                        account_id=accounts['gst_input'],
                        debit_amount=grn.gst_amount,
                        credit_amount=0.0,
                        description=f"GST Input Tax - {grn.grn_number}",
                        created_by=1
                    )
                    db.session.add(gst_entry)
                    entries.append(gst_entry)
                
                payable_entry = JournalEntry(
                    entry_number=inventory_entry.entry_number,
                    entry_date=inventory_entry.entry_date,
                    entry_type='grn_purchase',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['vendor_payable'],
                    debit_amount=0.0,
                    credit_amount=grn.final_amount,
                    description=f"Vendor Payable - {grn.grn_number} - {grn.supplier.name}",
                    created_by=1
                )
                db.session.add(payable_entry)
                entries.append(payable_entry)
            
            db.session.flush()  # Ensure entries are created
            
            logger.info(f"Created {len(entries)} accounting entries for GRN {grn.grn_number}")
            
            return {'success': True, 'entries': [entry.to_dict() for entry in entries]}
            
        except Exception as e:
            logger.error(f"Error creating GRN accounting entries: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def create_payment_entries(grn, payment_data):
        """Create accounting entries for payment (Step 3)"""
        try:
            entries = []
            accounts = AccountingService._get_required_accounts()
            
            # Dr. Vendor Payable
            # Cr. Bank/Cash Account
            
            payable_entry = JournalEntry(
                entry_number=AccountingService._generate_entry_number('PAY'),
                entry_date=payment_data['payment_date'],
                entry_type='payment',
                reference_type='grn',
                reference_id=grn.id,
                account_id=accounts['vendor_payable'],
                debit_amount=grn.payment_amount,
                credit_amount=0.0,
                description=f"Payment to {grn.supplier.name} - {grn.grn_number}",
                created_by=payment_data.get('created_by', 1)
            )
            db.session.add(payable_entry)
            entries.append(payable_entry)
            
            # Determine bank/cash account based on payment method
            payment_account = accounts['bank'] if payment_data['payment_method'] in ['bank_transfer', 'cheque'] else accounts['cash']
            
            bank_entry = JournalEntry(
                entry_number=payable_entry.entry_number,
                entry_date=payable_entry.entry_date,
                entry_type='payment',
                reference_type='grn',
                reference_id=grn.id,
                account_id=payment_account,
                debit_amount=0.0,
                credit_amount=grn.payment_amount,
                description=f"Payment via {payment_data['payment_method']} - {grn.grn_number}",
                created_by=payment_data.get('created_by', 1)
            )
            db.session.add(bank_entry)
            entries.append(bank_entry)
            
            # If job work, transfer from GRN Clearing to Job Work Cost
            if grn.receipt_type == 'job_work':
                clearing_transfer = JournalEntry(
                    entry_number=AccountingService._generate_entry_number('TRF'),
                    entry_date=payment_data['payment_date'],
                    entry_type='clearing_transfer',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['job_work_cost'],
                    debit_amount=grn.final_amount,
                    credit_amount=0.0,
                    description=f"Job Work Cost Transfer - {grn.grn_number}",
                    created_by=payment_data.get('created_by', 1)
                )
                db.session.add(clearing_transfer)
                entries.append(clearing_transfer)
                
                clearing_credit = JournalEntry(
                    entry_number=clearing_transfer.entry_number,
                    entry_date=clearing_transfer.entry_date,
                    entry_type='clearing_transfer',
                    reference_type='grn',
                    reference_id=grn.id,
                    account_id=accounts['grn_clearing'],
                    debit_amount=0.0,
                    credit_amount=grn.final_amount,
                    description=f"GRN Clearing Transfer - {grn.grn_number}",
                    created_by=payment_data.get('created_by', 1)
                )
                db.session.add(clearing_credit)
                entries.append(clearing_credit)
            
            db.session.flush()
            
            logger.info(f"Created {len(entries)} payment entries for GRN {grn.grn_number}")
            
            return {'success': True, 'entries': [entry.to_dict() for entry in entries]}
            
        except Exception as e:
            logger.error(f"Error creating payment entries: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def create_job_work_cost_entries(job_work, cost_data):
        """Create job work cost tracking entries"""
        try:
            entries = []
            accounts = AccountingService._get_required_accounts()
            
            # Dr. Work in Progress / Cr. Various Cost Accounts
            
            total_cost = 0
            for cost_type, amount in cost_data.items():
                if amount > 0:
                    cost_account = accounts.get(f'{cost_type}_cost', accounts['job_work_cost'])
                    
                    cost_entry = JournalEntry(
                        entry_number=AccountingService._generate_entry_number('JWC'),
                        entry_date=datetime.utcnow().date(),
                        entry_type='job_work_cost',
                        reference_type='job_work',
                        reference_id=job_work.id,
                        account_id=accounts['wip'],
                        debit_amount=amount,
                        credit_amount=0.0,
                        description=f"Job Work {cost_type.title()} Cost - {job_work.job_number}",
                        created_by=1
                    )
                    db.session.add(cost_entry)
                    entries.append(cost_entry)
                    
                    cost_credit = JournalEntry(
                        entry_number=cost_entry.entry_number,
                        entry_date=cost_entry.entry_date,
                        entry_type='job_work_cost',
                        reference_type='job_work',
                        reference_id=job_work.id,
                        account_id=cost_account,
                        debit_amount=0.0,
                        credit_amount=amount,
                        description=f"{cost_type.title()} Cost - {job_work.job_number}",
                        created_by=1
                    )
                    db.session.add(cost_credit)
                    entries.append(cost_credit)
                    
                    total_cost += amount
            
            db.session.flush()
            
            return {'success': True, 'entries': entries, 'total_cost': total_cost}
            
        except Exception as e:
            logger.error(f"Error creating job work cost entries: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _get_required_accounts():
        """Get or create required accounting heads"""
        accounts = {}
        
        # Account mapping with fallback creation
        account_config = {
            'inventory': ('Current Assets', 'Inventory'),
            'wip': ('Current Assets', 'Work in Progress'),
            'grn_clearing': ('Current Assets', 'GRN Clearing Account'),
            'vendor_payable': ('Current Liabilities', 'Accounts Payable'),
            'job_work_cost': ('Expenses', 'Job Work Expenses'),
            'material_cost': ('Expenses', 'Material Cost'),
            'labor_cost': ('Expenses', 'Labor Cost'),
            'overhead_cost': ('Expenses', 'Manufacturing Overhead'),
            'gst_input': ('Current Assets', 'GST Input Tax Credit'),
            'bank': ('Current Assets', 'Bank Account'),
            'cash': ('Current Assets', 'Cash in Hand')
        }
        
        for account_key, (category, name) in account_config.items():
            try:
                account = Account.query.filter_by(name=name).first()
                if not account:
                    # Create missing account
                    account = Account(
                        name=name,
                        account_type=category,
                        is_active=True,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(account)
                    db.session.flush()
                
                accounts[account_key] = account.id
                
            except Exception as e:
                logger.warning(f"Could not create/find account {name}: {str(e)}")
                # Use fallback account ID
                accounts[account_key] = 1
        
        return accounts
    
    @staticmethod
    def _generate_entry_number(entry_type):
        """Generate unique journal entry number"""
        try:
            settings = CompanySettings.query.first()
            prefix = f"{entry_type}-{datetime.now().year}-"
        except:
            prefix = f"{entry_type}-{datetime.now().year}-"
        
        # Get last entry number
        last_entry = JournalEntry.query.filter(
            JournalEntry.entry_number.like(f'{prefix}%')
        ).order_by(JournalEntry.id.desc()).first()
        
        if last_entry:
            try:
                last_num = int(last_entry.entry_number.split('-')[-1])
                next_num = last_num + 1
            except:
                next_num = 1
        else:
            next_num = 1
        
        return f"{prefix}{str(next_num).zfill(4)}"
    
    @staticmethod
    def get_cost_summary(reference_type, reference_id):
        """Get comprehensive cost summary for job work or production order"""
        try:
            entries = JournalEntry.query.filter_by(
                reference_type=reference_type,
                reference_id=reference_id
            ).all()
            
            cost_summary = {
                'material_cost': 0.0,
                'labor_cost': 0.0,
                'overhead_cost': 0.0,
                'job_work_cost': 0.0,
                'total_cost': 0.0
            }
            
            for entry in entries:
                if entry.account and entry.account.name:
                    account_name = entry.account.name.lower()
                    amount = entry.debit_amount - entry.credit_amount
                    
                    if 'material' in account_name:
                        cost_summary['material_cost'] += amount
                    elif 'labor' in account_name:
                        cost_summary['labor_cost'] += amount
                    elif 'overhead' in account_name:
                        cost_summary['overhead_cost'] += amount
                    elif 'job work' in account_name:
                        cost_summary['job_work_cost'] += amount
                    
                    cost_summary['total_cost'] += amount
            
            return {'success': True, 'cost_summary': cost_summary}
            
        except Exception as e:
            logger.error(f"Error getting cost summary: {str(e)}")
            return {'success': False, 'error': str(e)}