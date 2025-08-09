"""
Outsourcing Forms - Separate workflow for managing outsourcing after progress reports
"""

from flask_wtf import FlaskForm
from wtforms import (
    HiddenField, SelectField, IntegerField, FloatField, TextAreaField,
    BooleanField, SubmitField
)
from wtforms.validators import DataRequired, Optional, NumberRange


class OutsourcingWorkflowForm(FlaskForm):
    """Form for managing outsourcing workflow after progress report submission"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    daily_status_id = HiddenField('Daily Status ID', validators=[Optional()])
    
    # Process Selection for Outsourcing
    selected_processes = SelectField('Select Process to Outsource',
                                   choices=[],  # Populated dynamically
                                   validators=[DataRequired()])
    
    # Quantity Management
    available_quantity = FloatField('Available Quantity', 
                                  validators=[Optional()],
                                  render_kw={'readonly': True})
    
    outsource_quantity = FloatField('Quantity to Outsource', 
                                  validators=[DataRequired(), NumberRange(min=0.1)], 
                                  default=0)
    
    # Vendor Selection
    vendor_id = SelectField('Select Vendor',
                          choices=[],  # Populated dynamically
                          validators=[DataRequired()])
    
    # Outsourcing Details
    outsource_notes = TextAreaField('Outsourcing Instructions', 
                                  validators=[Optional()],
                                  description="Special instructions for vendor (e.g., zinc coating specifications, quality requirements)")
    
    expected_return_days = IntegerField('Expected Return (Days)', 
                                      validators=[Optional(), NumberRange(min=1, max=30)], 
                                      default=7)
    
    outsource_cost_estimate = FloatField('Estimated Cost per Unit', 
                                       validators=[Optional(), NumberRange(min=0)], 
                                       default=0)
    
    # Workflow Options
    create_tracking_batch = BooleanField('Create Tracking Batch for Outsourced Items', default=True)
    notify_vendor = BooleanField('Send Notification to Vendor', default=True)
    
    # Submit button
    submit = SubmitField('Send for Outsourcing')


class OutsourcingReturnForm(FlaskForm):
    """Form for handling returned items from outsourcing"""
    job_card_id = HiddenField('Job Card ID', validators=[DataRequired()])
    vendor_id = HiddenField('Vendor ID', validators=[DataRequired()])
    
    # Return Quantities
    returned_quantity = FloatField('Returned Quantity', 
                                 validators=[DataRequired(), NumberRange(min=0)], 
                                 default=0)
    
    good_quantity = FloatField('Good Quantity', 
                             validators=[DataRequired(), NumberRange(min=0)], 
                             default=0)
    
    defective_quantity = FloatField('Defective Quantity', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=0)
    
    # Quality Assessment
    quality_rating = SelectField('Quality Rating',
                               choices=[
                                   ('excellent', 'Excellent'),
                                   ('good', 'Good'),
                                   ('fair', 'Fair'),
                                   ('poor', 'Poor'),
                                   ('rejected', 'Rejected')
                               ],
                               default='good')
    
    # Return Details
    return_notes = TextAreaField('Return Notes', 
                               validators=[Optional()],
                               description="Quality assessment, issues found, etc.")
    
    actual_cost = FloatField('Actual Cost', 
                           validators=[Optional(), NumberRange(min=0)], 
                           default=0)
    
    # Next Steps
    next_action = SelectField('Next Action',
                            choices=[
                                ('continue_production', 'Continue Production'),
                                ('quality_check', 'Send to Quality Check'),
                                ('rework_required', 'Rework Required'),
                                ('reject_batch', 'Reject Batch')
                            ],
                            default='continue_production')
    
    # Submit button
    submit = SubmitField('Process Return')