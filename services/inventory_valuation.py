from app import db
from models import Item, ItemBatch
from models.accounting import InventoryValuation, AdvancedAccountingSettings
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import func

class InventoryValuationService:
    """Service for advanced inventory valuation methods"""
    
    @staticmethod
    def calculate_fifo_rate(item_id, quantity_needed):
        """Calculate FIFO (First In First Out) rate"""
        try:
            # Get all available batches ordered by creation date
            batches = ItemBatch.query.filter(
                ItemBatch.item_id == item_id,
                ItemBatch.current_quantity > 0
            ).order_by(ItemBatch.created_at).all()
            
            total_cost = 0
            remaining_qty = quantity_needed
            
            for batch in batches:
                if remaining_qty <= 0:
                    break
                
                available_qty = min(batch.current_quantity, remaining_qty)
                batch_cost = available_qty * (batch.unit_cost or 0)
                total_cost += batch_cost
                remaining_qty -= available_qty
            
            if quantity_needed > 0:
                return total_cost / quantity_needed
            return 0
            
        except Exception as e:
            print(f"Error calculating FIFO rate: {e}")
            return 0
    
    @staticmethod
    def calculate_lifo_rate(item_id, quantity_needed):
        """Calculate LIFO (Last In First Out) rate"""
        try:
            # Get all available batches ordered by creation date (newest first)
            batches = ItemBatch.query.filter(
                ItemBatch.item_id == item_id,
                ItemBatch.current_quantity > 0
            ).order_by(ItemBatch.created_at.desc()).all()
            
            total_cost = 0
            remaining_qty = quantity_needed
            
            for batch in batches:
                if remaining_qty <= 0:
                    break
                
                available_qty = min(batch.current_quantity, remaining_qty)
                batch_cost = available_qty * (batch.unit_cost or 0)
                total_cost += batch_cost
                remaining_qty -= available_qty
            
            if quantity_needed > 0:
                return total_cost / quantity_needed
            return 0
            
        except Exception as e:
            print(f"Error calculating LIFO rate: {e}")
            return 0
    
    @staticmethod
    def calculate_moving_average_rate(item_id, new_quantity=0, new_rate=0):
        """Calculate moving average rate"""
        try:
            # Get latest valuation
            latest = InventoryValuation.query.filter_by(
                item_id=item_id
            ).order_by(InventoryValuation.created_at.desc()).first()
            
            if not latest or latest.quantity == 0:
                return new_rate
            
            current_value = latest.quantity * latest.moving_avg_rate
            new_value = new_quantity * new_rate
            total_quantity = latest.quantity + new_quantity
            
            if total_quantity == 0:
                return new_rate
            
            return (current_value + new_value) / total_quantity
            
        except Exception as e:
            print(f"Error calculating moving average rate: {e}")
            return new_rate
    
    @staticmethod
    def get_standard_cost_rate(item_id):
        """Get standard cost rate from item master"""
        try:
            item = Item.query.get(item_id)
            return item.standard_cost if item and item.standard_cost else 0
        except Exception as e:
            print(f"Error getting standard cost rate: {e}")
            return 0
    
    @staticmethod
    def create_valuation_entry(item_id, quantity, transaction_type, transaction_id, batch_id=None):
        """Create inventory valuation entry with all methods"""
        try:
            settings = AdvancedAccountingSettings.get_settings()
            current_method = settings.inventory_valuation_method
            
            # Calculate rates using different methods
            fifo_rate = InventoryValuationService.calculate_fifo_rate(item_id, abs(quantity))
            lifo_rate = InventoryValuationService.calculate_lifo_rate(item_id, abs(quantity))
            
            # For moving average, we need the new rate from the transaction
            moving_avg_rate = 0
            if transaction_type == 'grn':
                # Get GRN line item rate
                from models import GRNLineItem
                grn_item = GRNLineItem.query.filter_by(
                    grn_id=transaction_id,
                    item_id=item_id
                ).first()
                if grn_item:
                    moving_avg_rate = InventoryValuationService.calculate_moving_average_rate(
                        item_id, quantity, grn_item.unit_price
                    )
            else:
                # Use existing moving average
                latest = InventoryValuation.query.filter_by(
                    item_id=item_id
                ).order_by(InventoryValuation.created_at.desc()).first()
                moving_avg_rate = latest.moving_avg_rate if latest else 0
            
            standard_cost_rate = InventoryValuationService.get_standard_cost_rate(item_id)
            
            # Determine current rate based on method
            current_rate = 0
            if current_method == 'fifo':
                current_rate = fifo_rate
            elif current_method == 'lifo':
                current_rate = lifo_rate
            elif current_method == 'moving_average':
                current_rate = moving_avg_rate
            elif current_method == 'standard_cost':
                current_rate = standard_cost_rate
            
            # Calculate new quantity (get current stock and add/subtract)
            current_stock = InventoryValuationService.get_current_stock(item_id)
            new_quantity = current_stock + quantity
            total_value = new_quantity * current_rate
            
            valuation = InventoryValuation(
                item_id=item_id,
                batch_id=batch_id,
                valuation_date=date.today(),
                quantity=new_quantity,
                fifo_rate=fifo_rate,
                lifo_rate=lifo_rate,
                moving_avg_rate=moving_avg_rate,
                standard_cost_rate=standard_cost_rate,
                current_rate=current_rate,
                total_value=total_value,
                transaction_type=transaction_type,
                transaction_id=transaction_id
            )
            
            db.session.add(valuation)
            db.session.commit()
            
            return valuation
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating valuation entry: {e}")
            return None
    
    @staticmethod
    def get_current_stock(item_id):
        """Get current stock quantity for an item"""
        try:
            latest = InventoryValuation.query.filter_by(
                item_id=item_id
            ).order_by(InventoryValuation.created_at.desc()).first()
            
            return latest.quantity if latest else 0
            
        except Exception as e:
            print(f"Error getting current stock: {e}")
            return 0
    
    @staticmethod
    def get_current_value(item_id, method=None):
        """Get current inventory value for an item"""
        try:
            if not method:
                settings = AdvancedAccountingSettings.get_settings()
                method = settings.inventory_valuation_method
            
            latest = InventoryValuation.query.filter_by(
                item_id=item_id
            ).order_by(InventoryValuation.created_at.desc()).first()
            
            if not latest:
                return 0
            
            rate = 0
            if method == 'fifo':
                rate = latest.fifo_rate
            elif method == 'lifo':
                rate = latest.lifo_rate
            elif method == 'moving_average':
                rate = latest.moving_avg_rate
            elif method == 'standard_cost':
                rate = latest.standard_cost_rate
            
            return latest.quantity * rate
            
        except Exception as e:
            print(f"Error getting current value: {e}")
            return 0
    
    @staticmethod
    def recalculate_all_items(method):
        """Recalculate inventory valuation for all items using specified method"""
        try:
            items_updated = 0
            
            # Update settings
            settings = AdvancedAccountingSettings.get_settings()
            settings.inventory_valuation_method = method
            db.session.commit()
            
            # Get all items with current stock
            items_with_stock = db.session.query(
                InventoryValuation.item_id,
                func.sum(InventoryValuation.quantity).label('total_qty')
            ).group_by(InventoryValuation.item_id).having(
                func.sum(InventoryValuation.quantity) > 0
            ).all()
            
            for item_data in items_with_stock:
                item_id = item_data.item_id
                current_qty = item_data.total_qty
                
                if current_qty > 0:
                    # Create new valuation entry with updated method
                    InventoryValuationService.create_valuation_entry(
                        item_id=item_id,
                        quantity=0,  # No quantity change, just revaluation
                        transaction_type='revaluation',
                        transaction_id=None
                    )
                    items_updated += 1
            
            return {'items_updated': items_updated}
            
        except Exception as e:
            db.session.rollback()
            print(f"Error recalculating inventory: {e}")
            return {'items_updated': 0}
    
    @staticmethod
    def get_valuation_summary():
        """Get inventory valuation summary by different methods"""
        try:
            # Get latest valuations for each item
            subquery = db.session.query(
                InventoryValuation.item_id,
                func.max(InventoryValuation.created_at).label('latest_date')
            ).group_by(InventoryValuation.item_id).subquery()
            
            valuations = db.session.query(InventoryValuation).join(
                subquery,
                db.and_(
                    InventoryValuation.item_id == subquery.c.item_id,
                    InventoryValuation.created_at == subquery.c.latest_date
                )
            ).filter(InventoryValuation.quantity > 0).all()
            
            summary = {
                'fifo_total': sum(v.quantity * v.fifo_rate for v in valuations),
                'lifo_total': sum(v.quantity * v.lifo_rate for v in valuations),
                'moving_avg_total': sum(v.quantity * v.moving_avg_rate for v in valuations),
                'standard_cost_total': sum(v.quantity * v.standard_cost_rate for v in valuations),
                'total_items': len(valuations),
                'total_quantity': sum(v.quantity for v in valuations)
            }
            
            return summary
            
        except Exception as e:
            print(f"Error getting valuation summary: {e}")
            return {}