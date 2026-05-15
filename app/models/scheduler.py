from app.extensions import db

class LoadSchedule(db.Model):
    __tablename__ = 'load_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    consumer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    appliance_type = db.Column(db.String(50), nullable=False) # AC, EV Charger, Water Heater, Other
    custom_name = db.Column(db.String(100), nullable=True) # Used if appliance_type == 'Other'
    
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    frequency = db.Column(db.String(20), default='DAILY')
    status = db.Column(db.String(20), default='ACTIVE')
    
    user = db.relationship('User', backref='schedules')
