"""
Email Sender Module.
Handles MIME message assembly, resume attachments, live SMTP transmission,
and safe outbox journaling for Dry-Run testing.
"""

import json
import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from .models import OutreachMessage, OutreachStatus

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        sender_name: str = "Job Applicant",
        sender_email: str = "",
        dry_run: bool = True,
        outbox_dir: Optional[Path] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_name = sender_name
        self.sender_email = sender_email or smtp_user or "applicant@example.com"
        self.dry_run = dry_run
        self.outbox_dir = outbox_dir or Path("outbox")
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def build_email(self, message: OutreachMessage, resume_path: Optional[str] = None) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = f"{message.recipient.full_name} <{message.recipient.email}>"
        msg["Subject"] = message.subject
        msg.set_content(message.body)

        # Attach resume if path exists
        if resume_path and Path(resume_path).exists():
            file_path = Path(resume_path)
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                subtype = "pdf" if file_path.suffix.lower() == ".pdf" else "octet-stream"
                msg.add_attachment(
                    content,
                    maintype="application",
                    subtype=subtype,
                    filename=file_path.name
                )
            except Exception as e:
                logger.warning(f"Could not attach resume file: {e}")

        return msg

    def send(self, message: OutreachMessage, resume_path: Optional[str] = None) -> bool:
        """
        Sends the message via SMTP or saves to outbox in Dry-Run mode.
        """
        try:
            email_msg = self.build_email(message, resume_path=resume_path)

            if self.dry_run:
                self._save_to_outbox(message, email_msg, resume_path)
                message.status = OutreachStatus.SENT
                message.sent_at = datetime.utcnow()
                logger.info(f"[DRY-RUN] Saved draft for {message.recipient.email} to outbox.")
                return True

            if not self.smtp_user or not self.smtp_password:
                err = "Cannot send live email: SMTP_USER or SMTP_PASSWORD not configured."
                message.status = OutreachStatus.FAILED
                message.error_message = err
                logger.error(err)
                return False

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(email_msg)

            message.status = OutreachStatus.SENT
            message.sent_at = datetime.utcnow()
            logger.info(f"Successfully sent live email to {message.recipient.email}")
            return True

        except Exception as e:
            message.status = OutreachStatus.FAILED
            message.error_message = str(e)
            logger.error(f"Failed to send email to {message.recipient.email}: {e}")
            return False

    def _save_to_outbox(self, message: OutreachMessage, email_msg: EmailMessage, resume_path: Optional[str]):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_email = message.recipient.email.replace("@", "_at_").replace(".", "_")
        filename_base = f"{timestamp}_{safe_email}"

        # 1. Save raw .eml
        eml_path = self.outbox_dir / f"{filename_base}.eml"
        with open(eml_path, "wb") as f:
            f.write(email_msg.as_bytes())

        # 2. Save metadata JSON
        json_path = self.outbox_dir / f"{filename_base}.json"
        metadata = {
            "to": message.recipient.email,
            "recipient_name": message.recipient.full_name,
            "recipient_role": message.recipient.role_title,
            "company": message.job.company_name,
            "job_title": message.job.title,
            "subject": message.subject,
            "body": message.body,
            "attached_resume": resume_path,
            "saved_at": datetime.utcnow().isoformat()
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
