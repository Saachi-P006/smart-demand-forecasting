"""
frontend/components/email_alerts.py
Sends critical stockout alerts to admin via Gmail SMTP.

Reads from your .env file:
    EMAIL_USER=saachipatwari@gmail.com
    EMAIL_PASS=dgyl fgfg wqyv bpio     ← spaces are automatically stripped
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    EMAIL_RECIPIENT=someone@email.com  (optional — defaults to EMAIL_USER)
"""

import os
import smtplib
import threading
import time
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not installed — rely on env vars being set externally

# ── Config — matches YOUR .env variable names exactly ─────────────────────────
SENDER_EMAIL    = os.getenv("EMAIL_USER", "")
SENDER_PASSWORD = os.getenv("EMAIL_PASS", "").replace(" ", "")  # strip spaces from app password
SMTP_SERVER     = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
RECIPIENT_EMAIL = os.getenv("EMAIL_RECIPIENT", SENDER_EMAIL)    # defaults to sender if not set

ALERT_INTERVAL_SECONDS = 3600

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
ALERTS_CSV = os.path.join(OUTPUT_DIR, "alerts_output.csv")

_thread_started = False


def _load_critical_alerts() -> pd.DataFrame:
    try:
        df = pd.read_csv(ALERTS_CSV)
        if "risk_level" in df.columns:
            return df[df["risk_level"].str.contains("Stockout", na=False, case=False)]
        elif "alert_type" in df.columns:
            return df[df["alert_type"].str.contains("Stockout", na=False, case=False)]
        return df.head(50)
    except Exception as e:
        print(f"[email_alerts] Could not load alerts CSV: {e}")
        return pd.DataFrame()


# (ONLY showing changed parts — rest remains same)

def _build_email_html(df: pd.DataFrame, sent_at: str) -> str:
    top = df.head(20)
    rows_html = ""

    for _, row in top.iterrows():
        product = row.get("product_id", row.get("product_name", "N/A"))
        store   = row.get("store_id", "N/A")
        city    = row.get("city", "N/A")
        inv     = row.get("inventory_on_hand", row.get("current_inventory", "N/A"))
        demand  = row.get("adjusted_demand", row.get("predicted_units", "N/A"))
        flags   = row.get("reason_flags", "")

        rows_html += f"""
        <tr style="background:#ffffff;">
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;font-weight:600;color:#020617">{product}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#1e293b">{store}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#1e293b">{city}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#dc2626;font-weight:700">{inv}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#059669;font-weight:600">{demand}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;font-size:12px;color:#334155">{flags}</td>
        </tr>
        """

    overflow = (f'<div style="padding:12px 0;font-size:12px;color:#64748b">... and {len(df)-20} more. Log in to view all.</div>'
                if len(df) > 20 else "")

    return f"""<!DOCTYPE html>
<html>
<body style="background:#f1f5f9;font-family:Arial;">
  <div style="max-width:700px;margin:auto;background:white;border-radius:10px;padding:20px">
    
    <h2 style="color:#0f172a;">🔴 Stockout Alert</h2>
    <p style="color:#334155;">{len(df)} products at risk • {sent_at}</p>

    <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead style="background:#e2e8f0;color:#020617">
            <tr>
                <th style="padding:8px;">Product</th>
                <th style="padding:8px;">Store</th>
                <th style="padding:8px;">City</th>
                <th style="padding:8px;">Inventory</th>
                <th style="padding:8px;">Forecast</th>
                <th style="padding:8px;">Flags</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

  </div>
</body>
</html>
"""


def send_critical_alerts():
    """Send stockout alert email. Returns (success: bool, message: str)."""

    # Re-read env each call in case .env was updated at runtime
    sender   = os.getenv("EMAIL_USER", SENDER_EMAIL)
    password = os.getenv("EMAIL_PASS", "").replace(" ", "")
    recipient = os.getenv("EMAIL_RECIPIENT", sender)
    host = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))

    if not sender or not password:
        return False, "❌ EMAIL_USER or EMAIL_PASS not set in .env"

    df = _load_critical_alerts()
    if df.empty:
        return True, "✅ No critical stockout alerts to send right now."

    sent_at   = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    subject   = f"🔴 [{len(df)} Stockout Alerts] SmartDemand — {datetime.now().strftime('%b %d, %H:%M')}"
    html_body = _build_email_html(df, sent_at)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = recipient
        msg.attach(MIMEText(html_body, "html"))

        # Port 587 → STARTTLS (matches your .env SMTP_PORT=587)
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        print(f"[email_alerts] ✅ Sent {len(df)} alerts to {recipient} at {sent_at}")
        return True, f"✅ Email sent to {recipient} — {len(df)} stockout alerts"

    except smtplib.SMTPAuthenticationError:
        return False, (
            "❌ Gmail authentication failed.\n"
            "Make sure EMAIL_PASS in .env is a Gmail App Password, not your regular password.\n"
            "Generate one at: myaccount.google.com/apppasswords (requires 2FA to be enabled)"
        )
    except smtplib.SMTPException as e:
        return False, f"❌ SMTP error: {e}"
    except Exception as e:
        return False, f"❌ Failed to send: {e}"


def _hourly_alert_loop():
    while True:
        print(f"[email_alerts] Hourly check at {datetime.now().strftime('%H:%M')}")
        send_critical_alerts()
        time.sleep(ALERT_INTERVAL_SECONDS)


def start_hourly_alerts():
    """Start background hourly alert thread. Safe to call multiple times."""
    global _thread_started
    if not _thread_started:
        t = threading.Thread(target=_hourly_alert_loop, daemon=True)
        t.start()
        _thread_started = True
        print("[email_alerts] ⏰ Hourly alert thread started.")