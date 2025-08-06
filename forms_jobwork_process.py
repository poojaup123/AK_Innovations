"""
Job Work Process Forms - Multi-Process Job Work Management

This module contains forms for managing multiple processes within a single job work.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FloatField, DateField, IntegerField, FieldList, FormField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from models import Supplier, Item
from datetime import datetime

class JobWorkProcessForm(FlaskForm):
    """Form for individual process within a job work"""
    process_name = SelectField('Process', 
                              validators=[DataRequired()], 
                              coerce=str,
                              choices=[('', 'Select Process'),
                                     ('Zinc', 'Zinc'),
                                     ('Cutting', 'Cutting'), 
                                     ('Bending', 'Bending'),
                                     ('Welding', 'Welding'),
                                     ('Painting', 'Painting'),
                                     ('Assembly', 'Assembly'),
                                     ('Machining', 'Machining'),
                                     ('Polishing', 'Polishing')])
    
    sequence_number = IntegerField('Sequence', 
                                  validators=[DataRequired(), NumberRange(min=1, max=20)],
                                  render_kw={'placeholder': 'Process order (1, 2, 3...)'})
    
    quantity_input = FloatField('Input Quantity', 
                               validators=[DataRequired(), NumberRange(min=0)],
                               render_kw={'placeholder': 'Quantity for this process'})
    input_uom = SelectField('Input Unit', validators=[DataRequired()], coerce=str)
    
    expected_scrap = FloatField('Expected Scrap', 
                               validators=[NumberRange(min=0)], 
                               default=0.0,
                               render_kw={'placeholder': 'Expected scrap quantity'})
    scrap_uom = SelectField('Scrap Unit', validators=[Optional()], coerce=str)
    
    # Output product specification
    output_item_id = SelectField('Output Product', 
                                coerce=int,
                                render_kw={'placeholder': 'What product will be created?'})
    
    output_quantity = FloatField('Output Quantity', 
                                validators=[NumberRange(min=0)], 
                                default=0.0,
                                render_kw={'placeholder': 'Expected quantity of output product'})
    output_uom = SelectField('Output Unit', validators=[Optional()], coerce=str)
    
    work_type = SelectField('Work Type',
                           validators=[DataRequired()],
                           coerce=str,
                           choices=[('outsourced', 'Outsourced'),
                                  ('in_house', 'In-House')],
                           default='outsourced')
    
    customer_name = SelectField('Customer/Vendor', 
                               coerce=str,
                               render_kw={'placeholder': 'Select vendor for this process'})
    
    department = SelectField('Department',
                            coerce=str,
                            choices=[('', 'Select Department'),
                                   ('production', 'Production'),
                                   ('assembly', 'Assembly'),
                                   ('quality_control', 'Quality Control'),
                                   ('finishing', 'Finishing'),
                                   ('packaging', 'Packaging'),
                                   ('maintenance', 'Maintenance')])
    
    rate_per_unit = FloatField('Rate per Unit', 
                              validators=[NumberRange(min=0)], 
                              default=0.0,
                              render_kw={'placeholder': 'Cost per unit for this process'})
    
    start_date = DateField('Start Date', 
                          validators=[Optional()],
                          render_kw={'placeholder': 'When this process starts'})
    
    expected_completion = DateField('Expected Completion', 
                                   validators=[Optional()],
                                   render_kw={'placeholder': 'Expected completion date'})
    
    notes = TextAreaField('Process Notes',
                         render_kw={'placeholder': 'Specific instructions for this process', 'rows': 2})
    
    def __init__(self, *args, **kwargs):
        super(JobWorkProcessForm, self).__init__(*args, **kwargs)
        
        # Populate customer choices from suppliers/vendors 
        suppliers = Supplier.query.order_by(Supplier.name).all()
        self.customer_name.choices = [('', 'Select Customer/Vendor')] + [(s.name, s.name) for s in suppliers]
        
        # Load UOM choices
        try:
            from models.uom import UnitOfMeasure
            uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
            uom_choices = [('', 'Select Unit')] + [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            self.input_uom.choices = uom_choices
            self.scrap_uom.choices = uom_choices
            self.output_uom.choices = uom_choices
        except Exception:
            fallback_choices = [('', 'Select Unit'), ('pcs', 'Pieces'), ('kg', 'Kilogram'), ('ltr', 'Liter')]
            self.input_uom.choices = fallback_choices
            self.scrap_uom.choices = fallback_choices
            self.output_uom.choices = fallback_choices
        
        # Populate output product choices with all items
        items = Item.query.order_by(Item.name).all()
        self.output_item_id.choices = [('', 'Select Output Product')] + [(str(i.id), f"{i.code} - {i.name}") for i in items]


class MultiProcessJobWorkForm(FlaskForm):
    """Enhanced Job Work form with multiple processes support"""
    
    # Basic Job Work Information (job_number will be auto-generated)
    item_id = SelectField('Item', validators=[DataRequired()], coerce=int)
    total_quantity = FloatField('Total Quantity', 
                               validators=[DataRequired(), NumberRange(min=0)],
                               render_kw={'placeholder': 'Total quantity for entire job work'})
    
    sent_date = DateField('Job Start Date', 
                         validators=[DataRequired()],
                         default=datetime.utcnow().date())
    
    expected_return = DateField('Overall Expected Completion', 
                               validators=[Optional()],
                               render_kw={'placeholder': 'Final completion date'})
    
    notes = TextAreaField('Job Work Notes',
                         render_kw={'placeholder': 'General notes for this job work', 'rows': 3})
    
    # Team work fields (existing)
    is_team_work = FormField(JobWorkProcessForm)  # This will be replaced with dynamic process fields
    
    def __init__(self, *args, **kwargs):
        super(MultiProcessJobWorkForm, self).__init__(*args, **kwargs)
        self.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
    
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        
        # Custom validation logic can be added here
        return True


class ProcessProgressForm(FlaskForm):
    """Form for updating progress on individual processes"""
    
    quantity_output = FloatField('Completed Quantity', 
                                validators=[DataRequired(), NumberRange(min=0)],
                                render_kw={'placeholder': 'Quantity completed'})
    
    quantity_scrap = FloatField('Scrap Quantity', 
                               validators=[Optional(), NumberRange(min=0)],
                               default=0.0,
                               render_kw={'placeholder': 'Scrap/waste generated'})
    
    status = SelectField('Process Status',
                        validators=[DataRequired()],
                        choices=[('pending', 'Pending'),
                               ('in_progress', 'In Progress'),
                               ('completed', 'Completed'),
                               ('on_hold', 'On Hold')])
    
    actual_completion = DateField('Completion Date', 
                                 validators=[Optional()],
                                 render_kw={'placeholder': 'Date process was completed'})
    
    notes = TextAreaField('Progress Notes',
                         render_kw={'placeholder': 'Notes about progress or issues', 'rows': 3})