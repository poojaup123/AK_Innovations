"""
Price Cascading Service - Automatic BOM Cost Updates
Handles automatic recalculation of BOM costs when raw material prices change
"""

from models import db, Item, BOM, BOMItem, ItemPriceHistory
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class PriceCascadingService:
    """Service to handle automatic price cascading through BOM hierarchy"""
    
    @classmethod
    def cascade_price_update(cls, item_id, new_price, price_type='purchase', user_id=None, source='price_cascade'):
        """
        Cascade price updates through BOM hierarchy
        
        Args:
            item_id: ID of item whose price changed
            new_price: New price of the item
            price_type: Type of price update
            user_id: User making the change
            source: Source of the price change
        
        Returns:
            dict: Results of cascading operation
        """
        try:
            updated_items = []
            updated_boms = []
            
            # Find all BOMs that use this item as a material
            affected_bom_items = BOMItem.query.filter_by(material_id=item_id).all()
            
            logger.info(f"Found {len(affected_bom_items)} BOM items affected by price change for item {item_id}")
            
            # Track which BOMs need cost recalculation
            boms_to_update = set()
            
            # Update BOM item costs
            for bom_item in affected_bom_items:
                old_unit_cost = bom_item.unit_cost
                bom_item.unit_cost = new_price
                
                logger.info(f"Updated BOM item {bom_item.id} unit cost: {old_unit_cost} -> {new_price}")
                boms_to_update.add(bom_item.bom_id)
            
            # Recalculate BOM costs and update finished goods prices
            for bom_id in boms_to_update:
                bom = BOM.query.get(bom_id)
                if bom:
                    old_cost = bom.total_cost_per_unit
                    
                    # BOM cost will be recalculated automatically via properties
                    new_cost = bom.total_cost_per_unit
                    
                    # Update the finished goods item price
                    finished_item = bom.product
                    if finished_item:
                        old_item_price = finished_item.unit_price
                        
                        # Update item price with BOM cost
                        finished_item.update_price(
                            new_price=new_cost,
                            price_type='standard',
                            effective_date=date.today(),
                            source=f'BOM Cost Update (Material: {Item.query.get(item_id).name})',
                            source_reference=f'BOM-{bom.bom_code}',
                            notes=f'Auto-updated due to material price change',
                            user_id=user_id
                        )
                        
                        updated_items.append({
                            'item_id': finished_item.id,
                            'item_name': finished_item.name,
                            'item_code': finished_item.code,
                            'old_price': old_item_price,
                            'new_price': new_cost,
                            'price_change': new_cost - old_item_price,
                            'price_change_percent': ((new_cost - old_item_price) / old_item_price * 100) if old_item_price > 0 else 0
                        })
                        
                        updated_boms.append({
                            'bom_id': bom.id,
                            'bom_code': bom.bom_code,
                            'product_name': finished_item.name,
                            'old_cost': old_cost,
                            'new_cost': new_cost,
                            'cost_change': new_cost - old_cost,
                            'cost_change_percent': ((new_cost - old_cost) / old_cost * 100) if old_cost > 0 else 0
                        })
                        
                        logger.info(f"Updated item {finished_item.name} price: {old_item_price} -> {new_cost}")
            
            # Commit all changes
            db.session.commit()
            
            # Check for multi-level BOMs (BOMs that use updated items as materials)
            multi_level_updates = cls._handle_multi_level_cascade(updated_items, user_id)
            
            return {
                'success': True,
                'items_updated': len(updated_items),
                'boms_updated': len(updated_boms),
                'updated_items': updated_items,
                'updated_boms': updated_boms,
                'multi_level_updates': multi_level_updates,
                'message': f'Successfully cascaded price update to {len(updated_items)} items and {len(updated_boms)} BOMs'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in price cascading: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to cascade price update: {str(e)}'
            }
    
    @classmethod
    def _handle_multi_level_cascade(cls, updated_items, user_id, max_levels=5):
        """
        Handle multi-level BOM cascading (sub-assemblies within assemblies)
        
        Args:
            updated_items: List of items that were just updated
            user_id: User making the change
            max_levels: Maximum levels to cascade (prevent infinite loops)
        
        Returns:
            list: Multi-level updates performed
        """
        multi_level_updates = []
        
        for level in range(max_levels):
            level_updates = []
            
            # Check if any updated items are used in other BOMs
            for item_info in updated_items:
                item_id = item_info['item_id']
                new_price = item_info['new_price']
                
                # Find BOMs that use this item
                bom_items_using_item = BOMItem.query.filter_by(material_id=item_id).all()
                
                for bom_item in bom_items_using_item:
                    bom = bom_item.bom
                    if bom:
                        old_cost = bom.total_cost_per_unit
                        
                        # Update BOM item cost
                        bom_item.unit_cost = new_price
                        
                        # Recalculate BOM cost
                        new_cost = bom.total_cost_per_unit
                        
                        # Update finished item price
                        finished_item = bom.product
                        if finished_item:
                            old_item_price = finished_item.unit_price
                            
                            finished_item.update_price(
                                new_price=new_cost,
                                price_type='standard',
                                effective_date=date.today(),
                                source=f'Multi-level BOM Update (Level {level + 1})',
                                source_reference=f'BOM-{bom.bom_code}',
                                notes=f'Auto-updated due to sub-assembly price change',
                                user_id=user_id
                            )
                            
                            level_updates.append({
                                'level': level + 1,
                                'item_id': finished_item.id,
                                'item_name': finished_item.name,
                                'bom_code': bom.bom_code,
                                'old_price': old_item_price,
                                'new_price': new_cost,
                                'price_change': new_cost - old_item_price
                            })
            
            if not level_updates:
                break  # No more levels to cascade
            
            multi_level_updates.extend(level_updates)
            updated_items = level_updates  # Use these for next level
        
        if multi_level_updates:
            db.session.commit()
            logger.info(f"Completed multi-level cascade with {len(multi_level_updates)} updates")
        
        return multi_level_updates
    
    @classmethod
    def get_price_impact_analysis(cls, item_id, new_price):
        """
        Analyze the impact of a price change before applying it
        
        Args:
            item_id: ID of item to analyze
            new_price: Proposed new price
        
        Returns:
            dict: Impact analysis results
        """
        try:
            item = Item.query.get(item_id)
            if not item:
                return {'error': 'Item not found'}
            
            current_price = item.unit_price or 0
            price_change = new_price - current_price
            price_change_percent = (price_change / current_price * 100) if current_price > 0 else 0
            
            # Find all BOMs that use this item
            affected_bom_items = BOMItem.query.filter_by(material_id=item_id).all()
            
            impact_analysis = {
                'item_name': item.name,
                'current_price': current_price,
                'new_price': new_price,
                'price_change': price_change,
                'price_change_percent': round(price_change_percent, 2),
                'affected_boms': [],
                'total_impact_value': 0
            }
            
            for bom_item in affected_bom_items:
                bom = bom_item.bom
                if bom:
                    current_bom_cost = bom.total_cost_per_unit
                    
                    # Calculate new BOM cost with updated material price
                    material_cost_change = price_change * bom_item.qty_required
                    new_bom_cost = current_bom_cost + material_cost_change
                    
                    bom_impact = {
                        'bom_code': bom.bom_code,
                        'product_name': bom.product.name if bom.product else 'Unknown',
                        'quantity_required': bom_item.qty_required,
                        'current_bom_cost': current_bom_cost,
                        'new_bom_cost': new_bom_cost,
                        'cost_change': material_cost_change,
                        'cost_change_percent': (material_cost_change / current_bom_cost * 100) if current_bom_cost > 0 else 0
                    }
                    
                    impact_analysis['affected_boms'].append(bom_impact)
                    impact_analysis['total_impact_value'] += abs(material_cost_change)
            
            return impact_analysis
            
        except Exception as e:
            logger.error(f"Error in price impact analysis: {str(e)}")
            return {'error': str(e)}
    
    @classmethod
    def validate_price_change(cls, item_id, new_price, threshold_percent=50):
        """
        Validate if a price change is reasonable
        
        Args:
            item_id: ID of item
            new_price: Proposed new price
            threshold_percent: Warning threshold for large changes
        
        Returns:
            dict: Validation results
        """
        try:
            item = Item.query.get(item_id)
            if not item:
                return {'valid': False, 'error': 'Item not found'}
            
            current_price = item.unit_price or 0
            if current_price <= 0:
                return {'valid': True, 'warning': 'No current price set, validation skipped'}
            
            price_change_percent = abs((new_price - current_price) / current_price * 100)
            
            validation = {
                'valid': True,
                'price_change_percent': round(price_change_percent, 2),
                'warnings': [],
                'requires_approval': False
            }
            
            if price_change_percent > threshold_percent:
                validation['warnings'].append(f'Large price change detected: {round(price_change_percent, 1)}%')
                validation['requires_approval'] = True
            
            if new_price <= 0:
                validation['valid'] = False
                validation['warnings'].append('Price cannot be zero or negative')
            
            return validation
            
        except Exception as e:
            logger.error(f"Error in price validation: {str(e)}")
            return {'valid': False, 'error': str(e)}