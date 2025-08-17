"""
Batch Integration Service
Provides integration hooks for batch tracking across different modules
"""

from datetime import datetime, date
from flask import current_app
from typing import Dict, List, Optional, Tuple

from models import db, Item, User
from models.batch import InventoryBatch, BatchMovement, JobWorkBatch, BatchTraceability
from models.job_card import JobCard
from services.unified_batch_tracking import UnifiedBatchTrackingService


class BatchIntegrationService:
    """
    Service for integrating batch tracking with various business processes
    """
    
    @staticmethod
    def integrate_job_card_with_batches(job_card_id: int, material_allocations: List[Dict]) -> bool:
        """
        Integrate job card with batch tracking
        Allocates specific batches to job card materials
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                return False
            
            for allocation in material_allocations:
                item_id = allocation['item_id']
                required_qty = allocation['required_qty']
                
                # Get batch allocations using FIFO
                batch_allocations = UnifiedBatchTrackingService.allocate_batch_for_production(
                    item_id, required_qty, fifo=True
                )
                
                if not batch_allocations:
                    current_app.logger.warning(f"No batches available for item {item_id} in job card {job_card_id}")
                    continue
                
                # For now, we'll store batch allocation info in job card notes
                # Future enhancement: Create JobCardMaterial model for detailed tracking
                for batch_allocation in batch_allocations:
                    # Record allocation in job card notes for now
                    if not hasattr(job_card, 'batch_allocations'):
                        job_card.notes = job_card.notes or ''
                        allocation_note = f"Batch {batch_allocation['batch_code']}: {batch_allocation['allocated_qty']} units allocated"
                        if allocation_note not in job_card.notes:
                            job_card.notes += f"\n{allocation_note}"
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error integrating job card with batches: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def consume_batches_for_job_card(job_card_id: int, consumption_data: List[Dict]) -> bool:
        """
        Consume batches when job card processes start
        Moves batch quantities from raw/finished to WIP
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                return False
            
            for consumption in consumption_data:
                batch_id = consumption['batch_id']
                consumed_qty = consumption['consumed_qty']
                process_name = consumption.get('process_name', 'General')
                
                # Get the batch
                batch = InventoryBatch.query.get(batch_id)
                if not batch:
                    continue
                
                # Check available quantity
                available_qty = (batch.qty_raw or 0) + (batch.qty_finished or 0)
                if consumed_qty > available_qty:
                    current_app.logger.warning(f"Insufficient quantity in batch {batch.batch_code}")
                    continue
                
                # Move quantities to WIP
                consumed_from_raw = min(consumed_qty, batch.qty_raw or 0)
                consumed_from_finished = consumed_qty - consumed_from_raw
                
                if consumed_from_raw > 0:
                    batch.qty_raw -= consumed_from_raw
                    batch.qty_wip += consumed_from_raw
                    
                    UnifiedBatchTrackingService.record_movement(
                        batch_id=batch_id,
                        quantity=consumed_from_raw,
                        from_state='raw',
                        to_state='wip',
                        movement_type='job_card_issue',
                        ref_type='job_card',
                        ref_id=job_card_id,
                        notes=f"Issued for job card {job_card.job_card_number} - Process: {process_name}",
                        user_id=job_card.assigned_worker_id
                    )
                
                if consumed_from_finished > 0:
                    batch.qty_finished -= consumed_from_finished
                    batch.qty_wip += consumed_from_finished
                    
                    UnifiedBatchTrackingService.record_movement(
                        batch_id=batch_id,
                        quantity=consumed_from_finished,
                        from_state='finished',
                        to_state='wip',
                        movement_type='job_card_issue',
                        ref_type='job_card',
                        ref_id=job_card_id,
                        notes=f"Issued for job card {job_card.job_card_number} - Process: {process_name}",
                        user_id=job_card.assigned_worker_id
                    )
                
                # Update job card notes with consumption info
                consumption_note = f"Consumed {consumed_qty} from batch {batch.batch_code} for {process_name}"
                if not job_card.notes:
                    job_card.notes = consumption_note
                elif consumption_note not in job_card.notes:
                    job_card.notes += f"\n{consumption_note}"
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error consuming batches for job card: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def complete_job_card_with_output_batch(job_card_id: int, output_data: Dict) -> Optional[InventoryBatch]:
        """
        Complete job card and create output batch
        Links input batches to output batch for traceability
        """
        try:
            job_card = JobCard.query.get(job_card_id)
            if not job_card:
                return None
            
            output_item_id = output_data['item_id']
            produced_qty = output_data['produced_qty']
            scrap_qty = output_data.get('scrap_qty', 0)
            
            # For now, get input batch information from a simple approach
            # Future enhancement: Use JobCardMaterial relationships
            input_batch_ids = []
            
            # Try to extract batch IDs from job card notes (temporary solution)
            if job_card.notes:
                import re
                batch_matches = re.findall(r'batch (\d+)', job_card.notes.lower())
                input_batch_ids = [int(bid) for bid in batch_matches if bid.isdigit()]
            
            # Create output batch
            output_batch = UnifiedBatchTrackingService.create_production_output_batch(
                item_id=output_item_id,
                produced_qty=produced_qty,
                production_ref_id=job_card_id,
                input_batches=input_batch_ids,
                user_id=job_card.assigned_worker_id
            )
            
            # Handle scrap if any
            if scrap_qty > 0:
                # Find a suitable input batch to assign scrap to
                if input_batch_ids:
                    scrap_batch = InventoryBatch.query.get(input_batch_ids[0])
                    if scrap_batch:
                        scrap_batch.qty_wip -= scrap_qty
                        scrap_batch.qty_scrap += scrap_qty
                        
                        UnifiedBatchTrackingService.record_movement(
                            batch_id=scrap_batch.id,
                            quantity=scrap_qty,
                            from_state='wip',
                            to_state='scrap',
                            movement_type='production_scrap',
                            ref_type='job_card',
                            ref_id=job_card_id,
                            notes=f"Scrap from job card {job_card.job_card_number}",
                            user_id=job_card.assigned_worker_id
                        )
            
            # Update job card status
            job_card.status = 'completed'
            job_card.actual_completion_date = date.today()
            job_card.output_batch_id = output_batch.id
            
            db.session.commit()
            return output_batch
            
        except Exception as e:
            current_app.logger.error(f"Error completing job card with output batch: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def dispatch_batch_for_sales(batch_id: int, dispatch_qty: float, sales_order_id: int, user_id: int = None) -> bool:
        """
        Dispatch batch quantities for sales orders
        Moves from finished goods to dispatched state
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return False
            
            # Check available finished goods quantity
            if (batch.qty_finished or 0) < dispatch_qty:
                current_app.logger.warning(f"Insufficient finished goods in batch {batch.batch_code}")
                return False
            
            # Move from finished to dispatched (represented as quantity reduction)
            batch.qty_finished -= dispatch_qty
            
            # Record dispatch movement
            UnifiedBatchTrackingService.record_movement(
                batch_id=batch_id,
                quantity=dispatch_qty,
                from_state='finished',
                to_state=None,  # Dispatched/sold
                movement_type='sales_dispatch',
                ref_type='sales_order',
                ref_id=sales_order_id,
                notes=f"Dispatched for sales order SO-{sales_order_id}",
                user_id=user_id
            )
            
            # Update item's current stock
            if hasattr(batch.item, 'sync_stock'):
                batch.item.sync_stock()
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error dispatching batch: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_batch_availability_for_item(item_id: int) -> Dict:
        """
        Get comprehensive batch availability information for an item
        Returns FIFO-ordered batches with all states
        """
        try:
            batches = UnifiedBatchTrackingService.get_available_batches_for_item(item_id, 'all')
            
            # Group by state and calculate totals
            totals = {
                'total_raw': 0,
                'total_wip': 0,
                'total_finished': 0,
                'total_scrap': 0,
                'total_inspection': 0,
                'available_for_production': 0,
                'available_for_dispatch': 0,
                'batch_count': len(batches)
            }
            
            for batch_info in batches:
                totals['total_raw'] += batch_info['qty_raw']
                totals['total_wip'] += batch_info['qty_wip']
                totals['total_finished'] += batch_info['qty_finished']
                totals['total_scrap'] += batch_info['qty_scrap']
                totals['available_for_production'] += batch_info['qty_raw'] + batch_info['qty_finished']
                totals['available_for_dispatch'] += batch_info['qty_finished']
            
            return {
                'batches': batches,
                'totals': totals,
                'fifo_order': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting batch availability: {e}")
            return {'batches': [], 'totals': {}, 'fifo_order': False}
    
    @staticmethod
    def transfer_batch_between_locations(batch_id: int, from_location: str, to_location: str, 
                                       transfer_qty: float = None, user_id: int = None) -> bool:
        """
        Transfer batch between storage locations
        Maintains state but updates location tracking
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return False
            
            if transfer_qty is None:
                transfer_qty = batch.total_quantity
            
            if transfer_qty > batch.total_quantity:
                current_app.logger.warning(f"Transfer quantity exceeds available quantity in batch {batch.batch_code}")
                return False
            
            # Update location
            old_location = batch.location
            batch.location = to_location
            
            # Record location transfer
            UnifiedBatchTrackingService.record_movement(
                batch_id=batch_id,
                quantity=transfer_qty,
                from_state=f"stored@{from_location}",
                to_state=f"stored@{to_location}",
                movement_type='location_transfer',
                ref_type='inventory_management',
                notes=f"Transferred from {from_location} to {to_location}",
                user_id=user_id
            )
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error transferring batch location: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def generate_batch_consumption_report(date_from: date, date_to: date) -> Dict:
        """
        Generate comprehensive batch consumption report
        Shows efficiency metrics and traceability
        """
        try:
            # Get all batch movements in date range
            movements = BatchMovement.query.filter(
                BatchMovement.timestamp >= datetime.combine(date_from, datetime.min.time()),
                BatchMovement.timestamp <= datetime.combine(date_to, datetime.max.time())
            ).all()
            
            # Group by movement type
            movement_summary = {}
            total_quantity_moved = 0
            
            for movement in movements:
                movement_type = movement.movement_type
                if movement_type not in movement_summary:
                    movement_summary[movement_type] = {
                        'count': 0,
                        'total_quantity': 0,
                        'items': set()
                    }
                
                movement_summary[movement_type]['count'] += 1
                movement_summary[movement_type]['total_quantity'] += movement.quantity
                movement_summary[movement_type]['items'].add(movement.item.name if movement.item else 'Unknown')
                total_quantity_moved += movement.quantity
            
            # Convert sets to lists for JSON serialization
            for summary in movement_summary.values():
                summary['items'] = list(summary['items'])
            
            # Calculate efficiency metrics
            production_receipts = sum(
                summary['total_quantity'] for key, summary in movement_summary.items()
                if 'production_receipt' in key
            )
            
            production_issues = sum(
                summary['total_quantity'] for key, summary in movement_summary.items()
                if 'production_issue' in key or 'job_card_issue' in key
            )
            
            production_efficiency = (production_receipts / production_issues * 100) if production_issues > 0 else 0
            
            return {
                'date_range': {'from': date_from, 'to': date_to},
                'movement_summary': movement_summary,
                'total_movements': len(movements),
                'total_quantity_moved': total_quantity_moved,
                'production_efficiency': round(production_efficiency, 2),
                'top_movement_types': sorted(
                    movement_summary.items(), 
                    key=lambda x: x[1]['total_quantity'], 
                    reverse=True
                )[:5]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating batch consumption report: {e}")
            return {}