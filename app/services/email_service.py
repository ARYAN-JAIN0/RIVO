from __future__ import annotations

import logging
import os
import smtplib
import uuid
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.exc import SQLAlchemyError

from app.database.db import get_db_session
from app.database.models import EmailLog, Lead
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)


@dataclass
class EmailTemplate:
    subject: str
    html_body: str
    text_body: str


class EmailService:
    def __init__(self) -> None:
        self.smtp_host = os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("GMAIL_SMTP_PORT", "587"))
        self.smtp_user = os.getenv("GMAIL_SMTP_USER")
        self.smtp_app_password = os.getenv("GMAIL_SMTP_APP_PASSWORD")
        self.from_email = os.getenv("GMAIL_FROM_EMAIL", self.smtp_user or "noreply@rivo.app")
        self.sandbox_mode = os.getenv("SMTP_SANDBOX_MODE", "true").lower() in {"1", "true", "yes", "on"}
        self.base_tracking_url = os.getenv("TRACKING_BASE_URL", "http://localhost:8000")

    def _tracking_pixel(self, tracking_id: str) -> str:
        return f'<img src="{self.base_tracking_url}/api/v1/track/open/{tracking_id}" width="1" height="1" style="display:none;" />'

    def build_template(self, recipient_name: str, company: str, message: str, tracking_id: str) -> EmailTemplate:
        subject = f"Quick idea for {company}"
        text = f"Hi {recipient_name},\n\n{message}\n\nBest regards,\nRIVO SDR Team"
        html = (
            f"<p>Hi {recipient_name},</p>"
            f"<p>{message}</p>"
            f"<p>Best regards,<br/>RIVO SDR Team</p>"
            f"{self._tracking_pixel(tracking_id)}"
        )
        return EmailTemplate(subject=subject, html_body=html, text_body=text)

    def _log_email(
        self,
        tenant_id: int,
        lead_id: int,
        recipient_email: str,
        subject: str,
        body: str,
        tracking_id: str,
        status: str,
        error_message: str | None = None,
        message_type: str = "outbound",
    ) -> int | None:
        try:
            with get_db_session() as session:
                row = EmailLog(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    recipient_email=sanitize_text(recipient_email, 320),
                    subject=sanitize_text(subject, 500),
                    body=sanitize_text(body, 8000),
                    tracking_id=tracking_id,
                    status=status,
                    error_message=sanitize_text(error_message or "", 2000) or None,
                    message_type=message_type,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                return row.id
        except SQLAlchemyError:
            logger.exception("email.log.failed", extra={"event": "email.log.failed"})
            return None

    def send_email(self, tenant_id: int, lead_id: int, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        tracking_id = uuid.uuid4().hex
        if self.sandbox_mode:
            self._log_email(tenant_id, lead_id, to_email, subject, text_body, tracking_id, "sandbox_sent")
            logger.info("email.sandbox.sent", extra={"event": "email.sandbox.sent", "to_email": to_email})
            return True

        if not (self.smtp_user and self.smtp_app_password):
            self._log_email(tenant_id, lead_id, to_email, subject, text_body, tracking_id, "failed", "smtp credentials missing")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_app_password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            self._log_email(tenant_id, lead_id, to_email, subject, text_body, tracking_id, "sent")
            return True
        except Exception as exc:
            self._log_email(tenant_id, lead_id, to_email, subject, text_body, tracking_id, "failed", str(exc))
            logger.exception("email.send.failed", extra={"event": "email.send.failed", "to_email": to_email})
            return False

    def send_followup(self, lead: Lead, day: int) -> bool:
        msg = f"Following up on my previous note from a few days ago. Would a short 15-minute call this week be useful? (Follow-up Day {day})"
        template = self.build_template(lead.name or "there", lead.company or "your team", msg, uuid.uuid4().hex)
        return self.send_email(lead.tenant_id, lead.id, lead.email, f"Follow-up: {template.subject}", template.html_body, template.text_body)
