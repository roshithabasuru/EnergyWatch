from flask_wtf import FlaskForm
from wtforms import FloatField, DateField, TimeField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, ValidationError
from datetime import datetime, time

class DREventForm(FlaskForm):
    zone_id = SelectField('Target Zone', coerce=int, validators=[DataRequired()])
    target_reduction = FloatField('Target Reduction (%)', validators=[DataRequired(), NumberRange(min=1, max=100)])
    incentive = FloatField('Incentive (₹/kWh)', validators=[DataRequired(), NumberRange(min=0.1)])
    
    event_date = DateField('Event Date', format='%Y-%m-%d', validators=[DataRequired()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[DataRequired()])
    end_time = TimeField('End Time', format='%H:%M', validators=[DataRequired()])
    
    submit = SubmitField('Create DR Event')
    
    def validate_end_time(self, field):
        if self.start_time.data and field.data:
            if field.data <= self.start_time.data:
                raise ValidationError('End time must be after start time.')
                
    def validate_event_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError('Event date cannot be in the past.')
            
    def validate_start_time(self, field):
        if self.event_date.data and field.data:
            event_dt = datetime.combine(self.event_date.data, field.data)
            now = datetime.now()
            # If event is in the past, only reject if it's more than 5 mins ago
            if event_dt < now and (now - event_dt).total_seconds() > 300:
                raise ValidationError(f'Event start time cannot be in the past. (Server time: {now.strftime("%H:%M")})')
