#!/usr/bin/env python3
"""
Test script to verify supplier ledger creation after Chart of Accounts setup
"""

from app import app, db
from models import Supplier
from models.accounting import AccountGroup, Account
from services.authentic_accounting_integration import AuthenticAccountingIntegration

def test_supplier_ledger_creation():
    """Test that suppliers can now create accounting ledgers properly"""
    with app.app_context():
        try:
            print("🧪 Testing Supplier Ledger Creation...")
            
            # Verify account groups exist
            sundry_creditors = AccountGroup.query.filter_by(name='Sundry Creditors').first()
            print(f"📋 Sundry Creditors group found: {sundry_creditors.name if sundry_creditors else 'NOT FOUND'}")
            
            # Check if Test Supplier ABC already exists
            existing_supplier = Supplier.query.filter_by(name='Test Supplier ABC').first()
            if existing_supplier:
                print(f"🔄 Using existing supplier: {existing_supplier.name} (ID: {existing_supplier.id})")
                test_supplier = existing_supplier
            else:
                # Create a test supplier
                test_supplier = Supplier(
                    name='Test Supplier ABC',
                    email='test@supplier.com',
                    phone='1234567890',
                    address='Test Address',
                    partner_type='supplier'
                )
                db.session.add(test_supplier)
                db.session.flush()
                print(f"✅ New supplier created: {test_supplier.name} (ID: {test_supplier.id})")
            
            # Test accounting ledger creation
            party_account = AuthenticAccountingIntegration.get_or_create_party_account(test_supplier, 'supplier')
            
            if party_account:
                print(f"✅ Accounting ledger created successfully!")
                print(f"   Ledger Name: {party_account.name}")
                print(f"   Account Code: {party_account.code}")
                print(f"   Account Group: {party_account.group.name}")
                print(f"   Account Type: {party_account.account_type}")
                
                db.session.commit()
                print("✅ All changes committed successfully!")
                
                return True
            else:
                print("❌ Failed to create accounting ledger")
                db.session.rollback()
                return False
                
        except Exception as e:
            print(f"❌ Error during test: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = test_supplier_ledger_creation()
    if success:
        print("\n🎉 SUCCESS! Supplier accounting integration is working perfectly!")
        print("   • Suppliers can now have automatic ledger creation")
        print("   • No more 'Account group not found for supplier' errors")
    else:
        print("\n💥 Test failed. Check the error messages above.")