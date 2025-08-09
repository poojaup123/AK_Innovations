"""
Job Card Generator Service

This service handles the automatic generation of job cards from production orders
based on BOM explosion and process routing.
"""

from datetime import datetime, timedelta
from app import db
from models import Item, Production, BOM, BOMItem
from models.job_card import JobCard
from sqlalchemy import and_
import json

class JobCardGenerator:
    """Service for generating job cards from production orders"""
    
    def __init__(self):
        self.generated_cards = []
        self.card_counter = 1
    
    def generate_job_cards_from_production(self, production_id):
        """
        Main method to generate job cards from a production order
        
        Args:
            production_id: ID of the production order
            
        Returns:
            List of generated job cards
        """
        try:
            production = Production.query.get(production_id)
            if not production:
                raise ValueError(f"Production order {production_id} not found")
            
            # Clear any existing job cards for this production
            self._clear_existing_job_cards(production_id)
            
            # Get the main BOM for the production item
            main_bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
            if not main_bom:
                # Create a simple job card for items without BOM
                return self._create_simple_job_card(production)
            
            # Explode BOM and generate job cards
            self.generated_cards = []
            self.card_counter = 1
            
            # Generate job cards for each BOM level
            self._explode_bom_and_create_job_cards(
                production=production,
                bom=main_bom,
                level=1,
                parent_quantity=production.quantity_planned,
                parent_job_card=None
            )
            
            # Commit all changes
            db.session.commit()
            
            return self.generated_cards
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def _clear_existing_job_cards(self, production_id):
        """Clear any existing job cards for the production order"""
        existing_cards = JobCard.query.filter_by(production_id=production_id).all()
        for card in existing_cards:
            db.session.delete(card)
    
    def _create_simple_job_card(self, production):
        """Create a simple job card for items without BOM"""
        job_card_number = self._generate_job_card_number(production)
        
        job_card = JobCard()
        job_card.job_card_number = job_card_number
        job_card.production_id = production.id
        job_card.item_id = production.item_id
        job_card.process_name = "Assembly/Manufacturing"
        job_card.process_sequence = 1
        job_card.planned_quantity = production.quantity_planned
        job_card.planned_start_date = production.start_date if hasattr(production, 'start_date') and production.start_date else production.created_at.date()
        job_card.target_completion_date = production.target_date if hasattr(production, 'target_date') and production.target_date else production.created_at.date()
        job_card.job_type = 'in_house'
        job_card.status = 'planned'
        job_card.component_level = 1
        job_card.operation_description = f"Complete manufacturing of {production.item.name}"
        job_card.process_routing = json.dumps([{
            "step": 1,
            "process": "Manufacturing", 
            "description": "Complete item manufacturing",
            "estimated_time": 480  # 8 hours default
        }])
        
        db.session.add(job_card)
        self.generated_cards.append(job_card)
        return [job_card]
    
    def _explode_bom_and_create_job_cards(self, production, bom, level, parent_quantity, parent_job_card):
        """
        Recursively explode BOM and create job cards for each component
        
        Args:
            production: Production order
            bom: Current BOM being processed
            level: Current BOM level (1 = top level)
            parent_quantity: Quantity needed from parent
            parent_job_card: Parent job card reference
        """
        
        # Get all BOM items for this BOM
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).order_by(BOMItem.id).all()
        
        for bom_item in bom_items:
            # Calculate required quantity
            quantity_per_unit = getattr(bom_item, 'qty_required', getattr(bom_item, 'quantity_required', 1.0))
            required_quantity = quantity_per_unit * parent_quantity
            
            # Determine if this is a purchased item or manufactured item
            item_id = getattr(bom_item, 'material_id', getattr(bom_item, 'item_id', None))
            child_bom = BOM.query.filter_by(product_id=item_id, is_active=True).first() if item_id else None
            
            if child_bom:
                # This item has its own BOM - create job card and recurse
                job_card = self._create_job_card_for_bom_item(
                    production=production,
                    bom_item=bom_item,
                    required_quantity=required_quantity,
                    level=level,
                    parent_job_card=parent_job_card
                )
                
                # Recurse into child BOM
                self._explode_bom_and_create_job_cards(
                    production=production,
                    bom=child_bom,
                    level=level + 1,
                    parent_quantity=required_quantity,
                    parent_job_card=job_card
                )
            else:
                # This is a raw material or purchased component
                # Check if it needs processing (based on item type or custom logic)
                material = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
                if self._item_needs_processing(material):
                    job_card = self._create_job_card_for_bom_item(
                        production=production,
                        bom_item=bom_item,
                        required_quantity=required_quantity,
                        level=level,
                        parent_job_card=parent_job_card
                    )
    
    def _create_job_card_for_bom_item(self, production, bom_item, required_quantity, level, parent_job_card):
        """Create a job card for a specific BOM item"""
        
        job_card_number = self._generate_job_card_number(production)
        
        # Determine job type based on item or BOM item settings
        job_type = self._determine_job_type(bom_item)
        
        # Generate process routing based on item type and requirements
        process_routing = self._generate_process_routing(bom_item, job_type)
        
        # Calculate dates based on level and dependencies
        start_date, end_date = self._calculate_job_dates(production, level, job_type)
        
        job_card = JobCard()
        job_card.job_card_number = job_card_number
        job_card.production_id = production.id
        job_card.item_id = getattr(bom_item, 'material_id', getattr(bom_item, 'item_id', None))
        job_card.bom_item_id = bom_item.id
        job_card.component_level = level
        job_card.parent_job_card_id = parent_job_card.id if parent_job_card else None
        job_card.process_name = self._get_primary_process_name(bom_item)
        job_card.process_sequence = 1  # Use sequential numbering
        job_card.planned_quantity = required_quantity
        job_card.planned_start_date = start_date if start_date else production.created_at.date()
        job_card.planned_end_date = end_date
        job_card.target_completion_date = end_date if end_date else production.created_at.date()
        job_card.job_type = job_type
        job_card.status = 'planned'
        material = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
        material_name = material.name if material else "Unknown Material"
        job_card.operation_description = f"Process {material_name} for {production.item.name}"
        job_card.process_routing = json.dumps(process_routing)
        job_card.special_instructions = getattr(bom_item, 'notes', "") or getattr(bom_item, 'remarks', "") or ""
        job_card.estimated_cost = self._estimate_job_cost(bom_item, required_quantity)
        job_card.department = self._determine_department(bom_item, job_type)
        
        db.session.add(job_card)
        self.generated_cards.append(job_card)
        self.card_counter += 1
        
        return job_card
    
    def _generate_job_card_number(self, production):
        """Generate unique job card number"""
        base_number = production.production_number.replace("PROD-", "JC-")
        return f"{base_number}-{self.card_counter:03d}"
    
    def _determine_job_type(self, bom_item):
        """Determine if job should be in-house or outsourced"""
        # Check if item has specific outsourcing requirements
        # This could be based on item type, supplier preferences, or BOM notes
        
        if bom_item.notes and 'outsource' in bom_item.notes.lower():
            return 'outsourced'
        
        # Check item category or type
        if bom_item.item.category and 'outsourced' in bom_item.item.category.lower():
            return 'outsourced'
        
        # Default to in-house
        return 'in_house'
    
    def _generate_process_routing(self, bom_item, job_type):
        """Generate process routing steps based on item and job type"""
        
        if job_type == 'outsourced':
            return [
                {
                    "step": 1,
                    "process": "Material Issue",
                    "description": "Issue raw materials to vendor",
                    "estimated_time": 30
                },
                {
                    "step": 2,
                    "process": "Gate Pass",
                    "description": "Create gate pass for material dispatch",
                    "estimated_time": 15
                },
                {
                    "step": 3,
                    "process": "Vendor Processing",
                    "description": f"Vendor processing of {bom_item.item.name}",
                    "estimated_time": 2880  # 2 days default
                },
                {
                    "step": 4,
                    "process": "GRN",
                    "description": "Goods receipt and quality check",
                    "estimated_time": 60
                }
            ]
        
        # In-house processing routing
        item_type = bom_item.item.item_type or 'manufactured'
        
        if 'sheet' in item_type.lower() or 'plate' in bom_item.item.name.lower():
            return [
                {
                    "step": 1,
                    "process": "Cutting",
                    "description": "Cut material to required size",
                    "estimated_time": 120
                },
                {
                    "step": 2,
                    "process": "Machining",
                    "description": "Machine to specifications",
                    "estimated_time": 240
                },
                {
                    "step": 3,
                    "process": "Finishing",
                    "description": "Final finishing operations",
                    "estimated_time": 60
                }
            ]
        
        # Default manufacturing process
        return [
            {
                "step": 1,
                "process": "Setup",
                "description": "Setup machine and tools",
                "estimated_time": 60
            },
            {
                "step": 2,
                "process": "Manufacturing", 
                "description": f"Manufacture component",
                "estimated_time": 240
            },
            {
                "step": 3,
                "process": "Quality Check",
                "description": "Quality inspection and approval",
                "estimated_time": 30
            }
        ]
    
    def _calculate_job_dates(self, production, level, job_type):
        """Calculate start and end dates for job card based on level and type"""
        
        # Base dates from production order
        production_start = getattr(production, 'start_date', None) or production.created_at.date()
        production_end = getattr(production, 'target_date', None) or (production.created_at + timedelta(days=7)).date()
        
        # Calculate backwards from production end date based on level
        if job_type == 'outsourced':
            # Outsourced jobs need more lead time
            lead_time_days = 3 + (level * 2)  # More time for higher levels
        else:
            # In-house jobs
            lead_time_days = 1 + level
        
        end_date = production_end - timedelta(days=level - 1)
        start_date = end_date - timedelta(days=lead_time_days)
        
        # Ensure start date is not before production start
        if start_date < production_start:
            start_date = production_start
        
        return start_date, end_date
    
    def _get_primary_process_name(self, bom_item):
        """Get the primary process name for the BOM item"""
        material = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
        item_name = material.name.lower() if material else "unknown"
        
        if 'plate' in item_name or 'sheet' in item_name:
            return "Cutting & Machining"
        elif 'assembly' in item_name:
            return "Assembly"
        elif 'weld' in item_name:
            return "Welding"
        else:
            return "Manufacturing"
    
    def _item_needs_processing(self, item):
        """Determine if a raw material item needs processing"""
        # Items that typically need processing even if they don't have BOMs
        processing_keywords = ['sheet', 'plate', 'bar', 'rod', 'tube', 'pipe']
        
        item_name = item.name.lower()
        return any(keyword in item_name for keyword in processing_keywords)
    
    def _estimate_job_cost(self, bom_item, quantity):
        """Estimate cost for the job card"""
        # Basic cost estimation - can be enhanced with more sophisticated logic
        material = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
        base_cost = getattr(material, 'unit_price', 0) or 0 if material else 0
        return base_cost * quantity * 1.2  # Add 20% for processing overhead
    
    def _determine_department(self, bom_item, job_type):
        """Determine the department for the job card"""
        if job_type == 'outsourced':
            return "Outsourcing"
        
        material = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
        item_name = material.name.lower() if material else "unknown"
        
        if 'weld' in item_name:
            return "Welding"
        elif 'machine' in item_name or 'cut' in item_name:
            return "Machining"
        elif 'assembly' in item_name:
            return "Assembly"
        else:
            return "Production"

# Helper function to generate job cards
def generate_job_cards_for_production(production_id):
    """
    Convenience function to generate job cards for a production order
    
    Args:
        production_id: ID of the production order
        
    Returns:
        List of generated job cards
    """
    generator = JobCardGenerator()
    return generator.generate_job_cards_from_production(production_id)