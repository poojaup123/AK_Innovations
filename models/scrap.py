from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from models import db

class ScrapTracking(db.Model):
    """
    Comprehensive scrap tracking system that integrates with BOM and batch tracking
    """
    __tablename__ = 'scrap_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    scrap_code = db.Column(db.String(50), unique=True, nullable=False)  # SCRP-001, SCRP-002, etc.
    
    # Production linkage
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=True)
    job_card_id = db.Column(db.Integer, db.ForeignKey('job_cards.id'), nullable=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False)
    
    # Batch linkage
    input_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=False)  # Source material batch
    output_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=True)  # Output finished goods batch
    scrap_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=True)  # Created scrap batch
    
    # Material and quantities
    material_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)  # Raw material used
    input_weight = db.Column(db.Float, nullable=False)  # Total input weight (kg)
    output_weight = db.Column(db.Float, nullable=False)  # Total output weight (kg)
    scrap_weight = db.Column(db.Float, nullable=False)  # Calculated scrap weight (kg)
    scrap_percentage = db.Column(db.Float, nullable=False)  # Calculated scrap percentage
    
    # Production details
    units_produced = db.Column(db.Integer, default=0)  # Number of finished units produced
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per finished unit
    
    # Scrap classification
    scrap_type = db.Column(db.String(50), default='offcut')  # offcut, defective, waste, trimming
    scrap_reason = db.Column(db.String(100))  # cutting_waste, quality_reject, material_defect, etc.
    scrap_status = db.Column(db.String(30), default='available')  # available, reused, sold, disposed
    
    # Recovery and reuse
    recoverable = db.Column(db.Boolean, default=True)  # Can this scrap be reused/recycled?
    recovery_value_per_kg = db.Column(db.Float, default=0.0)  # Recovery value per kg
    total_recovery_value = db.Column(db.Float, default=0.0)  # Total potential recovery value
    
    # Process and quality details
    process_step = db.Column(db.String(100))  # Which process generated the scrap
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who recorded this
    quality_notes = db.Column(db.Text)  # Quality control notes about the scrap
    
    # Storage and handling
    storage_location = db.Column(db.String(100), default='SCRAP-YARD')  # Where scrap is stored
    handling_instructions = db.Column(db.Text)  # Special handling requirements
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    production_order = relationship('ProductionOrder', backref='scrap_records')
    job_card = relationship('JobCard', backref='scrap_records')
    bom = relationship('BOM', backref='scrap_records')
    input_batch = relationship('ItemBatch', foreign_keys=[input_batch_id], backref='input_scrap_records')
    output_batch = relationship('ItemBatch', foreign_keys=[output_batch_id], backref='output_scrap_records')
    scrap_batch = relationship('ItemBatch', foreign_keys=[scrap_batch_id], backref='generated_from_scrap')
    material_item = relationship('Item', backref='scrap_records')
    operator = relationship('User', foreign_keys=[operator_id], backref='operated_scrap_records')
    recorded_by_user = relationship('User', foreign_keys=[recorded_by], backref='recorded_scrap_records')
    
    def __repr__(self):
        return f'<ScrapTracking {self.scrap_code}: {self.scrap_weight}kg ({self.scrap_percentage:.1f}%)>'
    
    @property
    def bom_expected_scrap_percentage(self):
        """Get expected scrap percentage from BOM"""
        return self.bom.estimated_scrap_percent if self.bom else 0.0
    
    @property
    def scrap_variance_percentage(self):
        """Calculate variance between actual and expected scrap"""
        expected = self.bom_expected_scrap_percentage
        if expected > 0:
            return self.scrap_percentage - expected
        return 0.0
    
    @property
    def is_excessive_scrap(self):
        """Check if scrap exceeds BOM expectations by more than 5%"""
        return abs(self.scrap_variance_percentage) > 5.0
    
    @property
    def efficiency_percentage(self):
        """Calculate material efficiency (output/input)"""
        if self.input_weight > 0:
            return (self.output_weight / self.input_weight) * 100
        return 0.0
    
    def calculate_scrap_metrics(self):
        """Auto-calculate scrap weight and percentage"""
        self.scrap_weight = self.input_weight - self.output_weight
        if self.input_weight > 0:
            self.scrap_percentage = (self.scrap_weight / self.input_weight) * 100
        else:
            self.scrap_percentage = 0.0
        
        # Calculate total recovery value
        self.total_recovery_value = self.scrap_weight * self.recovery_value_per_kg
    
    def create_scrap_batch(self):
        """Create a new batch record for the scrap generated"""
        if self.scrap_weight > 0 and not self.scrap_batch_id:
            from models import ItemBatch
            
            scrap_batch = ItemBatch()
            scrap_batch.item_id = self.material_item_id  # Same material type as input
            scrap_batch.batch_number = f"SCRAP-{self.scrap_code}-{datetime.now().strftime('%Y%m%d')}"
            scrap_batch.total_quantity = self.scrap_weight
            scrap_batch.qty_scrap = self.scrap_weight  # All quantity is scrap
            scrap_batch.quality_status = 'scrap'
            scrap_batch.storage_location = self.storage_location
            scrap_batch.manufacture_date = datetime.now().date()
            scrap_batch.created_by = self.recorded_by
            
            db.session.add(scrap_batch)
            db.session.flush()
            
            self.scrap_batch_id = scrap_batch.id
            return scrap_batch
        return None

class ScrapReuse(db.Model):
    """
    Track when scrap materials are reused in other production jobs
    """
    __tablename__ = 'scrap_reuse'
    
    id = db.Column(db.Integer, primary_key=True)
    original_scrap_id = db.Column(db.Integer, db.ForeignKey('scrap_tracking.id'), nullable=False)
    reuse_production_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    reuse_job_card_id = db.Column(db.Integer, db.ForeignKey('job_cards.id'), nullable=True)
    
    weight_reused = db.Column(db.Float, nullable=False)  # How much scrap was reused
    reuse_date = db.Column(db.DateTime, default=datetime.utcnow)
    reuse_purpose = db.Column(db.String(200))  # What was it used for
    cost_savings = db.Column(db.Float, default=0.0)  # Estimated cost savings from reuse
    
    # Relationships
    original_scrap = relationship('ScrapTracking', backref='reuse_records')
    reuse_production = relationship('ProductionOrder', backref='scrap_reuse_records')
    reuse_job_card = relationship('JobCard', backref='scrap_reuse_records')
    
    def __repr__(self):
        return f'<ScrapReuse {self.weight_reused}kg from {self.original_scrap.scrap_code}>'

class ScrapSale(db.Model):
    """
    Track sale/disposal of scrap materials to external vendors
    """
    __tablename__ = 'scrap_sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_code = db.Column(db.String(50), unique=True, nullable=False)  # SCRAP-SALE-001
    scrap_tracking_id = db.Column(db.Integer, db.ForeignKey('scrap_tracking.id'), nullable=False)
    
    buyer_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)  # Scrap buyer
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    weight_sold = db.Column(db.Float, nullable=False)
    rate_per_kg = db.Column(db.Float, nullable=False)
    total_sale_value = db.Column(db.Float, nullable=False)
    
    transport_cost = db.Column(db.Float, default=0.0)
    handling_charges = db.Column(db.Float, default=0.0)
    net_recovery_value = db.Column(db.Float, nullable=False)  # Sale value - costs
    
    payment_status = db.Column(db.String(30), default='pending')  # pending, received, partial
    payment_date = db.Column(db.DateTime, nullable=True)
    invoice_number = db.Column(db.String(50))
    
    # Relationships
    scrap_record = relationship('ScrapTracking', backref='sale_records')
    buyer = relationship('Supplier', backref='scrap_purchases')
    
    def __repr__(self):
        return f'<ScrapSale {self.sale_code}: {self.weight_sold}kg @ ₹{self.rate_per_kg}/kg>'
    
    def calculate_totals(self):
        """Auto-calculate total values"""
        self.total_sale_value = self.weight_sold * self.rate_per_kg
        self.net_recovery_value = self.total_sale_value - self.transport_cost - self.handling_charges