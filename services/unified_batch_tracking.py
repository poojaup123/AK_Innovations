"""
Unified Batch Tracking Service
Integrates batch tracking across all modules for complete traceability
"""

from datetime import datetime, date
from flask import current_app
from sqlalchemy import func, desc, and_
from typing import Dict, List, Optional, Union, Tuple
import re

from models import db, Item, User
from models.batch import InventoryBatch, BatchMovement, JobWorkBatch, BatchTraceability, BatchMovementLedger, BatchConsumptionReport
from models.grn import GRN, GRNLineItem
from models.job_card import JobCard


class UnifiedBatchTrackingService:
    """
    Central service for managing batch tracking across all modules
    Provides consistent batch creation, movement tracking, and traceability
    """
    
    @staticmethod
    def generate_batch_number(item_id: int, source_type: str = 'purchase', ref_number: str = None) -> str:
        """
        Generate consistent batch numbers across all modules
        Format: {ITEM_CODE}-{SOURCE}-{DATE}-{SEQUENCE}
        """
        try:
            item = Item.query.get(item_id)
            if not item:
                raise ValueError(f"Item with ID {item_id} not found")
            
            # Get current date components
            today = date.today()
            date_part = today.strftime("%y%m%d")  # YYMMDD format
            
            # Clean item code for batch number
            item_code = re.sub(r'[^A-Z0-9]', '', item.code.upper())[:6]
            
            # Source type abbreviations
            source_abbrev = {
                'purchase': 'PUR',
                'production': 'PRD',
                'jobwork': 'JOB',
                'transfer': 'TRF',
                'adjustment': 'ADJ',
                'sales_return': 'SRT'
            }.get(source_type, 'GEN')
            
            # Find next sequence number for today
            existing_batches = InventoryBatch.query.filter(
                InventoryBatch.item_id == item_id,
                InventoryBatch.batch_code.like(f"{item_code}-{source_abbrev}-{date_part}-%")
            ).count()
            
            sequence = str(existing_batches + 1).zfill(3)
            
            batch_number = f"{item_code}-{source_abbrev}-{date_part}-{sequence}"
            
            # If reference number provided, append abbreviated version
            if ref_number:
                ref_abbrev = re.sub(r'[^A-Z0-9]', '', ref_number.upper())[-4:]
                batch_number += f"-{ref_abbrev}"
            
            return batch_number
            
        except Exception as e:
            current_app.logger.error(f"Error generating batch number: {e}")
            # Fallback to simple timestamp-based number
            timestamp = datetime.now().strftime("%y%m%d%H%M%S")
            return f"BATCH-{timestamp}"
    
    @staticmethod
    def create_batch_from_grn(grn_line_item: GRNLineItem, user_id: int = None) -> InventoryBatch:
        """
        Create inventory batch from GRN line item
        Automatically integrates with quality inspection workflow
        """
        try:
            # Generate batch number
            batch_code = UnifiedBatchTrackingService.generate_batch_number(
                grn_line_item.item_id, 
                'purchase', 
                grn_line_item.grn.grn_number
            )
            
            # Create inventory batch
            batch = InventoryBatch(
                item_id=grn_line_item.item_id,
                batch_code=batch_code,
                qty_inspection=grn_line_item.quantity,  # Start in inspection
                uom=grn_line_item.uom or grn_line_item.item.unit_of_measure,
                supplier_batch_no=grn_line_item.supplier_batch_no,
                purchase_rate=grn_line_item.unit_price,
                grn_id=grn_line_item.grn_id,
                source_type='purchase',
                source_ref_id=grn_line_item.grn_id,
                mfg_date=grn_line_item.mfg_date,
                expiry_date=grn_line_item.expiry_date
            )
            
            db.session.add(batch)
            db.session.flush()  # Get batch ID
            
            # Create movement record
            UnifiedBatchTrackingService.record_movement(
                batch_id=batch.id,
                quantity=grn_line_item.quantity,
                from_state=None,
                to_state='inspection',
                movement_type='receipt',
                ref_type='grn',
                ref_id=grn_line_item.grn_id,
                notes=f"Received from {grn_line_item.grn.supplier.name if grn_line_item.grn.supplier else 'Unknown Supplier'}",
                user_id=user_id
            )
            
            return batch
            
        except Exception as e:
            current_app.logger.error(f"Error creating batch from GRN: {e}")
            db.session.rollback()
            raise
    
    @staticmethod
    def approve_inspection(batch_id: int, approved_qty: float, rejected_qty: float = 0, user_id: int = None) -> bool:
        """
        Approve inspection and move to raw material state
        Handles partial approvals and rejection tracking
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            
            total_inspected = approved_qty + rejected_qty
            if total_inspected > batch.qty_inspection:
                raise ValueError(f"Total inspected quantity ({total_inspected}) exceeds available quantity ({batch.qty_inspection})")
            
            # Move approved quantity to raw state
            if approved_qty > 0:
                batch.qty_inspection -= approved_qty
                batch.qty_raw += approved_qty
                batch.inspection_status = 'passed' if rejected_qty == 0 else 'partial'
                
                UnifiedBatchTrackingService.record_movement(
                    batch_id=batch_id,
                    quantity=approved_qty,
                    from_state='inspection',
                    to_state='raw',
                    movement_type='inspection_approval',
                    ref_type='quality_control',
                    notes=f"Quality inspection approved: {approved_qty} units",
                    user_id=user_id
                )
            
            # Move rejected quantity to scrap
            if rejected_qty > 0:
                batch.qty_inspection -= rejected_qty
                batch.qty_scrap += rejected_qty
                
                UnifiedBatchTrackingService.record_movement(
                    batch_id=batch_id,
                    quantity=rejected_qty,
                    from_state='inspection',
                    to_state='scrap',
                    movement_type='inspection_rejection',
                    ref_type='quality_control',
                    notes=f"Quality inspection rejected: {rejected_qty} units",
                    user_id=user_id
                )
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error approving inspection: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def allocate_batch_for_production(item_id: int, required_qty: float, fifo: bool = True) -> List[Dict]:
        """
        Allocate available batches for production using FIFO/LIFO
        Returns list of batch allocations with quantities
        """
        try:
            # Get available batches (raw + finished states)
            query = InventoryBatch.query.filter(
                InventoryBatch.item_id == item_id,
                InventoryBatch.inspection_status == 'passed'
            ).filter(
                (InventoryBatch.qty_raw > 0) | (InventoryBatch.qty_finished > 0)
            )
            
            # Apply FIFO or LIFO ordering
            if fifo:
                query = query.order_by(InventoryBatch.created_at.asc())
            else:
                query = query.order_by(InventoryBatch.created_at.desc())
            
            available_batches = query.all()
            
            allocations = []
            remaining_qty = required_qty
            
            for batch in available_batches:
                if remaining_qty <= 0:
                    break
                
                # Calculate available quantity in this batch
                available_qty = (batch.qty_raw or 0) + (batch.qty_finished or 0)
                
                if available_qty > 0:
                    # Allocate what we need or what's available
                    allocated_qty = min(remaining_qty, available_qty)
                    
                    allocations.append({
                        'batch_id': batch.id,
                        'batch_code': batch.batch_code,
                        'allocated_qty': allocated_qty,
                        'available_qty': available_qty,
                        'from_raw': min(allocated_qty, batch.qty_raw or 0),
                        'from_finished': max(0, allocated_qty - (batch.qty_raw or 0))
                    })
                    
                    remaining_qty -= allocated_qty
            
            if remaining_qty > 0:
                current_app.logger.warning(f"Insufficient stock for item {item_id}. Required: {required_qty}, Available: {required_qty - remaining_qty}")
            
            return allocations
            
        except Exception as e:
            current_app.logger.error(f"Error allocating batches: {e}")
            return []
    
    @staticmethod
    def consume_batch_for_production(allocations: List[Dict], production_ref_id: int, user_id: int = None) -> bool:
        """
        Consume allocated batches for production
        Moves quantities to WIP state with production reference
        """
        try:
            for allocation in allocations:
                batch = InventoryBatch.query.get(allocation['batch_id'])
                if not batch:
                    continue
                
                allocated_qty = allocation['allocated_qty']
                from_raw = allocation['from_raw']
                from_finished = allocation['from_finished']
                
                # Move from raw to WIP
                if from_raw > 0:
                    batch.qty_raw -= from_raw
                    batch.qty_wip += from_raw
                    
                    UnifiedBatchTrackingService.record_movement(
                        batch_id=batch.id,
                        quantity=from_raw,
                        from_state='raw',
                        to_state='wip',
                        movement_type='production_issue',
                        ref_type='production',
                        ref_id=production_ref_id,
                        notes=f"Issued for production: {from_raw} units from raw",
                        user_id=user_id
                    )
                
                # Move from finished to WIP (for rework scenarios)
                if from_finished > 0:
                    batch.qty_finished -= from_finished
                    batch.qty_wip += from_finished
                    
                    UnifiedBatchTrackingService.record_movement(
                        batch_id=batch.id,
                        quantity=from_finished,
                        from_state='finished',
                        to_state='wip',
                        movement_type='production_issue',
                        ref_type='production',
                        ref_id=production_ref_id,
                        notes=f"Issued for production: {from_finished} units from finished",
                        user_id=user_id
                    )
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error consuming batches: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def create_production_output_batch(item_id: int, produced_qty: float, production_ref_id: int, 
                                     input_batches: List[int], user_id: int = None) -> InventoryBatch:
        """
        Create output batch from production
        Links to input batches for complete traceability
        """
        try:
            # Generate batch number for production output
            batch_code = UnifiedBatchTrackingService.generate_batch_number(
                item_id, 
                'production', 
                f"PRD-{production_ref_id}"
            )
            
            # Create output batch
            output_batch = InventoryBatch(
                item_id=item_id,
                batch_code=batch_code,
                qty_finished=produced_qty,
                uom=Item.query.get(item_id).unit_of_measure,
                source_type='production',
                source_ref_id=production_ref_id
            )
            
            db.session.add(output_batch)
            db.session.flush()
            
            # Record production receipt
            UnifiedBatchTrackingService.record_movement(
                batch_id=output_batch.id,
                quantity=produced_qty,
                from_state=None,
                to_state='finished',
                movement_type='production_receipt',
                ref_type='production',
                ref_id=production_ref_id,
                notes=f"Production output: {produced_qty} units",
                user_id=user_id
            )
            
            # Create traceability links to input batches
            for input_batch_id in input_batches:
                input_batch = InventoryBatch.query.get(input_batch_id)
                if input_batch:
                    traceability = BatchTraceability(
                        source_batch_id=input_batch_id,
                        source_item_id=input_batch.item_id,
                        dest_batch_id=output_batch.id,
                        dest_item_id=item_id,
                        transformation_type='production',
                        transformation_ref_id=production_ref_id,
                        quantity_consumed=0,  # Will be calculated separately
                        quantity_produced=produced_qty
                    )
                    db.session.add(traceability)
            
            db.session.commit()
            return output_batch
            
        except Exception as e:
            current_app.logger.error(f"Error creating production output batch: {e}")
            db.session.rollback()
            raise
    
    @staticmethod
    def record_movement(batch_id: int, quantity: float, from_state: str, to_state: str,
                       movement_type: str, ref_type: str = None, ref_id: int = None,
                       notes: str = None, user_id: int = None) -> BatchMovement:
        """
        Record batch movement in both BatchMovement and BatchMovementLedger
        Provides complete audit trail
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            
            # Create BatchMovement record
            movement = BatchMovement(
                batch_id=batch_id,
                item_id=batch.item_id,
                quantity=quantity,
                from_state=from_state,
                to_state=to_state,
                movement_type=movement_type,
                ref_type=ref_type,
                ref_id=ref_id,
                notes=notes,
                user_id=user_id
            )
            db.session.add(movement)
            
            # Create BatchMovementLedger record for comprehensive tracking
            ledger_entry = BatchMovementLedger(
                ref_type=ref_type or movement_type,
                ref_id=ref_id or 0,
                ref_number=f"{ref_type}-{ref_id}" if ref_type and ref_id else movement_type,
                batch_id=batch_id,
                item_id=batch.item_id,
                from_state=from_state,
                to_state=to_state,
                quantity=quantity,
                unit_of_measure=batch.uom,
                notes=notes,
                created_by=user_id
            )
            db.session.add(ledger_entry)
            
            return movement
            
        except Exception as e:
            current_app.logger.error(f"Error recording batch movement: {e}")
            raise
    
    @staticmethod
    def get_batch_traceability(batch_id: int) -> Dict:
        """
        Get complete traceability information for a batch
        Returns upstream and downstream connections
        """
        try:
            batch = InventoryBatch.query.get(batch_id)
            if not batch:
                return {}
            
            # Get upstream traceability (what created this batch)
            upstream = BatchTraceability.query.filter_by(dest_batch_id=batch_id).all()
            
            # Get downstream traceability (what this batch created)
            downstream = BatchTraceability.query.filter_by(source_batch_id=batch_id).all()
            
            # Get all movements
            movements = BatchMovement.query.filter_by(batch_id=batch_id).order_by(BatchMovement.timestamp.desc()).all()
            
            return {
                'batch': batch,
                'upstream_sources': [
                    {
                        'source_batch': trace.source_batch,
                        'transformation_type': trace.transformation_type,
                        'quantity_consumed': trace.quantity_consumed,
                        'process_date': trace.process_date
                    } for trace in upstream
                ],
                'downstream_products': [
                    {
                        'dest_batch': trace.dest_batch,
                        'transformation_type': trace.transformation_type,
                        'quantity_produced': trace.quantity_produced,
                        'process_date': trace.process_date
                    } for trace in downstream
                ],
                'movement_history': [
                    {
                        'timestamp': movement.timestamp,
                        'quantity': movement.quantity,
                        'from_state': movement.from_state,
                        'to_state': movement.to_state,
                        'movement_type': movement.movement_type,
                        'ref_type': movement.ref_type,
                        'ref_id': movement.ref_id,
                        'notes': movement.notes,
                        'user': movement.user.username if movement.user else 'System'
                    } for movement in movements
                ]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting batch traceability: {e}")
            return {}
    
    @staticmethod
    def get_available_batches_for_item(item_id: int, state: str = 'all') -> List[Dict]:
        """
        Get all available batches for an item
        Can filter by state: 'raw', 'finished', 'wip', 'all'
        """
        try:
            query = InventoryBatch.query.filter_by(item_id=item_id)
            
            if state == 'raw':
                query = query.filter(InventoryBatch.qty_raw > 0)
            elif state == 'finished':
                query = query.filter(InventoryBatch.qty_finished > 0)
            elif state == 'wip':
                query = query.filter(InventoryBatch.qty_wip > 0)
            elif state != 'all':
                query = query.filter(getattr(InventoryBatch, f'qty_{state}', None) > 0)
            
            batches = query.order_by(InventoryBatch.created_at.asc()).all()
            
            return [
                {
                    'batch_id': batch.id,
                    'batch_code': batch.batch_code,
                    'qty_raw': batch.qty_raw or 0,
                    'qty_wip': batch.qty_wip or 0,
                    'qty_finished': batch.qty_finished or 0,
                    'qty_scrap': batch.qty_scrap or 0,
                    'total_available': batch.available_quantity,
                    'inspection_status': batch.inspection_status,
                    'mfg_date': batch.mfg_date,
                    'expiry_date': batch.expiry_date,
                    'is_expired': batch.is_expired,
                    'age_days': batch.age_days,
                    'supplier_batch_no': batch.supplier_batch_no,
                    'location': batch.location
                } for batch in batches
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting available batches: {e}")
            return []
    
    @staticmethod
    def consolidate_batches(batch_ids: List[int], target_batch_id: int, user_id: int = None) -> bool:
        """
        Consolidate multiple batches into a target batch
        Useful for merging small batches
        """
        try:
            target_batch = InventoryBatch.query.get(target_batch_id)
            if not target_batch:
                raise ValueError(f"Target batch {target_batch_id} not found")
            
            for batch_id in batch_ids:
                if batch_id == target_batch_id:
                    continue
                
                source_batch = InventoryBatch.query.get(batch_id)
                if not source_batch or source_batch.item_id != target_batch.item_id:
                    continue
                
                # Transfer quantities
                for state in ['raw', 'wip', 'finished', 'scrap']:
                    qty_field = f'qty_{state}'
                    source_qty = getattr(source_batch, qty_field, 0) or 0
                    
                    if source_qty > 0:
                        # Add to target batch
                        current_target_qty = getattr(target_batch, qty_field, 0) or 0
                        setattr(target_batch, qty_field, current_target_qty + source_qty)
                        
                        # Remove from source batch
                        setattr(source_batch, qty_field, 0)
                        
                        # Record movements
                        UnifiedBatchTrackingService.record_movement(
                            batch_id=source_batch.id,
                            quantity=source_qty,
                            from_state=state,
                            to_state=None,
                            movement_type='consolidation_out',
                            ref_type='batch_consolidation',
                            ref_id=target_batch_id,
                            notes=f"Consolidated into batch {target_batch.batch_code}",
                            user_id=user_id
                        )
                        
                        UnifiedBatchTrackingService.record_movement(
                            batch_id=target_batch_id,
                            quantity=source_qty,
                            from_state=None,
                            to_state=state,
                            movement_type='consolidation_in',
                            ref_type='batch_consolidation',
                            ref_id=source_batch.id,
                            notes=f"Consolidated from batch {source_batch.batch_code}",
                            user_id=user_id
                        )
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error consolidating batches: {e}")
            db.session.rollback()
            return False