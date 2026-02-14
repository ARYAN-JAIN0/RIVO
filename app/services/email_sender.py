"""SMTP email sender service."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_config
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class EmailSender(BaseService):
    """Service for sending transactional emails via SMTP."""

    def __init__(self):
        super().__init__()
        self.config = get_config()

    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        if not self.config.SMTP_SERVER:
            logger.warning("email.smtp_not_configured", extra={"event": "email.smtp_not_configured"})
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.config.SMTP_USERNAME or "noreply@rivo.app"
            message["To"] = to_email
            message.attach(MIMEText(body, "html" if is_html else "plain"))

            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                server.send_message(message)
            return True
        except Exception:
            logger.exception("email.send_failed", extra={"event": "email.send_failed", "to_email": to_email})
            return False

    def send_bulk_emails(
        self, recipients: list[str], subject: str, body: str, is_html: bool = False
    ) -> tuple[int, int]:
        successful = 0
        failed = 0
        for recipient in recipients:
            if self.send_email(recipient, subject, body, is_html):
                successful += 1
            else:
                failed += 1
        return successful, failed

