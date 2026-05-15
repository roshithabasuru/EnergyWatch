from flask import Blueprint

consumer_bp = Blueprint('consumer', __name__)

from app.blueprints.consumer import routes
