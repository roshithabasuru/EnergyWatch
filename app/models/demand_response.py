from app.extensions import db

class DREvent(db.Model):
    __tablename__ = 'demand_response_events'
    
    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=False)
    target_reduction = db.Column(db.Float, nullable=False) # % reduction expected
    incentive = db.Column(db.Float, nullable=False) # Reward in Rupees per kWh saved
    
    event_start = db.Column(db.DateTime, nullable=False)
    event_end = db.Column(db.DateTime, nullable=False)
    baseline_kwh = db.Column(db.Float, nullable=True) # Average of last 3 similar weekdays
    status = db.Column(db.String(20), default='SCHEDULED') # SCHEDULED, ACTIVE, COMPLETED, CANCELLED
    
    zone = db.relationship('Zone', backref='dr_events')
    
    __table_args__ = (
        db.UniqueConstraint('zone_id', 'event_start', name='_zone_event_start_uc'),
    )


class EventEnrollment(db.Model):
    __tablename__ = 'event_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('demand_response_events.id'), nullable=False)
    consumer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, OPTED_OUT
    
    event = db.relationship('DREvent', backref='enrollments')
    user = db.relationship('User', backref='event_enrollments')
    
    __table_args__ = (
        db.UniqueConstraint('event_id', 'consumer_id', name='_event_consumer_uc'),
    )
