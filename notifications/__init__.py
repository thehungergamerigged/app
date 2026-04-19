import os
import datetime
from email.mime.text import MIMEText

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GMAIL_SCOPES  = ["https://www.googleapis.com/auth/gmail.send"]
SA_KEY_PATH   = "service_account.json"
GMAIL_TOKEN   = "gmail_token.json"
USE_LIMIT     = 3
DAILY_LIMIT   = 100
ADMIN_EMAILS  = frozenset({
    "haschanf@gmail.com",
    "jobsil4u@gmail.com",
    "omerholly@gmail.com",
})


# ── helpers ──────────────────────────────────────────────────────────────────

def _sheet_id() -> str:
    try:
        import streamlit as st
        return st.secrets.get("GOOGLE_SHEET_ID", "") or os.environ.get("GOOGLE_SHEET_ID", "")
    except Exception:
        return os.environ.get("GOOGLE_SHEET_ID", "")


def _sheets_svc():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    try:
        import streamlit as st
        creds = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=SHEETS_SCOPES
        )
    except Exception:
        creds = service_account.Credentials.from_service_account_file(
            SA_KEY_PATH, scopes=SHEETS_SCOPES
        )
    return build("sheets", "v4", credentials=creds)


def _read_rows() -> list:
    """Return [[timestamp, email], ...] from the sheet, skipping header."""
    sid = _sheet_id()
    if not sid:
        return []
    result = _sheets_svc().spreadsheets().values().get(
        spreadsheetId=sid, range="גיליון1!A:B"
    ).execute()
    rows = result.get("values", [])
    if rows and not rows[0][0][:4].isdigit():
        rows = rows[1:]
    return rows


# ── public API ───────────────────────────────────────────────────────────────

def write_usage(email: str) -> bool:
    """Append one row [timestamp, email] to the sheet. Call BEFORE every AI run."""
    sid = _sheet_id()
    if not sid:
        print("[write_usage] GOOGLE_SHEET_ID not set")
        return False
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _sheets_svc().spreadsheets().values().append(
            spreadsheetId=sid,
            range="גיליון1!A:B",
            valueInputOption="USER_ENTERED",
            body={"values": [[ts, email.strip().lower()]]},
        ).execute()
        return True
    except Exception as e:
        print(f"[write_usage] ERROR: {e}")
        return False


def count_uses(email: str) -> int:
    """How many times this email appears in the sheet."""
    try:
        email_lower = email.strip().lower()
        return sum(1 for r in _read_rows() if len(r) >= 2 and r[1].strip().lower() == email_lower)
    except Exception as e:
        print(f"[count_uses] ERROR: {e}")
        return 0


def count_daily_total() -> int:
    """Total rows written today (all users)."""
    try:
        today = datetime.date.today().isoformat()
        return sum(1 for r in _read_rows() if len(r) >= 1 and r[0].startswith(today))
    except Exception as e:
        print(f"[count_daily_total] ERROR: {e}")
        return 0


def is_quota_exceeded(email: str) -> tuple:
    """
    Returns (blocked: bool, message: str).
    Admin emails are never blocked.
    """
    if email.strip().lower() in ADMIN_EMAILS:
        return False, ""
    if count_daily_total() >= DAILY_LIMIT:
        return True, "המערכת בעומס, אנא נסו שוב מחר."
    if count_uses(email) >= USE_LIMIT:
        return True, "הגעת למכסה של 3 שאלות. אנא נסה שוב מחר."
    return False, ""


def register_lead(email: str):
    """Send email notification on first login (no sheet write — sheet is for AI usage only)."""
    try:
        import streamlit as st
        notify = st.secrets.get("NOTIFY_EMAIL", "") or os.environ.get("NOTIFY_EMAIL", "")
    except Exception:
        notify = os.environ.get("NOTIFY_EMAIL", "")
    if not notify:
        return
    try:
        import base64
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
        svc = build("gmail", "v1", credentials=creds)
        msg = MIMEText(f"New lead:\n\n{email}\n\nTime: {datetime.datetime.now()}")
        msg["to"]      = notify
        msg["subject"] = f"🧬 New Lead: {email}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as e:
        print(f"[register_lead] notify failed: {e}")
