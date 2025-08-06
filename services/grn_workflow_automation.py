from app import db
from models.accounting import Account, AccountGroup, Voucher, VoucherType, JournalEntry
from models.grn import GRNWorkflowStatus, VendorInvoice, VendorInvoiceGRNLink, PaymentVoucher, POFulfillmentStatus
from models.accounting import AdvancedAccountingSettings
from services.authentic_accounting_integration import AuthenticAccountingIntegration
from datetime import datetime, date
from decimal import Decimal

class GRNWorkflowService:
    """Service for managing 3-step GRN workflow with clearing accounts"""
    
    @staticmethod
    def setup_clearing_accounts():
        """Validate required clearing accounts exist for GRN workflow"""
        try:
            # Check for existing authentic accounts instead of creating new ones
            grn_clearing = AuthenticAccountingIntegration.get_grn_clearing_account()
            gst_input = AuthenticAccountingIntegration.get_gst_account('input')
            
            if grn_clearing and gst_input:
                return True
            else:
                print("Warning: Required authentic accounts not found. Please ensure GRN Clearing (2150) and GST Input (1180) accounts exist.")
                return False
            
        except Exception as e:
            print(f"Error validating clearing accounts: {e}")
            return False
    
    @staticmethod
    def create_grn_material_receipt_voucher(grn):
        """Step 1: Create voucher when material is received (GRN created)"""
        try:
            # Setup workflow status
            workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first()
            if not workflow_status:
                workflow_status = GRNWorkflowStatus(grn_id=grn.id)
                db.session.add(workflow_status)
                db.session.flush()
            
            # Create voucher type if not exists
            voucher_type = VoucherType.query.filter_by(name='GRN Material Receipt').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='GRN Material Receipt',
                    code='GRNMR',
                    description='Material received against GRN'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Calculate total value
            total_value = sum(
                item.quantity_received * getattr(item, 'rate_per_unit', 0) 
                for item in grn.line_items
            )
            
            # Create voucher
            voucher = Voucher(
                voucher_type_id=voucher_type.id,
                voucher_number=f"GRNMR-{grn.grn_number}",
                transaction_date=grn.received_date or date.today(),
                narration=f"Material received against GRN {grn.grn_number}",
                total_amount=total_value,
                reference_type='grn',
                reference_id=grn.id
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            settings = AdvancedAccountingSettings.get_settings()
            inventory_account = settings.default_inventory_account
            grn_clearing_account = Account.query.filter_by(name='GRN Clearing Account').first()
            
            if not inventory_account or not grn_clearing_account:
                raise Exception("Required accounts not found")
            
            # Create journal entries
            # Dr. Inventory Account
            inventory_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=inventory_account.id,
                entry_type='debit',
                amount=total_value,
                narration=f"Material received - {grn.grn_number}",
                transaction_date=voucher.transaction_date
            )
            db.session.add(inventory_entry)
            
            # Cr. GRN Clearing Account
            clearing_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=grn_clearing_account.id,
                entry_type='credit',
                amount=total_value,
                narration=f"Material received - {grn.grn_number}",
                transaction_date=voucher.transaction_date
            )
            db.session.add(clearing_entry)
            
            # Post voucher
            voucher.post_voucher(1)  # Use admin user ID
            
            # Update workflow status
            workflow_status.material_received = True
            workflow_status.material_received_date = datetime.utcnow()
            workflow_status.grn_voucher_created = True
            workflow_status.grn_clearing_voucher_id = voucher.id
            
            # Update PO fulfillment status
            GRNWorkflowService.update_po_fulfillment_status(grn)
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating GRN material receipt voucher: {e}")
            return None
    
    @staticmethod
    def create_vendor_invoice_voucher(vendor_invoice, grn_links):
        """Step 2: Create voucher when vendor invoice is processed"""
        try:
            # Create voucher type if not exists
            voucher_type = VoucherType.query.filter_by(name='Vendor Invoice').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Vendor Invoice',
                    code='VINV',
                    description='Vendor invoice processing'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_type_id=voucher_type.id,
                voucher_number=f"VINV-{vendor_invoice.invoice_number}",
                transaction_date=vendor_invoice.invoice_date,
                narration=f"Vendor invoice {vendor_invoice.invoice_number}",
                total_amount=vendor_invoice.total_amount,
                reference_number=vendor_invoice.invoice_number,
                party_id=vendor_invoice.vendor_id,
                party_type='supplier',
                created_by=1  # Default admin user
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            grn_clearing_account = Account.query.filter_by(name='GRN Clearing Account').first()
            gst_input_account = Account.query.filter_by(name='GST Input Tax Credit').first()
            
            # Get vendor account (or create if not exists)
            vendor_account = Account.query.filter_by(
                name=f"{vendor_invoice.vendor.name} - Payable"
            ).first()
            
            if not vendor_account:
                # Create vendor payable account
                payables_group = db.session.query(AccountGroup).filter_by(name='Sundry Creditors').first()
                if payables_group:
                    vendor_account = Account(
                        name=f"{vendor_invoice.vendor.name} - Payable",
                        code=f"2200{vendor_invoice.vendor.id:04d}",
                        account_group_id=payables_group.id,
                        account_type='current_liability',
                        is_active=True
                    )
                    db.session.add(vendor_account)
                    db.session.flush()
            
            if not grn_clearing_account or not vendor_account:
                raise Exception("Required accounts not found")
            
            # Create journal entries
            # Dr. GRN Clearing Account (base amount)
            if vendor_invoice.base_amount > 0:
                clearing_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=grn_clearing_account.id,
                    entry_type='debit',
                    amount=vendor_invoice.base_amount,
                    narration=f"Invoice processing - {vendor_invoice.invoice_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='vendor_invoice',
                    reference_id=vendor_invoice.id
                )
                db.session.add(clearing_entry)
            
            # Dr. GST Input Tax (if applicable)
            if vendor_invoice.gst_amount > 0 and gst_input_account:
                gst_entry = JournalEntry(
                    voucher_id=voucher.id,
                    account_id=gst_input_account.id,
                    entry_type='debit',
                    amount=vendor_invoice.gst_amount,
                    narration=f"GST on invoice - {vendor_invoice.invoice_number}",
                    transaction_date=voucher.transaction_date,
                    reference_type='vendor_invoice',
                    reference_id=vendor_invoice.id
                )
                db.session.add(gst_entry)
            
            # Dr. Freight/Other charges (use expense account)
            if vendor_invoice.freight_amount > 0 or vendor_invoice.other_charges > 0:
                freight_total = vendor_invoice.freight_amount + vendor_invoice.other_charges
                freight_account = Account.query.filter_by(name='Freight & Transportation').first()
                if not freight_account:
                    # Create freight account if not exists
                    expenses_group = db.session.query(AccountGroup).filter_by(name='Direct Expenses').first()
                    if expenses_group:
                        freight_account = Account(
                            name='Freight & Transportation',
                            code='5120',
                            account_group_id=expenses_group.id,
                            account_type='direct_expense',
                            is_active=True
                        )
                        db.session.add(freight_account)
                        db.session.flush()
                
                if freight_account and freight_total > 0:
                    freight_entry = JournalEntry(
                        voucher_id=voucher.id,
                        account_id=freight_account.id,
                        entry_type='debit',
                        amount=freight_total,
                        narration=f"Freight & charges - {vendor_invoice.invoice_number}",
                        transaction_date=voucher.transaction_date,
                        reference_type='vendor_invoice',
                        reference_id=vendor_invoice.id
                    )
                    db.session.add(freight_entry)
            
            # Cr. Vendor Account (total amount)
            vendor_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=vendor_account.id,
                entry_type='credit',
                amount=vendor_invoice.total_amount,
                narration=f"Vendor liability - {vendor_invoice.invoice_number}",
                transaction_date=voucher.transaction_date,
                reference_type='vendor_invoice',
                reference_id=vendor_invoice.id
            )
            db.session.add(vendor_entry)
            
            # Post voucher
            voucher.post_voucher(1)  # Use admin user ID
            
            # Update workflow status for linked GRNs
            for link in grn_links:
                workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=link.grn_id).first()
                if workflow_status:
                    workflow_status.invoice_received = True
                    workflow_status.invoice_received_date = datetime.utcnow()
                    workflow_status.invoice_voucher_created = True
                    workflow_status.invoice_voucher_id = voucher.id
            
            # Update invoice status (ensure all amounts are Decimal)
            vendor_invoice.status = 'processed'
            vendor_invoice.paid_amount = Decimal('0.00')  # Ensure paid_amount is Decimal
            vendor_invoice.outstanding_amount = Decimal(str(vendor_invoice.total_amount))
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating vendor invoice voucher: {e}")
            return None
    
    @staticmethod
    def create_payment_voucher(payment_voucher, invoice_allocations):
        """Step 3: Create voucher when payment is made"""
        try:
            # Create voucher type if not exists
            voucher_type = VoucherType.query.filter_by(name='Payment Voucher').first()
            if not voucher_type:
                voucher_type = VoucherType(
                    name='Payment Voucher',
                    code='PAY',
                    description='Payment to vendors'
                )
                db.session.add(voucher_type)
                db.session.flush()
            
            # Create voucher
            voucher = Voucher(
                voucher_type_id=voucher_type.id,
                voucher_number=payment_voucher.voucher_number,
                transaction_date=payment_voucher.payment_date,
                narration=f"Payment to {payment_voucher.vendor.name}",
                total_amount=payment_voucher.payment_amount,
                reference_number=payment_voucher.voucher_number,
                party_id=payment_voucher.vendor_id,
                party_type='supplier',
                created_by=1  # Default admin user
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Get accounts
            vendor_account = Account.query.filter_by(
                name=f"{payment_voucher.vendor.name} - Payable"
            ).first()
            
            if payment_voucher.payment_method == 'cash':
                payment_account = Account.query.filter_by(name='Cash in Hand').first()
            else:
                payment_account = payment_voucher.bank_account
            
            if not vendor_account or not payment_account:
                raise Exception("Required accounts not found")
            
            # Create journal entries
            # Dr. Vendor Account (clear liability)
            vendor_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=vendor_account.id,
                entry_type='debit',
                amount=payment_voucher.payment_amount,
                narration=f"Payment to vendor - {payment_voucher.voucher_number}",
                transaction_date=voucher.transaction_date,
                reference_type='payment_voucher',
                reference_id=payment_voucher.id
            )
            db.session.add(vendor_entry)
            
            # Cr. Bank/Cash Account
            payment_entry = JournalEntry(
                voucher_id=voucher.id,
                account_id=payment_account.id,
                entry_type='credit',
                amount=payment_voucher.payment_amount,
                narration=f"Payment made - {payment_voucher.voucher_number}",
                transaction_date=voucher.transaction_date,
                reference_type='payment_voucher',
                reference_id=payment_voucher.id
            )
            db.session.add(payment_entry)
            
            # Post voucher
            voucher.post_voucher(1)  # Use admin user ID
            
            # Update payment voucher
            payment_voucher.voucher_id = voucher.id
            payment_voucher.status = 'posted'
            
            # Update invoice outstanding amounts (completely avoid += operation)
            for allocation in invoice_allocations:
                invoice = allocation.invoice
                # Calculate new paid amount without += to avoid type conflicts
                current_paid = Decimal(str(invoice.paid_amount or 0))
                new_allocation = Decimal(str(allocation.allocated_amount))
                new_paid_amount = current_paid + new_allocation
                
                # Set the new amount directly
                invoice.paid_amount = new_paid_amount
                invoice.update_outstanding()
                
                # Update workflow status for related GRNs
                for grn_link in invoice.grn_links:
                    workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn_link.grn_id).first()
                    if workflow_status and invoice.outstanding_amount <= 0:
                        workflow_status.payment_made = True
                        workflow_status.payment_made_date = datetime.utcnow()
                        workflow_status.payment_voucher_created = True
                        workflow_status.payment_voucher_id = voucher.id
            
            db.session.commit()
            return voucher
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating payment voucher: {e}")
            return None
    
    @staticmethod
    def update_po_fulfillment_status(grn):
        """Update PO fulfillment status when GRN is created"""
        try:
            po = grn.purchase_order
            if not po:
                return
            
            for grn_item in grn.line_items:
                # Find corresponding PO item
                po_item = None
                for po_line_item in po.items:
                    if po_line_item.item_id == grn_item.item_id:
                        po_item = po_line_item
                        break
                
                if not po_item:
                    continue
                
                # Get or create fulfillment status
                fulfillment_status = POFulfillmentStatus.query.filter_by(
                    po_id=po.id,
                    po_item_id=po_item.id
                ).first()
                
                if not fulfillment_status:
                    fulfillment_status = POFulfillmentStatus(
                        po_id=po.id,
                        po_item_id=po_item.id,
                        ordered_quantity=po_item.quantity,
                        ordered_value=po_item.quantity * po_item.unit_price
                    )
                    db.session.add(fulfillment_status)
                
                # Update received quantities
                fulfillment_status.received_quantity += Decimal(str(grn_item.quantity_received))
                fulfillment_status.received_value += Decimal(str(grn_item.quantity_received * getattr(grn_item, 'rate_per_unit', 0)))
                fulfillment_status.last_grn_date = grn.receipt_date or date.today()
                
                # Update status
                fulfillment_status.update_status()
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating PO fulfillment status: {e}")
    
    @staticmethod
    def get_grn_workflow_summary(grn_id):
        """Get workflow summary for a GRN"""
        try:
            workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn_id).first()
            if not workflow_status:
                return None
            
            summary = {
                'grn_id': grn_id,
                'material_received': workflow_status.material_received,
                'material_received_date': workflow_status.material_received_date,
                'invoice_received': workflow_status.invoice_received,
                'invoice_received_date': workflow_status.invoice_received_date,
                'payment_made': workflow_status.payment_made,
                'payment_made_date': workflow_status.payment_made_date,
                'grn_voucher_id': workflow_status.grn_clearing_voucher_id,
                'invoice_voucher_id': workflow_status.invoice_voucher_id,
                'payment_voucher_id': workflow_status.payment_voucher_id
            }
            
            return summary
            
        except Exception as e:
            print(f"Error getting GRN workflow summary: {e}")
            return None