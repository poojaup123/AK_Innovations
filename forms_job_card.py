from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SelectField, DateField, IntegerField, HiddenField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import date

class JobCardForm(FlaskForm):
    # Basic Information
    job_card_number = StringField('Job Card Number', validators=[DataRequired()])
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    item_id = SelectField('Item/Component', validators=[DataRequired()], coerce=int)
    
    # Process Information
    process_name = StringField('Process Name', validators=[DataRequired()])
    process_sequence = IntegerField('Process Sequence', default=1)
    operation_description = TextAreaField('Operation Description')
    
    # Quantities
    planned_quantity = FloatField('Planned Quantity', validators=[DataRequired(), NumberRange(min=0.1)])
    
    # Assignment
    assigned_worker_id = SelectField('Assigned Worker', coerce=int, validators=[Optional()])
    assigned_vendor_id = SelectField('Assigned Vendor', coerce=int, validators=[Optional()])
    machine_workstation = StringField('Machine/Workstation')
    
    # Time Estimates
    setup_time_minutes = FloatField('Setup Time (minutes)', default=0)
    run_time_minutes = FloatField('Run Time (minutes)', default=0)
    
    # Scheduling
    planned_start_date = DateField('Planned Start Date', default=date.today)
    planned_end_date = DateField('Planned End Date')
    target_completion_date = DateField('Target Completion Date', validators=[DataRequired()])
    
    # Priority and Cost
    priority = SelectField('Priority', choices=[
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')
    ], default='normal')
    estimated_cost = FloatField('Estimated Cost', default=0)
    
    # Notes
    production_notes = TextAreaField('Production Notes')

class JobCardDailyUpdateForm(FlaskForm):
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    
    # Daily Quantities
    qty_completed_today = FloatField('Quantity Completed Today', 
                                   validators=[DataRequired(), NumberRange(min=0)], default=0)
    qty_good_today = FloatField('Good Quantity Today', 
                               validators=[DataRequired(), NumberRange(min=0)], default=0)
    qty_defective_today = FloatField('Defective Quantity Today', 
                                   validators=[NumberRange(min=0)], default=0)
    qty_scrap_today = FloatField('Scrap Quantity Today', 
                               validators=[NumberRange(min=0)], default=0)
    
    # Time Tracking
    hours_worked = FloatField('Hours Worked Today', validators=[NumberRange(min=0)], default=0)
    setup_time_actual = FloatField('Actual Setup Time (minutes)', default=0)
    run_time_actual = FloatField('Actual Run Time (minutes)', default=0)
    downtime_minutes = FloatField('Downtime (minutes)', default=0)
    
    # Status Workflow
    daily_status = SelectField('Daily Status', choices=[
        ('active', 'Active'), 
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
        ('on_hold', 'On Hold')
    ], default='active')
    
    status_after_entry = SelectField('Status After Entry', choices=[
        ('', 'Select Status'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('pending_approval', 'Pending Approval')
    ], validators=[Optional()])
    
    # Batch Integration
    batch_number = StringField('Batch Number', validators=[Optional()])
    create_new_batch = BooleanField('Create New Batch for Good Quantity')
    
    # Process Step
    process_step = StringField('Process Step', validators=[Optional()])
    
    # Workflow Flags
    requires_supervisor_approval = BooleanField('Requires Supervisor Approval', default=True)
    requires_qc_approval = BooleanField('Requires QC Approval')
    is_outsourced_work = BooleanField('Outsourced Work (Auto-create GRN)')
    
    # Issues and Notes
    quality_issues = TextAreaField('Quality Issues')
    production_issues = TextAreaField('Production Issues')
    material_issues = TextAreaField('Material Issues')
    machine_issues = TextAreaField('Machine Issues')
    operator_notes = TextAreaField('Operator Notes')

class QuickJobCardUpdateForm(FlaskForm):
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    qty_completed = FloatField('Quantity Completed', validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
        ('on_hold', 'On Hold')
    ], default='active')
    notes = TextAreaField('Quick Notes')

class JobCardMaterialForm(FlaskForm):
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    item_id = SelectField('Material', validators=[DataRequired()], coerce=int)
    quantity_required = FloatField('Quantity Required', validators=[DataRequired(), NumberRange(min=0.1)])
    unit_cost = FloatField('Unit Cost', default=0)
    
class BulkJobCardForm(FlaskForm):
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    bom_id = HiddenField('BOM ID', validators=[DataRequired()])
    
    # Auto-generate settings
    auto_assign_sequences = SelectField('Auto Assign Sequences', 
                                      choices=[('yes', 'Yes'), ('no', 'No')], default='yes')
    default_priority = SelectField('Default Priority', 
                                 choices=[('low', 'Low'), ('normal', 'Normal'), 
                                         ('high', 'High'), ('urgent', 'Urgent')], 
                                 default='normal')
    
    # Time allocation
    buffer_days = IntegerField('Buffer Days Between Operations', default=1)