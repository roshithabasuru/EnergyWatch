from flask import Flask
from app.config import Config
from app.extensions import db, migrate, login_manager, mail, limiter
from app.models import user, grid, pricing # Ensure models are loaded for migrate

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions here
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # Register blueprints here
    from app.blueprints.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    # Will add UI routes later or register them differently if API vs UI

    from app.blueprints.consumer.routes import consumer_bp
    app.register_blueprint(consumer_bp, url_prefix='/consumer')

    from app.blueprints.main.routes import main_bp
    app.register_blueprint(main_bp)

    from app.blueprints.operator import operator_bp
    app.register_blueprint(operator_bp, url_prefix='/operator')

    from app.blueprints.consumption import consumption_bp
    app.register_blueprint(consumption_bp, url_prefix='/consumption')

    from app.blueprints.demand_response import dr_bp
    app.register_blueprint(dr_bp, url_prefix='/dr')

    from app.blueprints.schedules import schedules_bp
    app.register_blueprint(schedules_bp, url_prefix='/automations')

    from app.blueprints.notifications import notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    from app.blueprints.billing import billing_bp
    app.register_blueprint(billing_bp, url_prefix='/billing')

    # Context processor to inject unread notification count globally
    @app.context_processor
    def inject_unread_count():
        from flask_login import current_user
        from app.models.alert import Notification
        count = 0
        if current_user.is_authenticated and current_user.role == 'CONSUMER':
            count = Notification.query.filter(Notification.user_id == current_user.id, Notification.status != 'READ').count()
        return dict(unread_notifications=count)

    # Custom error handlers
    from flask_limiter.errors import RateLimitExceeded
    from flask import render_template
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return render_template('errors/429.html', title='Too Many Attempts'), 429

    return app
