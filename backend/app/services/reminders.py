"""
app/services/reminders.py

Background job that runs every hour and sends reminder emails to hospital
staff for approved appointments happening within the next 24 hours.

Staff then call/SMS the patient as a reminder.

Setup: call start_reminder_scheduler() from app/main.py on startup.
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.services.booking_rules import get_booking_config
from app.services.email import _send_smtp

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _send_reminder_email(
    staff_email: str,
    hospital_name: str,
    reference: str,
    patient_name: str,
    patient_phone: str,
    doctor_name: str,
    confirmed_time: str,
    preferred_date: str,
) -> bool:
    subject = f"[Arogya] Appointment Reminder — {reference} ({preferred_date})"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;">
      <div style="background:#7c3aed;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">Appointment Reminder</h2>
        <p style="color:#ede9fe;margin:4px 0 0;">{hospital_name}</p>
      </div>
      <div style="background:#f9fafb;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
        <p style="margin:0 0 16px;color:#374151;">
          The following appointment is coming up. Please call the patient to remind them.
        </p>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px;color:#6b7280;width:40%;">Reference</td>
              <td style="padding:8px;font-weight:bold;">{reference}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Patient</td>
              <td style="padding:8px;">{patient_name}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Phone</td>
              <td style="padding:8px;font-weight:bold;color:#7c3aed;">{patient_phone}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Doctor</td>
              <td style="padding:8px;">{doctor_name}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Date</td>
              <td style="padding:8px;">{preferred_date}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Confirmed Time</td>
              <td style="padding:8px;font-weight:bold;">{confirmed_time}</td></tr>
        </table>
      </div>
    </div>
    """
    return _send_smtp(staff_email, subject, html)


def _run_reminders() -> None:
    """
    Called every hour by APScheduler.
    Finds approved appointments within the next reminder_hours_before window
    that haven't had a reminder sent yet, and emails staff.

    We track whether a reminder was sent by checking if updated_at was
    touched after approval — a lightweight approach that avoids needing
    a separate reminder_sent column for now.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Load all approved appointments
        approved = (
            db.query(Appointment)
            .filter(Appointment.status == "approved")
            .all()
        )

        for appt in approved:
            try:
                hospital = db.query(Hospital).filter(Hospital.id == appt.hospital_id).first()
                if not hospital:
                    continue

                config = get_booking_config(hospital)
                staff_email = config.get("notification_email", "")
                reminder_hours = int(config.get("reminder_hours_before", 24))

                if not staff_email:
                    continue

                # Parse appointment date + confirmed time to get exact datetime
                try:
                    appt_date = datetime.strptime(appt.preferred_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

                # Window: send reminder if appointment is within the next reminder_hours
                # and the reminder hasn't been sent (updated_at hasn't been touched since
                # approval — we add a reminder_sent flag by bumping updated_at again)
                time_until = appt_date - now
                if not (timedelta(hours=0) < time_until <= timedelta(hours=reminder_hours)):
                    continue

                # Simple dedup: skip if updated_at is more recent than 23 hours ago
                # (meaning we already sent a reminder this cycle)
                if appt.updated_at:
                    updated_aware = appt.updated_at.replace(tzinfo=timezone.utc) if appt.updated_at.tzinfo is None else appt.updated_at
                    if (now - updated_aware) < timedelta(hours=23):
                        continue

                doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()

                sent = _send_reminder_email(
                    staff_email=staff_email,
                    hospital_name=hospital.name,
                    reference=appt.reference_number,
                    patient_name=appt.patient_name,
                    patient_phone=appt.patient_phone,
                    doctor_name=doctor.name if doctor else "Doctor",
                    confirmed_time=appt.confirmed_time or "TBD",
                    preferred_date=appt.preferred_date,
                )

                if sent:
                    # Bump updated_at so we don't send again this cycle
                    from datetime import datetime as dt
                    appt.updated_at = dt.now(timezone.utc)
                    db.commit()
                    logger.info("[Reminders] Sent reminder for %s", appt.reference_number)

            except Exception as e:
                logger.error("[Reminders] Error processing appointment %s: %s", appt.id, e)

    except Exception as e:
        logger.error("[Reminders] Job failed: %s", e)
    finally:
        db.close()


def start_reminder_scheduler() -> None:
    """
    Call this from main.py on app startup.
    Runs the reminder check every hour.
    """
    if _scheduler.running:
        return
    _scheduler.add_job(
        _run_reminders,
        trigger="interval",
        hours=1,
        id="appointment_reminders",
        replace_existing=True,
        next_run_time=datetime.now(),   # run immediately on startup too
    )
    _scheduler.start()
    logger.info("[Reminders] Scheduler started — checking every hour.")


def stop_reminder_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()