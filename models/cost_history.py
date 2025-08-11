"""
Cost History and Freezing Models

Track cost changes over time and support cost freezing for production orders
"""

from datetime import datetime
from app import db


class ItemCostHistory(db.Model):
    """Track cost changes over time for items"""
    __tablename__ = 'item_cost_history'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Cost information
    old_cost = db.Column(db.Float, nullable=False)
    new_cost = db.Column(db.Float, nullable=False)
    cost_source = db.Column(db.String(20), nullable=False)  # manual, bom_calculated, hybrid
    
    # Change information
    change_reason = db.Column(db.String(100))  # BOM update, material price change, etc.
    change_type = db.Column(db.String(50))  # automatic, manual, system
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Cost breakdown for bom_calculated items
    material_cost = db.Column(db.Float, default=0.0)
    labor_cost = db.Column(db.Float, default=0.0)
    overhead_cost = db.Column(db.Float, default=0.0)
    
    # Validation flags
    is_validated = db.Column(db.Boolean, default=False)
    validation_notes = db.Column(db.Text)
    
    # Relationships
    item = db.relationship('Item', backref='cost_history')
    changed_by_user = db.relationship('User', foreign_keys=[changed_by])
    
    @property
    def cost_change_percent(self):
        """Calculate percentage change in cost"""
        if self.old_cost and self.old_cost > 0:
            return ((self.new_cost - self.old_cost) / self.old_cost) * 100
        return 0
    
    @property
    def cost_change_amount(self):
        """Calculate absolute change in cost"""
        return self.new_cost - self.old_cost
    
    @classmethod
    def log_cost_change(cls, item_id, old_cost, new_cost, reason, change_type='automatic', user_id=None):
        """Log a cost change event"""
        cost_history = cls(
            item_id=item_id,
            old_cost=old_cost,
            new_cost=new_cost,
            cost_source=db.session.get(Item, item_id).cost_source if item_id else 'unknown',
            change_reason=reason,
            change_type=change_type,
            changed_by=user_id
        )
        db.session.add(cost_history)
        return cost_history


class ProductionOrderCostFreeze(db.Model):
    """Freeze costs for active production orders"""
    __tablename__ = 'production_order_cost_freeze'
    
    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, nullable=False)  # References production order
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    
    # Frozen cost information
    frozen_cost = db.Column(db.Float, nullable=False)
    cost_breakdown = db.Column(db.JSON)  # Detailed cost breakdown
    frozen_at = db.Column(db.DateTime, default=datetime.utcnow)
    frozen_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Production context
    production_quantity = db.Column(db.Float)
    estimated_completion_date = db.Column(db.Date)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    released_at = db.Column(db.DateTime)
    released_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    item = db.relationship('Item')
    frozen_by_user = db.relationship('User', foreign_keys=[frozen_by])
    released_by_user = db.relationship('User', foreign_keys=[released_by])
    
    @classmethod
    def freeze_cost_for_production(cls, production_order_id, item_id, quantity, user_id=None):
        """Freeze current cost for a production order"""
        from models import Item
        
        item = Item.query.get(item_id)
        if not item:
            return None
        
        # Get current cost
        current_cost = item.effective_cost
        
        # Get detailed breakdown if BOM calculated
        cost_breakdown = None
        if item.cost_source == 'bom_calculated':
            try:
                from services.cost_calculator import calculate_item_cost
                result = calculate_item_cost(item_id, 1.0)
                if result.get('success', True):
                    cost_breakdown = result
            except:
                pass
        
        freeze = cls(
            production_order_id=production_order_id,
            item_id=item_id,
            frozen_cost=current_cost,
            cost_breakdown=cost_breakdown,
            production_quantity=quantity,
            frozen_by=user_id
        )
        
        db.session.add(freeze)
        return freeze
    
    def release_freeze(self, user_id=None):
        """Release the cost freeze"""
        self.is_active = False
        self.released_at = datetime.utcnow()
        self.released_by = user_id


class CostValidationRule(db.Model):
    """Rules for validating calculated costs"""
    __tablename__ = 'cost_validation_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Rule configuration
    rule_type = db.Column(db.String(50), nullable=False)  # percentage_change, absolute_change, min_max_range
    threshold_value = db.Column(db.Float)  # Threshold for alerts
    comparison_type = db.Column(db.String(20))  # greater_than, less_than, between
    secondary_threshold = db.Column(db.Float)  # For range comparisons
    
    # Application scope
    item_type_filter = db.Column(db.String(50))  # Apply to specific item types
    cost_source_filter = db.Column(db.String(20))  # Apply to specific cost sources
    
    # Rule status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    created_by_user = db.relationship('User')
    
    def validate_cost_change(self, item, old_cost, new_cost):
        """Validate a cost change against this rule"""
        if not self.is_active:
            return True, None
        
        # Apply filters
        if self.item_type_filter and item.item_type != self.item_type_filter:
            return True, None
        
        if self.cost_source_filter and item.cost_source != self.cost_source_filter:
            return True, None
        
        # Calculate change metrics
        if self.rule_type == 'percentage_change' and old_cost > 0:
            change_percent = abs((new_cost - old_cost) / old_cost) * 100
            if change_percent > self.threshold_value:
                return False, f"Cost change of {change_percent:.1f}% exceeds threshold of {self.threshold_value}%"
        
        elif self.rule_type == 'absolute_change':
            change_amount = abs(new_cost - old_cost)
            if change_amount > self.threshold_value:
                return False, f"Cost change of ₹{change_amount:.2f} exceeds threshold of ₹{self.threshold_value:.2f}"
        
        elif self.rule_type == 'min_max_range':
            if new_cost < self.threshold_value or new_cost > self.secondary_threshold:
                return False, f"New cost ₹{new_cost:.2f} is outside acceptable range ₹{self.threshold_value:.2f} - ₹{self.secondary_threshold:.2f}"
        
        return True, None
    
    @classmethod
    def get_default_rules(cls):
        """Get or create default validation rules"""
        default_rules = [
            {
                'rule_name': 'Large Percentage Change Alert',
                'description': 'Alert when cost changes by more than 20%',
                'rule_type': 'percentage_change',
                'threshold_value': 20.0,
                'comparison_type': 'greater_than'
            },
            {
                'rule_name': 'High Cost Alert',
                'description': 'Alert when BOM calculated cost exceeds ₹1000',
                'rule_type': 'min_max_range',
                'threshold_value': 0.0,
                'secondary_threshold': 1000.0,
                'cost_source_filter': 'bom_calculated'
            },
            {
                'rule_name': 'Negative Cost Alert',
                'description': 'Alert when calculated cost is negative',
                'rule_type': 'min_max_range',
                'threshold_value': 0.0,
                'secondary_threshold': 999999.0,
                'comparison_type': 'less_than'
            }
        ]
        
        existing_rules = cls.query.filter_by(is_active=True).all()
        if not existing_rules:
            for rule_data in default_rules:
                rule = cls(**rule_data)
                db.session.add(rule)
            db.session.commit()
        
        return cls.query.filter_by(is_active=True).all()


from models import Item, User