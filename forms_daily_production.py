from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, DateTimeField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange
from wtforms.widgets import DateTimeLocalInput
from datetime import datetime

class DailyProductionUpdateForm(FlaskForm):
    """Form for updating daily production status"""
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    
    # Daily quantities
    qty_completed_today = FloatField('Quantity Completed Today', 
                                   validators=[Optional(), NumberRange(min=0)], 
                                   default=0.0,
                                   render_kw={"step": "0.01", "placeholder": "Enter quantity completed today"})
    
    qty_good_today = FloatField('Good Quantity Today', 
                              validators=[Optional(), NumberRange(min=0)], 
                              default=0.0,
                              render_kw={"step": "0.01", "placeholder": "Enter good quantity"})
    
    qty_defective_today = FloatField('Defective Quantity Today', 
                                   validators=[Optional(), NumberRange(min=0)], 
                                   default=0.0,
                                   render_kw={"step": "0.01", "placeholder": "Enter defective quantity"})
    
    qty_scrap_today = FloatField('Scrap Quantity Today', 
                               validators=[Optional(), NumberRange(min=0)], 
                               default=0.0,
                               render_kw={"step": "0.01", "placeholder": "Enter scrap quantity"})
    
    # Status and progress
    daily_status = SelectField('Daily Status', 
                             choices=[('planned', 'Planned'), 
                                    ('active', 'Active'), 
                                    ('paused', 'Paused'), 
                                    ('completed', 'Completed'), 
                                    ('delayed', 'Delayed')],
                             default='planned')
    
    # Resource allocation
    workers_assigned = IntegerField('Workers Assigned', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=0,
                                  render_kw={"placeholder": "Number of workers"})
    
    machine_hours_used = FloatField('Machine Hours Used', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=0.0,
                                  render_kw={"step": "0.5", "placeholder": "Machine hours today"})
    
    overtime_hours = FloatField('Overtime Hours', 
                              validators=[Optional(), NumberRange(min=0)], 
                              default=0.0,
                              render_kw={"step": "0.5", "placeholder": "Overtime hours"})
    
    # Costs
    material_consumed_cost = FloatField('Material Cost Consumed', 
                                      validators=[Optional(), NumberRange(min=0)], 
                                      default=0.0,
                                      render_kw={"step": "0.01", "placeholder": "Material cost today"})
    
    labor_cost_today = FloatField('Labor Cost Today', 
                                validators=[Optional(), NumberRange(min=0)], 
                                default=0.0,
                                render_kw={"step": "0.01", "placeholder": "Labor cost today"})
    
    # Issues and notes
    production_issues = TextAreaField('Production Issues', 
                                    validators=[Optional()],
                                    render_kw={"rows": "3", "placeholder": "Describe any production issues"})
    
    quality_issues = TextAreaField('Quality Issues', 
                                 validators=[Optional()],
                                 render_kw={"rows": "3", "placeholder": "Describe any quality issues"})
    
    delay_reason = StringField('Delay Reason', 
                             validators=[Optional()],
                             render_kw={"placeholder": "Reason for any delays"})
    
    supervisor_notes = TextAreaField('Supervisor Notes', 
                                   validators=[Optional()],
                                   render_kw={"rows": "4", "placeholder": "Additional notes from supervisor"})
    
    # Shift times
    shift_start_time = DateTimeField('Shift Start Time', 
                                   validators=[Optional()],
                                   widget=DateTimeLocalInput(),
                                   default=datetime.now)
    
    shift_end_time = DateTimeField('Shift End Time', 
                                 validators=[Optional()],
                                 widget=DateTimeLocalInput())

class ShiftLogForm(FlaskForm):
    """Form for logging shift-specific production data"""
    daily_production_status_id = HiddenField('Daily Status ID', validators=[DataRequired()])
    
    shift_type = SelectField('Shift Type', 
                           choices=[('morning', 'Morning Shift (6 AM - 2 PM)'), 
                                  ('afternoon', 'Afternoon Shift (2 PM - 10 PM)'), 
                                  ('night', 'Night Shift (10 PM - 6 AM)')],
                           validators=[DataRequired()])
    
    # Shift timing
    shift_start = DateTimeField('Shift Start', 
                              validators=[DataRequired()],
                              widget=DateTimeLocalInput(),
                              default=datetime.now)
    
    shift_end = DateTimeField('Shift End', 
                            validators=[Optional()],
                            widget=DateTimeLocalInput())
    
    # Production metrics
    qty_produced_shift = FloatField('Quantity Produced This Shift', 
                                  validators=[Optional(), NumberRange(min=0)], 
                                  default=0.0,
                                  render_kw={"step": "0.01"})
    
    qty_good_shift = FloatField('Good Quantity This Shift', 
                              validators=[Optional(), NumberRange(min=0)], 
                              default=0.0,
                              render_kw={"step": "0.01"})
    
    qty_defective_shift = FloatField('Defective Quantity This Shift', 
                                   validators=[Optional(), NumberRange(min=0)], 
                                   default=0.0,
                                   render_kw={"step": "0.01"})
    
    # Shift resources
    workers_present = IntegerField('Workers Present', 
                                 validators=[Optional(), NumberRange(min=0)], 
                                 default=0)
    
    supervisor_name = StringField('Supervisor Name', 
                                validators=[Optional()],
                                render_kw={"placeholder": "Shift supervisor name"})
    
    # Downtime tracking
    machine_downtime_minutes = IntegerField('Machine Downtime (minutes)', 
                                          validators=[Optional(), NumberRange(min=0)], 
                                          default=0)
    
    downtime_reason = StringField('Downtime Reason', 
                                validators=[Optional()],
                                render_kw={"placeholder": "Reason for machine downtime"})
    
    # Notes
    shift_notes = TextAreaField('Shift Notes', 
                              validators=[Optional()],
                              render_kw={"rows": "3", "placeholder": "General shift notes"})
    
    issues_encountered = TextAreaField('Issues Encountered', 
                                     validators=[Optional()],
                                     render_kw={"rows": "3", "placeholder": "Issues during this shift"})

class QuickStatusUpdateForm(FlaskForm):
    """Quick form for updating production status"""
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    
    qty_completed = FloatField('Quantity Completed', 
                             validators=[DataRequired(), NumberRange(min=0)], 
                             render_kw={"step": "0.01", "placeholder": "Quantity completed"})
    
    status = SelectField('Status', 
                        choices=[('active', 'Active'), 
                               ('paused', 'Paused'), 
                               ('completed', 'Completed'), 
                               ('delayed', 'Delayed')],
                        validators=[DataRequired()])
    
    notes = TextAreaField('Quick Notes', 
                         validators=[Optional()],
                         render_kw={"rows": "2", "placeholder": "Quick update notes"})

class BulkStatusUpdateForm(FlaskForm):
    """Form for bulk updating multiple production orders"""
    status = SelectField('Apply Status to Selected', 
                        choices=[('', 'Select Status to Apply'),
                               ('active', 'Mark as Active'), 
                               ('paused', 'Mark as Paused'), 
                               ('completed', 'Mark as Completed'), 
                               ('delayed', 'Mark as Delayed')],
                        validators=[Optional()])
    
    supervisor_notes = TextAreaField('Bulk Update Notes', 
                                   validators=[Optional()],
                                   render_kw={"rows": "3", "placeholder": "Notes to apply to all selected productions"})