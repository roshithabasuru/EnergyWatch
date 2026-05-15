import pytest
from app import create_app
from app.extensions import db
from app.models.grid import Zone
from app.models.pricing import PricingTier
from app.models.user import User

@pytest.fixture
def app():
    _app = create_app()
    _app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })

    with _app.app_context():
        db.create_all()
        yield _app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_password_hashing(app):
    """Test that passwords are correctly hashed and checked"""
    u = User(email='test@example.com', role='CONSUMER')
    u.set_password('mypassword123')
    
    assert u.password_hash is not None
    assert u.check_password('mypassword123') is True
    assert u.check_password('wrongpassword') is False

def test_zone_creation(app):
    """Test that a Zone object can be created and saved"""
    z = Zone(name='Zone Alpha', substation='Sub-A', capacity_mw=100.5)
    db.session.add(z)
    db.session.commit()
    
    fetched = Zone.query.filter_by(name='Zone Alpha').first()
    assert fetched is not None
    assert fetched.capacity_mw == 100.5

def test_pricing_tier_logic(app):
    """Test pricing tier initialization limitations"""
    t = PricingTier(name='Test Peak', rate_per_kwh=10.0, start_hour=14, end_hour=18)
    assert t.name == 'Test Peak'
    assert t.rate_per_kwh == 10.0
    assert t.start_hour == 14
    assert t.end_hour == 18
