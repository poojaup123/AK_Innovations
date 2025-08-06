from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, SalesOrder
from models.accounting import Account
from services.accounting_automation import AccountingAutomation

so_accounting_bp = Blueprint('so_accounting', __name__)

@so_accounting_bp.route('/advance_receipt/<int:so_id>', methods=['GET', 'POST'])
@login_required
def record_advance_receipt(so_id):
    """Record advance receipt for a sales order"""
    so = SalesOrder.query.get_or_404(so_id)
    
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            receipt_account_id = int(request.form.get('receipt_account_id'))
            notes = request.form.get('notes', '')
            
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('so_accounting.record_advance_receipt', so_id=so_id))
            
            # Create advance receipt voucher
            voucher = AccountingAutomation.create_advance_receipt_voucher(
                so, amount, receipt_account_id, notes
            )
            
            if voucher:
                flash(f'Advance receipt of ₹{amount:,.2f} recorded successfully for SO {so.so_number}', 'success')
                return redirect(url_for('sales.view_sales_order', id=so_id))
            else:
                flash('Failed to record advance receipt', 'danger')
                
        except ValueError:
            flash('Invalid amount entered', 'danger')
        except Exception as e:
            flash(f'Error recording advance receipt: {str(e)}', 'danger')
    
    # Get bank/cash accounts for receipt
    bank_accounts = Account.query.filter(
        Account.account_type.in_(['bank', 'cash'])
    ).all()
    
    return render_template('accounting/advance_receipt_form.html', 
                         so=so, bank_accounts=bank_accounts)

@so_accounting_bp.route('/deliver_so/<int:so_id>', methods=['POST'])
@login_required
def deliver_sales_order(so_id):
    """Mark sales order as delivered and create revenue voucher"""
    so = SalesOrder.query.get_or_404(so_id)
    
    try:
        # Update status to delivered
        so.status = 'delivered'
        
        # Create sales delivery voucher for revenue recognition
        result = AccountingAutomation.create_sales_delivery_voucher(so)
        
        db.session.commit()
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Sales Order {so.so_number} marked as delivered with revenue recognition'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Sales order status updated but accounting integration failed'
            })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error delivering sales order: {str(e)}'
        })

@so_accounting_bp.route('/close_so/<int:so_id>', methods=['POST'])
@login_required
def close_sales_order(so_id):
    """Close sales order accounting entries"""
    so = SalesOrder.query.get_or_404(so_id)
    
    try:
        result = AccountingAutomation.close_sales_order_voucher(so)
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Sales Order {so.so_number} closed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to close sales order accounting entries'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error closing sales order: {str(e)}'
        })