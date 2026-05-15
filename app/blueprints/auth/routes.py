from flask import render_template, redirect, url_for, flash, request
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import RegistrationForm, LoginForm
from app.extensions import db, login_manager, limiter
from app.models.user import User, ConsumerProfile
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, role='CONSUMER')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush() # flush to get user.id before profile creation
        
        profile = ConsumerProfile(user_id=user.id, meter_id=form.meter_id.data)
        db.session.add(profile)
        db.session.commit()
        
        flash('Registration successful! You are now able to log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        # Do not reveal whether account exists on error per requirements
        generic_error = 'Invalid email or password'
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash(generic_error, 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            if user.role == 'CONSUMER':
                next_page = url_for('consumption.dashboard')
            else:
                next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title='Login', form=form)

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for('main.index'))

from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def get_reset_token(user, expires_sec=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps({'user_id': user.id})

def verify_reset_token(token, expires_sec=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, max_age=expires_sec)['user_id']
    except:
        return None
    return User.query.get(user_id)

@auth_bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    from app.blueprints.auth.forms import RequestResetForm
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        token = get_reset_token(user)
        reset_link = url_for('auth.reset_token', token=token, _external=True)
        # Try sending real email via Flask-Mail
        email_sent = False
        try:
            from flask_mail import Message
            from app.extensions import mail
            from flask import current_app
            msg = Message(
                subject='EnergyWatch — Password Reset Request',
                sender=current_app.config.get('MAIL_USERNAME', 'noreply@energywatch.com'),
                recipients=[user.email]
            )
            msg.body = f"""Hello,

You requested a password reset for your EnergyWatch account.

Click the link below to reset your password (expires in 1 hour):
{reset_link}

If you did not request this, please ignore this email.

— EnergyWatch Security Team
"""
            mail.send(msg)
            email_sent = True
            flash(f'Password reset link sent to {user.email}. Please check your inbox.', 'success')
            reset_link = None  # Hide on-page link since email was sent
        except Exception as e:
            # SMTP not configured — fall back to showing link on page
            print(f"[PASSWORD RESET] Email failed ({e}). Showing link on page for: {user.email}")
            flash('Failed to send email. You can use the link provided on the page.', 'warning')
            
        if not email_sent:
            return render_template('auth/reset_request.html', title='Reset Password', form=form, reset_link=reset_link)
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html', title='Reset Password', form=form)

@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('auth.reset_request'))
    from app.blueprints.auth.forms import ResetPasswordForm
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_token.html', title='Reset Password', form=form)
