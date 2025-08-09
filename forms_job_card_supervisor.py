from flask_wtf import FlaskForm
from wtforms import HiddenField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional
from datetime import date

class SupervisorApprovalForm(FlaskForm):
    """Form for supervisor approval of daily job card status"""
    daily_status_id = HiddenField('Daily Status ID', validators=[DataRequired()])
    
    # Approval Decision
    approval_action = SelectField('Approval Decision', choices=[
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('request_changes', 'Request Changes')
    ], validators=[DataRequired()])
    
    # Supervisor Notes
    supervisor_notes = TextAreaField('Supervisor Notes', 
                                   render_kw={'placeholder': 'Add your comments about the approval decision...'})
    
    # Additional Actions
    require_qc_inspection = BooleanField('Require QC Inspection')
    create_grn_for_outsourced = BooleanField('Create GRN for Outsourced Work')
    
    submit = SubmitField('Submit Approval')

class QCApprovalForm(FlaskForm):
    """Form for QC approval of job card daily status"""
    daily_status_id = HiddenField('Daily Status ID', validators=[DataRequired()])
    
    # QC Decision
    qc_decision = SelectField('QC Decision', choices=[
        ('approve', 'Approve - Good Quality'),
        ('reject', 'Reject - Failed QC'),
        ('conditional', 'Conditional Approval')
    ], validators=[DataRequired()])
    
    # QC Notes
    qc_notes = TextAreaField('QC Notes', 
                            validators=[DataRequired()],
                            render_kw={'placeholder': 'Detailed QC inspection notes...'})
    
    # Batch Actions
    create_good_batch = BooleanField('Create Good Quality Batch', default=True)
    create_scrap_batch = BooleanField('Create Scrap Batch for Rejected Items')
    
    submit = SubmitField('Submit QC Decision')

class BulkApprovalForm(FlaskForm):
    """Form for bulk approval of multiple job card status reports"""
    selected_reports = HiddenField('Selected Reports')
    
    # Bulk Actions
    bulk_action = SelectField('Bulk Action', choices=[
        ('approve_all', 'Approve All Selected'),
        ('reject_all', 'Reject All Selected'),
        ('approve_qc', 'Approve for QC Inspection')
    ], validators=[DataRequired()])
    
    # Bulk Notes
    bulk_notes = TextAreaField('Notes for All Selected Reports',
                              render_kw={'placeholder': 'These notes will be applied to all selected reports...'})
    
    submit = SubmitField('Apply Bulk Action')

class DailyProductionReviewForm(FlaskForm):
    """Form for daily production review and approval workflow"""
    review_date = HiddenField('Review Date')
    
    # Overall Assessment
    overall_assessment = SelectField('Overall Production Assessment', choices=[
        ('excellent', 'Excellent - Above Target'),
        ('good', 'Good - Met Targets'),
        ('satisfactory', 'Satisfactory - Minor Issues'),
        ('poor', 'Poor - Significant Issues')
    ], validators=[DataRequired()])
    
    # Production Issues
    major_issues = TextAreaField('Major Issues Identified')
    corrective_actions = TextAreaField('Corrective Actions Required')
    
    # Next Day Planning
    next_day_priorities = TextAreaField('Next Day Priorities')
    resource_requirements = TextAreaField('Additional Resource Requirements')
    
    # Approval
    approve_production_day = BooleanField('Approve Production Day', default=True)
    
    submit = SubmitField('Submit Daily Review')