from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, FloatField, DateField, SelectField, TextAreaField, IntegerField, BooleanField, MultipleFileField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from wtforms.widgets import HiddenInput
from datetime import date


class GRNForm(FlaskForm):
    """Form for creating and editing GRN (Goods Receipt Note)"""
    
    # Basic GRN Information
    grn_number = StringField('GRN Number', validators=[DataRequired(), Length(max=50)])
    job_work_id = IntegerField('Job Work ID', validators=[Optional()], widget=HiddenInput())
    purchase_order_id = IntegerField('Purchase Order ID', validators=[Optional()], widget=HiddenInput())
    received_date = DateField('Received Date', validators=[DataRequired()], default=date.today)
    
    # Delivery Information
    delivery_note = StringField('Delivery Note Number', validators=[Optional(), Length(max=100)])
    transporter_name = StringField('Transporter Name', validators=[Optional(), Length(max=100)])
    vehicle_number = StringField('Vehicle Number', validators=[Optional(), Length(max=20)])
    
    # Quality Control
    inspection_required = BooleanField('Inspection Required', default=True)
    
    # Status - will be set automatically by system
    
    # Notes
    remarks = TextAreaField('Remarks', validators=[Optional()])
    
    # Document Upload
    supporting_documents = MultipleFileField('Supporting Documents', 
                                           validators=[FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'], 
                                                     'Only PDF, images, and office documents allowed!')])
    document_description = TextAreaField('Document Description', 
                                       validators=[Optional()],
                                       render_kw={'placeholder': 'Describe the uploaded documents (e.g., Delivery challan, Invoice, Quality certificate, etc.)'})


class GRNLineItemForm(FlaskForm):
    """Form for GRN line items"""
    
    # Hidden fields for identification
    grn_id = IntegerField('GRN ID', widget=HiddenInput())
    item_id = IntegerField('Item ID', validators=[DataRequired()], widget=HiddenInput())
    
    # Quantity fields
    quantity_received = FloatField('Quantity Received', 
                                 validators=[DataRequired(), NumberRange(min=0.01, message="Quantity must be greater than 0")])
    received_uom = SelectField('Received Unit', validators=[DataRequired()], coerce=str)
    quantity_passed = FloatField('Quantity Passed', 
                               validators=[Optional(), NumberRange(min=0, message="Quantity cannot be negative")],
                               default=0.0)
    passed_uom = SelectField('Passed Unit', validators=[Optional()], coerce=str)
    quantity_rejected = FloatField('Quantity Rejected', 
                                 validators=[Optional(), NumberRange(min=0, message="Quantity cannot be negative")],
                                 default=0.0)
    rejected_uom = SelectField('Rejected Unit', validators=[Optional()], coerce=str)
    
    # Scrap tracking
    scrap_quantity = FloatField('Scrap Quantity (Generated during receipt/inspection)', 
                               validators=[Optional(), NumberRange(min=0, message="Scrap quantity cannot be negative")],
                               default=0.0)
    scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    scrap_reasons = TextAreaField('Scrap Reasons', 
                                 render_kw={'rows': 2, 'placeholder': 'e.g., Material damage, Processing waste, Quality issues, etc.'})
    
    # Unit information
    unit_of_measure = StringField('Unit', validators=[Optional(), Length(max=20)])
    unit_weight = FloatField('Unit Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    
    def __init__(self, *args, **kwargs):
        super(GRNLineItemForm, self).__init__(*args, **kwargs)
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.received_uom.choices = uom_choices
            self.passed_uom.choices = uom_choices
            self.rejected_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.received_uom.choices = fallback_choices
            self.passed_uom.choices = fallback_choices
            self.rejected_uom.choices = fallback_choices
            self.scrap_uom.choices = fallback_choices
    
    # Quality control
    inspection_status = SelectField('Inspection Status', choices=[
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('rejected', 'Rejected'),
        ('partial', 'Partial')
    ], default='pending')
    
    rejection_reason = StringField('Rejection Reason', validators=[Optional(), Length(max=500)])
    quality_grade = SelectField('Quality Grade', choices=[
        ('', 'Not Graded'),
        ('A', 'Grade A'),
        ('B', 'Grade B'),
        ('C', 'Grade C'),
        ('Pass', 'Pass'),
        ('Fail', 'Fail')
    ])
    
    # Process information (for multi-process job works)
    process_name = StringField('Process Name', validators=[Optional(), Length(max=100)])
    process_stage = StringField('Process Stage', validators=[Optional(), Length(max=50)])
    

    
    # Tracking information
    batch_number = StringField('Batch Number', validators=[Optional(), Length(max=50)])
    serial_numbers = TextAreaField('Serial Numbers', validators=[Optional()],
                                 render_kw={'placeholder': 'Enter serial numbers separated by commas'})
    
    # Notes
    remarks = TextAreaField('Line Item Remarks', validators=[Optional()])


class QuickReceiveForm(FlaskForm):
    """Quick form for receiving materials from job work"""
    
    job_work_id = IntegerField('Job Work ID', validators=[DataRequired()], widget=HiddenInput())
    received_date = DateField('Received Date', validators=[DataRequired()], default=date.today)
    
    # Quick quantity fields
    quantity_received = FloatField('Quantity Received', 
                                 validators=[DataRequired(), NumberRange(min=0.01, message="Quantity must be greater than 0")])
    quantity_passed = FloatField('Quantity Passed (Auto-calculated)', 
                               validators=[Optional()], 
                               render_kw={'readonly': True})
    quantity_rejected = FloatField('Quantity Rejected', 
                                 validators=[Optional(), NumberRange(min=0)],
                                 default=0.0)
    
    # Quick inspection
    inspection_status = SelectField('Overall Status', choices=[
        ('passed', 'All Passed'),
        ('rejected', 'All Rejected'),
        ('partial', 'Partial (some rejected)')
    ], default='passed')
    
    rejection_reason = TextAreaField('Rejection Reason (if any)', validators=[Optional()])
    
    # Delivery info
    delivery_note = StringField('Delivery Note', validators=[Optional(), Length(max=100)])
    
    # Add to inventory option
    add_to_inventory = BooleanField('Add Passed Quantity to Inventory', default=True)
    
    remarks = TextAreaField('Remarks', validators=[Optional()])
    
    # Document Upload
    supporting_documents = MultipleFileField('Supporting Documents', 
                                           validators=[FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'], 
                                                     'Only PDF, images, and office documents allowed!')])
    document_description = TextAreaField('Document Description', 
                                       validators=[Optional()],
                                       render_kw={'placeholder': 'Describe uploaded documents (e.g., Job work completion certificate, Quality report, etc.)'})


class QuickReceivePOForm(FlaskForm):
    """Quick form for receiving materials from purchase order"""
    
    purchase_order_id = IntegerField('Purchase Order ID', validators=[DataRequired()], widget=HiddenInput())
    item_id = IntegerField('Item ID', validators=[DataRequired()], widget=HiddenInput())
    received_date = DateField('Received Date', validators=[DataRequired()], default=date.today)
    
    # Quick quantity fields
    quantity_received = FloatField('Quantity Received', 
                                 validators=[DataRequired(), NumberRange(min=0.01, message="Quantity must be greater than 0")])
    quantity_passed = FloatField('Quantity Passed (Auto-calculated)', 
                               validators=[Optional()], 
                               render_kw={'readonly': True})
    quantity_rejected = FloatField('Quantity Rejected', 
                                 validators=[Optional(), NumberRange(min=0)],
                                 default=0.0)
    
    # Quick inspection
    inspection_status = SelectField('Overall Status', choices=[
        ('passed', 'All Passed'),
        ('rejected', 'All Rejected'),
        ('partial', 'Partial (some rejected)')
    ], default='passed')
    
    rejection_reason = TextAreaField('Rejection Reason (if any)', validators=[Optional()])
    
    # Delivery info
    delivery_note = StringField('Delivery Note', validators=[Optional(), Length(max=100)])
    
    # Add to inventory option
    add_to_inventory = BooleanField('Add Passed Quantity to Inventory', default=True)
    
    remarks = TextAreaField('Remarks', validators=[Optional()])
    
    # Document Upload
    supporting_documents = MultipleFileField('Supporting Documents', 
                                           validators=[FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'], 
                                                     'Only PDF, images, and office documents allowed!')])
    document_description = TextAreaField('Document Description', 
                                       validators=[Optional()],
                                       render_kw={'placeholder': 'Describe uploaded documents (e.g., Purchase invoice, Delivery challan, Quality certificate, etc.)'})


class GRNSearchForm(FlaskForm):
    """Form for searching and filtering GRNs"""
    
    search = StringField('Search GRN/Job Number', validators=[Optional()])
    
    status = SelectField('Status', choices=[
        ('', 'All Status'),
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('inspected', 'Inspected'),
        ('completed', 'Completed')
    ])
    
    inspection_status = SelectField('Inspection Status', choices=[
        ('', 'All Inspection Status'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ])
    
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    
    customer = StringField('Customer/Supplier', validators=[Optional()])


class MultiProcessQuickReceiveForm(FlaskForm):
    """Specialized quick receive form for multi-process job works"""
    
    job_work_id = IntegerField('Job Work ID', validators=[DataRequired()], widget=HiddenInput())
    process_id = IntegerField('Process ID', validators=[Optional()], widget=HiddenInput())
    received_date = DateField('Received Date', validators=[DataRequired()], default=date.today)
    
    # Process selection
    process_selection = SelectField('Select Process', choices=[], coerce=int, validators=[DataRequired()])
    
    # Quick quantity fields
    quantity_received = FloatField('Quantity Received from Process', 
                                 validators=[DataRequired(), NumberRange(min=0.01, message="Quantity must be greater than 0")])
    quantity_passed = FloatField('Quantity Passed (Auto-calculated)', 
                               validators=[Optional()], 
                               render_kw={'readonly': True})
    quantity_rejected = FloatField('Quantity Rejected', 
                                 validators=[Optional(), NumberRange(min=0)],
                                 default=0.0)
    
    # Process stage info
    process_stage = StringField('Process Stage Completed', validators=[Optional(), Length(max=100)])
    
    # Quick inspection
    inspection_status = SelectField('Overall Status', choices=[
        ('passed', 'All Passed'),
        ('rejected', 'All Rejected'),
        ('partial', 'Partial (some rejected)')
    ], default='passed')
    
    rejection_reason = TextAreaField('Rejection Reason (if any)', validators=[Optional()])
    
    # Delivery info
    delivery_note = StringField('Delivery Note from Process', validators=[Optional(), Length(max=100)])
    
    # Add to inventory option
    add_to_inventory = BooleanField('Add Passed Quantity to Inventory', default=True)
    
    remarks = TextAreaField('Process Completion Notes', validators=[Optional()])