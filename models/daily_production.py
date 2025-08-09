from datetime import datetime, date
from app import db
from sqlalchemy import func

class DailyProductionStatus(db.Model):
    """Track daily production status for each production order"""
    __tablename__ = 'daily_production_status'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    report_date = db.Column(db.Date, nullable=False, default=date.today)
    
    # Daily progress metrics
    qty_completed_today = db.Column(db.Float, default=0.0)
    qty_good_today = db.Column(db.Float, default=0.0)
    qty_defective_today = db.Column(db.Float, default=0.0)
    qty_scrap_today = db.Column(db.Float, default=0.0)
    
    # Cumulative metrics
    cumulative_completed = db.Column(db.Float, default=0.0)
    cumulative_good = db.Column(db.Float, default=0.0)
    cumulative_defective = db.Column(db.Float, default=0.0)
    cumulative_scrap = db.Column(db.Float, default=0.0)
    
    # Status and progress
    daily_status = db.Column(db.String(20), default='planned')  # planned, active, paused, completed, delayed
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Resource tracking
    workers_assigned = db.Column(db.Integer, default=0)
    machine_hours_used = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)
    
    # Material consumption
    material_consumed_cost = db.Column(db.Float, default=0.0)
    labor_cost_today = db.Column(db.Float, default=0.0)
    
    # Issues and notes
    production_issues = db.Column(db.Text)
    quality_issues = db.Column(db.Text)
    delay_reason = db.Column(db.String(200))
    supervisor_notes = db.Column(db.Text)
    
    # Timestamps
    shift_start_time = db.Column(db.DateTime)
    shift_end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    production = db.relationship('Production', backref='daily_status_reports', lazy=True)
    created_by = db.relationship('User', backref='daily_production_reports', lazy=True)
    
    def __repr__(self):
        return f'<DailyProductionStatus {self.production_id} - {self.report_date}>'
    
    @property
    def efficiency_rate(self):
        """Calculate daily efficiency rate"""
        if self.qty_completed_today > 0:
            return (self.qty_good_today / self.qty_completed_today) * 100
        return 0.0
    
    @property
    def defect_rate(self):
        """Calculate daily defect rate"""
        if self.qty_completed_today > 0:
            return (self.qty_defective_today / self.qty_completed_today) * 100
        return 0.0
    
    @property
    def is_on_schedule(self):
        """Check if production is on schedule based on planned vs actual"""
        if self.production and self.production.quantity_planned:
            days_elapsed = (date.today() - self.production.created_at.date()).days + 1
            expected_daily_rate = self.production.quantity_planned / max(days_elapsed, 1)
            return self.cumulative_completed >= (expected_daily_rate * days_elapsed * 0.9)  # 90% tolerance
        return True
    
    @property
    def status_color(self):
        """Return color class for status display"""
        status_colors = {
            'planned': 'secondary',
            'active': 'success',
            'paused': 'warning',
            'completed': 'primary',
            'delayed': 'danger'
        }
        return status_colors.get(self.daily_status, 'secondary')
    
    @classmethod
    def get_today_report(cls, production_id):
        """Get today's report for a production order"""
        return cls.query.filter_by(
            production_id=production_id,
            report_date=date.today()
        ).first()
    
    @classmethod
    def create_or_update_today(cls, production_id, **kwargs):
        """Create or update today's production status"""
        report = cls.get_today_report(production_id)
        if not report:
            report = cls(production_id=production_id, report_date=date.today())
            db.session.add(report)
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(report, key):
                setattr(report, key, value)
        
        report.updated_at = datetime.utcnow()
        db.session.commit()
        return report

class ProductionShiftLog(db.Model):
    """Log production activities by shift"""
    __tablename__ = 'production_shift_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    daily_production_status_id = db.Column(db.Integer, db.ForeignKey('daily_production_status.id'), nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)  # morning, afternoon, night
    
    # Shift metrics
    shift_start = db.Column(db.DateTime, nullable=False)
    shift_end = db.Column(db.DateTime)
    qty_produced_shift = db.Column(db.Float, default=0.0)
    qty_good_shift = db.Column(db.Float, default=0.0)
    qty_defective_shift = db.Column(db.Float, default=0.0)
    
    # Shift details
    workers_present = db.Column(db.Integer, default=0)
    supervisor_name = db.Column(db.String(100))
    machine_downtime_minutes = db.Column(db.Integer, default=0)
    downtime_reason = db.Column(db.String(200))
    
    # Notes
    shift_notes = db.Column(db.Text)
    issues_encountered = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    daily_status = db.relationship('DailyProductionStatus', backref='shift_logs', lazy=True)
    
    def __repr__(self):
        return f'<ProductionShiftLog {self.shift_type} - {self.shift_start}>'
    
    @property
    def shift_duration_hours(self):
        """Calculate shift duration in hours"""
        if self.shift_end and self.shift_start:
            return (self.shift_end - self.shift_start).total_seconds() / 3600
        return 0.0
    
    @property
    def productivity_rate(self):
        """Calculate productivity rate per hour"""
        hours = self.shift_duration_hours
        if hours > 0:
            return self.qty_produced_shift / hours
        return 0.0

class DailyProductionSummary(db.Model):
    """Daily factory-wide production summary"""
    __tablename__ = 'daily_production_summary'
    
    id = db.Column(db.Integer, primary_key=True)
    summary_date = db.Column(db.Date, nullable=False, default=date.today)
    
    # Factory totals
    total_productions_active = db.Column(db.Integer, default=0)
    total_qty_produced = db.Column(db.Float, default=0.0)
    total_qty_good = db.Column(db.Float, default=0.0)
    total_qty_defective = db.Column(db.Float, default=0.0)
    total_scrap = db.Column(db.Float, default=0.0)
    
    # Performance metrics
    overall_efficiency = db.Column(db.Float, default=0.0)
    overall_defect_rate = db.Column(db.Float, default=0.0)
    on_schedule_count = db.Column(db.Integer, default=0)
    delayed_count = db.Column(db.Integer, default=0)
    
    # Resource utilization
    total_worker_hours = db.Column(db.Float, default=0.0)
    total_machine_hours = db.Column(db.Float, default=0.0)
    total_overtime_hours = db.Column(db.Float, default=0.0)
    
    # Costs
    total_material_cost = db.Column(db.Float, default=0.0)
    total_labor_cost = db.Column(db.Float, default=0.0)
    
    # Generated insights
    key_insights = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DailyProductionSummary {self.summary_date}>'
    
    @classmethod
    def generate_daily_summary(cls, target_date=None):
        """Generate daily summary from all production status reports"""
        if not target_date:
            target_date = date.today()
        
        # Get all daily status reports for the date
        daily_reports = DailyProductionStatus.query.filter_by(report_date=target_date).all()
        
        if not daily_reports:
            return None
        
        # Calculate totals
        total_productions_active = len([r for r in daily_reports if r.daily_status in ['active', 'paused']])
        total_qty_produced = sum(r.qty_completed_today for r in daily_reports)
        total_qty_good = sum(r.qty_good_today for r in daily_reports)
        total_qty_defective = sum(r.qty_defective_today for r in daily_reports)
        total_scrap = sum(r.qty_scrap_today for r in daily_reports)
        
        # Calculate performance metrics
        overall_efficiency = (total_qty_good / total_qty_produced * 100) if total_qty_produced > 0 else 0
        overall_defect_rate = (total_qty_defective / total_qty_produced * 100) if total_qty_produced > 0 else 0
        on_schedule_count = len([r for r in daily_reports if r.is_on_schedule])
        delayed_count = len([r for r in daily_reports if not r.is_on_schedule])
        
        # Calculate resource totals
        total_worker_hours = sum(r.workers_assigned * 8 for r in daily_reports)  # Assuming 8-hour shifts
        total_machine_hours = sum(r.machine_hours_used for r in daily_reports)
        total_overtime_hours = sum(r.overtime_hours for r in daily_reports)
        
        # Calculate costs
        total_material_cost = sum(r.material_consumed_cost for r in daily_reports)
        total_labor_cost = sum(r.labor_cost_today for r in daily_reports)
        
        # Generate insights
        insights = []
        if overall_efficiency > 95:
            insights.append("Excellent efficiency achieved today!")
        elif overall_efficiency < 80:
            insights.append("Efficiency below target - review processes")
        
        if overall_defect_rate > 5:
            insights.append("High defect rate - quality review needed")
        
        if delayed_count > on_schedule_count:
            insights.append("More productions delayed than on schedule")
        
        # Create or update summary
        summary = cls.query.filter_by(summary_date=target_date).first()
        if not summary:
            summary = cls(summary_date=target_date)
            db.session.add(summary)
        
        # Update summary
        summary.total_productions_active = total_productions_active
        summary.total_qty_produced = total_qty_produced
        summary.total_qty_good = total_qty_good
        summary.total_qty_defective = total_qty_defective
        summary.total_scrap = total_scrap
        summary.overall_efficiency = overall_efficiency
        summary.overall_defect_rate = overall_defect_rate
        summary.on_schedule_count = on_schedule_count
        summary.delayed_count = delayed_count
        summary.total_worker_hours = total_worker_hours
        summary.total_machine_hours = total_machine_hours
        summary.total_overtime_hours = total_overtime_hours
        summary.total_material_cost = total_material_cost
        summary.total_labor_cost = total_labor_cost
        summary.key_insights = '; '.join(insights)
        summary.updated_at = datetime.utcnow()
        
        db.session.commit()
        return summary


class DailyProductionEntry(db.Model):
    """Individual daily production entry records for detailed tracking"""
    __tablename__ = 'daily_production_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    
    # Entry details
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    shift = db.Column(db.String(20), default='day')  # day, night, general
    
    # Production quantities
    target_quantity = db.Column(db.Float, default=0.0)  # Target for this entry
    actual_quantity = db.Column(db.Float, nullable=False)  # Actually produced
    good_quantity = db.Column(db.Float, default=0.0)  # Good quality items
    defective_quantity = db.Column(db.Float, default=0.0)  # Defective/rework items
    scrap_quantity = db.Column(db.Float, default=0.0)  # Scrap/damaged items
    
    # Weight tracking
    weight_produced = db.Column(db.Float, default=0.0)  # Total weight produced
    
    # Quality control
    quality_status = db.Column(db.String(20), default='pending')  # pending, passed, failed, partial
    quality_notes = db.Column(db.Text)  # Quality control notes
    
    # Production notes
    production_notes = db.Column(db.Text)  # General production notes
    material_consumption_notes = db.Column(db.Text)  # Material consumption notes
    
    # Audit trail
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    production = db.relationship('Production', backref='daily_entries', lazy=True)
    recorded_by_user = db.relationship('User', backref='daily_production_entries', lazy=True)
    
    def __repr__(self):
        return f'<DailyProductionEntry {self.production_id} - {self.entry_date}: {self.actual_quantity}>'
    
    @property
    def quality_rate(self):
        """Calculate quality rate for this entry"""
        if self.actual_quantity > 0:
            return (self.good_quantity / self.actual_quantity) * 100
        return 0.0
    
    @property
    def defect_rate(self):
        """Calculate defect rate for this entry"""
        if self.actual_quantity > 0:
            return (self.defective_quantity / self.actual_quantity) * 100
        return 0.0
    
    @property
    def target_achievement(self):
        """Calculate target achievement percentage"""
        if self.target_quantity > 0:
            return (self.actual_quantity / self.target_quantity) * 100
        return 0.0
    
    @property
    def efficiency_status(self):
        """Get efficiency status based on target achievement"""
        achievement = self.target_achievement
        if achievement >= 100:
            return 'excellent'
        elif achievement >= 90:
            return 'good'
        elif achievement >= 80:
            return 'acceptable'
        else:
            return 'poor'
    
    @classmethod
    def get_entries_for_production(cls, production_id, start_date=None, end_date=None):
        """Get daily entries for a production order within date range"""
        query = cls.query.filter_by(production_id=production_id)
        
        if start_date:
            query = query.filter(cls.entry_date >= start_date)
        if end_date:
            query = query.filter(cls.entry_date <= end_date)
        
        return query.order_by(cls.entry_date.desc()).all()
    
    @classmethod
    def get_summary_for_production(cls, production_id):
        """Get summary statistics for a production order"""
        entries = cls.query.filter_by(production_id=production_id).all()
        
        if not entries:
            return {
                'total_entries': 0,
                'total_produced': 0,
                'total_good': 0,
                'total_defective': 0,
                'total_scrap': 0,
                'avg_quality_rate': 0,
                'avg_defect_rate': 0
            }
        
        total_produced = sum(e.actual_quantity for e in entries)
        total_good = sum(e.good_quantity for e in entries)
        total_defective = sum(e.defective_quantity for e in entries)
        total_scrap = sum(e.scrap_quantity for e in entries)
        
        avg_quality_rate = (total_good / total_produced * 100) if total_produced > 0 else 0
        avg_defect_rate = (total_defective / total_produced * 100) if total_produced > 0 else 0
        
        return {
            'total_entries': len(entries),
            'total_produced': total_produced,
            'total_good': total_good,
            'total_defective': total_defective,
            'total_scrap': total_scrap,
            'avg_quality_rate': avg_quality_rate,
            'avg_defect_rate': avg_defect_rate,
            'date_range': {
                'start': min(e.entry_date for e in entries),
                'end': max(e.entry_date for e in entries)
            }
        }