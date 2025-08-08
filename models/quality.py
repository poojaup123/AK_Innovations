"""
Quality Management Models
Process-specific quality templates, inspections, and KPI tracking
"""

from datetime import datetime
from app import db

class QualityTemplate(db.Model):
    """Process-specific quality inspection templates"""
    __tablename__ = 'quality_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(100), nullable=False)
    template_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Template configuration
    is_mandatory = db.Column(db.Boolean, default=True)
    auto_forward_on_pass = db.Column(db.Boolean, default=False)
    rejection_tolerance_percent = db.Column(db.Float, default=5.0)
    
    # Workflow integration
    required_for_stages = db.Column(db.Text)  # JSON array of stages where this template applies
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    checkpoints = db.relationship('QualityCheckpoint', backref='template', lazy=True, cascade='all, delete-orphan')
    inspections = db.relationship('QualityInspection', backref='template', lazy=True)
    creator = db.relationship('User', backref='created_quality_templates')
    
    def __repr__(self):
        return f'<QualityTemplate {self.template_name} for {self.process_name}>'

class QualityCheckpoint(db.Model):
    """Individual quality checkpoints within a template"""
    __tablename__ = 'quality_checkpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('quality_templates.id'), nullable=False)
    
    # Checkpoint details
    checkpoint_name = db.Column(db.String(200), nullable=False)
    checkpoint_type = db.Column(db.String(50), nullable=False)  # visual, measurement, test, document
    description = db.Column(db.Text)
    sequence_order = db.Column(db.Integer, default=1)
    
    # Criticality
    is_critical = db.Column(db.Boolean, default=False)  # Critical checkpoints must pass
    
    # Acceptance criteria
    acceptance_criteria = db.Column(db.Text)
    measurement_unit = db.Column(db.String(20))
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    reference_standard = db.Column(db.String(200))
    
    # Documentation requirements
    requires_photo = db.Column(db.Boolean, default=False)
    requires_measurement = db.Column(db.Boolean, default=False)
    requires_document = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    results = db.relationship('QualityResult', backref='checkpoint', lazy=True)
    
    def __repr__(self):
        return f'<QualityCheckpoint {self.checkpoint_name}>'

class QualityInspection(db.Model):
    """Quality inspection records for job work batches"""
    __tablename__ = 'quality_inspections'
    
    id = db.Column(db.Integer, primary_key=True)
    job_batch_id = db.Column(db.Integer, db.ForeignKey('jobwork_batches.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('quality_templates.id'), nullable=False)
    
    # Inspection details
    inspector_name = db.Column(db.String(100))
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    inspection_date = db.Column(db.Date, nullable=False)
    
    # Quantities
    quantity_inspected = db.Column(db.Float, nullable=False)
    quantity_passed = db.Column(db.Float, default=0)
    quantity_rejected = db.Column(db.Float, default=0)
    quantity_rework = db.Column(db.Float, default=0)
    
    # Results
    overall_status = db.Column(db.String(20), default='pending')  # pending, passed, rejected, partial
    pass_percentage = db.Column(db.Float)
    rejection_reason = db.Column(db.Text)
    
    # Process metrics
    inspection_duration_minutes = db.Column(db.Integer)
    defect_categories = db.Column(db.Text)  # JSON array of defect types found
    
    # Documentation
    notes = db.Column(db.Text)
    photos_attached = db.Column(db.Boolean, default=False)
    documents_attached = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_batch = db.relationship('JobWorkBatch', backref='quality_inspections')
    inspector = db.relationship('User', backref='conducted_quality_inspections')
    results = db.relationship('QualityResult', backref='inspection', lazy=True, cascade='all, delete-orphan')
    rework_records = db.relationship('QualityRework', backref='inspection', lazy=True)
    
    @property
    def defect_rate(self):
        """Calculate defect rate percentage"""
        if self.quantity_inspected > 0:
            return (self.quantity_rejected / self.quantity_inspected) * 100
        return 0
    
    @property
    def efficiency_score(self):
        """Calculate inspection efficiency score"""
        base_score = 100
        if self.pass_percentage:
            return min(base_score, self.pass_percentage)
        return 0
    
    def __repr__(self):
        return f'<QualityInspection {self.job_batch.job_work.job_number if self.job_batch else "Unknown"}>'

class QualityResult(db.Model):
    """Individual checkpoint results within an inspection"""
    __tablename__ = 'quality_results'
    
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('quality_inspections.id'), nullable=False)
    checkpoint_id = db.Column(db.Integer, db.ForeignKey('quality_checkpoints.id'), nullable=False)
    
    # Result data
    result_status = db.Column(db.String(20), nullable=False)  # pass, fail, na, conditional
    measured_value = db.Column(db.Float)
    actual_result = db.Column(db.Text)
    deviation = db.Column(db.Float)  # Deviation from standard
    
    # Analysis
    defect_severity = db.Column(db.String(20))  # minor, major, critical
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    
    # Documentation
    notes = db.Column(db.Text)
    inspector_remarks = db.Column(db.Text)
    photo_path = db.Column(db.String(500))
    document_path = db.Column(db.String(500))
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<QualityResult {self.result_status} for {self.checkpoint.checkpoint_name if self.checkpoint else "Unknown"}>'

class QualityRework(db.Model):
    """Rework records for quality failures"""
    __tablename__ = 'quality_reworks'
    
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('quality_inspections.id'), nullable=False)
    job_batch_id = db.Column(db.Integer, db.ForeignKey('jobwork_batches.id'), nullable=False)
    
    # Rework details
    rework_type = db.Column(db.String(50), nullable=False)  # standard, partial, complete
    rework_instructions = db.Column(db.Text)
    estimated_rework_time = db.Column(db.Integer)  # in hours
    rework_cost = db.Column(db.Float, default=0)
    
    # Rework execution
    rework_started_date = db.Column(db.Date)
    rework_completed_date = db.Column(db.Date)
    actual_rework_time = db.Column(db.Integer)  # in hours
    actual_rework_cost = db.Column(db.Float, default=0)
    
    # Results
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, failed
    rework_result = db.Column(db.String(20))  # passed, failed, needs_additional_rework
    quality_improvement = db.Column(db.Text)
    
    # Assignment
    assigned_to = db.Column(db.String(100))
    assigned_vendor = db.Column(db.String(100))
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_batch = db.relationship('JobWorkBatch', backref='rework_records')
    
    @property
    def rework_efficiency(self):
        """Calculate rework efficiency"""
        if self.estimated_rework_time and self.actual_rework_time:
            return (self.estimated_rework_time / self.actual_rework_time) * 100
        return 0
    
    def __repr__(self):
        return f'<QualityRework {self.rework_type} for {self.job_batch.job_work.job_number if self.job_batch else "Unknown"}>'

class QualityReturn(db.Model):
    """Material return records for quality failures"""
    __tablename__ = 'quality_returns'
    
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('quality_inspections.id'), nullable=False)
    job_batch_id = db.Column(db.Integer, db.ForeignKey('jobwork_batches.id'), nullable=False)
    
    # Return details
    return_reason = db.Column(db.Text, nullable=False)
    return_to = db.Column(db.String(100), nullable=False)  # vendor, company, scrap
    return_quantity = db.Column(db.Float, nullable=False)
    
    # Financial impact
    return_cost = db.Column(db.Float, default=0)
    vendor_penalty = db.Column(db.Float, default=0)
    recovery_amount = db.Column(db.Float, default=0)
    
    # Logistics
    return_date = db.Column(db.Date)
    return_method = db.Column(db.String(50))  # pickup, delivery, disposal
    transport_cost = db.Column(db.Float, default=0)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, in_transit, completed, disputed
    acknowledgment_received = db.Column(db.Boolean, default=False)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_batch = db.relationship('JobWorkBatch', backref='return_records')
    
    def __repr__(self):
        return f'<QualityReturn {self.return_quantity} units to {self.return_to}>'

class QualityKPI(db.Model):
    """Quality KPI tracking and historical data"""
    __tablename__ = 'quality_kpis'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Time period
    calculation_date = db.Column(db.Date, nullable=False)
    period_type = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    
    # Scope
    process_name = db.Column(db.String(100))  # Specific process or null for overall
    vendor_name = db.Column(db.String(100))  # Specific vendor or null for overall
    
    # KPI metrics
    total_inspections = db.Column(db.Integer, default=0)
    passed_inspections = db.Column(db.Integer, default=0)
    rejected_inspections = db.Column(db.Integer, default=0)
    rework_inspections = db.Column(db.Integer, default=0)
    
    # Rates
    pass_rate = db.Column(db.Float)  # Percentage
    rejection_rate = db.Column(db.Float)  # Percentage
    rework_rate = db.Column(db.Float)  # Percentage
    
    # Quality scores
    average_quality_score = db.Column(db.Float)
    quality_trend = db.Column(db.String(20))  # improving, declining, stable
    
    # Cost impact
    total_quality_cost = db.Column(db.Float, default=0)
    rework_cost = db.Column(db.Float, default=0)
    return_cost = db.Column(db.Float, default=0)
    
    # Efficiency metrics
    average_inspection_time = db.Column(db.Float)  # in minutes
    inspector_efficiency = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def calculate_daily_kpis(cls, target_date, process_name=None, vendor_name=None):
        """Calculate and store daily KPIs"""
        from sqlalchemy import func, and_
        
        # Build filter conditions
        filters = [QualityInspection.inspection_date == target_date]
        if process_name:
            filters.append(QualityInspection.job_batch.has(process_name=process_name))
        if vendor_name:
            filters.append(QualityInspection.job_batch.has(vendor_name=vendor_name))
        
        # Get inspection data
        inspections = QualityInspection.query.filter(and_(*filters)).all()
        
        if not inspections:
            return None
        
        # Calculate metrics
        total_inspections = len(inspections)
        passed = len([i for i in inspections if i.overall_status == 'passed'])
        rejected = len([i for i in inspections if i.overall_status == 'rejected'])
        rework = len([i for i in inspections if i.overall_status == 'rework_needed'])
        
        pass_rate = (passed / total_inspections) * 100 if total_inspections > 0 else 0
        rejection_rate = (rejected / total_inspections) * 100 if total_inspections > 0 else 0
        rework_rate = (rework / total_inspections) * 100 if total_inspections > 0 else 0
        
        # Average quality score
        avg_quality = sum(i.pass_percentage or 0 for i in inspections) / total_inspections
        
        # Create or update KPI record
        kpi = cls.query.filter_by(
            calculation_date=target_date,
            period_type='daily',
            process_name=process_name,
            vendor_name=vendor_name
        ).first()
        
        if not kpi:
            kpi = cls(
                calculation_date=target_date,
                period_type='daily',
                process_name=process_name,
                vendor_name=vendor_name
            )
            db.session.add(kpi)
        
        # Update metrics
        kpi.total_inspections = total_inspections
        kpi.passed_inspections = passed
        kpi.rejected_inspections = rejected
        kpi.rework_inspections = rework
        kpi.pass_rate = pass_rate
        kpi.rejection_rate = rejection_rate
        kpi.rework_rate = rework_rate
        kpi.average_quality_score = avg_quality
        
        # Determine trend (compare with previous day)
        previous_kpi = cls.query.filter_by(
            period_type='daily',
            process_name=process_name,
            vendor_name=vendor_name
        ).filter(cls.calculation_date < target_date).order_by(cls.calculation_date.desc()).first()
        
        if previous_kpi:
            if kpi.pass_rate > previous_kpi.pass_rate:
                kpi.quality_trend = 'improving'
            elif kpi.pass_rate < previous_kpi.pass_rate:
                kpi.quality_trend = 'declining'
            else:
                kpi.quality_trend = 'stable'
        
        return kpi
    
    def __repr__(self):
        return f'<QualityKPI {self.calculation_date} - {self.pass_rate}% pass rate>'