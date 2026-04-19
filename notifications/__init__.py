import os
import base64
import datetime
from email.mime.text import MIMEText

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GMAIL_SCOPES  = ["https://www.googleapis.com/auth/gmail.send"]
SA_KEY_PATH   = "service_account.json"
GMAIL_TOKEN   = "gmail_token.json"


def _get_secret(key: str) -> str:
    try:
        import streamlit as st
        return st.secrets.get(key, "") or os.environ.get(key, "")
    except Exception:
        return os.environ.get(key, "")


def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY_PATH, scopes=SHEETS_SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
    return build("gmail", "v1", credentials=creds)


def save_email_to_sheet(email: str) -> bool:
    try:
        spreadsheet_id = _get_secret("GOOGLE_SHEET_ID")
        if not spreadsheet_id:
            return False
        svc = _sheets_service()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        svc.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="גיליון1!A:B",
            valueInputOption="USER_ENTERED",
            body={"values": [[timestamp, email]]},
        ).execute()
        return True
    except Exception as e:
        try:
            import streamlit as st
            st.warning(f"Sheet save failed: {e}")
        except Exception:
            print(f"Sheet save failed: {e}")
        return False


def send_notification_email(email: str) -> bool:
    try:
        notify_email = _get_secret("NOTIFY_EMAIL")
        if not notify_email:
            return False
        svc = _gmail_service()
        body = f"New lead from Rigged Game Breaker:\n\n{email}\n\nTime: {datetime.datetime.now()}"
        msg = MIMEText(body)
        msg["to"]      = notify_email
        msg["subject"] = f"🧬 New Lead: {email}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        try:
            import streamlit as st
            st.warning(f"Email notification failed: {e}")
        except Exception:
            print(f"Email notification failed: {e}")
        return False


def register_lead(email: str):
    """Save to sheet and send notification. Silent on partial failures."""
    save_email_to_sheet(email)
    send_notification_email(email)
