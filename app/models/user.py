from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='CONSUMER') # CONSUMER, OPERATOR
    
    profile = db.relationship('ConsumerProfile', backref='user', uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ConsumerProfile(db.Model):
    __tablename__ = 'consumer_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    full_name = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    meter_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    alert_preference = db.Column(db.String(20), default='email') # email, sms, both
    pincode = db.Column(db.String(10), nullable=True)  # Used for auto zone assignment
    
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=True)
    
    zone = db.relationship('Zone')
