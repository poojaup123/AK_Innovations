"""Status tracking models for production and job work management"""

from app import db
from datetime import datetime


class ProductionStatusHistory(db.Model):
    """Track status changes for production orders"""
    __tablename__ = 'production_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    change_reason = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Additional context
    completion_percentage_at_change = db.Column(db.Float)
    quantity_produced_at_change = db.Column(db.Float)
    notes = db.Column(db.Text)
    
    # Relationships
    production_order = db.relationship('ProductionOrder', backref='status_history')
    changed_by_user = db.relationship('User', backref='production_status_changes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'change_reason': self.change_reason,
            'changed_by': self.changed_by_user.username if self.changed_by_user else 'System',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'completion_percentage': self.completion_percentage_at_change,
            'quantity_produced': self.quantity_produced_at_change,
            'notes': self.notes
        }


class JobWorkStatusHistory(db.Model):
    """Track status changes for job work orders"""
    __tablename__ = 'job_work_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    change_reason = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Additional context
    completion_percentage_at_change = db.Column(db.Float)
    quantity_received_at_change = db.Column(db.Float)
    quality_status_at_change = db.Column(db.String(20))
    
    # Relationships
    job_work = db.relationship('JobWork', backref='status_history')
    changed_by_user = db.relationship('User', backref='job_work_status_changes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'change_reason': self.change_reason,
            'changed_by': self.changed_by_user.username if self.changed_by_user else 'System',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'completion_percentage': self.completion_percentage_at_change,
            'quantity_received': self.quantity_received_at_change,
            'quality_status': self.quality_status_at_change
        }


class StatusValidationService:
    """Service for validating and managing status transitions"""
    
    # Production Order Status Definitions
    PRODUCTION_STATUSES = {
        'pending': 'Waiting to start production',
        'in_progress': 'Production is actively running',
        'partially_completed': 'Some production completed, work continues',
        'completed': 'Production fully completed',
        'closed': 'Production closed and finalized',
        'cancelled': 'Production cancelled',
        'on_hold': 'Production temporarily halted'
    }
    
    PRODUCTION_STATUS_TRANSITIONS = {
        'pending': ['in_progress', 'cancelled', 'on_hold'],
        'in_progress': ['partially_completed', 'completed', 'on_hold', 'cancelled'],
        'partially_completed': ['in_progress', 'completed', 'on_hold'],
        'completed': ['closed'],
        'on_hold': ['in_progress', 'cancelled'],
        'cancelled': [],  # Final state
        'closed': []      # Final state
    }
    
    # Job Work Status Definitions
    JOBWORK_STATUSES = {
        'pending': 'Job work created, waiting to start',
        'in_progress': 'Work is actively being performed',
        'on_hold': 'Work temporarily paused',
        'completed': 'Work completed and returned',
        'closed': 'Job work finalized and closed',
        'cancelled': 'Job work cancelled'
    }
    
    JOBWORK_STATUS_TRANSITIONS = {
        'pending': ['in_progress', 'cancelled', 'on_hold'],
        'in_progress': ['completed', 'on_hold', 'cancelled'],
        'on_hold': ['in_progress', 'cancelled'],
        'completed': ['closed'],
        'cancelled': [],  # Final state
        'closed': []      # Final state
    }
    
    @classmethod
    def validate_production_status_transition(cls, current_status, new_status):
        """Validate if production status transition is allowed"""
        if not current_status:
            current_status = 'pending'
        
        valid_transitions = cls.PRODUCTION_STATUS_TRANSITIONS.get(current_status, [])
        return new_status in valid_transitions
    
    @classmethod
    def validate_jobwork_status_transition(cls, current_status, new_status):
        """Validate if job work status transition is allowed"""
        if not current_status:
            current_status = 'pending'
        
        valid_transitions = cls.JOBWORK_STATUS_TRANSITIONS.get(current_status, [])
        return new_status in valid_transitions
    
    @classmethod
    def get_valid_production_transitions(cls, current_status):
        """Get list of valid transitions from current production status"""
        if not current_status:
            current_status = 'pending'
        return cls.PRODUCTION_STATUS_TRANSITIONS.get(current_status, [])
    
    @classmethod
    def get_valid_jobwork_transitions(cls, current_status):
        """Get list of valid transitions from current job work status"""
        if not current_status:
            current_status = 'pending'
        return cls.JOBWORK_STATUS_TRANSITIONS.get(current_status, [])
    
    @classmethod
    def check_production_prerequisites(cls, production_order, new_status):
        """Check if production order meets prerequisites for status change"""
        errors = []
        
        if new_status == 'in_progress':
            # Check material availability
            if hasattr(production_order, 'bom') and production_order.bom:
                shortages = []
                for bom_item in production_order.bom.items:
                    material = bom_item.material or bom_item.item
                    if material:
                        required_qty = bom_item.quantity_required * production_order.quantity_ordered
                        available_qty = getattr(material, 'current_stock', 0) or 0
                        if available_qty < required_qty:
                            shortages.append(material.name)
                
                if shortages:
                    errors.append(f"Material shortages: {', '.join(shortages[:3])}")
            
            # Check if BOM exists
            if not hasattr(production_order, 'bom') or not production_order.bom:
                errors.append("No BOM associated with production order")
        
        elif new_status == 'completed':
            # Check if any quantity is produced
            if not production_order.quantity_produced or production_order.quantity_produced <= 0:
                errors.append("No production quantity recorded")
        
        return errors
    
    @classmethod
    def check_jobwork_prerequisites(cls, job_work, new_status):
        """Check if job work meets prerequisites for status change"""
        errors = []
        
        if new_status == 'completed':
            # Check if any quantity is received
            if not job_work.quantity_received or job_work.quantity_received <= 0:
                errors.append("No quantity received for job work")
        
        return errors