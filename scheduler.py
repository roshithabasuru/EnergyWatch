import os
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app import create_app
from app.extensions import db
from app.models.demand_response import DREvent
from app.models.alert import AlertRule, Notification
from app.models.consumption import ConsumptionSummary, MeterReading
from app.models.pricing import PricingTier
from app.models.billing import Bill
from app.models.user import ConsumerProfile
from sqlalchemy import extract
import datetime as dt

app = create_app()

def sync_dr_event_status():
    """Shifts events between SCHEDULED -> ACTIVE -> COMPLETED based on current time."""
    with app.app_context():
        now = datetime.now()  # Use local time to match form-submitted event times
        try:
            # Activate events
            scheduled = DREvent.query.filter(
                DREvent.status == 'SCHEDULED',
                DREvent.event_start <= now,
                DREvent.event_end > now
            ).all()
            for e in scheduled:
                e.status = 'ACTIVE'
                
            # Complete events
            active = DREvent.query.filter(
                DREvent.status == 'ACTIVE',
                DREvent.event_end <= now
            ).all()
            for e in active:
                e.status = 'COMPLETED'
                
            if scheduled or active:
                db.session.commit()
                print(f"[{now}] Scheduler: Synchronized {len(scheduled)} to ACTIVE, {len(active)} to COMPLETED.")
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in sync_dr_event_status: {e}")

def send_dr_reminders():
    """Sends T-24h and T-2h advance reminder notifications to enrolled consumers."""
    with app.app_context():
        now = datetime.now()
        try:
            for window_hours, label in [(24, 'T-24h'), (2, 'T-2h')]:
                window_start = now + timedelta(hours=window_hours - 0.25)
                window_end   = now + timedelta(hours=window_hours + 0.25)
                events = DREvent.query.filter(
                    DREvent.status == 'SCHEDULED',
                    DREvent.event_start >= window_start,
                    DREvent.event_start <= window_end
                ).all()
                for event in events:
                    from app.models.demand_response import EventEnrollment
                    enrollments = EventEnrollment.query.filter_by(event_id=event.id, status='ACTIVE').all()
                    for enr in enrollments:
                        debounce_key = f"DR_REMINDER:{label}:Event{event.id}:User{enr.consumer_id}"
                        exists = Notification.query.filter(
                            Notification.user_id == enr.consumer_id,
                            Notification.message.like(f"{debounce_key}%")
                        ).first()
                        if exists:
                            continue
                        est_savings = round((event.baseline_kwh or 0) * (event.target_reduction / 100) * event.incentive, 2)
                        opt_in_link = '/demand-response/consumer/events'
                        msg = (f"{debounce_key} | ⚡ DR Event Reminder ({label}): "
                               f"Event in zone '{event.zone.name}' starts at {event.event_start.strftime('%H:%M on %d %b')}. "
                               f"Target reduction: {event.target_reduction}%. "
                               f"Estimated earnings: ₹{est_savings}. "
                               f"Opt-in: {opt_in_link}")
                        db.session.add(Notification(user_id=enr.consumer_id, message=msg))
                        # Mock dispatch
                        profile = ConsumerProfile.query.filter_by(user_id=enr.consumer_id).first()
                        
                        from app.models.user import User
                        user = User.query.get(enr.consumer_id)
                        print("=" * 60)
                        print(f"[DR REMINDER {label}] To: {user.email if user else enr.consumer_id}")
                        print(f"  {msg}")
                        print("=" * 60)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in send_dr_reminders: {e}")

def check_price_spikes():
    """Alerts all consumers when any active peak tier rate exceeds 150% of off-peak baseline."""
    with app.app_context():
        try:
            active_tiers = PricingTier.query.filter_by(is_active=True).all()
            if not active_tiers:
                return
            # Baseline = average of all active tier rates
            avg_rate = sum(t.rate_per_kwh for t in active_tiers) / len(active_tiers)
            spike_tiers = [t for t in active_tiers if t.rate_per_kwh > avg_rate * 1.5]
            if not spike_tiers:
                return
            consumers = ConsumerProfile.query.all()
            for profile in consumers:
                for spike in spike_tiers:
                    debounce_key = f"PRICE_SPIKE:Tier{spike.id}:{datetime.now().date()}"
                    exists = Notification.query.filter(
                        Notification.user_id == profile.user_id,
                        Notification.message.like(f"{debounce_key}%")
                    ).first()
                    if exists:
                        continue
                    msg = (f"{debounce_key} | 🔴 Price Spike Alert: '{spike.name}' tier rate "
                           f"₹{spike.rate_per_kwh}/kWh is >{150}% of average (₹{avg_rate:.2f}/kWh). "
                           f"Consider shifting loads to off-peak hours. View: /consumption/dashboard")
                    db.session.add(Notification(user_id=profile.user_id, message=msg))
                    # Mock dispatch
                    from app.models.user import User
                    user = User.query.get(profile.user_id)
                    print(f"[PRICE SPIKE ALERT] To: {user.email if user else profile.user_id} | {msg}")
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in check_price_spikes: {e}")

def check_consumption_thresholds():
    """Checks daily/weekly/monthly consumption vs AlertRules. Debounced, 5% tolerance, mock dispatch."""
    with app.app_context():
        now = datetime.now()  # local time
        today = now.date()
        try:
            active_rules = AlertRule.query.filter_by(is_active=True).all()
            for rule in active_rules:
                profile = rule.user.profile
                if not profile or not profile.meter_id:
                    continue

                meter_id = profile.meter_id
                actual_kwh = 0.0
                period_label = ''

                if rule.rule_type == 'DAILY_THRESHOLD':
                    summary = ConsumptionSummary.query.filter_by(meter_id=meter_id, date=today).first()
                    actual_kwh = summary.total_kwh if summary else 0.0
                    period_label = f'today ({today})'
                    debounce_key = f"THRESHOLD_BREACH:DAILY:{today}"

                elif rule.rule_type == 'WEEKLY_THRESHOLD':
                    from datetime import timedelta
                    week_start = today - timedelta(days=today.weekday())
                    rows = ConsumptionSummary.query.filter(
                        ConsumptionSummary.meter_id == meter_id,
                        ConsumptionSummary.date >= week_start,
                        ConsumptionSummary.date <= today
                    ).all()
                    actual_kwh = sum(r.total_kwh for r in rows)
                    period_label = f'this week (from {week_start})'
                    debounce_key = f"THRESHOLD_BREACH:WEEKLY:{week_start}"

                elif rule.rule_type == 'MONTHLY_THRESHOLD':
                    month_start = today.replace(day=1)
                    rows = ConsumptionSummary.query.filter(
                        ConsumptionSummary.meter_id == meter_id,
                        ConsumptionSummary.date >= month_start,
                        ConsumptionSummary.date <= today
                    ).all()
                    actual_kwh = sum(r.total_kwh for r in rows)
                    period_label = f'this month ({today.strftime("%B %Y")})'
                    debounce_key = f"THRESHOLD_BREACH:MONTHLY:{month_start}"
                else:
                    continue

                # 5% tolerance — do not alert for minor overages
                if actual_kwh <= rule.threshold_kwh * 1.05:
                    continue

                # Debounce — max 1 alert per rule type per period
                existing = Notification.query.filter(
                    Notification.user_id == rule.consumer_id,
                    Notification.message.like(f"{debounce_key}%")
                ).first()
                if existing:
                    continue

                # Build message with dashboard link
                dashboard_url = '/consumption/dashboard'
                msg = (f"{debounce_key} | Threshold Alert: Your usage {period_label} is "
                       f"{actual_kwh:.1f} kWh, exceeding your limit of {rule.threshold_kwh} kWh. "
                       f"View your graph: {dashboard_url}")
                db.session.add(Notification(user_id=rule.consumer_id, message=msg))

                # Mock email/SMS dispatch
                user = rule.user
                pref = 'email'
                print("=" * 60)
                print(f"[THRESHOLD ALERT] {rule.rule_type} | {pref.upper()}")
                if pref == 'email' and user.email:
                    print(f"  [EMAIL] To: {user.email}")
                    print(f"  Subject: EnergyWatch Threshold Alert")
                    print(f"  Body: {msg}")
                print("=" * 60)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in check_consumption_thresholds: {e}")

def generate_monthly_bills():
    """Calculates bills for all registered consumers automatically via Cron."""
    print("Scheduler: Generating Monthly Bills...")
    with app.app_context():
        # Typically run on 1st, so calculate for previous month
        now = datetime.utcnow()
        first_of_this_month = now.replace(day=1)
        last_month = first_of_this_month - dt.timedelta(days=1)
        month = last_month.month
        year = last_month.year
        
        try:
            tiers = PricingTier.query.all()
            if not tiers:
                return
                
            consumers = ConsumerProfile.query.all()
            for profile in consumers:
                if not profile.meter_id: continue
                
                # Check if bill already exists to prevent duplicate generation if run manually multiple times on 1st
                existing = Bill.query.filter_by(consumer_id=profile.user_id, billing_month=month, billing_year=year).first()
                if existing: continue

                readings = MeterReading.query.filter(
                    MeterReading.meter_id == profile.meter_id,
                    extract('month', MeterReading.timestamp) == month,
                    extract('year', MeterReading.timestamp) == year
                ).all()

                if not readings: continue

                total_kwh = 0.0
                total_cost = 0.0

                for r in readings:
                    hour = r.timestamp.hour
                    kwh = r.kwh_consumed
                    
                    applicable_rate = tiers[0].rate_per_kwh
                    for t in tiers:
                        if t.start_hour <= t.end_hour:
                            if t.start_hour <= hour < t.end_hour:
                                applicable_rate = t.rate_per_kwh
                                break
                        else:
                            if hour >= t.start_hour or hour < t.end_hour:
                                applicable_rate = t.rate_per_kwh
                                break
                                
                    total_kwh += kwh
                    total_cost += (kwh * applicable_rate)
                
                final_amount = total_cost + 200.0
                due_date = dt.date(now.year, now.month, 15)
                
                db.session.add(Bill(
                    consumer_id=profile.user_id,
                    billing_month=month,
                    billing_year=year,
                    total_kwh=total_kwh,
                    total_amount=final_amount,
                    due_date=due_date
                ))
                # Push Notification for new bill
                db.session.add(Notification(
                    user_id=profile.user_id,
                    message=f"Your statement for Month {month}, {year} has been generated. Total Due: ₹{final_amount:.2f}."
                ))
            db.session.commit()
            print(f"Scheduler: Monthly Bills Generation Done for Month {month}.")
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in generate_monthly_bills: {e}")

def process_notification_outbox():
    """Processes QUEUED notifications with exponential backoff on retries (max 3 attempts)."""
    with app.app_context():
        try:
            queued = Notification.query.filter(
                Notification.status.in_(['QUEUED', 'FAILED'])
            ).filter(Notification.retry_count < 3).all()
            for notif in queued:
                try:
                    # Exponential backoff: skip if last retry was too recent
                    if notif.retry_count > 0:
                        backoff_seconds = (2 ** notif.retry_count) * 30  # 60s, 120s, 240s
                        retry_due = notif.created_at + timedelta(seconds=backoff_seconds)
                        if datetime.now() < retry_due:
                            continue  # Not yet time to retry

                    # Simulate delivery
                    print(f"[OUTBOX] Dispatching (attempt {notif.retry_count + 1}) to User {notif.user_id}: {notif.message[:80]}...")
                    notif.status = 'SENT'
                except Exception:
                    notif.retry_count += 1
                    notif.status = 'FAILED' if notif.retry_count >= 3 else 'QUEUED'
                    print(f"[OUTBOX] Retry {notif.retry_count}/3 failed for Notification {notif.id}")

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Scheduler error in process_notification_outbox: {e}")

if __name__ == '__main__':
    print("Starting EnergyWatch Standalone APScheduler Background Worker...")
    scheduler = BackgroundScheduler()
    
    # Run status synchronization every 1 minute
    scheduler.add_job(func=sync_dr_event_status, trigger="interval", seconds=60)
    
    # Send T-24h and T-2h DR reminders every 15 minutes
    scheduler.add_job(func=send_dr_reminders, trigger="interval", minutes=15)

    # Check for price spikes every 30 minutes
    scheduler.add_job(func=check_price_spikes, trigger="interval", minutes=30)
    
    # Run threshold checks every 5 minutes
    scheduler.add_job(func=check_consumption_thresholds, trigger="interval", seconds=300)
    
    # Run Notification Outbox Dispatcher every 30 seconds
    scheduler.add_job(func=process_notification_outbox, trigger="interval", seconds=30)
    
    # Run Billing Generator on the 1st of every month at Midnight
    scheduler.add_job(func=generate_monthly_bills, trigger='cron', day=1, hour=0, minute=0)
    
    scheduler.start()
    
    try:
        # Keep the main thread alive securely
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down Scheduler.")
        scheduler.shutdown()
