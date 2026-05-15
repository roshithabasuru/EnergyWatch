from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app.extensions import db
from app.blueprints.demand_response import dr_bp
from app.blueprints.demand_response.forms import DREventForm
from app.models.grid import Zone
from app.models.demand_response import DREvent, EventEnrollment
from app.models.alert import Notification
from app.utils.decorators import require_role

@dr_bp.route('/operator/events', methods=['GET'])
@login_required
@require_role('OPERATOR')
def events_list():
    events = DREvent.query.order_by(DREvent.event_start.desc()).all()
    return render_template('demand_response/operator_list.html', events=events)

@dr_bp.route('/operator/new', methods=['GET', 'POST'])
@login_required
@require_role('OPERATOR')
def new_event():
    form = DREventForm()
    form.zone_id.choices = [(z.id, z.name) for z in Zone.query.all()]
    
    if form.validate_on_submit():
        event_start = datetime.combine(form.event_date.data, form.start_time.data)
        event_end = datetime.combine(form.event_date.data, form.end_time.data)
        
        try:
            with db.session.begin_nested(): # Transaction savepoint
                # ATOMICITY: Lock the target zone record specifically using with_for_update
                zone = Zone.query.filter_by(id=form.zone_id.data).with_for_update().first()
                if not zone:
                    raise Exception("Zone not found.")
                
                # Check for overlapping events in the same zone (2-hour buffer)
                from datetime import timedelta
                buffer = timedelta(hours=2)
                existing = DREvent.query.filter(
                    DREvent.zone_id == zone.id,
                    DREvent.status != 'CANCELLED',
                    DREvent.event_start < (event_end + buffer),
                    DREvent.event_end > (event_start - buffer)
                ).first()
                
                if existing:
                    flash('Conflict: Overlapping event exists within a 2-hour window in this Zone.', 'danger')
                    return render_template('demand_response/new.html', form=form)
                
                # Baseline Calculation (average of last 3 similar weekdays)
                from sqlalchemy.sql import func
                from app.models.consumption import ConsumptionSummary
                from app.models.user import ConsumerProfile
                
                target_weekday = event_start.weekday()
                past_dates = []
                curr_date = event_start.date() - timedelta(days=1)
                while len(past_dates) < 3 and curr_date >= event_start.date() - timedelta(days=30):
                    if curr_date.weekday() == target_weekday:
                        past_dates.append(curr_date)
                    curr_date -= timedelta(days=1)
                
                baseline = 0.0
                if past_dates:
                    res = db.session.query(func.avg(ConsumptionSummary.total_kwh)).join(
                        ConsumerProfile, ConsumptionSummary.meter_id == ConsumerProfile.meter_id
                    ).filter(
                        ConsumerProfile.zone_id == zone.id,
                        ConsumptionSummary.date.in_(past_dates)
                    ).scalar()
                    baseline = float(res or 0.0)
                
                # Create the event
                event = DREvent(
                    zone_id=zone.id,
                    target_reduction=form.target_reduction.data,
                    incentive=form.incentive.data,
                    event_start=event_start,
                    event_end=event_end,
                    baseline_kwh=baseline,
                    status='SCHEDULED'
                )
                db.session.add(event)
                db.session.flush() # Ensure event.id is generated
                
                # Enqueue notifications to opted-in consumers in that zone
                # For simplicity, we assume anyone in the zone gets a notification, and they can OPT IN.
                # The prompt asks consumers to enroll in advance or per event?
                # "Consumers opt-in for events... POST /api/demand-response/enroll/:eventId"
                # So we notify ALL consumers in the zone that an event was created so they can opt in.
                from app.models.user import ConsumerProfile, User
                profiles = ConsumerProfile.query.filter_by(zone_id=zone.id).all()
                for p in profiles:
                    msg = f"New Demand-Response Event in {zone.name} on {event_start.strftime('%Y-%m-%d %H:%M')}. Earn ₹{event.incentive}/kWh!"
                    db.session.add(Notification(user_id=p.user_id, message=msg))
                    # Real Email Dispatch
                    consumer_user = User.query.get(p.user_id)
                    
                    if consumer_user.email:
                        try:
                            from flask_mail import Message
                            from app.extensions import mail
                            msg_email = Message(
                                subject=f"EnergyWatch - New DR Event in {zone.name}",
                                recipients=[consumer_user.email],
                                body=msg
                            )
                            mail.send(msg_email)
                        except Exception as mail_err:
                            # Log email failure but don't crash event creation
                            print(f"Failed to send email to {consumer_user.email}: {str(mail_err)}")
                            
                from app.models.audit import AuditLog
                log = AuditLog(user_id=current_user.id, action='Create DREvent', resource_type='DREvent', resource_id=event.id, details=f'Zone: {zone.name}, Reduc: {event.target_reduction}%')
                log.save()
                    
            db.session.commit()
            flash('Demand Response Event successfully created & Notifications queued.', 'success')
            return redirect(url_for('demand_response.events_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {str(e)}', 'danger')

    return render_template('demand_response/new.html', form=form)

@dr_bp.route('/consumer/events', methods=['GET'])
@login_required
@require_role('CONSUMER')
def consumer_events():
    zone_id = current_user.profile.zone_id
    if not zone_id:
        flash("You are not assigned to a zone yet.", "warning")
        return redirect(url_for('consumer.profile'))
        
    events = DREvent.query.filter(
        DREvent.zone_id == zone_id,
        DREvent.event_end > datetime.now()
    ).order_by(DREvent.event_start.asc()).all()
    
    # Pass along enrolled event IDs to disable/highlight buttons
    enrollments = {e.event_id: e for e in current_user.event_enrollments if e.status == 'ACTIVE'}
    return render_template('demand_response/consumer_events.html', events=events, enrollments=enrollments)

@dr_bp.route('/consumer/enroll/<int:event_id>', methods=['POST'])
@login_required
@require_role('CONSUMER')
def enroll(event_id):
    event = DREvent.query.get_or_404(event_id)
    if event.zone_id != current_user.profile.zone_id:
        flash("This event is not active in your zone.", "danger")
        return redirect(url_for('demand_response.consumer_events'))
        
    enr = EventEnrollment.query.filter_by(event_id=event_id, consumer_id=current_user.id).first()
    if enr:
        if enr.status == 'OPTED_OUT':
            enr.status = 'ACTIVE'
            flash("You have successfully opted back into the event!", "success")
        else:
            flash("You are already enrolled.", "info")
    else:
        enr = EventEnrollment(event_id=event_id, consumer_id=current_user.id, status='ACTIVE')
        db.session.add(enr)
        flash("You have successfully enrolled! Thank you for participating.", "success")
        
    db.session.commit()
    return redirect(url_for('demand_response.consumer_events'))

@dr_bp.route('/consumer/optout/<int:event_id>', methods=['POST'])
@login_required
@require_role('CONSUMER')
def optout(event_id):
    enr = EventEnrollment.query.filter_by(event_id=event_id, consumer_id=current_user.id).first_or_404()
    enr.status = 'OPTED_OUT'
    db.session.commit()
    flash("You have opted out of the event.", "warning")
    return redirect(url_for('demand_response.consumer_events'))
