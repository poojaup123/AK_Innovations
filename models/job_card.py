from app import db
from datetime import datetime, date
from sqlalchemy import func

class JobCard(db.Model):
    __tablename__ = 'job_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    job_card_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Production Order Reference
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    production = db.relationship('Production', backref='job_cards')
    
    # Item/Component Details
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    item = db.relationship('Item', backref='job_cards')
    
    # Process Information
    process_name = db.Column(db.String(200), nullable=False)
    process_sequence = db.Column(db.Integer, default=1)  # Order of operations
    operation_description = db.Column(db.Text)
    
    # Quantities
    planned_quantity = db.Column(db.Float, nullable=False, default=0)
    completed_quantity = db.Column(db.Float, default=0)
    good_quantity = db.Column(db.Float, default=0)
    defective_quantity = db.Column(db.Float, default=0)
    scrap_quantity = db.Column(db.Float, default=0)
    
    # Assignment
    assigned_worker_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    assigned_worker = db.relationship('Employee', backref='job_cards')
    assigned_vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))  # For outsourced work
    assigned_vendor = db.relationship('Supplier', backref='job_cards')
    
    # Machine/Workstation
    machine_workstation = db.Column(db.String(100))
    setup_time_minutes = db.Column(db.Float, default=0)
    run_time_minutes = db.Column(db.Float, default=0)
    
    # Scheduling
    planned_start_date = db.Column(db.Date)
    planned_end_date = db.Column(db.Date)
    actual_start_date = db.Column(db.Date)
    actual_end_date = db.Column(db.Date)
    target_completion_date = db.Column(db.Date, nullable=False)
    
    # Status
    status = db.Column(db.String(50), default='planned')  # planned, in_progress, completed, on_hold, cancelled
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    
    # Cost Tracking
    estimated_cost = db.Column(db.Float, default=0)
    actual_cost = db.Column(db.Float, default=0)
    material_cost = db.Column(db.Float, default=0)
    labor_cost = db.Column(db.Float, default=0)
    overhead_cost = db.Column(db.Float, default=0)
    
    # Progress Tracking
    progress_percentage = db.Column(db.Float, default=0)
    quality_notes = db.Column(db.Text)
    production_notes = db.Column(db.Text)
    delay_reason = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.relationship('User', backref='created_job_cards')
    
    def __repr__(self):
        return f'<JobCard {self.job_card_number}>'
    
    @property
    def is_overdue(self):
        """Check if job card is overdue"""
        if self.status in ['completed', 'cancelled']:
            return False
        return date.today() > self.target_completion_date
    
    @property
    def days_remaining(self):
        """Calculate days remaining until target completion"""
        if self.status in ['completed', 'cancelled']:
            return 0
        delta = self.target_completion_date - date.today()
        return delta.days
    
    @property
    def efficiency_rate(self):
        """Calculate efficiency rate (good quantity / total completed)"""
        if self.completed_quantity == 0:
            return 0
        return (self.good_quantity / self.completed_quantity) * 100
    
    @property
    def completion_rate(self):
        """Calculate completion rate against planned quantity"""
        if self.planned_quantity == 0:
            return 0
        return (self.completed_quantity / self.planned_quantity) * 100
    
    @classmethod
    def generate_job_card_number(cls, production_number, sequence):
        """Generate unique job card number"""
        return f"JC-{production_number}-{sequence:03d}"
    
    def update_progress(self):
        """Auto-calculate progress percentage"""
        if self.planned_quantity > 0:
            self.progress_percentage = min(100, (self.completed_quantity / self.planned_quantity) * 100)
        
        # Auto-update status based on progress
        if self.progress_percentage == 0:
            self.status = 'planned'
        elif self.progress_percentage == 100:
            self.status = 'completed'
            if not self.actual_end_date:
                self.actual_end_date = date.today()
        elif self.progress_percentage > 0:
            self.status = 'in_progress'
            if not self.actual_start_date:
                self.actual_start_date = date.today()


class JobCardDailyStatus(db.Model):
    __tablename__ = 'job_card_daily_status'
    
    id = db.Column(db.Integer, primary_key=True)
    job_card_id = db.Column(db.Integer, db.ForeignKey('job_cards.id'), nullable=False)
    job_card = db.relationship('JobCard', backref='daily_status_reports')
    
    report_date = db.Column(db.Date, nullable=False, default=date.today)
    
    # Daily Production Quantities
    qty_completed_today = db.Column(db.Float, default=0)
    qty_good_today = db.Column(db.Float, default=0)
    qty_defective_today = db.Column(db.Float, default=0)
    qty_scrap_today = db.Column(db.Float, default=0)
    
    # Cumulative Totals
    cumulative_completed = db.Column(db.Float, default=0)
    cumulative_good = db.Column(db.Float, default=0)
    cumulative_defective = db.Column(db.Float, default=0)
    cumulative_scrap = db.Column(db.Float, default=0)
    
    # Time Tracking
    hours_worked = db.Column(db.Float, default=0)
    setup_time_actual = db.Column(db.Float, default=0)
    run_time_actual = db.Column(db.Float, default=0)
    downtime_minutes = db.Column(db.Float, default=0)
    
    # Status Workflow
    daily_status = db.Column(db.String(50), default='active')  # active, completed, delayed, on_hold
    status_after_entry = db.Column(db.String(50))  # planned, in_progress, completed, pending_approval
    
    # Process Reference (for future multi-process job cards)
    process_step = db.Column(db.String(100))  # Simple text field for now
    
    # Batch Integration (simplified for now)
    batch_number = db.Column(db.String(50))  # Simple batch reference
    
    # QC Integration
    qc_approved = db.Column(db.Boolean, default=False)
    qc_rejected = db.Column(db.Boolean, default=False)
    qc_notes = db.Column(db.Text)
    qc_approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    qc_approved_by = db.relationship('User', foreign_keys=[qc_approved_by_id], backref='qc_approvals')
    qc_approved_at = db.Column(db.DateTime)
    
    # Supervisor Approval Workflow
    supervisor_approved = db.Column(db.Boolean, default=False)
    supervisor_rejected = db.Column(db.Boolean, default=False)
    supervisor_notes = db.Column(db.Text)
    supervisor_approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    supervisor_approved_by = db.relationship('User', foreign_keys=[supervisor_approved_by_id], backref='supervisor_approvals')
    supervisor_approved_at = db.Column(db.DateTime)
    
    # Outsourced Work Integration
    grn_required = db.Column(db.Boolean, default=False)
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'))
    grn = db.relationship('GRN', backref='job_card_reports')
    grn_auto_created = db.Column(db.Boolean, default=False)
    
    # Issues and Notes
    quality_issues = db.Column(db.Text)
    production_issues = db.Column(db.Text)
    material_issues = db.Column(db.Text)
    machine_issues = db.Column(db.Text)
    operator_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reported_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reported_by = db.relationship('User', foreign_keys=[reported_by_id], backref='job_card_reports')
    
    __table_args__ = (db.UniqueConstraint('job_card_id', 'report_date'),)
    
    def __repr__(self):
        return f'<JobCardDailyStatus {self.job_card.job_card_number} - {self.report_date}>'
    
    @property
    def efficiency_rate(self):
        """Calculate daily efficiency rate"""
        if self.qty_completed_today == 0:
            return 0
        return (self.qty_good_today / self.qty_completed_today) * 100
    
    @classmethod
    def get_today_report(cls, job_card_id):
        """Get today's report for a job card"""
        return cls.query.filter_by(
            job_card_id=job_card_id,
            report_date=date.today()
        ).first()
    
    @classmethod
    def create_or_update_today(cls, job_card_id, **kwargs):
        """Create or update today's report"""
        today_report = cls.get_today_report(job_card_id)
        
        if today_report:
            # Update existing report
            for key, value in kwargs.items():
                if hasattr(today_report, key):
                    setattr(today_report, key, value)
            today_report.updated_at = datetime.utcnow()
        else:
            # Create new report
            today_report = cls(
                job_card_id=job_card_id,
                report_date=date.today(),
                **kwargs
            )
            db.session.add(today_report)
        
        # Update job card quantities
        job_card = JobCard.query.get(job_card_id)
        if job_card:
            job_card.completed_quantity = kwargs.get('cumulative_completed', job_card.completed_quantity)
            job_card.good_quantity = kwargs.get('cumulative_good', job_card.good_quantity)
            job_card.defective_quantity = kwargs.get('cumulative_defective', job_card.defective_quantity)
            job_card.scrap_quantity = kwargs.get('cumulative_scrap', job_card.scrap_quantity)
            job_card.update_progress()
        
        db.session.commit()
        return today_report
    
    def approve_by_supervisor(self, supervisor_id, notes=None):
        """Approve daily status by supervisor"""
        self.supervisor_approved = True
        self.supervisor_rejected = False
        self.supervisor_approved_by_id = supervisor_id
        self.supervisor_approved_at = datetime.utcnow()
        if notes:
            self.supervisor_notes = notes
        
        # Update status after approval
        if self.daily_status == 'completed':
            self.status_after_entry = 'completed'
        else:
            self.status_after_entry = 'in_progress'
        
        # Auto-create GRN for outsourced work if needed
        if self.job_card.assigned_vendor_id and self.qty_completed_today > 0:
            self.grn_required = True
            self._auto_create_grn()
        
        db.session.commit()
    
    def reject_by_supervisor(self, supervisor_id, notes):
        """Reject daily status by supervisor"""
        self.supervisor_approved = False
        self.supervisor_rejected = True
        self.supervisor_approved_by_id = supervisor_id
        self.supervisor_approved_at = datetime.utcnow()
        self.supervisor_notes = notes
        self.status_after_entry = 'pending_approval'
        db.session.commit()
    
    def approve_by_qc(self, qc_inspector_id, notes=None):
        """Approve daily status by QC"""
        self.qc_approved = True
        self.qc_rejected = False
        self.qc_approved_by_id = qc_inspector_id
        self.qc_approved_at = datetime.utcnow()
        if notes:
            self.qc_notes = notes
        
        # Auto-create good quantity batch if approved
        if self.qty_good_today > 0:
            self._create_good_batch()
        
        db.session.commit()
    
    def reject_by_qc(self, qc_inspector_id, notes):
        """Reject daily status by QC"""
        self.qc_approved = False
        self.qc_rejected = True
        self.qc_approved_by_id = qc_inspector_id
        self.qc_approved_at = datetime.utcnow()
        self.qc_notes = notes
        
        # Auto-create scrap batch for rejected quantities
        if self.qty_completed_today > 0:
            self._create_scrap_batch()
        
        db.session.commit()
    
    def _auto_create_grn(self):
        """Auto-create GRN for outsourced work"""
        from models.grn import GRN, GRNLineItem
        
        if not self.grn_auto_created and self.job_card.assigned_vendor_id:
            # Create GRN for outsourced work receipt
            grn = GRN(
                grn_number=GRN.generate_grn_number(),
                supplier_id=self.job_card.assigned_vendor_id,
                grn_type='job_work',
                status='pending',
                remarks=f'Auto-created for Job Card {self.job_card.job_card_number}',
                created_by_id=self.reported_by_id
            )
            db.session.add(grn)
            db.session.flush()
            
            # Add line item
            line_item = GRNLineItem(
                grn_id=grn.id,
                item_id=self.job_card.item_id,
                quantity_received=self.qty_completed_today,
                quantity_accepted=self.qty_good_today,
                quantity_rejected=self.qty_defective_today
            )
            db.session.add(line_item)
            
            self.grn_id = grn.id
            self.grn_auto_created = True
    
    def _create_good_batch(self):
        """Create batch for good quantity - simplified"""
        if self.qty_good_today > 0:
            # For now, just assign a batch number
            self.batch_number = f"GOOD-{self.job_card.job_card_number}-{self.report_date.strftime('%Y%m%d')}"
    
    def _create_scrap_batch(self):
        """Create batch for scrap quantity - simplified"""
        if self.qty_scrap_today > 0:
            # For now, just assign a batch number
            self.batch_number = f"SCRAP-{self.job_card.job_card_number}-{self.report_date.strftime('%Y%m%d')}"


class JobCardMaterial(db.Model):
    __tablename__ = 'job_card_materials'
    
    id = db.Column(db.Integer, primary_key=True)
    job_card_id = db.Column(db.Integer, db.ForeignKey('job_cards.id'), nullable=False)
    job_card = db.relationship('JobCard', backref='materials')
    
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    item = db.relationship('Item', backref='job_card_materials')
    
    # Material Requirements
    quantity_required = db.Column(db.Float, nullable=False)
    quantity_issued = db.Column(db.Float, default=0)
    quantity_consumed = db.Column(db.Float, default=0)
    quantity_returned = db.Column(db.Float, default=0)
    
    # Cost
    unit_cost = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    
    # Status
    issue_status = db.Column(db.String(50), default='pending')  # pending, issued, partial, complete
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<JobCardMaterial {self.item.name} for {self.job_card.job_card_number}>'