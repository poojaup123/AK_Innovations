from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from models.accounting import Account, AccountGroup
from models.accounting import AdvancedAccountingSettings, CostCenter, LedgerMapping, PaymentMethod, InventoryValuation
from forms_accounting_settings import AccountingSettingsForm, CostCenterForm, LedgerMappingForm, PaymentMethodForm
from decimal import Decimal

accounting_settings_bp = Blueprint('accounting_settings', __name__, url_prefix='/accounting/settings')

@accounting_settings_bp.route('/')
@login_required
def dashboard():
    """Accounting settings dashboard"""
    settings = AdvancedAccountingSettings.get_settings()
    cost_centers = CostCenter.query.filter_by(is_active=True).count()
    ledger_mappings = LedgerMapping.query.filter_by(is_active=True).count()
    payment_methods = PaymentMethod.query.filter_by(is_active=True).count()
    
    return render_template('accounting/settings/dashboard.html',
                         settings=settings,
                         cost_centers_count=cost_centers,
                         ledger_mappings_count=ledger_mappings,
                         payment_methods_count=payment_methods)

@accounting_settings_bp.route('/general', methods=['GET', 'POST'])
@login_required
def general_settings():
    """General accounting settings"""
    settings = AdvancedAccountingSettings.get_settings()
    form = AccountingSettingsForm(obj=settings)
    
    # Populate account choices
    cash_accounts = Account.query.filter_by(is_cash_account=True, is_active=True).all()
    bank_accounts = Account.query.filter_by(is_bank_account=True, is_active=True).all()
    all_accounts = Account.query.filter_by(is_active=True).all()
    
    form.default_cash_account_id.choices = [('', 'Select Cash Account')] + [(a.id, a.name) for a in cash_accounts]
    form.default_bank_account_id.choices = [('', 'Select Bank Account')] + [(a.id, a.name) for a in bank_accounts]
    form.default_purchase_account_id.choices = [('', 'Select Purchase Account')] + [(a.id, a.name) for a in all_accounts]
    form.default_sales_account_id.choices = [('', 'Select Sales Account')] + [(a.id, a.name) for a in all_accounts]
    form.default_inventory_account_id.choices = [('', 'Select Inventory Account')] + [(a.id, a.name) for a in all_accounts]
    form.default_cogs_account_id.choices = [('', 'Select COGS Account')] + [(a.id, a.name) for a in all_accounts]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(settings)
            db.session.commit()
            flash('Accounting settings updated successfully!', 'success')
            return redirect(url_for('accounting_settings.general_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'error')
    
    return render_template('accounting/settings/general.html', form=form, settings=settings)

@accounting_settings_bp.route('/cost-centers')
@login_required
def list_cost_centers():
    """List cost centers"""
    page = request.args.get('page', 1, type=int)
    cost_centers = CostCenter.query.filter_by(is_active=True).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('accounting/settings/cost_centers_list.html', cost_centers=cost_centers)

@accounting_settings_bp.route('/cost-centers/add', methods=['GET', 'POST'])
@login_required
def add_cost_center():
    """Add new cost center"""
    form = CostCenterForm()
    
    # Populate parent cost center choices
    cost_centers = CostCenter.query.filter_by(is_active=True).all()
    form.parent_center_id.choices = [('', 'No Parent')] + [(cc.id, cc.name) for cc in cost_centers]
    
    if form.validate_on_submit():
        try:
            cost_center = CostCenter(
                name=form.name.data,
                code=form.code.data.upper(),
                description=form.description.data,
                parent_center_id=form.parent_center_id.data if form.parent_center_id.data else None,
                monthly_budget=form.monthly_budget.data or 0.0,
                yearly_budget=form.yearly_budget.data or 0.0,
                is_active=form.is_active.data
            )
            
            db.session.add(cost_center)
            db.session.commit()
            
            flash(f'Cost center "{cost_center.name}" created successfully!', 'success')
            return redirect(url_for('accounting_settings.list_cost_centers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating cost center: {str(e)}', 'error')
    
    return render_template('accounting/settings/cost_center_form.html', form=form, title='Add Cost Center')

@accounting_settings_bp.route('/cost-centers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cost_center(id):
    """Edit cost center"""
    cost_center = CostCenter.query.get_or_404(id)
    form = CostCenterForm(obj=cost_center)
    
    # Populate parent cost center choices (excluding self)
    cost_centers = CostCenter.query.filter(CostCenter.is_active == True, CostCenter.id != id).all()
    form.parent_center_id.choices = [('', 'No Parent')] + [(cc.id, cc.name) for cc in cost_centers]
    
    if form.validate_on_submit():
        try:
            form.populate_obj(cost_center)
            db.session.commit()
            
            flash(f'Cost center "{cost_center.name}" updated successfully!', 'success')
            return redirect(url_for('accounting_settings.list_cost_centers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating cost center: {str(e)}', 'error')
    
    return render_template('accounting/settings/cost_center_form.html', 
                         form=form, cost_center=cost_center, title='Edit Cost Center')

@accounting_settings_bp.route('/ledger-mappings')
@login_required
def list_ledger_mappings():
    """List ledger mappings"""
    page = request.args.get('page', 1, type=int)
    mappings = LedgerMapping.query.filter_by(is_active=True).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('accounting/settings/ledger_mappings_list.html', mappings=mappings)

@accounting_settings_bp.route('/ledger-mappings/add', methods=['GET', 'POST'])
@login_required
def add_ledger_mapping():
    """Add new ledger mapping"""
    form = LedgerMappingForm()
    
    # Populate account choices
    accounts = Account.query.filter_by(is_active=True).all()
    cost_centers = CostCenter.query.filter_by(is_active=True).all()
    
    form.receivable_account_id.choices = [('', 'Select Account')] + [(a.id, a.name) for a in accounts]
    form.payable_account_id.choices = [('', 'Select Account')] + [(a.id, a.name) for a in accounts]
    form.expense_account_id.choices = [('', 'Select Account')] + [(a.id, a.name) for a in accounts]
    form.income_account_id.choices = [('', 'Select Account')] + [(a.id, a.name) for a in accounts]
    form.cost_center_id.choices = [('', 'Select Cost Center')] + [(cc.id, cc.name) for cc in cost_centers]
    
    if form.validate_on_submit():
        try:
            mapping = LedgerMapping(
                entity_type=form.entity_type.data,
                entity_id=form.entity_id.data,
                entity_name=form.entity_name.data,
                receivable_account_id=form.receivable_account_id.data if form.receivable_account_id.data else None,
                payable_account_id=form.payable_account_id.data if form.payable_account_id.data else None,
                expense_account_id=form.expense_account_id.data if form.expense_account_id.data else None,
                income_account_id=form.income_account_id.data if form.income_account_id.data else None,
                cost_center_id=form.cost_center_id.data if form.cost_center_id.data else None,
                is_active=form.is_active.data
            )
            
            db.session.add(mapping)
            db.session.commit()
            
            flash('Ledger mapping created successfully!', 'success')
            return redirect(url_for('accounting_settings.list_ledger_mappings'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating ledger mapping: {str(e)}', 'error')
    
    return render_template('accounting/settings/ledger_mapping_form.html', form=form, title='Add Ledger Mapping')

@accounting_settings_bp.route('/payment-methods')
@login_required
def list_payment_methods():
    """List payment methods"""
    page = request.args.get('page', 1, type=int)
    methods = PaymentMethod.query.filter_by(is_active=True).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('accounting/settings/payment_methods_list.html', methods=methods)

@accounting_settings_bp.route('/payment-methods/add', methods=['GET', 'POST'])
@login_required
def add_payment_method():
    """Add new payment method"""
    form = PaymentMethodForm()
    
    # Populate account choices
    accounts = Account.query.filter_by(is_active=True).all()
    form.account_id.choices = [(a.id, a.name) for a in accounts]
    
    if form.validate_on_submit():
        try:
            method = PaymentMethod(
                name=form.name.data,
                code=form.code.data.upper(),
                method_type=form.method_type.data,
                account_id=form.account_id.data,
                requires_reference=form.requires_reference.data,
                auto_reconcile=form.auto_reconcile.data,
                processing_fee_rate=form.processing_fee_rate.data or 0.0,
                is_active=form.is_active.data
            )
            
            db.session.add(method)
            db.session.commit()
            
            flash(f'Payment method "{method.name}" created successfully!', 'success')
            return redirect(url_for('accounting_settings.list_payment_methods'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating payment method: {str(e)}', 'error')
    
    return render_template('accounting/settings/payment_method_form.html', form=form, title='Add Payment Method')

@accounting_settings_bp.route('/inventory-valuation')
@login_required
def inventory_valuation_report():
    """Inventory valuation report with different methods"""
    from models import Item
    
    method = request.args.get('method', 'moving_average')
    page = request.args.get('page', 1, type=int)
    
    # Get latest valuations for each item
    subquery = db.session.query(
        InventoryValuation.item_id,
        db.func.max(InventoryValuation.created_at).label('latest_date')
    ).group_by(InventoryValuation.item_id).subquery()
    
    valuations = db.session.query(InventoryValuation).join(
        subquery,
        db.and_(
            InventoryValuation.item_id == subquery.c.item_id,
            InventoryValuation.created_at == subquery.c.latest_date
        )
    ).paginate(page=page, per_page=50, error_out=False)
    
    # Calculate totals
    total_value = sum(v.total_value for v in valuations.items)
    
    return render_template('accounting/settings/inventory_valuation.html',
                         valuations=valuations,
                         total_value=total_value,
                         current_method=method)

@accounting_settings_bp.route('/api/recalculate-inventory/<method>')
@login_required
def recalculate_inventory_valuation(method):
    """Recalculate inventory valuation using specified method"""
    try:
        from services.inventory_valuation import InventoryValuationService
        
        # This would be implemented in the service
        result = InventoryValuationService.recalculate_all_items(method)
        
        return jsonify({
            'success': True,
            'message': f'Inventory valuation recalculated using {method} method',
            'items_updated': result.get('items_updated', 0)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error recalculating inventory: {str(e)}'
        })