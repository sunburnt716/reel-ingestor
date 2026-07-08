"""
gmail_client.py
---------------
Reads Instagram reel URLs out of a Gmail label using the official Gmail API.

Auth model (free):
  * You create OAuth credentials once in Google Cloud (Desktop app) and save
    them as credentials.json next to this file.
  * First run opens a browser for a one-time consent, then caches a token in
    token.json so future runs are silent.

Scope is gmail.modify so the script can mark handled messages as read (that's
how it avoids reprocessing the same reel on the next run).
"""

import base64
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = SCRIPT_DIR / "credentials.json"
TOKEN_PATH = SCRIPT_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

INSTAGRAM_URL_RE = re.compile(r"https?://\S*instagram\.com/\S+")


def _get_service():
    """Build an authenticated Gmail API service, running the OAuth flow if needed."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise SystemExit(
            "Google API libraries not found. Install them:\n"
            "  pip install google-api-python-client google-auth-httplib2 "
            "google-auth-oauthlib"
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise SystemExit(
                    f"Missing credentials.json at {CREDENTIALS_PATH}\n"
                    "Create OAuth credentials in Google Cloud (see README) and "
                    "save them there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def _extract_body_text(payload: dict) -> str:
    """Walk a Gmail message payload and pull out decoded text from all parts."""
    chunks = []

    def walk(part):
        body = part.get("body", {})
        data = body.get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            chunks.append(decoded)
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return "\n".join(chunks)


def get_reel_urls(label: str = "Reel") -> list[dict]:
    """
    Fetch unread messages under the given label and extract Instagram URLs.
    Returns a list of {"url": ..., "message_id": ...} dicts.
    """
    service = _get_service()

    query = f"label:{label} is:unread"
    resp = service.users().messages().list(userId="me", q=query).execute()
    messages = resp.get("messages", [])

    results = []
    for msg_meta in messages:
        msg_id = msg_meta["id"]
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )
        text = _extract_body_text(msg.get("payload", {}))
        # Fall back to snippet if body parsing found nothing
        if not text:
            text = msg.get("snippet", "")

        for match in INSTAGRAM_URL_RE.finditer(text):
            url = match.group(0).rstrip(">)],.\"'")
            results.append({"url": url, "message_id": msg_id})

    return results


def mark_read(message_id: str) -> None:
    """Remove the UNREAD label so a handled reel isn't picked up again."""
    service = _get_service()
    service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()