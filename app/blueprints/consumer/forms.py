from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, Optional
from app.models.grid import Zone

class ConsumerProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    
    # Address must have at least letters + digits (e.g. "12 MG Road, Chennai")
    address = StringField('Address', validators=[
        DataRequired(),
        Length(min=10, max=255),
        Regexp(r'^[a-zA-Z0-9\s,.\-/#]+$', message='Address contains invalid characters.')
    ])
    phone = StringField('Phone Number', validators=[
        Optional(),
        Regexp(r'^\+?[0-9\s\-]{7,20}$', message='Enter a valid phone number.')
    ])
    
    # Pincode for auto zone assignment (no manual zone override)
    pincode = StringField('Pincode', validators=[
        DataRequired(),
        Regexp(r'^\d{6}$', message='Pincode must be exactly 6 digits.')
    ])
    
    
    
    submit = SubmitField('Update Profile')

