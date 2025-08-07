"""
Batch Tracking Models for Factory Management System
Implements comprehensive batch-wise inventory and job work tracking
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from app import db

class InventoryBatch(db.Model):
    """
    Track inventory in batches with state management
    Supports Raw, WIP, Finished, and Scrap states per batch
    """
    __tablename__ = 'inventory_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    batch_code = db.Column(db.String(50), nullable=False, index=True)
    
    # Quantities by state
    qty_inspection = db.Column(db.Float, default=0.0)  # Materials awaiting inspection
    qty_raw = db.Column(db.Float, default=0.0)
    qty_wip = db.Column(db.Float, default=0.0)
    qty_finished = db.Column(db.Float, default=0.0)
    qty_scrap = db.Column(db.Float, default=0.0)
    
    # Inspection status for this batch
    inspection_status = db.Column(db.String(20), default='pending')  # pending, passed, failed, quarantine
    
    # Batch metadata
    uom = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), default='Default')
    mfg_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    supplier_batch_no = db.Column(db.String(50))  # Vendor's batch number
    purchase_rate = db.Column(db.Float, default=0.0)
    
    # References
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'))  # Source GRN
    source_type = db.Column(db.String(20), default='purchase')  # purchase, production, return
    source_ref_id = db.Column(db.Integer)  # Reference to source document
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='inventory_batches')
    movements = db.relationship('BatchMovement', backref='batch', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_quantity(self):
        """Total quantity across all states"""
        return (self.qty_inspection or 0) + (self.qty_raw or 0) + (self.qty_wip or 0) + (self.qty_finished or 0) + (self.qty_scrap or 0)
    
    @property
    def available_quantity(self):
        """Available quantity (Raw + Finished) - NOT including inspection"""
        return (self.qty_raw or 0) + (self.qty_finished or 0)
    
    @property
    def inspection_quantity(self):
        """Quantity awaiting inspection (not available for use)"""
        return self.qty_inspection or 0
    
    @property
    def is_expired(self):
        """Check if batch is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()
    
    @property
    def age_days(self):
        """Age of batch in days"""
        if not self.mfg_date:
            return 0
        return (date.today() - self.mfg_date).days
    
    def move_quantity(self, quantity, from_state, to_state, ref_type=None, ref_id=None, notes=None):
        """
        Move quantity between states within this batch
        Returns True if successful, False if insufficient quantity
        """
        if quantity <= 0:
            return False
            
        # Check available quantity in from_state
        from_qty = getattr(self, f'qty_{from_state}', 0) or 0
        if from_qty < quantity:
            return False
        
        # Perform the move
        setattr(self, f'qty_{from_state}', from_qty - quantity)
        to_qty = getattr(self, f'qty_{to_state}', 0) or 0
        setattr(self, f'qty_{to_state}', to_qty + quantity)
        
        # Log the movement
        movement = BatchMovement(
            batch_id=self.id,
            item_id=self.item_id,
            quantity=quantity,
            from_state=from_state,
            to_state=to_state,
            movement_type='internal_transfer',
            ref_type=ref_type,
            ref_id=ref_id,
            notes=notes
        )
        db.session.add(movement)
        
        # Create accounting entry for state transfer valuation impact
        try:
            from services.accounting_automation import AccountingAutomation
            # Calculate valuation change based on transfer
            estimated_unit_cost = getattr(self, 'purchase_rate', 0) / max(getattr(self, 'initial_qty_raw', 1), 1)
            valuation_change = quantity * estimated_unit_cost
            
            # Create inventory valuation entry for internal movement
            if valuation_change > 0:
                AccountingAutomation.create_inventory_valuation_entry(
                    self.item, quantity, valuation_change, 'internal_transfer'
                )
        except Exception as e:
            print(f"Warning: Failed to create accounting entry for batch movement: {str(e)}")
        
        self.updated_at = datetime.utcnow()
        return True
    
    def __repr__(self):
        return f'<InventoryBatch {self.batch_code}: {self.item.name if self.item else "Unknown"}>'

class BatchMovement(db.Model):
    """
    Track all batch quantity movements for audit trail
    """
    __tablename__ = 'batch_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Movement details
    quantity = db.Column(db.Float, nullable=False)
    from_state = db.Column(db.String(20))  # raw, wip, finished, scrap, or None for new batch
    to_state = db.Column(db.String(20))    # raw, wip, finished, scrap, or None for consumed
    movement_type = db.Column(db.String(30), nullable=False)  # receipt, issue, return, transfer, scrap, internal_transfer
    
    # Reference to source document
    ref_type = db.Column(db.String(20))  # grn, jobwork, production, adjustment
    ref_id = db.Column(db.Integer)       # ID of reference document
    notes = db.Column(db.Text)
    
    # Metadata
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item')
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<BatchMovement {self.quantity} {self.from_state}->{self.to_state}>'

class JobWorkBatch(db.Model):
    """
    Track batch-wise job work processing
    Links input batches to output batches through job work
    """
    __tablename__ = 'jobwork_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    
    # Input batch details
    input_batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'))
    input_item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity_issued = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, default=date.today)
    
    # Output batch details (filled when job work is returned)
    output_batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'))
    output_item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity_produced = db.Column(db.Float, default=0.0)
    quantity_scrap = db.Column(db.Float, default=0.0)
    quantity_returned_unused = db.Column(db.Float, default=0.0)
    return_date = db.Column(db.Date)
    
    # Process tracking
    process_name = db.Column(db.String(50), nullable=False)
    vendor_name = db.Column(db.String(100))
    rate_per_unit = db.Column(db.Float, default=0.0)
    
    # Enhanced vendor location tracking
    current_location = db.Column(db.String(100), default='issued')  # issued, at_vendor, in_transit, returned, completed
    current_vendor = db.Column(db.String(100))  # Current vendor holding the material
    next_vendor = db.Column(db.String(100))  # Next vendor in the process chain
    process_sequence = db.Column(db.Integer, default=1)  # Order in multi-process workflow
    is_auto_forward_enabled = db.Column(db.Boolean, default=False)  # Auto-forward to next vendor
    
    # Status
    status = db.Column(db.String(20), default='issued')  # issued, in_progress, returned, completed
    notes = db.Column(db.Text)
    
    # Quality tracking per process
    quality_status = db.Column(db.String(20), default='pending')  # pending, passed, failed, rework_needed
    quality_notes = db.Column(db.Text)
    inspected_by = db.Column(db.String(100))
    inspection_date = db.Column(db.Date)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_work = db.relationship('JobWork', backref='batch_records')
    input_batch = db.relationship('InventoryBatch', foreign_keys=[input_batch_id], backref='job_work_issues')
    output_batch = db.relationship('InventoryBatch', foreign_keys=[output_batch_id], backref='job_work_returns')
    input_item = db.relationship('Item', foreign_keys=[input_item_id])
    output_item = db.relationship('Item', foreign_keys=[output_item_id])
    
    @property
    def yield_percentage(self):
        """Calculate yield percentage (output/input * 100)"""
        if not self.quantity_issued or self.quantity_issued == 0:
            return 0.0
        return (self.quantity_produced / self.quantity_issued) * 100
    
    @property
    def scrap_percentage(self):
        """Calculate scrap percentage"""
        if not self.quantity_issued or self.quantity_issued == 0:
            return 0.0
        return (self.quantity_scrap / self.quantity_issued) * 100
    
    @property
    def is_completed(self):
        """Check if job work batch is completed"""
        return self.status == 'completed' and self.return_date is not None
    
    @property
    def location_status_badge_class(self):
        """Return Bootstrap badge class for location status"""
        location_classes = {
            'issued': 'bg-info',
            'at_vendor': 'bg-warning', 
            'in_transit': 'bg-primary',
            'returned': 'bg-success',
            'completed': 'bg-success'
        }
        return location_classes.get(self.current_location, 'bg-secondary')
    
    @property
    def quality_status_badge_class(self):
        """Return Bootstrap badge class for quality status"""
        quality_classes = {
            'pending': 'bg-secondary',
            'passed': 'bg-success',
            'failed': 'bg-danger',
            'rework_needed': 'bg-warning'
        }
        return quality_classes.get(self.quality_status, 'bg-secondary')
    
    @property
    def current_location_display(self):
        """Human readable current location"""
        if self.current_location == 'at_vendor' and self.current_vendor:
            return f"At {self.current_vendor}"
        elif self.current_location == 'in_transit' and self.next_vendor:
            return f"In transit to {self.next_vendor}"
        else:
            return self.current_location.replace('_', ' ').title()
    
    def update_location(self, new_location, vendor=None, notes=None):
        """Update location with history tracking"""
        old_location = self.current_location
        self.current_location = new_location
        
        if vendor:
            if new_location == 'at_vendor':
                self.current_vendor = vendor
            elif new_location == 'in_transit':
                self.next_vendor = vendor
        
        if notes:
            self.notes = f"{self.notes or ''}\n{datetime.now().strftime('%Y-%m-%d %H:%M')}: {notes}".strip()
        
        # Create location history record
        history = JobWorkLocationHistory(
            jobwork_batch_id=self.id,
            from_location=old_location,
            to_location=new_location,
            vendor_name=vendor,
            notes=notes,
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<JobWorkBatch {self.job_work.job_number if self.job_work else "Unknown"}: {self.process_name}>'

class BatchTraceability(db.Model):
    """
    Track end-to-end traceability of batches through the production process
    """
    __tablename__ = 'batch_traceability'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Source batch
    source_batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False)
    source_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Destination batch
    dest_batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False)
    dest_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Transformation details
    transformation_type = db.Column(db.String(30), nullable=False)  # jobwork, production, assembly
    transformation_ref_id = db.Column(db.Integer)  # Reference to jobwork, production order, etc.
    quantity_consumed = db.Column(db.Float, nullable=False)
    quantity_produced = db.Column(db.Float, nullable=False)
    
    # Process metadata
    process_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    source_batch = db.relationship('InventoryBatch', foreign_keys=[source_batch_id], backref='transformations_out')
    dest_batch = db.relationship('InventoryBatch', foreign_keys=[dest_batch_id], backref='transformations_in')
    source_item = db.relationship('Item', foreign_keys=[source_item_id])
    dest_item = db.relationship('Item', foreign_keys=[dest_item_id])
    
    def __repr__(self):
        return f'<BatchTraceability {self.source_batch.batch_code if self.source_batch else "Unknown"} -> {self.dest_batch.batch_code if self.dest_batch else "Unknown"}>'"""
Batch Movement Ledger Models - Fixed Version
Tracks every batch movement across all modules for complete traceability
"""

from app import db
from datetime import datetime
from sqlalchemy import func

class BatchMovementLedger(db.Model):
    """
    Central ledger tracking every batch movement across all modules
    Every action that affects batch quantity/state creates a movement record
    """
    __tablename__ = 'batch_movement_ledger'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference Information
    ref_type = db.Column(db.String(50), nullable=False)  # GRN, JobWork, Production, Dispatch, Scrap, etc.
    ref_id = db.Column(db.Integer, nullable=False)  # ID of the reference document
    ref_number = db.Column(db.String(100))  # Human-readable reference number
    
    # Batch Information - Fixed foreign key reference
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Movement Details
    from_state = db.Column(db.String(50))  # None, Raw, WIP_Cutting, etc.
    to_state = db.Column(db.String(50), nullable=False)  # Raw, WIP_Cutting, Finished, Scrap, etc.
    quantity = db.Column(db.Float, nullable=False)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    
    # Additional Context
    process_name = db.Column(db.String(100))  # For WIP states: cutting, bending, etc.
    vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))  # For job work movements
    storage_location = db.Column(db.String(200))
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    
    # Quality and Notes
    quality_status = db.Column(db.String(50), default='good')
    notes = db.Column(db.Text)
    
    # Timestamps
    movement_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    batch = db.relationship('InventoryBatch', backref='movement_history')
    item = db.relationship('Item', backref='batch_movements')
    vendor = db.relationship('Supplier', backref='batch_movements')
    created_by_user = db.relationship('User', backref='batch_movements_created')
    
    def __repr__(self):
        return f'<BatchMovement {self.ref_type}-{self.ref_id}: {self.quantity} {self.item.name if self.item else ""}>'
    
    @property
    def movement_description(self):
        """Human-readable description of the movement"""
        from_desc = self.from_state.replace('_', ' ').title() if self.from_state else 'External'
        to_desc = self.to_state.replace('_', ' ').title()
        return f"{from_desc} → {to_desc}"
    
    @classmethod
    def create_movement(cls, ref_type, ref_id, batch_id, item_id, from_state, to_state, 
                       quantity, unit_of_measure, **kwargs):
        """Helper method to create batch movement records"""
        movement = cls(
            ref_type=ref_type,
            ref_id=ref_id,
            batch_id=batch_id,
            item_id=item_id,
            from_state=from_state,
            to_state=to_state,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            **kwargs
        )
        db.session.add(movement)
        return movement
    
    @classmethod
    def get_batch_history(cls, batch_id):
        """Get complete movement history for a batch"""
        return cls.query.filter_by(batch_id=batch_id).order_by(cls.created_at).all()


class JobWorkLocationHistory(db.Model):
    """Track location history of job work batches"""
    __tablename__ = 'jobwork_location_history'
    
    id = db.Column(db.Integer, primary_key=True)
    jobwork_batch_id = db.Column(db.Integer, db.ForeignKey('jobwork_batches.id'), nullable=False)
    
    from_location = db.Column(db.String(100))
    to_location = db.Column(db.String(100), nullable=False)
    vendor_name = db.Column(db.String(100))
    
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    jobwork_batch = db.relationship('JobWorkBatch', backref='location_history')
    user = db.relationship('User', backref='location_updates')
    
    def __repr__(self):
        return f'<LocationHistory {self.from_location} → {self.to_location}>'


class JobWorkProcessWorkflow(db.Model):
    """Define multi-vendor process workflows"""
    __tablename__ = 'jobwork_process_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_name = db.Column(db.String(100), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    
    # Process chain definition
    sequence_number = db.Column(db.Integer, nullable=False)
    process_name = db.Column(db.String(100), nullable=False)
    vendor_name = db.Column(db.String(100))
    department_name = db.Column(db.String(100))
    
    # Auto-forwarding settings
    auto_forward_enabled = db.Column(db.Boolean, default=False)
    requires_quality_check = db.Column(db.Boolean, default=True)
    expected_duration_days = db.Column(db.Integer, default=3)
    
    # Notifications
    send_alerts = db.Column(db.Boolean, default=True)
    alert_email = db.Column(db.String(200))
    alert_phone = db.Column(db.String(20))
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='process_workflows')
    
    def __repr__(self):
        return f'<ProcessWorkflow {self.workflow_name}: {self.process_name}>'
    
    @classmethod
    def get_item_movements(cls, item_id, start_date=None, end_date=None):
        """Get movements for an item within date range"""
        query = cls.query.filter_by(item_id=item_id)
        if start_date:
            query = query.filter(cls.movement_date >= start_date)
        if end_date:
            query = query.filter(cls.movement_date <= end_date)
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_vendor_movements(cls, vendor_id, start_date=None, end_date=None):
        """Get movements related to a specific vendor"""
        query = cls.query.filter_by(vendor_id=vendor_id)
        if start_date:
            query = query.filter(cls.movement_date >= start_date)
        if end_date:
            query = query.filter(cls.movement_date <= end_date)
        return query.order_by(cls.created_at.desc()).all()

class BatchConsumptionReport(db.Model):
    """
    Aggregated batch consumption data for reporting
    Automatically updated when batch movements occur
    """
    __tablename__ = 'batch_consumption_report'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Batch Information - Fixed foreign key reference
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    batch_number = db.Column(db.String(100), nullable=False)
    
    # Consumption Summary
    total_received = db.Column(db.Float, default=0.0)  # From GRN
    total_issued = db.Column(db.Float, default=0.0)    # To Job Work/Production
    total_finished = db.Column(db.Float, default=0.0)  # Finished products
    total_scrap = db.Column(db.Float, default=0.0)     # Scrapped
    total_returned = db.Column(db.Float, default=0.0)  # Unused returned
    total_dispatched = db.Column(db.Float, default=0.0) # Dispatched to customers
    
    # Process-wise consumption
    qty_cutting = db.Column(db.Float, default=0.0)
    qty_bending = db.Column(db.Float, default=0.0)
    qty_welding = db.Column(db.Float, default=0.0)
    qty_zinc = db.Column(db.Float, default=0.0)
    qty_painting = db.Column(db.Float, default=0.0)
    qty_assembly = db.Column(db.Float, default=0.0)
    qty_machining = db.Column(db.Float, default=0.0)
    qty_polishing = db.Column(db.Float, default=0.0)
    
    # Efficiency Metrics
    yield_percentage = db.Column(db.Float)  # (finished / issued) * 100
    scrap_percentage = db.Column(db.Float)  # (scrap / issued) * 100
    utilization_percentage = db.Column(db.Float)  # (issued / received) * 100
    
    # Vendor and Cost Information
    vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    unit_cost = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    
    # Timestamps
    first_received = db.Column(db.Date)
    last_movement = db.Column(db.Date)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    batch = db.relationship('InventoryBatch', backref='consumption_report')
    item = db.relationship('Item', backref='batch_consumption_reports')
    vendor = db.relationship('Supplier', backref='batch_consumption_reports')
    
    def __repr__(self):
        return f'<BatchConsumption {self.batch_number}: {self.yield_percentage:.1f}% yield>'
    
    @property
    def is_active(self):
        """Check if batch is still active (has remaining quantity)"""
        return (self.total_received - self.total_issued - self.total_dispatched) > 0
    
    @property
    def remaining_quantity(self):
        """Calculate remaining quantity in batch"""
        return max(0, self.total_received - self.total_issued - self.total_dispatched)
    
    def update_from_movement(self, movement):
        """Update consumption report based on batch movement"""
        if movement.ref_type == 'GRN':
            self.total_received += movement.quantity
            if not self.first_received:
                self.first_received = movement.movement_date
        
        elif movement.ref_type in ['JobWork', 'Production']:
            if movement.to_state.startswith('WIP') or movement.to_state == 'Issued':
                self.total_issued += movement.quantity
                
                # Update process-wise quantities
                if 'cutting' in movement.to_state.lower():
                    self.qty_cutting += movement.quantity
                elif 'bending' in movement.to_state.lower():
                    self.qty_bending += movement.quantity
                elif 'welding' in movement.to_state.lower():
                    self.qty_welding += movement.quantity
                elif 'zinc' in movement.to_state.lower():
                    self.qty_zinc += movement.quantity
                elif 'painting' in movement.to_state.lower():
                    self.qty_painting += movement.quantity
                elif 'assembly' in movement.to_state.lower():
                    self.qty_assembly += movement.quantity
                elif 'machining' in movement.to_state.lower():
                    self.qty_machining += movement.quantity
                elif 'polishing' in movement.to_state.lower():
                    self.qty_polishing += movement.quantity
            
            elif movement.to_state == 'Finished':
                self.total_finished += movement.quantity
            elif movement.to_state == 'Scrap':
                self.total_scrap += movement.quantity
            elif movement.to_state == 'Raw' and movement.from_state != 'None':
                self.total_returned += movement.quantity
        
        elif movement.ref_type == 'Dispatch':
            self.total_dispatched += movement.quantity
        
        # Update efficiency metrics
        self._calculate_efficiency_metrics()
        self.last_movement = movement.movement_date
        self.updated_at = datetime.utcnow()
    
    def _calculate_efficiency_metrics(self):
        """Calculate yield, scrap, and utilization percentages"""
        if self.total_issued > 0:
            self.yield_percentage = (self.total_finished / self.total_issued) * 100
            self.scrap_percentage = (self.total_scrap / self.total_issued) * 100
        
        if self.total_received > 0:
            self.utilization_percentage = (self.total_issued / self.total_received) * 100
    
    @classmethod
    def get_or_create(cls, batch_id):
        """Get existing report or create new one for batch"""
        report = cls.query.filter_by(batch_id=batch_id).first()
        if not report:
            from models import ItemBatch
            batch = ItemBatch.query.get(batch_id)
            if batch:
                report = cls(
                    batch_id=batch_id,
                    item_id=batch.item_id,
                    batch_number=batch.batch_number
                )
                db.session.add(report)
        return report