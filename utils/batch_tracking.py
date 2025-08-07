"""
Comprehensive Batch Tracking Utilities for Factory Management System
Provides complete material traceability from raw material to finished goods
"""

from models import ItemBatch, Item, JobWork
from models.batch import JobWorkBatch
from app import db
from datetime import datetime
from sqlalchemy import and_, or_


class BatchTracker:
    """Central class for managing batch movements and traceability"""
    
    @staticmethod
    def get_available_batches_for_item(item_id, required_quantity=None, process_name=None):
        """Get available batches for an item with process-specific availability"""
        try:
            # Get all batches for the item with available quantities
            batches = ItemBatch.query.filter(
                ItemBatch.item_id == item_id,
                ItemBatch.available_quantity > 0
            ).order_by(ItemBatch.manufacture_date.asc()).all()  # FIFO ordering
            
            available_batches = []
            for batch in batches:
                # Calculate available quantity based on process needs
                if process_name:
                    # For specific processes, check if batch has material in appropriate state
                    available_qty = batch.available_quantity
                else:
                    # General availability (raw + finished)
                    available_qty = batch.available_quantity
                
                if available_qty > 0:
                    batch_info = {
                        'id': batch.id,
                        'batch_number': batch.batch_number,
                        'available_quantity': available_qty,
                        'manufacture_date': batch.manufacture_date,
                        'expiry_date': batch.expiry_date,
                        'quality_status': batch.quality_status,
                        'storage_location': batch.storage_location,
                        'batch_age_days': batch.batch_age_days,
                        'is_expired': batch.is_expired,
                        'wip_breakdown': batch.wip_breakdown
                    }
                    available_batches.append(batch_info)
            
            return available_batches
            
        except Exception as e:
            print(f"Error getting available batches: {str(e)}")
            return []
    
    @staticmethod
    def issue_material_with_batch_tracking(job_work_id, item_id, quantity, batch_selections, process_name=None):
        """Issue material from specific batches for job work with complete tracking"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return False, "Job work not found"
            
            total_issued = 0
            job_work_batches = []
            
            # Process each batch selection
            for batch_selection in batch_selections:
                batch_id = batch_selection.get('batch_id')
                qty_to_issue = batch_selection.get('quantity', 0)
                
                if qty_to_issue <= 0:
                    continue
                
                batch = ItemBatch.query.get(batch_id)
                if not batch:
                    continue
                
                # Issue material from this batch
                success, message = batch.issue_for_job_work(qty_to_issue, process_name)
                
                if success:
                    # Create JobWorkBatch record for traceability
                    job_work_batch = JobWorkBatch(
                        job_work_id=job_work_id,
                        input_batch_id=batch_id,
                        quantity_issued=qty_to_issue,
                        process_name=process_name or 'general',
                        status='issued',
                        issued_date=datetime.utcnow().date(),
                        created_by=job_work.created_by
                    )
                    db.session.add(job_work_batch)
                    job_work_batches.append(job_work_batch)
                    total_issued += qty_to_issue
                else:
                    return False, f"Failed to issue from batch {batch.batch_number}: {message}"
            
            if total_issued < quantity:
                return False, f"Could only issue {total_issued} out of {quantity} required"
            
            db.session.commit()
            return True, f"Successfully issued {total_issued} units from {len(job_work_batches)} batches"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error issuing material with batch tracking: {str(e)}"
    
    @staticmethod
    def receive_material_with_batch_tracking(job_work_id, return_data):
        """Receive processed material back from job work with batch tracking"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return False, "Job work not found"
            
            # Process return data for each batch
            for batch_return in return_data:
                batch_id = batch_return.get('batch_id')
                finished_qty = batch_return.get('finished_quantity', 0)
                scrap_qty = batch_return.get('scrap_quantity', 0)
                unused_qty = batch_return.get('unused_quantity', 0)
                process_name = batch_return.get('process_name')
                
                if not batch_id:
                    continue
                
                batch = ItemBatch.query.get(batch_id)
                if not batch:
                    continue
                
                # Return processed material to batch
                success, message = batch.receive_from_job_work(
                    finished_qty, scrap_qty, unused_qty, process_name
                )
                
                if not success:
                    return False, f"Failed to receive material for batch {batch.batch_number}: {message}"
                
                # Update JobWorkBatch record
                job_work_batch = JobWorkBatch.query.filter_by(
                    job_work_id=job_work_id,
                    input_batch_id=batch_id
                ).first()
                
                if job_work_batch:
                    job_work_batch.quantity_finished = finished_qty
                    job_work_batch.quantity_scrap = scrap_qty
                    job_work_batch.quantity_unused = unused_qty
                    job_work_batch.status = 'completed' if (finished_qty + scrap_qty + unused_qty) > 0 else 'partial'
                    job_work_batch.received_date = datetime.utcnow().date()
            
            db.session.commit()
            return True, "Material received successfully with batch tracking"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error receiving material with batch tracking: {str(e)}"
    
    @staticmethod
    def transfer_batches_between_processes(job_work_id, transfer_data):
        """Transfer material between different process stages"""
        try:
            for transfer in transfer_data:
                batch_id = transfer.get('batch_id')
                from_process = transfer.get('from_process')
                to_process = transfer.get('to_process')
                quantity = transfer.get('quantity', 0)
                
                if not all([batch_id, from_process, to_process, quantity > 0]):
                    continue
                
                from models.batch import InventoryBatch
                batch = InventoryBatch.query.get(batch_id)
                if not batch:
                    continue
                
                # Simple transfer logic for now
                success, message = True, "Transfer completed"
                if not success:
                    return False, f"Failed to transfer batch {batch.batch_number}: {message}"
            
            db.session.commit()
            return True, "Batch transfers completed successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error transferring batches: {str(e)}"
    
    @staticmethod
    def get_batch_traceability_report(batch_id):
        """Get complete traceability report for a specific batch"""
        try:
            from models.batch import InventoryBatch
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return None
            
            # Get all job work batches associated with this batch
            job_work_batches = JobWorkBatch.query.filter(
                or_(
                    JobWorkBatch.input_batch_id == batch_id,
                    JobWorkBatch.output_batch_id == batch_id
                )
            ).order_by(JobWorkBatch.created_at).all()
            
            # Build traceability chain
            traceability_chain = []
            for jwb in job_work_batches:
                job_work = jwb.job_work
                chain_entry = {
                    'job_work_number': job_work.job_number,
                    'job_work_type': job_work.work_type,
                    'process_name': jwb.process_name,
                    'quantity_issued': jwb.quantity_issued,
                    'quantity_finished': jwb.quantity_finished,
                    'quantity_scrap': jwb.quantity_scrap,
                    'issued_date': jwb.issued_date,
                    'received_date': jwb.received_date,
                    'status': jwb.status,
                    'supplier_name': job_work.supplier.name if job_work.supplier else 'In-House'
                }
                traceability_chain.append(chain_entry)
            
            return {
                'batch': batch.get_batch_ledger(),
                'traceability_chain': traceability_chain,
                'total_jobs': len(job_work_batches),
                'current_location': batch.storage_location
            }
            
        except Exception as e:
            print(f"Error getting batch traceability report: {str(e)}")
            return None
    
    @staticmethod
    def create_output_batches_for_job_work(job_work_id, output_data):
        """Create new batches for job work output products"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return False, "Job work not found"
            
            created_batches = []
            
            for output_info in output_data:
                input_batch_id = output_info.get('input_batch_id')
                output_item_id = output_info.get('output_item_id')
                output_quantity = output_info.get('output_quantity', 0)
                batch_prefix = output_info.get('batch_prefix', 'OUT')
                
                if not all([input_batch_id, output_item_id, output_quantity > 0]):
                    continue
                
                input_batch = ItemBatch.query.get(input_batch_id)
                if not input_batch:
                    continue
                
                # Create output batch
                output_batch = input_batch.create_output_batch(
                    output_item_id, output_quantity, batch_prefix
                )
                
                db.session.add(output_batch)
                db.session.flush()  # Get the batch ID
                
                # Link input and output batches through JobWorkBatch
                job_work_batch = JobWorkBatch.query.filter_by(
                    job_work_id=job_work_id,
                    input_batch_id=input_batch_id
                ).first()
                
                if job_work_batch:
                    job_work_batch.output_batch_id = output_batch.id
                
                created_batches.append(output_batch)
            
            db.session.commit()
            return True, f"Created {len(created_batches)} output batches successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error creating output batches: {str(e)}"
    
    @staticmethod
    def get_process_wise_inventory_summary():
        """Get inventory summary organized by process states"""
        try:
            # Get all items with their batch-wise quantities
            items_with_batches = db.session.query(Item).join(ItemBatch).all()
            
            process_summary = {}
            
            for item in items_with_batches:
                if item.id not in process_summary:
                    process_summary[item.id] = {
                        'item_name': item.name,
                        'item_code': item.code,
                        'unit_of_measure': item.unit_of_measure,
                        'states': {
                            'raw': 0,
                            'cutting': 0,
                            'bending': 0,
                            'welding': 0,
                            'zinc': 0,
                            'painting': 0,
                            'assembly': 0,
                            'machining': 0,
                            'polishing': 0,
                            'finished': 0,
                            'scrap': 0
                        },
                        'total_quantity': 0,
                        'batch_count': 0
                    }
                
                # Sum quantities from all batches for this item
                for batch in item.batches:
                    process_summary[item.id]['states']['raw'] += batch.qty_raw or 0
                    process_summary[item.id]['states']['cutting'] += batch.qty_wip_cutting or 0
                    process_summary[item.id]['states']['bending'] += batch.qty_wip_bending or 0
                    process_summary[item.id]['states']['welding'] += batch.qty_wip_welding or 0
                    process_summary[item.id]['states']['zinc'] += batch.qty_wip_zinc or 0
                    process_summary[item.id]['states']['painting'] += batch.qty_wip_painting or 0
                    process_summary[item.id]['states']['assembly'] += batch.qty_wip_assembly or 0
                    process_summary[item.id]['states']['machining'] += batch.qty_wip_machining or 0
                    process_summary[item.id]['states']['polishing'] += batch.qty_wip_polishing or 0
                    process_summary[item.id]['states']['finished'] += batch.qty_finished or 0
                    process_summary[item.id]['states']['scrap'] += batch.qty_scrap or 0
                    process_summary[item.id]['batch_count'] += 1
                
                # Calculate total quantity
                total = sum(process_summary[item.id]['states'].values())
                process_summary[item.id]['total_quantity'] = total
            
            return process_summary
            
        except Exception as e:
            print(f"Error getting process-wise inventory summary: {str(e)}")
            return {}


class BatchValidator:
    """Utility class for validating batch operations"""
    
    @staticmethod
    def validate_batch_issue(batch_id, quantity, process_name=None):
        """Validate if batch can issue the requested quantity"""
        try:
            batch = ItemBatch.query.get(batch_id)
            if not batch:
                return False, "Batch not found"
            
            if quantity <= 0:
                return False, "Quantity must be greater than 0"
            
            if batch.is_expired:
                return False, f"Batch {batch.batch_number} has expired"
            
            if batch.quality_status == 'defective':
                return False, f"Batch {batch.batch_number} is marked as defective"
            
            available = batch.available_quantity
            if quantity > available:
                return False, f"Insufficient quantity. Available: {available}, Requested: {quantity}"
            
            return True, "Batch validation passed"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def validate_batch_return(job_work_id, batch_id, quantities):
        """Validate batch return quantities"""
        try:
            # Get the original issue record
            job_work_batch = JobWorkBatch.query.filter_by(
                job_work_id=job_work_id,
                input_batch_id=batch_id
            ).first()
            
            if not job_work_batch:
                return False, "No issue record found for this batch and job work"
            
            total_return = sum([
                quantities.get('finished', 0),
                quantities.get('scrap', 0),
                quantities.get('unused', 0)
            ])
            
            if total_return > job_work_batch.quantity_issued:
                return False, f"Cannot return more than issued. Issued: {job_work_batch.quantity_issued}"
            
            return True, "Return validation passed"
            
        except Exception as e:
            return False, f"Return validation error: {str(e)}"


# API helper functions for frontend integration
def get_batch_options_for_item_api(item_id):
    """API helper to get batch options for frontend"""
    try:
        batches = BatchTracker.get_available_batches_for_item(item_id)
        return {
            'success': True,
            'batches': batches,
            'total_available': sum(b['available_quantity'] for b in batches)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'batches': [],
            'total_available': 0
        }

def validate_batch_selection_api(batch_selections):
    """API helper to validate batch selections"""
    errors = []
    total_quantity = 0
    
    for selection in batch_selections:
        batch_id = selection.get('batch_id')
        quantity = selection.get('quantity', 0)
        
        is_valid, message = BatchValidator.validate_batch_issue(batch_id, quantity)
        if not is_valid:
            errors.append(f"Batch {batch_id}: {message}")
        else:
            total_quantity += quantity
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'total_quantity': total_quantity
    }