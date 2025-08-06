from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, Length

class DocumentUploadForm(FlaskForm):
    # Hidden fields for transaction association
    transaction_type = HiddenField('Transaction Type', validators=[DataRequired()])
    transaction_id = HiddenField('Transaction ID', validators=[DataRequired()])
    
    # File upload
    file = FileField('Document File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'xls', 'xlsx', 'txt'], 
                   'Only PDF, Word, Excel, Image and Text files are allowed!')
    ])
    
    # Document metadata
    document_category = SelectField('Document Category', validators=[DataRequired()], choices=[
        ('', 'Select Category'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt/Payment Proof'),
        ('purchase_order', 'Purchase Order'),
        ('quotation', 'Quotation'),
        ('contract', 'Contract/Agreement'),
        ('specification', 'Technical Specification'),
        ('quality_certificate', 'Quality Certificate'),
        ('test_report', 'Test Report'),
        ('delivery_note', 'Delivery Note'),
        ('packing_list', 'Packing List'),
        ('warranty', 'Warranty Document'),
        ('insurance', 'Insurance Document'),
        ('compliance', 'Compliance Certificate'),
        ('other', 'Other')
    ])
    
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)], 
                               render_kw={'placeholder': 'Brief description of the document'})
    
    submit = SubmitField('Upload Document')

class DocumentForm(FlaskForm):
    """Form for editing document details (not the file itself)"""
    document_category = SelectField('Document Category', validators=[DataRequired()], choices=[
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt/Payment Proof'),
        ('purchase_order', 'Purchase Order'),
        ('quotation', 'Quotation'),
        ('contract', 'Contract/Agreement'),
        ('specification', 'Technical Specification'),
        ('quality_certificate', 'Quality Certificate'),
        ('test_report', 'Test Report'),
        ('delivery_note', 'Delivery Note'),
        ('packing_list', 'Packing List'),
        ('warranty', 'Warranty Document'),
        ('insurance', 'Insurance Document'),
        ('compliance', 'Compliance Certificate'),
        ('other', 'Other')
    ])
    
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Update Document')