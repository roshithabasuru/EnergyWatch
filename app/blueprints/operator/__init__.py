from flask import Blueprint

operator_bp = Blueprint('operator', __name__)

from app.blueprints.operator import routes
