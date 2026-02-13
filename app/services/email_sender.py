# Email Sender

"""
Email Sender Service

Service for sending emails via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_config
from app.services.base_service import BaseService


class EmailSender(BaseService):
    """Service for sending emails via SMTP."""

    def __init__(self):
        super().__init__()
        self.config = get_config()

    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            is_html: Whether body is HTML (default: False)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if SMTP is configured
            if not self.config.SMTP_SERVER:
                print("⚠️  SMTP not configured. Skipping email send.")
                return False

            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.config.SMTP_USERNAME or "noreply@rivo.app"
            message["To"] = to_email

            # Attach body
            mime_type = "html" if is_html else "plain"
            message.attach(MIMEText(body, mime_type))

            # Send email
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                server.send_message(message)

            return True

        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False

    def send_bulk_emails(self, recipients: list[str], subject: str, body: str, is_html: bool = False) -> tuple[int, int]:
        """
        Send emails to multiple recipients.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Email body content
            is_html: Whether body is HTML (default: False)

        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0

        for email in recipients:
            if self.send_email(email, subject, body, is_html):
                successful += 1
            else:
                failed += 1

        return successful, failed
