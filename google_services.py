"""
google_services.py — Google Calendar + Gmail helper for Raj Dental Care
=======================================================================
Uses OAuth2 refresh_token flow (no user interaction after first setup).
Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN in .env
"""

import os
import logging
from datetime import datetime, timedelta
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger("voice-agent")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_credentials() -> Credentials:
    """Build OAuth2 credentials from .env tokens (no browser needed)."""
    return Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def create_calendar_event(
    patient_name: str,
    service: str,
    date_str: str,   # "YYYY-MM-DD"
    time_str: str,   # "HH:MM" 24-hour
    phone: str,
    email: str,
) -> dict:
    """Create a 1-hour appointment in Google Calendar. Returns event info."""
    creds = _get_credentials()
    service_cal = build("calendar", "v3", credentials=creds, cache_discovery=False)

    calendar_id = os.getenv("CLINIC_CALENDAR_ID", "primary")
    clinic_tz   = "Asia/Kolkata"

    start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_dt   = start_dt + timedelta(hours=1)

    event = {
        "summary": f"🦷 {service} — {patient_name}",
        "description": (
            f"Patient: {patient_name}\n"
            f"Phone:   {phone}\n"
            f"Email:   {email}\n"
            f"Service: {service}\n\n"
            f"Booked via AI Receptionist — Raj Dental Care"
        ),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": clinic_tz},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": clinic_tz},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 30},
            ],
        },
    }

    created = service_cal.events().insert(calendarId=calendar_id, body=event).execute()
    logger.info("Calendar event created: %s", created.get("htmlLink"))
    return created


def send_confirmation_email(
    patient_name: str,
    patient_email: str,
    service: str,
    date_str: str,
    time_str: str,
) -> bool:
    """Send HTML confirmation email to patient via Gmail API."""
    creds  = _get_credentials()
    gmail  = build("gmail", "v1", credentials=creds, cache_discovery=False)

    sender       = os.getenv("CLINIC_EMAIL", "rajdentalcare@gmail.com")
    clinic_phone = os.getenv("CLINIC_PHONE", "+91-XXXXXXXXXX")

    # Format display date
    try:
        disp_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        disp    = disp_dt.strftime("%d %B %Y, %I:%M %p")
    except ValueError:
        disp = f"{date_str} at {time_str}"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto">
      <div style="background:#1a73e8;padding:20px;border-radius:8px 8px 0 0;text-align:center">
        <h1 style="color:white;margin:0">🦷 Raj Dental Care</h1>
        <p style="color:#cce5ff;margin:4px 0">Faridabad, Haryana</p>
      </div>
      <div style="padding:24px;background:#f9f9f9;border:1px solid #e0e0e0">
        <h2 style="color:#1a73e8">Appointment Confirmed! ✅</h2>
        <p>Namaste <strong>{patient_name}</strong> ji,</p>
        <p>Aapka appointment book ho gaya hai. Details yeh hain:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#e8f0fe">
            <td style="padding:10px;font-weight:bold">Service</td>
            <td style="padding:10px">{service}</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold">Date &amp; Time</td>
            <td style="padding:10px">{disp}</td>
          </tr>
          <tr style="background:#e8f0fe">
            <td style="padding:10px;font-weight:bold">Clinic</td>
            <td style="padding:10px">Raj Dental Care, Faridabad, Haryana</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold">Timing</td>
            <td style="padding:10px">9:00 AM – 7:00 PM (All Days)</td>
          </tr>
          <tr style="background:#e8f0fe">
            <td style="padding:10px;font-weight:bold">Contact</td>
            <td style="padding:10px">{clinic_phone}</td>
          </tr>
        </table>
        <p style="background:#fff3cd;padding:12px;border-radius:6px;border-left:4px solid #ffc107">
          ⚠️ Please appointment se 10 minutes pehle aayein. Reschedule ke liye call karein.
        </p>
        <p>Dhanyavaad! Aapki healthy smile hamari priority hai 😊</p>
        <p style="color:#888;font-size:12px">— Raj Dental Care Team</p>
      </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✅ Appointment Confirmed — Raj Dental Care ({disp})"
    msg["From"]    = f"Raj Dental Care <{sender}>"
    msg["To"]      = patient_email
    msg.attach(MIMEText(html_body, "html"))

    raw  = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info("Confirmation email sent to %s", patient_email)
    return True
