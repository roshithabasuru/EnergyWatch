from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField, FloatField, DateTimeLocalField
from wtforms.validators import DataRequired, NumberRange

class CSVUploadForm(FlaskForm):
    csv_file = FileField('Upload Meter Readings CSV', validators=[
        FileRequired(),
        FileAllowed(['csv'], 'CSV files only!')
    ])
    submit = SubmitField('Upload Data')

class ManualReadingForm(FlaskForm):
    timestamp = DateTimeLocalField('Timestamp', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    kwh_consumed = FloatField('kWh Consumed', validators=[DataRequired(), NumberRange(min=0, message='kWh must be ≥ 0')])
    submit = SubmitField('Add Reading')

