from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                # Log the failed authorization attempt (no PII — only user_id, role, and endpoint)
                try:
                    from app.extensions import db
                    from app.models.audit import AuditLog
                    user_id = current_user.id if current_user.is_authenticated else 0
                    log = AuditLog(
                        user_id=user_id,
                        action='UNAUTHORIZED_ACCESS_ATTEMPT',
                        resource_type='Endpoint',
                        resource_id=None,
                        details=f'Required role: {role} | Endpoint: {request.endpoint} | IP: {request.remote_addr}'
                    )
                    log.save()
                    db.session.commit()
                except Exception:
                    pass  # Never let audit logging break the app
                flash('You do not have permission to access that page.', 'danger')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
