"""
Minimal BOM models to replace the problematic recursive models
"""
from datetime import datetime
from app import db

class MinimalBOM(db.Model):
    __tablename__ = 'minimal_boms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    output_quantity = db.Column(db.Float, default=1.0)
    output_uom_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.id'))
    labor_cost_per_unit = db.Column(db.Float, default=0.0)
    overhead_cost_per_unit = db.Column(db.Float, default=0.0)
    markup_percentage = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def total_material_cost(self):
        """Simple material cost calculation without recursion"""
        total = 0.0
        try:
            # Use direct SQL query to avoid SQLAlchemy relationship issues
            result = db.session.execute(
                "SELECT SUM(quantity_required * unit_cost) FROM minimal_bom_items WHERE bom_id = :bom_id",
                {"bom_id": self.id}
            ).scalar()
            total = float(result or 0)
        except:
            total = 0.0
        return total
    
    @property
    def total_cost_per_unit(self):
        """Total cost including all components"""
        material_cost = self.total_material_cost
        labor_cost = self.labor_cost_per_unit or 0
        overhead_cost = self.overhead_cost_per_unit or 0
        subtotal = material_cost + labor_cost + overhead_cost
        markup_amount = subtotal * (self.markup_percentage or 0) / 100
        return subtotal + markup_amount

class MinimalBOMItem(db.Model):
    __tablename__ = 'minimal_bom_items'
    
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('minimal_boms.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False, default=0.0)
    unit_cost = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def total_cost(self):
        return (self.quantity_required or 0) * (self.unit_cost or 0)