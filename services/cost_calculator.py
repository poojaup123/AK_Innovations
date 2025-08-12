"""
BOM-Based Cost Calculation Service

This service handles comprehensive cost calculation for items with BOM-calculated cost sources,
integrating material costs, in-house processes, and outsourced job work rates.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BOMCostCalculator:
    """
    Comprehensive BOM-based cost calculator that handles:
    - Multi-level BOM cost calculation
    - In-house vs outsourced process costs
    - Vendor rate management and selection
    - Dynamic cost updates and validation
    """

    def __init__(self):
        self.calculation_cache = {}
        self.circular_dependency_stack = set()

    def calculate_item_bom_cost(self, item_id: int, quantity: float = 1.0, 
                               force_recalculate: bool = False) -> Dict:
        """
        Calculate comprehensive BOM cost for an item
        
        Args:
            item_id: ID of the item to calculate cost for
            quantity: Production quantity (default 1.0)
            force_recalculate: Force recalculation ignoring cache
            
        Returns:
            Dict containing detailed cost breakdown
        """
        from models import Item, BOM
        
        # Get item and validate
        item = Item.query.get(item_id)
        if not item:
            return self._error_result(f"Item with ID {item_id} not found")
        
        # Check if item uses BOM-calculated cost
        if item.cost_source != 'bom_calculated':
            return self._manual_cost_result(item)
        
        # Get active BOM for this item
        bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
        if not bom:
            return self._error_result(f"No active BOM found for item {item.name}")
        
        # Check cache if not forcing recalculation
        cache_key = f"{item_id}_{quantity}_{bom.updated_at}"
        if not force_recalculate and cache_key in self.calculation_cache:
            logger.info(f"Using cached cost calculation for item {item.name}")
            return self.calculation_cache[cache_key]
        
        # Check for circular dependencies
        if item_id in self.circular_dependency_stack:
            return self._error_result(f"Circular dependency detected for item {item.name}")
        
        try:
            # Add to circular dependency check
            self.circular_dependency_stack.add(item_id)
            
            # Calculate comprehensive cost breakdown
            cost_breakdown = self._calculate_bom_cost_breakdown(bom, quantity)
            
            # Update item's calculated cost
            total_cost = cost_breakdown['total_cost_per_unit']
            old_cost = item.bom_calculated_cost or 0.0
            
            # Log cost change if significant
            if abs(total_cost - old_cost) > 0.01:  # Only log if change > 1 paisa
                self._log_cost_change(item, old_cost, total_cost, 'BOM recalculation')
            
            # Validate cost change
            validation_result = self._validate_cost_change(item, old_cost, total_cost)
            if not validation_result['is_valid']:
                cost_breakdown['validation_warnings'] = validation_result['warnings']
            
            item.bom_calculated_cost = total_cost
            item.last_cost_calculation = datetime.utcnow()
            item.cost_calculation_status = 'current'
            
            # Cache result
            self.calculation_cache[cache_key] = cost_breakdown
            
            logger.info(f"Calculated BOM cost for {item.name}: ₹{total_cost:.2f}")
            return cost_breakdown
            
        except Exception as e:
            logger.error(f"Error calculating BOM cost for {item.name}: {str(e)}")
            return self._error_result(f"Cost calculation failed: {str(e)}")
        
        finally:
            # Remove from circular dependency check
            self.circular_dependency_stack.discard(item_id)

    def _calculate_bom_cost_breakdown(self, bom, quantity: float) -> Dict:
        """Calculate detailed cost breakdown for a BOM"""
        breakdown = {
            'bom_code': bom.bom_code,
            'item_name': bom.product.name if bom.product else 'Unknown',
            'quantity': quantity,
            'material_costs': [],
            'process_costs': [],
            'overhead_costs': {},
            'nested_bom_costs': [],
            'total_material_cost': 0.0,
            'total_process_cost': 0.0,
            'total_overhead_cost': 0.0,
            'total_nested_cost': 0.0,
            'total_cost': 0.0,
            'total_cost_per_unit': 0.0,
            'calculation_timestamp': datetime.utcnow(),
            'cost_components': {
                'direct_materials': 0.0,
                'manufactured_components': 0.0,
                'in_house_labor': 0.0,
                'outsourced_processes': 0.0,
                'overhead': 0.0
            }
        }
        
        # Calculate material costs (including nested BOMs)
        material_costs = self._calculate_material_costs(bom, quantity)
        breakdown['material_costs'] = material_costs['details']
        breakdown['total_material_cost'] = material_costs['total']
        breakdown['nested_bom_costs'] = material_costs['nested_costs']
        breakdown['total_nested_cost'] = material_costs['nested_total']
        breakdown['cost_components']['direct_materials'] = material_costs['direct_total']
        breakdown['cost_components']['manufactured_components'] = material_costs['nested_total']
        
        # Calculate process costs (in-house + outsourced + job cards)
        process_costs = self._calculate_process_costs(bom, quantity)
        breakdown['process_costs'] = process_costs['details']
        breakdown['total_process_cost'] = process_costs['total']
        breakdown['cost_components']['in_house_labor'] = process_costs['in_house_total']
        breakdown['cost_components']['outsourced_processes'] = process_costs['outsourced_total']
        
        # Calculate outsourced job card costs
        job_card_costs = self._calculate_outsourced_job_card_costs(item_id, quantity)
        breakdown['outsourced_job_card_costs'] = job_card_costs['details']
        breakdown['total_job_card_cost'] = job_card_costs['total']
        breakdown['cost_components']['outsourced_job_cards'] = job_card_costs['total']
        
        # Calculate overhead costs
        overhead_costs = self._calculate_overhead_costs(bom, quantity)
        breakdown['overhead_costs'] = overhead_costs
        breakdown['total_overhead_cost'] = sum(overhead_costs.values())
        breakdown['cost_components']['overhead'] = breakdown['total_overhead_cost']
        
        # Calculate totals including job card costs
        breakdown['total_cost'] = (
            breakdown['total_material_cost'] + 
            breakdown['total_process_cost'] + 
            breakdown['total_overhead_cost'] +
            breakdown.get('total_job_card_cost', 0.0)
        )
        breakdown['total_cost_per_unit'] = (
            breakdown['total_cost'] / quantity if quantity > 0 else breakdown['total_cost']
        )
        
        return breakdown

    def _calculate_outsourced_job_card_costs(self, item_id: int, quantity: float) -> Dict:
        """
        Calculate costs for outsourced job cards related to this item
        
        Args:
            item_id: ID of the item being produced
            quantity: Production quantity
            
        Returns:
            Dict containing outsourced job card cost breakdown
        """
        from models import JobCard, Item
        from sqlalchemy import and_
        
        job_card_costs = {
            'details': [],
            'total': 0.0,
            'vendor_breakdown': {},
            'process_breakdown': {}
        }
        
        # Get outsourced job cards for this item (active or recent)
        outsourced_job_cards = JobCard.query.filter(
            and_(
                JobCard.item_id == item_id,
                JobCard.job_type == 'outsourced',
                JobCard.status.in_(['planned', 'in_progress', 'completed', 'received'])
            )
        ).all()
        
        for job_card in outsourced_job_cards:
            # Get vendor information
            vendor = job_card.assigned_vendor if hasattr(job_card, 'assigned_vendor') else None
            vendor_name = vendor.name if vendor else 'Unknown Vendor'
            vendor_id = vendor.id if vendor else None
            
            # Calculate job card costs based on different cost components
            estimated_cost = job_card.estimated_cost or 0.0
            actual_cost = job_card.actual_cost or estimated_cost
            material_cost = job_card.material_cost or 0.0
            labor_cost = job_card.labor_cost or 0.0
            overhead_cost = job_card.overhead_cost or 0.0
            transportation_cost = getattr(job_card, 'transportation_cost', 0.0)
            handling_charges = getattr(job_card, 'handling_charges', 0.0)
            
            # Calculate per unit cost
            job_card_quantity = job_card.planned_quantity or job_card.quantity_planned or 1.0
            unit_cost = actual_cost / job_card_quantity if job_card_quantity > 0 else actual_cost
            
            # Scale to required quantity
            scaled_cost = unit_cost * quantity
            
            job_card_detail = {
                'job_card_number': job_card.job_card_number,
                'process_name': job_card.process_name,
                'vendor_name': vendor_name,
                'vendor_id': vendor_id,
                'job_card_quantity': job_card_quantity,
                'unit_cost': unit_cost,
                'scaled_cost': scaled_cost,
                'cost_breakdown': {
                    'estimated_cost': estimated_cost,
                    'actual_cost': actual_cost,
                    'material_cost': material_cost,
                    'labor_cost': labor_cost,
                    'overhead_cost': overhead_cost,
                    'transportation_cost': transportation_cost,
                    'handling_charges': handling_charges
                },
                'status': job_card.status,
                'completion_percentage': getattr(job_card, 'progress_percentage', 0.0)
            }
            
            job_card_costs['details'].append(job_card_detail)
            job_card_costs['total'] += scaled_cost
            
            # Vendor breakdown
            if vendor_name not in job_card_costs['vendor_breakdown']:
                job_card_costs['vendor_breakdown'][vendor_name] = {
                    'total_cost': 0.0,
                    'job_cards': 0,
                    'processes': []
                }
            job_card_costs['vendor_breakdown'][vendor_name]['total_cost'] += scaled_cost
            job_card_costs['vendor_breakdown'][vendor_name]['job_cards'] += 1
            job_card_costs['vendor_breakdown'][vendor_name]['processes'].append(job_card.process_name)
            
            # Process breakdown
            process_name = job_card.process_name
            if process_name not in job_card_costs['process_breakdown']:
                job_card_costs['process_breakdown'][process_name] = {
                    'total_cost': 0.0,
                    'vendors': []
                }
            job_card_costs['process_breakdown'][process_name]['total_cost'] += scaled_cost
            if vendor_name not in job_card_costs['process_breakdown'][process_name]['vendors']:
                job_card_costs['process_breakdown'][process_name]['vendors'].append(vendor_name)
        
        return job_card_costs

    def get_outsourced_job_card_vendor_rates(self, process_name: str, quantity: float = 1.0) -> List[Dict]:
        """
        Get vendor rates for outsourced job card processes
        
        Args:
            process_name: Name of the process
            quantity: Quantity for rate calculation
            
        Returns:
            List of vendor rates with cost breakdown
        """
        from models import db
        
        # Query outsourced job card rates
        rates_query = """
        SELECT 
            ojr.vendor_id,
            s.name as vendor_name,
            s.contact_person,
            s.phone,
            ojr.rate_per_unit,
            ojr.setup_cost,
            ojr.transportation_cost,
            ojr.minimum_quantity,
            ojr.lead_time_days,
            ojr.quality_rating,
            ojr.is_preferred,
            ojr.effective_from,
            ojr.effective_to
        FROM outsourced_job_card_rates ojr
        JOIN suppliers s ON ojr.vendor_id = s.id
        WHERE ojr.process_name = %s 
        AND ojr.is_active = TRUE
        AND (ojr.effective_to IS NULL OR ojr.effective_to >= CURRENT_DATE)
        ORDER BY ojr.is_preferred DESC, ojr.rate_per_unit ASC
        """
        
        result = db.session.execute(rates_query, (process_name,))
        vendor_rates = []
        
        for row in result:
            # Calculate total cost for this vendor
            unit_rate = float(row.rate_per_unit or 0.0)
            setup_cost = float(row.setup_cost or 0.0)
            transport_cost = float(row.transportation_cost or 0.0)
            
            # Total cost = (unit rate * quantity) + setup cost + transport cost
            total_cost = (unit_rate * quantity) + setup_cost + transport_cost
            cost_per_unit = total_cost / quantity if quantity > 0 else total_cost
            
            vendor_rates.append({
                'vendor_id': row.vendor_id,
                'vendor_name': row.vendor_name,
                'contact_person': row.contact_person,
                'phone': row.phone,
                'rate_per_unit': unit_rate,
                'setup_cost': setup_cost,
                'transportation_cost': transport_cost,
                'total_cost': total_cost,
                'cost_per_unit': cost_per_unit,
                'minimum_quantity': float(row.minimum_quantity or 1.0),
                'lead_time_days': row.lead_time_days,
                'quality_rating': row.quality_rating,
                'is_preferred': row.is_preferred,
                'effective_from': row.effective_from,
                'effective_to': row.effective_to
            })
        
        return vendor_rates

    def _calculate_material_costs(self, bom, quantity: float) -> Dict:
        """Calculate material costs including nested BOM components"""
        from models import Item, BOM
        
        material_costs = {
            'details': [],
            'nested_costs': [],
            'total': 0.0,
            'direct_total': 0.0,
            'nested_total': 0.0
        }
        
        for bom_item in bom.items:
            material = bom_item.material or bom_item.item
            if not material:
                continue
                
            required_qty = (bom_item.qty_required or bom_item.quantity_required or 0) * quantity
            
            # Check if this material has its own BOM (nested component)
            material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
            
            if material_bom and material.cost_source == 'bom_calculated':
                # Recursive calculation for nested BOM
                nested_cost = self.calculate_item_bom_cost(material.id, required_qty)
                
                if nested_cost.get('success', True):
                    cost_per_unit = nested_cost['total_cost_per_unit']
                    total_cost = cost_per_unit * required_qty
                    
                    material_costs['nested_costs'].append({
                        'material_name': material.name,
                        'material_code': material.code,
                        'bom_code': material_bom.bom_code,
                        'quantity_required': required_qty,
                        'cost_per_unit': cost_per_unit,
                        'total_cost': total_cost,
                        'nested_breakdown': nested_cost
                    })
                    
                    material_costs['nested_total'] += total_cost
                else:
                    # Fallback to manual cost if BOM calculation fails
                    unit_cost = material.unit_price or 0.0
                    total_cost = unit_cost * required_qty
                    material_costs['direct_total'] += total_cost
                    
            else:
                # Direct material cost (purchased or manual cost)
                unit_cost = self._get_material_unit_cost(material, bom_item)
                total_cost = unit_cost * required_qty
                
                material_costs['details'].append({
                    'material_name': material.name,
                    'material_code': material.code,
                    'quantity_required': required_qty,
                    'unit_cost': unit_cost,
                    'total_cost': total_cost,
                    'cost_source': 'purchased' if material.cost_source == 'manual' else material.cost_source,
                    'supplier': getattr(bom_item.default_supplier, 'name', 'N/A') if bom_item.default_supplier else 'N/A'
                })
                
                material_costs['direct_total'] += total_cost
        
        material_costs['total'] = material_costs['direct_total'] + material_costs['nested_total']
        return material_costs

    def _calculate_process_costs(self, bom, quantity: float) -> Dict:
        """Calculate process costs for both in-house and outsourced processes"""
        process_costs = {
            'details': [],
            'total': 0.0,
            'in_house_total': 0.0,
            'outsourced_total': 0.0
        }
        
        for process in bom.processes:
            if process.is_outsourced:
                # Outsourced process cost
                cost_per_unit = process.get_outsourced_cost_per_unit()
                cost_type = 'outsourced'
                vendor_info = {
                    'vendor_name': process.vendor.name if process.vendor else 'TBD',
                    'vendor_id': process.vendor_id,
                    'rate_source': 'job_work_rates'
                }
                process_costs['outsourced_total'] += cost_per_unit * quantity
                
            else:
                # In-house process cost
                cost_per_unit = process.total_in_house_cost_per_unit
                cost_type = 'in_house'
                vendor_info = {
                    'department': process.department.name if process.department else 'N/A',
                    'department_id': process.department_id
                }
                process_costs['in_house_total'] += cost_per_unit * quantity
            
            total_process_cost = cost_per_unit * quantity
            
            process_costs['details'].append({
                'process_name': process.process_name,
                'process_code': process.process_code,
                'step_number': process.step_number,
                'cost_type': cost_type,
                'cost_per_unit': cost_per_unit,
                'quantity': quantity,
                'total_cost': total_process_cost,
                'time_minutes': process.total_time_minutes,
                'labor_rate': process.labor_rate_per_hour,
                'machine_cost': process.machine_cost_per_hour,
                'setup_cost': process.setup_cost,
                'vendor_info': vendor_info
            })
        
        process_costs['total'] = process_costs['in_house_total'] + process_costs['outsourced_total']
        return process_costs

    def _calculate_overhead_costs(self, bom, quantity: float) -> Dict:
        """Calculate overhead costs (factory overhead, utilities, etc.)"""
        overhead_costs = {}
        
        # Calculate freight/transportation costs
        if bom.freight_cost_per_unit:
            freight_cost = bom.calculated_freight_cost_per_unit * quantity
            overhead_costs['freight'] = freight_cost
        
        # Calculate other overhead costs based on BOM configuration
        if bom.overhead_percentage and bom.overhead_percentage > 0:
            # Calculate overhead as percentage of material + labor costs
            base_cost = bom.total_material_cost + bom.total_process_cost_per_unit
            overhead_amount = (base_cost * bom.overhead_percentage / 100) * quantity
            overhead_costs['factory_overhead'] = overhead_amount
        
        # Add any manual overhead costs
        if bom.overhead_cost_per_unit:
            overhead_costs['manual_overhead'] = bom.overhead_cost_per_unit * quantity
        
        return overhead_costs

    def _get_material_unit_cost(self, material, bom_item) -> float:
        """Get the appropriate unit cost for a material"""
        # Priority order: BOM item unit cost -> Item unit price -> 0
        if bom_item.unit_cost and bom_item.unit_cost > 0:
            return bom_item.unit_cost
        elif material.unit_price and material.unit_price > 0:
            return material.unit_price
        else:
            return 0.0

    def get_vendor_cost_comparison(self, item_id: int, process_type: str, quantity: float = 1.0) -> List[Dict]:
        """Get cost comparison across multiple vendors for a process"""
        from models import JobWorkRate
        
        rates = JobWorkRate.query.filter(
            JobWorkRate.item_id == item_id,
            JobWorkRate.process_type == process_type,
            JobWorkRate.is_active == True,
            JobWorkRate.minimum_quantity <= quantity
        ).all()
        
        vendor_comparison = []
        
        for rate in rates:
            if rate.is_current:
                vendor_comparison.append({
                    'vendor_name': rate.supplier.name if rate.supplier else rate.vendor_name,
                    'vendor_id': rate.supplier_id,
                    'rate_per_unit': rate.rate_per_unit,
                    'transportation_cost': rate.transportation_cost,
                    'total_cost_per_unit': rate.total_cost_per_unit,
                    'setup_cost': rate.setup_cost,
                    'lead_time_days': rate.lead_time_days,
                    'quality_rating': rate.quality_rating,
                    'is_primary': rate.is_primary_vendor,
                    'effective_from': rate.effective_from,
                    'effective_until': rate.effective_until
                })
        
        # Sort by total cost (primary) and quality rating (secondary)
        vendor_comparison.sort(key=lambda x: (x['total_cost_per_unit'], -x['quality_rating']))
        
        return vendor_comparison

    def update_costs_for_rate_change(self, rate_id: int) -> List[Dict]:
        """Update all affected item costs when a job work rate changes"""
        from models import JobWorkRate, Item, BOM
        
        rate = JobWorkRate.query.get(rate_id)
        if not rate:
            return []
        
        # Find all items that might be affected by this rate change
        affected_items = []
        
        # Direct items using this rate
        item = Item.query.get(rate.item_id)
        if item and item.cost_source == 'bom_calculated':
            affected_items.append(item)
        
        # Items with BOMs that have processes matching this rate's process type
        boms_with_process = BOM.query.join(BOM.processes).filter(
            BOM.processes.any(process_name=rate.process_type, is_outsourced=True),
            BOM.is_active == True
        ).all()
        
        for bom in boms_with_process:
            if bom.product and bom.product.cost_source == 'bom_calculated':
                if bom.product not in affected_items:
                    affected_items.append(bom.product)
        
        # Recalculate costs for all affected items
        update_results = []
        for item in affected_items:
            try:
                old_cost = item.bom_calculated_cost or 0.0
                result = self.calculate_item_bom_cost(item.id, force_recalculate=True)
                
                if result.get('success', True):
                    new_cost = result['total_cost_per_unit']
                    cost_change = new_cost - old_cost
                    cost_change_percent = ((cost_change / old_cost) * 100) if old_cost > 0 else 0
                    
                    update_results.append({
                        'item_id': item.id,
                        'item_name': item.name,
                        'old_cost': old_cost,
                        'new_cost': new_cost,
                        'cost_change': cost_change,
                        'cost_change_percent': cost_change_percent,
                        'update_timestamp': datetime.utcnow()
                    })
                    
            except Exception as e:
                logger.error(f"Error updating cost for item {item.name}: {str(e)}")
                update_results.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'error': str(e),
                    'update_timestamp': datetime.utcnow()
                })
        
        return update_results

    def get_cost_variance_analysis(self, item_id: int, actual_costs: Dict) -> Dict:
        """Compare estimated BOM costs with actual production costs"""
        estimated_costs = self.calculate_item_bom_cost(item_id)
        
        if not estimated_costs.get('success', True):
            return {'error': 'Could not calculate estimated costs'}
        
        variance_analysis = {
            'item_id': item_id,
            'analysis_date': datetime.utcnow(),
            'estimated_costs': estimated_costs,
            'actual_costs': actual_costs,
            'variances': {}
        }
        
        # Calculate variances for each cost component
        components = ['direct_materials', 'manufactured_components', 'in_house_labor', 
                     'outsourced_processes', 'overhead']
        
        for component in components:
            estimated = estimated_costs['cost_components'].get(component, 0.0)
            actual = actual_costs.get(component, 0.0)
            variance = actual - estimated
            variance_percent = ((variance / estimated) * 100) if estimated > 0 else 0
            
            variance_analysis['variances'][component] = {
                'estimated': estimated,
                'actual': actual,
                'variance': variance,
                'variance_percent': variance_percent,
                'status': 'over_budget' if variance > 0 else 'under_budget' if variance < 0 else 'on_budget'
            }
        
        # Overall variance
        total_estimated = estimated_costs['total_cost_per_unit']
        total_actual = sum(actual_costs.values())
        total_variance = total_actual - total_estimated
        total_variance_percent = ((total_variance / total_estimated) * 100) if total_estimated > 0 else 0
        
        variance_analysis['total_variance'] = {
            'estimated': total_estimated,
            'actual': total_actual,
            'variance': total_variance,
            'variance_percent': total_variance_percent,
            'status': 'over_budget' if total_variance > 0 else 'under_budget' if total_variance < 0 else 'on_budget'
        }
        
        return variance_analysis

    def mark_costs_outdated(self, trigger_reason: str, affected_item_ids: List[int] = None):
        """Mark item costs as outdated when dependencies change"""
        from models import Item
        
        query = Item.query.filter(Item.cost_source == 'bom_calculated')
        
        if affected_item_ids:
            query = query.filter(Item.id.in_(affected_item_ids))
        
        items = query.all()
        
        for item in items:
            item.cost_calculation_status = 'outdated'
            item.last_cost_calculation = datetime.utcnow()
        
        logger.info(f"Marked {len(items)} items as outdated due to: {trigger_reason}")

    def _manual_cost_result(self, item) -> Dict:
        """Return result for manually priced items"""
        return {
            'success': True,
            'cost_source': 'manual',
            'item_name': item.name,
            'total_cost_per_unit': item.unit_price or 0.0,
            'message': 'Item uses manual pricing',
            'calculation_timestamp': datetime.utcnow()
        }

    def _error_result(self, error_message: str) -> Dict:
        """Return error result"""
        return {
            'success': False,
            'error': error_message,
            'total_cost_per_unit': 0.0,
            'calculation_timestamp': datetime.utcnow()
        }


# Global instance
bom_cost_calculator = BOMCostCalculator()


def calculate_item_cost(item_id: int, quantity: float = 1.0, force_recalculate: bool = False) -> Dict:
    """Convenience function for calculating item cost"""
    return bom_cost_calculator.calculate_item_bom_cost(item_id, quantity, force_recalculate)


def get_vendor_comparison(item_id: int, process_type: str, quantity: float = 1.0) -> List[Dict]:
    """Convenience function for vendor cost comparison"""
    return bom_cost_calculator.get_vendor_cost_comparison(item_id, process_type, quantity)


def update_costs_after_rate_change(rate_id: int) -> List[Dict]:
    """Convenience function for updating costs after rate changes"""
    return bom_cost_calculator.update_costs_for_rate_change(rate_id)


def analyze_cost_variance(item_id: int, actual_costs: Dict) -> Dict:
    """Convenience function for cost variance analysis"""
    return bom_cost_calculator.get_cost_variance_analysis(item_id, actual_costs)


# Cost History and Validation Methods
def _log_cost_change(self, item, old_cost, new_cost, reason):
    """Log cost change for history tracking"""
    try:
        from models.cost_history import ItemCostHistory
        ItemCostHistory.log_cost_change(
            item_id=item.id,
            old_cost=old_cost,
            new_cost=new_cost,
            reason=reason,
            change_type='automatic'
        )
    except ImportError:
        logger.warning("Cost history tracking not available")


def _validate_cost_change(self, item, old_cost, new_cost):
    """Validate cost change against business rules"""
    try:
        from models.cost_history import CostValidationRule
        
        rules = CostValidationRule.query.filter_by(is_active=True).all()
        warnings = []
        
        for rule in rules:
            is_valid, message = rule.validate_cost_change(item, old_cost, new_cost)
            if not is_valid:
                warnings.append({
                    'rule': rule.rule_name,
                    'message': message,
                    'severity': 'warning'
                })
        
        return {
            'is_valid': len(warnings) == 0,
            'warnings': warnings
        }
        
    except ImportError:
        return {'is_valid': True, 'warnings': []}


# Add methods to BOMCostCalculator class
BOMCostCalculator._log_cost_change = _log_cost_change
BOMCostCalculator._validate_cost_change = _validate_cost_change