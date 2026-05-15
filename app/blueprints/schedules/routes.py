from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.blueprints.schedules import schedules_bp
from app.blueprints.schedules.forms import LoadScheduleForm, AlertRuleForm
from app.models.scheduler import LoadSchedule
from app.models.alert import AlertRule
from app.models.pricing import PricingTier
from app.utils.decorators import require_role

@schedules_bp.route('/dashboard', methods=['GET'])
@login_required
@require_role('CONSUMER')
def dashboard():
    schedule_form = LoadScheduleForm()
    alert_form = AlertRuleForm()
    
    schedules = LoadSchedule.query.filter_by(consumer_id=current_user.id).all()
    alerts = AlertRule.query.filter_by(consumer_id=current_user.id).all()
    pricing_tiers = PricingTier.query.filter_by(is_active=True).all()
    
    return render_template('schedules/dashboard.html', 
                          schedules=schedules, alerts=alerts, 
                          schedule_form=schedule_form, alert_form=alert_form,
                          pricing_tiers=pricing_tiers)

@schedules_bp.route('/schedule/new', methods=['POST'])
@login_required
@require_role('CONSUMER')
def new_schedule():
    form = LoadScheduleForm()
    if form.validate_on_submit():
        if form.appliance_type.data == 'Other' and not form.custom_name.data:
            flash("Please provide a custom name if selecting 'Other'.", "danger")
            return redirect(url_for('schedules.dashboard'))
            
        # Validate: do not allow scheduling in past time windows
        from datetime import datetime, time as dtime
        now = datetime.now()
        start_as_dt = datetime.combine(now.date(), form.start_time.data)
        if start_as_dt < now:
            flash('Cannot schedule appliance in a past time window. Please choose a future time.', 'danger')
            return redirect(url_for('schedules.dashboard'))

        # Validate against Peak pricing
        start_hour = form.start_time.data.hour
        end_hour = form.end_time.data.hour
        
        # Identify the peak tier dynamically by finding the tier with the highest rate
        highest_tier = PricingTier.query.order_by(PricingTier.rate_per_kwh.desc()).first()
        peak_tiers = [highest_tier] if highest_tier else []
        overlap = False
        
        for tier in peak_tiers:
            # Simple check if scheduling block touches the tier block
            if start_hour <= end_hour:
                if start_hour < tier.end_hour and end_hour > tier.start_hour:
                    overlap = True
            else: # Overnight schedule
                if start_hour < tier.end_hour or end_hour > tier.start_hour:
                    overlap = True
                    
        if overlap:
            flash(f"Warning: Your appliance schedule crosses into the '{highest_tier.name}' pricing tier (highest rate). Schedule rejected.", 'danger')
            return redirect(url_for('schedules.dashboard'))
            
        schedule = LoadSchedule(
            consumer_id=current_user.id,
            appliance_type=form.appliance_type.data,
            custom_name=form.custom_name.data if form.appliance_type.data == 'Other' else None,
            start_time=form.start_time.data,
            end_time=form.end_time.data
        )
        db.session.add(schedule)
        db.session.flush()
        
        from app.models.audit import AuditLog
        log = AuditLog(user_id=current_user.id, action='Create LoadSchedule', resource_type='LoadSchedule', resource_id=schedule.id, details=f'Appliance: {schedule.appliance_type}')
        log.save()
        
        db.session.commit()
        flash("Appliance schedule successfully created.", "success")
        
    return redirect(url_for('schedules.dashboard'))

@schedules_bp.route('/schedule/delete/<int:schedule_id>', methods=['POST'])
@login_required
@require_role('CONSUMER')
def delete_schedule(schedule_id):
    schedule = LoadSchedule.query.filter_by(id=schedule_id, consumer_id=current_user.id).first_or_404()
    db.session.delete(schedule)
    db.session.commit()
    flash("Schedule removed successfully.", "success")
    return redirect(url_for('schedules.dashboard'))

@schedules_bp.route('/alert/new', methods=['POST'])
@login_required
@require_role('CONSUMER')
def new_alert():
    form = AlertRuleForm()
    if form.validate_on_submit():
        # Allow multiple rules — one per rule_type, not one global
        rule = AlertRule.query.filter_by(
            consumer_id=current_user.id,
            rule_type=form.rule_type.data
        ).first()
        action_label = ''
        if rule:
            rule.threshold_kwh = form.threshold_kwh.data
            rule.is_active = True
            action_label = 'Update AlertRule'
            flash(f"{form.rule_type.data.replace('_', ' ').title()} alert updated.", "success")
        else:
            rule = AlertRule(
                consumer_id=current_user.id,
                rule_type=form.rule_type.data,
                threshold_kwh=form.threshold_kwh.data
            )
            db.session.add(rule)
            action_label = 'Create AlertRule'
            flash(f"{form.rule_type.data.replace('_', ' ').title()} alert created.", "success")
        
        db.session.flush()
        # Audit log — no PII, just rule type and threshold
        from app.models.audit import AuditLog
        log = AuditLog(
            user_id=current_user.id,
            action=action_label,
            resource_type='AlertRule',
            resource_id=rule.id,
            details=f'Type: {rule.rule_type} | Threshold: {rule.threshold_kwh} kWh'
        )
        log.save()
        db.session.commit()
        
    return redirect(url_for('schedules.dashboard'))


@schedules_bp.route('/alert/toggle/<int:alert_id>', methods=['POST'])
@login_required
@require_role('CONSUMER')
def toggle_alert(alert_id):
    rule = AlertRule.query.filter_by(id=alert_id, consumer_id=current_user.id).first_or_404()
    rule.is_active = not rule.is_active
    db.session.commit()
    status = "activated" if rule.is_active else "deactivated"
    flash(f"Threshold alert successfully {status}.", "success")
    return redirect(url_for('schedules.dashboard'))
