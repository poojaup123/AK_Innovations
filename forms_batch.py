"""
Forms for Batch-wise Job Work Management
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, FloatField, StringField, DateField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from wtforms.widgets import DateInput
from datetime import date
from models import Item
from models.batch import InventoryBatch

class BatchJobWorkIssueForm(FlaskForm):
    """Form for issuing materials to job work with batch tracking"""
    
    # Job Work Details
    job_work_id = SelectField('Job Work', coerce=int, validators=[DataRequired()])
    process_name = StringField('Process Name', validators=[DataRequired(), Length(max=50)])
    vendor_name = StringField('Vendor/Department', validators=[DataRequired(), Length(max=100)])
    
    # Material Issue Details
    input_item_id = SelectField('Input Material', coerce=int, validators=[DataRequired()])
    input_batch_id = SelectField('Select Batch', coerce=int, validators=[DataRequired()])
    quantity_issued = FloatField('Quantity to Issue', validators=[DataRequired(), NumberRange(min=0.01)])
    
    # Rate and Cost
    rate_per_unit = FloatField('Rate per Unit', validators=[Optional(), NumberRange(min=0)])
    
    # Dates
    issue_date = DateField('Issue Date', default=date.today, validators=[DataRequired()], widget=DateInput())
    expected_return_date = DateField('Expected Return Date', validators=[Optional()], widget=DateInput())
    
    # Notes
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Issue Material')
    
    def __init__(self, *args, **kwargs):
        super(BatchJobWorkIssueForm, self).__init__(*args, **kwargs)
        
        # Populate job work choices
        from models import JobWork
        self.job_work_id.choices = [(0, 'Select Job Work')] + [
            (jw.id, f"{jw.job_number} - {jw.customer_name}") 
            for jw in JobWork.query.filter_by(status='sent').all()
        ]
        
        # Populate item choices
        self.input_item_id.choices = [(0, 'Select Material')] + [
            (item.id, f"{item.code} - {item.name}") 
            for item in Item.query.all()
        ]
        
        # Batch choices will be populated via AJAX based on selected item

class BatchJobWorkReturnForm(FlaskForm):
    """Form for receiving job work returns with batch tracking"""
    
    # Reference to original issue
    job_work_batch_id = HiddenField('Job Work Batch ID')
    job_work_id = SelectField('Job Work', coerce=int, validators=[DataRequired()])
    
    # Return Details
    return_date = DateField('Return Date', default=date.today, validators=[DataRequired()], widget=DateInput())
    
    # Output Details
    output_item_id = SelectField('Output Product', coerce=int, validators=[DataRequired()])
    output_batch_code = StringField('Output Batch Code', validators=[DataRequired(), Length(max=50)])
    quantity_produced = FloatField('Quantity Produced', validators=[DataRequired(), NumberRange(min=0)])
    
    # Quality Control
    quantity_passed = FloatField('Quantity Passed QC', validators=[DataRequired(), NumberRange(min=0)])
    quantity_rejected = FloatField('Quantity Rejected', validators=[Optional(), NumberRange(min=0)])
    quantity_scrap = FloatField('Scrap Quantity', validators=[Optional(), NumberRange(min=0)])
    
    # Unused Material Return
    quantity_returned_unused = FloatField('Unused Material Returned', validators=[Optional(), NumberRange(min=0)])
    
    # Output Batch Metadata
    output_mfg_date = DateField('Manufacturing Date', default=date.today, validators=[Optional()], widget=DateInput())
    output_expiry_date = DateField('Expiry Date', validators=[Optional()], widget=DateInput())
    output_location = StringField('Storage Location', validators=[Optional(), Length(max=100)])
    
    # Notes
    return_notes = TextAreaField('Return Notes', validators=[Optional(), Length(max=500)])
    qc_notes = TextAreaField('QC Notes', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Process Return')
    
    def __init__(self, *args, **kwargs):
        super(BatchJobWorkReturnForm, self).__init__(*args, **kwargs)
        
        # Populate job work choices (only those with issued batches)
        from models import JobWork
        self.job_work_id.choices = [(0, 'Select Job Work')] + [
            (jw.id, f"{jw.job_number} - {jw.customer_name}") 
            for jw in JobWork.query.join(JobWork.batch_records).filter_by(status='issued').all()
        ]
        
        # Populate output item choices
        self.output_item_id.choices = [(0, 'Select Output Product')] + [
            (item.id, f"{item.code} - {item.name}") 
            for item in Item.query.all()
        ]

class BatchInventoryForm(FlaskForm):
    """Form for creating/editing inventory batches"""
    
    # Item Selection
    item_id = SelectField('Item', coerce=int, validators=[DataRequired()])
    
    # Batch Details
    batch_code = StringField('Batch Code', validators=[DataRequired(), Length(max=50)])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    uom = StringField('Unit of Measure', validators=[DataRequired(), Length(max=20)])
    
    # Batch Metadata
    mfg_date = DateField('Manufacturing Date', validators=[Optional()], widget=DateInput())
    expiry_date = DateField('Expiry Date', validators=[Optional()], widget=DateInput())
    supplier_batch_no = StringField('Supplier Batch No.', validators=[Optional(), Length(max=50)])
    purchase_rate = FloatField('Purchase Rate', validators=[Optional(), NumberRange(min=0)])
    location = StringField('Storage Location', validators=[Optional(), Length(max=100)], default='Default')
    
    # Initial State
    initial_state = SelectField('Initial State', 
                               choices=[('raw', 'Raw Material'), ('finished', 'Finished Goods')],
                               default='raw', validators=[DataRequired()])
    
    # Source Information
    source_type = SelectField('Source Type',
                             choices=[('purchase', 'Purchase'), ('production', 'Production'), ('return', 'Return')],
                             default='purchase', validators=[DataRequired()])
    grn_id = SelectField('GRN Reference', coerce=int, validators=[Optional()])
    
    # Notes
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Create Batch')
    
    def __init__(self, *args, **kwargs):
        super(BatchInventoryForm, self).__init__(*args, **kwargs)
        
        # Populate item choices
        self.item_id.choices = [(0, 'Select Item')] + [
            (item.id, f"{item.code} - {item.name}") 
            for item in Item.query.all()
        ]
        
        # Populate GRN choices
        from models.grn import GRN
        self.grn_id.choices = [(0, 'No GRN Reference')] + [
            (grn.id, f"{grn.grn_number} - {grn.supplier.name if grn.supplier else 'Unknown'}") 
            for grn in GRN.query.filter_by(status='approved').all()
        ]

class BatchTransferForm(FlaskForm):
    """Form for transferring quantities between batch states"""
    
    batch_id = HiddenField('Batch ID')
    quantity = FloatField('Quantity to Transfer', validators=[DataRequired(), NumberRange(min=0.01)])
    from_state = SelectField('From State', 
                            choices=[('raw', 'Raw'), ('wip', 'WIP'), ('finished', 'Finished'), ('scrap', 'Scrap')],
                            validators=[DataRequired()])
    to_state = SelectField('To State',
                          choices=[('raw', 'Raw'), ('wip', 'WIP'), ('finished', 'Finished'), ('scrap', 'Scrap')],
                          validators=[DataRequired()])
    notes = TextAreaField('Transfer Notes', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Transfer Quantity')

class BatchSearchForm(FlaskForm):
    """Form for searching and filtering batches"""
    
    item_id = SelectField('Item', coerce=int, validators=[Optional()])
    batch_code = StringField('Batch Code', validators=[Optional(), Length(max=50)])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    
    # Date filters
    mfg_date_from = DateField('Mfg Date From', validators=[Optional()], widget=DateInput())
    mfg_date_to = DateField('Mfg Date To', validators=[Optional()], widget=DateInput())
    
    # State filters
    show_raw = SelectField('Show Raw', choices=[('all', 'All'), ('yes', 'Yes'), ('no', 'No')], default='all')
    show_wip = SelectField('Show WIP', choices=[('all', 'All'), ('yes', 'Yes'), ('no', 'No')], default='all')
    show_finished = SelectField('Show Finished', choices=[('all', 'All'), ('yes', 'Yes'), ('no', 'No')], default='all')
    show_scrap = SelectField('Show Scrap', choices=[('all', 'All'), ('yes', 'Yes'), ('no', 'No')], default='all')
    
    # Expiry filter
    expiry_status = SelectField('Expiry Status',
                               choices=[('all', 'All'), ('expired', 'Expired'), ('expiring_soon', 'Expiring Soon'), ('valid', 'Valid')],
                               default='all')
    
    submit = SubmitField('Search')
    
    def __init__(self, *args, **kwargs):
        super(BatchSearchForm, self).__init__(*args, **kwargs)
        
        # Populate item choices
        self.item_id.choices = [(0, 'All Items')] + [
            (item.id, f"{item.code} - {item.name}") 
            for item in Item.query.all()
        ]