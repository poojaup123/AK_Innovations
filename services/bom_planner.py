"""
BOM-Driven Material Planning Service
Handles automatic material reservation, shortage detection, and purchase suggestions
"""
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class BOMPlanner:
    """BOM-driven manufacturing automation and material planning"""
    
    def __init__(self):
        self.shortage_threshold = 0.1  # 10% safety stock threshold
    
    def analyze_production_requirements(self, item_id, planned_quantity):
        """
        Analyze BOM requirements for a production order
        
        Args:
            item_id: ID of item to be produced
            planned_quantity: Quantity planned for production
            
        Returns:
            Dict with material requirements analysis
        """
        try:
            from models import Item, BOM, BOMItem
            from models.intelligence import MaterialReservation
            from services.uom_converter import UOMConverter
            
            item = Item.query.get(item_id)
            if not item:
                return {'error': 'Item not found'}
            
            # Get BOM for the item
            bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
            if not bom:
                return {
                    'item': item.name,
                    'planned_quantity': planned_quantity,
                    'has_bom': False,
                    'can_produce': True,
                    'message': 'No BOM found - production can proceed without material checks'
                }
            
            # Analyze each BOM component
            requirements = []
            shortages = []
            total_shortage_value = 0
            
            for bom_item in bom.items:
                material = bom_item.item
                required_qty = bom_item.quantity_required * planned_quantity
                
                # Convert BOM quantity to inventory UOM if needed
                if bom_item.unit != material.unit_of_measure:
                    converted_qty = UOMConverter.convert_quantity(
                        required_qty, bom_item.unit, material.unit_of_measure
                    )
                    if converted_qty:
                        required_qty = converted_qty
                
                # Check availability  
                available_qty = material.total_stock or 0
                shortage_qty = max(0, required_qty - available_qty)
                
                requirement = {
                    'material_id': material.id,
                    'material_name': material.name,
                    'material_code': material.item_code,
                    'required_quantity': required_qty,
                    'available_quantity': available_qty,
                    'shortage_quantity': shortage_qty,
                    'unit_of_measure': material.unit_of_measure,
                    'unit_cost': bom_item.unit_cost,
                    'total_cost': bom_item.unit_cost * required_qty,
                    'shortage_cost': bom_item.unit_cost * shortage_qty,
                    'is_sufficient': shortage_qty == 0,
                    'availability_percentage': (available_qty / required_qty * 100) if required_qty > 0 else 100
                }
                
                requirements.append(requirement)
                
                if shortage_qty > 0:
                    shortages.append(requirement)
                    total_shortage_value += requirement['shortage_cost']
            
            # Determine if production can proceed
            can_produce = len(shortages) == 0
            
            return {
                'item': item.name,
                'item_code': item.item_code,
                'planned_quantity': planned_quantity,
                'has_bom': True,
                'bom_id': bom.id,
                'total_materials': len(requirements),
                'materials_sufficient': len(requirements) - len(shortages),
                'materials_short': len(shortages),
                'can_produce': can_produce,
                'requirements': requirements,
                'shortages': shortages,
                'total_material_cost': sum(r['total_cost'] for r in requirements),
                'total_shortage_cost': total_shortage_value,
                'production_feasibility': 'Possible' if can_produce else 'Blocked by material shortages'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing production requirements: {e}")
            return {'error': f'Analysis failed: {str(e)}'}
    
    def generate_purchase_suggestions(self, shortage_analysis):
        """
        Generate purchase order suggestions based on shortage analysis
        
        Args:
            shortage_analysis: Result from analyze_production_requirements
            
        Returns:
            List of purchase suggestions
        """
        try:
            if not shortage_analysis.get('shortages'):
                return []
            
            from models import Supplier, PurchaseOrderItem
            
            suggestions = []
            
            for shortage in shortage_analysis['shortages']:
                material_id = shortage['material_id']
                shortage_qty = shortage['shortage_quantity']
                
                # Add safety stock (10% extra)
                suggested_qty = shortage_qty * (1 + self.shortage_threshold)
                
                # Find preferred supplier (last used or lowest cost)
                last_po_item = PurchaseOrderItem.query.filter_by(
                    item_id=material_id
                ).order_by(PurchaseOrderItem.id.desc()).first()
                
                preferred_supplier = None
                last_rate = shortage['unit_cost']  # BOM cost as fallback
                
                if last_po_item:
                    preferred_supplier = last_po_item.purchase_order.supplier
                    last_rate = last_po_item.rate
                
                suggestion = {
                    'material_id': material_id,
                    'material_name': shortage['material_name'],
                    'material_code': shortage['material_code'],
                    'shortage_quantity': shortage_qty,
                    'suggested_quantity': suggested_qty,
                    'unit_of_measure': shortage['unit_of_measure'],
                    'estimated_rate': last_rate,
                    'estimated_cost': suggested_qty * last_rate,
                    'preferred_supplier_id': preferred_supplier.id if preferred_supplier else None,
                    'preferred_supplier_name': preferred_supplier.name if preferred_supplier else 'No preferred supplier',
                    'priority': 'High' if shortage['availability_percentage'] < 20 else 'Medium',
                    'urgency_days': 3 if shortage['availability_percentage'] < 20 else 7
                }
                
                suggestions.append(suggestion)
            
            # Sort by priority and shortage cost
            suggestions.sort(key=lambda x: (
                x['priority'] == 'High',
                x['estimated_cost']
            ), reverse=True)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating purchase suggestions: {e}")
            return []
    
    def reserve_materials_for_production(self, production_id, requirements):
        """
        Reserve materials for a production order
        
        Args:
            production_id: Production order ID
            requirements: Material requirements from analysis
            
        Returns:
            Dict with reservation results
        """
        try:
            from models import Item, MaterialReservation, db
            
            reservations = []
            failed_reservations = []
            
            for requirement in requirements:
                if requirement['is_sufficient']:
                    material = Item.query.get(requirement['material_id'])
                    reserved_qty = requirement['required_quantity']
                    
                    # Create reservation record
                    reservation = MaterialReservation(
                        production_id=production_id,
                        item_id=material.id,
                        reserved_quantity=reserved_qty,
                        unit_of_measure=material.unit_of_measure,
                        reserved_at=datetime.utcnow(),
                        status='active',
                        notes=f"Auto-reserved for production order #{production_id}"
                    )
                    
                    # Move material to WIP (reserved state)
                    if material.qty_raw >= reserved_qty:
                        material.move_to_wip(reserved_qty, 'cutting')  # Default to cutting process
                        reservations.append({
                            'material': material.name,
                            'quantity': reserved_qty,
                            'status': 'reserved'
                        })
                        
                        db.session.add(reservation)
                    else:
                        failed_reservations.append({
                            'material': material.name,
                            'required': reserved_qty,
                            'available': material.qty_raw,
                            'reason': 'Insufficient raw material stock'
                        })
                else:
                    failed_reservations.append({
                        'material': requirement['material_name'],
                        'required': requirement['required_quantity'],
                        'available': requirement['available_quantity'],
                        'reason': 'Material shortage detected'
                    })
            
            if reservations:
                db.session.commit()
                logger.info(f"Reserved {len(reservations)} materials for production {production_id}")
            
            return {
                'production_id': production_id,
                'successful_reservations': len(reservations),
                'failed_reservations': len(failed_reservations),
                'reservations': reservations,
                'failures': failed_reservations,
                'all_materials_reserved': len(failed_reservations) == 0
            }
            
        except Exception as e:
            logger.error(f"Error reserving materials for production {production_id}: {e}")
            return {'error': f'Reservation failed: {str(e)}'}
    
    def get_material_forecast(self, days_ahead=30):
        """
        Generate material forecast based on planned productions
        
        Args:
            days_ahead: Number of days to forecast
            
        Returns:
            Dict with material forecast data
        """
        try:
            from models import Production, BOM, BOMItem, Item
            
            forecast_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            # Get planned productions
            planned_productions = Production.query.filter(
                Production.status.in_(['planned', 'in_progress']),
                Production.production_date <= forecast_date
            ).all()
            
            material_demand = defaultdict(float)
            
            for production in planned_productions:
                bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
                if bom:
                    for bom_item in bom.items:
                        required_qty = bom_item.quantity_required * production.planned_quantity
                        material_demand[bom_item.item_id] += required_qty
            
            # Generate forecast report
            forecast = []
            for item_id, total_demand in material_demand.items():
                item = Item.query.get(item_id)
                if item:
                    current_stock = item.available_stock
                    projected_shortage = max(0, total_demand - current_stock)
                    
                    forecast.append({
                        'material_id': item_id,
                        'material_name': item.name,
                        'material_code': item.item_code,
                        'current_stock': current_stock,
                        'forecasted_demand': total_demand,
                        'projected_shortage': projected_shortage,
                        'reorder_recommended': projected_shortage > 0,
                        'days_coverage': (current_stock / (total_demand / days_ahead)) if total_demand > 0 else 999,
                        'priority': 'Critical' if projected_shortage > total_demand * 0.5 else 'Normal'
                    })
            
            # Sort by priority and shortage
            forecast.sort(key=lambda x: (x['priority'] == 'Critical', x['projected_shortage']), reverse=True)
            
            return {
                'forecast_period_days': days_ahead,
                'total_materials': len(forecast),
                'materials_with_shortage': sum(1 for f in forecast if f['projected_shortage'] > 0),
                'total_shortage_items': sum(f['projected_shortage'] for f in forecast),
                'forecast': forecast
            }
            
        except Exception as e:
            logger.error(f"Error generating material forecast: {e}")
            return {'error': f'Forecast failed: {str(e)}'}