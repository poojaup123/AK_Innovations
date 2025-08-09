"""
Unified Job Work + GRN System
Handles both in-house and outsourced job work through a single GRN flow with conditional logic.
"""

from app import db
from models import JobWork, Production, Item, User
from models.grn import GRN, GRNLineItem
from models.grn import GRNWorkflowStatus, VendorInvoice
from models.accounting import Account, Voucher, JournalEntry
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

class UnifiedJobWorkGRNService:
    """
    Service to handle unified Job Work + GRN workflow for both in-house and outsourced work.
    
    Key Features:
    - Single GRN interface for both work types
    - Conditional logic: in-house work auto-updates production, outsourced work creates payables
    - Maintains complete material traceability
    - Eliminates duplicate entry
    - Proper cost tracking for both scenarios
    """
    
    @staticmethod
    def create_grn_from_job_work(job_work_id, received_data, received_by_user_id):
        """
        Create GRN from job work completion (both in-house and outsourced).
        
        Args:
            job_work_id: JobWork ID
            received_data: List of dicts with item_id, quantity_received, quality_status, etc.
            received_by_user_id: User ID who received the materials
            
        Returns:
            dict: {'success': bool, 'grn': GRN object, 'message': str}
        """
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'message': 'Job work not found'}
            
            # Create GRN
            grn = GRN(
                grn_number=GRN.generate_grn_number(),
                job_work_id=job_work_id,
                received_date=date.today(),
                received_by=received_by_user_id,
                status='received'
            )
            
            db.session.add(grn)
            db.session.flush()  # Get GRN ID
            
            # Create GRN line items
            total_received = 0
            for item_data in received_data:
                line_item = GRNLineItem(
                    grn_id=grn.id,
                    item_id=item_data['item_id'],
                    quantity_received=item_data['quantity_received'],
                    quantity_passed=item_data.get('quantity_passed', item_data['quantity_received']),
                    quantity_rejected=item_data.get('quantity_rejected', 0),
                    unit_of_measure=item_data.get('unit_of_measure', 'pcs'),
                    process_name=job_work.process,
                    material_classification=item_data.get('material_classification', 'finished_goods'),
                    rate_per_unit=job_work.rate_per_unit,
                    inspection_status=item_data.get('quality_status', 'passed'),
                    remarks=item_data.get('remarks', '')
                )
                db.session.add(line_item)
                total_received += item_data['quantity_received']
            
            # Initialize workflow status
            workflow_status = GRNWorkflowStatus(
                grn_id=grn.id,
                material_received=True,
                material_received_date=datetime.utcnow()
            )
            db.session.add(workflow_status)
            
            # Apply conditional logic based on work type
            if job_work.work_type == 'in_house':
                result = UnifiedJobWorkGRNService._handle_in_house_completion(
                    job_work, grn, total_received, received_by_user_id
                )
            else:  # outsourced
                result = UnifiedJobWorkGRNService._handle_outsourced_completion(
                    job_work, grn, received_by_user_id
                )
            
            if not result['success']:
                db.session.rollback()
                return result
            
            # Update job work status
            job_work.quantity_received += total_received
            if job_work.quantity_received >= job_work.quantity_sent:
                job_work.status = 'completed'
                job_work.received_date = date.today()
            else:
                job_work.status = 'partial_received'
            
            db.session.commit()
            
            return {
                'success': True,
                'grn': grn,
                'message': f'GRN {grn.grn_number} created successfully for {job_work.work_type} job work'
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in create_grn_from_job_work: {str(e)}")
            return {'success': False, 'message': f'Database error: {str(e)}'}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in create_grn_from_job_work: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    @staticmethod
    def _handle_in_house_completion(job_work, grn, total_received, received_by_user_id):
        """
        Handle in-house job work completion:
        - Auto-update production records
        - Move inventory from WIP to finished goods
        - No vendor payables created
        """
        try:
            # Find related production record if exists
            production = None
            if job_work.bom_id:
                # Look for production using this BOM
                production = Production.query.filter(
                    Production.bom_id == job_work.bom_id,
                    Production.status.in_(['planned', 'in_progress'])
                ).first()
            
            if production:
                # Update production with received quantities
                production.quantity_produced = (production.quantity_produced or 0) + total_received
                production.status = 'in_progress'
                
                # Update production notes
                note = f"\n[AUTO] Updated from in-house job work {job_work.job_number} - GRN {grn.grn_number}"
                production.notes = (production.notes or "") + note
                
                logger.info(f"Updated production {production.production_number} from in-house job work")
            
            # Update inventory: move from WIP to finished goods
            item = Item.query.get(job_work.item_id)
            if item:
                # Move from process-specific WIP to finished goods
                success = item.receive_from_wip(
                    finished_qty=total_received,
                    process=job_work.process
                )
                
                if not success:
                    return {
                        'success': False,
                        'message': f'Insufficient WIP inventory for {item.name} in {job_work.process} process'
                    }
                
                logger.info(f"Updated inventory for {item.name}: moved {total_received} from WIP to finished goods")
            
            # Create internal transfer voucher (no vendor payment needed)
            voucher_result = UnifiedJobWorkGRNService._create_internal_transfer_voucher(
                job_work, grn, total_received, received_by_user_id
            )
            
            if not voucher_result['success']:
                return voucher_result
            
            return {'success': True, 'message': 'In-house job work completed successfully'}
            
        except Exception as e:
            logger.error(f"Error in _handle_in_house_completion: {str(e)}")
            return {'success': False, 'message': f'Error handling in-house completion: {str(e)}'}
    
    @staticmethod
    def _handle_outsourced_completion(job_work, grn, received_by_user_id):
        """
        Handle outsourced job work completion:
        - Create vendor payables
        - Update inventory 
        - Set up invoice/payment workflow
        """
        try:
            # Create vendor payable entry
            total_amount = job_work.quantity_received * job_work.rate_per_unit
            
            # Create GRN clearing voucher
            voucher_result = UnifiedJobWorkGRNService._create_grn_clearing_voucher(
                job_work, grn, total_amount, received_by_user_id
            )
            
            if not voucher_result['success']:
                return voucher_result
            
            # Update workflow status
            workflow_status = GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first()
            if workflow_status:
                workflow_status.grn_voucher_created = True
                workflow_status.grn_clearing_voucher_id = voucher_result['voucher'].id
            
            # Update inventory for outsourced work
            item = Item.query.get(job_work.item_id)
            if item:
                # For outsourced work, typically add to finished goods directly
                # (since WIP was managed externally)
                item.qty_finished = (item.qty_finished or 0) + job_work.quantity_received
                logger.info(f"Updated inventory for {item.name}: added {job_work.quantity_received} to finished goods")
            
            logger.info(f"Created vendor payable for outsourced job work {job_work.job_number}")
            
            return {'success': True, 'message': 'Outsourced job work completed successfully'}
            
        except Exception as e:
            logger.error(f"Error in _handle_outsourced_completion: {str(e)}")
            return {'success': False, 'message': f'Error handling outsourced completion: {str(e)}'}
    
    @staticmethod
    def _create_internal_transfer_voucher(job_work, grn, quantity, user_id):
        """Create internal transfer voucher for in-house job work (no vendor payment)"""
        try:
            # Find accounts
            wip_account = Account.query.filter_by(account_code='WIP').first()
            finished_goods_account = Account.query.filter_by(account_code='FINISHED_GOODS').first()
            
            if not wip_account or not finished_goods_account:
                return {'success': False, 'message': 'Required accounts not found'}
            
            # Calculate value
            total_value = quantity * job_work.rate_per_unit
            
            # Create voucher
            voucher = Voucher(
                voucher_number=f"JV-{grn.grn_number}",
                voucher_type='Journal',
                voucher_date=date.today(),
                reference_number=grn.grn_number,
                description=f"Internal transfer for in-house job work {job_work.job_number}",
                total_amount=total_value,
                created_by=user_id
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            # Debit: Finished Goods
            entry1 = JournalEntry(
                voucher_id=voucher.id,
                account_id=finished_goods_account.id,
                debit_amount=total_value,
                credit_amount=0,
                description=f"Transfer from WIP - {job_work.process}"
            )
            
            # Credit: WIP
            entry2 = JournalEntry(
                voucher_id=voucher.id,
                account_id=wip_account.id,
                debit_amount=0,
                credit_amount=total_value,
                description=f"Transfer to finished goods - {job_work.process}"
            )
            
            db.session.add_all([entry1, entry2])
            
            return {'success': True, 'voucher': voucher}
            
        except Exception as e:
            logger.error(f"Error creating internal transfer voucher: {str(e)}")
            return {'success': False, 'message': f'Error creating voucher: {str(e)}'}
    
    @staticmethod
    def _create_grn_clearing_voucher(job_work, grn, amount, user_id):
        """Create GRN clearing voucher for outsourced job work"""
        try:
            # Find accounts
            inventory_account = Account.query.filter_by(account_code='INVENTORY').first()
            grn_clearing_account = Account.query.filter_by(account_code='GRN_CLEARING').first()
            
            if not inventory_account or not grn_clearing_account:
                return {'success': False, 'message': 'Required accounts not found'}
            
            # Create voucher
            voucher = Voucher(
                voucher_number=f"GRN-{grn.grn_number}",
                voucher_type='Purchase',
                voucher_date=date.today(),
                reference_number=grn.grn_number,
                description=f"GRN for outsourced job work {job_work.job_number}",
                total_amount=amount,
                created_by=user_id
            )
            db.session.add(voucher)
            db.session.flush()
            
            # Create journal entries
            # Debit: Inventory
            entry1 = JournalEntry(
                voucher_id=voucher.id,
                account_id=inventory_account.id,
                debit_amount=amount,
                credit_amount=0,
                description=f"Inventory received - {job_work.process}"
            )
            
            # Credit: GRN Clearing
            entry2 = JournalEntry(
                voucher_id=voucher.id,
                account_id=grn_clearing_account.id,
                debit_amount=0,
                credit_amount=amount,
                description=f"GRN Clearing - {job_work.job_number}"
            )
            
            db.session.add_all([entry1, entry2])
            
            return {'success': True, 'voucher': voucher}
            
        except Exception as e:
            logger.error(f"Error creating GRN clearing voucher: {str(e)}")
            return {'success': False, 'message': f'Error creating voucher: {str(e)}'}
    
    @staticmethod
    def get_job_work_grn_status(job_work_id):
        """Get comprehensive status of job work through GRN workflow"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'message': 'Job work not found'}
            
            # Get all GRNs for this job work
            grns = GRN.query.filter_by(job_work_id=job_work_id).all()
            
            status_info = {
                'job_work': job_work,
                'work_type': job_work.work_type,
                'total_sent': job_work.quantity_sent,
                'total_received': job_work.quantity_received,
                'completion_percentage': (job_work.quantity_received / job_work.quantity_sent * 100) if job_work.quantity_sent > 0 else 0,
                'grns': [],
                'next_actions': []
            }
            
            for grn in grns:
                grn_info = {
                    'grn': grn,
                    'workflow_status': GRNWorkflowStatus.query.filter_by(grn_id=grn.id).first(),
                    'line_items': grn.line_items
                }
                status_info['grns'].append(grn_info)
            
            # Determine next actions based on work type and status
            if job_work.work_type == 'in_house':
                if job_work.status == 'sent':
                    status_info['next_actions'].append('Receive materials through GRN')
                elif job_work.status == 'partial_received':
                    status_info['next_actions'].append('Receive remaining materials')
                elif job_work.status == 'completed':
                    status_info['next_actions'].append('Job work completed - check production updates')
            else:  # outsourced
                if job_work.status == 'sent':
                    status_info['next_actions'].append('Receive materials through GRN')
                elif job_work.status == 'partial_received':
                    status_info['next_actions'].append('Receive remaining materials')
                elif job_work.status == 'completed':
                    # Check if invoice and payment are pending
                    for grn_info in status_info['grns']:
                        workflow = grn_info['workflow_status']
                        if workflow:
                            if not workflow.invoice_received:
                                status_info['next_actions'].append('Receive vendor invoice')
                            elif not workflow.payment_made:
                                status_info['next_actions'].append('Make payment to vendor')
            
            return {'success': True, 'status': status_info}
            
        except Exception as e:
            logger.error(f"Error getting job work GRN status: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}