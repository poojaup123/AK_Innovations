"""
Job Card and Job Work Integration Service

This service handles the seamless integration between Job Cards and Job Work,
enabling dynamic switching between in-house and outsourced production processes.
"""

from datetime import datetime, date
from app import db
from models import JobCard, JobWork, Production, Item, Supplier
from models.grn import GRN
from models.batch import InventoryBatch, BatchMovement
from services.notifications import NotificationService
import json

class JobCardJobWorkIntegration:
    
    @staticmethod
    def outsource_job_card(job_card_id, vendor_id, expected_return_date=None, notes=None):
        """
        Convert an in-house job card to outsourced job work
        
        Args:
            job_card_id: ID of the job card to outsource
            vendor_id: ID of the vendor/supplier to assign work to
            expected_return_date: Expected date for work completion
            notes: Additional notes for outsourcing
        
        Returns:
            JobWork: Created job work instance
        """
        job_card = JobCard.query.get_or_404(job_card_id)
        vendor = Supplier.query.get_or_404(vendor_id)
        
        # Validate job card can be outsourced
        if job_card.status == 'completed':
            raise ValueError("Cannot outsource completed job card")
        
        if job_card.job_work_id:
            raise ValueError("Job card is already linked to job work")
        
        # Create job work entry
        job_work = JobWork(
            job_number=JobCardJobWorkIntegration._generate_job_number(),
            customer_name=job_card.production.customer_name if job_card.production else "Internal Production",
            item_id=job_card.item_id,
            process=job_card.process_name,
            work_type='outsourced',
            quantity_sent=job_card.planned_quantity,
            rate_per_unit=JobCardJobWorkIntegration._get_vendor_rate(job_card.item_id, vendor_id),
            sent_date=date.today(),
            expected_return=expected_return_date or job_card.target_completion_date,
            status='sent',
            notes=notes,
            created_by=1,  # Will be replaced with current user in actual implementation
            production_id=job_card.production_id,
            source_job_card_id=job_card.id
        )
        
        db.session.add(job_work)
        db.session.flush()
        
        # Update job card
        job_card.job_work_id = job_work.id
        job_card.job_type = 'outsourced'
        job_card.assigned_vendor_id = vendor_id
        job_card.status = 'outsourced'
        job_card.auto_created_job_work = True
        job_card.expected_return_date = expected_return_date
        job_card.outsource_notes = notes
        job_card.outsource_quantity = job_card.planned_quantity
        
        # Issue materials to job work (batch tracking)
        JobCardJobWorkIntegration._issue_materials_to_job_work(job_card, job_work)
        
        db.session.commit()
        
        # Send notification (placeholder - will implement when needed)
        # NotificationService.create_job_work_notification(
        #     job_work_id=job_work.id,
        #     message=f"Job Card {job_card.job_card_number} outsourced to {vendor.name}",
        #     notification_type='job_outsourced'
        # )
        
        return job_work
    
    @staticmethod
    def receive_outsourced_work(job_work_id, grn_id, received_quantity, quality_status='passed'):
        """
        Process receipt of outsourced work through GRN
        
        Args:
            job_work_id: ID of the job work being received
            grn_id: ID of the GRN documenting the receipt
            received_quantity: Actual quantity received
            quality_status: Quality check result
        
        Returns:
            bool: Success status
        """
        job_work = JobWork.query.get_or_404(job_work_id)
        grn = GRN.query.get_or_404(grn_id)
        
        # Update job work
        job_work.quantity_received += received_quantity
        job_work.received_date = date.today()
        
        if job_work.quantity_received >= job_work.quantity_sent:
            job_work.status = 'completed'
        else:
            job_work.status = 'partial_received'
        
        # Update linked job cards
        for job_card in job_work.linked_job_cards:
            job_card.grn_id = grn_id
            job_card.grn_received_quantity += received_quantity
            job_card.grn_received_date = date.today()
            job_card.completed_quantity += received_quantity
            
            if quality_status == 'passed':
                job_card.good_quantity += received_quantity
                job_card.quality_check_status = 'passed'
            else:
                job_card.defective_quantity += received_quantity
                job_card.quality_check_status = 'failed'
            
            # Update job card status
            if job_card.completed_quantity >= job_card.planned_quantity:
                job_card.status = 'completed'
                job_card.actual_end_date = date.today()
                job_card.progress_percentage = 100.0
            else:
                job_card.status = 'partial_complete'
                job_card.progress_percentage = (job_card.completed_quantity / job_card.planned_quantity) * 100
        
        # Create output batches for received material
        JobCardJobWorkIntegration._create_output_batches(job_work, grn, received_quantity)
        
        db.session.commit()
        
        # Send completion notification (placeholder - will implement when needed)
        # NotificationService.create_job_work_notification(
        #     job_work_id=job_work.id,
        #     message=f"Job Work {job_work.job_number} received: {received_quantity} units",
        #     notification_type='job_received'
        # )
        
        return True
    
    @staticmethod
    def switch_to_inhouse(job_card_id, department=None, assigned_worker_id=None):
        """
        Switch an outsourced job card back to in-house processing
        
        Args:
            job_card_id: ID of the job card to bring in-house
            department: Department to assign work to
            assigned_worker_id: Worker to assign the job to
        
        Returns:
            bool: Success status
        """
        job_card = JobCard.query.get_or_404(job_card_id)
        
        if job_card.job_type != 'outsourced':
            raise ValueError("Job card is not currently outsourced")
        
        if job_card.status == 'completed':
            raise ValueError("Cannot switch completed job card")
        
        # Cancel linked job work if not yet sent
        if job_card.job_work and job_card.job_work.status == 'sent':
            job_card.job_work.status = 'cancelled'
            job_card.job_work.notes = (job_card.job_work.notes or '') + "\nCancelled - switched to in-house processing"
        
        # Update job card
        job_card.job_type = 'in_house'
        job_card.department = department
        job_card.assigned_worker_id = assigned_worker_id
        job_card.assigned_vendor_id = None
        job_card.status = 'planned'
        
        db.session.commit()
        
        return True
    
    @staticmethod
    def get_job_card_status_summary(production_id=None):
        """
        Get comprehensive status summary of job cards and their integration with job work
        
        Args:
            production_id: Optional production order ID to filter by
        
        Returns:
            dict: Status summary with counts and details
        """
        query = JobCard.query
        if production_id:
            query = query.filter_by(production_id=production_id)
        
        job_cards = query.all()
        
        summary = {
            'total_job_cards': len(job_cards),
            'in_house': 0,
            'outsourced': 0,
            'completed': 0,
            'pending': 0,
            'overdue': 0,
            'linked_job_works': 0,
            'pending_receipts': 0,
            'details': []
        }
        
        for job_card in job_cards:
            # Count by type
            if job_card.job_type == 'in_house':
                summary['in_house'] += 1
            else:
                summary['outsourced'] += 1
            
            # Count by status
            if job_card.status == 'completed':
                summary['completed'] += 1
            else:
                summary['pending'] += 1
            
            # Check overdue
            if job_card.is_overdue:
                summary['overdue'] += 1
            
            # Check job work links
            if job_card.job_work_id:
                summary['linked_job_works'] += 1
                if job_card.job_work.status in ['sent', 'partial_received']:
                    summary['pending_receipts'] += 1
            
            # Add to details
            summary['details'].append({
                'id': job_card.id,
                'job_card_number': job_card.job_card_number,
                'item_name': job_card.item.name if job_card.item else 'Unknown',
                'process': job_card.process_name,
                'type': job_card.job_type,
                'status': job_card.status,
                'planned_quantity': job_card.planned_quantity,
                'completed_quantity': job_card.completed_quantity,
                'progress': job_card.progress_percentage,
                'is_overdue': job_card.is_overdue,
                'job_work_number': job_card.job_work.job_number if job_card.job_work else None,
                'vendor_name': job_card.assigned_vendor.name if job_card.assigned_vendor else None
            })
        
        return summary
    
    @staticmethod
    def _generate_job_number():
        """Generate unique job work number"""
        last_job = JobWork.query.order_by(JobWork.id.desc()).first()
        if last_job and last_job.job_number.startswith('JW-'):
            try:
                last_num = int(last_job.job_number.split('-')[1])
                return f"JW-{last_num + 1:06d}"
            except (ValueError, IndexError):
                pass
        return "JW-000001"
    
    @staticmethod
    def _get_vendor_rate(item_id, vendor_id):
        """Get vendor rate for item (placeholder - implement actual rate lookup)"""
        # This should lookup actual vendor rates from a rates table
        return 100.0  # Default rate
    
    @staticmethod
    def _issue_materials_to_job_work(job_card, job_work):
        """Issue materials from inventory to job work (batch tracking)"""
        # This would implement actual batch allocation and movement tracking
        # For now, just log the material issue
        if job_card.input_batch_numbers:
            try:
                batch_numbers = json.loads(job_card.input_batch_numbers)
                for batch_number in batch_numbers:
                    # Create batch movement record
                    movement = BatchMovement(
                        batch_code=batch_number,
                        movement_type='issue_to_jobwork',
                        quantity=job_card.planned_quantity / len(batch_numbers),
                        reference_type='job_work',
                        reference_id=job_work.id,
                        reference_number=job_work.job_number,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(movement)
            except (json.JSONDecodeError, TypeError):
                pass
    
    @staticmethod
    def _create_output_batches(job_work, grn, received_quantity):
        """Create output batches for received material"""
        # Create new batch for received processed material
        if received_quantity > 0:
            new_batch = InventoryBatch(
                batch_code=f"JW-OUT-{job_work.job_number}-{datetime.now().strftime('%Y%m%d')}",
                item_id=job_work.item_id,
                quantity=received_quantity,
                unit_cost=job_work.rate_per_unit,
                source_type='job_work_receipt',
                source_reference=job_work.job_number,
                grn_id=grn.id,
                created_at=datetime.utcnow()
            )
            db.session.add(new_batch)