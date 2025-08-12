"""
Cost Calculation Settings Model
Manages feature toggles and configuration for cost calculation system
"""
from app import db
from datetime import datetime


class CostCalculationSettings(db.Model):
    """Settings for cost calculation features"""
    __tablename__ = 'cost_calculation_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Phase 1: Core Infrastructure & Dashboard
    enable_enhanced_dashboard = db.Column(db.Boolean, default=True)
    enable_bulk_operations = db.Column(db.Boolean, default=True)
    enable_cost_source_switching = db.Column(db.Boolean, default=True)
    enable_variance_analysis = db.Column(db.Boolean, default=True)
    enable_excel_export = db.Column(db.Boolean, default=True)
    enable_advanced_analytics = db.Column(db.Boolean, default=True)
    
    # Phase 2: Smart Automation & Notifications
    enable_cost_change_notifications = db.Column(db.Boolean, default=True)
    enable_smart_bom_creation = db.Column(db.Boolean, default=True)
    enable_automated_cost_validation = db.Column(db.Boolean, default=True)
    enable_integration_alerts = db.Column(db.Boolean, default=True)
    
    # Phase 3: Enhanced User Experience
    enable_interactive_calculator = db.Column(db.Boolean, default=True)
    enable_cost_simulation = db.Column(db.Boolean, default=True)
    enable_drag_drop_bom = db.Column(db.Boolean, default=True)
    enable_smart_search = db.Column(db.Boolean, default=True)
    
    # Notification Settings
    cost_change_threshold_percent = db.Column(db.Float, default=10.0)  # Alert on 10%+ cost changes
    outdated_cost_days = db.Column(db.Integer, default=7)  # Alert after 7 days
    
    # Performance Settings
    real_time_calculation_enabled = db.Column(db.Boolean, default=True)
    batch_calculation_size = db.Column(db.Integer, default=50)
    
    # UI Settings
    default_cost_view = db.Column(db.String(20), default='comparison')  # comparison, bom_only, manual_only
    show_analytics_cards = db.Column(db.Boolean, default=True)
    show_comparison_table = db.Column(db.Boolean, default=True)
    enable_quick_actions = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    @classmethod
    def get_current_settings(cls):
        """Get current settings, create default if none exist"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def update_settings(self, **kwargs):
        """Update settings with validation"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert settings to dictionary for API responses"""
        return {
            'phase1': {
                'enhanced_dashboard': self.enable_enhanced_dashboard,
                'bulk_operations': self.enable_bulk_operations,
                'cost_source_switching': self.enable_cost_source_switching,
                'variance_analysis': self.enable_variance_analysis,
                'excel_export': self.enable_excel_export,
                'advanced_analytics': self.enable_advanced_analytics
            },
            'phase2': {
                'cost_change_notifications': self.enable_cost_change_notifications,
                'smart_bom_creation': self.enable_smart_bom_creation,
                'automated_cost_validation': self.enable_automated_cost_validation,
                'integration_alerts': self.enable_integration_alerts
            },
            'phase3': {
                'interactive_calculator': self.enable_interactive_calculator,
                'cost_simulation': self.enable_cost_simulation,
                'drag_drop_bom': self.enable_drag_drop_bom,
                'smart_search': self.enable_smart_search
            },
            'thresholds': {
                'cost_change_threshold': self.cost_change_threshold_percent,
                'outdated_cost_days': self.outdated_cost_days
            },
            'performance': {
                'real_time_calculation': self.real_time_calculation_enabled,
                'batch_size': self.batch_calculation_size
            },
            'ui': {
                'default_view': self.default_cost_view,
                'analytics_cards': self.show_analytics_cards,
                'comparison_table': self.show_comparison_table,
                'quick_actions': self.enable_quick_actions
            }
        }


class CostChangeNotification(db.Model):
    """Track cost change notifications"""
    __tablename__ = 'cost_change_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    old_cost = db.Column(db.Numeric(10, 2))
    new_cost = db.Column(db.Numeric(10, 2))
    change_percent = db.Column(db.Float)
    change_type = db.Column(db.String(20))  # 'increase', 'decrease', 'initial'
    notification_sent = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50))  # 'email', 'sms', 'dashboard'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime)
    acknowledged_by = db.Column(db.String(100))
    
    # Relationships
    item = db.relationship('Item', backref='cost_notifications')