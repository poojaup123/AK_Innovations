from models import db, Item, JobCard, Production
from models.batch import InventoryBatch
from services.accounting_automation import AccountingAutomation
from datetime import datetime, date
import logging

class BOMInventoryFlow:
    """
    Service for managing BOM-driven inventory flow in nested manufacturing structure
    
    Key Logic:
    - Sub-Assembly BOMs (Mounting/Base Plates) → Finished Components inventory
    - Master BOM (Castor Assembly) → Finished Products inventory
    - Intermediate processes → WIP inventory updates
    - Final process completion → Triggers finished goods
    """
    
    @staticmethod
    def update_inventory_on_job_card_completion(job_card_id: int, completed_quantity: float = None):
        """
        Update inventory when a job card (process) is completed
        Handles both in-house completion and outsourced GRN receipt
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Use completed quantity or default to planned quantity
            quantity = completed_quantity or job_card.completed_quantity or job_card.planned_quantity
            if quantity <= 0:
                return False, "No quantity to process"
            
            # Get production order and BOM information
            production = job_card.production
            if not production:
                return False, "Production order not found"
            
            # Determine if this is a sub-assembly or master BOM
            bom_level = BOMInventoryFlow._determine_bom_level(job_card)
            
            if bom_level == "sub_assembly":
                return BOMInventoryFlow._handle_sub_assembly_completion(
                    job_card, quantity, production
                )
            elif bom_level == "master_assembly": 
                return BOMInventoryFlow._handle_master_assembly_completion(
                    job_card, quantity, production
                )
            else:
                return BOMInventoryFlow._handle_intermediate_process(
                    job_card, quantity, production
                )
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating inventory for job card {job_card_id}: {str(e)}")
            return False, f"Error updating inventory: {str(e)}"
    
    @staticmethod
    def _determine_bom_level(job_card):
        """
        Determine if job card is part of sub-assembly, master assembly, or intermediate process
        
        Logic:
        - If item has its own BOM and is used in another BOM → sub_assembly
        - If item has BOM but isn't used in another BOM → master_assembly  
        - If item doesn't have BOM → intermediate_process
        """
        item = job_card.item
        if not item:
            return "intermediate_process"
        
        # Check if item has its own BOM (indicates it's an assembly)
        from models import db
        has_own_bom = db.session.execute(
            db.text("SELECT COUNT(*) FROM boms WHERE product_id = :item_id"),
            {"item_id": item.id}
        ).scalar() > 0
        
        if has_own_bom:
            # Check if this item is used as component in another BOM (sub-assembly)
            used_in_other_bom = db.session.execute(
                db.text("SELECT COUNT(*) FROM bom_items WHERE item_id = :item_id"),
                {"item_id": item.id}
            ).scalar() > 0
            
            if used_in_other_bom:
                return "sub_assembly"  # Has own BOM + used in other BOM
            else:
                return "master_assembly"  # Has own BOM but not used elsewhere
        else:
            return "intermediate_process"  # No BOM, just a process step
    
    @staticmethod
    def _handle_sub_assembly_completion(job_card, quantity, production):
        """
        Handle completion of sub-assembly (Mounting Plate, Base Plate)
        Updates inventory to 'Finished Components' state
        """
        try:
            item = job_card.item
            
            # Check if this is the final process for the sub-assembly
            is_final_process = BOMInventoryFlow._is_final_process_in_bom(job_card)
            
            if is_final_process:
                # Move from WIP to Finished Components inventory
                success = BOMInventoryFlow._move_inventory_state(
                    item_id=item.id,
                    from_state="wip",
                    to_state="finished",
                    quantity=quantity,
                    job_card=job_card,
                    notes=f"Sub-assembly {item.name} completed - Process: {job_card.process_name}"
                )
                
                if success:
                    # Update job card status
                    job_card.status = 'completed'
                    job_card.completed_quantity = quantity
                    job_card.actual_end_date = date.today()
                    
                    # Create accounting entry for finished component
                    AccountingAutomation.create_inventory_valuation_entry(
                        item=item,
                        quantity_change=quantity,
                        valuation_change=quantity * (item.unit_price or 0),
                        movement_type='production'
                    )
                    
                    db.session.commit()
                    return True, f"Sub-assembly {item.name} completed and moved to Finished Components"
                else:
                    return False, "Failed to update inventory state"
            else:
                # Intermediate process - update WIP state
                return BOMInventoryFlow._handle_intermediate_process(job_card, quantity, production)
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error handling sub-assembly completion: {str(e)}")
            return False, f"Error processing sub-assembly: {str(e)}"
    
    @staticmethod
    def _handle_master_assembly_completion(job_card, quantity, production):
        """
        Handle completion of master assembly (Castor Wheel)
        Updates inventory to 'Finished Products' state
        """
        try:
            item = job_card.item
            
            # Check if this is the final process for the master assembly
            is_final_process = BOMInventoryFlow._is_final_process_in_bom(job_card)
            
            if is_final_process:
                # Move to Finished Products inventory
                success = BOMInventoryFlow._move_inventory_state(
                    item_id=item.id,
                    from_state="wip",
                    to_state="finished", 
                    quantity=quantity,
                    job_card=job_card,
                    notes=f"Master assembly {item.name} completed - Process: {job_card.process_name}"
                )
                
                if success:
                    # Update job card and production order status
                    job_card.status = 'completed'
                    job_card.completed_quantity = quantity
                    job_card.actual_end_date = date.today()
                    
                    # Check if all job cards for this production are completed
                    all_completed = BOMInventoryFlow._check_production_completion(production.id)
                    if all_completed:
                        production.status = 'completed'
                        production.actual_end_date = date.today()
                    
                    # Create accounting entry for finished product
                    AccountingAutomation.create_inventory_valuation_entry(
                        item=item,
                        quantity_change=quantity,
                        valuation_change=quantity * (item.unit_price or 0),
                        movement_type='production'
                    )
                    
                    db.session.commit()
                    return True, f"Master assembly {item.name} completed and moved to Finished Products"
                else:
                    return False, "Failed to update inventory state"
            else:
                # Intermediate process in master assembly
                return BOMInventoryFlow._handle_intermediate_process(job_card, quantity, production)
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error handling master assembly completion: {str(e)}")
            return False, f"Error processing master assembly: {str(e)}"
    
    @staticmethod
    def _handle_intermediate_process(job_card, quantity, production):
        """
        Handle intermediate process completion
        Updates WIP inventory between process states
        """
        try:
            item = job_card.item
            process_name = job_card.process_name.lower()
            
            # Map process names to WIP columns
            wip_field_mapping = {
                'cutting': 'qty_wip_cutting',
                'blanking': 'qty_wip_cutting',  # Blanking is part of cutting
                'notching': 'qty_wip_cutting',  # Notching is part of cutting
                'bending': 'qty_wip_bending',
                'welding': 'qty_wip_welding',
                'zinc': 'qty_wip_zinc',
                'coating': 'qty_wip_zinc',  # Coating includes zinc
                'painting': 'qty_wip_painting',
                'assembly': 'qty_wip_assembly',
                'machining': 'qty_wip_machining',
                'polishing': 'qty_wip_polishing'
            }
            
            # Determine source and destination states
            current_wip_field = None
            next_wip_field = None
            
            for process_key, wip_field in wip_field_mapping.items():
                if process_key in process_name:
                    current_wip_field = wip_field
                    break
            
            if not current_wip_field:
                current_wip_field = 'qty_wip'  # Default WIP
            
            # Update WIP inventory
            success = BOMInventoryFlow._move_wip_inventory(
                item_id=item.id,
                from_wip_state=current_wip_field,
                quantity=quantity,
                job_card=job_card
            )
            
            if success:
                # Update job card status
                job_card.status = 'completed'
                job_card.completed_quantity = quantity
                job_card.actual_end_date = date.today()
                
                db.session.commit()
                return True, f"Process {job_card.process_name} completed, WIP inventory updated"
            else:
                return False, "Failed to update WIP inventory"
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error handling intermediate process: {str(e)}")
            return False, f"Error processing intermediate step: {str(e)}"
    
    @staticmethod
    def _is_final_process_in_bom(job_card):
        """
        Check if this job card represents the final process in its BOM
        """
        try:
            # Get all job cards for the same production and item
            production_job_cards = JobCard.query.filter_by(
                production_id=job_card.production_id,
                item_id=job_card.item_id
            ).order_by(JobCard.process_sequence.asc()).all()
            
            if not production_job_cards:
                return True  # Only job card, must be final
            
            # Check if this is the highest process sequence
            max_sequence = max(jc.process_sequence or 0 for jc in production_job_cards)
            return job_card.process_sequence == max_sequence
            
        except Exception:
            return True  # Default to final if can't determine
    
    @staticmethod
    def _move_inventory_state(item_id, from_state, to_state, quantity, job_card, notes=""):
        """
        Move inventory from one state to another
        """
        try:
            # Get or create inventory batch
            item = Item.query.get(item_id)
            if not item:
                return False
            
            # Find available batches for this item in the source state
            available_batches = InventoryBatch.query.filter_by(item_id=item_id).all()
            
            if not available_batches:
                # Create a new batch for this production
                batch_number = f"PROD-{job_card.production.production_number}-{item.code}"
                batch = InventoryBatch(
                    item_id=item_id,
                    batch_code=batch_number,
                    supplier_batch_no=batch_number,
                    mfg_date=date.today(),
                    qty_raw=0,
                    qty_finished=0 if to_state != 'finished' else quantity,
                    qty_scrap=0,
                    quality_status='good',
                    storage_location='PRODUCTION'
                )
                
                if to_state == 'finished':
                    batch.qty_finished = quantity
                elif from_state == 'wip':
                    # Moving from WIP to another state
                    setattr(batch, f'qty_{to_state}', quantity)
                
                db.session.add(batch)
            else:
                # Use existing batch and update quantities
                batch = available_batches[0]
                
                if to_state == 'finished':
                    batch.qty_finished = (batch.qty_finished or 0) + quantity
                elif to_state == 'wip':
                    batch.qty_wip = (batch.qty_wip or 0) + quantity
                
                if from_state == 'raw' and hasattr(batch, 'qty_raw'):
                    batch.qty_raw = max(0, (batch.qty_raw or 0) - quantity)
                elif from_state == 'wip' and hasattr(batch, 'qty_wip'):
                    batch.qty_wip = max(0, (batch.qty_wip or 0) - quantity)
            
            # Update item-level inventory totals
            if to_state == 'finished':
                item.qty_finished = (item.qty_finished or 0) + quantity
            elif to_state == 'wip':
                item.qty_wip = (item.qty_wip or 0) + quantity
            
            if from_state == 'raw':
                item.qty_raw = max(0, (item.qty_raw or 0) - quantity)
            elif from_state == 'wip':
                item.qty_wip = max(0, (item.qty_wip or 0) - quantity)
            
            return True
            
        except Exception as e:
            logging.error(f"Error moving inventory state: {str(e)}")
            return False
    
    @staticmethod
    def _move_wip_inventory(item_id, from_wip_state, quantity, job_card):
        """
        Move WIP inventory between different process states
        """
        try:
            item = Item.query.get(item_id)
            if not item:
                return False
            
            # Update the specific WIP field
            current_value = getattr(item, from_wip_state, 0) or 0
            setattr(item, from_wip_state, current_value + quantity)
            
            # Also update general WIP total
            item.qty_wip = (item.qty_wip or 0) + quantity
            
            return True
            
        except Exception as e:
            logging.error(f"Error moving WIP inventory: {str(e)}")
            return False
    
    @staticmethod
    def _check_production_completion(production_id):
        """
        Check if all job cards for a production order are completed
        """
        try:
            pending_job_cards = JobCard.query.filter_by(
                production_id=production_id
            ).filter(
                JobCard.status.notin_(['completed', 'cancelled'])
            ).count()
            
            return pending_job_cards == 0
            
        except Exception:
            return False
    
    @staticmethod
    def handle_outsourced_grn_receipt(job_card_id, grn_quantity):
        """
        Handle inventory updates when outsourced work is received via GRN
        This integrates with the existing GRN workflow
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Update job card with received quantity
            job_card.grn_received_quantity = grn_quantity
            job_card.grn_received_date = date.today()
            
            # Process inventory update using the same flow
            return BOMInventoryFlow.update_inventory_on_job_card_completion(
                job_card_id, grn_quantity
            )
            
        except Exception as e:
            logging.error(f"Error handling outsourced GRN receipt: {str(e)}")
            return False, f"Error processing GRN receipt: {str(e)}"