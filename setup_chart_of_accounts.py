#!/usr/bin/env python3
"""
Chart of Accounts Setup Script
Creates the complete accounting structure required for the factory management system
"""

from app import app, db
from models.accounting import AccountGroup, Account, VoucherType
from services.accounting_automation import AccountingAutomation

def setup_complete_chart_of_accounts():
    """Setup the complete Chart of Accounts structure"""
    with app.app_context():
        try:
            print("🏗️  Setting up Chart of Accounts...")
            
            # Run the existing setup method
            AccountingAutomation.setup_default_accounts()
            
            print("✅ Chart of Accounts setup completed successfully!")
            
            # Verify the critical account groups are created
            sundry_creditors = AccountGroup.query.filter_by(name='Sundry Creditors').first()
            sundry_debtors = AccountGroup.query.filter_by(name='Sundry Debtors').first()
            
            if sundry_creditors:
                print(f"✅ Sundry Creditors group created: {sundry_creditors.name} ({sundry_creditors.code})")
            else:
                print("❌ Sundry Creditors group not found!")
                
            if sundry_debtors:
                print(f"✅ Sundry Debtors group created: {sundry_debtors.name} ({sundry_debtors.code})")
            else:
                print("❌ Sundry Debtors group not found!")
            
            # Display summary
            total_groups = AccountGroup.query.count()
            total_accounts = Account.query.count()
            total_voucher_types = VoucherType.query.count()
            
            print(f"\n📊 Summary:")
            print(f"   Account Groups: {total_groups}")
            print(f"   Accounts: {total_accounts}")
            print(f"   Voucher Types: {total_voucher_types}")
            
            print("\n🎯 Account Groups Structure:")
            groups = AccountGroup.query.all()
            for group in groups:
                parent_info = f" (under {group.parent_group.name})" if group.parent_group else ""
                print(f"   • {group.name} ({group.code}) - {group.group_type}{parent_info}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error setting up Chart of Accounts: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = setup_complete_chart_of_accounts()
    if success:
        print("\n🚀 Your accounting system is now ready!")
        print("   Suppliers and customers can now have automatic ledger creation.")
    else:
        print("\n💥 Setup failed. Please check the error messages above.")