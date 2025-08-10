from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, BooleanField, FieldList, FormField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from models import Item, Supplier, UnitOfMeasure
from datetime import datetime

class EnhancedBOMItemForm(FlaskForm):
    """Enhanced BOM Item form with component type classification"""
    material_id = SelectField('Material', coerce=int, validators=[DataRequired()])
    qty_required = FloatField('Quantity Required', validators=[DataRequired(), NumberRange(min=0.01)])
    uom_id = SelectField('Unit of Measure', coerce=int, validators=[DataRequired()])
    unit_cost = FloatField('Unit Cost', validators=[NumberRange(min=0)], default=0.0)
    scrap_percent = FloatField('Scrap %', validators=[NumberRange(min=0, max=100)], default=0.0)
    
    # Component Type Classification
    component_type = SelectField('Component Type', 
                                choices=[
                                    ('raw_material', 'Raw Material'),
                                    ('sub_assembly', 'Sub-Assembly'),
                                    ('phantom_bom', 'Phantom BOM'),
                                    ('packing', 'Packing Material'),
                                    ('consumable', 'Consumable')
                                ],
                                default='raw_material')
    
    is_critical = BooleanField('Critical Material')
    is_phantom = BooleanField('Phantom Component')
    is_packing_material = BooleanField('Packing Material')
    process_step = IntegerField('Process Step', default=1)
    process_name = StringField('Process Name', validators=[Length(max=100)])
    default_supplier_id = SelectField('Default Supplier', coerce=int, validators=[Optional()])
    
    # Missing fields from user BOM design requirements
    component_source = SelectField('Source',
                                 choices=[
                                     ('purchase', 'Purchase'),
                                     ('in_house', 'In-house'),
                                     ('outsourced', 'Outsourced')
                                 ],
                                 default='purchase')
    
    batch_tracking_required = BooleanField('Batch Tracking Required', default=True)
    assigned_department_id = SelectField('Assigned Department', coerce=int, validators=[Optional()])
    assigned_machine_id = SelectField('Assigned Machine', coerce=int, validators=[Optional()])
    assigned_vendor_id = SelectField('Assigned Vendor', coerce=int, validators=[Optional()])
    
    remarks = TextAreaField('Remarks')
    
    def __init__(self, *args, **kwargs):
        super(EnhancedBOMItemForm, self).__init__(*args, **kwargs)
        
        # Populate Material choices
        try:
            materials = Item.query.order_by(Item.name).all()
            self.material_id.choices = [(0, '-- Select Material --')] + [(item.id, f"{item.name} ({item.code})") for item in materials]
        except:
            self.material_id.choices = [(0, '-- No Materials Available --')]
        
        # Populate UOM choices
        try:
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.name).all()
            self.uom_id.choices = [(0, '-- Select UOM --')] + [(uom.id, f"{uom.name} ({uom.symbol})") for uom in uoms]
        except:
            self.uom_id.choices = [(0, '-- No UOMs Available --')]
        
        # Populate Supplier choices
        try:
            suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
            self.default_supplier_id.choices = [(0, '-- Select Supplier --')] + [(supplier.id, supplier.name) for supplier in suppliers]
            self.assigned_vendor_id.choices = [(0, '-- Select Vendor --')] + [(supplier.id, supplier.name) for supplier in suppliers if supplier.partner_type in ['vendor', 'supplier']]
        except:
            self.default_supplier_id.choices = [(0, '-- No Suppliers Available --')]
            self.assigned_vendor_id.choices = [(0, '-- No Vendors Available --')]
        
        # Populate Department choices
        try:
            from models import Department
            departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
            self.assigned_department_id.choices = [(0, '-- Select Department --')] + [(dept.id, dept.name) for dept in departments]
        except:
            self.assigned_department_id.choices = [(0, '-- No Departments Available --')]
        
        # Populate Machine choices (from Items that are machines/tools)
        try:
            machines = Item.query.filter(Item.item_type.in_(['machine', 'tool', 'equipment'])).order_by(Item.name).all()
            self.assigned_machine_id.choices = [(0, '-- Select Machine --')] + [(machine.id, f"{machine.name} ({machine.code})") for machine in machines]
        except:
            self.assigned_machine_id.choices = [(0, '-- No Machines Available --')]

class EnhancedBOMProcessForm(FlaskForm):
    """Enhanced BOM Process form with lead time and vendor assignment"""
    step_number = IntegerField('Step Number', validators=[DataRequired(), NumberRange(min=1)])
    process_name = StringField('Process Name', validators=[DataRequired(), Length(max=100)])
    process_code = StringField('Process Code', validators=[Length(max=20)])
    operation_description = TextAreaField('Operation Description')
    
    # Time and Cost
    setup_time_minutes = FloatField('Setup Time (minutes)', validators=[NumberRange(min=0)], default=0.0)
    run_time_minutes = FloatField('Runtime (minutes)', validators=[NumberRange(min=0)], default=0.0)
    labor_rate_per_hour = FloatField('Labor Rate (₹/hour)', validators=[NumberRange(min=0)], default=0.0)
    cost_per_unit = FloatField('Cost per Unit', validators=[NumberRange(min=0)], default=0.0)
    cost_unit = SelectField('Cost Unit', 
                           choices=[
                               ('per_unit', 'Per Unit'),
                               ('per_kg', 'Per Kg'),
                               ('per_meter', 'Per Meter'),
                               ('per_hour', 'Per Hour')
                           ],
                           default='per_unit')
    
    # Enhanced Process Management
    lead_time_days = FloatField('Lead Time (days)', validators=[NumberRange(min=0)], default=1.0)
    machine_setup_time = FloatField('Machine Setup (minutes)', validators=[NumberRange(min=0)], default=0.0)
    process_priority = IntegerField('Priority (1=high, 5=low)', validators=[NumberRange(min=1, max=5)], default=1)
    operator_skill_required = SelectField('Skill Required',
                                        choices=[
                                            ('basic', 'Basic'),
                                            ('intermediate', 'Intermediate'),
                                            ('advanced', 'Advanced'),
                                            ('expert', 'Expert')
                                        ],
                                        default='basic')
    
    # Department and Outsourcing
    department_id = SelectField('Department', coerce=int, validators=[Optional()])
    is_outsourced = BooleanField('Outsourced Process')
    vendor_id = SelectField('Vendor', coerce=int, validators=[Optional()])
    
    # Quality and Scrap
    estimated_scrap_percent = FloatField('Expected Scrap %', validators=[NumberRange(min=0, max=100)], default=0.0)
    quality_check_required = BooleanField('Quality Check Required')
    
    notes = TextAreaField('Notes')
    
    def __init__(self, *args, **kwargs):
        super(EnhancedBOMProcessForm, self).__init__(*args, **kwargs)
        
        # Populate Department choices
        try:
            from models import Department
            departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
            self.department_id.choices = [(0, '-- Select Department --')] + [(dept.id, dept.name) for dept in departments]
        except:
            self.department_id.choices = [(0, '-- No Departments Available --')]
        
        # Populate Vendor choices for outsourcing
        try:
            vendors = Supplier.query.filter_by(is_active=True, partner_type='vendor').order_by(Supplier.name).all()
            self.vendor_id.choices = [(0, '-- Select Vendor --')] + [(vendor.id, vendor.name) for vendor in vendors]
        except:
            self.vendor_id.choices = [(0, '-- No Vendors Available --')]

class EnhancedBOMForm(FlaskForm):
    """Enhanced BOM form with partial production and advanced settings from user design requirements"""
    # Section 1: BOM Header (from user design requirements)
    bom_code = StringField('BOM Code', validators=[DataRequired(), Length(max=50)])
    product_id = SelectField('Product Name', coerce=int, validators=[DataRequired()])
    output_uom_id = SelectField('UOM', coerce=int, validators=[DataRequired()])
    output_quantity = FloatField('Quantity per BOM', validators=[DataRequired(), NumberRange(min=0.01)], default=1.0)
    is_phantom_bom = BooleanField('Phantom BOM?')
    version = StringField('Version', validators=[DataRequired(), Length(max=20)], default='1.0')
    effective_date = StringField('Effective Date', validators=[DataRequired()])
    bom_status = SelectField('Status',
                           choices=[
                               ('draft', 'Draft'),
                               ('active', 'Active'),
                               ('obsolete', 'Obsolete')
                           ],
                           default='draft')
    description = TextAreaField('Description')
    
    # Section 5: Additional Settings (from user design requirements)
    lead_time_days = FloatField('Lead Time (days)', validators=[NumberRange(min=0)], default=1.0)
    auto_cost_calculation = BooleanField('Auto-calculate Costs from GRN/Job Work/HR', default=True)
    batch_tracking_enabled = BooleanField('Enable Batch Tracking', default=True)
    
    # Removed duplicate Production Settings - already defined in Section 1
    unit_weight = FloatField('Unit Weight (kg)', validators=[NumberRange(min=0)], default=0.0)
    unit_weight_uom = SelectField('Weight UOM', 
                                 choices=[
                                     ('kg', 'Kilogram'),
                                     ('g', 'Gram'),
                                     ('lbs', 'Pounds'),
                                     ('oz', 'Ounces')
                                 ],
                                 default='kg')
    
    # Advanced BOM Features
    allow_partial_production = BooleanField('Allow Partial Production', default=True)
    allow_substitute_items = BooleanField('Allow Substitute Items', default=False)
    auto_create_job_work = BooleanField('Auto-create Job Work Orders', default=False)
    auto_batch_assignment = BooleanField('Smart Batch Assignment', default=True)
    
    # BOM Type (removed duplicate is_phantom_bom - already defined in Section 1)
    intermediate_product = BooleanField('Intermediate Product')
    
    # Cost Settings
    labor_cost_per_unit = FloatField('Manual Labor Cost', validators=[NumberRange(min=0)], default=0.0)
    overhead_cost_per_unit = FloatField('Overhead Cost', validators=[NumberRange(min=0)], default=0.0)
    overhead_percentage = FloatField('Overhead %', validators=[NumberRange(min=0, max=100)], default=0.0)
    freight_cost_per_unit = FloatField('Freight Cost', validators=[NumberRange(min=0)], default=0.0)
    freight_unit_type = SelectField('Freight Unit',
                                  choices=[
                                      ('per_piece', 'Per Piece'),
                                      ('per_kg', 'Per Kg'),
                                      ('per_ton', 'Per Ton'),
                                      ('per_box', 'Per Box'),
                                      ('per_carton', 'Per Carton')
                                  ],
                                  default='per_piece')
    markup_percentage = FloatField('Markup %', validators=[NumberRange(min=0, max=1000)], default=0.0)
    
    # Scrap Management
    estimated_scrap_percent = FloatField('Estimated Scrap %', validators=[NumberRange(min=0, max=100)], default=0.0)
    scrap_quantity = FloatField('Scrap Quantity (kg)', validators=[NumberRange(min=0)], default=0.0)
    scrap_value_recovery_percent = FloatField('Scrap Recovery %', validators=[NumberRange(min=0, max=100)], default=15.0)
    
    remarks = TextAreaField('Remarks')
    
    # Submit buttons
    save_draft = SubmitField('Save as Draft')
    save_active = SubmitField('Save & Activate')
    
    def __init__(self, *args, **kwargs):
        super(EnhancedBOMForm, self).__init__(*args, **kwargs)
        
        # Populate Product choices
        try:
            products = Item.query.order_by(Item.name).all()
            self.product_id.choices = [(0, '-- Select Product --')] + [(item.id, f"{item.name} ({item.code})") for item in products]
        except:
            self.product_id.choices = [(0, '-- No Products Available --')]
        
        # Populate UOM choices
        try:
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.name).all()
            self.output_uom_id.choices = [(0, '-- Select UOM --')] + [(uom.id, f"{uom.name} ({uom.symbol})") for uom in uoms]
        except:
            self.output_uom_id.choices = [(0, '-- No UOMs Available --')]

class PartialProductionForm(FlaskForm):
    """Form for planning partial production runs"""
    bom_id = SelectField('BOM', coerce=int, validators=[DataRequired()])
    target_quantity = FloatField('Target Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    production_date = StringField('Production Date', validators=[DataRequired()])  # Will be converted to date
    reason = TextAreaField('Reason for Partial Production')
    priority = SelectField('Priority',
                          choices=[
                              ('1', 'High Priority'),
                              ('2', 'Normal Priority'),
                              ('3', 'Low Priority')
                          ],
                          default='2')
    
    # Material availability override
    ignore_material_shortage = BooleanField('Proceed despite material shortage')
    use_substitute_materials = BooleanField('Use substitute materials if available')
    
    notes = TextAreaField('Additional Notes')
    submit = SubmitField('Plan Partial Production')
    
    def __init__(self, *args, **kwargs):
        super(PartialProductionForm, self).__init__(*args, **kwargs)
        
        # Populate BOM choices (only BOMs that allow partial production)
        try:
            from models import BOM
            boms = BOM.query.filter_by(is_active=True, allow_partial_production=True).order_by(BOM.bom_code).all()
            self.bom_id.choices = [(0, '-- Select BOM --')] + [(bom.id, f"{bom.bom_code} - {bom.product.name}") for bom in boms]
        except:
            self.bom_id.choices = [(0, '-- No BOMs Available --')]