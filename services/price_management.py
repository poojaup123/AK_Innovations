"""
Price Management Service
Handles automatic price updates based on purchase orders and provides price history management
"""
from datetime import date, datetime
from models import db, ItemPriceHistory, Item
from flask_login import current_user


class PriceManagementService:
    """Service for managing item prices with full history tracking"""
    
    @staticmethod
    def update_item_prices_from_po(purchase_order):
        """
        Update item prices when a Purchase Order is created
        Creates price history entries for each item with different rates
        """
        try:
            price_updates = []
            
            for po_item in purchase_order.items:
                item = po_item.item if hasattr(po_item, 'item') else po_item.item_ref
                if not item:
                    continue
                
                current_price = item.unit_price or 0
                new_price = po_item.rate or po_item.unit_price
                
                # Only update if price is different and greater than 0
                if new_price > 0 and abs(new_price - current_price) > 0.01:  # Allow for small rounding differences
                    
                    # Update the item price with full history tracking
                    success = item.update_price(
                        new_price=new_price,
                        price_type='purchase',
                        effective_date=purchase_order.order_date,
                        source='po_creation',
                        source_reference=purchase_order.po_number,
                        notes=f'Price updated from PO {purchase_order.po_number} - Supplier: {purchase_order.supplier.name}',
                        user_id=purchase_order.created_by
                    )
                    
                    if success:
                        price_updates.append({
                            'item': item,
                            'old_price': current_price,
                            'new_price': new_price,
                            'po_number': purchase_order.po_number
                        })
            
            # Commit all price updates
            if price_updates:
                db.session.commit()
            
            return price_updates
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating prices from PO {purchase_order.po_number}: {str(e)}")
            return []
    
    @staticmethod
    def get_price_analysis_for_po(purchase_order):
        """
        Analyze price differences between PO items and current item prices
        Returns analysis without updating prices
        """
        analysis = {
            'total_items': 0,
            'price_increases': 0,
            'price_decreases': 0,
            'price_unchanged': 0,
            'max_increase_percent': 0,
            'max_decrease_percent': 0,
            'items_analysis': []
        }
        
        for po_item in purchase_order.items:
            item = po_item.item if hasattr(po_item, 'item') else po_item.item_ref
            if not item:
                continue
                
            current_price = item.unit_price or 0
            po_price = po_item.rate or po_item.unit_price or 0
            
            analysis['total_items'] += 1
            
            if po_price > current_price:
                analysis['price_increases'] += 1
                if current_price > 0:
                    increase_percent = ((po_price - current_price) / current_price) * 100
                    if increase_percent > analysis['max_increase_percent']:
                        analysis['max_increase_percent'] = increase_percent
            elif po_price < current_price:
                analysis['price_decreases'] += 1
                if current_price > 0:
                    decrease_percent = ((current_price - po_price) / current_price) * 100
                    if decrease_percent > analysis['max_decrease_percent']:
                        analysis['max_decrease_percent'] = decrease_percent
            else:
                analysis['price_unchanged'] += 1
            
            analysis['items_analysis'].append({
                'item_name': item.name,
                'item_code': item.code,
                'current_price': current_price,
                'po_price': po_price,
                'difference': po_price - current_price,
                'difference_percent': ((po_price - current_price) / current_price * 100) if current_price > 0 else 0
            })
        
        return analysis
    
    @staticmethod
    def bulk_update_prices(price_updates, user_id=None):
        """
        Bulk update prices for multiple items
        price_updates: List of dictionaries with item_id, new_price, effective_date, etc.
        """
        try:
            updated_items = []
            
            for update in price_updates:
                item = Item.query.get(update['item_id'])
                if not item:
                    continue
                
                success = item.update_price(
                    new_price=update['new_price'],
                    price_type=update.get('price_type', 'purchase'),
                    effective_date=update.get('effective_date', date.today()),
                    source=update.get('source', 'manual_update'),
                    source_reference=update.get('source_reference'),
                    notes=update.get('notes'),
                    user_id=user_id or (current_user.id if current_user and current_user.is_authenticated else 1)
                )
                
                if success:
                    updated_items.append(item)
            
            db.session.commit()
            return updated_items
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in bulk price update: {str(e)}")
            return []
    
    @staticmethod
    def get_items_with_price_changes(days=30):
        """Get items that had price changes in the last N days"""
        from datetime import timedelta
        
        cutoff_date = date.today() - timedelta(days=days)
        
        recent_changes = db.session.query(ItemPriceHistory).filter(
            ItemPriceHistory.effective_date >= cutoff_date
        ).order_by(ItemPriceHistory.effective_date.desc()).all()
        
        # Group by item
        items_changed = {}
        for change in recent_changes:
            if change.item_id not in items_changed:
                items_changed[change.item_id] = {
                    'item': change.item,
                    'changes': []
                }
            items_changed[change.item_id]['changes'].append(change)
        
        return list(items_changed.values())
    
    @staticmethod
    def get_price_trend_analysis(item_id, months=6):
        """Get comprehensive price trend analysis for an item"""
        from datetime import timedelta
        
        cutoff_date = date.today() - timedelta(days=months * 30)
        
        price_history = ItemPriceHistory.query.filter(
            ItemPriceHistory.item_id == item_id,
            ItemPriceHistory.effective_date >= cutoff_date,
            ItemPriceHistory.price_type == 'purchase'
        ).order_by(ItemPriceHistory.effective_date.asc()).all()
        
        if len(price_history) < 2:
            return {'trend': 'insufficient_data', 'history': price_history}
        
        # Calculate trend metrics
        prices = [entry.price for entry in price_history]
        dates = [entry.effective_date for entry in price_history]
        
        # Simple linear trend calculation
        total_change = prices[-1] - prices[0]
        total_change_percent = (total_change / prices[0] * 100) if prices[0] > 0 else 0
        
        # Volatility (standard deviation of price changes)
        price_changes = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        volatility = sum([abs(change) for change in price_changes]) / len(price_changes) if price_changes else 0
        
        # Trend classification
        if total_change_percent > 10:
            trend = 'strongly_increasing'
        elif total_change_percent > 3:
            trend = 'increasing'
        elif total_change_percent < -10:
            trend = 'strongly_decreasing'
        elif total_change_percent < -3:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'total_change': total_change,
            'total_change_percent': round(total_change_percent, 2),
            'volatility': round(volatility, 2),
            'current_price': prices[-1],
            'highest_price': max(prices),
            'lowest_price': min(prices),
            'price_entries': len(price_history),
            'history': price_history
        }