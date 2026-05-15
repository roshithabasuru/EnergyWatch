from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Regexp

class ZoneForm(FlaskForm):
    name = StringField('Zone Name', validators=[DataRequired()])
    substation = StringField('Substation Name', validators=[DataRequired()])
    capacity_mw = FloatField('Capacity (MW)', validators=[DataRequired(), NumberRange(min=0.1)])
    pincode = StringField('Pincode (for consumer auto-assignment)', validators=[
        Optional(),
        Regexp(r'^\d{6}$', message='Pincode must be exactly 6 digits.')
    ])
    submit = SubmitField('Save Zone')

class PricingTierForm(FlaskForm):
    name = StringField('Tier Name', validators=[DataRequired()])
    rate_per_kwh = FloatField('Rate per kWh (₹)', validators=[DataRequired(), NumberRange(min=0)])
    start_hour = IntegerField('Start Hour (0-23)', validators=[DataRequired(), NumberRange(min=0, max=23)])
    end_hour = IntegerField('End Hour (0-23)', validators=[DataRequired(), NumberRange(min=0, max=23)])
    submit = SubmitField('Save Pricing Tier')
