from flask import render_template, request, flash, redirect, url_for
from app.blueprints.consumer import consumer_bp
from app.blueprints.consumer.forms import ConsumerProfileForm
from app.extensions import db
from app.models.grid import Zone
from app.models.audit import AuditLog
from flask_login import current_user, login_required

@consumer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role != 'CONSUMER':
        flash('Only consumers can access this profile page.', 'danger')
        return redirect(url_for('main.index'))
        
    form = ConsumerProfileForm()
    meter_id = current_user.profile.meter_id
    
    if form.validate_on_submit():
        # Auto-assign zone by pincode — consumer cannot directly pick a zone
        pincode = form.pincode.data.strip()
        matched_zone = Zone.query.filter_by(pincode=pincode).first()
        
        if not matched_zone:
            flash(f'Pincode "{pincode}" is not assigned to any zone. Please contact your utility operator.', 'warning')
            return redirect(url_for('consumer.profile'))
        
        current_user.profile.full_name = form.full_name.data
        current_user.profile.address = form.address.data
        current_user.profile.phone = form.phone.data
        current_user.profile.pincode = pincode
        
        # Auto-assign zone — operator-controlled via pincode mapping
        current_user.profile.zone_id = matched_zone.id
        
        # Audit log the profile update
        log = AuditLog(
            user_id=current_user.id,
            action='Consumer Profile Updated',
            resource_type='ConsumerProfile',
            resource_id=current_user.profile.id,
            details=f'Zone auto-assigned: {matched_zone.name} via pincode {pincode}'
        )
        log.save()
        db.session.commit()
        
        flash(f'Profile updated! Zone auto-assigned to: {matched_zone.name}', 'success')
        return redirect(url_for('consumption.dashboard'))
    
    elif request.method == 'GET':
        form.full_name.data = current_user.profile.full_name
        form.address.data = current_user.profile.address
        form.phone.data = current_user.profile.phone
        form.pincode.data = current_user.profile.pincode
        
    current_zone = current_user.profile.zone
        
    return render_template('consumer/profile.html', 
                           title='My Profile', 
                           form=form, 
                           meter_id=meter_id,
                           current_zone=current_zone)


