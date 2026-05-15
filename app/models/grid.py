from app.extensions import db

class Zone(db.Model):
    __tablename__ = 'zones'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    substation = db.Column(db.String(100), nullable=False)
    capacity_mw = db.Column(db.Float, nullable=False)
    pincode = db.Column(db.String(10), nullable=True, unique=True, index=True)  # For auto-assignment

    # Note: relationships will be built for DREvents and Pricing if needed,
    # but initially models are kept simple.
