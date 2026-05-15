from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import extract, func

from app.extensions import db
from app.blueprints.billing import billing_bp
from app.models.consumption import MeterReading, ConsumptionSummary
from app.models.pricing import PricingTier
from app.models.billing import Bill
from app.utils.decorators import require_role

@billing_bp.route('/statements')
@login_required
@require_role('CONSUMER')
def statements():
    bills = Bill.query.filter_by(consumer_id=current_user.id).order_by(Bill.billing_year.desc(), Bill.billing_month.desc()).all()
    return render_template('billing/statements.html', bills=bills)

@billing_bp.route('/generate', methods=['POST'])
@login_required
@require_role('CONSUMER')
def generate_bill():
    """Manually generate/recalculate the bill for the current month.
    In production, this is called gracefully by APScheduler automatically.
    """
    now = datetime.utcnow()
    month = now.month
    year = now.year
    meter_id = current_user.profile.meter_id
    
    if not meter_id:
        flash("You do not have a registered meter ID.", "danger")
        return redirect(url_for('consumer.profile'))

    readings = MeterReading.query.filter(
        MeterReading.meter_id == meter_id,
        extract('month', MeterReading.timestamp) == month,
        extract('year', MeterReading.timestamp) == year
    ).all()
    
    if not readings:
        flash("No consumption data found for the current month.", "warning")
        return redirect(url_for('billing.statements'))
        
    tiers = PricingTier.query.all()
    if not tiers:
        flash("System critical error: Pricing tiers are not configured.", "danger")
        return redirect(url_for('billing.statements'))

    total_kwh = 0.0
    total_cost = 0.0
    
    for r in readings:
        hour = r.timestamp.hour
        kwh = r.kwh_consumed
        
        # Determine applicable rate for this hour
        applicable_rate = 0.0
        handled = False
        
        for t in tiers:
            if t.start_hour <= t.end_hour:
                if t.start_hour <= hour < t.end_hour:
                    applicable_rate = t.rate_per_kwh
                    handled = True
                    break
            else: # Overnight overlap
                if hour >= t.start_hour or hour < t.end_hour:
                    applicable_rate = t.rate_per_kwh
                    handled = True
                    break
        
        # If no explicit tier matches (should never happen if configured fully), fallback to default rate.
        if not handled:
            applicable_rate = tiers[0].rate_per_kwh
            
        total_kwh += kwh
        total_cost += (kwh * applicable_rate)
        
    # Standard connection fee baseline
    grid_connection_fee = 200.00
    final_amount = total_cost + grid_connection_fee
    
    # Check if Bill exists
    bill = Bill.query.filter_by(consumer_id=current_user.id, billing_month=month, billing_year=year).first()
    if bill:
        bill.total_kwh = total_kwh
        # For simulation, just update the total amount.
        bill.total_amount = final_amount
        db.session.commit()
        flash(f"Current bill recalculated: ₹{final_amount:.2f}", "success")
    else:
        # Construct and set Due Date (15th of next month)
        next_month_raw = now.replace(day=28) + timedelta(days=4)
        due_date = date(next_month_raw.year, next_month_raw.month, 15)
        
        bill = Bill(
            consumer_id=current_user.id,
            billing_month=month,
            billing_year=year,
            total_kwh=total_kwh,
            total_amount=final_amount,
            due_date=due_date
        )
        db.session.add(bill)
        db.session.commit()
        flash(f"Monthly Bill processed successfully: ₹{final_amount:.2f}", "success")
        
    return redirect(url_for('billing.statements'))

@billing_bp.route('/view/<int:id>')
@login_required
@require_role('CONSUMER')
def view_bill(id):
    bill = Bill.query.filter_by(id=id, consumer_id=current_user.id).first_or_404()
    
    # Calculate textual representation of month/year
    import calendar
    month_str = calendar.month_name[bill.billing_month]
    
    return render_template('billing/statement_view.html', bill=bill, month_str=month_str)
