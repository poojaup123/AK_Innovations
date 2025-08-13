"""
Smart BOM-based Material Suggestion Service
Analyzes nested BOM structures to provide intelligent suggestions when materials are short
"""

from models import BOM, BOMItem, Item, PurchaseOrder, PurchaseOrderItem
from models.batch import InventoryBatch
from models.grn import GRN, GRNLineItem
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
        bom_items = bom.items if hasattr(bom, 'items') and bom.items else []
        for bom_item in bom_items:
            item = bom_item.item
            material_qty_per_output = bom_item.quantity_required or bom_item.qty_required
            bom_output_qty = bom.output_quantity or 1.0
            
            # Calculate required quantity
            required_qty = (planned_quantity / bom_output_qty) * material_qty_per_output
            
            # Check current availability
            available_qty = SmartBOMSuggestionService._get_available_quantity(item)
            
            if available_qty < required_qty:
                shortage_qty = required_qty - available_qty
                
                # Get PO status information for this item
                inventory_qty = SmartBOMSuggestionService._get_inventory_only_quantity(item)
                pending_po_qty = SmartBOMSuggestionService._get_pending_po_quantity(item)
                po_status = SmartBOMSuggestionService._get_po_status_info(item)
                
                # Basic shortage info with PO context
                shortage_info = {
                    'item_id': item.id,
                    'item_code': item.code,
                    'item_name': item.name,
                    'required_qty': required_qty,
                    'available_qty': available_qty,
                    'inventory_qty': inventory_qty,
                    'pending_po_qty': pending_po_qty,
                    'shortage_qty': shortage_qty,
                    'unit': item.unit_of_measure,
                    'item_type': getattr(item, 'item_type', 'material'),
                    'po_status': po_status
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
        
        # ALSO generate purchase suggestions for items that CAN be manufactured (buy vs make option)
        # BUT ONLY if they are not intermediate products with complex BOMs
        manufacturable_purchase_suggestions = SmartBOMSuggestionService._generate_purchase_alternatives_for_manufacturable_items([
            s for s in shortages if s.get('can_manufacture', False) and SmartBOMSuggestionService._should_offer_purchase_alternative(s)
        ])
        
        # Consolidate purchase suggestions for shared raw materials across manufacturing suggestions
        consolidated_purchase_suggestions = SmartBOMSuggestionService._consolidate_shared_material_purchases(
            optimized_suggestions, purchase_suggestions
        )
        
        # Keep all original suggestions AND add consolidated suggestions AND alternative purchase options
        # This gives users choice between individual purchases, consolidated bulk purchasing, and buy vs make
        all_suggestions = optimized_suggestions + consolidated_purchase_suggestions + purchase_suggestions + manufacturable_purchase_suggestions
        
        # Apply final deduplication to remove exact duplicates
        final_suggestions = SmartBOMSuggestionService._final_deduplication(all_suggestions)
        
        return {
            'has_shortages': len(shortages) > 0,
            'shortages': shortages,
            'suggestions': final_suggestions,
            'total_shortage_items': len(shortages),
            'manufacturable_items': len([s for s in shortages if s.get('can_manufacture', False)]),
            'direct_purchase_items': len([s for s in shortages if not s.get('can_manufacture', False)])
        }
    
    @staticmethod
    def _get_available_quantity(item: Item) -> float:
        """Get available quantity for immediate production (inventory only, not including pending POs)"""
        # Use only current inventory for production planning
        batch_qty = db.session.query(
            func.sum(InventoryBatch.qty_raw + InventoryBatch.qty_finished + InventoryBatch.qty_wip)
        ).filter_by(item_id=item.id).scalar() or 0
        
        return batch_qty
    
    @staticmethod
    def _get_pending_po_quantity(item: Item) -> float:
        """Get quantity of item that's ordered in POs but not yet received"""
        # Get all PO items for this material
        po_items = PurchaseOrderItem.query.filter_by(item_id=item.id).all()
        
        total_pending = 0
        for po_item in po_items:
            # Get the PO status
            po = PurchaseOrder.query.get(po_item.purchase_order_id)
            if po and po.status in ['sent', 'partial']:  # Active POs
                ordered_qty = po_item.quantity_ordered or 0
                
                # Calculate how much has been received via GRNs
                received_qty = 0
                grns = GRN.query.filter_by(purchase_order_id=po.id).all()
                for grn in grns:
                    grn_items = GRNLineItem.query.filter_by(grn_id=grn.id, item_id=item.id).all()
                    received_qty += sum(grn_item.quantity_received for grn_item in grn_items)
                
                # Pending = Ordered - Received
                pending = max(0, ordered_qty - received_qty)
                total_pending += pending
        
        return total_pending
    
    @staticmethod
    def _get_inventory_only_quantity(item: Item) -> float:
        """Get quantity available in inventory only (excluding pending POs)"""
        batch_qty = db.session.query(
            func.sum(InventoryBatch.qty_raw + InventoryBatch.qty_finished + InventoryBatch.qty_wip)
        ).filter_by(item_id=item.id).scalar() or 0
        return batch_qty
    
    @staticmethod
    def _get_po_status_info(item: Item) -> Dict:
        """Get detailed PO status information for an item"""
        po_items = PurchaseOrderItem.query.filter_by(item_id=item.id).all()
        
        total_ordered = 0
        total_received = 0
        active_pos = []
        
        for po_item in po_items:
            po = PurchaseOrder.query.get(po_item.purchase_order_id)
            if po and po.status in ['sent', 'partial']:
                ordered_qty = po_item.quantity_ordered or 0
                total_ordered += ordered_qty
                
                # Calculate received quantity for this PO
                received_qty = 0
                grns = GRN.query.filter_by(purchase_order_id=po.id).all()
                for grn in grns:
                    grn_items = GRNLineItem.query.filter_by(grn_id=grn.id, item_id=item.id).all()
                    received_qty += sum(grn_item.quantity_received for grn_item in grn_items)
                
                total_received += received_qty
                
                active_pos.append({
                    'po_number': po.po_number,
                    'ordered_qty': ordered_qty,
                    'received_qty': received_qty,
                    'pending_qty': max(0, ordered_qty - received_qty),
                    'status': po.status
                })
        
        return {
            'has_active_pos': len(active_pos) > 0,
            'total_ordered': total_ordered,
            'total_received': total_received,
            'total_pending': max(0, total_ordered - total_received),
            'active_pos': active_pos
        }
    
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
            # BOM output quantity tells us how many final products one BOM run produces
            # So raw_material_needed = (final_products_wanted / products_per_bom_run) * material_per_bom_run
            raw_material_needed = (required_qty / bom_output_qty) * material_qty_per_unit
            raw_material_available = SmartBOMSuggestionService._get_available_quantity(raw_material)
            
            # Get PO status for this raw material
            po_status = SmartBOMSuggestionService._get_po_status_info(raw_material)
            
            raw_material_info = {
                'material_id': raw_material.id,
                'material_code': raw_material.code,
                'material_name': raw_material.name,
                'needed_qty': raw_material_needed,
                'available_qty': raw_material_available,
                'sufficient': raw_material_available >= raw_material_needed,
                'unit': raw_material.unit_of_measure,
                'estimated_cost': (raw_material.unit_price or 0) * raw_material_needed,
                'po_status': po_status  # Include PO/GRN information
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
            steps.append(f"Create job card using BOM: {manufacturing_suggestion['bom_code']}")
            
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
                
                # Calculate allocation for shared materials 
                if len(usage_info['suggestions_using']) > 1:
                    available_qty = raw_material['available_qty']
                    total_needed_across_all = usage_info['total_needed']
                    
                    if available_qty >= total_needed_across_all:
                        # Sufficient for all - allocate fully
                        allocated_qty = raw_material['needed_qty']
                        sufficient = True
                        can_produce_qty = raw_material['needed_qty']
                    else:
                        # Calculate proportional allocation
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
                # Check pending PO information for context
                pending_context = []
                for material in optimized_raw_materials:
                    material_id = material.get('material_id', material.get('item_id'))
                    if material_id:
                        item = Item.query.get(material_id)
                        if item:
                            po_status = SmartBOMSuggestionService._get_po_status_info(item)
                            if po_status['total_pending'] > 0:
                                pending_context.append(f"{po_status['total_pending']:.0f} {material.get('material_name', item.name)} pending delivery")
                
                action_steps = [
                    f"Create job card for {max_producible:.1f} units using BOM: {suggestion.get('bom_code', 'N/A')}",
                    f"Issue available raw materials (current inventory only)",
                    f"Complete partial production: {max_producible:.1f} units"
                ]
                
                if pending_context:
                    action_steps.append(f"Additional production possible once pending materials arrive: {', '.join(pending_context)}")
                
                partial_suggestion = {
                    **suggestion,
                    'type': 'partial_manufacturing_recommendation',
                    'title': f"Manufacture {max_producible:.0f} units of {suggestion['target_item_name']} (Current Inventory)",
                    'description': f"Produce {max_producible:.0f} units using available inventory. Additional production possible once {', '.join(pending_context) if pending_context else 'pending materials arrive'}.",
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
                    'bom_id': suggestion.get('bom_id'),
                    'bom_product_name': suggestion.get('target_item_name'),
                    'action_steps': action_steps,
                    'pending_materials': pending_context
                }
                suggestions_to_add.append(partial_suggestion)
            
            # Material procurement suggestion for shortage (considering PO status)
            material_shortages = [mat for mat in optimized_raw_materials if mat['shortage_qty'] > 0]
            if material_shortages:
                # Check PO status for shortages - don't suggest purchase if sufficient POs exist
                po_aware_shortages = []
                for shortage in material_shortages:
                    item = Item.query.get(shortage.get('material_id', shortage.get('item_id')))
                    if item:
                        po_status = SmartBOMSuggestionService._get_po_status_info(item)
                    else:
                        po_status = {'total_pending': 0}
                    
                    # Only suggest purchase if pending PO quantity doesn't cover the shortage
                    if po_status['total_pending'] < shortage['shortage_qty']:
                        shortage['po_status'] = po_status
                        shortage['actual_shortage'] = shortage['shortage_qty'] - po_status['total_pending']
                        po_aware_shortages.append(shortage)
                
                material_shortages = po_aware_shortages
                
            if material_shortages:
                procurement_suggestion = {
                    'type': 'material_procurement_recommendation',
                    'title': f"Purchase Additional Materials for {suggestion['target_item_name']} Production",
                    'description': f"Purchase {len(material_shortages)} materials to satisfy remaining {(suggestion['target_quantity'] - max_producible):.1f} units (Check consolidated options above for potential cost savings)",
                    'target_item': suggestion['target_item_name'],
                    'target_item_id': suggestion.get('target_item_id'),  # Add missing target_item_id
                    'target_item_name': suggestion.get('target_item_name'),  # Add missing target_item_name
                    'remaining_quantity': suggestion['target_quantity'] - max_producible,
                    'material_shortages': material_shortages,
                    'priority': 'high',
                    'estimated_cost': sum(mat['shortage_qty'] * (mat.get('unit_price', 0) or 0) for mat in material_shortages),
                    'bom_id': suggestion.get('bom_id'),
                    'bom_product_name': suggestion.get('target_item_name'),
                    'action_steps': [
                        f"Purchase the following materials for remaining {(suggestion['target_quantity'] - max_producible):.1f} units:",
                        *[f"  • {mat['material_name']}: {mat['shortage_qty']:.1f} {mat['unit']}" for mat in material_shortages],
                        f"After procurement, complete remaining production"
                    ]
                }
                suggestions_to_add.append(procurement_suggestion)
            
            # Add all generated suggestions for this item
            optimized_suggestions.extend(suggestions_to_add)
        
        # Deduplicate suggestions more effectively - but keep separate suggestions for different target items
        seen_suggestions = {}
        deduplicated_suggestions = []
        
        for suggestion in optimized_suggestions:
            # Create a unique key based on target item ID, item name, and suggestion type to ensure separate items get separate suggestions
            target_item_id = suggestion.get('target_item_id', suggestion.get('bom_id', ''))
            item_name = suggestion.get('target_item_name', '')
            suggestion_type = suggestion.get('type', '')
            unique_key = f"{target_item_id}|{item_name}|{suggestion_type}"
            
            # Only add if we haven't seen this exact combination
            if unique_key not in seen_suggestions:
                seen_suggestions[unique_key] = suggestion
                deduplicated_suggestions.append(suggestion)
            else:
                # If we have seen it, keep the one with higher producible quantity
                existing = seen_suggestions[unique_key]
                current_qty = suggestion.get('producible_quantity', 0)
                existing_qty = existing.get('producible_quantity', 0)
                
                if current_qty > existing_qty:
                    # Replace with better suggestion
                    seen_suggestions[unique_key] = suggestion
                    # Remove the old one and add the new one
                    deduplicated_suggestions = [s for s in deduplicated_suggestions if s != existing]
                    deduplicated_suggestions.append(suggestion)
        
        return deduplicated_suggestions
    
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
    def _generate_purchase_alternatives_for_manufacturable_items(manufacturable_shortages: List[Dict]) -> List[Dict]:
        """
        Generate purchase alternatives for items that can be manufactured (buy vs make decision)
        """
        purchase_alternatives = []
        
        for shortage in manufacturable_shortages:
            if not shortage.get('can_manufacture', False):
                continue  # Skip items that cannot be manufactured
                
            purchase_alternative = {
                'type': 'purchase_order_recommendation',
                'priority': 'medium',  # Lower priority than direct materials since it can be manufactured
                'title': f"Purchase {shortage['item_name']} - Consolidated Item",
                'description': f"Buy {shortage['shortage_qty']:.1f} {shortage['unit']} of {shortage['item_name']} directly instead of manufacturing",
                'action_steps': [
                    f"Create Purchase Order for {shortage['shortage_qty']:.1f} {shortage['unit']} of {shortage['item_name']}",
                    "Contact supplier and negotiate pricing",
                    "Include additional safety stock (recommend +20%)",
                    f"Expected cost: ₹{(getattr(shortage, 'unit_price', 0) or 0) * shortage['shortage_qty']:.2f}",
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
                'target_item_id': shortage['item_id'],  # This is the key field that was missing!
                'target_item_name': shortage['item_name'],
                'estimated_cost': shortage.get('estimated_cost', 0),
                'estimated_time': "3-7 days (depends on supplier)",
                'feasibility': 'requires_supplier_contact',
                'purchase_priority': 'alternative',  # Mark as alternative to manufacturing
                'manufacturing_alternative': True,  # Flag to show this is a buy vs make option
                'alternative_note': f"Alternative to manufacturing using BOM. Consider cost comparison with raw materials."
            }
            
            purchase_alternatives.append(purchase_alternative)
        
        return purchase_alternatives
    
    @staticmethod
    def _should_offer_purchase_alternative(shortage_info: Dict) -> bool:
        """
        Determine if we should offer a purchase alternative for a manufacturable item
        Returns False for intermediate products that are part of complex nested BOMs
        """
        item_id = shortage_info.get('item_id')
        if not item_id:
            return False
            
        # Get the item
        item = Item.query.get(item_id)
        if not item:
            return False
            
        # Check if this item is used as a component in other BOMs (intermediate product)
        # If it's used in multiple BOMs or in complex assemblies, prefer manufacturing
        bom_usage_count = db.session.query(BOMItem).filter_by(item_id=item_id).count()
        
        # If the item is used in multiple BOMs (common intermediate), prefer manufacturing
        if bom_usage_count > 1:
            return False
            
        # Check if the item's BOM has complex sub-components (nested BOM structure)
        item_bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
        if item_bom:
            # If this item has its own BOM and is used as a component in another BOM, 
            # it's an intermediate product that should be manufactured, not purchased
            return False
        
        # For items without BOMs (true raw materials), offer purchase alternative
        return True
    
    @staticmethod
    def _final_deduplication(suggestions: List[Dict]) -> List[Dict]:
        """
        Final deduplication step to eliminate exact duplicates
        """
        seen_combinations = {}
        deduplicated = []
        
        for suggestion in suggestions:
            # Create unique identifier for each suggestion
            item_name = suggestion.get('target_item_name', suggestion.get('target_item', 'Unknown'))
            suggestion_type = suggestion.get('type', 'unknown')
            
            # For manufacturing suggestions, also consider producible quantity
            if suggestion_type in ['partial_manufacturing_recommendation', 'manufacturing_recommendation']:
                producible_qty = suggestion.get('producible_quantity', 0)
                unique_key = f"{item_name}|{suggestion_type}|{producible_qty:.2f}"
            else:
                unique_key = f"{item_name}|{suggestion_type}"
            
            # Only add if we haven't seen this exact combination
            if unique_key not in seen_combinations:
                seen_combinations[unique_key] = True
                deduplicated.append(suggestion)
        
        return deduplicated
    
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
                                    'unit_cost': material.get('unit_price', 0)
                                }
                            
                            consolidated_materials[material_id]['total_shortage_qty'] += shortage_qty
                            consolidated_materials[material_id]['used_by_products'].append({
                                'product_name': suggestion.get('target_item_name', 'Unknown'),
                                'quantity_needed': shortage_qty
                            })
                            consolidated_materials[material_id]['estimated_cost'] += shortage_qty * material.get('unit_price', 0)
            
            # Also process material_shortages from material_procurement_recommendation suggestions
            if suggestion.get('type') == 'material_procurement_recommendation' and suggestion.get('material_shortages'):
                for material in suggestion['material_shortages']:
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
                                'unit_cost': material.get('unit_price', 0)
                            }
                        
                        consolidated_materials[material_id]['total_shortage_qty'] += shortage_qty
                        consolidated_materials[material_id]['used_by_products'].append({
                            'product_name': suggestion.get('target_item', 'Unknown'),
                            'quantity_needed': shortage_qty
                        })
                        consolidated_materials[material_id]['estimated_cost'] += shortage_qty * material.get('unit_price', 0)
        
        # Create consolidated purchase suggestions
        consolidated_suggestions = []
        
        for material_id, material_info in consolidated_materials.items():
            # Always create suggestions, but highlight when it's consolidated vs single product
            product_list = [f"{prod['product_name']} ({prod['quantity_needed']:.1f} {material_info['unit']})" 
                          for prod in material_info['used_by_products']]
            
            is_consolidated = len(material_info['used_by_products']) > 1
            
            if is_consolidated:
                # Create consolidated purchase suggestion for multiple products
                consolidated_suggestion = {
                    'type': 'consolidated_purchase_recommendation',
                    'priority': 'high',
                    'title': f'📦 Consolidated Purchase: {material_info["material_name"]} (Multiple Products)',
                    'description': f'Purchase {material_info["total_shortage_qty"]:.1f} {material_info["unit"]} of {material_info["material_name"]} needed by {len(material_info["used_by_products"])} different products in one consolidated order (Alternative to individual purchases below)',
                    'action_steps': [
                        f'🛒 Create consolidated Purchase Order for {material_info["total_shortage_qty"]:.1f} {material_info["unit"]} of {material_info["material_name"]}',
                        f'💡 This material supports {len(material_info["used_by_products"])} different production items',
                        'Material breakdown by product:',
                        *[f'  • {prod_desc}' for prod_desc in product_list],
                        '💰 Contact supplier for bulk pricing discount (consolidated order)',
                        '⏱️ Schedule delivery to support all manufacturing timelines',
                        f'✅ Single purchase eliminates {len(material_info["used_by_products"]) - 1} separate purchase orders'
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
                        'unit_cost': material_info.get('unit_cost', 0),
                        'consolidated': True,
                        'used_by': material_info['used_by_products'],
                        'po_status': SmartBOMSuggestionService._get_po_status_info(Item.query.get(material_id)) if Item.query.get(material_id) else {'has_active_pos': False, 'total_pending': 0, 'active_pos': []},
                        'total_allocated_qty': material_info.get('total_allocated_qty', 0),  # Total allocated across all products
                        'is_shared_material': True  # Mark as shared for proper calculation
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
        
        # Filter out individual manufacturing suggestions that have been consolidated
        filtered_manufacturing_suggestions = []
        consolidated_material_ids = set(consolidated_materials.keys())
        
        for suggestion in manufacturing_suggestions:
            if suggestion.get('type') == 'material_procurement_recommendation':
                # Check if this procurement suggestion has materials that are consolidated
                has_consolidated_materials = False
                if suggestion.get('material_shortages'):
                    for material in suggestion['material_shortages']:
                        if material['material_id'] in consolidated_material_ids:
                            has_consolidated_materials = True
                            break
                
                # Only keep procurement suggestions that don't have consolidated materials
                if not has_consolidated_materials:
                    filtered_manufacturing_suggestions.append(suggestion)
            else:
                # Keep all other types of manufacturing suggestions
                filtered_manufacturing_suggestions.append(suggestion)
        
        # Add remaining non-consolidated purchase suggestions
        remaining_purchase_suggestions = []
        
        for suggestion in purchase_suggestions:
            item_details = suggestion.get('item_details', {})
            if item_details.get('item_id') not in consolidated_material_ids:
                remaining_purchase_suggestions.append(suggestion)
        
        return consolidated_suggestions + filtered_manufacturing_suggestions + remaining_purchase_suggestions