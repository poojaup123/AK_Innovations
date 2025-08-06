from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SelectField, IntegerField, DecimalField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length

class AccountingSettingsForm(FlaskForm):
    """Form for accounting settings configuration"""
    
    # Auto voucher settings
    auto_jv_posting = BooleanField('Auto Journal Voucher Posting', default=True)
    auto_grn_voucher = BooleanField('Auto GRN Vouchers', default=True)
    auto_sales_voucher = BooleanField('Auto Sales Vouchers', default=True)
    auto_production_voucher = BooleanField('Auto Production Vouchers', default=True)
    auto_expense_voucher = BooleanField('Auto Expense Vouchers', default=True)
    auto_salary_voucher = BooleanField('Auto Salary Vouchers', default=True)
    
    # Rounding rules
    amount_rounding_places = IntegerField('Amount Rounding Places', 
                                        validators=[NumberRange(min=0, max=4)], 
                                        default=2)
    rounding_method = SelectField('Rounding Method',
                                choices=[('normal', 'Normal Rounding'),
                                       ('up', 'Round Up'),
                                       ('down', 'Round Down')],
                                default='normal')
    
    # Inventory valuation
    inventory_valuation_method = SelectField('Inventory Valuation Method',
                                           choices=[('fifo', 'First In First Out (FIFO)'),
                                                  ('lifo', 'Last In First Out (LIFO)'),
                                                  ('moving_average', 'Moving Average'),
                                                  ('standard_cost', 'Standard Cost')],
                                           default='moving_average')
    
    # Default accounts
    default_cash_account_id = SelectField('Default Cash Account', 
                                        coerce=int, 
                                        validators=[Optional()])
    default_bank_account_id = SelectField('Default Bank Account', 
                                        coerce=int, 
                                        validators=[Optional()])
    default_purchase_account_id = SelectField('Default Purchase Account', 
                                            coerce=int, 
                                            validators=[Optional()])
    default_sales_account_id = SelectField('Default Sales Account', 
                                         coerce=int, 
                                         validators=[Optional()])
    default_inventory_account_id = SelectField('Default Inventory Account', 
                                             coerce=int, 
                                             validators=[Optional()])
    default_cogs_account_id = SelectField('Default COGS Account', 
                                        coerce=int, 
                                        validators=[Optional()])
    
    # GST settings
    gst_number = StringField('GST Number', 
                           validators=[Optional(), Length(max=50)])
    place_of_business = StringField('Place of Business', 
                                  validators=[Optional(), Length(max=100)])
    default_gst_rate = DecimalField('Default GST Rate (%)', 
                                  validators=[Optional(), NumberRange(min=0, max=100)], 
                                  default=18.0)
    
    # Payment modes
    enable_upi_payments = BooleanField('Enable UPI Payments', default=True)
    enable_credit_payments = BooleanField('Enable Credit Payments', default=True)
    default_credit_days = IntegerField('Default Credit Days', 
                                     validators=[NumberRange(min=0, max=365)], 
                                     default=30)
    
    submit = SubmitField('Save Settings')

class CostCenterForm(FlaskForm):
    """Form for cost center management"""
    
    name = StringField('Cost Center Name', 
                      validators=[DataRequired(), Length(max=100)])
    code = StringField('Cost Center Code', 
                      validators=[DataRequired(), Length(max=20)])
    description = TextAreaField('Description', 
                               validators=[Optional()])
    parent_center_id = SelectField('Parent Cost Center', 
                                 coerce=int, 
                                 validators=[Optional()])
    monthly_budget = DecimalField('Monthly Budget', 
                                validators=[Optional(), NumberRange(min=0)], 
                                default=0.0)
    yearly_budget = DecimalField('Yearly Budget', 
                               validators=[Optional(), NumberRange(min=0)], 
                               default=0.0)
    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Save Cost Center')

class LedgerMappingForm(FlaskForm):
    """Form for ledger mapping configuration"""
    
    entity_type = SelectField('Entity Type',
                            choices=[('supplier', 'Supplier'),
                                   ('customer', 'Customer'),
                                   ('item_category', 'Item Category'),
                                   ('department', 'Department')],
                            validators=[DataRequired()])
    entity_id = IntegerField('Entity ID', validators=[Optional()])
    entity_name = StringField('Entity Name', validators=[Optional(), Length(max=200)])
    
    receivable_account_id = SelectField('Receivable Account', 
                                      coerce=int, 
                                      validators=[Optional()])
    payable_account_id = SelectField('Payable Account', 
                                   coerce=int, 
                                   validators=[Optional()])
    expense_account_id = SelectField('Expense Account', 
                                   coerce=int, 
                                   validators=[Optional()])
    income_account_id = SelectField('Income Account', 
                                  coerce=int, 
                                  validators=[Optional()])
    cost_center_id = SelectField('Cost Center', 
                               coerce=int, 
                               validators=[Optional()])
    
    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Save Mapping')

class PaymentMethodForm(FlaskForm):
    """Form for payment method configuration"""
    
    name = StringField('Payment Method Name', 
                      validators=[DataRequired(), Length(max=100)])
    code = StringField('Payment Method Code', 
                      validators=[DataRequired(), Length(max=20)])
    method_type = SelectField('Method Type',
                            choices=[('cash', 'Cash'),
                                   ('bank', 'Bank Transfer'),
                                   ('upi', 'UPI'),
                                   ('credit_card', 'Credit Card'),
                                   ('cheque', 'Cheque')],
                            validators=[DataRequired()])
    account_id = SelectField('Associated Account', 
                           coerce=int, 
                           validators=[DataRequired()])
    requires_reference = BooleanField('Requires Reference Number', default=False)
    auto_reconcile = BooleanField('Auto Reconcile', default=False)
    processing_fee_rate = DecimalField('Processing Fee Rate (%)', 
                                     validators=[Optional(), NumberRange(min=0, max=100)], 
                                     default=0.0)
    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Save Payment Method')