from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, TextAreaField, DateField, HiddenField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms.widgets import TextArea
from datetime import date

class DailyProductionEntryForm(FlaskForm):
    """Form for recording daily production quantities and quality metrics"""
    
    # Hidden field to store production ID
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    
    # Production details (display only, but included for form processing)
    production_number = StringField('Production Order Number', render_kw={'readonly': True})
    item_name = StringField('Product Name', render_kw={'readonly': True})
    
    # Date of production entry
    production_date = DateField('Production Date', 
                               validators=[DataRequired()], 
                               default=date.today)
    
    # Shift information
    production_shift = SelectField('Production Shift', 
                                 choices=[
                                     ('day', 'Day Shift'),
                                     ('night', 'Night Shift'),
                                     ('general', 'General/Full Day')
                                 ],
                                 default='day',
                                 validators=[DataRequired()])
    
    # Target vs Actual Production
    target_quantity_today = FloatField('Target Quantity for Today', 
                                     validators=[Optional(), NumberRange(min=0)],
                                     render_kw={'placeholder': 'e.g., 500'})
    
    # Actual production quantities
    quantity_produced_today = FloatField('Actually Produced Today', 
                                       validators=[DataRequired(), NumberRange(min=0)],
                                       render_kw={'placeholder': 'e.g., 485'})
    
    # Quality metrics
    quantity_good_today = FloatField('Good Quality Items', 
                                   validators=[Optional(), NumberRange(min=0)],
                                   render_kw={'placeholder': 'e.g., 470'})
    
    quantity_defective_today = FloatField('Defective/Rework Items', 
                                        validators=[Optional(), NumberRange(min=0)],
                                        render_kw={'placeholder': 'e.g., 10'})
    
    quantity_scrap_today = FloatField('Scrap/Damaged Items', 
                                    validators=[Optional(), NumberRange(min=0)],
                                    render_kw={'placeholder': 'e.g., 5'})
    
    # Weight tracking (for items with weight specifications)
    weight_produced_today = FloatField('Total Weight Produced (kg)', 
                                     validators=[Optional(), NumberRange(min=0)],
                                     render_kw={'placeholder': 'e.g., 125.5'})
    
    # Quality control and notes
    quality_control_passed = SelectField('Quality Control Status',
                                        choices=[
                                            ('pending', 'Pending Inspection'),
                                            ('passed', 'QC Passed'),
                                            ('failed', 'QC Failed'),
                                            ('partial', 'Partial Pass')
                                        ],
                                        default='pending')
    
    # Detailed quality notes
    quality_notes = TextAreaField('Quality Control Notes',
                                 render_kw={
                                     'placeholder': 'Details about defects, quality issues, reasons for rejection, etc.',
                                     'rows': 4
                                 })
    
    # Production notes
    production_notes = TextAreaField('Production Notes',
                                   render_kw={
                                       'placeholder': 'Machine used, operator details, any production issues, etc.',
                                       'rows': 3
                                   })
    
    # Material consumption tracking
    material_consumption_notes = TextAreaField('Material Consumption Notes',
                                             render_kw={
                                                 'placeholder': 'Any variations from BOM, additional materials used, etc.',
                                                 'rows': 3
                                             })
    
    # Submit button
    submit = SubmitField('Record Daily Production')
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure quantities make sense"""
        if not super().validate(extra_validators):
            return False
        
        # Check if good + defective + scrap = total produced
        if (self.quantity_good_today.data is not None and 
            self.quantity_defective_today.data is not None and 
            self.quantity_scrap_today.data is not None and
            self.quantity_produced_today.data is not None):
            
            total_accounted = (self.quantity_good_today.data + 
                             self.quantity_defective_today.data + 
                             self.quantity_scrap_today.data)
            
            if abs(total_accounted - self.quantity_produced_today.data) > 0.01:
                self.quantity_produced_today.errors.append(
                    f'Total produced ({self.quantity_produced_today.data}) should equal '
                    f'good + defective + scrap ({total_accounted})'
                )
                return False
        
        return True


class ProductionProgressForm(FlaskForm):
    """Quick form for updating production progress from production list"""
    
    production_id = HiddenField('Production ID', validators=[DataRequired()])
    
    # Quick quantity update
    additional_quantity = FloatField('Additional Quantity Produced', 
                                   validators=[DataRequired(), NumberRange(min=0.01)],
                                   render_kw={'placeholder': 'e.g., 50'})
    
    # Quick quality split
    good_quantity = FloatField('Good Items', 
                             validators=[Optional(), NumberRange(min=0)])
    
    defective_quantity = FloatField('Defective Items', 
                                  validators=[Optional(), NumberRange(min=0)])
    
    # Quick notes
    notes = TextAreaField('Quick Notes',
                         render_kw={
                             'placeholder': 'Brief notes about this production update...',
                             'rows': 2
                         })
    
    submit = SubmitField('Update Production')


class BulkProductionUpdateForm(FlaskForm):
    """Form for updating multiple production orders at once"""
    
    # This will be populated dynamically with production orders
    # using JavaScript on the frontend
    
    submit = SubmitField('Update All Productions')