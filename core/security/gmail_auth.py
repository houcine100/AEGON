# core/security/gmail_auth.py
# Gmail OAuth: one-time authorization + loading/refreshing the saved token.
# Token is stored ENCRYPTED via token_store. The client_secret JSON identifies the app.

import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from core.security import token_store

SERVICE_NAME = "gmail"
CLIENT_SECRET_FILE = str(Path(__file__).resolve().parent / "gmail_client_secret.json")

# Read freely; send is allowed by scope but GATED in Aegon's code (asks first).
# Calendar: events read+write (for reminders) — creation is GATED in Aegon's code.
# calendar.events supersedes calendar.readonly for event ops; calendar_read still works.
# One Google login covers Gmail + Calendar on this token.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


def authorize_gmail() -> None:
    """One-time: open the browser, log in, approve, save the token encrypted."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    token_store.save_token(SERVICE_NAME, json.loads(creds.to_json()))
    print("Gmail authorized and token saved (encrypted).")


def get_gmail_credentials() -> Credentials | None:
    """Load the saved token, refresh if expired, return ready credentials (or None)."""
    data = token_store.load_token(SERVICE_NAME)
    if not data:
        return None
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_store.save_token(SERVICE_NAME, json.loads(creds.to_json()))
        except Exception as e:
            print(f"[gmail_auth] Token refresh failed: {e}")
            return None
    return creds


def get_gmail_service():
    """Return an authenticated Gmail API service, or None if not authorized yet."""
    creds = get_gmail_credentials()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    """Return an authenticated Google Calendar API service, or None if not authorized yet.
    Reuses the same Google token as Gmail (calendar.readonly scope)."""
    creds = get_gmail_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)