from flask import Blueprint

dr_bp = Blueprint('demand_response', __name__)

from app.blueprints.demand_response import routes
