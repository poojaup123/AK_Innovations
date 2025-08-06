from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from models import Item, BOM, BOMItem
from models.batch import InventoryBatch
from models.accounting import InventoryValuation, Account
from services.inventory_valuation import InventoryValuationService
from datetime import datetime, date
from sqlalchemy import func
from decimal import Decimal

inventory_valuation_bp = Blueprint('inventory_valuation', __name__, url_prefix='/accounting/inventory-valuation')

@inventory_valuation_bp.route('/dashboard')
@login_required
def dashboard():
    """Inventory valuation dashboard with BOM integration"""
    try:
        # Get all items with stock
        items_with_stock = Item.query.filter(Item.current_stock > 0).all()
        
        valuation_summary = {
            'raw_material': {'count': 0, 'value': 0},
            'wip': {'count': 0, 'value': 0}, 
            'finished_goods': {'count': 0, 'value': 0},
            'semi_finished': {'count': 0, 'value': 0},
            'scrap': {'count': 0, 'value': 0}
        }
        
        detailed_items = []
        
        for item in items_with_stock:
            if item.current_stock and item.current_stock > 0:
                # Calculate BOM-based valuation for manufactured items
                bom_cost = 0
                if item.item_type in ['finished_good', 'semi_finished_good']:
                    active_bom = BOM.query.filter_by(product_id=item.id, is_active=True).first()
                    if active_bom:
                        # Calculate material cost from BOM
                        material_cost = sum(
                            bom_item.quantity_required * (bom_item.item.unit_price or 0)
                            for bom_item in active_bom.items
                        )
                        labor_cost = active_bom.labor_cost_per_unit or 0
                        overhead_cost = active_bom.overhead_cost_per_unit or 0
                        bom_cost = material_cost + labor_cost + overhead_cost
                
                # Use BOM cost if available, otherwise use unit price
                unit_value = bom_cost if bom_cost > 0 else (item.unit_price or 0)
                total_value = float(item.current_stock) * float(unit_value)
                
                # Categorize by item type
                if item.item_type == 'raw_material':
                    category = 'raw_material'
                elif item.item_type == 'work_in_progress':
                    category = 'wip'
                elif item.item_type == 'finished_good':
                    category = 'finished_goods'
                elif item.item_type == 'semi_finished_good':
                    category = 'semi_finished'
                elif item.item_type == 'scrap':
                    category = 'scrap'
                else:
                    category = 'raw_material'  # default
                
                valuation_summary[category]['count'] += 1
                valuation_summary[category]['value'] += total_value
                
                detailed_items.append({
                    'item': item,
                    'unit_value': unit_value,
                    'total_value': total_value,
                    'has_bom': bom_cost > 0,
                    'bom_cost': bom_cost,
                    'category': category
                })
        
        # Calculate total valuation
        total_valuation = sum(cat['value'] for cat in valuation_summary.values())
        
        # Get accounting integration - inventory accounts
        inventory_accounts = Account.query.join(Account.group).filter(
            Account.group.has(name__ilike='%inventory%')
        ).all()
        
        return render_template('accounting/inventory_valuation_dashboard.html',
                             valuation_summary=valuation_summary,
                             detailed_items=detailed_items,
                             total_valuation=total_valuation,
                             inventory_accounts=inventory_accounts)
    
    except Exception as e:
        return render_template('accounting/inventory_valuation_dashboard.html',
                             error=str(e),
                             valuation_summary={},
                             detailed_items=[],
                             total_valuation=0)

@inventory_valuation_bp.route('/bom-cost-analysis/<int:item_id>')
@login_required 
def bom_cost_analysis(item_id):
    """Detailed BOM cost analysis for an item"""
    try:
        item = Item.query.get_or_404(item_id)
        bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
        
        if not bom:
            return jsonify({'error': 'No active BOM found for this item'})
        
        # Calculate detailed cost breakdown
        material_breakdown = []
        total_material_cost = 0
        
        for bom_item in bom.items:
            line_cost = bom_item.quantity_required * (bom_item.item.unit_price or 0)
            total_material_cost += line_cost
            
            material_breakdown.append({
                'item_code': bom_item.item.code,
                'item_name': bom_item.item.name,
                'quantity_required': float(bom_item.quantity_required),
                'unit_price': float(bom_item.item.unit_price or 0),
                'line_cost': float(line_cost),
                'uom': bom_item.item.unit_of_measure
            })
        
        cost_breakdown = {
            'material_cost': float(total_material_cost),
            'labor_cost': float(bom.labor_cost_per_unit or 0),
            'overhead_cost': float(bom.overhead_cost_per_unit or 0),
            'total_cost': float(total_material_cost + (bom.labor_cost_per_unit or 0) + (bom.overhead_cost_per_unit or 0))
        }
        
        return jsonify({
            'item': {
                'code': item.code,
                'name': item.name,
                'current_stock': float(item.current_stock or 0)
            },
            'bom': {
                'code': bom.bom_code,
                'version': bom.version
            },
            'material_breakdown': material_breakdown,
            'cost_breakdown': cost_breakdown
        })
    
    except Exception as e:
        return jsonify({'error': str(e)})

@inventory_valuation_bp.route('/accounting-entries')
@login_required
def accounting_entries():
    """Show how inventory valuation integrates with accounting"""
    try:
        # Get inventory accounts
        inventory_accounts = Account.query.join(Account.group).filter(
            Account.group.has(name__ilike='%inventory%')
        ).all()
        
        # Calculate current balances for each inventory account
        account_balances = []
        for account in inventory_accounts:
            balance = account.calculate_balance()
            account_balances.append({
                'account': account,
                'balance': balance,
                'balance_type': account.balance_type
            })
        
        return render_template('accounting/inventory_accounting_entries.html',
                             account_balances=account_balances)
    
    except Exception as e:
        return render_template('accounting/inventory_accounting_entries.html',
                             error=str(e),
                             account_balances=[])