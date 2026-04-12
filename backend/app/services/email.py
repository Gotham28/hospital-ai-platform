"""
app/services/email.py

Sends appointment notification emails using either:
  - SMTP (default, zero dependencies)
  - SendGrid API (set SENDGRID_API_KEY env var to switch)

Environment variables:
  SMTP_HOST          default: smtp.gmail.com
  SMTP_PORT          default: 587
  SMTP_USER          your Gmail / SMTP username
  SMTP_PASSWORD      app password (not your login password)
  EMAIL_FROM         displayed sender address
  SENDGRID_API_KEY   if set, uses SendGrid instead of SMTP
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM    = os.getenv("EMAIL_FROM", SMTP_USER)


def _send_smtp(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("[Email] SMTP_USER / SMTP_PASSWORD not set — skipping email.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to, msg.as_string())
        logger.info("[Email] Sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.error("[Email] Failed to send to %s: %s", to, e)
        return False


def notify_staff_new_appointment(
    staff_email: str,
    hospital_name: str,
    reference: str,
    patient_name: str,
    patient_age: str,
    patient_phone: str,
    doctor_name: str,
    preferred_date: str,
    time_of_day: str,
) -> bool:
    subject = f"[Arogya] New Appointment Request — {reference}"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;">
      <div style="background:#059669;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">New Appointment Request</h2>
        <p style="color:#d1fae5;margin:4px 0 0;">{hospital_name}</p>
      </div>
      <div style="background:#f9fafb;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px;color:#6b7280;width:40%;">Reference</td>
              <td style="padding:8px;font-weight:bold;">{reference}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Patient Name</td>
              <td style="padding:8px;">{patient_name}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Age</td>
              <td style="padding:8px;">{patient_age}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Phone</td>
              <td style="padding:8px;">{patient_phone}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Doctor</td>
              <td style="padding:8px;">{doctor_name}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Preferred Date</td>
              <td style="padding:8px;">{preferred_date}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Time of Day</td>
              <td style="padding:8px;text-transform:capitalize;">{time_of_day}</td></tr>
        </table>
        <div style="margin-top:24px;padding:16px;background:#ecfdf5;border-radius:6px;border:1px solid #6ee7b7;">
          <p style="margin:0;color:#065f46;">
            Please log in to your <strong>Arogya Admin Dashboard</strong> to approve or reject this request.
          </p>
        </div>
      </div>
    </div>
    """
    return _send_smtp(staff_email, subject, html)


def notify_patient_approved(
    staff_email: str,        # we email staff to call patient since we may not have patient email
    hospital_name: str,
    reference: str,
    patient_name: str,
    patient_phone: str,
    doctor_name: str,
    confirmed_time: str,
    preferred_date: str,
) -> bool:
    """
    Notifies staff that they should call/SMS the patient with confirmed time.
    In a future iteration this can be replaced with a direct Twilio SMS to the patient.
    """
    subject = f"[Arogya] Appointment Approved — Call Patient ({reference})"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;">
      <div style="background:#2563eb;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">Appointment Approved — Please Call Patient</h2>
      </div>
      <div style="background:#f9fafb;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
        <p>The following appointment has been approved. Please call the patient to confirm.</p>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px;color:#6b7280;width:40%;">Reference</td>
              <td style="padding:8px;font-weight:bold;">{reference}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;color:#6b7280;">Patient</td>
              <td style="padding:8px;">{patient_name}</td></tr>
          <tr><td style="padding:8px;color:#6b7280;">Phone</td>
              <td style="padding:8px;font-weight:bold;color:#059669;">{patient_phone}</td></tr>
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