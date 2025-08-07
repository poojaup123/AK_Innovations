from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, FloatField, IntegerField, DateField, TimeField, BooleanField, SelectMultipleField, ValidationError, DateTimeField
from wtforms.validators import DataRequired, Length, Email, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget
from models import User, Item, Supplier, QualityIssue, Production, PurchaseOrder, JobWork, ItemType, DailyJobWorkEntry, Employee
from models.uom import UnitOfMeasure
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired()])

class ItemForm(FlaskForm):
    code = StringField('Item Code', validators=[DataRequired(), Length(max=50)])
    name = StringField('Item Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    unit_of_measure = SelectField('Unit of Measure', 
                                choices=[],  # Will be populated dynamically
                                validators=[DataRequired()])
    hsn_code = StringField('HSN Code', validators=[Length(max=20)])
    gst_rate = FloatField('GST Rate (%)', validators=[NumberRange(min=0, max=100)], default=18.0)
    current_stock = FloatField('Current Stock', validators=[NumberRange(min=0)], default=0.0)
    minimum_stock = FloatField('Minimum Stock', validators=[NumberRange(min=0)], default=0.0)
    unit_price = FloatField('Unit Price', validators=[NumberRange(min=0)], default=0.0)
    unit_weight = FloatField('Unit Weight (kg)', validators=[NumberRange(min=0)], default=0.0)
    item_type = SelectField('Item Type', 
                          choices=[],  # Will be populated dynamically
                          validators=[DataRequired()])
    
    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        # Populate UOM choices from database
        try:
            # Ensure default UOMs exist
            UnitOfMeasure.ensure_default_units()
            
            # Get UOM choices using the model method
            self.unit_of_measure.choices = UnitOfMeasure.get_choices()
            
            # Add fallback options if no units in database
            if not self.unit_of_measure.choices:
                self.unit_of_measure.choices = [
                    ('Pcs', 'Pieces (Pcs) - Count'), 
                    ('Kg', 'Kilogram (Kg) - Weight'), 
                    ('M', 'Meter (M) - Length'),
                    ('L', 'Liter (L) - Volume')
                ]
        except Exception as e:
            # Fallback choices if database error
            print(f"UOM loading error: {e}")
            self.unit_of_measure.choices = [
                ('Pcs', 'Pieces (Pcs) - Count'), 
                ('Kg', 'Kilogram (Kg) - Weight'), 
                ('M', 'Meter (M) - Length'),
                ('L', 'Liter (L) - Volume')
            ]
        
        # Populate Item Type choices from database
        try:
            # Ensure default item types exist
            ItemType.get_default_types()
            
            # Get item type choices using the model method
            self.item_type.choices = ItemType.get_choices()
            
            # Add fallback options if no types in database
            if not self.item_type.choices:
                self.item_type.choices = [
                    ('1', 'Material'), 
                    ('2', 'Product'), 
                    ('3', 'Consumable'),
                    ('4', 'Tool'),
                    ('5', 'Spare Part'),
                    ('6', 'Packaging')
                ]
        except Exception as e:
            # Fallback choices if database error
            print(f"ItemType loading error: {e}")
            self.item_type.choices = [
                ('1', 'Material'), 
                ('2', 'Product'), 
                ('3', 'Consumable'),
                ('4', 'Tool'),
                ('5', 'Spare Part'),
                ('6', 'Packaging')
            ]

class SupplierForm(FlaskForm):
    # Basic Information
    name = StringField('Business Partner Name', validators=[DataRequired(), Length(max=200)], 
                      render_kw={"placeholder": "A.K. Metals"})
    contact_person = StringField('Contact Person', validators=[Length(max=100)], 
                                render_kw={"placeholder": "Mr. Rahul Kumar"})
    phone = StringField('Mobile Number', validators=[Length(max=20)], 
                       render_kw={"placeholder": "9876543210"})
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)], 
                       render_kw={"placeholder": "info@akmetals.com"})
    
    # Partner Type
    partner_type = SelectField('Partner Type', 
                              choices=[('supplier', 'Supplier'), ('customer', 'Customer'), ('vendor', 'Vendor'), ('transporter', 'Transporter'), ('both', 'Both Supplier & Customer')],
                              validators=[DataRequired()], default='supplier')
    
    # Compliance Information
    gst_number = StringField('GST Number', validators=[Length(max=50)], 
                            render_kw={"placeholder": "29ABCDE1234F1Z9"})
    pan_number = StringField('PAN Number', validators=[Optional(), Length(max=20)], 
                            render_kw={"placeholder": "ABCDE1234F"})
    
    # Address Information
    address = TextAreaField('Address', render_kw={"placeholder": "123, Industrial Area, Delhi"})
    city = StringField('City', validators=[Length(max=100)], 
                      render_kw={"placeholder": "Delhi"})
    state = StringField('State', validators=[Length(max=100)], 
                       render_kw={"placeholder": "Delhi"})
    pin_code = StringField('Pin Code', validators=[Length(max=10)], 
                          render_kw={"placeholder": "110001"})
    
    # Banking Information (Optional)
    account_number = StringField('Account Number', validators=[Optional(), Length(max=50)], 
                                render_kw={"placeholder": "123456789012"})
    bank_name = StringField('Bank Name', validators=[Optional(), Length(max=200)], 
                           render_kw={"placeholder": "State Bank of India"})
    ifsc_code = StringField('IFSC Code', validators=[Optional(), Length(max=20)], 
                           render_kw={"placeholder": "SBIN0001234"})
    
    # Transportation Specific (for transporters)
    freight_rate_per_unit = FloatField('Freight Rate (₹)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    freight_unit_type = SelectField('Freight Rate Type', validators=[Optional()],
                                   choices=[
                                       ('per_km', 'Per Kilometer'),
                                       ('per_kg', 'Per Kilogram'),
                                       ('per_box', 'Per Box'),
                                       ('per_carton', 'Per Carton'),
                                       ('per_ton', 'Per Ton')
                                   ],
                                   default='per_km')
    
    # Additional Information
    remarks = TextAreaField('Remarks', render_kw={"placeholder": "Preferred for steel items"})
    is_active = BooleanField('Active', default=True)

# Create alias for backward compatibility
BusinessPartnerForm = SupplierForm

class PurchaseOrderForm(FlaskForm):
    po_number = StringField('PO Number', validators=[DataRequired(), Length(max=50)])
    supplier_id = SelectField('Supplier', validators=[DataRequired()], coerce=int)
    po_date = DateField('PO Date', validators=[DataRequired()])
    delivery_date = DateField('Expected Delivery Date')
    payment_terms = StringField('Payment Terms', validators=[Length(max=100)])
    freight_terms = StringField('Freight Terms', validators=[Length(max=100)])
    validity_months = IntegerField('Validity (Months)', validators=[Optional(), NumberRange(min=1, max=12)])
    prepared_by = StringField('Prepared By', validators=[Length(max=100)])
    verified_by = StringField('Verified By', validators=[Length(max=100)])
    approved_by = StringField('Approved By', validators=[Length(max=100)])
    delivery_notes = TextAreaField('Delivery Notes')
    status = SelectField('Status', choices=[('draft', 'Draft'), ('open', 'Open'), ('partial', 'Partially Received'), ('closed', 'Closed'), ('cancelled', 'Cancelled')], default='open')
    notes = TextAreaField('Notes')
    
    def __init__(self, *args, **kwargs):
        super(PurchaseOrderForm, self).__init__(*args, **kwargs)
        # Include suppliers and vendors for purchase orders
        suppliers = Supplier.query.filter(Supplier.partner_type.in_(['supplier', 'vendor', 'both'])).all()
        self.supplier_id.choices = [(0, 'Select Supplier')] + [(s.id, s.name) for s in suppliers]

class PurchaseOrderItemForm(FlaskForm):
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    quantity_ordered = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    uom = SelectField('Unit of Measure', validators=[DataRequired()], coerce=str)
    unit_price = FloatField('Unit Price', validators=[DataRequired(), NumberRange(min=0)])
    material_destination = SelectField('Material Destination', 
                                     validators=[DataRequired()], 
                                     choices=[
                                         ('raw_material', 'Raw Material'),
                                         ('finished', 'Finished Goods'),
                                         ('wip', 'Work in Progress'),
                                         ('scrap', 'Scrap/Waste')
                                     ],
                                     default='raw_material')
    
    def __init__(self, *args, **kwargs):
        super(PurchaseOrderItemForm, self).__init__(*args, **kwargs)
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.uom.choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.uom.choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]

class SalesOrderForm(FlaskForm):
    so_number = StringField('SO Number', validators=[DataRequired(), Length(max=50)])
    customer_id = SelectField('Customer', validators=[DataRequired()], coerce=int)
    order_date = DateField('Order Date', validators=[DataRequired()])
    delivery_date = DateField('Expected Delivery Date')
    payment_terms = StringField('Payment Terms', validators=[Length(max=100)])
    freight_terms = StringField('Freight Terms', validators=[Length(max=100)])
    validity_months = IntegerField('Validity (Months)', validators=[Optional(), NumberRange(min=1, max=12)])
    prepared_by = StringField('Prepared By', validators=[Length(max=100)])
    verified_by = StringField('Verified By', validators=[Length(max=100)])
    approved_by = StringField('Approved By', validators=[Length(max=100)])
    delivery_notes = TextAreaField('Delivery Notes')
    status = SelectField('Status', choices=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')], default='draft')
    notes = TextAreaField('Notes')
    
    def __init__(self, *args, **kwargs):
        super(SalesOrderForm, self).__init__(*args, **kwargs)
        # Get suppliers who are customers (partner_type is 'customer' or 'both')
        customers = Supplier.query.filter(Supplier.partner_type.in_(['customer', 'both'])).all()
        self.customer_id.choices = [(0, 'Select Customer')] + [(c.id, c.name) for c in customers]

class SalesOrderItemForm(FlaskForm):
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    quantity_ordered = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    uom = SelectField('Unit of Measure', validators=[DataRequired()], coerce=str)
    unit_price = FloatField('Unit Price', validators=[DataRequired(), NumberRange(min=0)])
    
    def __init__(self, *args, **kwargs):
        super(SalesOrderItemForm, self).__init__(*args, **kwargs)
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.uom.choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.uom.choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]

class EmployeeForm(FlaskForm):
    employee_code = StringField('Employee Code', validators=[DataRequired(), Length(max=50)])
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    designation = StringField('Designation', validators=[Length(max=100)])
    department = SelectField('Department',
                            validators=[Optional()],
                            coerce=str)
    
    def __init__(self, *args, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)
        # Populate department choices from database
        try:
            from models.department import Department
            Department.get_default_departments()  # Ensure default departments exist
            self.department.choices = Department.get_choices()
        except Exception:
            # Fallback choices if database error
            self.department.choices = [
                ('', 'Select Department'),
                ('production', 'Production'),
                ('assembly', 'Assembly'),
                ('quality_control', 'Quality Control'),
                ('finishing', 'Finishing'),
                ('packaging', 'Packaging'),
                ('maintenance', 'Maintenance'),
                ('research_development', 'Research & Development'),
                ('administration', 'Administration'),
                ('sales_marketing', 'Sales & Marketing'),
                ('accounts_finance', 'Accounts & Finance'),
                ('human_resources', 'Human Resources'),
                ('stores_inventory', 'Stores & Inventory')
            ]
    salary_type = SelectField('Salary Type', 
                            choices=[('daily', 'Daily'), ('monthly', 'Monthly'), ('piece_rate', 'Piece Rate')],
                            validators=[DataRequired()])
    rate = FloatField('Rate', validators=[DataRequired(), NumberRange(min=0)])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address')
    joining_date = DateField('Joining Date', validators=[DataRequired()])
    salary = FloatField('Salary', validators=[Optional(), NumberRange(min=0)])
    is_active = BooleanField('Active', default=True)
    documents = FileField('Upload Documents', 
                         validators=[FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 
                                               'Only PDF, Images, and Word documents are allowed!')],
                         render_kw={'multiple': True, 'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'})

class JobWorkForm(FlaskForm):
    """Redesigned Job Work Form according to specification with BOM/Manual support, Process routing, and GRN integration"""
    
    # [1] Job Work Type & Basic Info
    job_work_type = SelectField('Job Work Type', 
                               validators=[DataRequired()], 
                               choices=[('bom_based', 'BOM-Based'), ('manual', 'Manual')],
                               default='manual')
    bom_id = SelectField('Select BOM', validators=[Optional()], coerce=int)
    job_title = StringField('Job Work Title', validators=[DataRequired(), Length(max=100)],
                           render_kw={'placeholder': 'e.g., JW-008 – Base Plate Work'})
    work_type = SelectField('Work Type',
                          validators=[DataRequired()],
                          choices=[('in_house', 'In-house'), ('vendor', 'Vendor'), ('machine', 'Machine')],
                          default='in_house')
    assigned_to = SelectField('Assigned To', validators=[DataRequired()], coerce=str)
    send_date = DateField('Send Date', validators=[DataRequired()], default=datetime.utcnow().date())
    expected_return = DateField('Expected Return', validators=[Optional()])
    
    # [2] Input Material & Issuance (will be auto-filled from BOM or manual selection)
    input_material_id = SelectField('Input Material', validators=[DataRequired()], coerce=int)
    batch_id = SelectField('Select Batch', validators=[Optional()], coerce=int)
    available_stock = FloatField('Available Stock', render_kw={'readonly': True})
    batch_available = FloatField('Batch Available', render_kw={'readonly': True})
    quantity_to_issue = FloatField('Quantity to Issue', validators=[DataRequired(), NumberRange(min=0)])
    input_uom = SelectField('UOM', validators=[Optional()], coerce=str)
    store_location = SelectField('Store', 
                               choices=[('raw_store', 'Raw Store'), ('wip_store', 'WIP Store'), ('finished_store', 'Finished Store')],
                               default='raw_store')
    
    # Batch tracking options
    enable_batch_tracking = BooleanField('Enable Batch Tracking', default=True)
    create_output_batch = BooleanField('Create Output Batch', default=True)
    output_batch_prefix = StringField('Output Batch Prefix', validators=[Optional(), Length(max=20)],
                                    render_kw={'placeholder': 'AUTO-GENERATED'})
    
    # [5] Optional Notes & Attachments
    remarks = TextAreaField('Remarks / Instructions', 
                          render_kw={'placeholder': 'Priority job. Ensure QC report.', 'rows': 3})
    
    # Legacy fields for compatibility
    job_number = StringField('Job Number', render_kw={'readonly': True})
    
    def __init__(self, *args, **kwargs):
        super(JobWorkForm, self).__init__(*args, **kwargs)
        
        # Populate BOM choices
        try:
            from models import BOM
            boms = BOM.query.filter_by(is_active=True).order_by(BOM.bom_code).all()
            self.bom_id.choices = [(0, 'Select BOM')] + [(b.id, f"{b.bom_code} - {b.product.name if b.product else 'No Product'}") for b in boms]
        except Exception:
            self.bom_id.choices = [(0, 'Select BOM')]
        
        # Populate assigned to choices (suppliers/vendors + departments)
        assigned_choices = [('', 'Select Assignment')]
        try:
            # Add suppliers/vendors for outsourced work - use actual vendor name as value for easier rate lookup
            suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
            for supplier in suppliers:
                # Use actual supplier name as value (this will be used for rate lookup)
                assigned_choices.append((supplier.name, f"🏢 {supplier.name}"))
            
            # Add departments for in-house work
            from models.department import Department
            departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
            for dept in departments:
                assigned_choices.append((f"dept_{dept.code}", f"🏭 {dept.name}"))
        except Exception:
            pass
        
        self.assigned_to.choices = assigned_choices
        
        # Populate input material choices
        items = Item.query.order_by(Item.name).all()
        self.input_material_id.choices = [(0, 'Select Material')] + [(i.id, f"{i.code} - {i.name}") for i in items]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.input_uom.choices = uom_choices
        except Exception:
            self.input_uom.choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('sheet', 'Sheet')]
        
        # Initialize batch choices (will be populated via AJAX based on selected material)
        self.batch_id.choices = [(0, 'Select Material First')]

class JobWorkProcessRowForm(FlaskForm):
    """Individual row in the process routing table"""
    selected = BooleanField('Include', default=True)
    sequence = IntegerField('Seq', validators=[DataRequired(), NumberRange(min=1)])
    process_name = SelectField('Process', 
                              validators=[DataRequired()],
                              choices=[('cutting', 'Cutting'), ('welding', 'Welding'), 
                                     ('powder_coating', 'Powder Coating'), ('bending', 'Bending'),
                                     ('assembly', 'Assembly'), ('machining', 'Machining'),
                                     ('zinc_plating', 'Zinc Plating'), ('painting', 'Painting')])
    output_product_id = SelectField('Output Product', validators=[DataRequired()], coerce=int)
    quantity = IntegerField('Qty', validators=[DataRequired(), NumberRange(min=1)])
    uom = SelectField('UOM', validators=[DataRequired()], coerce=str)
    rate_per_unit = FloatField('Rate (₹/unit)', validators=[NumberRange(min=0)], default=0.0)
    quality_check = BooleanField('QC')
    scrap_percent = FloatField('Scrap %', validators=[NumberRange(min=0, max=100)], default=0.0)
    notes = StringField('Notes', render_kw={'placeholder': 'e.g., Use laser cutter'})
    
    def __init__(self, *args, **kwargs):
        super(JobWorkProcessRowForm, self).__init__(*args, **kwargs)
        
        # Populate output product choices
        items = Item.query.order_by(Item.name).all()
        self.output_product_id.choices = [(0, 'Select Product')] + [(i.id, f"{i.code} - {i.name}") for i in items]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.uom.choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.uom.choices = [('', 'Select Unit'), ('piece', 'Piece'), ('kg', 'Kilogram')]

class DailyJobWorkForm(FlaskForm):
    """Simplified form for daily job work entry by workers"""
    worker_name = SelectField('Worker Name', validators=[DataRequired()], coerce=str)
    job_work_id = SelectField('Job Work Order', validators=[DataRequired()], coerce=int)
    work_date = DateField('Work Date', validators=[DataRequired()], default=datetime.utcnow().date())
    hours_worked = FloatField('Hours Worked', validators=[DataRequired(), NumberRange(min=0.1, max=24)],
                             render_kw={'placeholder': 'Hours spent on this job work'})
    quantity_completed = FloatField('Quantity Completed', validators=[DataRequired(), NumberRange(min=0)],
                                   render_kw={'placeholder': 'Units completed today'})
    completed_uom = SelectField('Completed Unit', validators=[DataRequired()], coerce=str)
    scrap_quantity = FloatField('Scrap Quantity', validators=[Optional(), NumberRange(min=0)],
                               render_kw={'placeholder': 'Scrap/waste quantity today'})
    scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    quality_status = SelectField('Quality Status', 
                                validators=[DataRequired()],
                                choices=[('good', 'Good Quality'),
                                       ('needs_rework', 'Needs Rework'),
                                       ('defective', 'Defective')],
                                default='good')
    process_stage = SelectField('Process Stage',
                               validators=[DataRequired()],
                               choices=[('started', 'Started'),
                                      ('in_progress', 'In Progress'),
                                      ('completed', 'Completed'),
                                      ('on_hold', 'On Hold')],
                               default='in_progress')
    
    # Inspection fields
    inspected_quantity = FloatField('Inspected Quantity', validators=[Optional(), NumberRange(min=0)],
                                   render_kw={'placeholder': 'Quantity inspected for quality'})
    inspected_uom = SelectField('Inspected Unit', validators=[Optional()], coerce=str)
    passed_quantity = FloatField('Passed/Good Quantity', validators=[Optional(), NumberRange(min=0)],
                                render_kw={'placeholder': 'Quantity that passed inspection'})
    passed_uom = SelectField('Passed Unit', validators=[Optional()], coerce=str)
    rejected_quantity = FloatField('Rejected Quantity', validators=[Optional(), NumberRange(min=0)],
                                  render_kw={'placeholder': 'Quantity rejected in inspection', 'readonly': True})
    rejected_uom = SelectField('Rejected Unit', validators=[Optional()], coerce=str)
    rejection_reasons = TextAreaField('Rejection Reasons', 
                                     render_kw={'rows': 3, 'placeholder': 'e.g., Scratches, Dents, Corrosion, Quality issues, etc.'})
    
    notes = TextAreaField('Work Notes', 
                         render_kw={'rows': 3, 'placeholder': 'Any issues, observations, or comments about today\'s work'})
    submit = SubmitField('Log Daily Work')
    
    def __init__(self, *args, **kwargs):
        super(DailyJobWorkForm, self).__init__(*args, **kwargs)
        
        # Load active employees for worker selection
        active_employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        self.worker_name.choices = [('', 'Select Worker')] + [
            (emp.name, f"{emp.name} ({emp.employee_code}) - {emp.designation or 'Worker'}")
            for emp in active_employees
        ]
        
        # Only show active in-house job works that are in progress
        active_jobs = JobWork.query.filter(
            JobWork.status.in_(['sent', 'partial_received']),
            JobWork.work_type == 'in_house'
        ).order_by(JobWork.job_number).all()
        self.job_work_id.choices = [(0, 'Select In-House Job Work')] + [
            (job.id, f"{job.job_number} - {job.item.name} ({job.process}) - {job.department.replace('_', ' ').title()}") 
            for job in active_jobs
        ]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.completed_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
            self.inspected_uom.choices = uom_choices
            self.passed_uom.choices = uom_choices
            self.rejected_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
            self.inspected_uom.choices = uom_choices
            self.passed_uom.choices = uom_choices
            self.rejected_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.completed_uom.choices = fallback_choices
            self.scrap_uom.choices = fallback_choices
            self.inspected_uom.choices = fallback_choices
            self.passed_uom.choices = fallback_choices
            self.rejected_uom.choices = fallback_choices

class JobWorkQuantityUpdateForm(FlaskForm):
    quantity_received = FloatField('Quantity Received', validators=[DataRequired(), NumberRange(min=0)])
    received_uom = SelectField('Received Unit', validators=[DataRequired()], coerce=str)
    received_date = DateField('Received Date', validators=[DataRequired()])
    notes = TextAreaField('Notes')
    
    def __init__(self, *args, **kwargs):
        super(JobWorkQuantityUpdateForm, self).__init__(*args, **kwargs)
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.received_uom.choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.received_uom.choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]

class JobWorkTeamAssignmentForm(FlaskForm):
    """Form for assigning job work to team members"""
    employee_id = SelectField('Select Employee', 
                             validators=[DataRequired()],
                             coerce=int,
                             render_kw={'class': 'form-select'})
    assigned_quantity = FloatField('Assigned Quantity', 
                                  validators=[DataRequired(), NumberRange(min=0.1)],
                                  render_kw={'placeholder': 'Quantity to assign to this member'})
    assigned_uom = SelectField('Assigned Unit', validators=[DataRequired()], coerce=str)
    estimated_hours = FloatField('Estimated Hours', 
                                validators=[Optional(), NumberRange(min=0)],
                                render_kw={'placeholder': 'Expected hours for this assignment'})
    member_role = StringField('Role/Responsibility', 
                             validators=[Optional(), Length(max=50)],
                             render_kw={'placeholder': 'e.g., Lead, Helper, Quality Check'})
    start_date = DateField('Start Date', 
                          validators=[Optional()],
                          default=datetime.utcnow().date())
    target_completion = DateField('Target Completion', 
                                 validators=[Optional()])
    notes = TextAreaField('Assignment Notes',
                         render_kw={'rows': 3, 'placeholder': 'Any specific instructions or notes for this team member'})
    submit = SubmitField('Assign to Team')
    
    def __init__(self, *args, **kwargs):
        super(JobWorkTeamAssignmentForm, self).__init__(*args, **kwargs)
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.assigned_uom.choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.assigned_uom.choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]

class ProductionForm(FlaskForm):
    production_number = StringField('Production Number', validators=[DataRequired(), Length(max=50)])
    item_id = SelectField('Item to Produce', validators=[DataRequired()], coerce=int)
    quantity_planned = FloatField('Planned Quantity', validators=[DataRequired(), NumberRange(min=0)])
    planned_uom = SelectField('Planned Unit', validators=[DataRequired()], coerce=str)
    quantity_produced = FloatField('Produced Quantity', validators=[NumberRange(min=0)], default=0.0)
    produced_uom = SelectField('Produced Unit', validators=[Optional()], coerce=str)
    quantity_good = FloatField('Good Quality Quantity', validators=[NumberRange(min=0)], default=0.0)
    good_uom = SelectField('Good Unit', validators=[Optional()], coerce=str)
    quantity_damaged = FloatField('Damaged/Defective Quantity', validators=[NumberRange(min=0)], default=0.0)
    damaged_uom = SelectField('Damaged Unit', validators=[Optional()], coerce=str)
    scrap_quantity = FloatField('Scrap Generated (Production waste)', validators=[NumberRange(min=0)], default=0.0)
    scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    production_date = DateField('Production Date', validators=[DataRequired()])
    status = SelectField('Status', choices=[('planned', 'Planned'), ('in_progress', 'In Progress'), ('completed', 'Completed')], default='planned')
    notes = TextAreaField('Notes')
    
    def __init__(self, *args, **kwargs):
        super(ProductionForm, self).__init__(*args, **kwargs)
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.planned_uom.choices = uom_choices
            self.produced_uom.choices = uom_choices
            self.good_uom.choices = uom_choices
            self.damaged_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.planned_uom.choices = fallback_choices
            self.produced_uom.choices = fallback_choices
            self.good_uom.choices = fallback_choices
            self.damaged_uom.choices = fallback_choices
            self.scrap_uom.choices = fallback_choices

class QualityIssueForm(FlaskForm):
    issue_number = StringField('Issue Number', validators=[DataRequired(), Length(max=50)])
    production_id = SelectField('Production Order', validators=[Optional()], coerce=int)
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    issue_type = SelectField('Issue Type', 
                           choices=[('damage', 'Damage'), ('malfunction', 'Malfunction'), 
                                  ('defect', 'Defect'), ('contamination', 'Contamination'),
                                  ('dimension_error', 'Dimension Error'), ('material_defect', 'Material Defect')],
                           validators=[DataRequired()])
    severity = SelectField('Severity', 
                         choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                         validators=[DataRequired()])
    quantity_affected = FloatField('Quantity Affected', validators=[DataRequired(), NumberRange(min=0)])
    affected_uom = SelectField('Affected Unit', validators=[DataRequired()], coerce=str)
    scrap_quantity = FloatField('Additional Scrap Generated (Due to quality issue)', validators=[NumberRange(min=0)], default=0.0)
    quality_scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    description = TextAreaField('Description', validators=[DataRequired()])
    root_cause = TextAreaField('Root Cause Analysis')
    corrective_action = TextAreaField('Corrective Action')
    preventive_action = TextAreaField('Preventive Action')
    status = SelectField('Status', 
                       choices=[('open', 'Open'), ('investigating', 'Investigating'), 
                              ('resolved', 'Resolved'), ('closed', 'Closed')], 
                       default='open')
    assigned_to = SelectField('Assigned To', validators=[Optional()], coerce=int)
    cost_impact = FloatField('Cost Impact', validators=[NumberRange(min=0)], default=0.0)
    
    def __init__(self, *args, **kwargs):
        super(QualityIssueForm, self).__init__(*args, **kwargs)
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
        self.production_id.choices = [(0, 'Not linked to production')] + [(p.id, f"{p.production_number}") for p in Production.query.all()]
        self.assigned_to.choices = [(0, 'Unassigned')] + [(u.id, u.username) for u in User.query.all()]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.affected_uom.choices = uom_choices
            self.quality_scrap_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.affected_uom.choices = fallback_choices
            self.quality_scrap_uom.choices = fallback_choices

class QualityControlLogForm(FlaskForm):
    production_id = SelectField('Production Order', validators=[DataRequired()], coerce=int)
    batch_number = StringField('Batch Number', validators=[Length(max=50)])
    total_inspected = FloatField('Total Inspected', validators=[DataRequired(), NumberRange(min=0)])
    inspected_uom = SelectField('Inspected Unit', validators=[DataRequired()], coerce=str)
    passed_quantity = FloatField('Passed Quantity', validators=[DataRequired(), NumberRange(min=0)])
    passed_uom = SelectField('Passed Unit', validators=[DataRequired()], coerce=str)
    failed_quantity = FloatField('Failed Quantity', validators=[DataRequired(), NumberRange(min=0)])
    failed_uom = SelectField('Failed Unit', validators=[DataRequired()], coerce=str)
    scrap_quantity = FloatField('Scrap Generated (During inspection)', validators=[NumberRange(min=0)], default=0.0)
    scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    inspection_notes = TextAreaField('Inspection Notes')
    
    def __init__(self, *args, **kwargs):
        super(QualityControlLogForm, self).__init__(*args, **kwargs)
        self.production_id.choices = [(0, 'Select Production Order')] + [(p.id, f"{p.production_number} - {p.produced_item.name}") for p in Production.query.all()]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.inspected_uom.choices = uom_choices
            self.passed_uom.choices = uom_choices
            self.failed_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.inspected_uom.choices = fallback_choices
            self.passed_uom.choices = fallback_choices
            self.failed_uom.choices = fallback_choices
            self.scrap_uom.choices = fallback_choices

# ... rest of existing forms remain the same

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class NotificationRecipientForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    
    notification_types = MultiCheckboxField(
        'Notification Types',
        choices=[('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')],
        validators=[DataRequired()]
    )
    
    event_types = MultiCheckboxField(
        'Event Types',
        choices=[
            ('low_stock', 'Low Stock Alerts'),
            ('order_update', 'Order Updates'),
            ('production_complete', 'Production Complete'),
            ('quality_issue', 'Quality Issues'),
            ('system_alert', 'System Alerts')
        ],
        validators=[DataRequired()]
    )
    
    is_active = BooleanField('Active', default=True)
    
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        
        # Ensure at least email or phone is provided
        if not self.email.data and not self.phone.data:
            self.email.errors.append('Either email or phone must be provided.')
            self.phone.errors.append('Either email or phone must be provided.')
            return False
        
        # Validate notification types match available contact methods
        if 'email' in self.notification_types.data and not self.email.data:
            self.notification_types.errors.append('Email is required for email notifications.')
            return False
        
        if ('sms' in self.notification_types.data or 'whatsapp' in self.notification_types.data) and not self.phone.data:
            self.notification_types.errors.append('Phone is required for SMS/WhatsApp notifications.')
            return False
        
        return True

class NotificationSettingsForm(FlaskForm):
    # Email settings
    email_enabled = BooleanField('Enable Email Notifications', default=True)
    sendgrid_api_key = StringField('SendGrid API Key', validators=[Optional(), Length(max=255)])
    sender_email = StringField('Sender Email', validators=[Optional(), Email(), Length(max=120)], default='noreply@akfactory.com')
    sender_name = StringField('Sender Name', validators=[Optional(), Length(max=100)], default='AK Innovations Factory')
    
    # SMS/WhatsApp settings
    sms_enabled = BooleanField('Enable SMS Notifications', default=True)
    whatsapp_enabled = BooleanField('Enable WhatsApp Notifications', default=True)
    twilio_account_sid = StringField('Twilio Account SID', validators=[Optional(), Length(max=255)])
    twilio_auth_token = StringField('Twilio Auth Token', validators=[Optional(), Length(max=255)])
    twilio_phone_number = StringField('Twilio Phone Number', validators=[Optional(), Length(max=20)])
    
    # Notification preferences
    low_stock_notifications = BooleanField('Low Stock Alerts', default=True)
    order_status_notifications = BooleanField('Order Status Updates', default=True)
    production_notifications = BooleanField('Production Notifications', default=True)
    
    # Admin recipients
    admin_email = StringField('Admin Email', validators=[Optional(), Email(), Length(max=120)])
    admin_phone = StringField('Admin Phone', validators=[Optional(), Length(max=20)])
    
    submit = SubmitField('Save Settings')

class NotificationTestForm(FlaskForm):
    recipient_type = SelectField('Recipient Type', 
                               choices=[('sms', 'SMS'), ('email', 'Email'), ('whatsapp', 'WhatsApp')],
                               validators=[DataRequired()])
    recipient = StringField('Recipient', validators=[DataRequired()])
    message = TextAreaField('Test Message', validators=[DataRequired()])

class BOMForm(FlaskForm):
    # Basic BOM Information
    bom_code = StringField('BOM Code', validators=[Optional(), Length(max=50)], 
                          render_kw={"placeholder": "e.g., BOM-2025-001"})
    product_id = SelectField('Product', validators=[DataRequired()], coerce=int)
    output_uom_id = SelectField('Output UOM', validators=[Optional()], coerce=int)
    version = StringField('Version', validators=[Optional(), Length(max=20)], default='1.0')
    status = SelectField('Status', validators=[Optional()], 
                        choices=[('active', 'Active'), ('inactive', 'Inactive'), ('draft', 'Draft')], 
                        default='active')
    is_active = BooleanField('Active', default=True)  # Keep for backward compatibility
    output_quantity = FloatField('Output Quantity', validators=[Optional(), NumberRange(min=0.001)], default=1.0,
                                render_kw={"placeholder": "How many units this BOM produces (e.g., 400 pieces from 1 sheet)"})
    unit_weight = FloatField('Unit Weight', validators=[Optional(), NumberRange(min=0)], default=0.0,
                            render_kw={"placeholder": "Weight per unit for cost conversions (e.g., 2.5 kg/unit)"})
    unit_weight_uom = SelectField('Unit Weight UOM', validators=[Optional()], 
                                 choices=[('kg', 'Kilogram (kg)'), ('g', 'Gram (g)'), ('lbs', 'Pound (lbs)'), ('oz', 'Ounce (oz)')],
                                 default='kg')
    estimated_scrap_percent = FloatField('Overall Scrap %', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    scrap_quantity = FloatField('Expected Scrap Quantity per Unit', validators=[Optional(), NumberRange(min=0)], default=0.0,
                               render_kw={"placeholder": "Weight-based scrap expected per unit produced"})
    scrap_uom = SelectField('Scrap UOM', validators=[Optional()], choices=[], default='kg')
    scrap_value_recovery_percent = FloatField('Scrap Value Recovery %', validators=[Optional(), NumberRange(min=0, max=100)], default=15.0,
                                            render_kw={"placeholder": "Percentage of material value recoverable from scrap"})
    description = TextAreaField('BOM Description', render_kw={"rows": 3})
    remarks = TextAreaField('Remarks', render_kw={"rows": 2})
    
    # Labor and Overhead fields - All optional
    labor_cost_per_unit = FloatField('Labor Cost per Unit', validators=[Optional(), NumberRange(min=0)], default=0.0)
    labor_hours_per_unit = FloatField('Labor Hours per Unit', validators=[Optional(), NumberRange(min=0)], default=0.0)
    labor_rate_per_hour = FloatField('Labor Rate per Hour', validators=[Optional(), NumberRange(min=0)], default=0.0)
    overhead_cost_per_unit = FloatField('Fixed Overhead per Unit', validators=[Optional(), NumberRange(min=0)], default=0.0)
    overhead_percentage = FloatField('Overhead % (of material cost)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    freight_cost_per_unit = FloatField('Freight/Transportation Cost (Optional)', validators=[Optional(), NumberRange(min=0)], default=0.0)
    freight_unit_type = SelectField('Freight Unit Type', validators=[Optional()],
                                   choices=[
                                       ('per_piece', 'Per Piece/Unit'),
                                       ('per_kg', 'Per Kilogram'),
                                       ('per_box', 'Per Box'),
                                       ('per_carton', 'Per Carton'),
                                       ('per_ton', 'Per Ton')
                                   ],
                                   default='per_piece')
    markup_percentage = FloatField('Markup % (Profit Margin)', validators=[Optional(), NumberRange(min=0, max=500)], default=0.0)
    
    # Multi-level BOM fields
    parent_bom_id = SelectField('Parent BOM (if sub-BOM)', validators=[Optional()], coerce=int)
    bom_level = IntegerField('BOM Level', validators=[Optional(), NumberRange(min=0, max=10)], default=0,
                           render_kw={"readonly": True, "placeholder": "Auto-calculated based on parent BOM"})
    is_phantom_bom = BooleanField('Phantom BOM (not stocked)', default=False,
                                render_kw={"title": "Phantom BOMs are intermediate products that are not kept in inventory"})
    intermediate_product = BooleanField('Intermediate Product', default=False,
                                      render_kw={"title": "This BOM produces intermediate products used by other BOMs"})
    
    def __init__(self, *args, **kwargs):
        super(BOMForm, self).__init__(*args, **kwargs)
        # Allow any product type for BOM creation - no restrictions
        self.product_id.choices = [(0, 'Select Product')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.order_by(Item.name).all()]
        
        # Populate parent BOM choices (only top-level BOMs can be parents to avoid deep nesting)
        from models import BOM
        parent_boms = BOM.query.filter_by(is_active=True, bom_level=0).order_by(BOM.bom_code).all()
        self.parent_bom_id.choices = [(0, 'None (Top-level BOM)')] + [(b.id, f"{b.bom_code} - {b.product.name}") for b in parent_boms]
        
        # Populate UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.output_uom_id.choices = [(0, 'Select UOM')] + [(u.id, f"{u.name} ({u.symbol})") for u in uoms]
            # Populate scrap UOM choices (typically weight-based)
            weight_uoms = [u for u in uoms if u.category == 'Weight']
            scrap_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in weight_uoms]
            if not scrap_choices:
                scrap_choices = [('kg', 'Kilogram (kg)'), ('g', 'Gram (g)'), ('lbs', 'Pound (lbs)')]
            self.scrap_uom.choices = [('', 'Select Scrap Unit')] + scrap_choices
        except Exception:
            self.output_uom_id.choices = [(0, 'Select UOM')]
            self.scrap_uom.choices = [('', 'Select Scrap Unit'), ('kg', 'Kilogram (kg)'), ('g', 'Gram (g)')]

class BOMItemForm(FlaskForm):
    # New advanced fields
    material_id = SelectField('Material/Component', validators=[DataRequired()], coerce=int)
    qty_required = FloatField('Quantity Required', validators=[DataRequired(), NumberRange(min=0)])
    uom_id = SelectField('Unit of Measure', validators=[DataRequired()], coerce=int)
    unit_cost = FloatField('Unit Cost', validators=[Optional(), NumberRange(min=0)], default=0.0)
    scrap_percent = FloatField('Expected Scrap %', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    process_step = IntegerField('Process Step', validators=[Optional(), NumberRange(min=1)], default=1)
    process_name = StringField('Process Name', validators=[Optional(), Length(max=100)])
    is_critical = BooleanField('Critical Material', default=False)
    substitute_materials = StringField('Substitute Materials (comma-separated codes)')
    default_supplier_id = SelectField('Default Supplier', validators=[Optional()], coerce=int)
    remarks = TextAreaField('Remarks', render_kw={"rows": 2})
    
    # Legacy fields for backward compatibility
    item_id = SelectField('Material/Component (Legacy)', validators=[Optional()], coerce=int)
    quantity_required = FloatField('Quantity Required (Legacy)', validators=[Optional(), NumberRange(min=0)])
    unit = SelectField('Unit (Legacy)', validators=[Optional()], choices=[
        ('pcs', 'Pieces (pcs)'),
        ('kg', 'Kilograms (kg)'),
        ('g', 'Grams (g)'),
        ('nos', 'Numbers (nos)'),
        ('m', 'Meters (m)'),
        ('cm', 'Centimeters (cm)'),
        ('l', 'Liters (l)'),
        ('ml', 'Milliliters (ml)'),
        ('sqft', 'Square Feet (sq.ft)'),
        ('sqm', 'Square Meters (sq.m)')
    ], default='pcs')
    
    def __init__(self, *args, **kwargs):
        super(BOMItemForm, self).__init__(*args, **kwargs)
        
        # Populate material choices - all items can be BOM materials now
        items = Item.query.order_by(Item.name).all()
        material_choices = [(0, 'Select Material')] + [(i.id, f"{i.code} - {i.name}") for i in items]
        self.material_id.choices = material_choices
        self.item_id.choices = material_choices  # Legacy compatibility
        
        # Populate UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            self.uom_id.choices = [(0, 'Select UOM')] + [(u.id, f"{u.name} ({u.symbol})") for u in uoms]
        except Exception:
            self.uom_id.choices = [(0, 'Select UOM')]
        
        # Populate supplier choices
        try:
            suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
            self.default_supplier_id.choices = [(0, 'Select Supplier')] + [(s.id, s.name) for s in suppliers]
        except Exception:
            self.default_supplier_id.choices = [(0, 'Select Supplier')]

# New form for BOM Process routing
class BOMProcessForm(FlaskForm):
    step_number = IntegerField('Step Number', validators=[DataRequired(), NumberRange(min=1)])
    process_name = StringField('Process Name', validators=[DataRequired(), Length(max=100)], 
                              render_kw={"placeholder": "e.g., Cutting, Welding, Assembly"})
    process_code = StringField('Process Code', validators=[Length(max=20)], 
                              render_kw={"placeholder": "e.g., CUT, WELD, ASSY"})
    operation_description = TextAreaField('Operation Description', render_kw={"rows": 3})
    setup_time_minutes = FloatField('Setup Time (minutes)', validators=[NumberRange(min=0)], default=0.0)
    run_time_minutes = FloatField('Runtime per Unit (minutes)', validators=[NumberRange(min=0)], default=0.0)
    labor_rate_per_hour = FloatField('Labor Rate per Hour', validators=[NumberRange(min=0)], default=0.0)
    machine_id = SelectField('Machine/Tool', validators=[Optional()], coerce=int)
    department_id = SelectField('Department', validators=[Optional()], coerce=int)
    is_outsourced = BooleanField('Outsourced Process', default=False)
    vendor_id = SelectField('Outsourcing Vendor', validators=[Optional()], coerce=int)
    cost_per_unit = FloatField('Process Cost per Unit', validators=[NumberRange(min=0)], default=0.0)
    quality_check_required = BooleanField('Quality Check Required', default=False)
    estimated_scrap_percent = FloatField('Expected Scrap %', validators=[NumberRange(min=0, max=100)], default=0.0)
    parallel_processes = StringField('Parallel Processes (comma-separated)')
    predecessor_processes = StringField('Predecessor Processes (comma-separated)')
    
    # Process transformation fields
    input_product_id = SelectField('Input Product', validators=[Optional()], coerce=int)
    output_product_id = SelectField('Output Product', validators=[Optional()], coerce=int)
    input_quantity = FloatField('Input Quantity', validators=[NumberRange(min=0.001)], default=1.0)
    output_quantity = FloatField('Output Quantity', validators=[NumberRange(min=0.001)], default=1.0)
    transformation_type = SelectField('Transformation Type', validators=[Optional()],
                                    choices=[
                                        ('modify', 'Modify (same material, different form)'),
                                        ('convert', 'Convert (change material properties)'),
                                        ('assemble', 'Assemble (combine multiple inputs)'),
                                        ('disassemble', 'Disassemble (split into parts)'),
                                        ('coating', 'Coating/Surface Treatment'),
                                        ('machining', 'Machining/Shaping')
                                    ],
                                    default='modify')
    
    notes = TextAreaField('Notes', render_kw={"rows": 2})
    
    def __init__(self, *args, **kwargs):
        super(BOMProcessForm, self).__init__(*args, **kwargs)
        
        # Populate machine choices (items that are tools/machines)
        try:
            machines = Item.query.filter(Item.item_type.in_(['tool', 'machine'])).order_by(Item.name).all()
            self.machine_id.choices = [(0, 'Select Machine')] + [(m.id, f"{m.code} - {m.name}") for m in machines]
        except Exception:
            self.machine_id.choices = [(0, 'Select Machine')]
        
        # Populate department choices
        try:
            from models.department import Department
            departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
            self.department_id.choices = [(0, 'Select Department')] + [(d.id, d.name) for d in departments]
        except Exception:
            self.department_id.choices = [(0, 'Select Department')]
        
        # Populate vendor choices
        try:
            vendors = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
            self.vendor_id.choices = [(0, 'Select Vendor')] + [(v.id, v.name) for v in vendors]
        except Exception:
            self.vendor_id.choices = [(0, 'Select Vendor')]
        
        # Populate input and output product choices
        try:
            products = Item.query.order_by(Item.name).all()
            product_choices = [(0, 'Select Product')] + [(p.id, f"{p.code} - {p.name}") for p in products]
            self.input_product_id.choices = product_choices
            self.output_product_id.choices = product_choices
        except Exception:
            self.input_product_id.choices = [(0, 'Select Product')]
            self.output_product_id.choices = [(0, 'Select Product')]

class CompanySettingsForm(FlaskForm):
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=200)])
    address_line1 = StringField('Address Line 1', validators=[DataRequired(), Length(max=200)])
    address_line2 = StringField('Address Line 2', validators=[Optional(), Length(max=200)])
    city = StringField('City', validators=[DataRequired(), Length(max=100)])
    state = StringField('State', validators=[DataRequired(), Length(max=100)])
    pin_code = StringField('PIN Code', validators=[DataRequired(), Length(max=10)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    gst_number = StringField('GST Number', validators=[DataRequired(), Length(max=50)])
    arn_number = StringField('ARN Number', validators=[Optional(), Length(max=50)])
    website = StringField('Website', validators=[Optional(), Length(max=200)])

class MaterialInspectionForm(FlaskForm):
    purchase_order_id = SelectField('Purchase Order', coerce=int, validators=[Optional()])
    job_work_id = SelectField('Job Work', coerce=int, validators=[Optional()])
    item_id = SelectField('Item', coerce=int, validators=[DataRequired()])
    received_quantity = FloatField('Received Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    inspected_quantity = FloatField('Inspected Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    passed_quantity = FloatField('Passed/Good Quantity', validators=[DataRequired(), NumberRange(min=0)])
    rejected_quantity = FloatField('Rejected Quantity', validators=[Optional(), NumberRange(min=0)])
    rejection_reasons = TextAreaField('Rejection Reasons', validators=[Optional()],
                                    render_kw={"placeholder": "e.g., Scratches, Dents, Corrosion, Quality issues, etc."})
    inspection_notes = TextAreaField('Inspection Notes', validators=[Optional()],
                                   render_kw={"placeholder": "Additional inspection observations"})
    
    def __init__(self, *args, **kwargs):
        super(MaterialInspectionForm, self).__init__(*args, **kwargs)
        self.purchase_order_id.choices = [(0, 'Select Purchase Order')] + [(po.id, f"{po.po_number} - {po.supplier.name}") for po in PurchaseOrder.query.filter_by(inspection_status='pending').all()]
        self.job_work_id.choices = [(0, 'Select Job Work')] + [(jw.id, f"{jw.job_number} - {jw.customer_name}") for jw in JobWork.query.filter_by(inspection_status='pending').all()]
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]

class FactoryExpenseForm(FlaskForm):
    # Basic Details
    expense_date = DateField('Expense Date', validators=[DataRequired()], default=datetime.today)
    category = SelectField('Category', validators=[DataRequired()], 
                          choices=[
                              ('utilities', 'Utilities & Infrastructure'),
                              ('maintenance', 'Maintenance & Repairs'),
                              ('salary', 'Salaries & Benefits'),
                              ('materials', 'Raw Materials & Supplies'),
                              ('overhead', 'Factory Overhead'),
                              ('transport', 'Transportation & Logistics'),
                              ('others', 'Other Expenses')
                          ])
    subcategory = StringField('Subcategory', validators=[Optional(), Length(max=100)], 
                             render_kw={"placeholder": "e.g., Electricity, Water, Equipment Repair"})
    department = SelectField('Department', validators=[Optional()], coerce=str)
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=500)], 
                               render_kw={"placeholder": "Detailed description of the expense"})
    
    # Financial Details
    amount = FloatField('Amount (₹)', validators=[DataRequired(), NumberRange(min=0.01)], 
                       render_kw={"placeholder": "0.00"})
    tax_amount = FloatField('Tax Amount (₹)', validators=[Optional(), NumberRange(min=0)], default=0.0,
                           render_kw={"placeholder": "0.00"})
    payment_method = SelectField('Payment Method', validators=[Optional()],
                                choices=[
                                    ('', 'Select Payment Method'),
                                    ('cash', 'Cash'),
                                    ('bank_transfer', 'Bank Transfer'),
                                    ('cheque', 'Cheque'),
                                    ('upi', 'UPI'),
                                    ('card', 'Card Payment')
                                ])
    paid_by = StringField('Paid By', validators=[Optional(), Length(max=100)], 
                         render_kw={"placeholder": "Person/Entity who made the payment"})
    
    # Vendor Details (Optional)
    vendor_name = StringField('Vendor/Supplier Name', validators=[Optional(), Length(max=200)], 
                             render_kw={"placeholder": "Vendor or supplier name"})
    vendor_contact = StringField('Vendor Contact', validators=[Optional(), Length(max=100)], 
                                render_kw={"placeholder": "Phone/Email of vendor"})
    invoice_number = StringField('Invoice Number', validators=[Optional(), Length(max=100)], 
                                render_kw={"placeholder": "Invoice/Bill number"})
    invoice_date = DateField('Invoice Date', validators=[Optional()])
    
    # Recurring Support
    is_recurring = BooleanField('Recurring Expense', default=False)
    recurring_frequency = SelectField('Frequency', validators=[Optional()],
                                     choices=[
                                         ('', 'Select Frequency'),
                                         ('monthly', 'Monthly'),
                                         ('quarterly', 'Quarterly'),
                                         ('yearly', 'Yearly')
                                     ])
    
    # Additional Information
    notes = TextAreaField('Notes', validators=[Optional()], 
                         render_kw={"placeholder": "Additional notes or comments"})
    
    submit = SubmitField('Save Expense')
    
    def __init__(self, *args, **kwargs):
        super(FactoryExpenseForm, self).__init__(*args, **kwargs)
        # Populate department choices from database
        try:
            from models.department import Department
            Department.get_default_departments()  # Ensure default departments exist
            self.department.choices = Department.get_choices()
        except Exception:
            # Fallback choices if database error
            self.department.choices = [
                ('', 'Select Department'),
                ('production', 'Production'),
                ('assembly', 'Assembly'),
                ('quality_control', 'Quality Control'),
                ('finishing', 'Finishing'),
                ('packaging', 'Packaging'),
                ('maintenance', 'Maintenance'),
                ('administration', 'Administration'),
                ('accounts_finance', 'Accounts & Finance')
            ]

class SalaryRecordForm(FlaskForm):
    salary_number = StringField('Salary Number', validators=[DataRequired()], render_kw={'readonly': True})
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    pay_period_start = DateField('Pay Period Start', validators=[DataRequired()])
    pay_period_end = DateField('Pay Period End', validators=[DataRequired()])
    
    # Attendance-based calculation fields
    daily_rate = FloatField('Daily Rate', validators=[DataRequired(), NumberRange(min=0.01)], 
                           render_kw={'placeholder': 'Rate per working day'})
    expected_working_days = IntegerField('Expected Working Days', validators=[Optional()], 
                                       render_kw={'readonly': True, 'placeholder': 'Auto-calculated'})
    actual_days_worked = IntegerField('Actual Days Worked', validators=[Optional()], 
                                    render_kw={'readonly': True, 'placeholder': 'From attendance records'})
    basic_amount = FloatField('Basic Amount', validators=[Optional()], 
                             render_kw={'readonly': True, 'placeholder': 'Auto-calculated from days worked'})
    
    # Overtime and additional amounts
    overtime_hours = FloatField('Overtime Hours', validators=[Optional(), NumberRange(min=0)], default=0,
                               render_kw={'readonly': True, 'placeholder': 'From attendance records'})
    overtime_rate = FloatField('Overtime Rate per Hour', validators=[Optional(), NumberRange(min=0)], default=0)
    bonus_amount = FloatField('Bonus Amount', validators=[Optional(), NumberRange(min=0)], default=0)
    deduction_amount = FloatField('Other Deductions', validators=[Optional(), NumberRange(min=0)], default=0)
    advance_deduction = FloatField('Advance Deduction', validators=[Optional(), NumberRange(min=0)], default=0)
    payment_method = SelectField('Payment Method', 
                                choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('cheque', 'Cheque')])
    notes = TextAreaField('Notes', render_kw={'rows': 3})
    
    # Form buttons
    calculate_attendance = SubmitField('Calculate from Attendance', render_kw={'class': 'btn btn-info'})
    submit = SubmitField('Save Salary Record')
    
    def __init__(self, *args, **kwargs):
        super(SalaryRecordForm, self).__init__(*args, **kwargs)
        from models import Employee
        self.employee_id.choices = [(0, 'Select Employee')] + [
            (e.id, f"{e.name} ({e.employee_code})") 
            for e in Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        ]

class EmployeeAdvanceForm(FlaskForm):
    advance_number = StringField('Advance Number', validators=[DataRequired()], render_kw={'readonly': True})
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    amount = FloatField('Advance Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    reason = StringField('Reason for Advance', validators=[DataRequired(), Length(max=200)])
    advance_date = DateField('Advance Date', validators=[DataRequired()], default=datetime.utcnow().date())
    repayment_months = IntegerField('Repayment Months', validators=[DataRequired(), NumberRange(min=1, max=24)], default=1)
    payment_method = SelectField('Payment Method', 
                                choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('cheque', 'Cheque')])
    notes = TextAreaField('Notes', render_kw={'rows': 3})
    submit = SubmitField('Save Advance Request')
    
    def __init__(self, *args, **kwargs):
        super(EmployeeAdvanceForm, self).__init__(*args, **kwargs)
        from models import Employee
        self.employee_id.choices = [(0, 'Select Employee')] + [
            (e.id, f"{e.name} ({e.employee_code})") 
            for e in Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        ]

class AttendanceForm(FlaskForm):
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    attendance_date = DateField('Attendance Date', validators=[DataRequired()], default=datetime.utcnow().date())
    check_in_time = TimeField('Check-in Time')
    check_out_time = TimeField('Check-out Time')
    overtime_hours = FloatField('Overtime Hours', validators=[Optional(), NumberRange(min=0, max=24)], default=0.0)
    status = SelectField('Attendance Status', 
                        choices=[('present', 'Present'), 
                                ('absent', 'Absent'), 
                                ('late', 'Late'), 
                                ('half_day', 'Half Day'),
                                ('leave', 'On Leave')],
                        validators=[DataRequired()], default='present')
    leave_type = SelectField('Leave Type (if applicable)', 
                            choices=[('', 'Not Applicable'),
                                    ('sick', 'Sick Leave'), 
                                    ('casual', 'Casual Leave'), 
                                    ('personal', 'Personal Leave'),
                                    ('vacation', 'Vacation')],
                            validators=[Optional()])
    notes = TextAreaField('Notes', render_kw={'rows': 3})
    submit = SubmitField('Mark Attendance')
    
    def __init__(self, *args, **kwargs):
        super(AttendanceForm, self).__init__(*args, **kwargs)
        from models import Employee
        self.employee_id.choices = [(0, 'Select Employee')] + [
            (e.id, f"{e.name} ({e.employee_code})") 
            for e in Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        ]

class BulkAttendanceForm(FlaskForm):
    attendance_date = DateField('Attendance Date', validators=[DataRequired()], default=datetime.utcnow().date())
    submit = SubmitField('Mark All Present')

class JobWorkBatchReturnForm(FlaskForm):
    """Form for processing job work returns with batch tracking"""
    
    # Job Work Selection
    job_work_id = SelectField('Job Work', validators=[DataRequired()], coerce=int)
    batch_record_id = SelectField('Batch Record', validators=[DataRequired()], coerce=int)
    
    # Return Details
    return_date = DateField('Return Date', validators=[DataRequired()], default=datetime.utcnow().date())
    
    # Output Details
    output_item_id = SelectField('Output Product', validators=[DataRequired()], coerce=int)
    output_batch_code = StringField('Output Batch Code', validators=[DataRequired(), Length(max=50)])
    quantity_finished = FloatField('Finished Quantity', validators=[DataRequired(), NumberRange(min=0)])
    quantity_scrap = FloatField('Scrap Quantity', validators=[Optional(), NumberRange(min=0)], default=0.0)
    quantity_returned_unused = FloatField('Unused Material Returned', validators=[Optional(), NumberRange(min=0)], default=0.0)
    
    # Quality Control
    quality_status = SelectField('Quality Status',
                                choices=[('passed', 'Passed'), ('failed', 'Failed'), ('partial', 'Partial')],
                                validators=[DataRequired()], default='passed')
    qc_notes = TextAreaField('QC Notes', validators=[Optional(), Length(max=500)])
    
    # Output Batch Properties
    output_manufacture_date = DateField('Manufacture Date', validators=[Optional()], 
                                       default=datetime.utcnow().date())
    output_expiry_date = DateField('Expiry Date', validators=[Optional()])
    output_location = StringField('Storage Location', validators=[Optional(), Length(max=100)], 
                                 default='Default')
    
    # Return Notes
    return_notes = TextAreaField('Return Notes', validators=[Optional(), Length(max=500)])
    
    def __init__(self, *args, **kwargs):
        super(JobWorkBatchReturnForm, self).__init__(*args, **kwargs)
        
        # Populate job work choices (only those with issued batches)
        try:
            from models import JobWork
            from models.batch import JobWorkBatch
            issued_job_works = JobWork.query.join(JobWorkBatch).filter(
                JobWorkBatch.status == 'issued'
            ).distinct().all()
            self.job_work_id.choices = [(0, 'Select Job Work')] + [
                (jw.id, f"{jw.job_number} - {jw.customer_name}") 
                for jw in issued_job_works
            ]
        except Exception:
            self.job_work_id.choices = [(0, 'Select Job Work')]
        
        # Populate output item choices
        items = Item.query.order_by(Item.name).all()
        self.output_item_id.choices = [(0, 'Select Output Product')] + [
            (i.id, f"{i.code} - {i.name}") for i in items
        ]
        
        # Initialize batch record choices (will be populated via AJAX)
        self.batch_record_id.choices = [(0, 'Select Job Work First')]

class BatchInventoryForm(FlaskForm):
    """Form for creating/editing inventory batches"""
    
    # Item Selection
    item_id = SelectField('Item', coerce=int, validators=[DataRequired()])
    
    # Batch Details
    batch_number = StringField('Batch Number', validators=[DataRequired(), Length(max=50)])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    
    # Batch Metadata
    manufacture_date = DateField('Manufacture Date', validators=[Optional()])
    expiry_date = DateField('Expiry Date', validators=[Optional()])
    supplier_batch = StringField('Supplier Batch No.', validators=[Optional(), Length(max=50)])
    purchase_rate = FloatField('Purchase Rate', validators=[Optional(), NumberRange(min=0)])
    storage_location = StringField('Storage Location', validators=[Optional(), Length(max=100)], 
                                 default='Default')
    
    # Initial State
    initial_state = SelectField('Initial State', 
                               choices=[('raw', 'Raw Material'), ('finished', 'Finished Goods')],
                               default='raw', validators=[DataRequired()])
    
    # Source Information
    grn_id = SelectField('GRN Reference', coerce=int, validators=[Optional()])
    
    # Notes
    quality_notes = TextAreaField('Quality Notes', validators=[Optional(), Length(max=500)])
    
    def __init__(self, *args, **kwargs):
        super(BatchInventoryForm, self).__init__(*args, **kwargs)
        
        # Populate item choices
        items = Item.query.order_by(Item.name).all()
        self.item_id.choices = [(0, 'Select Item')] + [
            (i.id, f"{i.code} - {i.name}") for i in items
        ]
        
        # Populate GRN choices
        try:
            from models.grn import GRN
            grns = GRN.query.filter_by(status='approved').order_by(GRN.grn_number.desc()).all()
            self.grn_id.choices = [(0, 'No GRN Reference')] + [
                (grn.id, f"{grn.grn_number} - {grn.supplier.name if grn.supplier else 'Unknown'}") 
                for grn in grns
            ]
        except Exception:
            self.grn_id.choices = [(0, 'No GRN Reference')]