from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from models import UnitOfMeasure, Item

class UnitOfMeasureForm(FlaskForm):
    """Form for creating/editing units of measure"""
    name = StringField('Unit Name', validators=[DataRequired(), Length(max=50)], 
                      render_kw={"placeholder": "e.g., Kilogram, Pieces, Meters"})
    symbol = StringField('Symbol', validators=[DataRequired(), Length(max=10)], 
                        render_kw={"placeholder": "e.g., Kg, Pcs, M"})
    category = SelectField('Category', validators=[DataRequired()], 
                          choices=[
                              ('Weight', 'Weight (Kg, g, ton)'),
                              ('Count', 'Count (Pieces, Units)'),
                              ('Length', 'Length (M, cm, ft)'),
                              ('Volume', 'Volume (L, ml, gal)'),
                              ('Area', 'Area (sq.m, sq.ft)'),
                              ('Other', 'Other')
                          ])
    is_base_unit = BooleanField('Base Unit for Category')
    description = TextAreaField('Description', validators=[Optional()], 
                               render_kw={"rows": 3, "placeholder": "Optional description"})
    submit = SubmitField('Save Unit')

class UOMConversionForm(FlaskForm):
    """Form for setting up global UOM conversions"""
    from_unit = SelectField('From Unit', validators=[DataRequired()], coerce=int)
    to_unit = SelectField('To Unit', validators=[DataRequired()], coerce=int)
    conversion_factor = DecimalField('Conversion Factor', validators=[DataRequired(), NumberRange(min=0.000001)],
                                   render_kw={"step": "0.000001", "placeholder": "e.g., 1000 (1 Kg = 1000 g)"})
    notes = TextAreaField('Notes', validators=[Optional()], 
                         render_kw={"rows": 2, "placeholder": "e.g., Standard conversion factor"})
    submit = SubmitField('Save Conversion')
    
    def __init__(self, *args, **kwargs):
        super(UOMConversionForm, self).__init__(*args, **kwargs)
        units = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        self.from_unit.choices = [(u.id, f"{u.name} ({u.symbol})") for u in units]
        self.to_unit.choices = [(u.id, f"{u.name} ({u.symbol})") for u in units]

class ItemUOMConversionForm(FlaskForm):
    """Form for setting up item-specific UOM conversions"""
    item = SelectField('Item', validators=[DataRequired()], coerce=int)
    
    # Unit selections
    purchase_unit = SelectField('Purchase Unit (What you buy in)', validators=[DataRequired()], coerce=int)
    inventory_unit = SelectField('Inventory Unit (What you track in)', validators=[DataRequired()], coerce=int)
    sale_unit = SelectField('Sale Unit (What you sell in)', validators=[DataRequired()], coerce=int)
    
    # Conversion factors
    purchase_to_inventory = DecimalField('Purchase to Inventory Factor', 
                                       validators=[DataRequired(), NumberRange(min=0.000001)],
                                       render_kw={"step": "0.000001", "placeholder": "1 purchase unit = ? inventory units"})
    inventory_to_sale = DecimalField('Inventory to Sale Factor', 
                                   validators=[DataRequired(), NumberRange(min=0.000001)],
                                   render_kw={"step": "0.000001", "placeholder": "1 inventory unit = ? sale units"})
    
    # Optional metadata
    weight_per_piece = DecimalField('Weight per Piece (Kg)', validators=[Optional(), NumberRange(min=0.0001)],
                                  render_kw={"step": "0.0001", "placeholder": "e.g., 0.025 (25 grams per piece)"})
    pieces_per_kg = DecimalField('Pieces per Kg', validators=[Optional(), NumberRange(min=0.01)],
                               render_kw={"step": "0.01", "placeholder": "e.g., 40 (40 pieces per Kg)"})
    
    notes = TextAreaField('Notes', validators=[Optional()], 
                         render_kw={"rows": 3, "placeholder": "e.g., Based on average weight measurements"})
    
    submit = SubmitField('Save Item Conversion')
    
    def __init__(self, *args, **kwargs):
        super(ItemUOMConversionForm, self).__init__(*args, **kwargs)
        
        # Populate item choices
        items = Item.query.order_by(Item.name).all()
        self.item.choices = [(i.id, f"{i.name} ({i.code})") for i in items]
        
        # Populate unit choices
        units = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        unit_choices = [(u.id, f"{u.name} ({u.symbol}) - {u.category}") for u in units]
        
        self.purchase_unit.choices = unit_choices
        self.inventory_unit.choices = unit_choices
        self.sale_unit.choices = unit_choices

class UOMCalculatorForm(FlaskForm):
    """Form for quick UOM calculations"""
    item = SelectField('Item', validators=[DataRequired()], coerce=int)
    quantity = DecimalField('Quantity', validators=[DataRequired(), NumberRange(min=0.0001)],
                          render_kw={"step": "0.0001"})
    from_unit = SelectField('From Unit', validators=[DataRequired()], coerce=int)
    to_unit = SelectField('To Unit', validators=[DataRequired()], coerce=int)
    calculate = SubmitField('Calculate')
    
    def __init__(self, *args, **kwargs):
        super(UOMCalculatorForm, self).__init__(*args, **kwargs)
        
        # Populate item choices
        items = Item.query.order_by(Item.name).all()
        self.item.choices = [(i.id, f"{i.name} ({i.code})") for i in items]
        
        # Populate unit choices
        units = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        unit_choices = [(u.id, f"{u.name} ({u.symbol})") for u in units]
        
        self.from_unit.choices = unit_choices
        self.to_unit.choices = unit_choices