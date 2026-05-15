from app.extensions import db
from datetime import datetime

class AlertRule(db.Model):
    __tablename__ = 'alert_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    consumer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # E.g. "DAILY_THRESHOLD"
    rule_type = db.Column(db.String(50), nullable=False, default='DAILY_THRESHOLD')
    threshold_kwh = db.Column(db.Float, nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref='alert_rules')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='QUEUED') # QUEUED, SENT, FAILED
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')
