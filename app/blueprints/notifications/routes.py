from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.blueprints.notifications import notifications_bp
from app.models.alert import Notification
from app.utils.decorators import require_role

@notifications_bp.route('/inbox', methods=['GET'])
@login_required
@require_role('CONSUMER')
def inbox():
    # Order by unread first, then by date descending
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.status.desc(), 
        Notification.created_at.desc()
    ).all()
    
    return render_template('notifications/inbox.html', notifications=notifications)

@notifications_bp.route('/read/<int:id>', methods=['POST'])
@login_required
@require_role('CONSUMER')
def mark_read(id):
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    notif.status = 'READ'
    db.session.commit()
    return redirect(url_for('notifications.inbox'))

@notifications_bp.route('/clear', methods=['POST'])
@login_required
@require_role('CONSUMER')
def clear_all():
    notifications = Notification.query.filter_by(user_id=current_user.id, status='READ').all()
    for notif in notifications:
        db.session.delete(notif)
    db.session.commit()
    flash('Cleared all read notifications.', 'success')
    return redirect(url_for('notifications.inbox'))
