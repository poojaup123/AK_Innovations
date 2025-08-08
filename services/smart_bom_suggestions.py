"""
Smart BOM-based Material Suggestion Service
Analyzes nested BOM structures to provide intelligent suggestions when materials are short
"""

from models import BOM, BOMItem, Item
from models.batch import InventoryBatch
from app import db
from sqlalchemy import func
from typing import List, Dict, Tuple, Optional

class SmartBOMSuggestionService:
    """
    Provides intelligent suggestions for material shortages based on nested BOM analysis
    """
    
    @staticmethod
    def analyze_material_shortages_with_suggestions(bom: BOM, planned_quantity: float) -> Dict:
        """
        Analyze material shortages and provide smart suggestions for production alternatives
        Returns a comprehensive analysis with suggestions for using raw materials to make intermediate products
        """
        shortages = []
        suggestions = []
        
        # Get all BOM items and their requirements
        for bom_item in bom.items:
            item = bom_item.item
            material_qty_per_output = bom_item.quantity_required or bom_item.qty_required
            bom_output_qty = bom.output_quantity or 1.0
            
            # Calculate required quantity
            required_qty = (planned_quantity / bom_output_qty) * material_qty_per_output
            
            # Check current availability
            available_qty = SmartBOMSuggestionService._get_available_quantity(item)
            
            if available_qty < required_qty:
                shortage_qty = required_qty - available_qty
                
                # Basic shortage info
                shortage_info = {
                    'item_id': item.id,
                    'item_code': item.code,
                    'item_name': item.name,
                    'required_qty': required_qty,
                    'available_qty': available_qty,
                    'shortage_qty': shortage_qty,
                    'unit': item.unit_of_measure,
                    'item_type': getattr(item, 'item_type', 'material')
                }
                
                # Check if this item can be manufactured (has its own BOM)
                manufacturing_suggestion = SmartBOMSuggestionService._analyze_manufacturing_options(
                    item, shortage_qty
                )
                
                if manufacturing_suggestion:
                    shortage_info['can_manufacture'] = True
                    shortage_info['manufacturing_suggestion'] = manufacturing_suggestion
                    suggestions.append(manufacturing_suggestion)
                else:
                    shortage_info['can_manufacture'] = False
                
                shortages.append(shortage_info)
        
        return {
            'has_shortages': len(shortages) > 0,
            'shortages': shortages,
            'suggestions': suggestions,
            'total_shortage_items': len(shortages),
            'manufacturable_items': len([s for s in shortages if s.get('can_manufacture', False)])
        }
    
    @staticmethod
    def _get_available_quantity(item: Item) -> float:
        """Get total available quantity for an item across all inventory states and batches"""
        # Item-level quantities
        available_qty = 0
        if hasattr(item, 'qty_raw') and hasattr(item, 'qty_finished'):
            available_qty = (item.qty_raw or 0) + (item.qty_finished or 0)
        else:
            available_qty = item.current_stock or 0
        
        # Batch-level quantities (use higher value)
        # Use actual InventoryBatch fields: qty_raw, qty_finished, qty_wip
        batch_qty = db.session.query(
            func.sum(InventoryBatch.qty_raw + InventoryBatch.qty_finished + InventoryBatch.qty_wip)
        ).filter_by(item_id=item.id).scalar() or 0
        
        return max(available_qty, batch_qty)
    
    @staticmethod
    def _analyze_manufacturing_options(item: Item, required_qty: float) -> Optional[Dict]:
        """
        Analyze if an item can be manufactured and what raw materials are needed
        """
        # Find BOM for this item
        item_bom = BOM.query.filter_by(product_id=item.id, is_active=True).first()
        
        if not item_bom:
            return None
        
        # Analyze raw materials needed to manufacture this item
        raw_materials_analysis = []
        can_manufacture = True
        total_estimated_cost = 0
        
        for bom_item in item_bom.items:
            raw_material = bom_item.item
            material_qty_per_unit = bom_item.quantity_required or bom_item.qty_required
            bom_output_qty = item_bom.output_quantity or 1.0
            
            # Calculate how much raw material needed for the shortage quantity
            raw_material_needed = (required_qty / bom_output_qty) * material_qty_per_unit
            raw_material_available = SmartBOMSuggestionService._get_available_quantity(raw_material)
            
            raw_material_info = {
                'material_id': raw_material.id,
                'material_code': raw_material.code,
                'material_name': raw_material.name,
                'needed_qty': raw_material_needed,
                'available_qty': raw_material_available,
                'sufficient': raw_material_available >= raw_material_needed,
                'unit': raw_material.unit_of_measure,
                'estimated_cost': (raw_material.unit_price or 0) * raw_material_needed
            }
            
            if not raw_material_info['sufficient']:
                can_manufacture = False
            
            total_estimated_cost += raw_material_info['estimated_cost']
            raw_materials_analysis.append(raw_material_info)
        
        return {
            'target_item_id': item.id,
            'target_item_code': item.code,
            'target_item_name': item.name,
            'target_quantity': required_qty,
            'bom_id': item_bom.id,
            'bom_code': item_bom.bom_code,
            'can_manufacture': can_manufacture,
            'raw_materials': raw_materials_analysis,
            'total_estimated_cost': total_estimated_cost,
            'manufacturing_lead_time': getattr(item_bom, 'lead_time_days', 1),
            'suggestion_type': 'manufacture_from_raw_materials',
            'confidence_level': 'high' if can_manufacture else 'medium'
        }
    
    @staticmethod
    def get_smart_suggestions_for_shortages(shortages: List[Dict]) -> List[Dict]:
        """
        Generate actionable smart suggestions for a list of material shortages
        """
        smart_suggestions = []
        
        for shortage in shortages:
            if shortage.get('can_manufacture', False):
                suggestion = shortage['manufacturing_suggestion']
                
                # Enhanced suggestion with actionable steps
                smart_suggestion = {
                    'type': 'manufacturing_recommendation',
                    'priority': 'high' if suggestion['can_manufacture'] else 'medium',
                    'title': f"Manufacture {shortage['item_name']} from Raw Materials",
                    'description': f"You can produce {shortage['shortage_qty']:.1f} {shortage['unit']} of {shortage['item_name']} using available raw materials",
                    'action_steps': SmartBOMSuggestionService._generate_action_steps(suggestion),
                    'raw_materials_required': suggestion['raw_materials'],
                    'estimated_cost': suggestion['total_estimated_cost'],
                    'estimated_time': f"{suggestion['manufacturing_lead_time']} days",
                    'bom_reference': suggestion['bom_code'],
                    'feasibility': 'feasible' if suggestion['can_manufacture'] else 'limited_by_raw_materials'
                }
                
                smart_suggestions.append(smart_suggestion)
        
        return smart_suggestions
    
    @staticmethod
    def _generate_action_steps(manufacturing_suggestion: Dict) -> List[str]:
        """Generate step-by-step actions for manufacturing suggestions"""
        steps = []
        
        if manufacturing_suggestion['can_manufacture']:
            steps.append(f"Create job work order using BOM: {manufacturing_suggestion['bom_code']}")
            
            # Build materials list without nested f-strings
            materials_list = []
            for rm in manufacturing_suggestion['raw_materials']:
                materials_list.append(f"{rm['needed_qty']:.1f} {rm['unit']} of {rm['material_name']}")
            steps.append(f"Issue raw materials: {', '.join(materials_list)}")
            
            steps.append(f"Expected output: {manufacturing_suggestion['target_quantity']:.1f} units of {manufacturing_suggestion['target_item_name']}")
            steps.append(f"Estimated completion: {manufacturing_suggestion['manufacturing_lead_time']} days")
        else:
            insufficient_materials = [rm for rm in manufacturing_suggestion['raw_materials'] if not rm['sufficient']]
            steps.append("⚠ Cannot manufacture due to insufficient raw materials:")
            for rm in insufficient_materials:
                shortage = rm['needed_qty'] - rm['available_qty']
                steps.append(f"  • Need {shortage:.1f} more {rm['unit']} of {rm['material_name']}")
            steps.append("Consider purchasing additional raw materials or finding alternative suppliers")
        
        return steps