from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField, DateField, BooleanField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from datetime import date

class AccountGroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('Group Code', validators=[DataRequired(), Length(min=1, max=20)])
    group_type = SelectField('Group Type', validators=[DataRequired()], choices=[
        ('assets', 'Assets'),
        ('liabilities', 'Liabilities'),
        ('income', 'Income'),
        ('expenses', 'Expenses'),
        ('equity', 'Equity')
    ])
    parent_group_id = SelectField('Parent Group', coerce=int, validators=[Optional()])

class AccountForm(FlaskForm):
    name = StringField('Account Name', validators=[DataRequired(), Length(min=2, max=200)])
    code = StringField('Account Code', validators=[DataRequired(), Length(min=1, max=50)])
    account_group_id = SelectField('Account Group', coerce=int, validators=[DataRequired()])
    account_type = SelectField('Account Type', validators=[DataRequired()], choices=[
        ('current_asset', 'Current Asset'),
        ('fixed_asset', 'Fixed Asset'),
        ('current_liability', 'Current Liability'),
        ('long_term_liability', 'Long Term Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
        ('cost_of_goods_sold', 'Cost of Goods Sold')
    ])
    opening_balance = DecimalField('Opening Balance', validators=[Optional()], default=0.0)
    is_gst_applicable = BooleanField('GST Applicable')
    gst_rate = DecimalField('GST Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    hsn_sac_code = StringField('HSN/SAC Code', validators=[Optional(), Length(max=20)])
    is_bank_account = BooleanField('Is Bank Account')
    is_cash_account = BooleanField('Is Cash Account')

class VoucherForm(FlaskForm):
    voucher_type_id = SelectField('Voucher Type', coerce=int, validators=[DataRequired()])
    transaction_date = DateField('Transaction Date', validators=[DataRequired()], default=date.today)
    reference_number = StringField('Reference Number', validators=[Optional(), Length(max=100)])
    narration = TextAreaField('Narration', validators=[Optional(), Length(max=500)])
    party_id = SelectField('Party', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    party_type = SelectField('Party Type', validators=[Optional()], choices=[
        ('', 'Select Party Type'),
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('employee', 'Employee')
    ])
    total_amount = DecimalField('Total Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    tax_amount = DecimalField('Tax Amount', validators=[Optional()], default=0.0)
    discount_amount = DecimalField('Discount Amount', validators=[Optional()], default=0.0)
    is_gst_applicable = BooleanField('GST Applicable')

class JournalEntryForm(FlaskForm):
    account_id = SelectField('Account', coerce=int, validators=[DataRequired()])
    entry_type = SelectField('Entry Type', validators=[DataRequired()], choices=[
        ('debit', 'Debit'),
        ('credit', 'Credit')
    ])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    narration = TextAreaField('Narration', validators=[Optional(), Length(max=500)])
    reference_type = StringField('Reference Type', validators=[Optional(), Length(max=50)])
    reference_id = IntegerField('Reference ID', validators=[Optional()])

class InvoiceForm(FlaskForm):
    invoice_type = SelectField('Invoice Type', validators=[DataRequired()], choices=[
        ('sales', 'Sales Invoice'),
        ('purchase', 'Purchase Invoice')
    ])
    party_id = SelectField('Party', coerce=int, validators=[DataRequired()])
    invoice_date = DateField('Invoice Date', validators=[DataRequired()], default=date.today)
    due_date = DateField('Due Date', validators=[Optional()])
    place_of_supply = StringField('Place of Supply', validators=[Optional(), Length(max=100)])
    reference_type = SelectField('Reference Type', validators=[Optional()], choices=[
        ('', 'No Reference'),
        ('sales_order', 'Sales Order'),
        ('purchase_order', 'Purchase Order'),
        ('job_work', 'Job Work Order')
    ])
    reference_id = IntegerField('Reference ID', validators=[Optional()])

class InvoiceItemForm(FlaskForm):
    item_id = SelectField('Item', coerce=int, validators=[Optional()])
    item_name = StringField('Item Name', validators=[DataRequired(), Length(min=1, max=200)])
    item_code = StringField('Item Code', validators=[Optional(), Length(max=50)])
    hsn_code = StringField('HSN Code', validators=[Optional(), Length(max=20)])
    quantity = DecimalField('Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    unit = StringField('Unit', validators=[DataRequired(), Length(min=1, max=20)])
    rate = DecimalField('Rate', validators=[DataRequired(), NumberRange(min=0.01)])
    gst_rate = DecimalField('GST Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)

class TaxMasterForm(FlaskForm):
    hsn_sac_code = StringField('HSN/SAC Code', validators=[DataRequired(), Length(min=1, max=20)])
    description = StringField('Description', validators=[DataRequired(), Length(min=1, max=500)])
    cgst_rate = DecimalField('CGST Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    sgst_rate = DecimalField('SGST Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    igst_rate = DecimalField('IGST Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    tax_category = SelectField('Tax Category', validators=[Optional()], choices=[
        ('goods', 'Goods'),
        ('services', 'Services')
    ])

class BankAccountForm(FlaskForm):
    account_id = SelectField('GL Account', coerce=int, validators=[DataRequired()])
    bank_name = StringField('Bank Name', validators=[DataRequired(), Length(min=2, max=200)])
    branch_name = StringField('Branch Name', validators=[Optional(), Length(max=200)])
    account_number = StringField('Account Number', validators=[DataRequired(), Length(min=5, max=50)])
    ifsc_code = StringField('IFSC Code', validators=[DataRequired(), Length(min=11, max=11)])
    account_type = SelectField('Account Type', validators=[DataRequired()], choices=[
        ('current', 'Current Account'),
        ('savings', 'Savings Account'),
        ('overdraft', 'Overdraft Account')
    ])
    opening_balance = DecimalField('Opening Balance', validators=[Optional()], default=0.0)

class PaymentForm(FlaskForm):
    """Form for payment vouchers"""
    party_id = SelectField('Pay To', coerce=lambda x: int(x) if x else None, validators=[DataRequired()])
    payment_date = DateField('Payment Date', validators=[DataRequired()], default=date.today)
    payment_mode = SelectField('Payment Mode', validators=[DataRequired()], choices=[
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('upi', 'UPI'),
        ('neft', 'NEFT/RTGS')
    ])
    bank_account_id = SelectField('From Bank Account', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    reference_number = StringField('Reference/Cheque Number', validators=[Optional(), Length(max=100)])
    narration = TextAreaField('Narration', validators=[Optional(), Length(max=500)])

class ReceiptForm(FlaskForm):
    """Form for receipt vouchers"""
    party_id = SelectField('Received From', coerce=lambda x: int(x) if x else None, validators=[DataRequired()])
    receipt_date = DateField('Receipt Date', validators=[DataRequired()], default=date.today)
    receipt_mode = SelectField('Receipt Mode', validators=[DataRequired()], choices=[
        ('cash', 'Cash'),
        ('bank', 'Bank Deposit'),
        ('cheque', 'Cheque'),
        ('upi', 'UPI'),
        ('neft', 'NEFT/RTGS')
    ])
    bank_account_id = SelectField('To Bank Account', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    reference_number = StringField('Reference/Cheque Number', validators=[Optional(), Length(max=100)])
    narration = TextAreaField('Narration', validators=[Optional(), Length(max=500)])

class ReportFilterForm(FlaskForm):
    """Form for financial report filters"""
    from_date = DateField('From Date', validators=[DataRequired()], default=date.today().replace(day=1))
    to_date = DateField('To Date', validators=[DataRequired()], default=date.today)
    account_group_id = SelectField('Account Group', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    account_id = SelectField('Specific Account', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    party_id = SelectField('Party', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    voucher_type_id = SelectField('Voucher Type', coerce=lambda x: int(x) if x else None, validators=[Optional()])
    
class GSATReportForm(FlaskForm):
    """Form for GST reports"""
    report_type = SelectField('Report Type', validators=[DataRequired()], choices=[
        ('gstr1', 'GSTR-1 (Outward Supplies)'),
        ('gstr3b', 'GSTR-3B (Summary Return)')
    ])
    month = SelectField('Month', validators=[DataRequired()], choices=[
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ])
    year = SelectField('Year', validators=[DataRequired()], choices=[
        ('2023', '2023'), ('2024', '2024'), ('2025', '2025'), ('2026', '2026')
    ])