# tools/gmail_send/gmail_send_tool.py
# Sends an email from Gmail. ALWAYS GATED — asks every time.
# Before sending, tool_node shows the full To/Subject/Body via approval_prompt().
# The email body is REDACTED from the tool log; the recipient + subject are kept for audit.

import base64
from email.message import EmailMessage

from tools.base_connector import BaseConnector
from core.security.gmail_auth import get_gmail_service


class GmailSendConnector(BaseConnector):
    name = "gmail_send"
    version = "1.0.0"
    description = "Sends an email from the user's Gmail. Always requires approval."
    permission_level = "always_gated"

    def validate(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        to = payload.get("to", "")
        body = payload.get("body", "")
        return isinstance(to, str) and "@" in to and isinstance(body, str) and len(body.strip()) > 0

    def approval_prompt(self, payload: dict) -> str:
        to = payload.get("to", "")
        subject = payload.get("subject", "") or "(no subject)"
        body = payload.get("body", "")
        return (
            "I'm ready to send this email, Sir:\n\n"
            f"To: {to}\n"
            f"Subject: {subject}\n\n"
            f"{body}\n\n"
            "Shall I send it?"
        )

    def redact_for_log(self, payload: dict, result: dict) -> tuple:
        # Keep who/subject for the audit trail; never log the body.
        safe_payload = {
            "to": payload.get("to", ""),
            "subject": payload.get("subject", ""),
            "body": "[redacted]",
        }
        return safe_payload, result

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "Email needs a recipient and a body, Sir."}
        service = get_gmail_service()
        if service is None:
            return {"status": "error", "output": "Gmail is not connected, Sir."}
        to = payload["to"].strip()
        subject = (payload.get("subject") or "").strip()
        body = payload["body"]
        try:
            msg = EmailMessage()
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return {"status": "success", "output": f"Email sent to {to}."}
        except Exception as e:
            return {"status": "error", "output": f"Could not send the email: {e}"}