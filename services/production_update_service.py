from models import db
from models.job_card import JobCard, JobCardDailyStatus
from models.production import Production, ProductionBatch
from models.batch import InventoryBatch
from datetime import datetime, date
import logging

class ProductionUpdateService:
    """
    Service to automatically update production orders when outsourced job cards are received
    Handles quantity updates, status changes, and batch tracking
    """
    
    @staticmethod
    def update_production_on_job_card_receipt(job_card_id, received_quantities):
        """
        Update production order when an outsourced job card is received back
        
        Args:
            job_card_id: ID of the job card being received
            received_quantities: Dict with 'good', 'defective', 'scrap' quantities
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                raise ValueError(f"Job card {job_card_id} not found")
            
            production = job_card.production
            if not production:
                raise ValueError(f"No production order linked to job card {job_card.job_card_number}")
            
            # Update job card quantities
            job_card.completed_quantity += received_quantities.get('total', 0)
            job_card.good_quantity += received_quantities.get('good', 0)
            job_card.defective_quantity += received_quantities.get('defective', 0)
            job_card.scrap_quantity += received_quantities.get('scrap', 0)
            
            # Update job card status
            if job_card.completed_quantity >= job_card.planned_quantity:
                job_card.status = 'completed'
                job_card.actual_end_date = date.today()
            else:
                job_card.status = 'partially_completed'
            
            # Update production order quantities
            ProductionUpdateService._update_production_quantities(production, received_quantities)
            
            # Update production status based on all job cards
            ProductionUpdateService._update_production_status(production)
            
            # Create inventory batches for received items
            ProductionUpdateService._create_production_batches(job_card, received_quantities)
            
            # Log the update
            logging.info(f"Production {production.production_number} updated from job card {job_card.job_card_number} receipt")
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating production on job card receipt: {e}")
            raise e
    
    @staticmethod
    def _update_production_quantities(production, received_quantities):
        """Update production order quantities"""
        production.completed_quantity += received_quantities.get('total', 0)
        production.good_quantity += received_quantities.get('good', 0)
        production.defective_quantity += received_quantities.get('defective', 0)
        production.scrap_quantity += received_quantities.get('scrap', 0)
        
        # Update progress percentage
        if production.planned_quantity > 0:
            production.progress_percentage = min(
                (production.completed_quantity / production.planned_quantity) * 100, 
                100
            )
    
    @staticmethod
    def _update_production_status(production):
        """Update production status based on all associated job cards"""
        job_cards = JobCard.query.filter_by(production_id=production.id).all()
        
        if not job_cards:
            return
        
        total_planned = sum(jc.planned_quantity for jc in job_cards)
        total_completed = sum(jc.completed_quantity for jc in job_cards)
        
        # Calculate overall completion percentage
        if total_planned > 0:
            completion_percentage = (total_completed / total_planned) * 100
            
            if completion_percentage >= 100:
                production.status = 'completed'
                production.completed_date = date.today()
            elif completion_percentage > 0:
                production.status = 'in_progress'
            else:
                production.status = 'planned'
        
        # Check if all job cards are completed
        all_completed = all(jc.status == 'completed' for jc in job_cards)
        if all_completed:
            production.status = 'completed'
            production.completed_date = date.today()
    
    @staticmethod
    def _create_production_batches(job_card, received_quantities):
        """Create production batches for received quantities"""
        if received_quantities.get('good', 0) > 0:
            # Create good quantity batch
            batch_code = f"PROD-{job_card.job_card_number}-{date.today().strftime('%Y%m%d')}"
            
            # Check if batch already exists
            existing_batch = InventoryBatch.query.filter_by(
                item_id=job_card.item_id,
                batch_code=batch_code
            ).first()
            
            if not existing_batch:
                batch = InventoryBatch(
                    item_id=job_card.item_id,
                    batch_code=batch_code,
                    qty_finished=received_quantities['good'],
                    uom=job_card.item.base_uom if job_card.item else 'PCS',
                    location='Production Floor',
                    mfg_date=date.today(),
                    source_type='production',
                    source_ref_id=job_card.production_id
                )
                db.session.add(batch)
            else:
                existing_batch.qty_finished += received_quantities['good']
        
        # Create scrap batch if needed
        if received_quantities.get('scrap', 0) > 0:
            scrap_batch_code = f"SCRAP-{job_card.job_card_number}-{date.today().strftime('%Y%m%d')}"
            scrap_batch = InventoryBatch(
                item_id=job_card.item_id,
                batch_code=scrap_batch_code,
                qty_scrap=received_quantities['scrap'],
                uom=job_card.item.base_uom if job_card.item else 'PCS',
                location='Scrap Yard',
                mfg_date=date.today(),
                source_type='production',
                source_ref_id=job_card.production_id
            )
            db.session.add(scrap_batch)
    
    @staticmethod
    def auto_update_on_grn_receipt(grn_id):
        """
        Automatically update production when GRN is created for outsourced job card
        This is called from the GRN workflow
        """
        try:
            from models.grn import GRN, GRNLineItem
            
            grn = GRN.query.get(grn_id)
            if not grn:
                return False
            
            # Find associated job cards through GRN line items
            for line_item in grn.line_items:
                # Check if this line item is from a job card
                job_card_daily_status = JobCardDailyStatus.query.filter_by(grn_id=grn_id).first()
                if job_card_daily_status:
                    received_quantities = {
                        'total': line_item.received_quantity,
                        'good': line_item.accepted_quantity,
                        'defective': line_item.rejected_quantity,
                        'scrap': line_item.rejected_quantity  # Assuming rejected = scrap for now
                    }
                    
                    ProductionUpdateService.update_production_on_job_card_receipt(
                        job_card_daily_status.job_card_id,
                        received_quantities
                    )
            
            return True
            
        except Exception as e:
            logging.error(f"Error in auto_update_on_grn_receipt: {e}")
            return False
    
    @staticmethod
    def get_production_completion_summary(production_id):
        """Get completion summary for a production order including job card details"""
        production = Production.query.get(production_id)
        if not production:
            return None
        
        job_cards = JobCard.query.filter_by(production_id=production_id).all()
        
        summary = {
            'production_number': production.production_number,
            'total_planned': production.planned_quantity,
            'total_completed': production.completed_quantity,
            'total_good': production.good_quantity,
            'total_defective': production.defective_quantity,
            'total_scrap': production.scrap_quantity,
            'completion_percentage': production.progress_percentage,
            'status': production.status,
            'job_cards': []
        }
        
        for jc in job_cards:
            jc_summary = {
                'job_card_number': jc.job_card_number,
                'process_name': jc.process_name,
                'job_type': jc.job_type,
                'planned_quantity': jc.planned_quantity,
                'completed_quantity': jc.completed_quantity,
                'good_quantity': jc.good_quantity,
                'status': jc.status,
                'assigned_vendor': jc.assigned_vendor.name if jc.assigned_vendor else None,
                'outsourced': jc.job_type == 'outsourced'
            }
            summary['job_cards'].append(jc_summary)
        
        return summary