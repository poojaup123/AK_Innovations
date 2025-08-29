"""
Production Cost Analysis Service

Calculates actual production costs when production orders are completed and updates 
item unit prices with real production data instead of BOM estimates.
"""

from datetime import datetime
from app import db
from models import (
    Production, BOM, Item, JobCard, DailyProductionStatus, 
    ItemBatch, JobWorkBatch, BatchMovementLedger
)
from services.process_integration import ProcessIntegrationService


class ProductionCostAnalysisService:
    """Service for analyzing actual production costs and updating item prices"""
    
    @staticmethod
    def calculate_actual_production_costs(production_id):
        """
        Calculate actual production costs from completed production order
        
        Returns dict with:
        - actual_material_cost_per_unit
        - actual_labor_cost_per_unit  
        - actual_overhead_cost_per_unit
        - actual_scrap_cost_per_unit
        - total_actual_cost_per_unit
        - units_produced
        - cost_variance_from_bom
        """
        
        production = Production.query.get(production_id)
        if not production or production.status != 'completed':
            return None
        
        if not production.item:
            return None
        
        # Get BOM for comparison
        bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
        
        # Calculate actual material costs from batch movements
        actual_material_cost = ProductionCostAnalysisService._calculate_actual_material_cost(production)
        
        # Calculate actual labor costs from job cards
        actual_labor_cost = ProductionCostAnalysisService._calculate_actual_labor_cost(production)
        
        # Calculate actual scrap costs
        actual_scrap_cost = ProductionCostAnalysisService._calculate_actual_scrap_cost(production)
        
        # Calculate overhead allocation (can be based on labor hours or material cost)
        actual_overhead_cost = ProductionCostAnalysisService._calculate_actual_overhead_cost(
            production, actual_material_cost, actual_labor_cost
        )
        
        # Get units produced
        units_produced = production.quantity_good or production.quantity_produced or 0
        
        if units_produced <= 0:
            return None
        
        # Calculate per-unit costs
        actual_costs = {
            'actual_material_cost_per_unit': actual_material_cost / units_produced,
            'actual_labor_cost_per_unit': actual_labor_cost / units_produced,
            'actual_overhead_cost_per_unit': actual_overhead_cost / units_produced,
            'actual_scrap_cost_per_unit': actual_scrap_cost / units_produced,
            'total_actual_cost_per_unit': (actual_material_cost + actual_labor_cost + actual_overhead_cost + actual_scrap_cost) / units_produced,
            'units_produced': units_produced,
            'production_id': production_id,
            'production_number': production.production_number,
            'item_name': production.item.name,
            'completion_date': production.actual_end_date or datetime.now().date()
        }
        
        # Calculate variance from BOM estimates if BOM exists
        if bom:
            bom_cost_per_unit = bom.total_material_cost / (bom.output_quantity or 1) + (bom.calculated_labor_cost_per_unit or 0)
            actual_costs['bom_estimated_cost_per_unit'] = bom_cost_per_unit
            actual_costs['cost_variance_amount'] = actual_costs['total_actual_cost_per_unit'] - bom_cost_per_unit
            actual_costs['cost_variance_percent'] = (actual_costs['cost_variance_amount'] / bom_cost_per_unit * 100) if bom_cost_per_unit > 0 else 0
        
        return actual_costs
    
    @staticmethod
    def _calculate_actual_material_cost(production):
        """Calculate actual material costs from batch movements"""
        total_material_cost = 0.0
        
        # Get all batch movements related to this production (materials consumed)
        # Look for movements from Raw Material to WIP state for this production
        material_movements = BatchMovementLedger.query.filter(
            BatchMovementLedger.ref_type == 'Production',
            BatchMovementLedger.ref_id == production.id,
            BatchMovementLedger.from_state == 'Raw',
            BatchMovementLedger.to_state == 'WIP'
        ).all()
        
        for movement in material_movements:
            total_material_cost += movement.total_cost or 0
        
        # If no batch movements found, estimate from BOM and quantities
        if total_material_cost == 0 and production.item:
            bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
            if bom:
                # Estimate material cost based on BOM and actual production quantity
                production_qty = production.quantity_produced or 0
                bom_output_qty = bom.output_quantity or 1
                material_cost_ratio = production_qty / bom_output_qty
                total_material_cost = bom.total_material_cost * material_cost_ratio
        
        return total_material_cost
    
    @staticmethod
    def _calculate_actual_labor_cost(production):
        """Calculate actual labor costs from job cards"""
        total_labor_cost = 0.0
        
        # Get all job cards for this production
        job_cards = JobCard.query.filter_by(production_order_id=production.id).all()
        
        for job_card in job_cards:
            # Calculate actual labor cost from job card data
            if job_card.actual_labor_hours and job_card.labor_rate_per_hour:
                job_labor_cost = job_card.actual_labor_hours * job_card.labor_rate_per_hour
                total_labor_cost += job_labor_cost
            elif job_card.process and hasattr(job_card.process, 'labor_cost_per_unit'):
                # Use process-based labor cost if available
                units_produced = job_card.quantity_completed or 0
                process_labor_cost = (job_card.process.labor_cost_per_unit or 0) * units_produced
                total_labor_cost += process_labor_cost
        
        # If no job cards, estimate from production daily status or BOM
        if total_labor_cost == 0:
            # Try to get from production daily reports
            daily_reports = DailyProductionStatus.query.filter_by(production_id=production.id).all()
            total_workers_hours = sum(
                (report.workers_assigned or 0) * 8 for report in daily_reports  # Assume 8 hours per day
            )
            if total_workers_hours > 0:
                average_labor_rate = 150  # Default labor rate per hour
                total_labor_cost = total_workers_hours * average_labor_rate
        
        return total_labor_cost
    
    @staticmethod
    def _calculate_actual_scrap_cost(production):
        """Calculate actual scrap costs"""
        scrap_cost = 0.0
        
        # Get actual scrap quantity and calculate cost impact
        scrap_quantity = production.scrap_quantity or 0
        
        if scrap_quantity > 0 and production.item:
            # Estimate scrap cost as material cost of scrapped units
            bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
            if bom and bom.output_quantity:
                material_cost_per_unit = bom.total_material_cost / bom.output_quantity
                scrap_cost = scrap_quantity * material_cost_per_unit
        
        return scrap_cost
    
    @staticmethod
    def _calculate_actual_overhead_cost(production, material_cost, labor_cost):
        """Calculate actual overhead allocation"""
        overhead_cost = 0.0
        
        # Get overhead percentage from BOM or use default
        bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
        
        if bom and bom.overhead_percentage and bom.overhead_percentage > 0:
            # Apply overhead as percentage of material cost
            overhead_cost = material_cost * (bom.overhead_percentage / 100)
        elif bom and bom.overhead_cost_per_unit and bom.overhead_cost_per_unit > 0:
            # Use fixed overhead per unit
            units_produced = production.quantity_produced or 0
            overhead_cost = (bom.overhead_cost_per_unit * units_produced)
        else:
            # Default overhead as percentage of labor cost
            overhead_cost = labor_cost * 0.15  # 15% default overhead on labor
        
        return overhead_cost
    
    @staticmethod
    def update_item_price_from_production(production_id, update_method='weighted_average'):
        """
        Update item unit price based on actual production costs
        
        Args:
            production_id: ID of completed production order
            update_method: 'latest', 'weighted_average', or 'moving_average'
        """
        
        # Calculate actual production costs
        actual_costs = ProductionCostAnalysisService.calculate_actual_production_costs(production_id)
        
        if not actual_costs:
            print(f"⚠️ Could not calculate actual costs for production {production_id}")
            return False
        
        production = Production.query.get(production_id)
        item = production.item
        
        try:
            old_price = item.unit_price or 0
            new_price = actual_costs['total_actual_cost_per_unit']
            
            # Apply update method
            if update_method == 'weighted_average':
                # Weight by quantity produced vs existing stock
                existing_stock = item.current_stock or 0
                new_stock = actual_costs['units_produced']
                total_stock = existing_stock + new_stock
                
                if total_stock > 0:
                    weighted_price = ((old_price * existing_stock) + (new_price * new_stock)) / total_stock
                    new_price = weighted_price
            
            # Update item price with detailed cost breakdown
            cost_notes = (f"Production {production.production_number}: "
                         f"Material(₹{actual_costs['actual_material_cost_per_unit']:.2f}) + "
                         f"Labor(₹{actual_costs['actual_labor_cost_per_unit']:.2f}) + "
                         f"Overhead(₹{actual_costs['actual_overhead_cost_per_unit']:.2f}) + "
                         f"Scrap(₹{actual_costs['actual_scrap_cost_per_unit']:.2f}) = "
                         f"₹{actual_costs['total_actual_cost_per_unit']:.2f} | "
                         f"Units: {actual_costs['units_produced']}")
            
            item.update_price(
                new_price=new_price,
                price_type='production_actual',
                effective_date=actual_costs['completion_date'],
                source='Production Cost Analysis',
                source_reference=f"Production-{production.production_number}",
                notes=cost_notes,
                user_id=1  # System user
            )
            
            db.session.commit()
            
            # Log the update
            variance_info = ""
            if 'cost_variance_amount' in actual_costs:
                variance_info = f" | Variance from BOM: {actual_costs['cost_variance_amount']:+.2f} ({actual_costs['cost_variance_percent']:+.1f}%)"
            
            print(f"✅ Updated {item.name}: ₹{old_price:.2f} → ₹{new_price:.2f} (Actual Production Costs){variance_info}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating item price for production {production_id}: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_production_cost_summary(production_id):
        """Get a detailed cost summary for a completed production"""
        actual_costs = ProductionCostAnalysisService.calculate_actual_production_costs(production_id)
        
        if not actual_costs:
            return None
        
        return {
            'production_info': {
                'production_number': actual_costs['production_number'],
                'item_name': actual_costs['item_name'],
                'units_produced': actual_costs['units_produced'],
                'completion_date': actual_costs['completion_date']
            },
            'cost_breakdown': {
                'material': actual_costs['actual_material_cost_per_unit'],
                'labor': actual_costs['actual_labor_cost_per_unit'],
                'overhead': actual_costs['actual_overhead_cost_per_unit'],
                'scrap': actual_costs['actual_scrap_cost_per_unit'],
                'total': actual_costs['total_actual_cost_per_unit']
            },
            'variance_analysis': {
                'bom_estimate': actual_costs.get('bom_estimated_cost_per_unit', 0),
                'variance_amount': actual_costs.get('cost_variance_amount', 0),
                'variance_percent': actual_costs.get('cost_variance_percent', 0)
            }
        }