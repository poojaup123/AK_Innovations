"""
Cost Update Triggers

Automatic cost recalculation when dependencies change
"""

from flask import Blueprint
from flask_login import login_required, current_user
from sqlalchemy import event
from datetime import datetime
import logging

from models import db, Item, BOM, BOMItem, JobWorkRate
from services.cost_calculator import bom_cost_calculator

logger = logging.getLogger(__name__)

cost_triggers_bp = Blueprint('cost_triggers', __name__)


def mark_dependent_costs_outdated(item_id, reason):
    """Mark all items that depend on this item as having outdated costs"""
    try:
        # Find all BOMs that use this item as a component
        dependent_bom_items = BOMItem.query.filter_by(material_id=item_id).all()
        
        affected_items = []
        for bom_item in dependent_bom_items:
            if bom_item.bom and bom_item.bom.product:
                product = bom_item.bom.product
                if product.cost_source == 'bom_calculated':
                    product.cost_calculation_status = 'outdated'
                    affected_items.append(product.id)
        
        if affected_items:
            db.session.commit()
            logger.info(f"Marked {len(affected_items)} items as outdated due to: {reason}")
            
        return affected_items
        
    except Exception as e:
        logger.error(f"Error marking dependent costs outdated: {str(e)}")
        return []


# Event listeners for automatic cost updates
@event.listens_for(Item.unit_price, 'set')
def item_price_changed(target, value, oldvalue, initiator):
    """When item price changes, mark dependent items as outdated"""
    if oldvalue != value and value is not None:
        # Schedule cost update after transaction commits
        @event.listens_for(db.session, 'after_commit', once=True)
        def update_dependent_costs():
            mark_dependent_costs_outdated(target.id, f"Price change for {target.name}")


@event.listens_for(BOMItem.quantity_required, 'set')
def bom_quantity_changed(target, value, oldvalue, initiator):
    """When BOM quantity changes, mark product cost as outdated"""
    if oldvalue != value and value is not None and target.bom:
        product = target.bom.product
        if product and product.cost_source == 'bom_calculated':
            product.cost_calculation_status = 'outdated'


@event.listens_for(BOMItem, 'after_insert')
def bom_item_added(mapper, connection, target):
    """When new BOM item is added, mark product cost as outdated"""
    if target.bom and target.bom.product:
        product = target.bom.product
        if product.cost_source == 'bom_calculated':
            # Use a raw SQL update to avoid session conflicts
            connection.execute(
                "UPDATE items SET cost_calculation_status = 'outdated' WHERE id = %s",
                (product.id,)
            )


@event.listens_for(BOMItem, 'after_delete')
def bom_item_removed(mapper, connection, target):
    """When BOM item is removed, mark product cost as outdated"""
    if target.bom and target.bom.product:
        product = target.bom.product
        if product.cost_source == 'bom_calculated':
            # Use a raw SQL update to avoid session conflicts
            connection.execute(
                "UPDATE items SET cost_calculation_status = 'outdated' WHERE id = %s",
                (product.id,)
            )


@event.listens_for(JobWorkRate.rate_per_unit, 'set')
def job_work_rate_changed(target, value, oldvalue, initiator):
    """When job work rate changes, update affected costs"""
    if oldvalue != value and value is not None:
        # Schedule cost update after transaction commits
        @event.listens_for(db.session, 'after_commit', once=True)
        def update_affected_costs():
            try:
                from services.cost_calculator import update_costs_after_rate_change
                update_costs_after_rate_change(target.id)
            except Exception as e:
                logger.error(f"Error updating costs after rate change: {str(e)}")


# Integration Point Functions
def integrate_with_purchase_orders():
    """Integration with Purchase Order system"""
    
    @cost_triggers_bp.route('/api/cost_for_po_item/<int:item_id>')
    @login_required
    def get_cost_for_po_item(item_id):
        """Get appropriate cost for purchase order item"""
        from flask import jsonify
        
        item = Item.query.get_or_404(item_id)
        
        # For purchased items, use manual cost
        if item.cost_source == 'manual':
            cost = item.unit_price or 0.0
            source = 'manual'
        
        # For manufactured items, use BOM calculated cost
        elif item.cost_source == 'bom_calculated':
            cost = item.bom_calculated_cost or 0.0
            source = 'bom_calculated'
            
            # Recalculate if outdated
            if item.cost_calculation_needed:
                try:
                    from services.cost_calculator import calculate_item_cost
                    result = calculate_item_cost(item_id, force_recalculate=True)
                    if result.get('success', True):
                        cost = result['total_cost_per_unit']
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error recalculating cost: {str(e)}")
        
        # For hybrid items, use override or BOM cost
        else:  # hybrid
            cost = item.manual_cost_override or item.bom_calculated_cost or item.unit_price or 0.0
            source = 'hybrid'
        
        return jsonify({
            'item_id': item_id,
            'item_name': item.name,
            'cost': cost,
            'cost_source': source,
            'last_updated': item.last_cost_calculation.isoformat() if item.last_cost_calculation else None
        })


def integrate_with_production_orders():
    """Integration with Production Order system"""
    
    @cost_triggers_bp.route('/api/freeze_costs_for_production', methods=['POST'])
    @login_required
    def freeze_costs_for_production():
        """Freeze costs for production order"""
        from flask import request, jsonify
        
        try:
            data = request.get_json()
            production_order_id = data.get('production_order_id')
            items = data.get('items', [])
            
            frozen_costs = []
            
            for item_data in items:
                item_id = item_data['item_id']
                quantity = item_data['quantity']
                
                # Create cost freeze record
                from models.cost_history import ProductionOrderCostFreeze
                freeze = ProductionOrderCostFreeze.freeze_cost_for_production(
                    production_order_id=production_order_id,
                    item_id=item_id,
                    quantity=quantity,
                    user_id=current_user.id
                )
                
                if freeze:
                    frozen_costs.append({
                        'item_id': item_id,
                        'frozen_cost': freeze.frozen_cost,
                        'quantity': quantity
                    })
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'frozen_costs': frozen_costs,
                'message': f'Costs frozen for {len(frozen_costs)} items'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


def integrate_with_inventory_valuation():
    """Integration with Inventory Valuation system"""
    
    @cost_triggers_bp.route('/api/inventory_valuation_cost/<int:item_id>')
    @login_required
    def get_inventory_valuation_cost(item_id):
        """Get cost for inventory valuation"""
        from flask import jsonify, request
        
        item = Item.query.get_or_404(item_id)
        valuation_method = request.args.get('method', 'current')
        
        if valuation_method == 'current':
            # Use current effective cost
            cost = item.effective_cost
        
        elif valuation_method == 'frozen':
            # Use frozen cost if available
            cost = item.frozen_cost if item.cost_is_frozen else item.effective_cost
        
        elif valuation_method == 'historical':
            # Use cost from specific date (implement based on requirements)
            cost = item.effective_cost  # Placeholder
        
        else:
            cost = item.effective_cost
        
        return jsonify({
            'item_id': item_id,
            'valuation_cost': cost,
            'method': valuation_method,
            'cost_source': item.cost_source,
            'is_frozen': item.cost_is_frozen
        })


# Register integration functions
integrate_with_purchase_orders()
integrate_with_production_orders() 
integrate_with_inventory_valuation()