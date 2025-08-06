"""
Comprehensive Batch Management Services
Implements the complete batch tracking blueprint across all modules
"""

from app import db
from models import Item, JobWork, Production
from models.batch import InventoryBatch, BatchMovementLedger, BatchConsumptionReport
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional, Tuple

class BatchManager:
    """
    Central service for managing batch operations across all modules
    Implements the complete factory management app flow as per blueprint
    """
    
    @staticmethod
    def create_batch_from_grn(grn_line_item, supplier_batch_number=None, add_to_inventory=True):
        """
        Create batch when materials are received via GRN
        GRN → Inventory [Raw Batch]
        """
        try:
            item = grn_line_item.item
            grn = grn_line_item.grn
            
            # Check if item requires batch tracking (default to True for comprehensive tracking)
            if hasattr(item, 'batch_required') and item.batch_required is False:
                return None, "Item does not require batch tracking"
            
            # Generate batch number
            batch_number = BatchManager._generate_batch_number(
                item, supplier_batch_number or ""
            )
            
            # Calculate expiry date if shelf life is defined
            expiry_date = None
            if item.shelf_life_days:
                expiry_date = datetime.now().date() + timedelta(days=item.shelf_life_days)
            
            # Determine batch quantities and status based on add_to_inventory flag
            # When add_to_inventory=True, bypass inspection and go directly to inventory
            if add_to_inventory:
                # Direct to inventory - approved material (bypassing inspection)
                qty_raw = grn_line_item.quantity_received
                qty_inspection = 0.0
                quality_status = 'good'
                storage_location = 'MAIN-STORE'
            else:
                # Hold in inspection area
                qty_raw = 0.0
                qty_inspection = grn_line_item.quantity_received
                quality_status = 'pending_inspection'
                storage_location = 'INSPECTION-AREA'
            
            # Create new batch using InventoryBatch model
            batch = InventoryBatch(
                item_id=item.id,
                batch_code=batch_number,
                supplier_batch_no=supplier_batch_number or '',
                mfg_date=grn_line_item.grn.received_date if hasattr(grn_line_item.grn.received_date, 'date') else grn_line_item.grn.received_date,
                expiry_date=expiry_date,
                qty_raw=qty_raw,
                qty_inspection=qty_inspection,
                location=storage_location,
                purchase_rate=grn_line_item.quantity_received * (getattr(grn_line_item, 'rate_per_unit', 0) or 0),
                inspection_status=quality_status,
                grn_id=grn_line_item.grn_id,
                uom=item.unit_of_measure or 'PCS',
                source_type='purchase'
            )
            
            db.session.add(batch)
            db.session.flush()  # Get the batch ID
            
            # Record batch movement
            BatchMovementLedger.create_movement(
                ref_type='GRN',
                ref_id=grn_line_item.grn_id,
                ref_number=grn_line_item.grn.grn_number,
                batch_id=batch.id,
                item_id=item.id,
                from_state=None,
                to_state='Raw',
                quantity=grn_line_item.quantity_received,
                unit_of_measure=item.unit_of_measure,
                vendor_id=getattr(grn_line_item.grn, 'supplier_id', None),
                storage_location=batch.location,
                cost_per_unit=getattr(grn_line_item, 'rate_per_unit', 0) or 0.0,
                total_cost=(grn_line_item.quantity_received * (getattr(grn_line_item, 'rate_per_unit', 0) or 0.0)),
                movement_date=grn_line_item.grn.received_date,
                notes=f"Material received from GRN {grn_line_item.grn.grn_number}"
            )
            
            # Create accounting valuation entry for inventory receipt
            try:
                from services.accounting_automation import AccountingAutomation
                cost_per_unit = getattr(grn_line_item, 'rate_per_unit', 0) or 0.0
                total_valuation = grn_line_item.quantity_received * cost_per_unit
                AccountingAutomation.create_inventory_valuation_entry(
                    item, grn_line_item.quantity_received, total_valuation, 'receipt'
                )
            except Exception as e:
                print(f"Warning: Could not create accounting entry: {e}")
                # Continue processing even if accounting fails
            
            # Update consumption report
            report = BatchConsumptionReport.get_or_create(batch.id)
            if report:
                movement = BatchMovementLedger.query.filter_by(batch_id=batch.id).first()
                report.update_from_movement(movement)
            
            db.session.commit()
            return batch, "Batch created successfully"
            
        except Exception as e:
            db.session.rollback()
            return None, f"Error creating batch: {str(e)}"
    
    @staticmethod
    def issue_batch_to_jobwork(job_work_id: int, batch_selections: List[Dict]) -> Tuple[bool, str]:
        """
        Issue materials from batches to job work
        Raw → WIP (issued to JW)
        """
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return False, "Job work not found"
            
            total_issued = 0
            
            for selection in batch_selections:
                batch_id = selection['batch_id']
                quantity = selection['quantity']
                process_name = selection.get('process_name', 'cutting')
                
                batch = InventoryBatch.query.get(batch_id)
                if not batch:
                    continue
                
                # Check if enough raw material is available
                if batch.qty_raw < quantity:
                    return False, f"Insufficient raw material in batch {batch.batch_code}"
                
                # Move from raw to process-specific WIP
                success = batch.move_to_wip(quantity, process_name)
                if not success:
                    return False, f"Failed to move material from batch {batch.batch_code}"
                
                # Record batch movement
                BatchMovementLedger.create_movement(
                    ref_type='JobWork',
                    ref_id=job_work_id,
                    ref_number=job_work.job_number,
                    batch_id=batch_id,
                    item_id=batch.item_id,
                    from_state='Raw',
                    to_state=f'WIP_{process_name.title()}',
                    quantity=quantity,
                    unit_of_measure=batch.item.unit_of_measure,
                    process_name=process_name,
                    vendor_id=job_work.vendor_id,
                    notes=f"Material issued to job work {job_work.job_number} for {process_name}"
                )
                
                total_issued += quantity
            
            db.session.commit()
            return True, f"Successfully issued {total_issued} units to job work"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error issuing materials: {str(e)}"
    
    @staticmethod
    def receive_from_jobwork(job_work_id: int, return_data: List[Dict]) -> Tuple[bool, str]:
        """
        Receive materials back from job work
        WIP → Finished + Scrap + Return unused
        """
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return False, "Job work not found"
            
            for return_item in return_data:
                input_batch_id = return_item['input_batch_id']
                output_item_id = return_item.get('output_item_id')
                finished_qty = return_item.get('finished_qty', 0)
                scrap_qty = return_item.get('scrap_qty', 0)
                unused_qty = return_item.get('unused_qty', 0)
                process_name = return_item.get('process_name', 'cutting')
                
                input_batch = InventoryBatch.query.get(input_batch_id)
                if not input_batch:
                    continue
                
                # Handle finished output (create new batch if different item)
                if finished_qty > 0:
                    if output_item_id and output_item_id != input_batch.item_id:
                        # Create new batch for output product
                        output_batch = BatchManager._create_output_batch(
                            output_item_id, finished_qty, input_batch, job_work
                        )
                        
                        # Record movement for output batch
                        BatchMovementLedger.create_movement(
                            ref_type='JobWork',
                            ref_id=job_work_id,
                            ref_number=job_work.job_number,
                            batch_id=output_batch.id,
                            item_id=output_item_id,
                            from_state=f'WIP_{process_name.title()}',
                            to_state='Finished',
                            quantity=finished_qty,
                            unit_of_measure=output_batch.item.unit_of_measure,
                            process_name=process_name,
                            vendor_id=job_work.vendor_id,
                            notes=f"Finished product from job work {job_work.job_number}"
                        )
                    else:
                        # Same item - move from WIP to finished in same batch
                        input_batch.receive_from_wip(finished_qty, 0, process_name)
                        
                        # Record movement
                        BatchMovementLedger.create_movement(
                            ref_type='JobWork',
                            ref_id=job_work_id,
                            ref_number=job_work.job_number,
                            batch_id=input_batch_id,
                            item_id=input_batch.item_id,
                            from_state=f'WIP_{process_name.title()}',
                            to_state='Finished',
                            quantity=finished_qty,
                            unit_of_measure=input_batch.item.unit_of_measure,
                            process_name=process_name,
                            vendor_id=job_work.vendor_id,
                            notes=f"Finished material from job work {job_work.job_number}"
                        )
                
                # Handle scrap
                if scrap_qty > 0:
                    input_batch.receive_from_wip(0, scrap_qty, process_name)
                    
                    # Record scrap movement
                    BatchMovementLedger.create_movement(
                        ref_type='JobWork',
                        ref_id=job_work_id,
                        ref_number=job_work.job_number,
                        batch_id=input_batch_id,
                        item_id=input_batch.item_id,
                        from_state=f'WIP_{process_name.title()}',
                        to_state='Scrap',
                        quantity=scrap_qty,
                        unit_of_measure=input_batch.item.unit_of_measure,
                        process_name=process_name,
                        vendor_id=job_work.vendor_id,
                        quality_status='defective',
                        notes=f"Scrap from job work {job_work.job_number}"
                    )
                
                # Handle unused material return
                if unused_qty > 0:
                    # Move back to raw state
                    success = input_batch.move_from_wip_to_raw(unused_qty, process_name)
                    if success:
                        BatchMovementLedger.create_movement(
                            ref_type='JobWork',
                            ref_id=job_work_id,
                            ref_number=job_work.job_number,
                            batch_id=input_batch_id,
                            item_id=input_batch.item_id,
                            from_state=f'WIP_{process_name.title()}',
                            to_state='Raw',
                            quantity=unused_qty,
                            unit_of_measure=input_batch.item.unit_of_measure,
                            process_name=process_name,
                            vendor_id=job_work.vendor_id,
                            notes=f"Unused material returned from job work {job_work.job_number}"
                        )
            
            db.session.commit()
            return True, "Materials received successfully from job work"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error receiving materials: {str(e)}"
    
    @staticmethod
    def dispatch_batch(batch_id: int, quantity: float, sales_order_ref: str = None) -> Tuple[bool, str]:
        """
        Dispatch finished goods from batch
        Finished → Dispatched
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return False, "Batch not found"
            
            # Check if enough finished quantity is available
            if batch.qty_finished < quantity:
                return False, f"Insufficient finished quantity in batch {batch.batch_code}"
            
            # Deduct from finished quantity
            batch.qty_finished -= quantity
            
            # Record dispatch movement
            BatchMovementLedger.create_movement(
                ref_type='Dispatch',
                ref_id=0,  # Will be updated with actual sales order ID
                ref_number=sales_order_ref or 'DIRECT-DISPATCH',
                batch_id=batch_id,
                item_id=batch.item_id,
                from_state='Finished',
                to_state='Dispatched',
                quantity=quantity,
                unit_of_measure=batch.item.unit_of_measure,
                notes=f"Dispatched from batch {batch.batch_code}"
            )
            
            db.session.commit()
            return True, f"Successfully dispatched {quantity} units from batch {batch.batch_code}"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error dispatching batch: {str(e)}"
    
    @staticmethod
    def get_batch_traceability(batch_id: int) -> Dict:
        """
        Get complete traceability for a batch
        Returns full movement history and current status
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return {'error': 'Batch not found'}
            
            # Get all movements for this batch
            movements = BatchMovementLedger.get_batch_history(batch_id)
            
            # Get consumption report
            report = BatchConsumptionReport.query.filter_by(batch_id=batch_id).first()
            
            movement_data = []
            for movement in movements:
                movement_data.append({
                    'id': movement.id,
                    'ref_type': movement.ref_type,
                    'ref_number': movement.ref_number,
                    'from_state': movement.from_state,
                    'to_state': movement.to_state,
                    'quantity': movement.quantity,
                    'unit_of_measure': movement.unit_of_measure,
                    'process_name': movement.process_name,
                    'vendor_name': movement.vendor.name if movement.vendor else None,
                    'movement_date': movement.movement_date.isoformat(),
                    'created_at': movement.created_at.isoformat(),
                    'notes': movement.notes
                })
            
            return {
                'batch': {
                    'id': batch.id,
                    'batch_number': batch.batch_code,
                    'item_name': batch.item.name,
                    'item_code': batch.item.code,
                    'supplier_batch': batch.supplier_batch_no,
                    'manufacture_date': batch.mfg_date.isoformat() if batch.mfg_date else None,
                    'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                    'current_quantities': {
                        'raw': batch.qty_raw or 0,
                        'wip_cutting': batch.qty_wip_cutting or 0,
                        'wip_bending': batch.qty_wip_bending or 0,
                        'wip_welding': batch.qty_wip_welding or 0,
                        'wip_zinc': batch.qty_wip_zinc or 0,
                        'wip_painting': batch.qty_wip_painting or 0,
                        'wip_assembly': batch.qty_wip_assembly or 0,
                        'wip_machining': batch.qty_wip_machining or 0,
                        'wip_polishing': batch.qty_wip_polishing or 0,
                        'finished': batch.qty_finished or 0,
                        'scrap': batch.qty_scrap or 0
                    },
                    'total_quantity': batch.total_quantity,
                    'available_quantity': batch.available_quantity,
                    'quality_status': batch.inspection_status,
                    'storage_location': batch.location
                },
                'movements': movement_data,
                'consumption_report': {
                    'total_received': report.total_received if report else 0,
                    'total_issued': report.total_issued if report else 0,
                    'total_finished': report.total_finished if report else 0,
                    'total_scrap': report.total_scrap if report else 0,
                    'total_dispatched': report.total_dispatched if report else 0,
                    'yield_percentage': report.yield_percentage if report else 0,
                    'scrap_percentage': report.scrap_percentage if report else 0,
                    'utilization_percentage': report.utilization_percentage if report else 0
                } if report else None
            }
            
        except Exception as e:
            return {'error': f"Error getting traceability: {str(e)}"}
    
    @staticmethod
    def _generate_batch_number(item: Item, supplier_batch: str = None) -> str:
        """Generate batch number based on item configuration"""
        if supplier_batch and not item.batch_numbering_auto:
            return supplier_batch
        
        # Auto-generate batch number
        prefix = item.default_batch_prefix or item.code[:3].upper()
        
        # Get current date for batch numbering
        current_date = datetime.now()
        date_str = current_date.strftime('%y%m')
        
        # Find next sequence number for this item and month
        existing_batches = InventoryBatch.query.filter(
            InventoryBatch.item_id == item.id,
            InventoryBatch.batch_code.like(f'{prefix}-{date_str}-%')
        ).count()
        
        sequence = existing_batches + 1
        
        return f"{prefix}-{date_str}-{sequence:03d}"
    
    @staticmethod
    def _create_output_batch(output_item_id: int, quantity: float, input_batch: InventoryBatch, job_work: JobWork) -> InventoryBatch:
        """Create new batch for output product from job work"""
        output_item = Item.query.get(output_item_id)
        
        # Generate batch number for output
        output_batch_number = BatchManager._generate_batch_number(output_item)
        
        # Create output batch
        output_batch = InventoryBatch(
            item_id=output_item_id,
            batch_code=output_batch_number,
            supplier_batch_no=f"JW-{job_work.job_number}",
            mfg_date=datetime.now().date(),
            qty_finished=quantity,
            location=input_batch.location,
            purchase_rate=input_batch.purchase_rate,  # Inherit cost from input
            inspection_status='passed',
            uom=output_item.unit_of_measure or 'PCS',
            source_type='production'
        )
        
        db.session.add(output_batch)
        db.session.flush()
        
        return output_batch

class BatchValidator:
    """
    Validation service for batch operations
    Ensures data integrity and business rules compliance
    """
    
    @staticmethod
    def validate_batch_selection(batch_selections: List[Dict]) -> Dict:
        """Validate batch selection for job work or production"""
        errors = []
        warnings = []
        
        total_quantity = 0
        
        for selection in batch_selections:
            batch_id = selection.get('batch_id')
            quantity = selection.get('quantity', 0)
            
            if not batch_id:
                errors.append("Batch ID is required")
                continue
            
            if quantity <= 0:
                errors.append(f"Quantity must be greater than 0 for batch {batch_id}")
                continue
            
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                errors.append(f"Batch {batch_id} not found")
                continue
            
            # Check available quantity
            if batch.qty_raw < quantity:
                errors.append(f"Insufficient quantity in batch {batch.batch_code}. Available: {batch.qty_raw}, Required: {quantity}")
            
            # Check quality status
            if batch.inspection_status == 'failed':
                errors.append(f"Cannot use defective batch {batch.batch_code}")
            elif batch.inspection_status == 'pending':
                warnings.append(f"Batch {batch.batch_code} is pending inspection")
            
            # Check expiry
            if batch.expiry_date and batch.expiry_date < datetime.now().date():
                errors.append(f"Batch {batch.batch_code} has expired")
            elif batch.expiry_date and batch.expiry_date < (datetime.now().date() + timedelta(days=7)):
                warnings.append(f"Batch {batch.batch_code} expires soon ({batch.expiry_date})")
            
            total_quantity += quantity
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_quantity': total_quantity
        }
    
    @staticmethod
    def validate_fifo_compliance(item_id: int, requested_batches: List[int]) -> Dict:
        """Validate FIFO (First In, First Out) compliance for batch selection"""
        
        # Get all available batches for item ordered by manufacture date (FIFO)
        available_batches = InventoryBatch.query.filter(
            InventoryBatch.item_id == item_id,
            InventoryBatch.qty_raw > 0,
            InventoryBatch.inspection_status.in_(['passed', 'pending'])
        ).order_by(InventoryBatch.mfg_date).all()
        
        if not available_batches:
            return {'compliant': True, 'message': 'No available batches'}
        
        # Check if requested batches follow FIFO order
        requested_batch_objs = [b for b in available_batches if b.id in requested_batches]
        
        # Find oldest available batch not in selection
        for batch in available_batches:
            if batch.id not in requested_batches and batch.qty_raw > 0:
                # Found older batch not selected - FIFO violation
                return {
                    'compliant': False,
                    'message': f'FIFO violation: Older batch {batch.batch_code} (Date: {batch.mfg_date}) should be used before newer batches',
                    'suggested_batch': {
                        'id': batch.id,
                        'batch_number': batch.batch_code,
                        'manufacture_date': batch.mfg_date.isoformat() if batch.mfg_date else None,
                        'available_quantity': batch.qty_raw
                    }
                }
        
        return {'compliant': True, 'message': 'FIFO compliance maintained'}