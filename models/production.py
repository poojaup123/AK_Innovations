"""Production Order Model with complete Job Work integration"""

from app import db
from datetime import datetime
from sqlalchemy import func
from models import CompanySettings

class ProductionOrder(db.Model):
    """Production Order model integrated with Job Work system"""
    __tablename__ = 'production_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Quantities
    quantity_ordered = db.Column(db.Float, nullable=False)
    quantity_produced = db.Column(db.Float, default=0.0)
    quantity_remaining = db.Column(db.Float, default=0.0)
    
    # Dates
    order_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    start_date = db.Column(db.Date)
    expected_completion = db.Column(db.Date)
    actual_completion = db.Column(db.Date)
    
    # Status tracking (compatible with existing database)
    status = db.Column(db.String(20), default='draft')  # draft, open, in_progress, partial, completed, cancelled
    priority = db.Column(db.String(10), default='normal')  # low, normal, high, urgent
    
    # Cost tracking
    material_cost = db.Column(db.Float, default=0.0)
    labor_cost = db.Column(db.Float, default=0.0)
    overhead_cost = db.Column(db.Float, default=0.0)
    job_work_cost = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, default=0.0)
    cost_per_unit = db.Column(db.Float, default=0.0)
    
    # References
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bom = db.relationship('BOM', backref='production_orders')
    product = db.relationship('Item', backref='production_orders')
    # Note: job_works and grn_entries relationships removed due to missing foreign keys
    # These can be re-added when proper foreign key columns exist
    
    def __init__(self, **kwargs):
        super(ProductionOrder, self).__init__(**kwargs)
        if not self.po_number:
            self.po_number = self.generate_po_number()
        self.quantity_remaining = self.quantity_ordered
    
    @staticmethod
    def generate_po_number():
        """Generate unique production order number"""
        try:
            settings = CompanySettings.query.first()
            prefix = settings.po_number_prefix if settings and settings.po_number_prefix else "PO"
        except:
            prefix = "PO"
        
        # Get next sequential number
        last_order = ProductionOrder.query.order_by(ProductionOrder.id.desc()).first()
        next_num = 1 if not last_order else last_order.id + 1
        
        return f"{prefix}-{datetime.now().year}-{str(next_num).zfill(4)}"
    
    def explode_bom(self):
        """Multi-level BOM explosion with phantom BOM support"""
        from models import BOMItem
        materials_required = []
        
        def explode_recursive(bom_id, parent_qty=1, level=0):
            bom_items = BOMItem.query.filter_by(bom_id=bom_id).all()
            
            for bom_item in bom_items:
                required_qty = bom_item.quantity * parent_qty * self.quantity_ordered
                
                # Check if this item has its own BOM (sub-assembly)
                try:
                    sub_bom = bom_item.item.bom_items.first() if hasattr(bom_item.item, 'bom_items') else None
                except:
                    sub_bom = None
                
                if sub_bom and sub_bom.bom.is_phantom:
                    # Phantom BOM - explode further without adding to materials list
                    explode_recursive(sub_bom.bom.id, required_qty, level + 1)
                elif sub_bom:
                    # Regular sub-assembly - add to materials and explode
                    materials_required.append({
                        'item_id': bom_item.item_id,
                        'item': bom_item.item,
                        'quantity_required': required_qty,
                        'uom': bom_item.uom,
                        'level': level,
                        'type': 'sub_assembly'
                    })
                    explode_recursive(sub_bom.bom.id, required_qty, level + 1)
                else:
                    # Raw material - add to list
                    materials_required.append({
                        'item_id': bom_item.item_id,
                        'item': bom_item.item,
                        'quantity_required': required_qty,
                        'uom': bom_item.uom,
                        'level': level,
                        'type': 'raw_material'
                    })
        
        explode_recursive(self.bom_id)
        return materials_required
    
    def create_job_works(self):
        """Create job works based on BOM processes"""
        from models import JobWork
        from services.jobwork_automation import JobWorkAutomationService
        
        materials = self.explode_bom()
        job_works_created = []
        
        # Group materials by process requirements
        process_groups = {}
        for material in materials:
            # Check if item requires processing
            if hasattr(material['item'], 'requires_processing') and material['item'].requires_processing:
                process_type = material['item'].default_process or 'machining'
                if process_type not in process_groups:
                    process_groups[process_type] = []
                process_groups[process_type].append(material)
        
        # Create job work for each process group
        for process_type, materials_group in process_groups.items():
            job_work = JobWorkAutomationService.create_from_production_order(
                production_order=self,
                materials=materials_group,
                process_type=process_type
            )
            if job_work:
                job_works_created.append(job_work)
        
        return job_works_created
    
    def can_transition_to_status(self, new_status):
        """Check if production order can transition to the specified status using validation service"""
        from models.status_tracking import StatusValidationService
        return StatusValidationService.validate_production_status_transition(self.status, new_status)
    
    def update_status(self, new_status, user_id=None, notes=None, auto_update=False):
        """Update production status with validation and logging"""
        from models.status_tracking import StatusValidationService, ProductionStatusHistory
        
        # Validate transition
        if not self.can_transition_to_status(new_status):
            raise ValueError(f"Invalid status transition from {self.status} to {new_status}")
        
        # Check prerequisites
        if not auto_update:
            errors = StatusValidationService.check_production_prerequisites(self, new_status)
            if errors:
                raise ValueError(f"Cannot change status: {'; '.join(errors)}")
        
        # Store previous status and update
        old_status = self.status
        self.status = new_status
        
        # Auto-update related fields based on status
        if new_status == 'in_progress' and not self.start_date:
            self.start_date = datetime.utcnow().date()
        elif new_status in ['completed'] and not self.actual_completion:
            self.actual_completion = datetime.utcnow().date()
        
        # Create status history record
        history = ProductionStatusHistory(
            production_order_id=self.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user_id,
            change_reason=notes or f"Status changed from {old_status} to {new_status}",
            completion_percentage_at_change=self.get_completion_percentage(),
            quantity_produced_at_change=self.quantity_produced,
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        
        return True
    
    def check_material_readiness(self):
        """Check if all required materials are available for production"""
        if not self.bom:
            return False, "No BOM associated with production order"
        
        shortages = []
        for bom_item in self.bom.items:
            material = bom_item.material or bom_item.item
            if material:
                required_qty = bom_item.quantity_required * self.quantity_ordered
                available_qty = getattr(material, 'current_stock', 0) or 0
                
                if available_qty < required_qty:
                    shortages.append({
                        'material': material.name,
                        'required': required_qty,
                        'available': available_qty,
                        'shortage': required_qty - available_qty
                    })
        
        if shortages:
            return False, f"Material shortages: {len(shortages)} items short"
        
        return True, "All materials available"
    
    def update_progress(self):
        """Enhanced production progress tracking with automatic status updates"""
        completed_qty = 0
        total_cost = 0
        
        # Calculate from completed job works
        total_job_works = 0
        completed_job_works = 0
        
        for job_work in self.job_works:
            total_job_works += 1
            if job_work.status == 'completed':
                completed_job_works += 1
                completed_qty += job_work.quantity_received or 0
                total_cost += job_work.total_cost or 0
        
        # Update quantities
        self.quantity_produced = completed_qty
        self.quantity_remaining = max(0, self.quantity_ordered - completed_qty)
        self.job_work_cost = total_cost
        
        # Auto-update status based on progress with validation
        try:
            completion_percentage = (completed_qty / self.quantity_ordered * 100) if self.quantity_ordered > 0 else 0
            
            if completion_percentage >= 100:
                if self.can_transition_to_status('completed'):
                    self.update_status('completed', auto_update=True, 
                                     notes=f"Auto-completed: {completion_percentage:.1f}% progress achieved")
            elif completion_percentage > 0 and completion_percentage < 100:
                if self.can_transition_to_status('partial'):
                    self.update_status('partial', auto_update=True,
                                     notes=f"Auto-updated: {completion_percentage:.1f}% progress")
            elif total_job_works > 0 and self.status == 'draft':
                if self.can_transition_to_status('in_progress'):
                    self.update_status('in_progress', auto_update=True,
                                     notes="Auto-started: Job works initiated")
        except ValueError:
            # Status transition not allowed, continue without status update
            pass
        
        # Calculate total cost
        self.total_cost = self.material_cost + self.labor_cost + self.overhead_cost + self.job_work_cost
        if self.quantity_produced > 0:
            self.cost_per_unit = self.total_cost / self.quantity_produced
        
        db.session.commit()
    
    def get_status_history(self):
        """Get status change history for this production order"""
        from models.status_tracking import ProductionStatusHistory
        return ProductionStatusHistory.query.filter_by(
            production_order_id=self.id
        ).order_by(ProductionStatusHistory.timestamp.desc()).all()
    
    def get_completion_percentage(self):
        """Calculate completion percentage"""
        if self.quantity_ordered == 0:
            return 0
        return min(100, (self.quantity_produced / self.quantity_ordered) * 100)
    
    def get_process_completion_percentage(self):
        """Calculate process completion percentage based on job works"""
        if not hasattr(self, 'job_works') or self.job_works.count() == 0:
            return 0
        
        total_job_works = self.job_works.count()
        completed_job_works = self.job_works.filter_by(status='completed').count()
        
        return min(100, (completed_job_works / total_job_works) * 100)
    
    def get_valid_status_transitions(self):
        """Get list of valid status transitions from current status"""
        from models.status_tracking import StatusValidationService
        return StatusValidationService.get_valid_production_transitions(self.status)
    
    def get_status_display_info(self):
        """Get comprehensive status information for UI display"""
        return {
            'current_status': self.status,
            'valid_transitions': self.get_valid_status_transitions(),
            'completion_percentage': self.get_completion_percentage(),
            'process_completion_percentage': self.get_process_completion_percentage(),
            'can_start': self.can_transition_to_status('in_progress'),
            'can_complete': self.can_transition_to_status('completed'),
            'materials_check': self.check_material_readiness()
        }
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'po_number': self.po_number,
            'product': self.product.name if self.product else None,
            'quantity_ordered': self.quantity_ordered,
            'quantity_produced': self.quantity_produced,
            'quantity_remaining': self.quantity_remaining,
            'status': self.status,
            'priority': self.priority,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'expected_completion': self.expected_completion.isoformat() if self.expected_completion else None,
            'actual_completion': self.actual_completion.isoformat() if self.actual_completion else None,
            'total_cost': self.total_cost,
            'cost_per_unit': self.cost_per_unit,
            'job_works_count': self.job_works.count(),
            'completion_percentage': self.get_completion_percentage(),
            'process_completion_percentage': self.get_process_completion_percentage(),
            'valid_transitions': self.get_valid_status_transitions(),
            'status_info': self.get_status_display_info(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ProductionProcess(db.Model):
    """Individual process step in production with multi-vendor routing"""
    __tablename__ = 'production_processes'
    
    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey('production_orders.id'), nullable=False)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'))
    
    # Process details
    sequence_number = db.Column(db.Integer, nullable=False, default=1)
    process_name = db.Column(db.String(100), nullable=False)
    process_type = db.Column(db.String(20), default='outsourced')  # in_house, outsourced
    
    # Assignment
    assigned_to = db.Column(db.String(200))  # Vendor name or department
    assigned_type = db.Column(db.String(20))  # vendor, department
    
    # Quantities and timing
    input_quantity = db.Column(db.Float, nullable=False)
    output_quantity = db.Column(db.Float, default=0.0)
    scrap_quantity = db.Column(db.Float, default=0.0)
    
    # Status and dates
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, on_hold
    start_date = db.Column(db.Date)
    completion_date = db.Column(db.Date)
    
    # Cost tracking
    estimated_cost = db.Column(db.Float, default=0.0)
    actual_cost = db.Column(db.Float, default=0.0)
    
    # Quality tracking
    quality_status = db.Column(db.String(20), default='pending')  # pending, passed, failed, rework
    quality_remarks = db.Column(db.Text)
    
    # Multi-vendor routing
    next_process_id = db.Column(db.Integer, db.ForeignKey('production_processes.id'))
    previous_process_id = db.Column(db.Integer, db.ForeignKey('production_processes.id'))
    
    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    production_order = db.relationship('ProductionOrder', backref='processes')
    job_work = db.relationship('JobWork', backref='production_process')
    next_process = db.relationship('ProductionProcess', remote_side=[id], foreign_keys=[next_process_id])
    previous_process = db.relationship('ProductionProcess', remote_side=[id], foreign_keys=[previous_process_id])
    
    def forward_to_next_vendor(self):
        """Auto-forward material to next vendor in sequence"""
        if self.next_process and self.status == 'completed':
            from services.jobwork_automation import JobWorkAutomationService
            
            # Create job work for next process
            next_job_work = JobWorkAutomationService.create_sequential_job_work(
                current_process=self,
                next_process=self.next_process,
                output_quantity=self.output_quantity
            )
            
            if next_job_work:
                self.next_process.job_work_id = next_job_work.id
                self.next_process.status = 'in_progress'
                self.next_process.start_date = datetime.utcnow().date()
                db.session.commit()
                
                return next_job_work
        return None
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'sequence_number': self.sequence_number,
            'process_name': self.process_name,
            'process_type': self.process_type,
            'assigned_to': self.assigned_to,
            'input_quantity': self.input_quantity,
            'output_quantity': self.output_quantity,
            'scrap_quantity': self.scrap_quantity,
            'status': self.status,
            'quality_status': self.quality_status,
            'estimated_cost': self.estimated_cost,
            'actual_cost': self.actual_cost,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'notes': self.notes
        }