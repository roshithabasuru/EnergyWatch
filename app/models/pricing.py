from app.extensions import db
from datetime import datetime

class PricingTier(db.Model):
    __tablename__ = 'pricing_tiers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False) # Peak, Off-Peak, Shoulder
    rate_per_kwh = db.Column(db.Float, nullable=False)
    start_hour = db.Column(db.Integer, nullable=False) # 0-23
    end_hour = db.Column(db.Integer, nullable=False) # 0-23
    effective_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
