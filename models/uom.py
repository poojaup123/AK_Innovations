from app import db
from datetime import datetime

class UnitOfMeasure(db.Model):
    """Base units of measure (Kg, Pieces, Meters, etc.)"""
    __tablename__ = 'units_of_measure'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # e.g., "Kilogram", "Pieces", "Meters"
    symbol = db.Column(db.String(10), nullable=False, unique=True)  # e.g., "Kg", "Pcs", "M"
    category = db.Column(db.String(50), nullable=False)  # "Weight", "Count", "Length", "Volume"
    is_base_unit = db.Column(db.Boolean, default=False)  # Base unit for conversion calculations
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    conversions_from = db.relationship('UOMConversion', foreign_keys='UOMConversion.from_unit_id', backref='from_unit')
    conversions_to = db.relationship('UOMConversion', foreign_keys='UOMConversion.to_unit_id', backref='to_unit')
    
    def __repr__(self):
        return f'<UnitOfMeasure {self.name} ({self.symbol})>'
    
    @staticmethod
    def ensure_default_units():
        """Ensure default units of measure exist in the database"""
        from app import db
        
        # Check if any UOMs already exist
        if UnitOfMeasure.query.first():
            return  # Already populated
        
        default_units = [
            # Count/Pieces
            {'name': 'Pieces', 'symbol': 'Pcs', 'category': 'Count', 'is_base_unit': True},
            {'name': 'Units', 'symbol': 'Nos', 'category': 'Count', 'is_base_unit': False},
            {'name': 'Sets', 'symbol': 'Set', 'category': 'Count', 'is_base_unit': False},
            {'name': 'Dozen', 'symbol': 'Dzn', 'category': 'Count', 'is_base_unit': False},
            {'name': 'Pairs', 'symbol': 'Pair', 'category': 'Count', 'is_base_unit': False},
            
            # Weight
            {'name': 'Kilogram', 'symbol': 'Kg', 'category': 'Weight', 'is_base_unit': True},
            {'name': 'Gram', 'symbol': 'g', 'category': 'Weight', 'is_base_unit': False},
            {'name': 'Tonne', 'symbol': 'MT', 'category': 'Weight', 'is_base_unit': False},
            {'name': 'Pound', 'symbol': 'lbs', 'category': 'Weight', 'is_base_unit': False},
            {'name': 'Quintal', 'symbol': 'Qtl', 'category': 'Weight', 'is_base_unit': False},
            
            # Length
            {'name': 'Meter', 'symbol': 'M', 'category': 'Length', 'is_base_unit': True},
            {'name': 'Centimeter', 'symbol': 'cm', 'category': 'Length', 'is_base_unit': False},
            {'name': 'Millimeter', 'symbol': 'mm', 'category': 'Length', 'is_base_unit': False},
            {'name': 'Kilometer', 'symbol': 'Km', 'category': 'Length', 'is_base_unit': False},
            {'name': 'Inch', 'symbol': 'in', 'category': 'Length', 'is_base_unit': False},
            {'name': 'Feet', 'symbol': 'ft', 'category': 'Length', 'is_base_unit': False},
            
            # Area
            {'name': 'Square Meter', 'symbol': 'SQM', 'category': 'Area', 'is_base_unit': True},
            {'name': 'Square Feet', 'symbol': 'SQFT', 'category': 'Area', 'is_base_unit': False},
            {'name': 'Square Inch', 'symbol': 'SQIN', 'category': 'Area', 'is_base_unit': False},
            {'name': 'Square Centimeter', 'symbol': 'SQCM', 'category': 'Area', 'is_base_unit': False},
            
            # Volume
            {'name': 'Liter', 'symbol': 'L', 'category': 'Volume', 'is_base_unit': True},
            {'name': 'Milliliter', 'symbol': 'ml', 'category': 'Volume', 'is_base_unit': False},
            {'name': 'Gallon', 'symbol': 'Gal', 'category': 'Volume', 'is_base_unit': False},
            {'name': 'Cubic Meter', 'symbol': 'CBM', 'category': 'Volume', 'is_base_unit': False},
            {'name': 'Cubic Feet', 'symbol': 'CFT', 'category': 'Volume', 'is_base_unit': False},
            
            # Time
            {'name': 'Hour', 'symbol': 'Hr', 'category': 'Time', 'is_base_unit': True},
            {'name': 'Minute', 'symbol': 'Min', 'category': 'Time', 'is_base_unit': False},
            {'name': 'Day', 'symbol': 'Day', 'category': 'Time', 'is_base_unit': False},
            {'name': 'Week', 'symbol': 'Wk', 'category': 'Time', 'is_base_unit': False},
            {'name': 'Month', 'symbol': 'Mo', 'category': 'Time', 'is_base_unit': False}
        ]
        
        try:
            for unit_data in default_units:
                unit = UnitOfMeasure(**unit_data)
                db.session.add(unit)
            
            db.session.commit()
            print(f"Successfully created {len(default_units)} default units of measure")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating default UOMs: {e}")
    
    @staticmethod
    def get_choices():
        """Get choices for form dropdowns"""
        units = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        return [(unit.symbol, f"{unit.name} ({unit.symbol}) - {unit.category}") for unit in units]

class UOMConversion(db.Model):
    """Conversion factors between units of measure"""
    __tablename__ = 'uom_conversions'
    
    id = db.Column(db.Integer, primary_key=True)
    from_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)
    to_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)
    conversion_factor = db.Column(db.Numeric(15, 6), nullable=False)  # 1 from_unit = X to_units
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)  # e.g., "Based on average weight per piece"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('from_unit_id', 'to_unit_id', name='unique_conversion_pair'),)
    
    def __repr__(self):
        return f'<UOMConversion 1 {self.from_unit.symbol} = {self.conversion_factor} {self.to_unit.symbol}>'

class ItemUOMConversion(db.Model):
    """Item-specific unit conversions (overrides global conversions)"""
    __tablename__ = 'item_uom_conversions'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    purchase_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)  # What we buy in
    sale_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)  # What we sell in
    inventory_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)  # What we track in
    
    # Conversion factors
    purchase_to_inventory = db.Column(db.Numeric(15, 6), nullable=False)  # 1 purchase unit = X inventory units
    inventory_to_sale = db.Column(db.Numeric(15, 6), nullable=False)  # 1 inventory unit = X sale units
    
    # Optional: Direct purchase to sale conversion for efficiency
    purchase_to_sale = db.Column(db.Numeric(15, 6))  # 1 purchase unit = X sale units
    
    # Metadata
    weight_per_piece = db.Column(db.Numeric(10, 4))  # For weight-to-count conversions
    pieces_per_kg = db.Column(db.Numeric(10, 4))  # For count-to-weight conversions
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='uom_conversion')
    purchase_unit = db.relationship('UnitOfMeasure', foreign_keys=[purchase_unit_id])
    sale_unit = db.relationship('UnitOfMeasure', foreign_keys=[sale_unit_id])
    inventory_unit = db.relationship('UnitOfMeasure', foreign_keys=[inventory_unit_id])
    
    def convert_purchase_to_inventory(self, purchase_qty):
        """Convert purchase quantity to inventory quantity"""
        return float(purchase_qty) * float(self.purchase_to_inventory)
    
    def convert_inventory_to_sale(self, inventory_qty):
        """Convert inventory quantity to sale quantity"""
        return float(inventory_qty) * float(self.inventory_to_sale)
    
    def convert_sale_to_inventory(self, sale_qty):
        """Convert sale quantity to inventory quantity"""
        return float(sale_qty) / float(self.inventory_to_sale)
    
    def convert_purchase_to_sale(self, purchase_qty):
        """Convert purchase quantity directly to sale quantity"""
        if self.purchase_to_sale:
            return float(purchase_qty) * float(self.purchase_to_sale)
        else:
            # Calculate via inventory
            inventory_qty = self.convert_purchase_to_inventory(purchase_qty)
            return self.convert_inventory_to_sale(inventory_qty)
    
    def __repr__(self):
        return f'<ItemUOMConversion {self.item.name}: Buy {self.purchase_unit.symbol} → Stock {self.inventory_unit.symbol} → Sell {self.sale_unit.symbol}>'

class UOMConversionLog(db.Model):
    """Log of UOM conversions for audit trail"""
    __tablename__ = 'uom_conversion_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'purchase', 'sale', 'production', 'adjustment'
    transaction_id = db.Column(db.String(100))  # Reference to PO, SO, etc.
    
    original_quantity = db.Column(db.Numeric(15, 4), nullable=False)
    original_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)
    converted_quantity = db.Column(db.Numeric(15, 4), nullable=False)
    converted_unit_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'), nullable=False)
    conversion_factor = db.Column(db.Numeric(15, 6), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    item = db.relationship('Item')
    original_unit = db.relationship('UnitOfMeasure', foreign_keys=[original_unit_id])
    converted_unit = db.relationship('UnitOfMeasure', foreign_keys=[converted_unit_id])
    created_by_user = db.relationship('User')
    
    def __repr__(self):
        return f'<UOMConversionLog {self.original_quantity} {self.original_unit.symbol} → {self.converted_quantity} {self.converted_unit.symbol}>'