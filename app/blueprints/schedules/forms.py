from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TimeField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from app.models.pricing import PricingTier
from datetime import datetime

class LoadScheduleForm(FlaskForm):
    appliance_type = SelectField('Appliance Type', choices=[
        ('AC', 'Air Conditioner'),
        ('EV Charger', 'EV Charger'),
        ('Water Heater', 'Water Heater'),
        ('Washing Machine', 'Washing Machine'),
        ('Dishwasher', 'Dishwasher'),
        ('Other', 'Other (Specify)')
    ], validators=[DataRequired()])
    
    custom_name = StringField('Custom Name (if using Other)', validators=[Optional()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[DataRequired()])
    end_time = TimeField('End Time', format='%H:%M', validators=[DataRequired()])
    
    submit = SubmitField('Save Schedule')
    
    def validate_end_time(self, field):
        if self.start_time.data and field.data:
            if field.data == self.start_time.data:
                raise ValidationError('End time must be different from start time.')

    # Business Logic Validation: Ensure consumers aren't scheduling loads during Peak pricing
    def validate_schedule(self):
        # We need context for the request, though we can't reliably pass context to a form method easily.
        # So we'll handle peak validation in the route itself.
        pass

class AlertRuleForm(FlaskForm):
    rule_type = SelectField('Alert Period', choices=[
        ('DAILY_THRESHOLD', 'Daily (kWh/day)'),
        ('WEEKLY_THRESHOLD', 'Weekly (kWh/week)'),
        ('MONTHLY_THRESHOLD', 'Monthly (kWh/month)')
    ], validators=[DataRequired()])
    threshold_kwh = FloatField('Threshold (kWh)', validators=[
        DataRequired(), 
        NumberRange(min=1, message="Threshold must be at least 1 kWh.")
    ])
    submit = SubmitField('Set Threshold Alert')
