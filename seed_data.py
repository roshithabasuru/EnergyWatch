from app.extensions import db
from app import create_app
from app.models.grid import Zone
from app.models.pricing import PricingTier
from app.models.user import User, ConsumerProfile

app = create_app()
with app.app_context():
    # Clear existing data to avoid unique constraint errors during multiple runs
    db.session.query(ConsumerProfile).delete()
    db.session.query(User).delete()
    db.session.query(PricingTier).delete()
    db.session.query(Zone).delete()
    db.session.commit()

    # Zones
    z1 = Zone(name='North Grid', substation='Substation A', capacity_mw=50)
    z2 = Zone(name='South Grid', substation='Substation B', capacity_mw=75)
    db.session.add_all([z1, z2])
    
    # Pricing
    peak = PricingTier(name='Peak', rate_per_kwh=8.0, start_hour=6, end_hour=10)
    offpeak = PricingTier(name='Off-Peak', rate_per_kwh=4.0, start_hour=23, end_hour=6)
    shoulder = PricingTier(name='Shoulder', rate_per_kwh=6.0, start_hour=10, end_hour=23)
    db.session.add_all([peak, offpeak, shoulder])
    
    # Sample Consumer
    user = User(email='consumer@example.com', role='CONSUMER')
    user.set_password('Password123!')
    db.session.add(user)
    
    # Sample Operator
    operator = User(email='operator@example.com', role='OPERATOR')
    operator.set_password('Admin123!')
    db.session.add(operator)
    
    db.session.flush()
    
    profile = ConsumerProfile(user_id=user.id, meter_id='MTR1234567', zone_id=z1.id)
    db.session.add(profile)
    
    db.session.commit()
    print("Seed data loaded successfully!")
