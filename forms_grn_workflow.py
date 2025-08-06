from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, DateField, SelectField, TextAreaField, HiddenField, FieldList, FormField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from datetime import date

class VendorInvoiceForm(FlaskForm):
    """Form for creating vendor invoices"""
    
    invoice_number = StringField('Invoice Number', 
                               validators=[DataRequired(), Length(max=100)])
    invoice_date = DateField('Invoice Date', 
                           validators=[DataRequired()], 
                           default=date.today)
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[DataRequired()])
    
    # Amount fields
    base_amount = DecimalField('Base Amount', 
                             validators=[DataRequired(), NumberRange(min=0)], 
                             default=0.0)
    gst_amount = DecimalField('GST Amount', 
                            validators=[Optional(), NumberRange(min=0)], 
                            default=0.0)
    freight_amount = DecimalField('Freight Amount', 
                                validators=[Optional(), NumberRange(min=0)], 
                                default=0.0)
    other_charges = DecimalField('Other Charges', 
                               validators=[Optional(), NumberRange(min=0)], 
                               default=0.0)
    total_amount = DecimalField('Total Amount', 
                              validators=[DataRequired(), NumberRange(min=0)])
    
    # Document upload
    invoice_document = FileField('Upload Invoice Document',
                               validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'Only PDF and image files allowed')])
    
    submit = SubmitField('Save Invoice')

class GRNInvoiceLinkForm(FlaskForm):
    """Form for linking GRNs to vendor invoice"""
    
    grn_id = HiddenField('GRN ID', validators=[DataRequired()])
    grn_number = StringField('GRN Number', render_kw={'readonly': True})
    allocated_amount = DecimalField('Allocated Amount', 
                                  validators=[DataRequired(), NumberRange(min=0)])
    include_in_invoice = BooleanField('Include in Invoice', default=True)

class VendorInvoiceWithGRNForm(FlaskForm):
    """Form for creating vendor invoice with GRN links"""
    
    invoice_number = StringField('Invoice Number', 
                               validators=[DataRequired(), Length(max=100)])
    invoice_date = DateField('Invoice Date', 
                           validators=[DataRequired()], 
                           default=date.today)
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[DataRequired()])
    
    # GRN links - populated dynamically
    grn_links = FieldList(FormField(GRNInvoiceLinkForm), min_entries=0)
    
    # Amount fields
    base_amount = DecimalField('Base Amount', 
                             validators=[DataRequired(), NumberRange(min=0)], 
                             default=0.0)
    gst_amount = DecimalField('GST Amount', 
                            validators=[Optional(), NumberRange(min=0)], 
                            default=0.0)
    freight_amount = DecimalField('Freight Amount', 
                                validators=[Optional(), NumberRange(min=0)], 
                                default=0.0)
    other_charges = DecimalField('Other Charges', 
                               validators=[Optional(), NumberRange(min=0)], 
                               default=0.0)
    total_amount = DecimalField('Total Amount', 
                              validators=[DataRequired(), NumberRange(min=0)])
    
    # Document upload
    invoice_document = FileField('Upload Invoice Document',
                               validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'Only PDF and image files allowed')])
    
    submit = SubmitField('Create Invoice & Process')

class PaymentVoucherForm(FlaskForm):
    """Form for creating payment vouchers"""
    
    payment_date = DateField('Payment Date', 
                           validators=[DataRequired()], 
                           default=date.today)
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[DataRequired()])
    payment_method = SelectField('Payment Method',
                               choices=[('cash', 'Cash'),
                                      ('bank', 'Bank Transfer'),
                                      ('upi', 'UPI'),
                                      ('cheque', 'Cheque'),
                                      ('credit_card', 'Credit Card')],
                               validators=[DataRequired()])
    
    payment_amount = DecimalField('Payment Amount', 
                                validators=[DataRequired(), NumberRange(min=0.01)])
    
    # Bank details (shown based on payment method)
    bank_account_id = SelectField('Bank Account', 
                                coerce=int, 
                                validators=[Optional()])
    reference_number = StringField('Reference Number', 
                                 validators=[Optional(), Length(max=100)])
    
    # Notes
    narration = TextAreaField('Narration/Notes', 
                            validators=[Optional()])
    
    # Document upload
    payment_document = FileField('Upload Supporting Document',
                               validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'Only PDF and image files allowed')])
    
    submit = SubmitField('Record Payment')

class InvoiceAllocationForm(FlaskForm):
    """Form for allocating payments to invoices"""
    
    invoice_id = HiddenField('Invoice ID', validators=[DataRequired()])
    invoice_number = StringField('Invoice Number', render_kw={'readonly': True})
    invoice_amount = DecimalField('Invoice Amount', render_kw={'readonly': True})
    outstanding_amount = DecimalField('Outstanding Amount', render_kw={'readonly': True})
    allocated_amount = DecimalField('Allocated Amount', 
                                  validators=[DataRequired(), NumberRange(min=0)])

class PaymentWithAllocationForm(FlaskForm):
    """Form for payment with invoice allocation"""
    
    payment_date = DateField('Payment Date', 
                           validators=[DataRequired()], 
                           default=date.today)
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[DataRequired()])
    payment_method = SelectField('Payment Method',
                               choices=[('cash', 'Cash'),
                                      ('bank', 'Bank Transfer'),
                                      ('upi', 'UPI'),
                                      ('cheque', 'Cheque'),
                                      ('credit_card', 'Credit Card')],
                               validators=[DataRequired()])
    
    total_payment_amount = DecimalField('Total Payment Amount', 
                                      validators=[DataRequired(), NumberRange(min=0.01)])
    
    # Bank details
    bank_account_id = SelectField('Bank Account', 
                                coerce=int, 
                                validators=[Optional()])
    reference_number = StringField('Reference Number', 
                                 validators=[Optional(), Length(max=100)])
    
    # Invoice allocations - populated dynamically
    invoice_allocations = FieldList(FormField(InvoiceAllocationForm), min_entries=0)
    
    # Notes
    narration = TextAreaField('Narration/Notes', 
                            validators=[Optional()])
    
    # Document upload
    payment_document = FileField('Upload Supporting Document',
                               validators=[Optional(), FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'Only PDF and image files allowed')])
    
    submit = SubmitField('Record Payment & Allocate')

class GRNSearchForm(FlaskForm):
    """Form for searching GRNs for invoice linking"""
    
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[Optional()])
    grn_number = StringField('GRN Number', 
                           validators=[Optional()])
    date_from = DateField('From Date', 
                        validators=[Optional()])
    date_to = DateField('To Date', 
                      validators=[Optional()])
    
    # Status filters
    pending_invoice_only = BooleanField('Only Pending Invoice', default=True)
    
    search = SubmitField('Search GRNs')

class POFulfillmentFilterForm(FlaskForm):
    """Form for filtering PO fulfillment report"""
    
    vendor_id = SelectField('Vendor', 
                          coerce=int, 
                          validators=[Optional()])
    po_number = StringField('PO Number', 
                          validators=[Optional()])
    status = SelectField('Status',
                       choices=[('all', 'All Status'),
                              ('pending', 'Pending'),
                              ('partial', 'Partial'),
                              ('complete', 'Complete')],
                       default='all')
    date_from = DateField('From Date', 
                        validators=[Optional()])
    date_to = DateField('To Date', 
                      validators=[Optional()])
    
    filter_report = SubmitField('Filter Report')