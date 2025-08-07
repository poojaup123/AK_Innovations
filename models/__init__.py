from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from .department import Department

# Import UOM models
from .uom import UnitOfMeasure, UOMConversion, ItemUOMConversion, UOMConversionLog

# Import permission models
from .permissions import Permission, UserPermission

# Import custom report models
from .custom_reports import CustomReport, CustomReportExecution

# Import visual scanning models
from .visual_scanning import ComponentDetection, DetectedComponent, ComponentDetectionTemplate

# Import notification models
from .notifications import NotificationRecipient, NotificationLog

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False, default='Your Company Name')
    address_line1 = db.Column(db.String(200), default='Your Company Address Line 1')
    address_line2 = db.Column(db.String(200), default='Your Company Address Line 2')
    city = db.Column(db.String(100), default='City')
    state = db.Column(db.String(100), default='State')
    pin_code = db.Column(db.String(10), default='PIN Code')
    phone = db.Column(db.String(20), default='+91-XXX-XXXXXXX')
    email = db.Column(db.String(120))
    gst_number = db.Column(db.String(50), default='XXAABCRXXXXMXZC')
    arn_number = db.Column(db.String(50), default='AAXXXXXXXGX')
    website = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_settings(cls):
        """Get company settings, create default if none exist"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')  # admin, staff
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission"""
        # Admins have all permissions
        if self.is_admin():
            return True
        
        # Check user-specific permissions
        from .permissions import Permission, UserPermission
        permission = Permission.query.filter_by(code=permission_code).first()
        if not permission:
            return False
        
        user_permission = UserPermission.query.filter_by(
            user_id=self.id,
            permission_id=permission.id,
            granted=True
        ).first()
        
        return user_permission is not None
    
    def get_permissions(self):
        """Get all permissions for this user"""
        if self.is_admin():
            from .permissions import Permission
            return Permission.query.all()
        
        from .permissions import Permission, UserPermission
        return db.session.query(Permission).join(UserPermission).filter(
            UserPermission.user_id == self.id,
            UserPermission.granted == True
        ).all()
    
    def grant_permission(self, permission_code, granted_by_user_id):
        """Grant a permission to this user"""
        from .permissions import Permission, UserPermission
        permission = Permission.query.filter_by(code=permission_code).first()
        if not permission:
            return False
        
        # Check if permission already exists
        existing = UserPermission.query.filter_by(
            user_id=self.id,
            permission_id=permission.id
        ).first()
        
        if existing:
            existing.granted = True
            existing.granted_by = granted_by_user_id
            existing.granted_at = datetime.utcnow()
        else:
            user_permission = UserPermission(
                user_id=self.id,
                permission_id=permission.id,
                granted=True,
                granted_by=granted_by_user_id
            )
            db.session.add(user_permission)
        
        return True
    
    def revoke_permission(self, permission_code):
        """Revoke a permission from this user"""
        from .permissions import Permission, UserPermission
        permission = Permission.query.filter_by(code=permission_code).first()
        if not permission:
            return False
        
        user_permission = UserPermission.query.filter_by(
            user_id=self.id,
            permission_id=permission.id
        ).first()
        
        if user_permission:
            user_permission.granted = False
        
        return True

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Information
    name = db.Column(db.String(200), nullable=False)  # Full legal name
    contact_person = db.Column(db.String(100))  # Person to contact
    phone = db.Column(db.String(20))  # Mobile number
    email = db.Column(db.String(120))  # Email for orders/inquiries
    
    # Compliance Information
    gst_number = db.Column(db.String(50))  # GSTIN (mandatory for GST)
    pan_number = db.Column(db.String(20))  # PAN (optional, for compliance)
    
    # Address Information
    address = db.Column(db.Text)  # Full postal address
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(10))
    
    # Banking Information (optional, for payments)
    account_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(200))
    ifsc_code = db.Column(db.String(20))
    
    # Transportation Specific (for transporters)
    freight_rate_per_unit = db.Column(db.Float, default=0.0)  # Freight rate amount
    freight_unit_type = db.Column(db.String(20), default='per_km')  # per_km, per_kg, per_box, per_carton, per_ton
    
    # Partner Type - can be 'supplier', 'customer', 'vendor', 'transporter', or 'both'
    partner_type = db.Column(db.String(20), default='supplier')  # supplier, customer, vendor, transporter, both
    
    # Additional Information
    remarks = db.Column(db.Text)  # Any notes
    is_active = db.Column(db.Boolean, default=True)  # Partner status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy=True)
    sales_orders = db.relationship('SalesOrder', backref='customer', foreign_keys='SalesOrder.customer_id', lazy=True)
    
    @property
    def is_supplier(self):
        return self.partner_type in ['supplier', 'vendor', 'both']
    
    @property
    def is_customer(self):
        return self.partner_type in ['customer', 'both']
    
    @property
    def is_vendor(self):
        return self.partner_type in ['vendor', 'both']
    
    @property
    def is_transporter(self):
        return self.partner_type in ['transporter', 'both']

# Customer model removed - now using unified Supplier table for all business partners

class ItemBatch(db.Model):
    """Model for tracking inventory batches/lots for better traceability"""
    __tablename__ = 'item_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    batch_number = db.Column(db.String(50), nullable=False)  # Batch/Lot number
    supplier_batch = db.Column(db.String(50))  # Supplier's batch number
    manufacture_date = db.Column(db.Date)  # Date of manufacture
    expiry_date = db.Column(db.Date)  # Expiry date (if applicable)
    
    # Batch quantities by state
    qty_raw = db.Column(db.Float, default=0.0)
    qty_wip = db.Column(db.Float, default=0.0)  # Legacy WIP
    qty_finished = db.Column(db.Float, default=0.0)
    qty_scrap = db.Column(db.Float, default=0.0)
    
    # Process-specific WIP for this batch
    qty_wip_cutting = db.Column(db.Float, default=0.0)
    qty_wip_bending = db.Column(db.Float, default=0.0)
    qty_wip_welding = db.Column(db.Float, default=0.0)
    qty_wip_zinc = db.Column(db.Float, default=0.0)
    qty_wip_painting = db.Column(db.Float, default=0.0)
    qty_wip_assembly = db.Column(db.Float, default=0.0)
    qty_wip_machining = db.Column(db.Float, default=0.0)
    qty_wip_polishing = db.Column(db.Float, default=0.0)
    
    # Enhanced batch metadata for job work tracking
    purchase_rate = db.Column(db.Float, default=0.0)  # Purchase rate for cost tracking
    storage_location = db.Column(db.String(100), default='Default')  # Storage location
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'))  # Source GRN reference
    
    # Quality information
    quality_status = db.Column(db.String(20), default='good')  # good, defective, expired
    quality_notes = db.Column(db.Text)
    
    # Tracking information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='batches')
    creator = db.relationship('User', backref='created_batches')
    
    @property
    def total_quantity(self):
        """Calculate total quantity across all states"""
        return (
            (self.qty_raw or 0) + (self.qty_wip or 0) + (self.qty_finished or 0) + (self.qty_scrap or 0) +
            (self.qty_wip_cutting or 0) + (self.qty_wip_bending or 0) + (self.qty_wip_welding or 0) +
            (self.qty_wip_zinc or 0) + (self.qty_wip_painting or 0) + (self.qty_wip_assembly or 0) +
            (self.qty_wip_machining or 0) + (self.qty_wip_polishing or 0)
        )
    
    @property
    def available_quantity(self):
        """Available quantity for issuing (Raw + Finished)"""
        return (self.qty_raw or 0) + (self.qty_finished or 0)
    
    @property
    def total_wip_quantity(self):
        """Total WIP across all processes"""
        return (
            (self.qty_wip_cutting or 0) + (self.qty_wip_bending or 0) + (self.qty_wip_welding or 0) +
            (self.qty_wip_zinc or 0) + (self.qty_wip_painting or 0) + (self.qty_wip_assembly or 0) +
            (self.qty_wip_machining or 0) + (self.qty_wip_polishing or 0)
        )
    
    @property
    def is_expired(self):
        """Check if this batch is expired"""
        if self.expiry_date:
            return datetime.now().date() > self.expiry_date
        return False
    
    @property
    def days_to_expiry(self):
        """Days until expiry (negative if expired)"""
        if self.expiry_date:
            return (self.expiry_date - datetime.now().date()).days
        return None
    
    @property
    def age_days(self):
        """Age of batch in days since manufacture"""
        if self.manufacture_date:
            return (datetime.now().date() - self.manufacture_date).days
        return 0
    
    def move_quantity(self, quantity, from_state, to_state):
        """Move quantity between states within this batch"""
        if quantity <= 0:
            return False
            
        # Get current quantity in from_state
        from_qty = getattr(self, f'qty_{from_state}', 0) or 0
        
        if from_qty < quantity:
            return False  # Insufficient quantity
        
        # Move the quantity
        setattr(self, f'qty_{from_state}', from_qty - quantity)
        to_qty = getattr(self, f'qty_{to_state}', 0) or 0
        setattr(self, f'qty_{to_state}', to_qty + quantity)
        
        self.updated_at = datetime.utcnow()
        return True
    
    def issue_for_jobwork(self, quantity, process):
        """Issue quantity from raw to process-specific WIP"""
        if self.qty_raw < quantity:
            return False
            
        self.qty_raw -= quantity
        
        # Move to process-specific WIP
        process_lower = process.lower()
        if process_lower == 'cutting':
            self.qty_wip_cutting += quantity
        elif process_lower == 'bending':
            self.qty_wip_bending += quantity
        elif process_lower == 'welding':
            self.qty_wip_welding += quantity
        elif process_lower == 'zinc':
            self.qty_wip_zinc += quantity
        elif process_lower == 'painting':
            self.qty_wip_painting += quantity
        elif process_lower == 'assembly':
            self.qty_wip_assembly += quantity
        elif process_lower == 'machining':
            self.qty_wip_machining += quantity
        elif process_lower == 'polishing':
            self.qty_wip_polishing += quantity
        else:
            # Unknown process, use legacy WIP
            self.qty_wip += quantity
        
        self.updated_at = datetime.utcnow()
        return True
    
    def receive_from_jobwork(self, finished_qty, scrap_qty, unused_qty, process):
        """Receive finished goods, scrap, and unused material from job work"""
        process_lower = process.lower()
        
        # Get WIP quantity for this process
        if process_lower == 'cutting':
            wip_qty = self.qty_wip_cutting
        elif process_lower == 'bending':
            wip_qty = self.qty_wip_bending
        elif process_lower == 'welding':
            wip_qty = self.qty_wip_welding
        elif process_lower == 'zinc':
            wip_qty = self.qty_wip_zinc
        elif process_lower == 'painting':
            wip_qty = self.qty_wip_painting
        elif process_lower == 'assembly':
            wip_qty = self.qty_wip_assembly
        elif process_lower == 'machining':
            wip_qty = self.qty_wip_machining
        elif process_lower == 'polishing':
            wip_qty = self.qty_wip_polishing
        else:
            wip_qty = self.qty_wip
        
        total_returned = finished_qty + scrap_qty + unused_qty
        if wip_qty < total_returned:
            return False  # Cannot return more than what was sent
        
        # Reduce WIP quantity
        if process_lower == 'cutting':
            self.qty_wip_cutting -= total_returned
        elif process_lower == 'bending':
            self.qty_wip_bending -= total_returned
        elif process_lower == 'welding':
            self.qty_wip_welding -= total_returned
        elif process_lower == 'zinc':
            self.qty_wip_zinc -= total_returned
        elif process_lower == 'painting':
            self.qty_wip_painting -= total_returned
        elif process_lower == 'assembly':
            self.qty_wip_assembly -= total_returned
        elif process_lower == 'machining':
            self.qty_wip_machining -= total_returned
        elif process_lower == 'polishing':
            self.qty_wip_polishing -= total_returned
        else:
            self.qty_wip -= total_returned
        
        # Add to respective states
        if finished_qty > 0:
            self.qty_finished += finished_qty
        if scrap_qty > 0:
            self.qty_scrap += scrap_qty
        if unused_qty > 0:
            self.qty_raw += unused_qty  # Return unused to raw
        
        self.updated_at = datetime.utcnow()
        return True

    # Comprehensive Batch Movement Methods for Complete Traceability
    def issue_for_job_work(self, quantity, process_name=None):
        """Issue material from this batch for job work processing"""
        if quantity <= 0:
            return False, "Quantity must be greater than 0"
        
        # Check availability (can issue from Raw or Finished state)
        available = self.available_quantity
        if quantity > available:
            return False, f"Insufficient quantity. Available: {available}, Requested: {quantity}"
        
        # Deduct from raw material first, then finished goods
        if self.qty_raw >= quantity:
            self.qty_raw -= quantity
        else:
            remaining = quantity - self.qty_raw
            self.qty_raw = 0
            self.qty_finished -= remaining
        
        # Move to appropriate WIP state
        if process_name:
            process_lower = process_name.lower().replace(' ', '_')
            if process_lower == 'cutting':
                self.qty_wip_cutting += quantity
            elif process_lower == 'bending':
                self.qty_wip_bending += quantity
            elif process_lower == 'welding':
                self.qty_wip_welding += quantity
            elif process_lower in ['zinc', 'zinc_plating']:
                self.qty_wip_zinc += quantity
            elif process_lower == 'painting':
                self.qty_wip_painting += quantity
            elif process_lower == 'assembly':
                self.qty_wip_assembly += quantity
            elif process_lower == 'machining':
                self.qty_wip_machining += quantity
            elif process_lower == 'polishing':
                self.qty_wip_polishing += quantity
            else:
                self.qty_wip += quantity
        else:
            self.qty_wip += quantity
            
        self.updated_at = datetime.utcnow()
        return True, f"Issued {quantity} units for {process_name or 'general'} processing"
    
    def transfer_between_processes(self, from_process, to_process, quantity):
        """Transfer material between different process WIP states"""
        if quantity <= 0:
            return False, "Quantity must be greater than 0"
            
        # Get current quantities
        from_qty = self.get_wip_quantity_by_process(from_process)
        
        if quantity > from_qty:
            return False, f"Insufficient quantity in {from_process}. Available: {from_qty}"
        
        # Reduce from source process
        self.set_wip_quantity_by_process(from_process, from_qty - quantity)
        
        # Add to destination process
        to_qty = self.get_wip_quantity_by_process(to_process)
        self.set_wip_quantity_by_process(to_process, to_qty + quantity)
        
        self.updated_at = datetime.utcnow()
        return True, f"Transferred {quantity} from {from_process} to {to_process}"
    
    def get_wip_quantity_by_process(self, process_name):
        """Get WIP quantity for a specific process"""
        if not process_name:
            return self.qty_wip or 0
            
        process_lower = process_name.lower().replace(' ', '_')
        process_map = {
            'cutting': self.qty_wip_cutting,
            'bending': self.qty_wip_bending,
            'welding': self.qty_wip_welding,
            'zinc': self.qty_wip_zinc,
            'zinc_plating': self.qty_wip_zinc,
            'painting': self.qty_wip_painting,
            'assembly': self.qty_wip_assembly,
            'machining': self.qty_wip_machining,
            'polishing': self.qty_wip_polishing
        }
        return process_map.get(process_lower, self.qty_wip or 0) or 0
    
    def set_wip_quantity_by_process(self, process_name, quantity):
        """Set WIP quantity for a specific process"""
        if not process_name:
            self.qty_wip = quantity
            return True
            
        process_lower = process_name.lower().replace(' ', '_')
        if process_lower == 'cutting':
            self.qty_wip_cutting = quantity
        elif process_lower == 'bending':
            self.qty_wip_bending = quantity
        elif process_lower == 'welding':
            self.qty_wip_welding = quantity
        elif process_lower in ['zinc', 'zinc_plating']:
            self.qty_wip_zinc = quantity
        elif process_lower == 'painting':
            self.qty_wip_painting = quantity
        elif process_lower == 'assembly':
            self.qty_wip_assembly = quantity
        elif process_lower == 'machining':
            self.qty_wip_machining = quantity
        elif process_lower == 'polishing':
            self.qty_wip_polishing = quantity
        else:
            self.qty_wip = quantity
        return True
    
    def create_output_batch(self, output_item_id, output_quantity, output_batch_prefix="OUT"):
        """Create a new batch for finished goods output"""
        # Generate unique output batch number
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        output_batch_number = f"{output_batch_prefix}-{self.batch_number}-{timestamp}"
        
        # Create new batch for output item
        output_batch = ItemBatch(
            item_id=output_item_id,
            batch_number=output_batch_number,
            qty_finished=output_quantity,
            manufacture_date=datetime.now().date(),
            storage_location=self.storage_location,
            quality_status='pending_inspection',
            created_by=self.created_by,
            quality_notes=f"Produced from input batch: {self.batch_number}"
        )
        
        return output_batch
    
    @property 
    def wip_breakdown(self):
        """Return dictionary of WIP quantities by process"""
        return {
            'cutting': self.qty_wip_cutting or 0,
            'bending': self.qty_wip_bending or 0,
            'welding': self.qty_wip_welding or 0,
            'zinc': self.qty_wip_zinc or 0,
            'painting': self.qty_wip_painting or 0,
            'assembly': self.qty_wip_assembly or 0,
            'machining': self.qty_wip_machining or 0,
            'polishing': self.qty_wip_polishing or 0,
            'general': self.qty_wip or 0
        }
    
    @property
    def batch_age_days(self):
        """Age of batch in days"""
        if not self.manufacture_date:
            return None
        return (datetime.utcnow().date() - self.manufacture_date).days
    
    @property
    def days_until_expiry(self):
        """Days until expiry (negative if expired)"""
        if not self.expiry_date:
            return None
        return (self.expiry_date - datetime.utcnow().date()).days
    
    @property
    def is_expired(self):
        """Check if this batch is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < datetime.utcnow().date()
    
    @property
    def qty_total(self):
        """Total quantity for compatibility (alias for total_quantity)"""
        return self.total_quantity
    
    @property
    def qty_available(self):
        """Available quantity for compatibility (alias for available_quantity)"""
        return self.available_quantity
    
    def get_batch_ledger(self):
        """Get a summary of all movements for this batch"""
        return {
            'batch_number': self.batch_number,
            'item': self.item.name if self.item else 'Unknown',
            'states': {
                'raw': self.qty_raw or 0,
                'wip_total': self.total_wip_quantity,
                'wip_breakdown': self.wip_breakdown,
                'finished': self.qty_finished or 0,
                'scrap': self.qty_scrap or 0
            },
            'totals': {
                'total_quantity': self.total_quantity,
                'available_quantity': self.available_quantity,
            },
            'metadata': {
                'age_days': self.batch_age_days,
                'days_until_expiry': self.days_until_expiry,
                'quality_status': self.quality_status,
                'storage_location': self.storage_location,
                'is_expired': self.is_expired
            }
        }
    
    def __repr__(self):
        return f'<ItemBatch {self.batch_number} - {self.item.name if self.item else "Unknown"}>'

class ItemType(db.Model):
    __tablename__ = 'item_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    @classmethod
    def get_default_types(cls):
        """Get or create default item types"""
        default_types = [
            {'name': 'Material', 'description': 'Raw materials and components'},
            {'name': 'Product', 'description': 'Finished products'},
            {'name': 'Consumable', 'description': 'Consumable items'},
            {'name': 'Tool', 'description': 'Tools and equipment'},
            {'name': 'Spare Part', 'description': 'Spare parts and accessories'},
            {'name': 'Packaging', 'description': 'Packaging materials'}
        ]
        
        existing_types = cls.query.filter_by(is_active=True).all()
        if not existing_types:
            for type_data in default_types:
                item_type = cls(
                    name=type_data['name'],
                    description=type_data['description'],
                    is_active=True
                )
                db.session.add(item_type)
            db.session.commit()
            existing_types = cls.query.filter_by(is_active=True).all()
        
        return existing_types
    
    @classmethod
    def get_choices(cls):
        """Get choices for form SelectField"""
        types = cls.query.filter_by(is_active=True).order_by(cls.name).all()
        return [(str(t.id), t.name) for t in types]
    
    def __repr__(self):
        return f'<ItemType {self.name}>'

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit_of_measure = db.Column(db.String(20), nullable=False)  # kg, pcs, meter, etc.
    uom_conversion_factor = db.Column(db.Float)  # Custom conversion factor for purchase to inventory UOM
    hsn_code = db.Column(db.String(20))  # HSN Code for GST
    gst_rate = db.Column(db.Float, default=0.0)  # GST rate (can be 0%, 5%, 12%, 18%, 28% etc.)
    current_stock = db.Column(db.Float, default=0.0)  # Legacy total stock field
    minimum_stock = db.Column(db.Float, default=0.0)
    
    # Batch Tracking Configuration (as per blueprint)
    batch_required = db.Column(db.Boolean, default=True)  # Whether this item requires batch tracking
    default_batch_prefix = db.Column(db.String(10))  # Default prefix for auto-generated batch numbers
    shelf_life_days = db.Column(db.Integer)  # Shelf life in days for expiry tracking
    batch_numbering_auto = db.Column(db.Boolean, default=True)  # Auto-generate batch numbers
    
    # Multi-state inventory tracking
    qty_raw = db.Column(db.Float, default=0.0)      # Raw material stock
    qty_wip = db.Column(db.Float, default=0.0)      # Work in Progress (sent for job work) - LEGACY
    qty_finished = db.Column(db.Float, default=0.0) # Finished goods (completed job work)
    qty_scrap = db.Column(db.Float, default=0.0)    # Scrap/rejected material
    
    # Process-specific WIP breakdown
    qty_wip_cutting = db.Column(db.Float, default=0.0)     # WIP in cutting process
    qty_wip_bending = db.Column(db.Float, default=0.0)     # WIP in bending process  
    qty_wip_welding = db.Column(db.Float, default=0.0)     # WIP in welding process
    qty_wip_zinc = db.Column(db.Float, default=0.0)        # WIP in zinc plating process
    qty_wip_painting = db.Column(db.Float, default=0.0)    # WIP in painting process
    qty_wip_assembly = db.Column(db.Float, default=0.0)    # WIP in assembly process
    qty_wip_machining = db.Column(db.Float, default=0.0)   # WIP in machining process
    qty_wip_polishing = db.Column(db.Float, default=0.0)   # WIP in polishing process
    
    unit_price = db.Column(db.Float, default=0.0)
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    weight_unit = db.Column(db.String(10), default='kg')  # Weight unit (kg, g, lbs, oz, ton)
    item_type = db.Column(db.String(20), default='material')  # Legacy field for backward compatibility
    item_type_id = db.Column(db.Integer, db.ForeignKey('item_types.id'))  # New foreign key to ItemType
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_order_items = db.relationship('PurchaseOrderItem', backref='item_ref', lazy=True)
    sales_order_items = db.relationship('SalesOrderItem', lazy=True)
    # Removed conflicting backref - BOMItem has its own 'item' relationship
    item_type_obj = db.relationship('ItemType', backref='items', lazy=True)
    
    @property
    def total_stock(self):
        """Calculate total stock across all states"""
        return (self.qty_raw or 0) + (self.total_wip or 0) + (self.qty_finished or 0) + (self.qty_scrap or 0)
    
    @property
    def total_wip(self):
        """Calculate total WIP across all processes"""
        return (
            (self.qty_wip_cutting or 0) + (self.qty_wip_bending or 0) + 
            (self.qty_wip_welding or 0) + (self.qty_wip_zinc or 0) + 
            (self.qty_wip_painting or 0) + (self.qty_wip_assembly or 0) + 
            (self.qty_wip_machining or 0) + (self.qty_wip_polishing or 0)
        )
    
    @property
    def wip_breakdown(self):
        """Return WIP breakdown by process"""
        return {
            'cutting': self.qty_wip_cutting or 0,
            'bending': self.qty_wip_bending or 0,
            'welding': self.qty_wip_welding or 0,
            'zinc': self.qty_wip_zinc or 0,
            'painting': self.qty_wip_painting or 0,
            'assembly': self.qty_wip_assembly or 0,
            'machining': self.qty_wip_machining or 0,
            'polishing': self.qty_wip_polishing or 0,
            'other': 0  # No legacy WIP
        }
    
    @property
    def available_stock(self):
        """Stock available for use (raw + finished, excluding WIP)"""
        return (self.qty_raw or 0) + (self.qty_finished or 0)
    
    @property
    def active_bom(self):
        """Get the active BOM for this item (for nested BOM functionality)"""
        # Avoid circular import by using dynamic import
        from sqlalchemy import text
        # Query the database directly to avoid circular import issues
        result = db.session.execute(
            text("SELECT * FROM boms WHERE product_id = :product_id AND is_active = true LIMIT 1"),
            {"product_id": self.id}
        ).fetchone()
        
        if result:
            # Convert result to BOM object
            bom_dict = dict(result._mapping)
            # Create a simple object with basic properties needed for nested BOM
            class SimpleBOM:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
                
                @property
                def items(self):
                    # Get BOM items for this BOM
                    items_result = db.session.execute(
                        text("SELECT * FROM bom_items WHERE bom_id = :bom_id"),
                        {"bom_id": self.id}
                    ).fetchall()
                    return [dict(item._mapping) for item in items_result]
            
            return SimpleBOM(bom_dict)
        return None
    
    def move_to_wip(self, quantity, process=None):
        """Move raw material to Work in Progress (job work sent)
        Args:
            quantity: Amount to move to WIP
            process: Process name (cutting, bending, welding, zinc, painting, assembly, machining, polishing)
        """
        if self.qty_raw >= quantity:
            self.qty_raw -= quantity
            
            # Move to process-specific WIP if process specified
            if process:
                process_lower = process.lower()
                if process_lower == 'cutting':
                    self.qty_wip_cutting += quantity
                elif process_lower == 'bending':
                    self.qty_wip_bending += quantity
                elif process_lower == 'welding':
                    self.qty_wip_welding += quantity
                elif process_lower == 'zinc':
                    self.qty_wip_zinc += quantity
                elif process_lower == 'painting':
                    self.qty_wip_painting += quantity
                elif process_lower == 'assembly':
                    self.qty_wip_assembly += quantity
                elif process_lower == 'machining':
                    self.qty_wip_machining += quantity
                elif process_lower == 'polishing':
                    self.qty_wip_polishing += quantity
                else:
                    # Unknown process, default to cutting
                    self.qty_wip_cutting += quantity
            else:
                # No process specified, default to cutting
                self.qty_wip_cutting += quantity
            return True
        return False
    
    def receive_from_wip(self, finished_qty, scrap_qty=0, process=None):
        """Receive finished goods and scrap from WIP (job work completed)
        Args:
            finished_qty: Amount of finished goods
            scrap_qty: Amount of scrap generated
            process: Process name to receive from
        """
        total_received = finished_qty + scrap_qty
        
        # Check if we have enough WIP in the specified process
        if process:
            process_lower = process.lower()
            process_wip = 0
            
            if process_lower == 'cutting':
                process_wip = self.qty_wip_cutting or 0
            elif process_lower == 'bending':
                process_wip = self.qty_wip_bending or 0
            elif process_lower == 'welding':
                process_wip = self.qty_wip_welding or 0
            elif process_lower == 'zinc':
                process_wip = self.qty_wip_zinc or 0
            elif process_lower == 'painting':
                process_wip = self.qty_wip_painting or 0
            elif process_lower == 'assembly':
                process_wip = self.qty_wip_assembly or 0
            elif process_lower == 'machining':  
                process_wip = self.qty_wip_machining or 0
            elif process_lower == 'polishing':
                process_wip = self.qty_wip_polishing or 0
            else:
                # Unknown process, check cutting as default
                process_wip = self.qty_wip_cutting or 0
            
            if process_wip >= total_received:
                # Deduct from process-specific WIP
                if process_lower == 'cutting':
                    self.qty_wip_cutting -= total_received
                elif process_lower == 'bending':
                    self.qty_wip_bending -= total_received
                elif process_lower == 'welding':
                    self.qty_wip_welding -= total_received
                elif process_lower == 'zinc':
                    self.qty_wip_zinc -= total_received
                elif process_lower == 'painting':
                    self.qty_wip_painting -= total_received
                elif process_lower == 'assembly':
                    self.qty_wip_assembly -= total_received
                elif process_lower == 'machining':
                    self.qty_wip_machining -= total_received
                elif process_lower == 'polishing':
                    self.qty_wip_polishing -= total_received
                else:
                    # Unknown process, deduct from cutting as default
                    self.qty_wip_cutting -= total_received
                
                # Add to finished and scrap
                self.qty_finished += finished_qty
                self.qty_scrap += scrap_qty
                return True
        else:
            # No process specified - deduct from total WIP proportionally
            if self.total_wip >= total_received:
                remaining = total_received
                
                # Deduct from process WIPs proportionally
                for process_attr in ['qty_wip_cutting', 'qty_wip_bending', 'qty_wip_welding', 
                                   'qty_wip_zinc', 'qty_wip_painting', 'qty_wip_assembly', 
                                   'qty_wip_machining', 'qty_wip_polishing']:
                    if remaining <= 0:
                        break
                    process_qty = getattr(self, process_attr) or 0
                    if process_qty > 0:
                        deduct = min(process_qty, remaining)
                        setattr(self, process_attr, process_qty - deduct)
                        remaining -= deduct
                
                # Add to finished and scrap
                self.qty_finished += finished_qty
                self.qty_scrap += scrap_qty
                return True
        
        return False
    
    def sync_stock(self):
        """Sync current_stock with multi-state total for display compatibility"""
        self.current_stock = self.total_stock
    
    @property
    def stock_breakdown(self):
        """Return stock breakdown as dictionary"""
        return {
            'raw': self.qty_raw or 0,
            'wip': self.total_wip,
            'finished': self.qty_finished or 0,
            'scrap': self.qty_scrap or 0,
            'total': self.total_stock,
            'available': self.available_stock
        }

    @property
    def display_item_type(self):
        """Get display name for item type"""
        if self.item_type_obj:
            return self.item_type_obj.name
        return self.item_type.title() if self.item_type else 'Unknown'

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    order_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    expected_date = db.Column(db.Date)
    payment_terms = db.Column(db.String(50), default='30 Days')  # Payment terms like "30 Days"
    freight_terms = db.Column(db.String(100))  # Freight terms
    delivery_notes = db.Column(db.Text)  # Special delivery instructions
    validity_months = db.Column(db.Integer, default=6)  # PO validity in months
    status = db.Column(db.String(20), default='sent')  # draft, sent, partial, closed, cancelled
    subtotal = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    prepared_by = db.Column(db.String(100))  # Name of person who prepared
    verified_by = db.Column(db.String(100))  # Name of person who verified
    approved_by = db.Column(db.String(100))  # Name of person who approved
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Tally integration
    tally_synced = db.Column(db.Boolean, default=False)
    
    # Accounting integration
    supplier_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    purchase_commitment_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    advance_payment_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    advance_amount_paid = db.Column(db.Float, default=0.0)
    accounting_status = db.Column(db.String(20), default='pending')  # pending, committed, advance_paid, invoiced, closed
    
    # Inspection workflow fields
    inspection_required = db.Column(db.Boolean, default=True)
    inspection_status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, failed
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    inspected_at = db.Column(db.DateTime)
    
    # Relationships
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True, cascade='all, delete-orphan')
    delivery_schedules = db.relationship('DeliverySchedule', backref='purchase_order', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_purchase_orders')
    inspector = db.relationship('User', foreign_keys=[inspected_by], backref='inspected_purchase_orders')
    material_inspections = db.relationship('MaterialInspection', backref='purchase_order', lazy=True, cascade='all, delete-orphan')
    
    # Accounting relationships
    supplier_account = db.relationship('Account', foreign_keys=[supplier_account_id])
    commitment_voucher = db.relationship('Voucher', foreign_keys=[purchase_commitment_voucher_id])
    advance_voucher = db.relationship('Voucher', foreign_keys=[advance_payment_voucher_id])

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    sr_no = db.Column(db.Integer)  # Serial Number (No.)
    rm_code = db.Column(db.String(50))  # RM Code (Raw Material Code)
    item_description = db.Column(db.Text)  # Item + Description
    drawing_spec_no = db.Column(db.String(100))  # Drawing / Spec Sheet No.
    hsn_code = db.Column(db.String(20))  # HSN Code
    gst_rate = db.Column(db.Float, default=18.0)  # GST Rate %
    uom = db.Column(db.String(20))  # UOM (Unit of Measure)
    qty = db.Column(db.Float, nullable=False)  # Qty (Quantity)
    rate = db.Column(db.Float, nullable=False)  # Rate (per unit)
    amount = db.Column(db.Float, nullable=False)  # Amount (qty × rate)
    # Legacy fields for compatibility
    quantity_ordered = db.Column(db.Float, nullable=False)
    quantity_received = db.Column(db.Float, default=0.0)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight = db.Column(db.Float, default=0.0)  # Total weight (qty × unit_weight)
    material_destination = db.Column(db.String(20), default='raw_material')  # Where material goes: raw_material, finished, wip, scrap
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships  
    item = db.relationship('Item')
    
    @property
    def calculated_total_weight(self):
        """Calculate total weight based on quantity and unit weight"""
        if self.item and self.item.unit_weight:
            return self.quantity_ordered * self.item.unit_weight
        return self.total_weight or 0.0
    
    @property
    def pending_quantity(self):
        """Calculate pending quantity (ordered - received)"""
        return self.qty - (self.quantity_received or 0)
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage based on received vs ordered quantity"""
        if self.qty > 0:
            return min(((self.quantity_received or 0) / self.qty) * 100, 100)
        return 0

class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    so_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    order_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    delivery_date = db.Column(db.Date)
    payment_terms = db.Column(db.String(100))
    freight_terms = db.Column(db.String(100))
    validity_months = db.Column(db.Integer)
    prepared_by = db.Column(db.String(100))
    verified_by = db.Column(db.String(100))
    approved_by = db.Column(db.String(100))
    delivery_notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft, confirmed, delivered, cancelled
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Tally integration
    tally_synced = db.Column(db.Boolean, default=False)
    
    # Accounting integration
    customer_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    sales_booking_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    advance_receipt_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    sales_voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    advance_amount_received = db.Column(db.Float, default=0.0)
    accounting_status = db.Column(db.String(20), default='pending')  # pending, booked, advance_received, delivered, invoiced, closed
    subtotal = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    
    # Relationships
    items = db.relationship('SalesOrderItem', backref='sales_order', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', backref='created_sales_orders')
    
    # Accounting relationships
    customer_account = db.relationship('Account', foreign_keys=[customer_account_id])
    booking_voucher = db.relationship('Voucher', foreign_keys=[sales_booking_voucher_id])
    advance_voucher = db.relationship('Voucher', foreign_keys=[advance_receipt_voucher_id])
    sales_voucher = db.relationship('Voucher', foreign_keys=[sales_voucher_id])

class SalesOrderItem(db.Model):
    __tablename__ = 'sales_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_ordered = db.Column(db.Float, nullable=False)
    quantity_delivered = db.Column(db.Float, default=0.0)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight = db.Column(db.Float, default=0.0)  # Total weight (qty × unit_weight)
    
    # GST and accounting fields
    hsn_code = db.Column(db.String(20))  # HSN Code
    gst_rate = db.Column(db.Float, default=18.0)  # GST Rate %
    gst_amount = db.Column(db.Float, default=0.0)  # GST Amount
    taxable_amount = db.Column(db.Float, default=0.0)  # Amount before GST
    
    # Relationships
    item = db.relationship('Item')

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    salary_type = db.Column(db.String(20), nullable=False)  # daily, monthly, piece_rate
    rate = db.Column(db.Float, nullable=False)  # daily rate, monthly salary, or per piece rate
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    joining_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    salary_records = db.relationship('SalaryRecord', backref='employee', lazy=True, cascade='all, delete-orphan')
    advances = db.relationship('EmployeeAdvance', backref='employee', lazy=True, cascade='all, delete-orphan')
    
    @staticmethod
    def generate_employee_code():
        """Generate unique employee code"""
        last_employee = Employee.query.order_by(Employee.id.desc()).first()
        if last_employee:
            # Extract number from code like "EMP-0001"
            try:
                last_num = int(last_employee.employee_code.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        return f"EMP-{next_num:04d}"

class JobWorkRate(db.Model):
    __tablename__ = 'job_work_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    rate_per_unit = db.Column(db.Float, nullable=False, default=0.0)
    process_type = db.Column(db.String(50), nullable=True)  # Optional process-specific rate
    vendor_name = db.Column(db.String(200), nullable=True)  # Optional vendor/supplier name
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship
    item = db.relationship('Item', backref='job_work_rates')
    
    def __repr__(self):
        return f'<JobWorkRate {self.item.name}: ₹{self.rate_per_unit}>'

class JobWork(db.Model):
    __tablename__ = 'job_works'
    
    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    process = db.Column(db.String(100), nullable=False)  # Process type: Zinc, Cutting, Bending, etc.
    work_type = db.Column(db.String(20), nullable=False, default='outsourced')  # in_house or outsourced
    department = db.Column(db.String(100), nullable=True)  # Department for in-house work
    quantity_sent = db.Column(db.Float, nullable=False)
    quantity_received = db.Column(db.Float, default=0.0)
    expected_finished_material = db.Column(db.Float, default=0.0)  # Expected finished material quantity
    expected_scrap = db.Column(db.Float, default=0.0)  # Expected scrap quantity
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight_sent = db.Column(db.Float, default=0.0)  # Total weight sent
    total_weight_received = db.Column(db.Float, default=0.0)  # Total weight received
    rate_per_unit = db.Column(db.Float, nullable=False)
    sent_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    received_date = db.Column(db.Date)
    expected_return = db.Column(db.Date)
    status = db.Column(db.String(20), default='sent')  # sent, partial_received, completed
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Team work settings
    is_team_work = db.Column(db.Boolean, default=False)  # Whether this job can be divided among team members
    max_team_members = db.Column(db.Integer, default=1)  # Maximum team members allowed
    
    # Inspection workflow fields
    inspection_required = db.Column(db.Boolean, default=True)
    inspection_status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, failed
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    inspected_at = db.Column(db.DateTime)
    
    # BOM Integration fields
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=True)  # Reference to BOM for production
    production_quantity = db.Column(db.Integer, nullable=True)  # Quantity to produce from BOM
    
    # Relationships
    item = db.relationship('Item', backref='job_works')
    bom = db.relationship('BOM', backref='job_works')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_job_works')
    inspector = db.relationship('User', foreign_keys=[inspected_by], backref='inspected_job_works')
    processes = db.relationship('JobWorkProcess', backref='job_work', lazy=True, cascade='all, delete-orphan')
    team_assignments = db.relationship('JobWorkTeamAssignment', backref='job_work', lazy=True, cascade='all, delete-orphan')
    grn_receipts = db.relationship('GRN', backref='job_work', lazy=True)
    
    @property
    def total_cost(self):
        """Calculate total job cost (quantity_sent × rate_per_unit). Returns 0 for in-house work."""
        if self.work_type == 'in_house':
            return 0.0  # In-house work has no direct cost
        return (self.quantity_sent or 0.0) * (self.rate_per_unit or 0.0)
    
    @property
    def total_cost_received(self):
        """Calculate total cost for received quantity (quantity_received × rate_per_unit)"""
        return (self.quantity_received or 0.0) * (self.rate_per_unit or 0.0)
    
    @property
    def cost_per_unit_display(self):
        """Return formatted cost per unit for display"""
        return f"₹{self.rate_per_unit:.2f}" if self.rate_per_unit else "₹0.00"
    
    @property
    def pending_quantity(self):
        """Calculate pending quantity to be received"""
        # For BOM-based job works, calculate expected output quantity
        if self.bom_id and self.production_quantity:
            try:
                # For BOM-based jobs, the expected output is the production quantity
                # This represents the finished products we expect to receive
                expected_output = self.production_quantity
                return max(0, expected_output - (self.quantity_received or 0))
            except:
                pass
        
        # For multi-process jobs, calculate based on expected output vs received output
        if self.work_type in ['multi_process', 'unified']:
            try:
                # Calculate total expected output from all processes
                total_expected = 0
                for process in self.processes:
                    if process.output_quantity:
                        total_expected += process.output_quantity
                
                if total_expected > 0:
                    return max(0, total_expected - (self.quantity_received or 0))
            except:
                # Fallback to standard calculation if process data unavailable
                pass
        
        # For regular jobs, use standard calculation (sent - received)
        return max(0, (self.quantity_sent or 0) - (self.quantity_received or 0))
    
    @property
    def pending_receipt_display(self):
        """Get display text for pending material receipt, considering multi-process output"""
        # For BOM-based job works, show expected output product
        if self.bom_id and self.production_quantity and self.bom:
            try:
                # Show the BOM product name and pending quantity
                pending_qty = self.pending_quantity
                if pending_qty > 0:
                    unit_display = getattr(self.bom.product, 'unit_of_measure', 'pcs')
                    return f"{pending_qty} {unit_display} {self.bom.product.name}"
            except:
                pass
        
        if self.work_type in ['multi_process', 'unified']:
            # For multi-process jobs, show expected output materials
            processes = self.processes.all() if hasattr(self, 'processes') else []
            if processes:
                pending_items = []
                for process in processes:
                    if process.output_item_id and process.output_quantity:
                        pending_items.append(f"{process.output_quantity} {process.output_item.unit_of_measure} {process.output_item.name}")
                
                if pending_items:
                    return " + ".join(pending_items[:2])  # Show first 2 outputs to avoid clutter
                    
        # For regular jobs, show pending input material
        pending_qty = self.pending_quantity
        if pending_qty > 0:
            return f"{pending_qty} {self.item.unit_of_measure}"
        return "No pending receipt"
    
    @property
    def has_pending_quantity(self):
        """Check if there's any pending quantity"""
        return self.pending_quantity > 0
    
    @property
    def total_grn_received(self):
        """Calculate total quantity received through all GRNs"""
        try:
            from .grn import GRN
            total = 0
            for grn in self.grn_receipts:
                total += grn.total_quantity_received
            return total
        except:
            return 0
    
    @property
    def total_grn_passed(self):
        """Calculate total quantity passed inspection through all GRNs"""
        try:
            from .grn import GRN
            total = 0
            for grn in self.grn_receipts:
                total += grn.total_quantity_passed
            return total
        except:
            return 0
    
    @property
    def total_grn_rejected(self):
        """Calculate total quantity rejected through all GRNs"""
        try:
            from .grn import GRN
            total = 0
            for grn in self.grn_receipts:
                total += grn.total_quantity_rejected
            return total
        except:
            return 0
    
    @property
    def grn_acceptance_rate(self):
        """Calculate overall acceptance rate from GRNs"""
        total_received = self.total_grn_received
        if total_received > 0:
            return (self.total_grn_passed / total_received) * 100
        return 0
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage for job work"""
        # For multi-process jobs, calculate based on expected output vs received output
        if self.work_type in ['multi_process', 'unified']:
            try:
                # Calculate total expected output from all processes
                total_expected = 0
                for process in self.processes:
                    if process.output_quantity:
                        total_expected += process.output_quantity * (self.quantity_sent or 0)
                
                # Return completion based on received vs expected output
                if total_expected > 0:
                    return min(((self.quantity_received or 0) / total_expected) * 100, 100)
            except:
                # Fallback to standard calculation if process data unavailable
                pass
        
        # For regular jobs, use standard calculation (received / sent)
        if self.quantity_sent > 0:
            return min((self.quantity_received / self.quantity_sent) * 100, 100)
        return 0
    
    @property
    def total_cost_display(self):
        """Return formatted total cost for display"""
        if self.work_type == 'in_house':
            return "Internal Cost"
        return f"₹{self.total_cost:.2f}"
    
    @property
    def work_type_display(self):
        """Return user-friendly work type display"""
        return "In-House" if self.work_type == 'in_house' else "Outsourced"
    
    @property
    def work_type_badge_class(self):
        """Return Bootstrap badge class for work type"""
        return 'bg-success' if self.work_type == 'in_house' else 'bg-primary'
    
    @property
    def calculated_quantity_received(self):
        """Calculate quantity received from material inspections (source of truth)"""
        # Import here to avoid circular imports
        from sqlalchemy import func
        
        # Calculate sum of received quantities from material inspections
        total_received = db.session.query(func.sum(MaterialInspection.received_quantity)).filter(
            MaterialInspection.job_work_id == self.id
        ).scalar() or 0.0
        
        return float(total_received)
    
    @property
    def has_quantity_mismatch(self):
        """Check if stored quantity_received differs from actual inspection data"""
        return abs((self.quantity_received or 0) - self.calculated_quantity_received) > 0.01
    
    def sync_quantity_received(self):
        """Sync quantity_received field with actual inspection data"""
        calculated_qty = self.calculated_quantity_received
        if abs((self.quantity_received or 0) - calculated_qty) > 0.01:
            old_qty = self.quantity_received
            self.quantity_received = calculated_qty
            
            # Update status based on corrected quantity
            if self.quantity_received >= self.quantity_sent:
                self.status = 'completed'
            elif self.quantity_received > 0:
                self.status = 'partial_received'
            else:
                self.status = 'sent'
                
            # Log the correction in notes
            note = f"\n[SYSTEM] Quantity received corrected from {old_qty} to {calculated_qty} based on inspection records"
            self.notes = (self.notes or "") + note
            
            return True  # Indicates correction was made
        return False  # No correction needed
    
    @property
    def assigned_team_members(self):
        """Get list of assigned team members"""
        return [assignment.member_name for assignment in self.team_assignments]
    
    @property
    def team_member_count(self):
        """Get count of assigned team members"""
        return len(self.team_assignments)
    
    def check_and_update_completion_status(self):
        """Check if all team members are completed and update job work status"""
        if not self.is_team_work:
            return
            
        # Get all team assignments for this job
        assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=self.id).all()
        
        if not assignments:
            return
            
        # Check if all assignments are at 100% completion
        all_completed = all(assignment.completion_percentage >= 100.0 for assignment in assignments)
        
        if all_completed and self.status != 'completed':
            self.status = 'completed'
            self.received_date = datetime.utcnow().date()
            
            # Calculate total received quantity as sum of completed quantities
            total_completed = sum(assignment.completed_quantity for assignment in assignments)
            self.quantity_received = total_completed
    
    @property
    def remaining_team_slots(self):
        """Get remaining team member slots available"""
        return max(0, self.max_team_members - self.team_member_count)
    
    @property
    def is_team_full(self):
        """Check if team is at maximum capacity"""
        return self.team_member_count >= self.max_team_members
    
    @property
    def total_assigned_quantity(self):
        """Get total quantity assigned to all team members"""
        return sum(assignment.assigned_quantity for assignment in self.team_assignments)
    
    @property
    def unassigned_quantity(self):
        """Get quantity not yet assigned to team members"""
        return max(0, self.quantity_sent - self.total_assigned_quantity)
    
    @staticmethod
    def generate_job_number():
        """Generate unique job work number"""
        current_year = datetime.now().year
        # Find last job work number for current year
        last_job = JobWork.query.filter(JobWork.job_number.like(f'JOB-{current_year}-%')).order_by(JobWork.id.desc()).first()
        if last_job:
            # Extract sequence number from job number like "JOB-2024-0001"
            try:
                last_sequence = int(last_job.job_number.split('-')[-1])
                next_sequence = last_sequence + 1
            except (ValueError, IndexError):
                next_sequence = 1
        else:
            next_sequence = 1
        return f"JOB-{current_year}-{next_sequence:04d}"

class JobWorkTeamAssignment(db.Model):
    """Model for assigning job work to multiple team members"""
    __tablename__ = 'job_work_team_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    member_name = db.Column(db.String(100), nullable=False)  # Keep for backward compatibility
    assigned_quantity = db.Column(db.Float, nullable=False)  # Quantity assigned to this member
    completion_percentage = db.Column(db.Float, default=0.0)  # Progress percentage (0-100)
    estimated_hours = db.Column(db.Float, nullable=True)  # Estimated hours for this assignment
    actual_hours_worked = db.Column(db.Float, default=0.0)  # Actual hours worked so far
    member_role = db.Column(db.String(50), nullable=True)  # Role/responsibility of this member
    start_date = db.Column(db.Date, nullable=True)
    target_completion = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed, paused
    notes = db.Column(db.Text)
    
    # Audit fields
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships  
    employee = db.relationship('Employee', backref='team_assignments')
    assigner = db.relationship('User', backref='team_assignments_created')
    
    # Unique constraint to prevent duplicate assignments
    __table_args__ = (db.UniqueConstraint('job_work_id', 'employee_id', name='unique_job_employee'),)
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'assigned': 'bg-info',
            'in_progress': 'bg-warning',
            'completed': 'bg-success',
            'paused': 'bg-secondary'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @property
    def completion_progress_class(self):
        """Return Bootstrap progress bar class based on completion"""
        if self.completion_percentage >= 100:
            return 'bg-success'
        elif self.completion_percentage >= 75:
            return 'bg-info'
        elif self.completion_percentage >= 50:
            return 'bg-warning'
        else:
            return 'bg-danger'
    
    @property
    def completed_quantity(self):
        """Calculate completed quantity based on completion percentage"""
        return (self.completion_percentage * self.assigned_quantity / 100) if self.assigned_quantity > 0 else 0
    
    def update_progress_from_daily_entries(self):
        """Update progress based on cumulative daily work entries"""
        from sqlalchemy import func
        
        # Find the employee's daily entries for this job work
        employee = Employee.query.get(self.employee_id)
        if not employee:
            return
            
        # Get all daily entries for this employee on this job work
        total_completed = db.session.query(func.sum(DailyJobWorkEntry.quantity_completed)).filter(
            DailyJobWorkEntry.job_work_id == self.job_work_id,
            DailyJobWorkEntry.worker_name == employee.name
        ).scalar() or 0
        
        # Calculate completion percentage
        if self.assigned_quantity > 0:
            completion_percentage = min(100.0, (total_completed / self.assigned_quantity) * 100)
            self.completion_percentage = round(completion_percentage, 2)
            
            # Update status based on completion
            if completion_percentage >= 100:
                self.status = 'completed'
            elif completion_percentage > 0:
                self.status = 'in_progress'
            else:
                self.status = 'assigned'
        
        # Update actual hours worked
        total_hours = db.session.query(func.sum(DailyJobWorkEntry.hours_worked)).filter(
            DailyJobWorkEntry.job_work_id == self.job_work_id,
            DailyJobWorkEntry.worker_name == employee.name
        ).scalar() or 0
        
        self.actual_hours_worked = total_hours

class JobWorkProcess(db.Model):
    """Model for tracking individual processes within a job work"""
    __tablename__ = 'job_work_processes'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    process_name = db.Column(db.String(100), nullable=False)  # Zinc, Cutting, Bending, Welding, etc.
    sequence_number = db.Column(db.Integer, nullable=False, default=1)  # Order of process execution
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, on_hold
    
    # Process tracking fields
    quantity_input = db.Column(db.Float, nullable=False, default=0.0)
    quantity_output = db.Column(db.Float, default=0.0)
    quantity_scrap = db.Column(db.Float, default=0.0)
    expected_scrap = db.Column(db.Float, default=0.0)  # Expected scrap quantity for planning
    
    # Live status tracking with timestamps
    status_history = db.Column(db.Text)  # JSON field to track status changes
    started_at = db.Column(db.DateTime)  # When process actually started
    completed_at = db.Column(db.DateTime)  # When process completed
    on_hold_since = db.Column(db.DateTime)  # When process was put on hold
    on_hold_reason = db.Column(db.String(200))  # Reason for hold
    
    # Batch tracking for this process
    batch_number = db.Column(db.String(50))  # Batch/lot number for traceability
    input_batch_ids = db.Column(db.Text)  # JSON array of input batch IDs
    
    # Output product specification
    output_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # What product is being created
    output_quantity = db.Column(db.Float, default=0.0)  # How many units of output product expected
    
    # Work assignment fields
    work_type = db.Column(db.String(20), default='outsourced')  # outsourced, in_house
    customer_name = db.Column(db.String(100))  # For outsourced work
    department = db.Column(db.String(100))  # For in-house work
    rate_per_unit = db.Column(db.Float, default=0.0)
    
    # Date tracking
    start_date = db.Column(db.Date)
    expected_completion = db.Column(db.Date)
    actual_completion = db.Column(db.Date)
    
    # Team assignment fields (for in-house processes)
    is_team_work = db.Column(db.Boolean, default=False)  # Whether this process allows team assignment
    max_team_members = db.Column(db.Integer, default=1)  # Maximum team members allowed
    team_lead_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Team lead for this process
    
    # Notes and timestamps
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    output_item = db.relationship('Item', foreign_keys=[output_item_id], backref='processes_output')
    team_lead = db.relationship('Employee', foreign_keys=[team_lead_id], backref='processes_led')
    
    @property
    def process_cost(self):
        """Calculate total cost for this process"""
        return self.quantity_input * self.rate_per_unit
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage based on output + scrap vs input"""
        if self.quantity_input == 0:
            return 0
        processed = (self.quantity_output or 0) + (self.quantity_scrap or 0)
        return min(100, (processed / self.quantity_input) * 100)
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'pending': 'bg-secondary',
            'in_progress': 'bg-primary',
            'completed': 'bg-success',
            'on_hold': 'bg-warning'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @property
    def process_badge_class(self):
        """Return Bootstrap badge class for process type"""
        process_classes = {
            'Zinc': 'bg-info',
            'Cutting': 'bg-warning',
            'Bending': 'bg-primary',
            'Welding': 'bg-danger',
            'Painting': 'bg-success',
            'Assembly': 'bg-dark',
            'Machining': 'bg-secondary',
            'Polishing': 'bg-light text-dark'
        }
        return process_classes.get(self.process_name, 'bg-secondary')
    
    def update_status(self, new_status, user_id, reason=None):
        """Update process status with tracking"""
        import json
        
        old_status = self.status
        self.status = new_status
        
        # Update timestamps based on status
        now = datetime.utcnow()
        if new_status == 'in_progress' and not self.started_at:
            self.started_at = now
        elif new_status == 'completed':
            self.completed_at = now
        elif new_status == 'on_hold':
            self.on_hold_since = now
            self.on_hold_reason = reason
        elif new_status == 'in_progress' and old_status == 'on_hold':
            # Resume from hold
            self.on_hold_since = None
            self.on_hold_reason = None
        
        # Track status history
        try:
            history = json.loads(self.status_history or '[]')
        except (json.JSONDecodeError, TypeError):
            history = []
        
        history.append({
            'timestamp': now.isoformat(),
            'old_status': old_status,
            'new_status': new_status,
            'user_id': user_id,
            'reason': reason
        })
        
        self.status_history = json.dumps(history)
        self.updated_at = now
        
        return True
    
    @property
    def time_in_current_status(self):
        """Calculate time spent in current status"""
        if self.status == 'in_progress' and self.started_at:
            return datetime.utcnow() - self.started_at
        elif self.status == 'completed' and self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        elif self.status == 'on_hold' and self.on_hold_since:
            return datetime.utcnow() - self.on_hold_since
        return None
    
    @property
    def is_delayed(self):
        """Check if process is delayed based on expected completion"""
        if self.expected_completion and self.status not in ['completed']:
            return datetime.now().date() > self.expected_completion
        return False
    
    # Quantity tracking for this specific process
    quantity_input = db.Column(db.Float, nullable=False)  # Quantity received for this process
    input_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for input
    quantity_output = db.Column(db.Float, default=0.0)  # Quantity completed from this process
    output_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for output
    quantity_scrap = db.Column(db.Float, default=0.0)  # Scrap generated in this process
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap (typically weight-based)
    
    # Process-specific details
    customer_name = db.Column(db.String(100))  # Customer for this process (may differ per process)
    rate_per_unit = db.Column(db.Float, default=0.0)  # Rate for this specific process
    work_type = db.Column(db.String(20), default='outsourced')  # in_house or outsourced
    department = db.Column(db.String(100))  # Department for in-house processes
    
    # Timing
    start_date = db.Column(db.Date)  # When this process started
    expected_completion = db.Column(db.Date)  # Expected completion date
    actual_completion = db.Column(db.Date)  # Actual completion date
    
    # Process tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text)
    
    @property
    def process_cost(self):
        """Calculate cost for this specific process"""
        return (self.quantity_input or 0.0) * (self.rate_per_unit or 0.0)
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage for this process"""
        if not self.quantity_input or self.quantity_input == 0:
            return 0.0
        output_plus_scrap = (self.quantity_output or 0.0) + (self.quantity_scrap or 0.0)
        return min(100.0, (output_plus_scrap / self.quantity_input) * 100)
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'pending': 'bg-secondary',
            'in_progress': 'bg-primary',
            'completed': 'bg-success',
            'on_hold': 'bg-warning'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @property
    def process_badge_class(self):
        """Return Bootstrap badge class for process type"""
        process_classes = {
            'Zinc': 'bg-info',
            'Cutting': 'bg-danger',
            'Bending': 'bg-warning',
            'Welding': 'bg-dark',
            'Painting': 'bg-success',
            'Assembly': 'bg-primary',
            'Machining': 'bg-secondary',
            'Polishing': 'bg-light text-dark'
        }
        return process_classes.get(self.process_name, 'bg-secondary')

class JobWorkBatch(db.Model):
    """Model for tracking batch-wise job work processing"""
    __tablename__ = 'job_work_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    process_id = db.Column(db.Integer, db.ForeignKey('job_work_processes.id'), nullable=True)
    
    # Input batch tracking
    input_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=False)
    input_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_issued = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, default=datetime.utcnow().date())
    
    # Output batch tracking (filled when material is returned)
    output_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=True)
    output_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)
    quantity_finished = db.Column(db.Float, default=0.0)
    quantity_scrap = db.Column(db.Float, default=0.0)
    quantity_returned_unused = db.Column(db.Float, default=0.0)
    return_date = db.Column(db.Date)
    
    # Process details
    process_name = db.Column(db.String(100), nullable=False)
    vendor_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    rate_per_unit = db.Column(db.Float, default=0.0)
    
    # Status tracking
    status = db.Column(db.String(20), default='issued')  # issued, in_progress, returned, completed
    quality_status = db.Column(db.String(20), default='pending')  # pending, passed, failed, partial
    
    # Quality control data
    qc_notes = db.Column(db.Text)
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    inspected_at = db.Column(db.DateTime)
    
    # Traceability
    batch_notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_work = db.relationship('JobWork', backref='jobwork_batch_records')
    process = db.relationship('JobWorkProcess', backref='process_batch_records')
    input_batch = db.relationship('ItemBatch', foreign_keys=[input_batch_id], backref='jobwork_issues')
    output_batch = db.relationship('ItemBatch', foreign_keys=[output_batch_id], backref='jobwork_returns')
    input_item = db.relationship('Item', foreign_keys=[input_item_id])
    output_item = db.relationship('Item', foreign_keys=[output_item_id])
    creator = db.relationship('User', foreign_keys=[created_by], backref='jobwork_batches_created')
    inspector = db.relationship('User', foreign_keys=[inspected_by], backref='jobwork_batches_inspected')
    
    @property
    def yield_percentage(self):
        """Calculate yield percentage (finished / issued * 100)"""
        if self.quantity_issued == 0:
            return 0.0
        return (self.quantity_finished / self.quantity_issued) * 100
    
    @property
    def scrap_percentage(self):
        """Calculate scrap percentage (scrap / issued * 100)"""
        if self.quantity_issued == 0:
            return 0.0
        return (self.quantity_scrap / self.quantity_issued) * 100
    
    @property
    def utilization_percentage(self):
        """Calculate material utilization (total processed / issued * 100)"""
        if self.quantity_issued == 0:
            return 0.0
        total_processed = self.quantity_finished + self.quantity_scrap
        return (total_processed / self.quantity_issued) * 100
    
    @property
    def is_completed(self):
        """Check if this batch job work is completed"""
        return self.status == 'completed' and self.return_date is not None
    
    @property
    def days_in_process(self):
        """Calculate days between issue and return (or current date if not returned)"""
        end_date = self.return_date or datetime.utcnow().date()
        return (end_date - self.issue_date).days
    
    @property
    def total_cost(self):
        """Calculate total cost for this batch"""
        return self.quantity_issued * self.rate_per_unit
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'issued': 'bg-info',
            'in_progress': 'bg-warning',
            'returned': 'bg-primary',
            'completed': 'bg-success'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    def complete_return(self, finished_qty, scrap_qty, unused_qty, output_batch_code=None, qc_notes=None):
        """Complete the return process for this batch"""
        try:
            # Update quantities
            self.quantity_finished = finished_qty
            self.quantity_scrap = scrap_qty
            self.quantity_returned_unused = unused_qty
            self.return_date = datetime.utcnow().date()
            self.status = 'returned'
            
            if qc_notes:
                self.qc_notes = qc_notes
            
            # Update input batch inventory
            input_batch = self.input_batch
            if input_batch:
                success = input_batch.receive_from_jobwork(
                    finished_qty, scrap_qty, unused_qty, self.process_name
                )
                if not success:
                    return False, "Failed to update input batch inventory"
            
            # Create output batch if finished quantity > 0 and output item specified
            if finished_qty > 0 and self.output_item_id:
                output_batch = ItemBatch(
                    item_id=self.output_item_id,
                    batch_number=f"{self.input_batch.batch_number}-{self.process_name}",
                    qty_finished=finished_qty,
                    qty_scrap=scrap_qty,
                    manufacture_date=self.return_date,
                    quality_status='good' if scrap_qty == 0 else 'mixed',
                    created_by=self.created_by
                )
                db.session.add(output_batch)
                db.session.flush()
                self.output_batch_id = output_batch.id
            
            self.updated_at = datetime.utcnow()
            return True, "Batch return completed successfully"
            
        except Exception as e:
            return False, f"Error completing batch return: {str(e)}"
    
    def __repr__(self):
        return f'<JobWorkBatch {self.job_work.job_number if self.job_work else "Unknown"}: {self.process_name}>'

class ProductionBatch(db.Model):
    """Track material batches consumed in production"""
    __tablename__ = 'production_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    material_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=False)
    quantity_consumed = db.Column(db.Float, nullable=False)
    quantity_remaining = db.Column(db.Float, default=0.0)
    consumption_date = db.Column(db.Date, default=datetime.utcnow().date())
    bom_item_id = db.Column(db.Integer, db.ForeignKey('bom_items.id'), nullable=True)  # Link to BOM material
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    material_batch = db.relationship('ItemBatch', foreign_keys=[material_batch_id], backref='production_consumptions')
    bom_item = db.relationship('BOMItem', foreign_keys=[bom_item_id], backref='production_batch_usages')
    
    @property
    def material_name(self):
        """Get material name from batch"""
        return self.material_batch.item.name if self.material_batch and self.material_batch.item else "Unknown"
    
    @property
    def batch_number(self):
        """Get batch number"""
        return self.material_batch.batch_number if self.material_batch else "Unknown"
    
    def __repr__(self):
        return f'<ProductionBatch {self.production.production_number if self.production else "Unknown"}: {self.batch_number}>'

class Production(db.Model):
    __tablename__ = 'productions'
    
    id = db.Column(db.Integer, primary_key=True)
    production_number = db.Column(db.String(50), unique=True, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_planned = db.Column(db.Float, nullable=False)
    planned_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for planned quantity
    quantity_produced = db.Column(db.Float, default=0.0)
    produced_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for produced quantity
    quantity_good = db.Column(db.Float, default=0.0)  # Good quality items
    good_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for good items
    quantity_damaged = db.Column(db.Float, default=0.0)  # Damaged/defective items
    damaged_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for damaged items
    scrap_quantity = db.Column(db.Float, default=0.0)  # Scrap generated during production
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap (typically weight-based)
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight_planned = db.Column(db.Float, default=0.0)  # Total planned weight
    total_weight_produced = db.Column(db.Float, default=0.0)  # Total produced weight
    production_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    status = db.Column(db.String(20), default='planned')  # planned, in_progress, completed
    notes = db.Column(db.Text)
    
    # Batch Tracking Fields
    batch_tracking_enabled = db.Column(db.Boolean, default=False)  # Enable batch tracking for this production
    output_batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=True)  # Output batch created
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=True)  # BOM used for production
    production_shift = db.Column(db.String(20), default='day')  # day, night, general
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Production operator
    quality_control_passed = db.Column(db.Boolean, default=False)  # QC status for batch
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    produced_item = db.relationship('Item', backref='productions')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_productions')
    operator = db.relationship('User', foreign_keys=[operator_id], backref='operated_productions')
    output_batch = db.relationship('ItemBatch', foreign_keys=[output_batch_id], backref='production_source')
    bom = db.relationship('BOM', foreign_keys=[bom_id], backref='productions_using_bom')
    quality_issues = db.relationship('QualityIssue', backref='production', lazy=True, cascade='all, delete-orphan')
    # production_batches relationship added at end of file
    
    @property
    def completion_percentage(self):
        """Calculate production completion percentage"""
        if self.quantity_planned > 0:
            return min((self.quantity_produced / self.quantity_planned) * 100, 100)
        return 0
    
    @property
    def efficiency_percentage(self):
        """Calculate production efficiency (good items / planned items)"""
        if self.quantity_planned > 0:
            return min((self.quantity_good / self.quantity_planned) * 100, 100)
        return 0
    
    @property
    def defect_rate(self):
        """Calculate defect rate percentage"""
        if self.quantity_produced > 0:
            return (self.quantity_damaged / self.quantity_produced) * 100
        return 0
    
    @property
    def scrap_rate(self):
        """Calculate scrap rate percentage"""
        if self.quantity_produced > 0:
            return (self.scrap_quantity / self.quantity_produced) * 100
        return 0
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'planned': 'bg-primary',
            'in_progress': 'bg-warning',
            'completed': 'bg-success',
            'cancelled': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    def create_output_batch(self):
        """Create output batch when production is completed"""
        if self.quantity_good > 0 and not self.output_batch_id:
            # Generate batch number
            batch_number = f"PROD-{self.production_number}-{self.production_date.strftime('%Y%m%d')}"
            
            # Create new batch for finished goods
            output_batch = ItemBatch(
                item_id=self.item_id,
                batch_number=batch_number,
                qty_finished=self.quantity_good,
                qty_scrap=self.quantity_damaged,
                total_quantity=self.quantity_good,
                manufacture_date=self.production_date,
                quality_status='good' if self.quality_control_passed else 'pending_inspection',
                storage_location='Finished Goods',
                created_by=self.created_by
            )
            
            db.session.add(output_batch)
            db.session.flush()
            
            self.output_batch_id = output_batch.id
            return output_batch
        return None

# Production-ProductionBatch relationship will be added at the very end of the file

class BOM(db.Model):
    __tablename__ = 'boms'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_code = db.Column(db.String(50), unique=True, nullable=False)  # Unique BOM identifier
    product_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    output_uom_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=True)  # Output unit of measure
    version = db.Column(db.String(20), default='1.0')
    status = db.Column(db.String(20), default='active')  # active, inactive, draft
    is_active = db.Column(db.Boolean, default=True)  # Keep for backward compatibility
    output_quantity = db.Column(db.Float, default=1.0)  # How many units this BOM produces (e.g., 1 sheet = 400 pieces)
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit for cost conversions (kg, g, etc.)
    unit_weight_uom = db.Column(db.String(10), default='kg')  # Unit of measure for unit weight
    estimated_scrap_percent = db.Column(db.Float, default=0.0)  # Overall expected scrap percentage
    scrap_quantity = db.Column(db.Float, default=0.0)  # Expected scrap quantity per unit produced
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap (typically weight-based)
    scrap_value_recovery_percent = db.Column(db.Float, default=15.0)  # Percentage of original material value recoverable from scrap
    description = db.Column(db.Text)  # BOM description
    remarks = db.Column(db.Text)  # Additional remarks
    
    # Labor and Overhead costs
    labor_cost_per_unit = db.Column(db.Float, default=0.0)
    overhead_cost_per_unit = db.Column(db.Float, default=0.0)
    labor_hours_per_unit = db.Column(db.Float, default=0.0)
    labor_rate_per_hour = db.Column(db.Float, default=0.0)
    overhead_percentage = db.Column(db.Float, default=0.0)  # Percentage of material cost
    freight_cost_per_unit = db.Column(db.Float, default=0.0)  # Transportation/freight cost per unit (optional)
    freight_unit_type = db.Column(db.String(20), default='per_piece')  # per_piece, per_kg, per_box, per_carton
    markup_percentage = db.Column(db.Float, default=0.0)  # Markup percentage for profit margin
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Multi-level BOM support fields
    parent_bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=True)  # Parent BOM if this is a sub-BOM
    bom_level = db.Column(db.Integer, default=0)  # BOM hierarchy level (0 = top level, 1 = sub-BOM, etc.)
    is_phantom_bom = db.Column(db.Boolean, default=False)  # Phantom BOM (intermediate product not stocked)
    intermediate_product = db.Column(db.Boolean, default=False)  # This BOM produces intermediate products for other BOMs
    
    # Relationships
    product = db.relationship('Item', backref='boms')
    output_uom = db.relationship('UnitOfMeasure', foreign_keys=[output_uom_id])
    items = db.relationship('BOMItem', backref='bom', lazy=True, cascade='all, delete-orphan')
    processes = db.relationship('BOMProcess', backref='bom', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    # Multi-level BOM relationships
    parent_bom = db.relationship('BOM', remote_side=[id], backref='sub_boms')
    
    # Relationship to track which BOMs use this BOM's output as input
    dependent_boms = db.relationship('BOMItem', 
                                   primaryjoin='BOM.product_id == BOMItem.material_id',
                                   foreign_keys='BOMItem.material_id',
                                   backref='source_bom',
                                   viewonly=True)
    
    @property
    def total_material_cost(self):
        """Calculate total material cost for one unit including nested BOM costs"""
        total_cost = 0.0
        
        for item in self.items:
            material = item.material or item.item
            if material:
                # Check if this material has its own BOM (nested BOM)
                material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                
                if material_bom:
                    # Use the BOM cost for this material (recursive cost calculation)
                    # Always apply output_quantity conversion for accurate per-unit costing
                    base_cost = material_bom.total_cost_per_unit
                    if material_bom.output_quantity and material_bom.output_quantity > 0:
                        material_cost = base_cost / material_bom.output_quantity
                    else:
                        material_cost = base_cost
                else:
                    # Use the unit cost from inventory
                    material_cost = item.unit_cost or 0
                
                # Calculate total cost for this item including scrap adjustment
                required_qty = item.qty_required or item.quantity_required or 0
                
                # Apply scrap adjustment if scrap percentage is defined
                if self.estimated_scrap_percent and self.estimated_scrap_percent > 0:
                    # Increase material requirement to account for scrap
                    scrap_multiplier = 1 + (self.estimated_scrap_percent / 100)
                    adjusted_qty = required_qty * scrap_multiplier
                else:
                    adjusted_qty = required_qty
                
                total_cost += adjusted_qty * material_cost
        
        return total_cost
    
    def auto_calculate_output_quantity(self):
        """Automatically calculate output quantity based on material conversion ratios"""
        # This method can be extended to automatically detect conversion ratios
        # For now, it provides a framework for future automatic calculations
        
        # Example logic: If BOM has sheet materials, detect cutting patterns
        for item in self.items:
            material = item.material or item.item
            if material and 'sheet' in material.name.lower():
                # Could implement automatic sheet nesting calculations here
                # For now, maintain current output_quantity if set
                if not self.output_quantity or self.output_quantity <= 1:
                    # Default assumption: sheet materials often have higher yields
                    self.output_quantity = 100.0  # Conservative default
        
        # If no specific logic applies, ensure minimum output quantity of 1
        if not self.output_quantity:
            self.output_quantity = 1.0
            
        return self.output_quantity
    
    @classmethod
    def update_all_bom_calculations(cls):
        """Update all BOMs to use consistent output quantity calculations"""
        all_boms = cls.query.filter_by(is_active=True).all()
        updated_count = 0
        
        for bom in all_boms:
            # Ensure proper output quantity is set
            if not bom.output_quantity or bom.output_quantity <= 0:
                bom.output_quantity = 1.0
                updated_count += 1
        
        if updated_count > 0:
            db.session.commit()
            
        return updated_count
    
    @property
    def expected_scrap_value(self):
        """Calculate expected scrap value recovery per unit"""
        if not self.scrap_quantity or not self.scrap_value_recovery_percent:
            return 0.0
        
        # Calculate scrap value based on material costs and recovery percentage
        material_cost_per_unit = self.total_material_cost
        if self.output_quantity and self.output_quantity > 0:
            material_cost_per_unit = material_cost_per_unit / self.output_quantity
        
        scrap_value = (self.scrap_quantity * material_cost_per_unit * 
                      (self.scrap_value_recovery_percent / 100))
        return scrap_value
    
    @property 
    def total_scrap_weight_per_unit(self):
        """Calculate total expected scrap weight per unit produced"""
        if self.scrap_uom == 'kg':
            return self.scrap_quantity
        elif self.scrap_uom == 'g':
            return self.scrap_quantity / 1000  # Convert grams to kg
        elif self.scrap_uom == 'ton':
            return self.scrap_quantity * 1000  # Convert tons to kg
        return self.scrap_quantity  # Default to kg
    
    def calculate_scrap_for_production(self, production_quantity):
        """Calculate expected scrap weight and value for given production quantity"""
        scrap_weight = self.total_scrap_weight_per_unit * production_quantity
        scrap_value = self.expected_scrap_value * production_quantity
        
        return {
            'scrap_weight_kg': scrap_weight,
            'scrap_value': scrap_value,
            'scrap_percentage': self.estimated_scrap_percent,
            'recovery_percentage': self.scrap_value_recovery_percent
        }
    
    @property
    def calculated_scrap_percent(self):
        """Calculate total scrap percentage from all processes"""
        total_scrap = 0.0
        for process in self.processes:
            if hasattr(process, 'scrap_percentage') and process.scrap_percentage:
                total_scrap += process.scrap_percentage
        
        # Add BOM-level scrap if specified
        if self.estimated_scrap_percent:
            total_scrap += self.estimated_scrap_percent
            
        return total_scrap
    
    @property
    def calculated_freight_cost_per_unit(self):
        """Calculate actual freight cost per unit based on freight unit type"""
        if not self.freight_cost_per_unit or self.freight_cost_per_unit == 0:
            return 0.0
            
        # If freight is per piece/unit, return as-is
        if not self.freight_unit_type or self.freight_unit_type == 'per_piece':
            return self.freight_cost_per_unit
        
        # Calculate total weight per unit for weight-based freight
        total_weight = 0.0
        for item in self.items:
            if item.item.unit_weight and item.item.unit_weight > 0:
                total_weight += item.item.unit_weight * item.quantity_required
        
        if total_weight == 0:
            return 0.0
            
        # Calculate freight cost based on unit type
        if self.freight_unit_type == 'per_kg':
            return self.freight_cost_per_unit * total_weight
        elif self.freight_unit_type == 'per_ton':
            return self.freight_cost_per_unit * (total_weight / 1000)  # Convert kg to tons
        elif self.freight_unit_type in ['per_box', 'per_carton']:
            # For box/carton, assume 1 unit = 1 box/carton (user can adjust freight cost accordingly)
            return self.freight_cost_per_unit
        
        return self.freight_cost_per_unit
    
    @property
    def total_weight_per_unit(self):
        """Calculate total weight per unit for this BOM"""
        total_weight = 0.0
        for item in self.items:
            if item.item.unit_weight and item.item.unit_weight > 0:
                total_weight += item.item.unit_weight * item.quantity_required
        return total_weight
    
    @property
    def total_process_cost_per_unit(self):
        """Calculate total process cost from all manufacturing processes using converted costs"""
        if not self.processes:
            return self.labor_cost_per_unit or 0.0
        
        # Sum up all process costs using converted costs for automatic kg to unit conversion
        process_cost = sum(process.converted_cost_per_unit for process in self.processes)
        return process_cost
    
    @property
    def calculated_labor_cost_per_unit(self):
        """Get labor cost - from processes if available (with conversions), otherwise from manual entry"""
        process_labor = self.total_process_cost_per_unit
        return process_labor if process_labor > 0 else (self.labor_cost_per_unit or 0.0)
    
    @property
    def calculated_scrap_percent(self):
        """Calculate total scrap percentage from all manufacturing processes"""
        if not self.processes:
            return self.estimated_scrap_percent or 0.0
        
        # Sum up scrap percentages from all processes
        total_process_scrap = sum(process.estimated_scrap_percent or 0 for process in self.processes)
        return total_process_scrap if total_process_scrap > 0 else (self.estimated_scrap_percent or 0.0)
    
    @property
    def calculated_total_manufacturing_time(self):
        """Calculate total manufacturing time from all processes"""
        if not self.processes:
            return self.labor_hours_per_unit or 0.0
        
        total_time_minutes = sum(process.total_time_minutes for process in self.processes)
        return total_time_minutes / 60.0  # Convert to hours
    
    @property
    def manufacturing_complexity(self):
        """Determine manufacturing complexity based on processes"""
        if not self.processes:
            return "Simple"
        
        process_count = len(self.processes)
        total_time = self.calculated_total_manufacturing_time
        
        if process_count <= 2 and total_time <= 1.0:
            return "Simple"
        elif process_count <= 4 and total_time <= 4.0:
            return "Moderate"
        elif process_count <= 6 and total_time <= 8.0:
            return "Complex"
        else:
            return "Very Complex"
    
    @property
    def total_cost_per_unit(self):
        """Calculate total cost per unit including materials, labor, overhead, freight, and markup"""
        material_cost = self.total_material_cost
        
        # Use calculated labor cost from processes if available
        labor_cost = self.calculated_labor_cost_per_unit
        
        overhead_cost = self.overhead_cost_per_unit or 0
        freight_cost = self.calculated_freight_cost_per_unit
        
        # If overhead is percentage-based, calculate from material cost
        if self.overhead_percentage and self.overhead_percentage > 0:
            overhead_cost = material_cost * (self.overhead_percentage / 100)
        
        subtotal = material_cost + labor_cost + overhead_cost + freight_cost
        
        # Apply markup percentage
        markup_amount = subtotal * (self.markup_percentage or 0) / 100
        
        return subtotal + markup_amount
    
    @property
    def markup_amount_per_unit(self):
        """Calculate markup amount per unit"""
        material_cost = self.total_material_cost
        labor_cost = self.labor_cost_per_unit or 0
        overhead_cost = self.overhead_cost_per_unit or 0
        freight_cost = self.calculated_freight_cost_per_unit
        
        # If overhead is percentage-based, calculate from material cost
        if self.overhead_percentage and self.overhead_percentage > 0:
            overhead_cost = material_cost * (self.overhead_percentage / 100)
        
        subtotal = material_cost + labor_cost + overhead_cost + freight_cost
        
        return subtotal * (self.markup_percentage or 0) / 100
    
    @property
    def total_bom_cost(self):
        """Total BOM cost per output quantity - alias for total_cost_per_unit"""
        return self.total_cost_per_unit
    
    @property
    def expected_scrap_value(self):
        """Calculate expected scrap value recovery"""
        if self.scrap_quantity and self.scrap_value_recovery_percent:
            # Estimate scrap value based on material cost and recovery percentage
            material_cost = self.total_material_cost
            scrap_value_per_kg = material_cost * (self.scrap_value_recovery_percent / 100)
            return self.scrap_quantity * scrap_value_per_kg
        return 0.0
    
    @property
    def total_scrap_weight_per_unit(self):
        """Calculate total expected scrap weight per unit including material and process scrap"""
        total_scrap = self.scrap_quantity or 0.0
        
        # Add process-specific scrap if available
        for process in self.processes:
            if hasattr(process, 'estimated_scrap_percent') and process.estimated_scrap_percent:
                # Estimate process scrap weight (this could be enhanced with specific calculations)
                process_scrap_weight = 0.1 * (process.estimated_scrap_percent / 100)  # Rough estimate
                total_scrap += process_scrap_weight
        
        return total_scrap
    
    def calculate_scrap_for_production(self, production_qty):
        """Calculate expected scrap for a specific production quantity"""
        return {
            'total_scrap_weight': self.total_scrap_weight_per_unit * production_qty,
            'scrap_uom': self.scrap_uom,
            'estimated_scrap_value': self.expected_scrap_value * production_qty,
            'scrap_percentage': self.estimated_scrap_percent
        }
    
    def get_material_availability(self):
        """Check material availability for this BOM including nested BOM dependencies"""
        shortages = []
        nested_requirements = []
        
        for bom_item in self.items:
            material = bom_item.material or bom_item.item  # Handle both old and new structure
            if material:
                # Check if this material has its own BOM (nested BOM)
                material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                
                if material_bom:
                    # This is a nested BOM - check its sub-material availability
                    sub_shortages = material_bom.get_material_availability()
                    if sub_shortages:
                        nested_requirements.append({
                            'intermediate_product': material,
                            'bom': material_bom,
                            'shortages': sub_shortages,
                            'required_qty': bom_item.effective_quantity
                        })
                else:
                    # Regular material - check direct availability
                    available_qty = material.total_stock if hasattr(material, 'total_stock') else (material.current_stock or 0)
                    required_qty = bom_item.effective_quantity
                    
                    if available_qty < required_qty:
                        shortages.append({
                            'material': material,
                            'required': required_qty,
                            'available': available_qty,
                            'shortage': required_qty - available_qty,
                            'type': 'direct_material'
                        })
        
        # Add nested requirements to shortages
        for nested_req in nested_requirements:
            shortages.append({
                'material': nested_req['intermediate_product'],
                'required': nested_req['required_qty'],
                'available': 0,  # Assume intermediate products are produced on demand
                'shortage': nested_req['required_qty'],
                'type': 'intermediate_product',
                'nested_bom': nested_req['bom'],
                'sub_material_shortages': nested_req['shortages']
            })
        
        return shortages
    
    def can_produce_quantity(self, production_qty):
        """Check if BOM can produce specified quantity with current inventory"""
        shortages = []
        for bom_item in self.items:
            material = bom_item.material or bom_item.item  # Handle both old and new structure
            if material:
                available_qty = material.total_stock if hasattr(material, 'total_stock') else (material.current_stock or 0)
                required_qty = bom_item.effective_quantity * production_qty
                
                if available_qty < required_qty:
                    shortages.append({
                        'material': material,
                        'required': required_qty,
                        'available': available_qty,
                        'shortage': required_qty - available_qty
                    })
        return len(shortages) == 0, shortages
    
    @property
    def total_process_steps(self):
        """Get total number of process steps in this BOM"""
        return len(self.processes)
    
    @property
    def total_process_time_per_unit(self):
        """Calculate total process time per unit across all steps"""
        return sum(process.total_time_minutes for process in self.processes)
    
    @property
    def total_process_cost_per_unit(self):
        """Calculate total process cost per unit across all steps"""
        return sum(process.labor_cost_per_unit for process in self.processes)
    
    @property
    def manufacturing_complexity(self):
        """Determine manufacturing complexity based on number of processes"""
        steps = self.total_process_steps
        if steps <= 2:
            return "Simple"
        elif steps <= 5:
            return "Moderate"
        elif steps <= 8:
            return "Complex"
        else:
            return "Very Complex"
    
    @property
    def outsourced_processes(self):
        """Get list of outsourced processes"""
        return [p for p in self.processes if p.is_outsourced]
    
    @property
    def in_house_processes(self):
        """Get list of in-house processes"""
        return [p for p in self.processes if not p.is_outsourced]
    
    # Multi-level BOM methods
    
    def get_bom_hierarchy(self):
        """Get the complete BOM hierarchy tree"""
        hierarchy = {
            'bom': self,
            'level': self.bom_level,
            'children': []
        }
        
        # Find all sub-BOMs that use this BOM's output as input
        for bom_item in self.items:
            material = bom_item.material or bom_item.item
            if material:
                # Find BOMs that produce this material
                sub_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                if sub_bom and sub_bom.id != self.id:  # Avoid circular reference
                    sub_hierarchy = sub_bom.get_bom_hierarchy()
                    sub_hierarchy['parent_requirement'] = {
                        'quantity': bom_item.qty_required or bom_item.quantity_required,
                        'uom': bom_item.unit
                    }
                    hierarchy['children'].append(sub_hierarchy)
        
        return hierarchy
    
    def get_flattened_materials_list(self):
        """Get a flattened list of all materials required including nested BOMs"""
        materials_list = []
        
        def process_bom(bom, multiplier=1):
            for bom_item in bom.items:
                material = bom_item.material or bom_item.item
                if material:
                    required_qty = (bom_item.qty_required or bom_item.quantity_required or 0) * multiplier
                    
                    # Check if this material has its own BOM
                    material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                    
                    if material_bom:
                        # Recursive call for nested BOM
                        process_bom(material_bom, required_qty)
                    else:
                        # Add to final materials list
                        existing_material = next((m for m in materials_list if m['material'].id == material.id), None)
                        if existing_material:
                            existing_material['total_quantity'] += required_qty
                        else:
                            materials_list.append({
                                'material': material,
                                'total_quantity': required_qty,
                                'unit': bom_item.unit,
                                'source_bom': bom.bom_code,
                                'bom_level': bom.bom_level
                            })
        
        process_bom(self)
        return materials_list
    
    def get_suggested_production_sequence(self):
        """Get suggested production sequence for multi-level BOMs"""
        sequence = []
        
        def analyze_dependencies(bom, level=0):
            bom_info = {
                'bom': bom,
                'level': level,
                'dependencies': [],
                'estimated_lead_time': bom.calculated_total_manufacturing_time
            }
            
            for bom_item in bom.items:
                material = bom_item.material or bom_item.item
                if material:
                    material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                    if material_bom and material_bom.id != bom.id:
                        dependency = analyze_dependencies(material_bom, level + 1)
                        bom_info['dependencies'].append(dependency)
            
            return bom_info
        
        dependency_tree = analyze_dependencies(self)
        
        # Create production sequence (deepest dependencies first)
        def extract_sequence(node):
            # First add all dependencies
            for dep in node['dependencies']:
                extract_sequence(dep)
            
            # Then add this BOM if not already in sequence
            if not any(item['bom'].id == node['bom'].id for item in sequence):
                sequence.append({
                    'bom': node['bom'],
                    'level': node['level'],
                    'estimated_lead_time': node['estimated_lead_time'],
                    'priority': len(node['dependencies'])  # Higher priority for more dependencies
                })
        
        extract_sequence(dependency_tree)
        return sequence
    
    def get_missing_intermediate_products(self):
        """Get list of intermediate products that need to be produced"""
        missing_products = []
        
        for bom_item in self.items:
            material = bom_item.material or bom_item.item
            if material:
                # Check if this material has a BOM (intermediate product)
                material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                
                if material_bom:
                    # Check current stock vs required
                    available_qty = material.total_stock if hasattr(material, 'total_stock') else (material.current_stock or 0)
                    required_qty = bom_item.qty_required or bom_item.quantity_required or 0
                    
                    if available_qty < required_qty:
                        missing_products.append({
                            'material': material,
                            'bom': material_bom,
                            'required_qty': required_qty,
                            'available_qty': available_qty,
                            'shortage_qty': required_qty - available_qty,
                            'suggested_job_work': f"Create Job Work for {material_bom.bom_code}",
                            'estimated_cost': material_bom.total_cost_per_unit * (required_qty - available_qty)
                        })
        
        return missing_products
    
    def calculate_multi_level_cost_breakdown(self):
        """Calculate detailed cost breakdown including nested BOM costs"""
        breakdown = {
            'direct_materials': 0.0,
            'intermediate_products': 0.0,
            'labor_costs': 0.0,
            'overhead_costs': 0.0,
            'total_cost': 0.0,
            'cost_details': []
        }
        
        for bom_item in self.items:
            material = bom_item.material or bom_item.item
            if material:
                required_qty = bom_item.qty_required or bom_item.quantity_required or 0
                
                # Check if this material has its own BOM
                material_bom = BOM.query.filter_by(product_id=material.id, is_active=True).first()
                
                if material_bom:
                    # Intermediate product cost
                    sub_cost = material_bom.total_cost_per_unit * required_qty
                    breakdown['intermediate_products'] += sub_cost
                    
                    # Get sub-BOM breakdown
                    sub_breakdown = material_bom.calculate_multi_level_cost_breakdown()
                    
                    breakdown['cost_details'].append({
                        'material': material,
                        'type': 'intermediate_product',
                        'quantity': required_qty,
                        'unit_cost': material_bom.total_cost_per_unit,
                        'total_cost': sub_cost,
                        'sub_breakdown': sub_breakdown
                    })
                else:
                    # Direct material cost
                    direct_cost = bom_item.unit_cost * required_qty
                    breakdown['direct_materials'] += direct_cost
                    
                    breakdown['cost_details'].append({
                        'material': material,
                        'type': 'direct_material',
                        'quantity': required_qty,
                        'unit_cost': bom_item.unit_cost,
                        'total_cost': direct_cost
                    })
        
        # Add labor and overhead costs
        breakdown['labor_costs'] = self.calculated_labor_cost_per_unit
        breakdown['overhead_costs'] = self.overhead_cost_per_unit or 0
        
        if self.overhead_percentage and self.overhead_percentage > 0:
            material_cost = breakdown['direct_materials'] + breakdown['intermediate_products']
            breakdown['overhead_costs'] = material_cost * (self.overhead_percentage / 100)
        
        breakdown['total_cost'] = (breakdown['direct_materials'] + 
                                 breakdown['intermediate_products'] + 
                                 breakdown['labor_costs'] + 
                                 breakdown['overhead_costs'])
        
        return breakdown

# New model for BOM Process routing
class BOMProcess(db.Model):
    """Process routing for BOM operations"""
    __tablename__ = 'bom_processes'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)  # Sequential step number
    process_name = db.Column(db.String(100), nullable=False)  # e.g., "Cutting", "Welding", "Assembly"
    process_code = db.Column(db.String(20))  # Short code like "CUT", "WELD", "ASSY"
    operation_description = db.Column(db.Text)  # Detailed description of the operation
    setup_time_minutes = db.Column(db.Float, default=0.0)  # Setup time in minutes
    run_time_minutes = db.Column(db.Float, default=0.0)  # Runtime per unit in minutes
    labor_rate_per_hour = db.Column(db.Float, default=0.0)  # Labor rate for this process
    machine_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # Machine/tool used
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)  # Department
    is_outsourced = db.Column(db.Boolean, default=False)  # Is this process outsourced?
    vendor_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)  # Outsourcing vendor
    cost_per_unit = db.Column(db.Float, default=0.0)  # Process cost per unit
    cost_unit = db.Column(db.String(20), default='per_unit')  # Cost unit (per_unit, per_kg, per_meter, etc.)
    quality_check_required = db.Column(db.Boolean, default=False)  # Quality check after this step
    parallel_processes = db.Column(db.Text)  # JSON list of processes that can run in parallel
    predecessor_processes = db.Column(db.Text)  # JSON list of required predecessor processes
    
    # Process transformation fields
    input_product_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # Input product for this process
    output_product_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # Output product from this process
    input_quantity = db.Column(db.Float, default=1.0)  # Input quantity per unit
    output_quantity = db.Column(db.Float, default=1.0)  # Output quantity per unit
    transformation_type = db.Column(db.String(50), default='modify')  # modify, convert, assemble, disassemble
    
    notes = db.Column(db.Text)
    
    # Relationships
    machine = db.relationship('Item', foreign_keys=[machine_id])
    department = db.relationship('Department', foreign_keys=[department_id])
    vendor = db.relationship('Supplier', foreign_keys=[vendor_id])
    input_product = db.relationship('Item', foreign_keys=[input_product_id])
    output_product = db.relationship('Item', foreign_keys=[output_product_id])
    
    @property
    def total_time_minutes(self):
        """Calculate total time including setup and runtime"""
        return (self.setup_time_minutes or 0) + (self.run_time_minutes or 0)
    
    @property
    def labor_cost_per_unit(self):
        """Calculate labor cost per unit for this process"""
        if self.labor_rate_per_hour and self.run_time_minutes:
            return (self.labor_rate_per_hour / 60) * self.run_time_minutes
        return self.converted_cost_per_unit or 0
        return self.converted_cost_per_unit or 0
    
    @property
    def converted_cost_per_unit(self):
        """Convert cost per unit based on cost_unit and BOM's unit weight"""
        if not self.cost_per_unit or self.cost_per_unit == 0:
            return 0.0
        
        # If cost is already per unit, return as-is
        if not self.cost_unit or self.cost_unit == 'per_unit':
            return self.cost_per_unit
        
        # Get BOM's unit weight for conversion
        bom = self.bom
        if not bom or not bom.unit_weight or bom.unit_weight == 0:
            return self.cost_per_unit  # Can't convert without unit weight
        
        # Convert based on cost unit type
        if self.cost_unit == 'per_kg':
            # Convert per kg cost to per unit cost using BOM unit weight
            unit_weight_kg = bom.unit_weight
            if bom.unit_weight_uom == 'g':
                unit_weight_kg = bom.unit_weight / 1000
            elif bom.unit_weight_uom == 'lbs':
                unit_weight_kg = bom.unit_weight * 0.453592
            elif bom.unit_weight_uom == 'oz':
                unit_weight_kg = bom.unit_weight * 0.0283495
            
            return self.cost_per_unit * unit_weight_kg
        
        elif self.cost_unit == 'per_g':
            # Convert per gram cost to per unit cost
            unit_weight_g = bom.unit_weight
            if bom.unit_weight_uom == 'kg':
                unit_weight_g = bom.unit_weight * 1000
            elif bom.unit_weight_uom == 'lbs':
                unit_weight_g = bom.unit_weight * 453.592
            elif bom.unit_weight_uom == 'oz':
                unit_weight_g = bom.unit_weight * 28.3495
            
            return self.cost_per_unit * unit_weight_g
        
        # For other cost units (per_meter, per_box, etc.), return as-is
        return self.cost_per_unit
    
    @property
    def cost_display_info(self):
        """Get cost display information for templates"""
        original_cost = self.cost_per_unit or 0
        converted_cost = self.converted_cost_per_unit
        cost_unit = self.cost_unit or 'per_unit'
        
        return {
            'original_cost': original_cost,
            'converted_cost': converted_cost,
            'cost_unit': cost_unit,
            'has_conversion': abs(original_cost - converted_cost) > 0.001 and original_cost > 0,
            'conversion_factor': (converted_cost / original_cost) if original_cost > 0 else 1
        }

class BOMItem(db.Model):
    __tablename__ = 'bom_items'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('boms.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    qty_required = db.Column(db.Float, nullable=False)
    uom_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)  # UOM for this BOM item
    unit = db.Column(db.String(20), nullable=False, default='pcs')  # Keep for backward compatibility
    unit_cost = db.Column(db.Float, default=0.0)
    scrap_percent = db.Column(db.Float, default=0.0)  # Expected scrap percentage for this material
    process_step = db.Column(db.Integer, default=1)  # Which process step this material is used in
    process_name = db.Column(db.String(100))  # Process where this material is used
    is_critical = db.Column(db.Boolean, default=False)  # Critical material flag
    substitute_materials = db.Column(db.Text)  # JSON string of substitute material IDs
    default_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)  # Default supplier
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight = db.Column(db.Float, default=0.0)  # Total weight (qty × unit_weight)
    remarks = db.Column(db.Text)  # Additional remarks
    
    # Legacy fields for backward compatibility
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)  # Keep for backward compatibility
    quantity_required = db.Column(db.Float, nullable=True)  # Keep for backward compatibility
    
    # Relationships
    material = db.relationship('Item', foreign_keys=[material_id], backref='bom_material_components')
    item = db.relationship('Item', foreign_keys=[item_id], backref='legacy_bom_items')  # Keep for backward compatibility
    uom = db.relationship('UnitOfMeasure', foreign_keys=[uom_id])
    default_supplier = db.relationship('Supplier', foreign_keys=[default_supplier_id])
    
    def __init__(self, **kwargs):
        super(BOMItem, self).__init__(**kwargs)
        
        # Handle backward compatibility
        if self.item_id and not self.material_id:
            self.material_id = self.item_id
        if self.quantity_required and not self.qty_required:
            self.qty_required = self.quantity_required
            
        # Auto-populate unit cost from item's unit price if not provided
        if self.unit_cost == 0.0:
            material_id = self.material_id or self.item_id
            if material_id:
                item = Item.query.get(material_id)
                if item and item.unit_price:
                    self.unit_cost = item.unit_price
    
    @property
    def total_cost(self):
        """Calculate total cost for this BOM item"""
        return self.qty_required * self.unit_cost
    
    @property
    def effective_quantity(self):
        """Calculate effective quantity including scrap"""
        base_qty = self.qty_required or self.quantity_required or 0
        if self.scrap_percent > 0:
            return base_qty * (1 + self.scrap_percent / 100)
        return base_qty

class QualityIssue(db.Model):
    __tablename__ = 'quality_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    issue_number = db.Column(db.String(50), unique=True, nullable=False)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)  # damage, malfunction, defect, contamination
    severity = db.Column(db.String(20), nullable=False)  # low, medium, high, critical
    quantity_affected = db.Column(db.Float, nullable=False)
    affected_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for affected quantity
    scrap_quantity = db.Column(db.Float, default=0.0)  # Additional scrap generated due to quality issue
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight_affected = db.Column(db.Float, default=0.0)  # Total weight affected
    description = db.Column(db.Text, nullable=False)
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    preventive_action = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, closed
    detected_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    detected_date = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_date = db.Column(db.DateTime)
    cost_impact = db.Column(db.Float, default=0.0)  # Financial impact
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='quality_issues')
    detector = db.relationship('User', foreign_keys=[detected_by], backref='detected_issues')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_issues')

class QualityControlLog(db.Model):
    __tablename__ = 'quality_control_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('productions.id'), nullable=False)
    inspection_date = db.Column(db.DateTime, default=datetime.utcnow)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    batch_number = db.Column(db.String(50))
    total_inspected = db.Column(db.Float, nullable=False)
    inspected_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for inspected
    passed_quantity = db.Column(db.Float, nullable=False)
    passed_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for passed
    failed_quantity = db.Column(db.Float, nullable=False)
    failed_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for failed
    scrap_quantity = db.Column(db.Float, default=0.0)  # Scrap generated during inspection
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap
    rejection_rate = db.Column(db.Float, nullable=False)  # Percentage
    inspection_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    production_ref = db.relationship('Production', backref='quality_logs')
    inspector = db.relationship('User', backref='quality_inspections')

class NotificationSettings(db.Model):
    __tablename__ = 'notification_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    # Email settings
    email_enabled = db.Column(db.Boolean, default=True)
    sendgrid_api_key = db.Column(db.String(255))
    sender_email = db.Column(db.String(120), default='noreply@akfactory.com')
    sender_name = db.Column(db.String(100), default='AK Innovations Factory')
    
    # SMS/WhatsApp settings
    sms_enabled = db.Column(db.Boolean, default=True)
    whatsapp_enabled = db.Column(db.Boolean, default=True)
    twilio_account_sid = db.Column(db.String(255))
    twilio_auth_token = db.Column(db.String(255))
    twilio_phone_number = db.Column(db.String(20))
    
    # Notification preferences
    low_stock_notifications = db.Column(db.Boolean, default=True)
    order_status_notifications = db.Column(db.Boolean, default=True)
    production_notifications = db.Column(db.Boolean, default=True)
    
    # Recipients
    admin_email = db.Column(db.String(120))
    admin_phone = db.Column(db.String(20))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Notification models moved to models.notifications.py to prevent conflicts

class DeliverySchedule(db.Model):
    __tablename__ = 'delivery_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    delivery_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='delivery_schedules')

class MaterialInspection(db.Model):
    __tablename__ = 'material_inspections'
    
    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(db.String(50), unique=True, nullable=False)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=True)
    process_id = db.Column(db.Integer, db.ForeignKey('job_work_processes.id'), nullable=True)
    inspection_type = db.Column(db.String(50), default='general')  # general, job_work_process
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    received_quantity = db.Column(db.Float, nullable=False)
    received_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for received
    inspected_quantity = db.Column(db.Float, nullable=False)
    inspected_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for inspected
    passed_quantity = db.Column(db.Float, nullable=False)
    passed_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for passed
    damaged_quantity = db.Column(db.Float, nullable=False)
    damaged_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for damaged
    rejected_quantity = db.Column(db.Float, nullable=False)
    rejected_uom = db.Column(db.String(20), default='pcs')  # Unit of measure for rejected
    scrap_quantity = db.Column(db.Float, default=0.0)  # Scrap generated during inspection
    scrap_uom = db.Column(db.String(20), default='kg')  # Unit of measure for scrap
    unit_weight = db.Column(db.Float, default=0.0)  # Weight per unit in kg
    total_weight_inspected = db.Column(db.Float, default=0.0)  # Total weight inspected
    total_weight_passed = db.Column(db.Float, default=0.0)  # Total weight passed
    total_weight_rejected = db.Column(db.Float, default=0.0)  # Total weight rejected
    acceptance_rate = db.Column(db.Float, nullable=False)  # Percentage of accepted quantity
    damage_types = db.Column(db.Text)  # JSON or comma-separated damage types
    rejection_reasons = db.Column(db.Text)  # Reasons for rejection
    inspection_notes = db.Column(db.Text)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    inspection_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='completed')  # pending, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='material_inspections')
    inspector = db.relationship('User', backref='material_inspections')
    job_work = db.relationship('JobWork', backref='material_inspections')

class FactoryExpense(db.Model):
    __tablename__ = 'factory_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, nullable=False)  # EXP-YYYY-0001
    
    # Basic Details
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # utilities, maintenance, salary, materials, overhead, transport, others
    subcategory = db.Column(db.String(100))  # electricity, water, repair, cleaning, etc.
    department_code = db.Column(db.String(50))  # Link to Department.code for organization
    description = db.Column(db.String(500), nullable=False)
    
    # Financial Details
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(15, 2), default=0.0)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, cheque, upi, card
    paid_by = db.Column(db.String(100))  # person/entity who made the payment
    
    # Vendor/Supplier Details (optional)
    vendor_name = db.Column(db.String(200))
    vendor_contact = db.Column(db.String(100))
    invoice_number = db.Column(db.String(100))
    invoice_date = db.Column(db.Date)
    
    # Approval and Processing
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, paid
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approval_date = db.Column(db.DateTime)
    payment_date = db.Column(db.Date)
    
    # Documentation
    receipt_path = db.Column(db.String(500))  # Path to uploaded receipt/invoice
    notes = db.Column(db.Text)
    
    # Recurring Expense Support
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_frequency = db.Column(db.String(20))  # monthly, quarterly, yearly
    parent_expense_id = db.Column(db.Integer, db.ForeignKey('factory_expenses.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Tally integration
    tally_synced = db.Column(db.Boolean, default=False)
    
    # Accounting integration
    voucher_id = db.Column(db.Integer, nullable=True)  # Link to accounting voucher
    
    # Relationships
    requested_by = db.relationship('User', foreign_keys=[requested_by_id], backref='requested_expenses')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_expenses')
    child_expenses = db.relationship('FactoryExpense', backref=db.backref('parent_expense', remote_side=[id]))
    
    @classmethod
    def generate_expense_number(cls):
        """Generate next expense number in format EXP-YYYY-0001"""
        from datetime import datetime
        current_year = datetime.now().year
        
        # Find the latest expense number for current year
        latest_expense = cls.query.filter(
            cls.expense_number.like(f'EXP-{current_year}-%')
        ).order_by(cls.expense_number.desc()).first()
        
        if latest_expense:
            # Extract the sequence number and increment
            last_sequence = int(latest_expense.expense_number.split('-')[-1])
            next_sequence = last_sequence + 1
        else:
            next_sequence = 1
        
        return f'EXP-{current_year}-{next_sequence:04d}'
    
    @property
    def category_display(self):
        """Return user-friendly category name"""
        categories = {
            'utilities': 'Utilities & Infrastructure',
            'maintenance': 'Maintenance & Repairs',
            'salary': 'Salaries & Benefits',
            'materials': 'Raw Materials & Supplies',
            'overhead': 'Factory Overhead',
            'transport': 'Transportation & Logistics',
            'others': 'Other Expenses'
        }
        return categories.get(self.category, self.category.title())
    
    @property
    def department_name(self):
        """Return department name from department code"""
        if not self.department_code:
            return None
        try:
            from .department import Department
            dept = Department.get_by_code(self.department_code)
            return dept.name if dept else self.department_code.replace('_', ' ').title()
        except Exception:
            return self.department_code.replace('_', ' ').title() if self.department_code else None
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status"""
        status_classes = {
            'pending': 'bg-warning',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'paid': 'bg-primary'
        }
        return status_classes.get(self.status, 'bg-secondary')

class SalaryRecord(db.Model):
    __tablename__ = 'salary_records'
    
    id = db.Column(db.Integer, primary_key=True)
    salary_number = db.Column(db.String(50), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    pay_period_start = db.Column(db.Date, nullable=False)
    pay_period_end = db.Column(db.Date, nullable=False)
    # Days-based calculation fields
    expected_working_days = db.Column(db.Integer, default=0)  # Total working days in period
    actual_days_worked = db.Column(db.Integer, default=0)    # Days from attendance records
    daily_rate = db.Column(db.Float, default=0.0)           # Rate per day
    basic_amount = db.Column(db.Float, nullable=False)       # Calculated from days * daily rate
    overtime_hours = db.Column(db.Float, default=0.0)
    overtime_rate = db.Column(db.Float, default=0.0)
    overtime_amount = db.Column(db.Float, default=0.0)
    bonus_amount = db.Column(db.Float, default=0.0)
    deduction_amount = db.Column(db.Float, default=0.0)
    advance_deduction = db.Column(db.Float, default=0.0)  # Auto-deducted from advances
    gross_amount = db.Column(db.Float, nullable=False)
    net_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, paid
    payment_date = db.Column(db.Date)
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, cheque
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Accounting integration
    voucher_id = db.Column(db.Integer, nullable=True)  # Link to accounting voucher
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_salary_records')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_salary_records')
    
    @staticmethod
    def generate_salary_number():
        """Generate unique salary record number"""
        from datetime import datetime
        year = datetime.now().year
        last_record = SalaryRecord.query.filter(
            SalaryRecord.salary_number.like(f'SAL-{year}-%')
        ).order_by(SalaryRecord.id.desc()).first()
        
        if last_record:
            try:
                last_num = int(last_record.salary_number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        return f"SAL-{year}-{next_num:04d}"
    
    def calculate_attendance_based_salary(self):
        """Calculate salary based on actual attendance records"""
        from datetime import timedelta
        
        # Get attendance records for the pay period
        attendance_records = EmployeeAttendance.query.filter(
            EmployeeAttendance.employee_id == self.employee_id,
            EmployeeAttendance.attendance_date >= self.pay_period_start,
            EmployeeAttendance.attendance_date <= self.pay_period_end
        ).all()
        
        # Calculate expected working days (excluding Sundays)
        current_date = self.pay_period_start
        expected_days = 0
        while current_date <= self.pay_period_end:
            # Exclude Sundays (weekday 6)
            if current_date.weekday() != 6:
                expected_days += 1
            current_date += timedelta(days=1)
        
        self.expected_working_days = expected_days
        
        # Calculate actual days worked and overtime
        actual_days = 0
        total_overtime_hours = 0.0
        
        for attendance in attendance_records:
            if attendance.status in ['present', 'late', 'half_day']:
                if attendance.status == 'half_day':
                    actual_days += 0.5
                else:
                    actual_days += 1
                
                # Add overtime hours
                if attendance.overtime_hours:
                    total_overtime_hours += attendance.overtime_hours
        
        self.actual_days_worked = int(actual_days)
        self.overtime_hours = total_overtime_hours
        
        # Calculate basic amount based on actual days worked
        if self.daily_rate > 0:
            self.basic_amount = self.actual_days_worked * self.daily_rate
        
        # Calculate overtime amount
        if self.overtime_rate > 0:
            self.overtime_amount = self.overtime_hours * self.overtime_rate
        
        return {
            'expected_working_days': self.expected_working_days,
            'actual_days_worked': self.actual_days_worked,
            'daily_rate': self.daily_rate,
            'basic_amount': self.basic_amount,
            'overtime_hours': self.overtime_hours,
            'overtime_amount': self.overtime_amount
        }

class EmployeeAdvance(db.Model):
    __tablename__ = 'employee_advances'
    
    id = db.Column(db.Integer, primary_key=True)
    advance_number = db.Column(db.String(50), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)  # Amount yet to be deducted
    reason = db.Column(db.String(200), nullable=False)
    advance_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    repayment_months = db.Column(db.Integer, default=1)  # Number of months to deduct
    monthly_deduction = db.Column(db.Float, nullable=False)  # Amount to deduct per month
    status = db.Column(db.String(20), default='pending')  # pending, approved, active, completed, cancelled
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, cheque
    notes = db.Column(db.Text)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    requester = db.relationship('User', foreign_keys=[requested_by], backref='requested_advances')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_advances')
    
    @staticmethod
    def generate_advance_number():
        """Generate unique advance number"""
        from datetime import datetime
        year = datetime.now().year
        last_advance = EmployeeAdvance.query.filter(
            EmployeeAdvance.advance_number.like(f'ADV-{year}-%')
        ).order_by(EmployeeAdvance.id.desc()).first()
        
        if last_advance:
            try:
                last_num = int(last_advance.advance_number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        return f"ADV-{year}-{next_num:04d}"
    
    def __repr__(self):
        return f'<EmployeeAdvance {self.advance_number}>'

class EmployeeAttendance(db.Model):
    __tablename__ = 'employee_attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.Time)
    check_out_time = db.Column(db.Time)
    status = db.Column(db.String(20), nullable=False, default='present')  # present, absent, late, half_day, leave
    hours_worked = db.Column(db.Float, default=0.0)  # Calculated working hours
    overtime_hours = db.Column(db.Float, default=0.0)  # Extra hours beyond standard
    leave_type = db.Column(db.String(50))  # sick, casual, personal, vacation (when status = leave)
    notes = db.Column(db.Text)
    
    # Record keeping
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='attendance_records')
    marker = db.relationship('User', backref='marked_attendance')
    
    # Unique constraint to prevent duplicate attendance for same day
    __table_args__ = (db.UniqueConstraint('employee_id', 'attendance_date', name='unique_employee_date'),)
    
    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for attendance status"""
        status_classes = {
            'present': 'bg-success',
            'absent': 'bg-danger',
            'late': 'bg-warning',
            'half_day': 'bg-info',
            'leave': 'bg-secondary'
        }
        return status_classes.get(self.status, 'bg-light')
    
    def calculate_hours_worked(self):
        """Calculate hours worked from check-in and check-out times"""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime, timedelta
            
            # Convert times to datetime for calculation
            today = datetime.today().date()
            check_in = datetime.combine(today, self.check_in_time)
            check_out = datetime.combine(today, self.check_out_time)
            
            # Handle overnight shifts
            if check_out < check_in:
                check_out += timedelta(days=1)
            
            # Calculate total hours
            total_seconds = (check_out - check_in).total_seconds()
            hours = total_seconds / 3600
            
            # Standard working hours (8 hours)
            standard_hours = 8.0
            
            # Calculate regular hours worked
            if hours > standard_hours:
                self.hours_worked = standard_hours
                # Only auto-calculate overtime if not manually set (i.e., overtime_hours is 0)
                if not hasattr(self, '_manual_overtime_set') and self.overtime_hours == 0:
                    self.overtime_hours = round(hours - standard_hours, 2)
            else:
                self.hours_worked = round(hours, 2)
                # Only reset overtime if not manually set
                if not hasattr(self, '_manual_overtime_set') and self.overtime_hours == 0:
                    self.overtime_hours = 0.0
        else:
            self.hours_worked = 0.0
            # Only reset overtime if not manually set
            if not hasattr(self, '_manual_overtime_set'):
                self.overtime_hours = 0.0
    
    def __repr__(self):
        return f'<EmployeeAttendance {self.employee.full_name} - {self.attendance_date}>'

# Document model moved to models.document.py to avoid conflicts

class DailyJobWorkEntry(db.Model):
    """Model for tracking daily job work progress by workers"""
    __tablename__ = 'daily_job_work_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    job_work_id = db.Column(db.Integer, db.ForeignKey('job_works.id'), nullable=False)
    worker_name = db.Column(db.String(100), nullable=False)
    work_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    hours_worked = db.Column(db.Float, nullable=False)
    quantity_completed = db.Column(db.Float, nullable=False)
    scrap_quantity = db.Column(db.Float, default=0.0)  # Scrap/waste quantity produced
    quality_status = db.Column(db.String(20), nullable=False, default='good')  # good, needs_rework, defective
    process_stage = db.Column(db.String(20), nullable=False, default='in_progress')  # started, in_progress, completed, on_hold
    notes = db.Column(db.Text)
    
    # Inspection fields for in-house job work entries
    inspection_status = db.Column(db.String(20), default='pending')  # pending, passed, failed
    inspection_notes = db.Column(db.Text)  # Inspection notes
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    inspected_at = db.Column(db.DateTime, nullable=True)
    material_classification = db.Column(db.String(50), nullable=False, default='production_use')  # raw_material, production_use, finished_goods
    
    # Quality inspection quantity fields
    inspected_quantity = db.Column(db.Float, default=0.0)  # Total quantity inspected
    passed_quantity = db.Column(db.Float, default=0.0)  # Quantity that passed inspection
    rejected_quantity = db.Column(db.Float, default=0.0)  # Quantity that was rejected
    rejection_reasons = db.Column(db.Text)  # Reasons for rejection
    
    # Audit fields
    logged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job_work = db.relationship('JobWork', backref='daily_entries')
    logger = db.relationship('User', foreign_keys='DailyJobWorkEntry.logged_by', backref='logged_daily_work')
    inspector = db.relationship('User', foreign_keys='DailyJobWorkEntry.inspected_by', backref='inspected_daily_entries')
    
    # Unique constraint to prevent duplicate entries for same worker/job/date
    __table_args__ = (db.UniqueConstraint('job_work_id', 'worker_name', 'work_date', name='unique_worker_job_date'),)
    
    @property
    def quality_badge_class(self):
        """Return Bootstrap badge class for quality status"""
        quality_classes = {
            'good': 'bg-success',
            'needs_rework': 'bg-warning',
            'defective': 'bg-danger'
        }
        return quality_classes.get(self.quality_status, 'bg-light')
    
    @property
    def stage_badge_class(self):
        """Return Bootstrap badge class for process stage"""
        stage_classes = {
            'started': 'bg-info',
            'in_progress': 'bg-primary',
            'completed': 'bg-success',
            'on_hold': 'bg-secondary'
        }
        return stage_classes.get(self.process_stage, 'bg-light')
    
    def __repr__(self):
        return f'<DailyJobWorkEntry {self.worker_name} - {self.job_work.job_number} - {self.work_date}>'

# Add Production-ProductionBatch relationship at the end after all models are defined
Production.production_batches = db.relationship('ProductionBatch', backref='production', lazy=True, cascade='all, delete-orphan')
