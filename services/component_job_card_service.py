from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import ComponentJobCard, ComponentJobCardProcess, Production, BOM, BOMItem, BOMProcess, Item, User
import json

class ComponentJobCardService:
    """Service layer for Component Job Card management"""
    
    @staticmethod
    def create_job_cards_for_production(production_id, created_by_id):
        """Create component job cards for a production order"""
        try:
            production = Production.query.get(production_id)
            if not production or not production.bom_id:
                return False, "Production order or BOM not found"
            
            # Check if job cards already exist for this production
            existing_cards = ComponentJobCard.query.filter_by(production_id=production_id).first()
            if existing_cards:
                return False, "Job cards already exist for this production order"
            
            return ComponentJobCard.create_job_cards_from_production(production_id, created_by_id)
            
        except Exception as e:
            return False, f"Error creating job cards: {str(e)}"
    
    @staticmethod
    def get_dashboard_data():
        """Get dashboard summary data for component job cards"""
        today = date.today()
        
        # Today's active job cards
        today_cards = ComponentJobCard.query.filter(
            ComponentJobCard.target_completion_date == today,
            ComponentJobCard.status.in_(['planned', 'issued', 'in_progress'])
        ).all()
        
        # Overdue job cards
        overdue_cards = ComponentJobCard.query.filter(
            ComponentJobCard.target_completion_date < today,
            ComponentJobCard.status.in_(['planned', 'issued', 'in_progress'])
        ).all()
        
        # Status summary
        status_summary = db.session.query(
            ComponentJobCard.status,
            func.count(ComponentJobCard.id).label('count')
        ).group_by(ComponentJobCard.status).all()
        
        # Priority summary
        priority_summary = db.session.query(
            ComponentJobCard.priority,
            func.count(ComponentJobCard.id).label('count')
        ).filter(ComponentJobCard.status != 'completed').group_by(ComponentJobCard.priority).all()
        
        # Recent completions (last 7 days)
        seven_days_ago = date.today() - timedelta(days=7)
        recent_completions = ComponentJobCard.query.filter(
            ComponentJobCard.status == 'completed',
            ComponentJobCard.completed_at >= seven_days_ago
        ).count()
        
        return {
            'today_cards': today_cards,
            'overdue_cards': overdue_cards,
            'status_summary': dict(status_summary),
            'priority_summary': dict(priority_summary),
            'recent_completions': recent_completions,
            'total_active': len(today_cards) + len(overdue_cards)
        }
    
    @staticmethod
    def get_todays_job_cards():
        """Get all job cards scheduled for today"""
        today = date.today()
        
        return ComponentJobCard.query.filter(
            or_(
                ComponentJobCard.target_completion_date == today,
                and_(
                    ComponentJobCard.status.in_(['in_progress', 'issued']),
                    ComponentJobCard.target_completion_date <= today
                )
            )
        ).order_by(
            ComponentJobCard.priority.desc(),
            ComponentJobCard.target_completion_date.asc()
        ).all()
    
    @staticmethod
    def get_job_card_details(job_card_id):
        """Get detailed information for a specific job card"""
        job_card = ComponentJobCard.query.get(job_card_id)
        if not job_card:
            return None
        
        # Parse process steps if available
        process_steps = []
        if job_card.process_steps:
            try:
                process_steps = json.loads(job_card.process_steps)
            except json.JSONDecodeError:
                process_steps = []
        
        # Get material availability
        component = job_card.component
        available_stock = component.total_stock if component else 0
        stock_status = 'sufficient' if available_stock >= job_card.remaining_quantity else 'insufficient'
        
        return {
            'job_card': job_card,
            'process_steps': process_steps,
            'available_stock': available_stock,
            'stock_status': stock_status,
            'stock_shortage': max(0, job_card.remaining_quantity - available_stock)
        }
    
    @staticmethod
    def update_job_card_progress(job_card_id, quantity_consumed, process_step=None, worker_id=None, notes=None):
        """Update progress on a job card"""
        try:
            job_card = ComponentJobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Update assigned worker if provided
            if worker_id:
                job_card.assigned_worker_id = worker_id
            
            # Update progress
            success = job_card.update_progress(quantity_consumed, process_step, notes)
            if not success:
                return False, "Failed to update progress"
            
            db.session.commit()
            return True, "Progress updated successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error updating progress: {str(e)}"
    
    @staticmethod
    def assign_job_card(job_card_id, worker_id=None, vendor_id=None, department=None, target_date=None):
        """Assign a job card to worker/vendor"""
        try:
            job_card = ComponentJobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Update assignments
            if worker_id:
                job_card.assigned_worker_id = worker_id
                job_card.work_type = 'in_house'
            elif vendor_id:
                job_card.assigned_vendor_id = vendor_id
                job_card.work_type = 'outsourced'
            
            if department:
                job_card.assigned_department = department
            
            if target_date:
                job_card.target_completion_date = target_date
            
            # Update status to issued if it was planned
            if job_card.status == 'planned':
                job_card.status = 'issued'
            
            db.session.commit()
            return True, "Job card assigned successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error assigning job card: {str(e)}"
    
    @staticmethod
    def hold_job_card(job_card_id, reason, notes=None):
        """Put a job card on hold"""
        try:
            job_card = ComponentJobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            job_card.status = 'on_hold'
            job_card.on_hold_reason = reason
            
            if notes:
                if job_card.resolution_notes:
                    job_card.resolution_notes += f"\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}: ON HOLD - {notes}"
                else:
                    job_card.resolution_notes = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}: ON HOLD - {notes}"
            
            db.session.commit()
            return True, "Job card put on hold"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error holding job card: {str(e)}"
    
    @staticmethod
    def resume_job_card(job_card_id, notes=None):
        """Resume a job card from hold"""
        try:
            job_card = ComponentJobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Determine appropriate status based on progress
            if job_card.actual_quantity_consumed > 0:
                job_card.status = 'in_progress'
            elif job_card.assigned_worker_id or job_card.assigned_vendor_id:
                job_card.status = 'issued'
            else:
                job_card.status = 'planned'
            
            job_card.on_hold_reason = None
            
            if notes:
                if job_card.resolution_notes:
                    job_card.resolution_notes += f"\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}: RESUMED - {notes}"
                else:
                    job_card.resolution_notes = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}: RESUMED - {notes}"
            
            db.session.commit()
            return True, "Job card resumed"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error resuming job card: {str(e)}"
    
    @staticmethod
    def complete_job_card(job_card_id, actual_quantity=None, scrap_quantity=0, quality_notes=None):
        """Complete a job card"""
        try:
            job_card = ComponentJobCard.query.get(job_card_id)
            if not job_card:
                return False, "Job card not found"
            
            # Update quantities if provided
            if actual_quantity is not None:
                job_card.actual_quantity_consumed = actual_quantity
                job_card.remaining_quantity = max(0, job_card.planned_quantity - actual_quantity)
            
            if scrap_quantity > 0:
                job_card.scrap_quantity = scrap_quantity
            
            # Mark as completed
            job_card.status = 'completed'
            job_card.completed_at = datetime.utcnow()
            job_card.progress_percentage = 100.0
            job_card.actual_completion_date = date.today()
            
            if quality_notes:
                job_card.inspection_notes = quality_notes
                job_card.quality_status = 'passed'
                job_card.inspection_date = datetime.utcnow()
            
            db.session.commit()
            return True, "Job card completed"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error completing job card: {str(e)}"
    
    @staticmethod
    def get_production_job_cards(production_id):
        """Get all job cards for a specific production order"""
        return ComponentJobCard.query.filter_by(production_id=production_id).order_by(
            ComponentJobCard.priority.desc(),
            ComponentJobCard.created_at.asc()
        ).all()
    
    @staticmethod
    def get_worker_job_cards(worker_id, active_only=True):
        """Get job cards assigned to a specific worker"""
        query = ComponentJobCard.query.filter_by(assigned_worker_id=worker_id)
        
        if active_only:
            query = query.filter(ComponentJobCard.status.in_(['planned', 'issued', 'in_progress', 'on_hold']))
        
        return query.order_by(
            ComponentJobCard.priority.desc(),
            ComponentJobCard.target_completion_date.asc()
        ).all()
    
    @staticmethod
    def get_analytics_data():
        """Get analytics data for job cards"""
        # Completion rate by day (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        
        daily_completions = db.session.query(
            func.date(ComponentJobCard.completed_at).label('completion_date'),
            func.count(ComponentJobCard.id).label('completed_count')
        ).filter(
            ComponentJobCard.completed_at >= thirty_days_ago,
            ComponentJobCard.status == 'completed'
        ).group_by(func.date(ComponentJobCard.completed_at)).all()
        
        # Average completion time
        avg_completion_time = db.session.query(
            func.avg(func.julianday(ComponentJobCard.completed_at) - func.julianday(ComponentJobCard.created_at)).label('avg_days')
        ).filter(ComponentJobCard.status == 'completed').scalar()
        
        # On-time completion rate
        on_time_completions = ComponentJobCard.query.filter(
            ComponentJobCard.status == 'completed',
            ComponentJobCard.actual_completion_date <= ComponentJobCard.target_completion_date
        ).count()
        
        total_completions = ComponentJobCard.query.filter(ComponentJobCard.status == 'completed').count()
        on_time_rate = (on_time_completions / total_completions * 100) if total_completions > 0 else 0
        
        return {
            'daily_completions': daily_completions,
            'avg_completion_days': round(avg_completion_time or 0, 1),
            'on_time_rate': round(on_time_rate, 1),
            'total_completions': total_completions
        }