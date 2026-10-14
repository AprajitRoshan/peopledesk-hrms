import smtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.notification_log import NotificationLog

TEMPLATES = {
    "employee_onboarding": ("Welcome to PeopleDesk", "Hello {name},\n\nYour employee account has been created. You can now sign in to the PeopleDesk HRMS portal.\n\nRegards,\nHR Team"),
    "leave_applied": ("Leave request received", "Hello {name},\n\nYour leave request for {start_date} to {end_date} has been received and is pending review.\n\nRegards,\nHR Team"),
    "leave_decision": ("Leave request {decision}", "Hello {name},\n\nYour leave request for {start_date} to {end_date} was {decision}.\n\nRegards,\nHR Team"),
    "payroll_processed": ("Payroll processed for {period}", "Hello {name},\n\nYour payroll for {period} has been processed. Sign in to PeopleDesk to view your payroll details.\n\nRegards,\nPayroll Team"),
    "salary_slip_generated": ("Salary slip generated for {period}", "Hello {name},\n\nYour salary slip for {period} has been generated and is available in PeopleDesk. Sign in to download it.\n\nRegards,\nPayroll Team"),
}


def send_template_notification(db: Session, *, recipient: str, template_key: str, context: dict,
                               related_entity_type: str | None = None, related_entity_id: int | str | None = None) -> None:
    """Send a configured SMTP email, or record it as logged when SMTP is not configured."""
    template = TEMPLATES.get(template_key)
    if not template:
        return
    subject_template, body_template = template
    safe_context = {key: str(value) for key, value in context.items()}
    try:
        subject = subject_template.format(**safe_context)
        body = body_template.format(**safe_context)
    except (KeyError, ValueError):
        subject, body = subject_template, body_template

    log = NotificationLog(recipient=recipient, template_key=template_key, subject=subject,
        status="logged", related_entity_type=related_entity_type,
        related_entity_id=str(related_entity_id) if related_entity_id is not None else None)
    db.add(log)
    db.flush()

    if not (settings.smtp_host and settings.smtp_from_email):
        return
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(message)
        log.status = "sent"
    except (OSError, smtplib.SMTPException) as exc:
        # Notification failure must not roll back a successful HR transaction.
        log.status = "failed"
        log.error_message = str(exc)[:2000]
