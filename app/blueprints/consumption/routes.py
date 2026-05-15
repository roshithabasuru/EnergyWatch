import csv
from datetime import datetime, timedelta
from io import StringIO
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.extensions import db
from app.blueprints.consumption import consumption_bp
from app.blueprints.consumption.forms import CSVUploadForm, ManualReadingForm
from app.models.consumption import MeterReading, ConsumptionSummary

@consumption_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if current_user.role != 'CONSUMER':
        flash('Only consumers can access this dashboard.', 'danger')
        return redirect(url_for('main.index'))
        
    form = CSVUploadForm()
    manual_form = ManualReadingForm(prefix='manual')
    
    if form.validate_on_submit():
        file = form.csv_file.data
        if not file:
            flash("No file selected", "danger")
            return redirect(url_for('consumption.dashboard'))
            
        try:
            # Read and decode CSV content
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            # Check expected columns
            fieldnames = [name.strip().lower() for name in (csv_reader.fieldnames or [])]
            if 'timestamp' not in fieldnames or 'kwh_consumed' not in fieldnames:
                flash("CSV must contain 'timestamp' and 'kWh_consumed' columns.", "danger")
                return redirect(url_for('consumption.dashboard'))
                
            readings = []
            aggregated_daily = {}
            meter_id = current_user.profile.meter_id
            
            for row in csv_reader:
                try:
                    # Look for headers disregarding exact case/spaces
                    row_keys = {k.strip().lower(): v for k, v in row.items()}
                    
                    ts_str = row_keys['timestamp']
                    kwh_str = row_keys['kwh_consumed']
                    
                    # Tolerant date format parsing
                    try:
                        timestamp = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        timestamp = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S')

                    kwh = float(kwh_str)
                    if kwh < 0:
                        continue # Validate kWh >= 0
                        
                    # Skip future timestamps
                    if timestamp > datetime.now():
                        continue
                        
                    # Validate against zone capacity
                    zone = current_user.profile.zone
                    if zone and kwh > (zone.capacity_mw * 1000):
                        continue
                        
                    readings.append(MeterReading(
                        meter_id=meter_id, 
                        timestamp=timestamp, 
                        kwh_consumed=kwh
                    ))
                    
                    # Daily aggregation map
                    d_key = timestamp.date()
                    aggregated_daily[d_key] = aggregated_daily.get(d_key, 0.0) + kwh
                    
                except (ValueError, KeyError):
                    continue # Map errors tolerated and skipped per MVP guidelines
            
            if not readings:
                flash("No valid readings found in the file.", "warning")
                return redirect(url_for('consumption.dashboard'))
                
            # Efficient insertion ignoring duplicates using merge or try/except block.
            # For MVP, appending row-by-row is okay but we'll try to flush. 
            # Easiest way in pure SQLAlch to ignore duplicates is ignoring IntegrityError
            inserted = 0
            for reading in readings:
                db.session.add(reading)
                try:
                    db.session.commit()
                    inserted += 1
                except IntegrityError:
                    db.session.rollback() # Duplicate ignored
            
            # Upsert Summaries
            for d_key, total_kwh in aggregated_daily.items():
                summary = ConsumptionSummary.query.filter_by(meter_id=meter_id, date=d_key).first()
                if summary:
                    # In a real app we'd recalculate precisely, here we just add or set.
                    # Since we ignored duplicate readings, adding here would duplicate summary loads.
                    # As a simpler approach, we'll cleanly recalculate the summary from DB directly.
                    pass
                else:
                    db.session.add(ConsumptionSummary(meter_id=meter_id, date=d_key, total_kwh=total_kwh))
                    db.session.commit()

            # Fix: After inserts, bulk recalculate the affected summary dates to be perfect.
            for d_key in aggregated_daily.keys():
                total = db.session.query(func.sum(MeterReading.kwh_consumed)).filter(
                    MeterReading.meter_id == meter_id,
                    func.date(MeterReading.timestamp) == d_key
                ).scalar() or 0.0
                
                summary = ConsumptionSummary.query.filter_by(meter_id=meter_id, date=d_key).first()
                if summary:
                    summary.total_kwh = total
                else:
                    db.session.add(ConsumptionSummary(meter_id=meter_id, date=d_key, total_kwh=total))
                db.session.commit()

            flash(f'Successfully imported {inserted} new readings!', 'success')
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
            
        return redirect(url_for('consumption.dashboard'))
        
    return render_template('consumption/dashboard.html', title='Analytics Dashboard', form=form, manual_form=manual_form)


@consumption_bp.route('/manual', methods=['POST'])
@login_required
def manual_entry():
    if current_user.role != 'CONSUMER':
        return redirect(url_for('main.index'))
    
    manual_form = ManualReadingForm(prefix='manual')
    if manual_form.validate_on_submit():
        ts = manual_form.timestamp.data
        kwh = manual_form.kwh_consumed.data
        
        if ts > datetime.now():
            flash('Cannot enter future timestamps.', 'danger')
            return redirect(url_for('consumption.dashboard'))
        
        # Validate against zone capacity (1 MW = 1000 kW, so in 1 hour max kWh is capacity * 1000)
        zone = current_user.profile.zone
        if zone and kwh > (zone.capacity_mw * 1000):
            flash(f'Reading exceeds your assigned zone capacity ({zone.capacity_mw} MW).', 'danger')
            return redirect(url_for('consumption.dashboard'))
            
        meter_id = current_user.profile.meter_id
        reading = MeterReading(meter_id=meter_id, timestamp=ts, kwh_consumed=kwh)
        db.session.add(reading)
        try:
            db.session.commit()
            # Update summary
            d_key = ts.date()
            total = db.session.query(func.sum(MeterReading.kwh_consumed)).filter(
                MeterReading.meter_id == meter_id,
                func.date(MeterReading.timestamp) == d_key
            ).scalar() or 0.0
            summary = ConsumptionSummary.query.filter_by(meter_id=meter_id, date=d_key).first()
            if summary:
                summary.total_kwh = total
            else:
                db.session.add(ConsumptionSummary(meter_id=meter_id, date=d_key, total_kwh=total))
            db.session.commit()
            flash(f'Reading of {kwh} kWh added for {ts.strftime("%Y-%m-%d %H:%M")}.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('A reading for this exact timestamp already exists (duplicate).', 'warning')
    else:
        for field, errors in manual_form.errors.items():
            flash(f'{field}: {errors[0]}', 'danger')
    return redirect(url_for('consumption.dashboard'))


@consumption_bp.route('/api/data')
@login_required
def consumption_data():
    if current_user.role != 'CONSUMER':
        return jsonify({"error": "Unauthorized"}), 403
        
    meter_id = current_user.profile.meter_id
    now_date = datetime.utcnow().date()
    
    # 1. Daily (last 30 days)
    thirty_days_ago = now_date - timedelta(days=30)
    daily_summaries = ConsumptionSummary.query.filter(
        ConsumptionSummary.meter_id == meter_id,
        ConsumptionSummary.date >= thirty_days_ago
    ).order_by(ConsumptionSummary.date.asc()).all()
    
    daily_labels = [s.date.strftime('%b %d') for s in daily_summaries]
    daily_data = [s.total_kwh for s in daily_summaries]

    # 2. Weekly (last 90 days)
    ninety_days_ago = now_date - timedelta(days=90)
    all_summaries = ConsumptionSummary.query.filter(
        ConsumptionSummary.meter_id == meter_id,
        ConsumptionSummary.date >= ninety_days_ago
    ).order_by(ConsumptionSummary.date.asc()).all()

    weekly_data_map = {}
    for s in all_summaries:
        # Group by 'YYYY-WW'
        iso_year, iso_week, _ = s.date.isocalendar()
        week_label = f"W{iso_week} {iso_year}"
        weekly_data_map[week_label] = weekly_data_map.get(week_label, 0) + s.total_kwh

    weekly_labels = list(weekly_data_map.keys())
    weekly_data = list(weekly_data_map.values())

    # 3. Monthly Comparison — current month vs previous month, day by day
    from calendar import monthrange
    today = datetime.now().date()
    curr_start = today.replace(day=1)
    prev_month = (curr_start - timedelta(days=1))
    prev_start = prev_month.replace(day=1)
    prev_end = prev_month.replace(day=monthrange(prev_month.year, prev_month.month)[1])

    def get_daily_map(start, end):
        rows = ConsumptionSummary.query.filter(
            ConsumptionSummary.meter_id == meter_id,
            ConsumptionSummary.date >= start,
            ConsumptionSummary.date <= end
        ).order_by(ConsumptionSummary.date.asc()).all()
        return {r.date.day: r.total_kwh for r in rows}

    curr_map = get_daily_map(curr_start, today)
    prev_map = get_daily_map(prev_start, prev_end)
    max_day = max(today.day, prev_end.day)
    day_labels = [str(d) for d in range(1, max_day + 1)]
    curr_month_data = [curr_map.get(d, 0) for d in range(1, max_day + 1)]
    prev_month_data = [prev_map.get(d, 0) for d in range(1, max_day + 1)]

    return jsonify({
        "daily": {"labels": daily_labels, "data": daily_data},
        "weekly": {"labels": weekly_labels, "data": weekly_data},
        "monthly": {
            "labels": day_labels,
            "current": {"label": today.strftime('%B %Y'), "data": curr_month_data},
            "previous": {"label": prev_month.strftime('%B %Y'), "data": prev_month_data}
        }
    })

