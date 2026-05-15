from app.extensions import db
from datetime import datetime

class Bill(db.Model):
    __tablename__ = 'bills'
    
    id = db.Column(db.Integer, primary_key=True)
    consumer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    billing_month = db.Column(db.Integer, nullable=False) # 1-12
    billing_year = db.Column(db.Integer, nullable=False) # e.g. 2026
    
    total_kwh = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    
    generated_on = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=False)
    
    status = db.Column(db.String(20), default='UNPAID') # UNPAID, PAID
    
    user = db.relationship('User', backref='bills')
    
    __table_args__ = (
        db.UniqueConstraint('consumer_id', 'billing_month', 'billing_year', name='_user_bill_month_uc'),
    )
