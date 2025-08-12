"""
Cost Change Notification Service
Phase 2: Smart automation for cost change alerts
"""
from models.cost_settings import CostCalculationSettings, CostChangeNotification
from models import Item
from app import db
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CostNotificationService:
    """Service for managing cost change notifications"""
    
    @staticmethod
    def check_cost_changes() -> Dict:
        """Check for significant cost changes and create notifications"""
        try:
            settings = CostCalculationSettings.get_current_settings()
            
            if not settings.enable_cost_change_notifications:
                return {'success': True, 'message': 'Cost change notifications disabled'}
            
            threshold = settings.cost_change_threshold_percent
            notifications_created = 0
            errors = []
            
            # Get items with recent cost calculations
            recent_threshold = datetime.utcnow() - timedelta(hours=24)
            items_with_changes = Item.query.filter(
                Item.last_cost_calculation >= recent_threshold,
                Item.cost_source == 'bom_calculated'
            ).all()
            
            for item in items_with_changes:
                try:
                    # Check if we already have a notification for this change
                    existing_notification = CostChangeNotification.query.filter_by(
                        item_id=item.id,
                        new_cost=item.bom_calculated_cost
                    ).first()
                    
                    if existing_notification:
                        continue
                    
                    # Get previous cost from last notification or default to unit_price
                    last_notification = CostChangeNotification.query.filter_by(
                        item_id=item.id
                    ).order_by(CostChangeNotification.created_at.desc()).first()
                    
                    old_cost = last_notification.new_cost if last_notification else (item.unit_price or 0)
                    new_cost = item.bom_calculated_cost or 0
                    
                    if old_cost == 0:
                        continue  # Skip if no previous cost
                    
                    # Calculate percentage change
                    change_percent = ((new_cost - old_cost) / old_cost) * 100
                    
                    # Check if change exceeds threshold
                    if abs(change_percent) >= threshold:
                        change_type = 'increase' if change_percent > 0 else 'decrease'
                        
                        # Create notification record
                        notification = CostChangeNotification(
                            item_id=item.id,
                            old_cost=old_cost,
                            new_cost=new_cost,
                            change_percent=change_percent,
                            change_type=change_type,
                            notification_type='dashboard'
                        )
                        
                        db.session.add(notification)
                        notifications_created += 1
                        
                        logger.info(f"Cost change notification created for {item.name}: {change_percent:.1f}%")
                        
                except Exception as e:
                    error_msg = f"Error processing cost change for item {item.id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            db.session.commit()
            
            return {
                'success': True,
                'notifications_created': notifications_created,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error in cost change check: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_pending_notifications() -> List[Dict]:
        """Get all pending cost change notifications"""
        try:
            notifications = CostChangeNotification.query.filter_by(
                acknowledged_at=None
            ).order_by(CostChangeNotification.created_at.desc()).all()
            
            result = []
            for notification in notifications:
                result.append({
                    'id': notification.id,
                    'item_name': notification.item.name,
                    'item_code': notification.item.code,
                    'old_cost': float(notification.old_cost or 0),
                    'new_cost': float(notification.new_cost or 0),
                    'change_percent': notification.change_percent,
                    'change_type': notification.change_type,
                    'created_at': notification.created_at.isoformat(),
                    'severity': 'high' if abs(notification.change_percent) >= 25 else 'medium'
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting pending notifications: {str(e)}")
            return []
    
    @staticmethod
    def acknowledge_notification(notification_id: int, user: str) -> bool:
        """Mark a notification as acknowledged"""
        try:
            notification = CostChangeNotification.query.get(notification_id)
            if notification:
                notification.acknowledged_at = datetime.utcnow()
                notification.acknowledged_by = user
                db.session.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error acknowledging notification {notification_id}: {str(e)}")
            return False
    
    @staticmethod
    def check_outdated_costs() -> Dict:
        """Check for items with outdated cost calculations"""
        try:
            settings = CostCalculationSettings.get_current_settings()
            
            if not settings.enable_automated_cost_validation:
                return {'success': True, 'message': 'Automated validation disabled'}
            
            outdated_threshold = datetime.utcnow() - timedelta(days=settings.outdated_cost_days)
            
            outdated_items = Item.query.filter(
                Item.cost_source == 'bom_calculated',
                (Item.last_cost_calculation < outdated_threshold) | 
                (Item.last_cost_calculation.is_(None))
            ).all()
            
            result = []
            for item in outdated_items:
                days_outdated = None
                if item.last_cost_calculation:
                    days_outdated = (datetime.utcnow() - item.last_cost_calculation).days
                
                result.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'item_code': item.code,
                    'last_calculation': item.last_cost_calculation.isoformat() if item.last_cost_calculation else None,
                    'days_outdated': days_outdated,
                    'current_cost': float(item.bom_calculated_cost or 0)
                })
            
            return {
                'success': True,
                'outdated_items': result,
                'count': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error checking outdated costs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class SmartBomCreationService:
    """Service for intelligent BOM creation workflow"""
    
    @staticmethod
    def validate_bom_for_costing(bom_data: Dict) -> Dict:
        """Validate BOM data for cost calculation readiness"""
        try:
            validation_results = {
                'is_valid': True,
                'warnings': [],
                'errors': [],
                'missing_costs': [],
                'estimated_total': 0
            }
            
            if not bom_data.get('components'):
                validation_results['is_valid'] = False
                validation_results['errors'].append('BOM has no components')
                return validation_results
            
            total_cost = 0
            missing_cost_items = []
            
            for component in bom_data['components']:
                item_id = component.get('item_id')
                quantity = component.get('quantity', 0)
                
                if not item_id:
                    validation_results['errors'].append(f"Component missing item ID")
                    continue
                
                # Get item cost
                item = Item.query.get(item_id)
                if not item:
                    validation_results['errors'].append(f"Component item {item_id} not found")
                    continue
                
                component_cost = item.effective_cost
                if not component_cost:
                    missing_cost_items.append({
                        'item_name': item.name,
                        'item_code': item.code,
                        'quantity': quantity
                    })
                    validation_results['warnings'].append(f"Component {item.name} has no cost data")
                else:
                    total_cost += component_cost * quantity
            
            validation_results['missing_costs'] = missing_cost_items
            validation_results['estimated_total'] = total_cost
            
            if missing_cost_items:
                validation_results['warnings'].append(f"{len(missing_cost_items)} components missing cost data")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating BOM: {str(e)}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': [],
                'missing_costs': [],
                'estimated_total': 0
            }
    
    @staticmethod
    def suggest_missing_components(product_name: str, existing_components: List[Dict]) -> List[Dict]:
        """Suggest missing components based on similar BOMs"""
        try:
            # This is a placeholder for AI-powered component suggestion
            # In a real implementation, this would use ML to analyze similar products
            suggestions = []
            
            # Basic keyword-based suggestions
            common_components = {
                'plate': ['screw', 'washer', 'nut'],
                'assembly': ['bolt', 'spacer', 'gasket'],
                'electronic': ['resistor', 'capacitor', 'connector'],
                'mechanical': ['bearing', 'shaft', 'coupling']
            }
            
            product_lower = product_name.lower()
            existing_names = [comp.get('name', '').lower() for comp in existing_components]
            
            for keyword, suggestions_list in common_components.items():
                if keyword in product_lower:
                    for suggestion in suggestions_list:
                        if suggestion not in existing_names:
                            # Look for items in inventory
                            suggested_items = Item.query.filter(
                                Item.name.ilike(f'%{suggestion}%')
                            ).limit(3).all()
                            
                            for item in suggested_items:
                                suggestions.append({
                                    'item_id': item.id,
                                    'item_name': item.name,
                                    'item_code': item.code,
                                    'suggested_quantity': 1,
                                    'confidence': 0.7,
                                    'reason': f'Common component for {keyword} products'
                                })
            
            return suggestions[:10]  # Limit to top 10 suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting components: {str(e)}")
            return []