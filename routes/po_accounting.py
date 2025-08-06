from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, PurchaseOrder
from models.accounting import Account
from services.accounting_automation import AccountingAutomation

po_accounting_bp = Blueprint('po_accounting', __name__)

@po_accounting_bp.route('/advance_payment/<int:po_id>', methods=['GET', 'POST'])
@login_required
def record_advance_payment(po_id):
    """Record advance payment for a purchase order"""
    po = PurchaseOrder.query.get_or_404(po_id)
    
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            payment_account_id = int(request.form.get('payment_account_id'))
            notes = request.form.get('notes', '')
            
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('po_accounting.record_advance_payment', po_id=po_id))
            
            # Create advance payment voucher
            voucher = AccountingAutomation.create_advance_payment_voucher(
                po, amount, payment_account_id, notes
            )
            
            if voucher:
                flash(f'Advance payment of ₹{amount:,.2f} recorded successfully for PO {po.po_number}', 'success')
                return redirect(url_for('purchase.view_purchase_order', id=po_id))
            else:
                flash('Failed to record advance payment', 'danger')
                
        except ValueError:
            flash('Invalid amount entered', 'danger')
        except Exception as e:
            flash(f'Error recording advance payment: {str(e)}', 'danger')
    
    # Get bank/cash accounts for payment
    bank_accounts = Account.query.filter(
        Account.account_type.in_(['bank', 'cash'])
    ).all()
    
    return render_template('accounting/advance_payment_form.html', 
                         po=po, bank_accounts=bank_accounts)

@po_accounting_bp.route('/close_po/<int:po_id>', methods=['POST'])
@login_required  
def close_purchase_order(po_id):
    """Close purchase order accounting entries"""
    po = PurchaseOrder.query.get_or_404(po_id)
    
    try:
        result = AccountingAutomation.close_purchase_order_voucher(po)
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Purchase Order {po.po_number} closed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to close purchase order accounting entries'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error closing purchase order: {str(e)}'
        })