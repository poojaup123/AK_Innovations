"""Partial Job Work Support - Handle partial issuance and receipt"""

from app import db
from models import JobWork
from models.batch import InventoryBatch, BatchMovement, JobWorkBatch
from services.grn_service import GRNService
from services.costing_service import CostingService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PartialJobService:
    """Handle partial job work issuance and receipt operations"""
    
    @staticmethod
    def issue_partial_material(job_work_id, partial_issue_data):
        """Issue partial material for job work"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            if job_work.status not in ['draft', 'sent', 'partial_issued']:
                return {'success': False, 'error': f'Cannot issue material - job work is {job_work.status}'}
            
            # Validate partial issue quantity
            issue_qty = partial_issue_data['issue_quantity']
            remaining_to_issue = (job_work.quantity_to_issue or 0) - (job_work.quantity_issued or 0)
            
            if issue_qty > remaining_to_issue:
                return {'success': False, 'error': f'Issue quantity ({issue_qty}) exceeds remaining quantity ({remaining_to_issue})'}
            
            # Get source batch
            source_batch = InventoryBatch.query.get(partial_issue_data['source_batch_id'])
            if not source_batch:
                return {'success': False, 'error': 'Source batch not found'}
            
            # Check batch availability
            available_qty = source_batch.qty_raw + source_batch.qty_finished
            if issue_qty > available_qty:
                return {'success': False, 'error': f'Insufficient batch quantity. Available: {available_qty}'}
            
            # Create job work batch record for partial issue
            job_work_batch = JobWorkBatch(
                job_work_id=job_work.id,
                source_batch_id=source_batch.id,
                issued_quantity=issue_qty,
                issued_date=partial_issue_data.get('issue_date', datetime.utcnow().date()),
                status='issued',
                uom=source_batch.uom,
                issue_type='partial',
                gate_pass_no=partial_issue_data.get('gate_pass_no', ''),
                vehicle_no=partial_issue_data.get('vehicle_no', ''),
                issued_by=partial_issue_data.get('issued_by', 1),
                remarks=partial_issue_data.get('remarks', '')
            )
            
            db.session.add(job_work_batch)
            
            # Update source batch quantities
            if source_batch.qty_raw >= issue_qty:
                source_batch.qty_raw -= issue_qty
            else:
                remaining_qty = issue_qty - source_batch.qty_raw
                source_batch.qty_raw = 0
                source_batch.qty_finished -= remaining_qty
            
            # Create batch movement record
            movement = BatchMovement(
                batch_id=source_batch.id,
                movement_type='issue',
                quantity=issue_qty,
                from_state='raw' if source_batch.qty_raw > 0 else 'finished',
                to_state='issued',
                reference_type='job_work',
                reference_id=job_work.id,
                movement_date=job_work_batch.issued_date,
                notes=f"Partial issue for job work {job_work.job_number}"
            )
            
            db.session.add(movement)
            
            # Update job work status
            job_work.quantity_issued = (job_work.quantity_issued or 0) + issue_qty
            
            if job_work.quantity_issued >= job_work.quantity_to_issue:
                job_work.status = 'sent'
                job_work.sent_date = datetime.utcnow().date()
            else:
                job_work.status = 'partial_issued'
            
            db.session.commit()
            
            logger.info(f"Partial material issued for job work {job_work.job_number}: {issue_qty} units")
            
            return {
                'success': True,
                'job_work_batch': job_work_batch.to_dict(),
                'remaining_to_issue': (job_work.quantity_to_issue or 0) - job_work.quantity_issued,
                'message': 'Partial material issued successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error issuing partial material: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def receive_partial_output(job_work_id, partial_receipt_data):
        """Receive partial output from job work"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            if job_work.status not in ['sent', 'partial_received']:
                return {'success': False, 'error': f'Cannot receive material - job work is {job_work.status}'}
            
            # Validate partial receipt quantity
            receipt_qty = partial_receipt_data['receipt_quantity']
            scrap_qty = partial_receipt_data.get('scrap_quantity', 0)
            total_processed = receipt_qty + scrap_qty
            
            remaining_to_receive = (job_work.quantity_issued or 0) - (job_work.quantity_received or 0)
            
            if total_processed > remaining_to_receive:
                return {'success': False, 'error': f'Total processed ({total_processed}) exceeds remaining quantity ({remaining_to_receive})'}
            
            # Create GRN for partial receipt
            grn_data = {
                'supplier_id': job_work.supplier_id or 1,
                'job_work_id': job_work.id,
                'receipt_date': partial_receipt_data.get('receipt_date', datetime.utcnow().date()),
                'receipt_type': 'job_work',
                'received_by': partial_receipt_data.get('received_by', 1),
                'remarks': partial_receipt_data.get('remarks', ''),
                'gate_pass_no': partial_receipt_data.get('gate_pass_no', ''),
                'vehicle_no': partial_receipt_data.get('vehicle_no', ''),
                'created_by': partial_receipt_data.get('created_by', 1),
                'line_items': [{
                    'item_id': job_work.output_item_id or job_work.input_material_id,
                    'quantity_received': receipt_qty,
                    'quantity_accepted': receipt_qty,
                    'quantity_rejected': 0,
                    'scrap_quantity': scrap_qty,
                    'uom': job_work.input_uom or 'Pcs',
                    'material_state': 'finished',
                    'quality_status': partial_receipt_data.get('quality_status', 'passed'),
                    'quality_remarks': partial_receipt_data.get('quality_remarks', ''),
                    'batch_code': f"JW-{job_work.job_number}-P{datetime.now().strftime('%Y%m%d')}"
                }]
            }
            
            # Create GRN for material receipt (Step 1)
            grn_result = GRNService.create_material_receipt(grn_data)
            if not grn_result['success']:
                return {'success': False, 'error': f"GRN creation failed: {grn_result['error']}"}
            
            # Update job work quantities
            job_work.quantity_received = (job_work.quantity_received or 0) + receipt_qty
            job_work.scrap_quantity = (job_work.scrap_quantity or 0) + scrap_qty
            
            # Update status based on completion
            if job_work.quantity_received >= job_work.quantity_issued:
                job_work.status = 'completed'
                job_work.completion_date = datetime.utcnow().date()
                
                # Calculate final costs
                costing_result = CostingService.calculate_job_work_cost(job_work.id)
                if not costing_result['success']:
                    logger.warning(f"Cost calculation failed for job work {job_work.job_number}")
            else:
                job_work.status = 'partial_received'
            
            # Update job work batches
            job_work_batches = JobWorkBatch.query.filter_by(
                job_work_id=job_work.id,
                status='issued'
            ).all()
            
            remaining_receipt = receipt_qty
            for batch in job_work_batches:
                if remaining_receipt <= 0:
                    break
                
                if batch.issued_quantity <= remaining_receipt:
                    batch.received_quantity = batch.issued_quantity
                    batch.status = 'received'
                    remaining_receipt -= batch.issued_quantity
                else:
                    batch.received_quantity = remaining_receipt
                    batch.status = 'partial_received'
                    remaining_receipt = 0
            
            db.session.commit()
            
            logger.info(f"Partial output received for job work {job_work.job_number}: {receipt_qty} units")
            
            return {
                'success': True,
                'grn': grn_result['grn'],
                'job_work_status': job_work.status,
                'remaining_to_receive': (job_work.quantity_issued or 0) - job_work.quantity_received,
                'message': 'Partial output received successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error receiving partial output: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_partial_job_status(job_work_id):
        """Get comprehensive partial job work status"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            # Get all job work batches
            job_work_batches = JobWorkBatch.query.filter_by(job_work_id=job_work.id).all()
            
            # Calculate progress
            total_to_issue = job_work.quantity_to_issue or 0
            total_issued = job_work.quantity_issued or 0
            total_received = job_work.quantity_received or 0
            total_scrap = job_work.scrap_quantity or 0
            
            issue_progress = (total_issued / total_to_issue * 100) if total_to_issue > 0 else 0
            receipt_progress = (total_received / total_issued * 100) if total_issued > 0 else 0
            
            # Get batch details
            batch_details = []
            for batch in job_work_batches:
                batch_info = {
                    'id': batch.id,
                    'issued_quantity': batch.issued_quantity,
                    'received_quantity': batch.received_quantity or 0,
                    'issued_date': batch.issued_date.isoformat() if batch.issued_date else None,
                    'status': batch.status,
                    'gate_pass_no': batch.gate_pass_no,
                    'remarks': batch.remarks
                }
                batch_details.append(batch_info)
            
            return {
                'success': True,
                'job_work': {
                    'id': job_work.id,
                    'job_number': job_work.job_number,
                    'status': job_work.status,
                    'work_type': job_work.work_type
                },
                'quantities': {
                    'to_issue': total_to_issue,
                    'issued': total_issued,
                    'received': total_received,
                    'scrap': total_scrap,
                    'remaining_to_issue': total_to_issue - total_issued,
                    'remaining_to_receive': total_issued - total_received
                },
                'progress': {
                    'issue_percentage': round(issue_progress, 2),
                    'receipt_percentage': round(receipt_progress, 2)
                },
                'batch_details': batch_details
            }
            
        except Exception as e:
            logger.error(f"Error getting partial job status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def handle_multi_stage_delivery(job_work_id, stage_data):
        """Handle multi-stage delivery to different vendors"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            results = []
            
            # Process each stage delivery
            for stage in stage_data['stages']:
                # Issue material to vendor
                partial_issue_result = PartialJobService.issue_partial_material(
                    job_work_id, {
                        'issue_quantity': stage['quantity'],
                        'source_batch_id': stage['source_batch_id'],
                        'issue_date': stage.get('delivery_date', datetime.utcnow().date()),
                        'gate_pass_no': stage.get('gate_pass_no', ''),
                        'vehicle_no': stage.get('vehicle_no', ''),
                        'remarks': f"Stage {stage['stage_number']} delivery to {stage['vendor_name']}",
                        'issued_by': stage_data.get('issued_by', 1)
                    }
                )
                
                if partial_issue_result['success']:
                    # Create tracking record for this stage
                    from models.batch import BatchTraceability
                    
                    stage_tracking = BatchTraceability(
                        source_batch_id=stage['source_batch_id'],
                        job_work_id=job_work.id,
                        transformation_type='multi_stage_delivery',
                        input_quantity=stage['quantity'],
                        process_date=stage.get('delivery_date', datetime.utcnow().date()),
                        process_notes=f"Stage {stage['stage_number']}: {stage['vendor_name']} - {stage.get('process_type', 'Processing')}",
                        vendor_name=stage['vendor_name'],
                        stage_number=stage['stage_number']
                    )
                    
                    db.session.add(stage_tracking)
                    
                    results.append({
                        'stage': stage['stage_number'],
                        'vendor': stage['vendor_name'],
                        'quantity': stage['quantity'],
                        'status': 'delivered',
                        'job_work_batch_id': partial_issue_result['job_work_batch']['id']
                    })
                else:
                    results.append({
                        'stage': stage['stage_number'],
                        'vendor': stage['vendor_name'],
                        'quantity': stage['quantity'],
                        'status': 'failed',
                        'error': partial_issue_result['error']
                    })
            
            db.session.commit()
            
            successful_stages = len([r for r in results if r['status'] == 'delivered'])
            total_stages = len(results)
            
            return {
                'success': True,
                'stages_processed': total_stages,
                'successful_deliveries': successful_stages,
                'failed_deliveries': total_stages - successful_stages,
                'stage_results': results,
                'message': f'Multi-stage delivery processed: {successful_stages}/{total_stages} successful'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling multi-stage delivery: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_partial_jobs_dashboard():
        """Get dashboard metrics for partial jobs"""
        try:
            metrics = {
                'total_partial_jobs': JobWork.query.filter(
                    JobWork.status.in_(['partial_issued', 'partial_received'])
                ).count(),
                'pending_issues': JobWork.query.filter_by(status='partial_issued').count(),
                'pending_receipts': JobWork.query.filter_by(status='partial_received').count(),
                'completed_today': JobWork.query.filter(
                    JobWork.status == 'completed',
                    JobWork.completion_date == datetime.utcnow().date()
                ).count()
            }
            
            # Get recent partial activities
            recent_partial_jobs = JobWork.query.filter(
                JobWork.status.in_(['partial_issued', 'partial_received'])
            ).order_by(JobWork.updated_at.desc()).limit(10).all()
            
            partial_jobs_data = []
            for job in recent_partial_jobs:
                status_result = PartialJobService.get_partial_job_status(job.id)
                if status_result['success']:
                    partial_jobs_data.append(status_result)
            
            return {
                'success': True,
                'metrics': metrics,
                'recent_partial_jobs': partial_jobs_data
            }
            
        except Exception as e:
            logger.error(f"Error getting partial jobs dashboard: {str(e)}")
            return {'success': False, 'error': str(e)}