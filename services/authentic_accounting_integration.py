#!/usr/bin/env python3
"""
Authentic Accounting Integration Service
This service ensures all non-accounting sections work with the existing accounting system
WITHOUT modifying the accounting section itself.
"""

import logging
from app import db
from models.accounting import Account, AccountGroup, Voucher, VoucherType, JournalEntry
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

class AuthenticAccountingIntegration:
    """
    Integration service that respects the authentic accounting system
    and only creates entries, never modifies existing accounts or structure
    """
    
    @staticmethod
    def get_authentic_account(account_code_priority=None, account_name_pattern=None, account_type=None):
        """
        Get an existing authentic account without creating new ones
        Priority: code -> name pattern -> type
        """
        try:
            # First try by specific codes (in order of preference)
            if account_code_priority:
                for code in account_code_priority:
                    account = Account.query.filter_by(code=code).first()
                    if account:
                        return account
            
            # Then try by name pattern
            if account_name_pattern:
                account = Account.query.filter(Account.name.ilike(f'%{account_name_pattern}%')).first()
                if account:
                    return account
            
            # Finally try by account type
            if account_type:
                account = Account.query.filter_by(account_type=account_type).first()
                if account:
                    return account
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting authentic account: {str(e)}")
            return None
    
    @staticmethod
    def get_salary_account():
        """Get the authentic salary account"""
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=['5001', 'WAGES', 'SAL_WAGES'],
            account_name_pattern='salary',
            account_type='expense'
        )
    
    @staticmethod
    def get_cash_account():
        """Get the authentic cash account"""
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=['1001', 'CASH', 'CASH_ACC'],
            account_name_pattern='cash',
            account_type='current_asset'
        )
    
    @staticmethod
    def get_purchase_account():
        """Get the authentic purchase account"""
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=['PURCHASE', 'PUR001', 'PURCHASES'],
            account_name_pattern='purchase',
            account_type='expense'
        )
    
    @staticmethod
    def get_inventory_account(inventory_type='raw_material'):
        """Get authentic inventory accounts"""
        if inventory_type == 'raw_material':
            codes = ['RM_INV', 'RAW_MAT', 'RM']
        elif inventory_type == 'finished_goods':
            codes = ['FG_INV', 'FINISHED', 'FG']
        elif inventory_type == 'wip':
            codes = ['WIP_INV', 'WIP', 'WORK_PROG']
        else:
            codes = ['RM_INV']
            
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=codes,
            account_name_pattern=inventory_type.replace('_', ' '),
            account_type='current_asset'
        )
    
    @staticmethod
    def get_gst_account(gst_type='input'):
        """Get authentic GST accounts"""
        if gst_type == 'input':
            codes = ['1180', 'GST_INPUT', 'INPUT_GST']
        elif gst_type == 'cgst':
            codes = ['CGST_PAY', 'CGST', 'CGST_PAYABLE']
        elif gst_type == 'sgst':
            codes = ['SGST_PAY', 'SGST', 'SGST_PAYABLE']
        elif gst_type == 'igst':
            codes = ['IGST_PAY', 'IGST', 'IGST_PAYABLE']
        else:
            codes = ['1180']
            
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=codes,
            account_name_pattern='gst',
            account_type='current_asset' if gst_type == 'input' else 'current_liability'
        )
    
    @staticmethod
    def get_grn_clearing_account():
        """Get authentic GRN clearing account"""
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=['2150', 'GRN_CLEAR', 'CLEARING'],
            account_name_pattern='clearing',
            account_type='current_liability'
        )
    
    @staticmethod
    def get_overhead_account():
        """Get authentic overhead account"""
        return AuthenticAccountingIntegration.get_authentic_account(
            account_code_priority=['OVERHEAD', 'FACT_OH', 'FACTORY_OH'],
            account_name_pattern='overhead',
            account_type='expense'
        )
    
    @staticmethod
    def get_or_create_party_account(party, account_type='supplier'):
        """
        Get or create party account using existing accounting system logic
        Uses the same pattern as AccountingAutomation but doesn't modify base structure
        """
        try:
            # Check if party account already exists
            party_code = f"{'SUP' if account_type == 'supplier' else 'CUS'}_{party.id}"
            existing_account = Account.query.filter_by(code=party_code).first()
            
            if existing_account:
                return existing_account
            
            # Get appropriate account group
            if account_type == 'supplier':
                group = AccountGroup.query.filter_by(name='Sundry Creditors').first()
                acc_type = 'current_liability'
            else:
                group = AccountGroup.query.filter_by(name='Sundry Debtors').first()
                acc_type = 'current_asset'
            
            if not group:
                logger.error(f"Account group not found for {account_type}")
                return None
            
            # Create party account
            party_account = Account(
                name=party.name,
                code=party_code,
                account_group_id=group.id,
                account_type=acc_type,
                is_active=True
            )
            
            db.session.add(party_account)
            db.session.flush()
            
            return party_account
            
        except Exception as e:
            logger.error(f"Error creating party account: {str(e)}")
            return None
    
    @staticmethod
    def create_simple_voucher(voucher_type_code, reference_number, description, entries, transaction_date=None, created_by=None):
        """
        Create a simple voucher with journal entries
        Uses existing accounting system without modifying it
        """
        try:
            # Get voucher type
            voucher_type = VoucherType.query.filter_by(code=voucher_type_code).first()
            if not voucher_type:
                voucher_type = VoucherType.query.filter(VoucherType.name.ilike(f'%{voucher_type_code}%')).first()
            
            if not voucher_type:
                logger.error(f"Voucher type {voucher_type_code} not found")
                return None
            
            # Calculate total amount
            total_amount = sum(entry.get('amount', 0) for entry in entries)
            
            # Create voucher
            voucher = Voucher(
                voucher_number=f"{voucher_type_code}-{reference_number}",
                voucher_type_id=voucher_type.id,
                transaction_date=transaction_date or datetime.now().date(),
                reference_number=reference_number,
                narration=description,
                total_amount=Decimal(str(total_amount)),
                status='posted',
                created_by=created_by or 1  # Default to admin user ID if not provided
            )
            
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            for entry_data in entries:
                if entry_data.get('account') and entry_data.get('amount', 0) > 0:
                    journal_entry = JournalEntry(
                        voucher_id=voucher.id,
                        account_id=entry_data['account'].id,
                        entry_type=entry_data['type'],  # 'debit' or 'credit'
                        amount=Decimal(str(entry_data['amount'])),
                        narration=entry_data.get('narration', description),
                        transaction_date=voucher.transaction_date
                    )
                    db.session.add(journal_entry)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating voucher: {str(e)}")
            return None
    
    @staticmethod
    def validate_accounting_readiness():
        """
        Validate that the accounting system has all required accounts
        Returns dict with validation results
        """
        validation_results = {
            'valid': True,
            'missing_accounts': [],
            'recommendations': []
        }
        
        # Check for essential accounts
        essential_accounts = [
            ('Cash Account', ['1001', 'CASH']),
            ('Salary Account', ['5001', 'WAGES']),
            ('Purchase Account', ['PURCHASE', 'PUR001']),
            ('Raw Material', ['RM_INV']),
            ('GST Input', ['1180']),
            ('GRN Clearing', ['2150'])
        ]
        
        for account_name, codes in essential_accounts:
            found = False
            for code in codes:
                if Account.query.filter_by(code=code).first():
                    found = True
                    break
            
            if not found:
                validation_results['valid'] = False
                validation_results['missing_accounts'].append(account_name)
                validation_results['recommendations'].append(f"Create {account_name} account with one of these codes: {', '.join(codes)}")
        
        return validation_results