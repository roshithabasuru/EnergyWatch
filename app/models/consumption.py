from app.extensions import db
from datetime import datetime

class MeterReading(db.Model):
    __tablename__ = 'meter_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    meter_id = db.Column(db.String(50), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    kwh_consumed = db.Column(db.Float, nullable=False)
    
    # Composite unique constraint to avoid duplicate uploads
    __table_args__ = (
        db.UniqueConstraint('meter_id', 'timestamp', name='_meter_timestamp_uc'),
    )

class ConsumptionSummary(db.Model):
    __tablename__ = 'consumption_summary'
    
    id = db.Column(db.Integer, primary_key=True)
    meter_id = db.Column(db.String(50), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_kwh = db.Column(db.Float, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('meter_id', 'date', name='_meter_date_uc'),
    )
