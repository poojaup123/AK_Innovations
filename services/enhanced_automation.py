from app import db
from models.accounting import Account, JournalEntry, Voucher, VoucherType
from models.settings import AccountingSettings
from models.accounting import CostCenter, LedgerMapping
from services.inventory_valuation import InventoryValuationService
from datetime import datetime, date
from decimal import Decimal

class EnhancedAccountingAutomation:
    """Enhanced accounting automation with advanced features"""
    
    @staticmethod
    def create_enhanced_grn_entry(grn):
        """Create enhanced GRN entry with inventory valuation"""
        try:
            settings = AccountingSettings.get_settings()
            
            if not settings.auto_grn_voucher:
                return None
            
            # Create inventory valuation entries for each line item
            for line_item in grn.line_items:
                InventoryValuationService.create_valuation_entry(
                    item_id=line_item.item_id,
                    quantity=line_item.received_quantity,
                    transaction_type='grn',
                    transaction_id=grn.id,
                    batch_id=line_item.batch_id if hasattr(line_item, 'batch_id') else None
                )
            
            # Create standard GRN voucher (existing logic)
            from services.accounting_automation import AccountingAutomation
            voucher = AccountingAutomation.create_grn_voucher(grn)
            
            return voucher
            
        except Exception as e:
            print(f"Error creating enhanced GRN entry: {e}")
            return None
    
    @staticmethod
    def create_cost_center_allocation(expense_type, amount, department_id=None, cost_center_id=None):
        """Allocate expenses to cost centers"""
        try:
            if not cost_center_id and department_id:
                # Find cost center mapping for department
                mapping = LedgerMapping.query.filter_by(
                    entity_type='department',
                    entity_id=department_id
                ).first()
                if mapping:
                    cost_center_id = mapping.cost_center_id
            
            if cost_center_id:
                # Create cost center allocation entry
                # This would be tracked in a separate cost allocation table
                pass
            
            return True
            
        except Exception as e:
            print(f"Error creating cost center allocation: {e}")
            return False
    
    @staticmethod
    def create_automatic_inventory_adjustment(item_id, quantity_difference, reason="Stock Adjustment"):
        """Create automatic inventory adjustment with proper accounting"""
        try:
            settings = AccountingSettings.get_settings()
            
            # Create inventory valuation entry
            valuation = InventoryValuationService.create_valuation_entry(
                item_id=item_id,
                quantity=quantity_difference,
                transaction_type='adjustment',
                transaction_id=None
            )
            
            if not valuation:
                return None
            
            # Create accounting voucher
            voucher_type = VoucherType.query.filter_by(name='Inventory Adjustment').first()
            if not voucher_type:
                voucher_type = VoucherType(name='Inventory Adjustment', code='INVADJ')
                db.session.add(voucher_type)
                db.session.flush()
            
            voucher = Voucher(
                voucher_type_id=voucher_type.id,
                voucher_number=f"INVADJ-{datetime.now().strftime('%Y%m%d')}-{Voucher.query.count() + 1:04d}",
                transaction_date=date.today(),
                narration=f"Inventory adjustment - {reason}",
                total_amount=abs(valuation.total_value)
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            inventory_account = settings.default_inventory_account
            adjustment_account = Account.query.filter_by(name='Inventory Adjustment').first()
            
            if inventory_account and adjustment_account:
                if quantity_difference > 0:
                    # Increase in inventory
                    entries = [
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=inventory_account.id,
                            entry_type='debit',
                            amount=valuation.total_value,
                            narration=reason,
                            transaction_date=date.today()
                        ),
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=adjustment_account.id,
                            entry_type='credit',
                            amount=valuation.total_value,
                            narration=reason,
                            transaction_date=date.today()
                        )
                    ]
                else:
                    # Decrease in inventory
                    entries = [
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=adjustment_account.id,
                            entry_type='debit',
                            amount=abs(valuation.total_value),
                            narration=reason,
                            transaction_date=date.today()
                        ),
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=inventory_account.id,
                            entry_type='credit',
                            amount=abs(valuation.total_value),
                            narration=reason,
                            transaction_date=date.today()
                        )
                    ]
                
                for entry in entries:
                    db.session.add(entry)
                
                voucher.post_voucher()
                db.session.commit()
                
                return voucher
            
            return None
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating inventory adjustment: {e}")
            return None
    
    @staticmethod
    def create_department_wise_expense_allocation(total_amount, allocation_rules):
        """Allocate expenses across departments based on rules"""
        try:
            allocations = []
            
            for rule in allocation_rules:
                department_id = rule.get('department_id')
                percentage = rule.get('percentage', 0)
                cost_center_id = rule.get('cost_center_id')
                
                allocation_amount = total_amount * (percentage / 100)
                
                if allocation_amount > 0:
                    allocation = {
                        'department_id': department_id,
                        'cost_center_id': cost_center_id,
                        'amount': allocation_amount,
                        'percentage': percentage
                    }
                    allocations.append(allocation)
            
            return allocations
            
        except Exception as e:
            print(f"Error creating expense allocation: {e}")
            return []
    
    @staticmethod
    def create_advanced_job_work_accounting(job_work):
        """Create advanced job work accounting with scrap tracking"""
        try:
            settings = AccountingSettings.get_settings()
            
            # Create valuation entries for materials sent
            for material in job_work.materials:
                if job_work.type == 'send':
                    # Material going out for job work
                    InventoryValuationService.create_valuation_entry(
                        item_id=material.item_id,
                        quantity=-material.quantity,
                        transaction_type='job_work_send',
                        transaction_id=job_work.id
                    )
                elif job_work.type == 'receive':
                    # Material coming back from job work
                    InventoryValuationService.create_valuation_entry(
                        item_id=material.item_id,
                        quantity=material.quantity,
                        transaction_type='job_work_receive',
                        transaction_id=job_work.id
                    )
            
            # Handle scrap accounting if applicable
            if hasattr(job_work, 'scrap_quantity') and job_work.scrap_quantity > 0:
                EnhancedAccountingAutomation.create_scrap_accounting(job_work)
            
            # Create job work charges voucher
            if job_work.job_work_charges > 0:
                EnhancedAccountingAutomation.create_job_work_charges_voucher(job_work)
            
            return True
            
        except Exception as e:
            print(f"Error creating advanced job work accounting: {e}")
            return False
    
    @staticmethod
    def create_scrap_accounting(job_work):
        """Create accounting entries for scrap"""
        try:
            settings = AccountingSettings.get_settings()
            
            # Create scrap valuation entry
            if hasattr(job_work, 'scrap_item_id') and job_work.scrap_item_id:
                InventoryValuationService.create_valuation_entry(
                    item_id=job_work.scrap_item_id,
                    quantity=job_work.scrap_quantity,
                    transaction_type='scrap_generation',
                    transaction_id=job_work.id
                )
            
            # Create scrap recovery voucher if scrap has value
            if hasattr(job_work, 'scrap_value') and job_work.scrap_value > 0:
                voucher_type = VoucherType.query.filter_by(name='Scrap Recovery').first()
                if not voucher_type:
                    voucher_type = VoucherType(name='Scrap Recovery', code='SCRAP')
                    db.session.add(voucher_type)
                    db.session.flush()
                
                voucher = Voucher(
                    voucher_type_id=voucher_type.id,
                    voucher_number=f"SCRAP-{datetime.now().strftime('%Y%m%d')}-{job_work.id}",
                    transaction_date=date.today(),
                    narration=f"Scrap recovery from job work {job_work.job_number}",
                    total_amount=job_work.scrap_value
                )
                db.session.add(voucher)
                db.session.flush()
                
                # Create journal entries for scrap recovery
                scrap_account = Account.query.filter_by(name='Scrap Recovery').first()
                wip_account = Account.query.filter_by(name='Work in Progress').first()
                
                if scrap_account and wip_account:
                    entries = [
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=scrap_account.id,
                            entry_type='debit',
                            amount=job_work.scrap_value,
                            narration=f"Scrap recovery - {job_work.job_number}",
                            transaction_date=date.today()
                        ),
                        JournalEntry(
                            voucher_id=voucher.id,
                            account_id=wip_account.id,
                            entry_type='credit',
                            amount=job_work.scrap_value,
                            narration=f"Scrap recovery - {job_work.job_number}",
                            transaction_date=date.today()
                        )
                    ]
                    
                    for entry in entries:
                        db.session.add(entry)
                    
                    voucher.post_voucher()
            
            return True
            
        except Exception as e:
            print(f"Error creating scrap accounting: {e}")
            return False
    
    @staticmethod
    def create_job_work_charges_voucher(job_work):
        """Create voucher for job work charges"""
        try:
            voucher_type = VoucherType.query.filter_by(name='Job Work Charges').first()
            if not voucher_type:
                voucher_type = VoucherType(name='Job Work Charges', code='JWCHG')
                db.session.add(voucher_type)
                db.session.flush()
            
            voucher = Voucher(
                voucher_type_id=voucher_type.id,
                voucher_number=f"JWCHG-{datetime.now().strftime('%Y%m%d')}-{job_work.id}",
                transaction_date=date.today(),
                narration=f"Job work charges - {job_work.job_number}",
                total_amount=job_work.job_work_charges
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            job_work_account = Account.query.filter_by(name='Job Work Charges').first()
            vendor_account = Account.query.filter_by(name='Sundry Creditors').first()
            
            if job_work_account and vendor_account:
                entries = [
                    JournalEntry(
                        voucher_id=voucher.id,
                        account_id=job_work_account.id,
                        entry_type='debit',
                        amount=job_work.job_work_charges,
                        narration=f"Job work charges - {job_work.job_number}",
                        transaction_date=date.today()
                    ),
                    JournalEntry(
                        voucher_id=voucher.id,
                        account_id=vendor_account.id,
                        entry_type='credit',
                        amount=job_work.job_work_charges,
                        narration=f"Job work charges - {job_work.job_number}",
                        transaction_date=date.today()
                    )
                ]
                
                for entry in entries:
                    db.session.add(entry)
                
                voucher.post_voucher()
                return voucher
            
            return None
            
        except Exception as e:
            print(f"Error creating job work charges voucher: {e}")
            return None