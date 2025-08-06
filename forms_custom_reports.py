from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length

class CustomReportForm(FlaskForm):
    name = StringField('Report Name', validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    report_type = SelectField('Data Source', validators=[DataRequired()], choices=[
        ('inventory', 'Inventory Items'),
        ('purchase', 'Purchase Orders'),
        ('sales', 'Sales Orders'),
        ('jobwork', 'Job Work Orders'),
        ('production', 'Production Orders'),
        ('employee', 'Employee Records'),
        ('expenses', 'Factory Expenses'),
        ('quality', 'Quality Control'),
        ('mixed', 'Mixed Data Sources')
    ])
    is_shared = BooleanField('Share with other users')
    config = HiddenField('Configuration')

class CustomReportFilterForm(FlaskForm):
    """Form for adding filters to custom reports"""
    field = SelectField('Field', validators=[DataRequired()])
    operator = SelectField('Operator', validators=[DataRequired()], choices=[
        ('equals', 'Equals'),
        ('contains', 'Contains'),
        ('starts_with', 'Starts With'),
        ('ends_with', 'Ends With'),
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('greater_equal', 'Greater Than or Equal'),
        ('less_equal', 'Less Than or Equal'),
        ('between', 'Between'),
        ('in', 'In List'),
        ('not_null', 'Not Empty'),
        ('is_null', 'Is Empty')
    ])
    value = StringField('Value')
    value2 = StringField('Second Value')  # For between operator