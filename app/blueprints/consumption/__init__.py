from flask import Blueprint

consumption_bp = Blueprint('consumption', __name__)

from app.blueprints.consumption import routes
