from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, ValidationError
from wtforms.validators import DataRequired, Length, Optional
from models.department import Department

class DepartmentForm(FlaskForm):
    name = StringField('Department Name', validators=[DataRequired(), Length(min=2, max=100)],
                      render_kw={"placeholder": "e.g., Production, Quality Control"})
    code = StringField('Department Code', validators=[DataRequired(), Length(min=2, max=50)],
                      render_kw={"placeholder": "e.g., production, quality_control"})
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)],
                               render_kw={"placeholder": "Brief description of department functions", "rows": 3})
    is_active = BooleanField('Active', default=True)
    
    def __init__(self, department_id=None, *args, **kwargs):
        super(DepartmentForm, self).__init__(*args, **kwargs)
        self.department_id = department_id
    
    def validate_name(self, field):
        # Check if name already exists (excluding current department if editing)
        query = Department.query.filter_by(name=field.data)
        if self.department_id:
            query = query.filter(Department.id != self.department_id)
        
        if query.first():
            raise ValidationError('Department name already exists.')
    
    def validate_code(self, field):
        # Check if code already exists (excluding current department if editing)
        query = Department.query.filter_by(code=field.data)
        if self.department_id:
            query = query.filter(Department.id != self.department_id)
        
        if query.first():
            raise ValidationError('Department code already exists.')
        
        # Ensure code is lowercase and uses underscores
        if not field.data.islower() or ' ' in field.data:
            raise ValidationError('Department code must be lowercase and use underscores instead of spaces.')