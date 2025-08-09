"""
Job Card Forms

Forms for job card management, daily status updates, 
and workflow control according to the production specifications.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, FloatField, SelectField, DateField, BooleanField, HiddenField, FieldList, FormField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import date

class JobCardForm(FlaskForm):
    """Main job card creation/editing form"""
    job_card_number = StringField('Job Card Number', validators=[DataRequired()])
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    item_id = IntegerField('Item ID', validators=[DataRequired()])
    
    # Process Information
    process_name = StringField('Process Name', validators=[DataRequired()])
    process_sequence = IntegerField('Process Sequence', validators=[Optional()], default=1)
    operation_description = TextAreaField('Operation Description', validators=[Optional()])
    job_type = SelectField('Job Type', 
                          choices=[('in_house', 'In-House'), ('outsourced', 'Outsourced')],
                          default='in_house')
    department = StringField('Department', validators=[Optional()])
    
    # Quantities
    planned_quantity = FloatField('Planned Quantity', validators=[DataRequired(), NumberRange(min=0)])
    
    # Assignment
    assigned_worker_id = IntegerField('Assigned Worker', validators=[Optional()])
    assigned_vendor_id = IntegerField('Assigned Vendor', validators=[Optional()])
    machine_workstation = StringField('Machine/Workstation', validators=[Optional()])
    
    # Scheduling
    planned_start_date = DateField('Planned Start Date', validators=[Optional()], default=date.today)
    target_completion_date = DateField('Target Completion Date', validators=[DataRequired()])
    
    # Cost Estimation
    estimated_cost = FloatField('Estimated Cost', validators=[Optional()], default=0)
    run_time_minutes = IntegerField('Estimated Runtime (minutes)', validators=[Optional()], default=0)
    
    # Instructions
    work_instructions = TextAreaField('Work Instructions', validators=[Optional()])
    safety_notes = TextAreaField('Safety Notes', validators=[Optional()])
    special_instructions = TextAreaField('Special Instructions', validators=[Optional()])
    quality_requirements = TextAreaField('Quality Requirements', validators=[Optional()])
    
    # Priority
    priority = SelectField('Priority',
                          choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                          default='medium')
    
    # Notes
    notes = TextAreaField('Additional Notes', validators=[Optional()])

class JobCardDailyUpdateForm(FlaskForm):
    """Daily status update form for job cards"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    
    # Quantity Updates
    qty_completed_today = FloatField('Quantity Completed Today', 
                                   validators=[DataRequired(), NumberRange(min=0)], 
                                   default=0)
    qty_good_today = FloatField('Good Quantity Today', 
                              validators=[DataRequired(), NumberRange(min=0)], 
                              default=0)
    qty_defective_today = FloatField('Defective Quantity Today', 
                                   validators=[Optional(), NumberRange(min=0)], 
                                   default=0)
    qty_scrap_today = FloatField('Scrap Quantity Today', 
                               validators=[Optional(), NumberRange(min=0)], 
                               default=0)
    
    # Process Selection
    selected_processes = TextAreaField('Selected Processes (JSON)', validators=[Optional()])
    
    # Process-wise tracking
    process_completed = BooleanField('Process Completed Today', default=False)
    current_process_step = StringField('Current Process Step', validators=[Optional()])
    process_notes = TextAreaField('Process-specific Notes', validators=[Optional()])
    
    # Status and Progress
    daily_status = SelectField('Today\'s Status',
                             choices=[
                                 ('not_started', 'Not Started'),
                                 ('active', 'Active'),
                                 ('completed', 'Completed'),
                                 ('delayed', 'Delayed'),
                                 ('on_hold', 'On Hold'),
                                 ('quality_check', 'Quality Check')
                             ],
                             default='active')
    
    efficiency_rate = FloatField('Efficiency Rate (%)', 
                               validators=[Optional(), NumberRange(min=0, max=100)], 
                               default=100)
    
    # Resource Usage
    machine_hours_used = FloatField('Machine Hours Used', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=0)
    overtime_hours = FloatField('Overtime Hours', 
                              validators=[Optional(), NumberRange(min=0)], 
                              default=0)
    
    # Cost Tracking
    material_consumed_cost = FloatField('Material Cost Consumed Today', 
                                      validators=[Optional(), NumberRange(min=0)], 
                                      default=0)
    labor_cost_today = FloatField('Labor Cost Today', 
                                validators=[Optional(), NumberRange(min=0)], 
                                default=0)
    
    # Issues and Notes
    production_issues = TextAreaField('Production Issues', validators=[Optional()])
    quality_issues = TextAreaField('Quality Issues', validators=[Optional()])
    delay_reason = TextAreaField('Delay Reason (if applicable)', validators=[Optional()])
    supervisor_notes = TextAreaField('Supervisor Notes', validators=[Optional()])
    
    # Batch Management - Automated
    create_new_batch = BooleanField('Create New Output Batch', default=False)
    # Note: Input batch numbers are automatically determined from job card material requirements
    
    # Outsourcing Management
    outsource_process = BooleanField('Outsource Selected Process(es)', default=False)
    outsource_quantity = FloatField('Quantity to Outsource', validators=[Optional(), NumberRange(min=0)], default=0)
    outsource_vendor_id = IntegerField('Outsource to Vendor', validators=[Optional()])
    outsource_notes = TextAreaField('Outsourcing Instructions', validators=[Optional()])
    
    # Workflow Control
    status_after_entry = SelectField('Action After Entry',
                                   choices=[
                                       ('none', 'Save Only'),
                                       ('pending_approval', 'Submit for Supervisor Approval'),
                                       ('submit_to_qc', 'Submit to Quality Control'),
                                       ('outsource_process', 'Send to Vendor for Processing'),
                                       ('partial_outsource', 'Partial Outsource - Continue Other Work'),
                                       ('complete_job', 'Mark Job Card Complete')
                                   ],
                                   default='none')

class BulkJobCardForm(FlaskForm):
    """Form for bulk job card creation from BOM"""
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    bom_id = HiddenField('BOM ID', validators=[DataRequired()])
    
    # Scheduling options
    buffer_days = IntegerField('Buffer Days Between Processes', 
                              validators=[Optional(), NumberRange(min=0)], 
                              default=1)
    
    default_priority = SelectField('Default Priority',
                                 choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                                 default='medium')
    
    # Worker assignment options
    auto_assign_workers = BooleanField('Auto-assign Available Workers', default=False)
    default_department = StringField('Default Department', validators=[Optional()])
    
    # Cost and timing
    default_labor_rate = FloatField('Default Labor Rate (per hour)', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=25.0)
    
    # Process options
    create_process_cards = BooleanField('Create Process-based Job Cards', default=True)
    create_component_cards = BooleanField('Create Component-based Job Cards', default=False)
    
    # Notes
    bulk_notes = TextAreaField('Bulk Creation Notes', validators=[Optional()])

class JobCardApprovalForm(FlaskForm):
    """Form for supervisor approval workflow"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    daily_status_id = HiddenField('Daily Status ID', validators=[DataRequired()])
    
    approval_action = SelectField('Approval Decision',
                                choices=[
                                    ('approve', 'Approve'),
                                    ('reject', 'Reject'),
                                    ('request_changes', 'Request Changes')
                                ],
                                validators=[DataRequired()])
    
    supervisor_comments = TextAreaField('Supervisor Comments', validators=[Optional()])
    
    # If approving, where to send next
    next_step = SelectField('Next Step (if approved)',
                          choices=[
                              ('continue_production', 'Continue Production'),
                              ('send_to_qc', 'Send to Quality Control'),
                              ('complete_job_card', 'Complete Job Card')
                          ],
                          default='continue_production')

class JobCardQCForm(FlaskForm):
    """Quality Control form for job cards"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    daily_status_id = HiddenField('Daily Status ID', validators=[DataRequired()])
    
    qc_decision = SelectField('Quality Decision',
                            choices=[
                                ('passed', 'Passed'),
                                ('failed', 'Failed'),
                                ('conditional_pass', 'Conditional Pass'),
                                ('rework_required', 'Rework Required')
                            ],
                            validators=[DataRequired()])
    
    quality_rating = IntegerField('Quality Rating (1-10)', 
                                validators=[Optional(), NumberRange(min=1, max=10)])
    
    defects_found = TextAreaField('Defects Found', validators=[Optional()])
    qc_notes = TextAreaField('QC Notes', validators=[Optional()])
    rework_instructions = TextAreaField('Rework Instructions (if applicable)', validators=[Optional()])
    
    # Sample inspection details
    sample_size = IntegerField('Sample Size', validators=[Optional(), NumberRange(min=0)])
    defective_in_sample = IntegerField('Defective in Sample', validators=[Optional(), NumberRange(min=0)])
    
    # Final actions
    final_action = SelectField('Final Action',
                             choices=[
                                 ('accept_lot', 'Accept Lot'),
                                 ('reject_lot', 'Reject Lot'),
                                 ('partial_accept', 'Partial Accept'),
                                 ('send_for_rework', 'Send for Rework')
                             ],
                             default='accept_lot')

class JobCardMaterialIssueForm(FlaskForm):
    """Form for issuing materials to job cards"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    
    material_id = IntegerField('Material', validators=[DataRequired()])
    quantity_issued = FloatField('Quantity to Issue', 
                               validators=[DataRequired(), NumberRange(min=0)])
    batch_number = StringField('Batch Number', validators=[Optional()])
    
    issue_notes = TextAreaField('Issue Notes', validators=[Optional()])
    issued_by_id = HiddenField('Issued By', validators=[DataRequired()])

class JobCardProcessStepForm(FlaskForm):
    """Form for updating individual process steps"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    process_step = StringField('Process Step', validators=[DataRequired()])
    
    step_status = SelectField('Step Status',
                            choices=[
                                ('started', 'Started'),
                                ('in_progress', 'In Progress'),
                                ('completed', 'Completed'),
                                ('on_hold', 'On Hold'),
                                ('skipped', 'Skipped')
                            ],
                            validators=[DataRequired()])
    
    time_taken_minutes = IntegerField('Time Taken (minutes)', validators=[Optional()])
    step_notes = TextAreaField('Step Notes', validators=[Optional()])
    quality_check_passed = BooleanField('Quality Check Passed', default=True)

class JobCardBatchCreationForm(FlaskForm):
    """Form for creating output batches from job cards"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    
    batch_quantity = FloatField('Batch Quantity', 
                              validators=[DataRequired(), NumberRange(min=0)])
    batch_quality = SelectField('Batch Quality',
                              choices=[
                                  ('good', 'Good'),
                                  ('defective', 'Defective'),
                                  ('rework', 'Rework Required')
                              ],
                              default='good')
    
    batch_notes = TextAreaField('Batch Notes', validators=[Optional()])
    storage_location = StringField('Storage Location', validators=[Optional()])
    expiry_date = DateField('Expiry Date', validators=[Optional()])