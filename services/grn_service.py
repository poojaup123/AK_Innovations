"""3-Step GRN Workflow Service with complete Job Work integration"""

from app import db
from models import GRN, GRNLineItem, JobWork, Supplier
from models.batch import InventoryBatch, BatchMovement
from models.production import ProductionOrder, ProductionProcess
from services.accounting_service import AccountingService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GRNService:
    """Complete 3-Step GRN Workflow: Material Receipt → Invoice → Payment"""
    
    # Step 1: Material Receipt
    @staticmethod
    def create_material_receipt(grn_data):
        """Step 1: Create GRN for material receipt from job work"""
        try:
            # Create GRN header
            grn = GRN(
                grn_number=GRNService._generate_grn_number(),
                supplier_id=grn_data['supplier_id'],
                job_work_id=grn_data.get('job_work_id'),
                production_order_id=grn_data.get('production_order_id'),
                receipt_date=grn_data.get('receipt_date', datetime.utcnow().date()),
                receipt_type=grn_data.get('receipt_type', 'job_work'),
                status='material_received',  # Step 1 status
                received_by=grn_data['received_by'],
                remarks=grn_data.get('remarks', ''),
                gate_pass_no=grn_data.get('gate_pass_no', ''),
                vehicle_no=grn_data.get('vehicle_no', ''),
                
                # Step 1: Only material quantities, no financial entries yet
                total_value=0.0,  # Will be updated in Step 2
                gst_amount=0.0,
                final_amount=0.0,
                
                created_by=grn_data['created_by']
            )
            
            db.session.add(grn)
            db.session.flush()  # Get GRN ID
            
            # Process line items and create inventory batches
            line_items_created = []
            for item_data in grn_data['line_items']:
                # Create GRN line item
                line_item = GRNLineItem(
                    grn_id=grn.id,
                    item_id=item_data['item_id'],
                    po_line_item_id=item_data.get('po_line_item_id'),
                    
                    # Quantities
                    quantity_ordered=item_data.get('quantity_ordered', 0),
                    quantity_received=item_data['quantity_received'],
                    quantity_accepted=item_data.get('quantity_accepted', item_data['quantity_received']),
                    quantity_rejected=item_data.get('quantity_rejected', 0),
                    
                    uom=item_data['uom'],
                    
                    # Pricing will be filled in Step 2
                    unit_rate=0.0,
                    line_total=0.0,
                    gst_rate=item_data.get('gst_rate', 0.0),
                    
                    # Material state
                    material_state=item_data.get('material_state', 'finished'),
                    quality_status=item_data.get('quality_status', 'pending'),
                    quality_remarks=item_data.get('quality_remarks', ''),
                    
                    # Scrap tracking
                    scrap_quantity=item_data.get('scrap_quantity', 0),
                    scrap_reason=item_data.get('scrap_reason', ''),
                    
                    # Batch information
                    batch_code=item_data.get('batch_code', ''),
                    supplier_batch_no=item_data.get('supplier_batch_no', '')
                )
                
                db.session.add(line_item)
                line_items_created.append(line_item)
                
                # Create inventory batch for received material
                if line_item.quantity_accepted > 0:
                    batch_result = GRNService._create_inventory_batch(
                        grn, line_item, item_data
                    )
                    if not batch_result['success']:
                        raise Exception(f"Failed to create batch: {batch_result['error']}")
            
            # Update job work status if applicable
            if grn_data.get('job_work_id'):
                job_work = JobWork.query.get(grn_data['job_work_id'])
                if job_work:
                    # Update quantities received
                    total_received = sum(item['quantity_received'] for item in grn_data['line_items'])
                    job_work.quantity_received = (job_work.quantity_received or 0) + total_received
                    
                    # Update status based on completion
                    if job_work.quantity_received >= job_work.quantity_to_issue:
                        job_work.status = 'completed'
                        job_work.completion_date = datetime.utcnow().date()
                    else:
                        job_work.status = 'partial_received'
                    
                    # Create batch movement record
                    GRNService._record_job_work_completion(job_work, grn)
            
            db.session.commit()
            
            logger.info(f"GRN {grn.grn_number} created - Step 1 Complete: Material Receipt")
            
            return {
                'success': True,
                'grn': grn,
                'line_items_count': len(line_items_created),
                'step': 1,
                'next_step': 'invoice_received',
                'message': 'Material receipt completed. Awaiting invoice for Step 2.'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in GRN Step 1: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Step 2: Invoice Processing
    @staticmethod
    def process_invoice(grn_id, invoice_data):
        """Step 2: Process vendor invoice and match with GRN"""
        try:
            grn = GRN.query.get(grn_id)
            if not grn:
                return {'success': False, 'error': 'GRN not found'}
            
            if grn.status != 'material_received':
                return {'success': False, 'error': f'GRN is in {grn.status} status, expecting material_received'}
            
            # Update GRN with invoice details
            grn.invoice_number = invoice_data['invoice_number']
            grn.invoice_date = invoice_data['invoice_date']
            grn.invoice_amount = invoice_data['invoice_amount']
            grn.status = 'invoice_received'  # Step 2 status
            
            # Process line item pricing
            total_value = 0.0
            total_gst = 0.0
            
            for line_pricing in invoice_data['line_items']:
                line_item = GRNLineItem.query.filter_by(
                    grn_id=grn_id,
                    item_id=line_pricing['item_id']
                ).first()
                
                if line_item:
                    line_item.unit_rate = line_pricing['unit_rate']
                    line_item.line_total = line_item.quantity_accepted * line_item.unit_rate
                    line_item.gst_amount = line_item.line_total * (line_item.gst_rate / 100)
                    
                    total_value += line_item.line_total
                    total_gst += line_item.gst_amount
            
            # Update GRN totals
            grn.total_value = total_value
            grn.gst_amount = total_gst
            grn.final_amount = total_value + total_gst
            
            # Validate invoice amount matches
            if abs(grn.final_amount - grn.invoice_amount) > 0.01:
                logger.warning(f"Invoice amount mismatch: GRN={grn.final_amount}, Invoice={grn.invoice_amount}")
            
            # Create accounting entries (Step 2: GRN Clearing)
            accounting_result = AccountingService.create_grn_accounting_entries(grn)
            if not accounting_result['success']:
                raise Exception(f"Accounting error: {accounting_result['error']}")
            
            # Update inventory batch values
            for line_item in grn.line_items:
                if line_item.quantity_accepted > 0:
                    batch = InventoryBatch.query.filter_by(
                        grn_id=grn.id,
                        item_id=line_item.item_id
                    ).first()
                    
                    if batch:
                        batch.purchase_rate = line_item.unit_rate
                        batch.total_value = line_item.line_total + line_item.gst_amount
            
            db.session.commit()
            
            logger.info(f"GRN {grn.grn_number} - Step 2 Complete: Invoice Processed")
            
            return {
                'success': True,
                'grn': grn,
                'step': 2,
                'next_step': 'payment',
                'total_amount': grn.final_amount,
                'accounting_entries': accounting_result.get('entries', []),
                'message': 'Invoice processed and accounting entries created. Ready for payment.'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in GRN Step 2: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Step 3: Payment Processing
    @staticmethod
    def process_payment(grn_id, payment_data):
        """Step 3: Process payment and complete GRN workflow"""
        try:
            grn = GRN.query.get(grn_id)
            if not grn:
                return {'success': False, 'error': 'GRN not found'}
            
            if grn.status != 'invoice_received':
                return {'success': False, 'error': f'GRN is in {grn.status} status, expecting invoice_received'}
            
            # Update GRN with payment details
            grn.payment_date = payment_data['payment_date']
            grn.payment_method = payment_data['payment_method']
            grn.payment_reference = payment_data.get('payment_reference', '')
            grn.payment_amount = payment_data['payment_amount']
            grn.status = 'completed'  # Final status
            
            # Validate payment amount
            if abs(grn.payment_amount - grn.final_amount) > 0.01:
                logger.warning(f"Payment amount mismatch: Expected={grn.final_amount}, Paid={grn.payment_amount}")
            
            # Create payment accounting entries
            payment_result = AccountingService.create_payment_entries(grn, payment_data)
            if not payment_result['success']:
                raise Exception(f"Payment accounting error: {payment_result['error']}")
            
            # Update production order cost if applicable
            if grn.production_order_id:
                production_order = ProductionOrder.query.get(grn.production_order_id)
                if production_order:
                    production_order.job_work_cost += grn.final_amount
                    production_order.update_progress()
            
            # Complete job work if applicable
            if grn.job_work_id:
                job_work = JobWork.query.get(grn.job_work_id)
                if job_work:
                    job_work.actual_cost = grn.final_amount
                    job_work.cost_per_unit = grn.final_amount / job_work.quantity_received if job_work.quantity_received > 0 else 0
                    job_work.payment_date = payment_data['payment_date']
                    job_work.payment_status = 'paid'
            
            db.session.commit()
            
            logger.info(f"GRN {grn.grn_number} - Step 3 Complete: Payment Processed - Workflow Complete")
            
            return {
                'success': True,
                'grn': grn,
                'step': 3,
                'workflow_complete': True,
                'total_paid': grn.payment_amount,
                'payment_entries': payment_result.get('entries', []),
                'message': '3-Step GRN workflow completed successfully.'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in GRN Step 3: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _generate_grn_number():
        """Generate unique GRN number"""
        try:
            from models import CompanySettings
            settings = CompanySettings.query.first()
            prefix = settings.grn_number_prefix if settings and settings.grn_number_prefix else "GRN"
        except:
            prefix = "GRN"
        
        last_grn = GRN.query.order_by(GRN.id.desc()).first()
        next_num = 1 if not last_grn else last_grn.id + 1
        
        return f"{prefix}-{datetime.now().year}-{str(next_num).zfill(4)}"
    
    @staticmethod
    def _create_inventory_batch(grn, line_item, item_data):
        """Create inventory batch for received material"""
        try:
            batch_code = item_data.get('batch_code') or f"GRN-{grn.grn_number}-{line_item.item.code}"
            
            batch = InventoryBatch(
                item_id=line_item.item_id,
                batch_code=batch_code,
                uom=line_item.uom,
                grn_id=grn.id,
                source_type='job_work' if grn.job_work_id else 'purchase',
                source_ref_id=grn.job_work_id or grn.id,
                supplier_batch_no=item_data.get('supplier_batch_no', ''),
                mfg_date=item_data.get('mfg_date'),
                expiry_date=item_data.get('expiry_date'),
                location=item_data.get('location', 'Main Store')
            )
            
            # Set quantity based on material state
            material_state = line_item.material_state
            if material_state == 'raw':
                batch.qty_raw = line_item.quantity_accepted
            elif material_state == 'wip':
                batch.qty_wip = line_item.quantity_accepted
            elif material_state == 'finished':
                batch.qty_finished = line_item.quantity_accepted
            elif material_state == 'scrap':
                batch.qty_scrap = line_item.quantity_accepted
            else:
                # Default to inspection queue
                batch.qty_inspection = line_item.quantity_accepted
                batch.inspection_status = 'pending'
            
            db.session.add(batch)
            
            # Create batch movement record
            movement = BatchMovement(
                batch_id=batch.id,
                movement_type='receipt',
                quantity=line_item.quantity_accepted,
                from_state='external',
                to_state=material_state,
                reference_type='grn',
                reference_id=grn.id,
                movement_date=grn.receipt_date,
                notes=f"GRN Receipt: {grn.grn_number}"
            )
            db.session.add(movement)
            
            return {'success': True, 'batch': batch}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _record_job_work_completion(job_work, grn):
        """Record job work completion in batch system"""
        try:
            from models.batch import BatchTraceability
            
            # Create traceability record
            traceability = BatchTraceability(
                source_batch_id=job_work.source_batch_id,
                target_batch_id=grn.line_items[0].batch_id if grn.line_items else None,
                job_work_id=job_work.id,
                grn_id=grn.id,
                transformation_type='job_work_completion',
                input_quantity=job_work.quantity_to_issue,
                output_quantity=job_work.quantity_received,
                scrap_quantity=(job_work.quantity_to_issue or 0) - (job_work.quantity_received or 0),
                process_date=grn.receipt_date,
                process_notes=f"Job work completed via GRN {grn.grn_number}"
            )
            
            db.session.add(traceability)
            
        except Exception as e:
            logger.error(f"Error recording job work completion: {str(e)}")
    
    @staticmethod
    def get_grn_status(grn_id):
        """Get complete GRN status with all steps"""
        try:
            grn = GRN.query.get(grn_id)
            if not grn:
                return {'success': False, 'error': 'GRN not found'}
            
            # Determine current step and next actions
            step_info = {
                'material_received': {
                    'current_step': 1,
                    'step_name': 'Material Receipt',
                    'next_step': 'Process Invoice',
                    'completed_steps': ['material_receipt'],
                    'pending_steps': ['invoice_processing', 'payment']
                },
                'invoice_received': {
                    'current_step': 2,
                    'step_name': 'Invoice Processing',
                    'next_step': 'Process Payment',
                    'completed_steps': ['material_receipt', 'invoice_processing'],
                    'pending_steps': ['payment']
                },
                'completed': {
                    'current_step': 3,
                    'step_name': 'Payment Complete',
                    'next_step': 'Workflow Complete',
                    'completed_steps': ['material_receipt', 'invoice_processing', 'payment'],
                    'pending_steps': []
                }
            }
            
            current_info = step_info.get(grn.status, {
                'current_step': 0,
                'step_name': 'Unknown Status',
                'next_step': 'Check Status',
                'completed_steps': [],
                'pending_steps': ['material_receipt', 'invoice_processing', 'payment']
            })
            
            # Get related records
            job_work = JobWork.query.get(grn.job_work_id) if grn.job_work_id else None
            production_order = ProductionOrder.query.get(grn.production_order_id) if grn.production_order_id else None
            
            return {
                'success': True,
                'grn': {
                    'id': grn.id,
                    'grn_number': grn.grn_number,
                    'supplier': grn.supplier.name if grn.supplier else 'Unknown',
                    'receipt_date': grn.receipt_date.isoformat() if grn.receipt_date else None,
                    'status': grn.status,
                    'total_value': grn.total_value,
                    'final_amount': grn.final_amount,
                    'invoice_number': grn.invoice_number,
                    'invoice_date': grn.invoice_date.isoformat() if grn.invoice_date else None,
                    'payment_date': grn.payment_date.isoformat() if grn.payment_date else None,
                    'payment_amount': grn.payment_amount
                },
                'workflow_status': current_info,
                'line_items': [
                    {
                        'item_name': li.item.name,
                        'quantity_received': li.quantity_received,
                        'quantity_accepted': li.quantity_accepted,
                        'unit_rate': li.unit_rate,
                        'line_total': li.line_total,
                        'quality_status': li.quality_status
                    } for li in grn.line_items
                ],
                'job_work': job_work.to_dict() if job_work else None,
                'production_order': production_order.to_dict() if production_order else None
            }
            
        except Exception as e:
            logger.error(f"Error getting GRN status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_pending_grns_by_step():
        """Get GRNs pending at each step of the workflow"""
        try:
            pending_grns = {
                'step_1_pending': GRN.query.filter_by(status='material_received').count(),
                'step_2_pending': GRN.query.filter_by(status='invoice_received').count(),
                'completed': GRN.query.filter_by(status='completed').count(),
                'total_grns': GRN.query.count()
            }
            
            # Get detailed lists
            step_1_grns = GRN.query.filter_by(status='material_received').order_by(GRN.receipt_date.desc()).limit(10).all()
            step_2_grns = GRN.query.filter_by(status='invoice_received').order_by(GRN.invoice_date.desc()).limit(10).all()
            
            return {
                'success': True,
                'summary': pending_grns,
                'step_1_details': [grn.to_dict() for grn in step_1_grns],
                'step_2_details': [grn.to_dict() for grn in step_2_grns]
            }
            
        except Exception as e:
            logger.error(f"Error getting pending GRNs: {str(e)}")
            return {'success': False, 'error': str(e)}