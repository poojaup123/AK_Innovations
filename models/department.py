from app import db
from datetime import datetime

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Note: Employee relationship is managed through department code matching
    
    def __repr__(self):
        return f'<Department {self.name}>'
    
    @classmethod
    def get_choices(cls):
        """Get choices for SelectField"""
        departments = cls.query.filter_by(is_active=True).order_by(cls.name).all()
        return [('', 'Select Department')] + [(dept.code, dept.name) for dept in departments]
    
    @classmethod
    def get_default_departments(cls):
        """Create default departments if none exist"""
        if cls.query.count() == 0:
            default_departments = [
                ('production', 'Production', 'Manufacturing and production operations'),
                ('assembly', 'Assembly', 'Product assembly and finishing'),
                ('quality_control', 'Quality Control', 'Quality assurance and testing'),
                ('finishing', 'Finishing', 'Surface treatment and final finishing'),
                ('packaging', 'Packaging', 'Product packaging and shipping preparation'),
                ('maintenance', 'Maintenance', 'Equipment maintenance and repair'),
                ('research_development', 'Research & Development', 'R&D and new product development'),
                ('administration', 'Administration', 'General administration and management'),
                ('sales_marketing', 'Sales & Marketing', 'Sales, marketing, and customer relations'),
                ('accounts_finance', 'Accounts & Finance', 'Financial management and accounting'),
                ('human_resources', 'Human Resources', 'HR management and employee relations'),
                ('stores_inventory', 'Stores & Inventory', 'Warehouse and inventory management')
            ]
            
            for code, name, description in default_departments:
                dept = cls(code=code, name=name, description=description)
                db.session.add(dept)
            
            db.session.commit()
        
        return cls.query.filter_by(is_active=True).all()
    
    @classmethod
    def get_by_code(cls, code):
        """Get department by code"""
        return cls.query.filter_by(code=code, is_active=True).first()