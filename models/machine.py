"""
Machine Management Models

Models for machine-based real-time costing system including:
- Machines and their operational data
- Machine-operator assignments
- Machine expenses and utility costs
- Operator-machine time tracking
- Real-time cost calculations
"""

from datetime import datetime, timedelta
from decimal import Decimal
from app import db


class Machine(db.Model):
    """Manufacturing machines with cost and operational data"""
    __tablename__ = 'machines'
    
    id = db.Column(db.Integer, primary_key=True)
    machine_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    machine_type = db.Column(db.String(100), nullable=False)  # Cutting, Bending, Drilling, etc.
    
    # Cost Information
    hourly_rate = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    depreciation_per_hour = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    maintenance_cost_per_hour = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    
    # Technical Specifications
    power_consumption_kw = db.Column(db.Float, default=0.0)
    efficiency_rating = db.Column(db.Float, default=100.0)  # 0-100%
    max_capacity_per_hour = db.Column(db.Float, default=0.0)
    
    # Operational Data
    status = db.Column(db.String(20), default='active')  # active, maintenance, idle, breakdown
    location = db.Column(db.String(200), default='Production Floor')
    installation_date = db.Column(db.Date)
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_due = db.Column(db.Date)
    
    # Performance Tracking
    total_running_hours = db.Column(db.Float, default=0.0)
    total_production_units = db.Column(db.Float, default=0.0)
    breakdown_count = db.Column(db.Integer, default=0)
    maintenance_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    operators = db.relationship('MachineOperator', backref='machine', lazy=True, cascade='all, delete-orphan')
    expenses = db.relationship('MachineExpense', backref='machine', lazy=True, cascade='all, delete-orphan')
    operating_times = db.relationship('OperatorMachineTime', backref='machine', lazy=True)
    
    def __repr__(self):
        return f'<Machine {self.machine_code}: {self.name}>'
    
    @property
    def current_efficiency(self):
        """Calculate current efficiency based on recent performance"""
        recent_times = OperatorMachineTime.query.filter(
            OperatorMachineTime.machine_id == self.id,
            OperatorMachineTime.start_time >= (datetime.now() - timedelta(days=30))
        ).all()
        
        if not recent_times:
            return self.efficiency_rating
        
        total_efficiency = sum(time.efficiency_achieved or self.efficiency_rating for time in recent_times)
        return total_efficiency / len(recent_times)
    
    @property
    def current_hourly_cost(self):
        """Calculate current total hourly cost including utilities"""
        base_cost = float(self.hourly_rate or 0)
        depreciation = float(self.depreciation_per_hour or 0)
        maintenance = float(self.maintenance_cost_per_hour or 0)
        
        # Add current utility cost
        utility_cost = self.get_current_utility_cost_per_hour()
        
        return base_cost + depreciation + maintenance + utility_cost
    
    def get_current_utility_cost_per_hour(self):
        """Get current utility cost per hour"""
        latest_utility = MachineExpense.query.filter(
            MachineExpense.machine_id == self.id,
            MachineExpense.expense_type == 'utility'
        ).order_by(MachineExpense.effective_date.desc()).first()
        
        return float(latest_utility.cost_per_hour or 0) if latest_utility else 0.0
    
    @property
    def utilization_rate(self):
        """Calculate machine utilization rate for current month"""
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_hours = db.session.query(db.func.sum(OperatorMachineTime.actual_hours)).filter(
            OperatorMachineTime.machine_id == self.id,
            OperatorMachineTime.start_time >= start_of_month
        ).scalar() or 0
        
        # Assuming 8 hours/day, 22 working days/month
        available_hours = 8 * 22
        return (total_hours / available_hours * 100) if available_hours > 0 else 0
    
    @property
    def status_badge_class(self):
        """Bootstrap badge class for machine status"""
        status_classes = {
            'active': 'bg-success',
            'maintenance': 'bg-warning',
            'idle': 'bg-info',
            'breakdown': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')


class MachineOperator(db.Model):
    """Machine-operator assignments with skill levels"""
    __tablename__ = 'machine_operators'
    
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Assignment Details
    assigned_date = db.Column(db.Date, default=datetime.utcnow().date())
    end_date = db.Column(db.Date)  # For temporary assignments
    is_primary = db.Column(db.Boolean, default=False)  # Primary operator for this machine
    
    # Skill and Performance
    skill_level = db.Column(db.String(20), default='intermediate')  # beginner, intermediate, expert
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    efficiency_multiplier = db.Column(db.Float, default=1.0)  # 0.8 to 1.5 (performance factor)
    quality_score = db.Column(db.Float, default=100.0)  # Average quality score (0-100%)
    
    # Performance Tracking
    total_hours_operated = db.Column(db.Float, default=0.0)
    total_units_produced = db.Column(db.Float, default=0.0)
    average_efficiency = db.Column(db.Float, default=100.0)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, inactive, training
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='machine_assignments')
    operating_times = db.relationship('OperatorMachineTime', backref='operator', lazy=True)
    
    __table_args__ = (db.UniqueConstraint('machine_id', 'employee_id', name='unique_machine_operator'),)
    
    def __repr__(self):
        return f'<MachineOperator {self.employee.name if self.employee else "Unknown"} -> {self.machine.machine_code if self.machine else "Unknown"}>'
    
    @property
    def effective_hourly_cost(self):
        """Calculate effective hourly cost including efficiency"""
        base_rate = float(self.hourly_rate or 0)
        efficiency_factor = self.efficiency_multiplier or 1.0
        
        # If operator is more efficient, cost per unit goes down
        return base_rate / efficiency_factor
    
    @property
    def skill_badge_class(self):
        """Bootstrap badge class for skill level"""
        skill_classes = {
            'beginner': 'bg-info',
            'intermediate': 'bg-primary',
            'expert': 'bg-success'
        }
        return skill_classes.get(self.skill_level, 'bg-secondary')


class MachineExpense(db.Model):
    """Track machine-related expenses (utilities, maintenance, etc.)"""
    __tablename__ = 'machine_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    
    # Expense Details
    expense_type = db.Column(db.String(50), nullable=False)  # utility, maintenance, repair, depreciation, insurance
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Billing Period
    billing_start_date = db.Column(db.Date, nullable=False)
    billing_end_date = db.Column(db.Date, nullable=False)
    effective_date = db.Column(db.Date, default=datetime.utcnow().date())
    
    # Cost Calculation
    total_machine_hours = db.Column(db.Float, default=0.0)  # Total hours machine ran during billing period
    cost_per_hour = db.Column(db.Numeric(10, 4))  # Calculated: amount / total_machine_hours
    
    # Utility-specific fields
    utility_type = db.Column(db.String(50))  # electricity, gas, water, compressed_air
    units_consumed = db.Column(db.Float)  # KWH, cubic meters, etc.
    rate_per_unit = db.Column(db.Numeric(10, 4))  # Rate per KWH, etc.
    
    # Reference Documents
    bill_reference = db.Column(db.String(200))  # Bill number, invoice reference
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))  # Attached utility bill
    
    # Allocation Method
    allocation_method = db.Column(db.String(50), default='actual_usage')  # actual_usage, proportional, fixed
    allocation_percentage = db.Column(db.Float)  # For proportional allocation
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    document = db.relationship('Document', backref='machine_expense_records')
    creator = db.relationship('User', backref='machine_expenses_created')
    
    def __repr__(self):
        return f'<MachineExpense {self.expense_type}: ₹{self.amount} for {self.machine.machine_code if self.machine else "Unknown"}>'
    
    @property
    def billing_period_days(self):
        """Calculate billing period in days"""
        return (self.billing_end_date - self.billing_start_date).days + 1
    
    @property
    def daily_cost(self):
        """Calculate daily cost"""
        return float(self.amount) / max(1, self.billing_period_days)
    
    def calculate_cost_per_hour(self, machine_hours=None):
        """Calculate or recalculate cost per hour"""
        if machine_hours is not None:
            self.total_machine_hours = machine_hours
        
        if self.total_machine_hours and self.total_machine_hours > 0:
            self.cost_per_hour = self.amount / Decimal(str(self.total_machine_hours))
        else:
            # Fallback: distribute over billing period assuming 8 hours/day
            working_days = max(1, self.billing_period_days * 0.7)  # Assume 70% working days
            estimated_hours = working_days * 8
            self.cost_per_hour = self.amount / Decimal(str(estimated_hours))
    
    @property
    def expense_type_badge_class(self):
        """Bootstrap badge class for expense type"""
        type_classes = {
            'utility': 'bg-warning',
            'maintenance': 'bg-info',
            'repair': 'bg-danger',
            'depreciation': 'bg-secondary',
            'insurance': 'bg-primary'
        }
        return type_classes.get(self.expense_type, 'bg-light')


class OperatorMachineTime(db.Model):
    """Track actual operator-machine working time for accurate cost allocation"""
    __tablename__ = 'operator_machine_time'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # References
    operator_id = db.Column(db.Integer, db.ForeignKey('machine_operators.id'), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    job_card_id = db.Column(db.Integer, db.ForeignKey('job_cards.id'))  # Optional: link to specific job
    process_name = db.Column(db.String(100))  # cutting, bending, drilling, etc.
    
    # Time Tracking
    shift_date = db.Column(db.Date, default=datetime.utcnow().date(), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    actual_hours = db.Column(db.Float)  # Calculated from start/end time
    
    # Production Data
    units_planned = db.Column(db.Float, default=0.0)
    units_produced = db.Column(db.Float, default=0.0)
    units_good = db.Column(db.Float, default=0.0)
    units_scrap = db.Column(db.Float, default=0.0)
    
    # Performance Metrics
    efficiency_achieved = db.Column(db.Float, default=100.0)  # % efficiency vs standard
    quality_score = db.Column(db.Float, default=100.0)  # % good units
    downtime_hours = db.Column(db.Float, default=0.0)  # Machine breakdown/setup time
    
    # Cost Calculation
    operator_cost = db.Column(db.Numeric(10, 2))  # Operator cost for this period
    machine_cost = db.Column(db.Numeric(10, 2))  # Machine cost for this period
    utility_cost = db.Column(db.Numeric(10, 2))  # Utility cost for this period
    total_cost = db.Column(db.Numeric(10, 2))  # Total combined cost
    
    # Status and Notes
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_card = db.relationship('JobCard', backref='operator_machine_times')
    
    def __repr__(self):
        return f'<OperatorMachineTime {self.shift_date} - {self.actual_hours}h - {self.machine.machine_code if self.machine else "Unknown"}>'
    
    @property
    def productive_hours(self):
        """Calculate productive hours (excluding downtime)"""
        total_hours = self.actual_hours or 0
        downtime = self.downtime_hours or 0
        return max(0, total_hours - downtime)
    
    @property
    def efficiency_percentage(self):
        """Calculate efficiency percentage"""
        if self.units_planned and self.units_planned > 0:
            return (self.units_produced / self.units_planned) * 100
        return self.efficiency_achieved or 100.0
    
    @property
    def quality_percentage(self):
        """Calculate quality percentage"""
        if self.units_produced and self.units_produced > 0:
            return (self.units_good / self.units_produced) * 100
        return self.quality_score or 100.0
    
    @property
    def cost_per_unit(self):
        """Calculate cost per unit produced"""
        if self.units_good and self.units_good > 0:
            return float(self.total_cost or 0) / self.units_good
        return 0.0
    
    @property
    def utilization_rate(self):
        """Calculate machine utilization rate for this time period"""
        if not self.actual_hours or self.actual_hours <= 0:
            return 0.0
        return (self.productive_hours / self.actual_hours) * 100
    
    def calculate_costs(self):
        """Calculate all cost components for this time period"""
        if not self.actual_hours or self.actual_hours <= 0:
            return
        
        # Operator cost
        if self.operator:
            operator_rate = float(self.operator.hourly_rate or 0)
            efficiency_factor = self.operator.efficiency_multiplier or 1.0
            self.operator_cost = Decimal(str((operator_rate * self.actual_hours) / efficiency_factor))
        
        # Machine cost (base rate + depreciation + maintenance)
        machine = self.machine
        if machine:
            base_rate = float(machine.hourly_rate or 0)
            depreciation = float(machine.depreciation_per_hour or 0)
            maintenance = float(machine.maintenance_cost_per_hour or 0)
            machine_hourly_cost = base_rate + depreciation + maintenance
            self.machine_cost = Decimal(str(machine_hourly_cost * self.actual_hours))
        
        # Utility cost
        if machine:
            utility_cost_per_hour = machine.get_current_utility_cost_per_hour()
            self.utility_cost = Decimal(str(utility_cost_per_hour * self.actual_hours))
        
        # Total cost
        operator_cost = float(self.operator_cost or 0)
        machine_cost = float(self.machine_cost or 0)
        utility_cost = float(self.utility_cost or 0)
        self.total_cost = Decimal(str(operator_cost + machine_cost + utility_cost))
    
    def start_operation(self):
        """Start tracking time for this operation"""
        self.start_time = datetime.now()
        self.status = 'active'
    
    def end_operation(self, units_produced=0, units_good=0, units_scrap=0, notes=''):
        """End tracking and calculate final costs"""
        self.end_time = datetime.now()
        self.status = 'completed'
        
        # Calculate actual hours
        if self.start_time and self.end_time:
            time_diff = self.end_time - self.start_time
            self.actual_hours = time_diff.total_seconds() / 3600
        
        # Update production data
        self.units_produced = units_produced
        self.units_good = units_good
        self.units_scrap = units_scrap
        
        # Calculate costs
        self.calculate_costs()
        
        # Add notes
        if notes:
            self.notes = notes


class MachineCostAnalysis(db.Model):
    """Periodic analysis of machine costs for reporting and BOM updates"""
    __tablename__ = 'machine_cost_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    
    # Analysis Period
    analysis_date = db.Column(db.Date, default=datetime.utcnow().date(), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    
    # Calculated Costs
    average_hourly_cost = db.Column(db.Numeric(10, 2))  # Average total cost per hour
    operator_cost_per_hour = db.Column(db.Numeric(10, 2))  # Average operator cost
    machine_cost_per_hour = db.Column(db.Numeric(10, 2))  # Machine + depreciation + maintenance
    utility_cost_per_hour = db.Column(db.Numeric(10, 2))  # Utility cost per hour
    
    # Performance Metrics
    total_hours_operated = db.Column(db.Float)
    total_units_produced = db.Column(db.Float)
    average_efficiency = db.Column(db.Float)
    average_quality = db.Column(db.Float)
    utilization_rate = db.Column(db.Float)
    
    # Cost Analysis
    cost_per_unit = db.Column(db.Numeric(10, 4))  # Average cost per unit produced
    variance_from_standard = db.Column(db.Numeric(10, 2))  # Variance from standard cost
    variance_percentage = db.Column(db.Float)  # Variance as percentage
    
    # Recommendations
    recommended_bom_rate = db.Column(db.Numeric(10, 2))  # Recommended rate for BOM updates
    cost_trend = db.Column(db.String(20))  # increasing, stable, decreasing
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    machine = db.relationship('Machine', backref='cost_analyses')
    creator = db.relationship('User', backref='machine_cost_analyses_created')
    
    def __repr__(self):
        return f'<MachineCostAnalysis {self.machine.machine_code if self.machine else "Unknown"} - {self.analysis_date}>'
    
    @property
    def period_days(self):
        """Calculate analysis period in days"""
        return (self.period_end - self.period_start).days + 1
    
    @classmethod
    def generate_analysis(cls, machine_id, start_date, end_date):
        """Generate cost analysis for a machine over a period"""
        machine = Machine.query.get(machine_id)
        if not machine:
            return None
        
        # Get all operator-machine time records for the period
        time_records = OperatorMachineTime.query.filter(
            OperatorMachineTime.machine_id == machine_id,
            OperatorMachineTime.shift_date >= start_date,
            OperatorMachineTime.shift_date <= end_date
        ).filter(OperatorMachineTime.status == 'completed').all()
        
        if not time_records:
            return None
        
        # Calculate aggregated metrics
        total_hours = sum(record.actual_hours or 0 for record in time_records)
        total_units = sum(record.units_produced or 0 for record in time_records)
        total_good_units = sum(record.units_good or 0 for record in time_records)
        total_operator_cost = sum(float(record.operator_cost or 0) for record in time_records)
        total_machine_cost = sum(float(record.machine_cost or 0) for record in time_records)
        total_utility_cost = sum(float(record.utility_cost or 0) for record in time_records)
        total_cost = total_operator_cost + total_machine_cost + total_utility_cost
        
        # Create analysis record
        analysis = cls(
            machine_id=machine_id,
            period_start=start_date,
            period_end=end_date,
            total_hours_operated=total_hours,
            total_units_produced=total_units,
            average_efficiency=sum(record.efficiency_achieved or 100 for record in time_records) / len(time_records),
            average_quality=sum(record.quality_score or 100 for record in time_records) / len(time_records),
            utilization_rate=sum(record.utilization_rate or 100 for record in time_records) / len(time_records)
        )
        
        # Calculate hourly costs
        if total_hours > 0:
            analysis.average_hourly_cost = Decimal(str(total_cost / total_hours))
            analysis.operator_cost_per_hour = Decimal(str(total_operator_cost / total_hours))
            analysis.machine_cost_per_hour = Decimal(str(total_machine_cost / total_hours))
            analysis.utility_cost_per_hour = Decimal(str(total_utility_cost / total_hours))
        
        # Calculate cost per unit
        if total_good_units > 0:
            analysis.cost_per_unit = Decimal(str(total_cost / total_good_units))
        
        # Calculate variance from machine's standard hourly rate
        if machine.hourly_rate:
            standard_cost = float(machine.hourly_rate)
            actual_cost = float(analysis.average_hourly_cost or 0)
            analysis.variance_from_standard = Decimal(str(actual_cost - standard_cost))
            if standard_cost > 0:
                analysis.variance_percentage = ((actual_cost - standard_cost) / standard_cost) * 100
        
        # Set recommended BOM rate
        analysis.recommended_bom_rate = analysis.average_hourly_cost
        
        # Determine cost trend (simplified - would need historical data)
        analysis.cost_trend = 'stable'
        
        return analysis