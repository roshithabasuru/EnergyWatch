from flask import render_template, request, flash, redirect, url_for
from app.blueprints.operator import operator_bp
from app.blueprints.operator.forms import ZoneForm, PricingTierForm
from app.models.grid import Zone
from app.models.pricing import PricingTier
from app.utils.decorators import require_role
from app.extensions import db
from flask_login import login_required

@operator_bp.route('/dashboard')
@login_required
@require_role('OPERATOR')
def dashboard():
    zones = Zone.query.all()
    pricing = PricingTier.query.filter_by(is_active=True).all()
    
    from app.models.user import ConsumerProfile
    from app.models.demand_response import DREvent, EventEnrollment
    from app.models.consumption import ConsumptionSummary
    from sqlalchemy import func
    from datetime import datetime, timedelta

    total_consumers = ConsumerProfile.query.count()
    active_events = DREvent.query.filter_by(status='ACTIVE').count()

    # Card: Estimated current grid load in MW (sum of last 24h kWh / 24 / 1000)
    yesterday = datetime.now().date() - timedelta(days=1)
    kwh_24h = db.session.query(func.sum(ConsumptionSummary.total_kwh)).filter(
        ConsumptionSummary.date >= yesterday
    ).scalar() or 0.0
    grid_load_mw = round(kwh_24h / 24 / 1000, 3)  # average MW over 24h

    # Card: DR Participation rate (enrolled active / consumers in zones with active events)
    active_event_ids = [e.id for e in DREvent.query.filter_by(status='ACTIVE').all()]
    enrolled_count = 0
    eligible_count = 0
    if active_event_ids:
        enrolled_count = EventEnrollment.query.filter(
            EventEnrollment.event_id.in_(active_event_ids),
            EventEnrollment.status == 'ACTIVE'
        ).count()
        active_zone_ids = [e.zone_id for e in DREvent.query.filter_by(status='ACTIVE').all()]
        eligible_count = ConsumerProfile.query.filter(
            ConsumerProfile.zone_id.in_(active_zone_ids)
        ).count()
    participation_rate = round((enrolled_count / eligible_count * 100), 1) if eligible_count else 0.0

    return render_template('operator/dashboard.html', title='Operator Dashboard', 
                           zones=zones, pricing=pricing,
                           total_consumers=total_consumers, active_events=active_events,
                           grid_load_mw=grid_load_mw, participation_rate=participation_rate)

import csv
from io import StringIO
from flask import Response

@operator_bp.route('/api/operator/consumption.csv')
@login_required
@require_role('OPERATOR')
def export_consumption_csv():
    from app.models.consumption import MeterReading
    from app.models.user import ConsumerProfile
    from datetime import datetime
    
    zone_id = request.args.get('zone_id')
    date_from = request.args.get('date_from')  # YYYY-MM-DD
    date_to   = request.args.get('date_to')    # YYYY-MM-DD
    
    query = db.session.query(MeterReading, ConsumerProfile).join(
        ConsumerProfile, MeterReading.meter_id == ConsumerProfile.meter_id
    )
    if zone_id:
        query = query.filter(ConsumerProfile.zone_id == zone_id)
    if date_from:
        try:
            query = query.filter(MeterReading.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(MeterReading.timestamp <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass
        
    readings = query.order_by(MeterReading.timestamp.desc()).limit(5000).all()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        # No PII — no name, email, phone; only meter_id and zone_id
        writer.writerow(('Meter ID', 'Zone ID', 'Timestamp', 'kWh Consumed'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)
        for reading, profile in readings:
            writer.writerow((reading.meter_id, profile.zone_id, reading.timestamp, reading.kwh_consumed))
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)
            
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment; filename=consumption_export.csv"})

from flask import jsonify
@operator_bp.route('/api/operator/grid_health')
@login_required
@require_role('OPERATOR')
def grid_health_data():
    from app.models.consumption import ConsumptionSummary
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    
    results = db.session.query(
        ConsumptionSummary.date, 
        func.sum(ConsumptionSummary.total_kwh)
    ).filter(
        ConsumptionSummary.date >= thirty_days_ago
    ).group_by(ConsumptionSummary.date).order_by(ConsumptionSummary.date.asc()).all()
    
    labels = [r[0].strftime('%b %d') for r in results]
    data = [float(r[1]) for r in results]
    
    return jsonify({"labels": labels, "data": data})

@operator_bp.route('/api/operator/zone_heatmap')
@login_required
@require_role('OPERATOR')
def zone_heatmap_data():
    """Returns zone-wise aggregated kWh consumption for the last 24 hours."""
    from app.models.consumption import MeterReading
    from app.models.user import ConsumerProfile
    from app.models.grid import Zone
    from datetime import datetime, timedelta
    from sqlalchemy import func

    since = datetime.now() - timedelta(hours=24)
    results = db.session.query(
        ConsumerProfile.zone_id,
        func.sum(MeterReading.kwh_consumed).label('total_kwh')
    ).join(
        MeterReading, MeterReading.meter_id == ConsumerProfile.meter_id
    ).filter(
        MeterReading.timestamp >= since
    ).group_by(ConsumerProfile.zone_id).all()

    zone_map = {z.id: z.name for z in Zone.query.all()}
    labels = [zone_map.get(r.zone_id, f'Zone {r.zone_id}') for r in results]
    data   = [round(float(r.total_kwh), 2) for r in results]

    return jsonify({"labels": labels, "data": data})

@operator_bp.route('/zone/new', methods=['GET', 'POST'])
@login_required
@require_role('OPERATOR')
def new_zone():
    form = ZoneForm()
    if form.validate_on_submit():
        zone = Zone(name=form.name.data, substation=form.substation.data,
                    capacity_mw=form.capacity_mw.data, pincode=form.pincode.data or None)
        db.session.add(zone)
        db.session.commit()
        flash('Zone created successfully.', 'success')
        return redirect(url_for('operator.dashboard'))
    return render_template('operator/form.html', title='New Zone', form=form, subject='Zone')

@operator_bp.route('/zone/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@require_role('OPERATOR')
def edit_zone(id):
    zone = Zone.query.get_or_404(id)
    form = ZoneForm(obj=zone)
    if form.validate_on_submit():
        zone.name = form.name.data
        zone.substation = form.substation.data
        zone.capacity_mw = form.capacity_mw.data
        zone.pincode = form.pincode.data or None
        db.session.commit()
        flash('Zone updated successfully.', 'success')
        return redirect(url_for('operator.dashboard'))
    return render_template('operator/form.html', title='Edit Zone', form=form, subject='Zone')

@operator_bp.route('/pricing/new', methods=['GET', 'POST'])
@login_required
@require_role('OPERATOR')
def new_pricing():
    form = PricingTierForm()
    if form.validate_on_submit():
        tier = PricingTier(name=form.name.data, rate_per_kwh=form.rate_per_kwh.data,
                           start_hour=form.start_hour.data, end_hour=form.end_hour.data)
        
        # Validate non-overlapping time bands
        active_tiers = PricingTier.query.filter_by(is_active=True).all()
        for existing in active_tiers:
            if _hours_overlap(form.start_hour.data, form.end_hour.data, existing.start_hour, existing.end_hour):
                flash(f'Time band conflicts with existing tier "{existing.name}" ({existing.start_hour}:00–{existing.end_hour}:00).', 'danger')
                return render_template('operator/form.html', title='New Pricing Tier', form=form, subject='Pricing Tier')
        
        db.session.add(tier)
        db.session.flush()
        
        from app.models.audit import AuditLog
        from flask_login import current_user
        log = AuditLog(user_id=current_user.id, action='Create PricingTier', resource_type='PricingTier', resource_id=tier.id, details=f'Rate: {tier.rate_per_kwh}')
        log.save()
        
        db.session.commit()
        flash('Pricing Tier created successfully.', 'success')
        return redirect(url_for('operator.dashboard'))
    return render_template('operator/form.html', title='New Pricing Tier', form=form, subject='Pricing Tier')

@operator_bp.route('/pricing/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@require_role('OPERATOR')
def edit_pricing(id):
    tier = PricingTier.query.get_or_404(id)
    form = PricingTierForm(obj=tier)
    if form.validate_on_submit():
        # Validate non-overlapping time bands (exclude self from check)
        active_tiers = PricingTier.query.filter(PricingTier.is_active == True, PricingTier.id != tier.id).all()
        for existing in active_tiers:
            if _hours_overlap(form.start_hour.data, form.end_hour.data, existing.start_hour, existing.end_hour):
                flash(f'Time band conflicts with existing tier "{existing.name}" ({existing.start_hour}:00–{existing.end_hour}:00).', 'danger')
                return render_template('operator/form.html', title='Edit Pricing Tier', form=form, subject='Pricing Tier')

        # Archive old tier
        tier.is_active = False
        
        # Insert new versioned tier
        new_tier = PricingTier(
            name=form.name.data,
            rate_per_kwh=form.rate_per_kwh.data,
            start_hour=form.start_hour.data,
            end_hour=form.end_hour.data,
            is_active=True
        )
        db.session.add(new_tier)
        db.session.flush()
        
        from app.models.audit import AuditLog
        from flask_login import current_user
        log = AuditLog(user_id=current_user.id, action='Edit PricingTier (New Version)', resource_type='PricingTier', resource_id=new_tier.id, details=f'New Rate: {new_tier.rate_per_kwh}')
        log.save()
        
        db.session.commit()
        flash('Pricing Tier updated and versioned successfully.', 'success')
        return redirect(url_for('operator.dashboard'))
    return render_template('operator/form.html', title='Edit Pricing Tier', form=form, subject='Pricing Tier')

@operator_bp.route('/pricing/delete/<int:id>', methods=['POST'])
@login_required
@require_role('OPERATOR')
def delete_pricing(id):
    tier = PricingTier.query.get_or_404(id)
    tier.is_active = False  # Soft delete — archive, not hard delete (preserves billing history)
    from app.models.audit import AuditLog
    from flask_login import current_user
    log = AuditLog(user_id=current_user.id, action='Deactivate PricingTier', resource_type='PricingTier', resource_id=tier.id, details=f'Tier archived: {tier.name}')
    log.save()
    db.session.commit()
    flash(f'Pricing Tier "{tier.name}" has been deactivated (archived).', 'warning')
    return redirect(url_for('operator.dashboard'))

@operator_bp.route('/zone/delete/<int:id>', methods=['POST'])
@login_required
@require_role('OPERATOR')
def delete_zone(id):
    zone = Zone.query.get_or_404(id)
    db.session.delete(zone)
    db.session.commit()
    flash(f'Zone "{zone.name}" deleted.', 'warning')
    return redirect(url_for('operator.dashboard'))

@operator_bp.route('/audit')
@login_required
@require_role('OPERATOR')
def audit_logs():
    from app.models.audit import AuditLog
    logs = AuditLog.get_all()
    return render_template('operator/audit.html', title='Audit Logs', logs=logs)

def _hours_overlap(s1, e1, s2, e2):
    """Check if two time bands overlap, handling midnight-crossing bands."""
    def to_set(s, e):
        if s < e:
            return set(range(s, e))
        else:  # crosses midnight
            return set(range(s, 24)) | set(range(0, e))
    return bool(to_set(s1, e1) & to_set(s2, e2))

