"""
Enhanced Manufacturing Intelligence Models
Database models for advanced manufacturing analytics and automation
"""
from app import db
from datetime import datetime
from sqlalchemy import func

class MaterialReservation(db.Model):
    """Track material reservations for production orders"""
    __tablename__ = 'material_reservations'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    reserved_quantity = db.Column(db.Float, nullable=False)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    reserved_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    released_at = db.Column(db.DateTime)  # When reservation is released
    consumed_quantity = db.Column(db.Float, default=0.0)  # Actually consumed quantity
    status = db.Column(db.String(20), default='active')  # active, consumed, released, expired
    notes = db.Column(db.Text)
    
    # Relationships
    production = db.relationship('Production', backref='material_reservations')
    item = db.relationship('Item', backref='material_reservations')
    
    @property
    def remaining_quantity(self):
        """Get remaining reserved quantity"""
        return self.reserved_quantity - self.consumed_quantity
    
    @property
    def status_badge_class(self):
        """Bootstrap badge class for status"""
        status_classes = {
            'active': 'bg-info',
            'consumed': 'bg-success',
            'released': 'bg-warning',
            'expired': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

class ProcessEfficiencyMetric(db.Model):
    """Track process efficiency metrics over time"""
    __tablename__ = 'process_efficiency_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(50), nullable=False)  # cutting, bending, etc.
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'))
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'))
    
    # Efficiency metrics
    planned_quantity = db.Column(db.Float, nullable=False)
    actual_quantity = db.Column(db.Float, default=0.0)
    scrap_quantity = db.Column(db.Float, default=0.0)
    planned_time_hours = db.Column(db.Float)
    actual_time_hours = db.Column(db.Float)
    
    # Calculated metrics
    efficiency_percentage = db.Column(db.Float)  # (actual/planned) * 100
    scrap_percentage = db.Column(db.Float)  # (scrap/planned) * 100
    throughput_per_hour = db.Column(db.Float)  # actual_quantity / actual_time_hours
    
    # Timestamps
    process_start = db.Column(db.DateTime)
    process_end = db.Column(db.DateTime)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    job_work = db.relationship('JobWork', backref='efficiency_metrics')
    production = db.relationship('Production', backref='efficiency_metrics')
    
    @classmethod
    def calculate_metrics(cls, process_name, planned_qty, actual_qty, scrap_qty, planned_hours, actual_hours):
        """Calculate efficiency metrics"""
        metrics = {}
        
        if planned_qty > 0:
            metrics['efficiency_percentage'] = (actual_qty / planned_qty) * 100
            metrics['scrap_percentage'] = (scrap_qty / planned_qty) * 100
        
        if actual_hours and actual_hours > 0:
            metrics['throughput_per_hour'] = actual_qty / actual_hours
        
        return metrics

class SupplierPerformanceMetric(db.Model):
    """Track supplier performance for enhanced GRN intelligence"""
    __tablename__ = 'supplier_performance_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))  # Optional - item-specific metrics
    
    # Performance metrics
    total_orders = db.Column(db.Integer, default=0)
    on_time_deliveries = db.Column(db.Integer, default=0)
    quality_pass_rate = db.Column(db.Float, default=100.0)  # Percentage
    average_lead_time_days = db.Column(db.Float)
    rejection_rate = db.Column(db.Float, default=0.0)  # Percentage
    
    # Financial metrics
    total_order_value = db.Column(db.Float, default=0.0)
    total_rejected_value = db.Column(db.Float, default=0.0)
    
    # Date range for metrics
    metric_period_start = db.Column(db.Date)
    metric_period_end = db.Column(db.Date)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    supplier = db.relationship('Supplier', backref='performance_metrics')
    item = db.relationship('Item', backref='supplier_performance_metrics')
    
    @property
    def on_time_percentage(self):
        """Calculate on-time delivery percentage"""
        if self.total_orders == 0:
            return 100.0
        return (self.on_time_deliveries / self.total_orders) * 100
    
    @property
    def performance_grade(self):
        """Calculate overall performance grade"""
        on_time_score = self.on_time_percentage
        quality_score = self.quality_pass_rate
        rejection_score = 100 - self.rejection_rate
        
        overall_score = (on_time_score + quality_score + rejection_score) / 3
        
        if overall_score >= 90:
            return 'A'
        elif overall_score >= 80:
            return 'B'
        elif overall_score >= 70:
            return 'C'
        else:
            return 'D'
    
    @property
    def grade_badge_class(self):
        """Bootstrap badge class for performance grade"""
        grade_classes = {
            'A': 'bg-success',
            'B': 'bg-info',
            'C': 'bg-warning',
            'D': 'bg-danger'
        }
        return grade_classes.get(self.performance_grade, 'bg-secondary')

class ManufacturingAlert(db.Model):
    """Intelligent manufacturing alerts and notifications"""
    __tablename__ = 'manufacturing_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)  # material_shortage, quality_issue, efficiency_drop
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Related entities
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'))
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    
    # Alert data
    threshold_value = db.Column(db.Float)  # Threshold that triggered alert
    actual_value = db.Column(db.Float)  # Actual value that triggered alert
    recommended_action = db.Column(db.Text)
    
    # Status tracking
    status = db.Column(db.String(20), default='active')  # active, acknowledged, resolved, dismissed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolved_at = db.Column(db.DateTime)
    
    # Relationships
    item = db.relationship('Item', backref='manufacturing_alerts')
    job_work = db.relationship('JobWork', backref='manufacturing_alerts')
    production = db.relationship('Production', backref='manufacturing_alerts')
    supplier = db.relationship('Supplier', backref='manufacturing_alerts')
    acknowledger = db.relationship('User', backref='acknowledged_alerts')
    
    @property
    def severity_badge_class(self):
        """Bootstrap badge class for severity"""
        severity_classes = {
            'low': 'bg-info',
            'medium': 'bg-warning',
            'high': 'bg-danger',
            'critical': 'bg-dark'
        }
        return severity_classes.get(self.severity, 'bg-secondary')
    
    @property
    def status_badge_class(self):
        """Bootstrap badge class for status"""
        status_classes = {
            'active': 'bg-danger',
            'acknowledged': 'bg-warning',
            'resolved': 'bg-success',
            'dismissed': 'bg-secondary'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @property
    def age_hours(self):
        """Get alert age in hours"""
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600

class InventoryForecast(db.Model):
    """Predictive inventory forecasting"""
    __tablename__ = 'inventory_forecasts'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    forecast_date = db.Column(db.Date, nullable=False)
    forecast_horizon_days = db.Column(db.Integer, default=30)  # Forecast period
    
    # Current state
    current_stock = db.Column(db.Float, nullable=False)
    current_wip = db.Column(db.Float, default=0.0)
    current_reserved = db.Column(db.Float, default=0.0)
    
    # Forecast data
    predicted_consumption = db.Column(db.Float, default=0.0)
    predicted_production = db.Column(db.Float, default=0.0)
    predicted_purchases = db.Column(db.Float, default=0.0)
    predicted_stock_level = db.Column(db.Float)
    
    # Risk assessment
    stockout_risk_percentage = db.Column(db.Float, default=0.0)
    recommended_reorder_quantity = db.Column(db.Float)
    recommended_reorder_date = db.Column(db.Date)
    
    # Metadata
    forecast_confidence = db.Column(db.Float, default=75.0)  # Confidence percentage
    model_used = db.Column(db.String(50), default='trend_analysis')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='inventory_forecasts')
    
    @property
    def risk_level(self):
        """Categorize stockout risk"""
        if self.stockout_risk_percentage >= 80:
            return 'Critical'
        elif self.stockout_risk_percentage >= 60:
            return 'High'
        elif self.stockout_risk_percentage >= 40:
            return 'Medium'
        else:
            return 'Low'
    
    @property
    def risk_badge_class(self):
        """Bootstrap badge class for risk level"""
        risk_classes = {
            'Critical': 'bg-danger',
            'High': 'bg-warning',
            'Medium': 'bg-info',
            'Low': 'bg-success'
        }
        return risk_classes.get(self.risk_level, 'bg-secondary')