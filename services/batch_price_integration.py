"""
Batch Price Integration Service
Automatically integrates batch price tracking with GRN, Purchase Orders, and manual updates
"""

from app import db
from models.batch import InventoryBatch, BatchPriceHistory
from models import PurchaseOrder, GRN
from datetime import datetime, date
from flask_login import current_user

class BatchPriceIntegrationService:
    """Service to handle automatic batch price updates from various sources"""
    
    @staticmethod
    def update_batch_price_from_grn(grn, batch, user_id=None):
        """
        Update batch price when GRN is created or received
        This creates the initial price history for the batch
        """
        try:
            if not batch or not grn:
                return False
            
            # Get the purchase rate from GRN item
            grn_item = next((item for item in grn.items if item.item_id == batch.item_id), None)
            if not grn_item:
                return False
            
            purchase_rate = grn_item.rate_per_unit or 0
            if purchase_rate <= 0:
                return False
            
            # Create purchase price history
            BatchPriceHistory.create_price_update(
                batch=batch,
                price_type='purchase',
                new_price=purchase_rate,
                source='grn_creation',
                source_ref_id=grn.id,
                source_ref_number=grn.grn_number,
                notes=f'Initial price from GRN receipt - PO: {grn.purchase_order.po_number if grn.purchase_order else "Direct"}',
                user_id=user_id or (current_user.id if current_user.is_authenticated else None)
            )
            
            # If there's freight or other charges, calculate actual cost
            if hasattr(grn, 'freight_charges') and grn.freight_charges:
                # Calculate freight per unit
                total_quantity = sum(item.quantity for item in grn.items)
                freight_per_unit = grn.freight_charges / total_quantity if total_quantity > 0 else 0
                actual_cost = purchase_rate + freight_per_unit
                
                # Create actual cost history
                BatchPriceHistory.create_price_update(
                    batch=batch,
                    price_type='actual',
                    new_price=actual_cost,
                    source='freight_addition',
                    source_ref_id=grn.id,
                    source_ref_number=grn.grn_number,
                    notes=f'Actual cost including freight: ₹{freight_per_unit:.2f} per unit',
                    user_id=user_id or (current_user.id if current_user.is_authenticated else None)
                )
            
            return True
            
        except Exception as e:
            print(f"Error updating batch price from GRN: {str(e)}")
            return False
    
    @staticmethod
    def update_batch_price_from_purchase_order(po, item_id, new_rate, user_id=None):
        """
        Update batch prices when purchase order rates change
        This affects all future batches from this PO
        """
        try:
            # Find all batches sourced from this PO for this item
            batches = InventoryBatch.query.filter(
                InventoryBatch.item_id == item_id,
                InventoryBatch.source_type == 'purchase',
                InventoryBatch.source_ref_id == po.id
            ).all()
            
            for batch in batches:
                # Only update if this is a newer rate (don't overwrite manual updates)
                latest_price = BatchPriceHistory.query.filter_by(
                    batch_id=batch.id,
                    price_type='purchase'
                ).order_by(BatchPriceHistory.effective_date.desc()).first()
                
                if not latest_price or latest_price.source in ['grn_creation', 'po_update']:
                    BatchPriceHistory.create_price_update(
                        batch=batch,
                        price_type='purchase',
                        new_price=new_rate,
                        source='po_update',
                        source_ref_id=po.id,
                        source_ref_number=po.po_number,
                        notes=f'Price updated from PO revision',
                        user_id=user_id or (current_user.id if current_user.is_authenticated else None)
                    )
            
            return True
            
        except Exception as e:
            print(f"Error updating batch price from PO: {str(e)}")
            return False
    
    @staticmethod
    def update_standard_cost_for_item(item_id, new_standard_cost, notes=None, user_id=None):
        """
        Update standard cost for all batches of an item
        Used for cost accounting and valuation purposes
        """
        try:
            # Get all active batches for this item
            batches = InventoryBatch.query.filter(
                InventoryBatch.item_id == item_id,
                InventoryBatch.total_quantity > 0
            ).all()
            
            for batch in batches:
                BatchPriceHistory.create_price_update(
                    batch=batch,
                    price_type='standard',
                    new_price=new_standard_cost,
                    source='standard_cost_update',
                    notes=notes or f'Standard cost revision for item',
                    user_id=user_id or (current_user.id if current_user.is_authenticated else None)
                )
            
            return True
            
        except Exception as e:
            print(f"Error updating standard cost: {str(e)}")
            return False
    
    @staticmethod
    def get_batch_current_prices(batch_id):
        """
        Get current prices for all price types for a batch
        Returns dict with purchase, standard, actual, and market prices
        """
        try:
            current_prices = {}
            
            for price_type in ['purchase', 'standard', 'actual', 'market']:
                latest_record = BatchPriceHistory.query.filter_by(
                    batch_id=batch_id,
                    price_type=price_type
                ).order_by(BatchPriceHistory.effective_date.desc()).first()
                
                current_prices[price_type] = {
                    'price': latest_record.new_price if latest_record else 0,
                    'last_updated': latest_record.effective_date if latest_record else None,
                    'source': latest_record.source if latest_record else None
                }
            
            return current_prices
            
        except Exception as e:
            print(f"Error getting batch current prices: {str(e)}")
            return {}
    
    @staticmethod
    def get_price_comparison_for_item(item_id):
        """
        Get price comparison across all batches of an item
        Useful for procurement and inventory management decisions
        """
        try:
            batches = InventoryBatch.query.filter_by(item_id=item_id).all()
            comparison_data = []
            
            for batch in batches:
                current_prices = BatchPriceIntegrationService.get_batch_current_prices(batch.id)
                
                comparison_data.append({
                    'batch': batch,
                    'prices': current_prices,
                    'total_value': batch.total_quantity * current_prices.get('purchase', {}).get('price', 0)
                })
            
            return comparison_data
            
        except Exception as e:
            print(f"Error getting price comparison: {str(e)}")
            return []
    
    @staticmethod
    def calculate_weighted_average_cost(item_id):
        """
        Calculate weighted average cost across all batches of an item
        Used for inventory valuation and cost analysis
        """
        try:
            batches = InventoryBatch.query.filter(
                InventoryBatch.item_id == item_id,
                InventoryBatch.total_quantity > 0
            ).all()
            
            total_value = 0
            total_quantity = 0
            
            for batch in batches:
                # Use purchase price for valuation
                purchase_price = batch.purchase_rate or 0
                batch_value = batch.total_quantity * purchase_price
                
                total_value += batch_value
                total_quantity += batch.total_quantity
            
            if total_quantity > 0:
                return total_value / total_quantity
            else:
                return 0
                
        except Exception as e:
            print(f"Error calculating weighted average cost: {str(e)}")
            return 0