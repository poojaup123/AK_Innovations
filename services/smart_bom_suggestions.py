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
        
        # Optimize manufacturing suggestions with shared raw materials
        optimized_suggestions = SmartBOMSuggestionService._optimize_shared_raw_materials(suggestions)
        
        # Generate purchase order suggestions for direct materials 
        purchase_suggestions = SmartBOMSuggestionService._generate_purchase_suggestions([
            s for s in shortages if not s.get('can_manufacture', False)
        ])
        
        # Consolidate purchase suggestions for shared raw materials across manufacturing suggestions
        consolidated_purchase_suggestions = SmartBOMSuggestionService._consolidate_shared_material_purchases(
            optimized_suggestions, purchase_suggestions
        )
        
        all_suggestions = optimized_suggestions + consolidated_purchase_suggestions
        
        return {
            'has_shortages': len(shortages) > 0,
            'shortages': shortages,
            'suggestions': all_suggestions,
            'total_shortage_items': len(shortages),
            'manufacturable_items': len([s for s in shortages if s.get('can_manufacture', False)]),
            'direct_purchase_items': len([s for s in shortages if not s.get('can_manufacture', False)])
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
    
    @staticmethod
    def _optimize_shared_raw_materials(manufacturing_suggestions: List[Dict]) -> List[Dict]:
        """
        Optimize manufacturing suggestions when multiple items share the same raw materials
        Intelligently allocate raw materials and adjust priorities
        """
        if not manufacturing_suggestions:
            return []
        
        # Group suggestions by shared raw materials
        raw_material_usage = {}
        
        for suggestion in manufacturing_suggestions:
            for raw_material in suggestion['raw_materials']:
                material_id = raw_material['material_id']
                if material_id not in raw_material_usage:
                    raw_material_usage[material_id] = {
                        'material_info': raw_material,
                        'total_needed': 0,
                        'suggestions_using': []
                    }
                
                raw_material_usage[material_id]['total_needed'] += raw_material['needed_qty']
                raw_material_usage[material_id]['suggestions_using'].append(suggestion)
        
        optimized_suggestions = []
        
        for suggestion in manufacturing_suggestions:
            # Update raw material allocations based on shared usage
            optimized_raw_materials = []
            total_cost = 0
            all_materials_sufficient = True
            
            for raw_material in suggestion['raw_materials']:
                material_id = raw_material['material_id']
                usage_info = raw_material_usage[material_id]
                
                # Calculate what can be made with available materials
                if len(usage_info['suggestions_using']) > 1:
                    available_qty = raw_material['available_qty']
                    total_needed_across_all = usage_info['total_needed']
                    
                    if available_qty >= total_needed_across_all:
                        # Sufficient for all - allocate proportionally
                        allocated_qty = raw_material['needed_qty']
                        sufficient = True
                        can_produce_qty = raw_material['needed_qty']
                    else:
                        # Calculate what portion can be produced with available material
                        proportion = available_qty / total_needed_across_all
                        can_produce_qty = raw_material['needed_qty'] * proportion
                        allocated_qty = available_qty * (raw_material['needed_qty'] / total_needed_across_all)
                        sufficient = False
                    
                    shortage_qty = max(0, raw_material['needed_qty'] - allocated_qty)
                    
                    optimized_material = {
                        **raw_material,
                        'allocated_qty': allocated_qty,
                        'can_produce_qty': can_produce_qty,
                        'shortage_qty': shortage_qty,
                        'sufficient': sufficient,
                        'shared_material': True,
                        'sharing_info': f"Shared with {len(usage_info['suggestions_using']) - 1} other items"
                    }
                else:
                    # Only one suggestion needs this material
                    available_qty = raw_material['available_qty']
                    needed_qty = raw_material['needed_qty']
                    can_produce_qty = min(available_qty, needed_qty)
                    shortage_qty = max(0, needed_qty - available_qty)
                    
                    optimized_material = {
                        **raw_material,
                        'allocated_qty': can_produce_qty,
                        'can_produce_qty': can_produce_qty,
                        'shortage_qty': shortage_qty,
                        'sufficient': available_qty >= needed_qty,
                        'shared_material': False
                    }
                
                if not optimized_material['sufficient']:
                    all_materials_sufficient = False
                
                total_cost += optimized_material['estimated_cost']
                optimized_raw_materials.append(optimized_material)
            
            # Calculate what can be produced with available materials
            max_producible = min([
                (mat['allocated_qty'] / mat['needed_qty']) * suggestion['target_quantity'] 
                for mat in optimized_raw_materials if mat['needed_qty'] > 0
            ]) if optimized_raw_materials else 0
            
            # Generate suggestions for both partial production and material procurement
            suggestions_to_add = []
            
            # Partial production suggestion (if any amount can be produced)
            if max_producible > 0:
                partial_suggestion = {
                    **suggestion,
                    'type': 'partial_manufacturing_recommendation',
                    'title': f"Manufacture {max_producible:.1f} units of {suggestion['target_item_name']} (Partial Production)",
                    'description': f"Produce {max_producible:.1f} out of {suggestion['target_quantity']:.1f} units using available materials",
                    'producible_quantity': max_producible,
                    'target_quantity': suggestion['target_quantity'],
                    'raw_materials_required': optimized_raw_materials,
                    'can_manufacture': True,
                    'total_estimated_cost': total_cost * (max_producible / suggestion['target_quantity']),
                    'estimated_cost': total_cost * (max_producible / suggestion['target_quantity']),
                    'priority': 'high',
                    'feasibility': 'feasible',
                    'estimated_time': f"{suggestion.get('manufacturing_lead_time', 1)} days",
                    'bom_reference': suggestion.get('bom_code', 'N/A'),
                    'action_steps': [
                        f"Create job work order for {max_producible:.1f} units using BOM: {suggestion.get('bom_code', 'N/A')}",
                        f"Issue available raw materials (partial quantities)",
                        f"Complete partial production: {max_producible:.1f} units",
                        f"Remaining needed: {(suggestion['target_quantity'] - max_producible):.1f} units"
                    ]
                }
                suggestions_to_add.append(partial_suggestion)
            
            # Material procurement suggestion for shortage
            material_shortages = [mat for mat in optimized_raw_materials if mat['shortage_qty'] > 0]
            if material_shortages:
                procurement_suggestion = {
                    'type': 'material_procurement_recommendation',
                    'title': f"Purchase Additional Materials for {suggestion['target_item_name']} Production",
                    'description': f"Purchase {len(material_shortages)} materials to satisfy remaining {(suggestion['target_quantity'] - max_producible):.1f} units",
                    'target_item': suggestion['target_item_name'],
                    'remaining_quantity': suggestion['target_quantity'] - max_producible,
                    'material_shortages': material_shortages,
                    'priority': 'high',
                    'estimated_cost': sum(mat['shortage_qty'] * (mat.get('unit_cost', 0) or 0) for mat in material_shortages),
                    'action_steps': [
                        f"Purchase the following materials for remaining {(suggestion['target_quantity'] - max_producible):.1f} units:",
                        *[f"  • {mat['material_name']}: {mat['shortage_qty']:.1f} {mat['unit']}" for mat in material_shortages],
                        f"After procurement, complete remaining production"
                    ]
                }
                suggestions_to_add.append(procurement_suggestion)
            
            # Add all generated suggestions for this item
            optimized_suggestions.extend(suggestions_to_add)
        
        return optimized_suggestions
    
    @staticmethod
    def _generate_purchase_suggestions(direct_material_shortages: List[Dict]) -> List[Dict]:
        """
        Generate purchase order suggestions for direct materials that cannot be manufactured
        """
        purchase_suggestions = []
        
        for shortage in direct_material_shortages:
            if shortage.get('can_manufacture', False):
                continue  # Skip items that can be manufactured
                
            purchase_suggestion = {
                'type': 'purchase_order_recommendation',
                'priority': 'high',  # Direct materials are high priority
                'title': f"Purchase {shortage['item_name']} - Direct Material",
                'description': f"Create purchase order for {shortage['shortage_qty']:.1f} {shortage['unit']} of {shortage['item_name']}",
                'action_steps': [
                    f"Create Purchase Order for {shortage['shortage_qty']:.1f} {shortage['unit']} of {shortage['item_name']}",
                    "Contact supplier and negotiate pricing",
                    "Include additional safety stock (recommend +20%)",
                    f"Expected cost: ₹{(shortage.get('item_type') == 'material' and getattr(shortage, 'unit_price', 0) or 0) * shortage['shortage_qty']:.2f}",
                    "Track delivery schedule and update inventory upon receipt"
                ],
                'item_details': {
                    'item_id': shortage['item_id'],
                    'item_code': shortage['item_code'],
                    'item_name': shortage['item_name'],
                    'shortage_qty': shortage['shortage_qty'],
                    'recommended_qty': shortage['shortage_qty'] * 1.2,  # Add 20% safety stock
                    'unit': shortage['unit']
                },
                'estimated_cost': shortage.get('estimated_cost', 0),
                'estimated_time': "3-7 days (depends on supplier)",
                'feasibility': 'requires_supplier_contact',
                'purchase_priority': 'immediate' if shortage['shortage_qty'] > shortage['available_qty'] * 2 else 'normal'
            }
            
            purchase_suggestions.append(purchase_suggestion)
        
        return purchase_suggestions
    
    @staticmethod
    def _generate_optimization_notes(optimized_materials: List[Dict], usage_info: Dict = None) -> List[str]:
        """Generate optimization notes for material allocation"""
        notes = []
        
        shared_materials = [m for m in optimized_materials if m.get('shared_material', False)]
        if shared_materials:
            notes.append("⚠ Raw material optimization applied:")
            for material in shared_materials:
                notes.append(f"  • {material['material_name']}: {material.get('sharing_info', 'Shared resource')}")
        
        insufficient_materials = [m for m in optimized_materials if not m.get('sufficient', True)]
        if insufficient_materials:
            notes.append("📋 Additional materials needed:")
            for material in insufficient_materials:
                shortage = material['needed_qty'] - material.get('allocated_qty', material['available_qty'])
                notes.append(f"  • {material['material_name']}: {shortage:.1f} {material['unit']} more required")
                notes.append(f"    Recommended: Purchase additional {material['material_name']} sheets")
        
        return notes
    
    @staticmethod
    def _consolidate_shared_material_purchases(manufacturing_suggestions: List[Dict], purchase_suggestions: List[Dict]) -> List[Dict]:
        """
        Consolidate purchase suggestions when multiple manufacturing suggestions require the same raw materials
        Create a single consolidated purchase order for shared materials
        """
        # Track material requirements across all manufacturing suggestions
        consolidated_materials = {}
        
        # Process manufacturing suggestions to extract raw material requirements
        for suggestion in manufacturing_suggestions:
            if suggestion.get('raw_materials_required'):
                for material in suggestion['raw_materials_required']:
                    if not material.get('sufficient', True):  # Only insufficient materials
                        material_id = material['material_id']
                        shortage_qty = material.get('shortage_qty', 0)
                        
                        if shortage_qty > 0:
                            if material_id not in consolidated_materials:
                                consolidated_materials[material_id] = {
                                    'material_id': material_id,
                                    'material_name': material['material_name'],
                                    'unit': material['unit'],
                                    'total_shortage_qty': 0,
                                    'used_by_products': [],
                                    'estimated_cost': 0,
                                    'unit_cost': material.get('unit_cost', 0)
                                }
                            
                            consolidated_materials[material_id]['total_shortage_qty'] += shortage_qty
                            consolidated_materials[material_id]['used_by_products'].append({
                                'product_name': suggestion.get('target_item_name', 'Unknown'),
                                'quantity_needed': shortage_qty
                            })
                            consolidated_materials[material_id]['estimated_cost'] += shortage_qty * material.get('unit_cost', 0)
        
        # Create consolidated purchase suggestions
        consolidated_suggestions = []
        
        for material_id, material_info in consolidated_materials.items():
            if len(material_info['used_by_products']) > 1:  # Only consolidate if used by multiple products
                # Create consolidated purchase suggestion
                product_list = [f"{prod['product_name']} ({prod['quantity_needed']:.1f} {material_info['unit']})" 
                              for prod in material_info['used_by_products']]
                
                consolidated_suggestion = {
                    'type': 'consolidated_purchase_recommendation',
                    'priority': 'high',
                    'title': f'Consolidated Purchase: {material_info["material_name"]}',
                    'description': f'Purchase {material_info["total_shortage_qty"]:.1f} {material_info["unit"]} of {material_info["material_name"]} for multiple products',
                    'action_steps': [
                        f'Create consolidated Purchase Order for {material_info["total_shortage_qty"]:.1f} {material_info["unit"]} of {material_info["material_name"]}',
                        f'This material is needed for: {", ".join([prod["product_name"] for prod in material_info["used_by_products"]])}',
                        'Material breakdown by product:',
                        *[f'  • {prod_desc}' for prod_desc in product_list],
                        'Contact supplier for bulk pricing discount',
                        'Schedule delivery to support all manufacturing timelines'
                    ],
                    'estimated_cost': material_info['estimated_cost'],
                    'estimated_time': '3-7 days (supplier dependent)',
                    'feasibility': 'requires_supplier_contact',
                    'consolidation_benefit': f'Consolidated {len(material_info["used_by_products"])} separate purchases into one order',
                    'raw_materials_required': [{
                        'material_id': material_id,
                        'material_name': material_info['material_name'],
                        'needed_qty': material_info['total_shortage_qty'],
                        'shortage_qty': material_info['total_shortage_qty'],
                        'unit': material_info['unit'],
                        'sufficient': False,
                        'unit_cost': material_info['unit_cost'],
                        'consolidated': True,
                        'used_by': material_info['used_by_products']
                    }],
                    'item_details': {
                        'item_id': material_id,
                        'item_code': f'CONSOLIDATED-{material_id}',
                        'item_name': material_info['material_name'],
                        'shortage_qty': material_info['total_shortage_qty'],
                        'recommended_qty': material_info['total_shortage_qty'] * 1.1,  # Add 10% safety stock
                        'unit': material_info['unit']
                    }
                }
                
                consolidated_suggestions.append(consolidated_suggestion)
        
        # Add remaining non-consolidated purchase suggestions
        remaining_purchase_suggestions = []
        consolidated_material_ids = set(consolidated_materials.keys())
        
        for suggestion in purchase_suggestions:
            item_details = suggestion.get('item_details', {})
            if item_details.get('item_id') not in consolidated_material_ids:
                remaining_purchase_suggestions.append(suggestion)
        
        return consolidated_suggestions + remaining_purchase_suggestions