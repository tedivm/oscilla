from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import getLogger
from typing import Dict

import aiosmtplib

from oscilla.settings import settings

logger = getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when an outbound SMTP operation fails."""


async def send_email(to: str, subject: str, body_html: str, body_text: str) -> None:
    """Send a transactional email via SMTP.

    When ``smtp_host`` is not configured, the call is a silent no-op so that
    development environments without an SMTP server do not break email flows.
    Raises ``EmailDeliveryError`` if the SMTP operation itself fails.
    """
    if settings.smtp_host is None:
        logger.debug("smtp_host is not configured; skipping email send to %s", to)
        return

    from_address = settings.smtp_from_address or "oscilla@localhost"

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to
    message.attach(MIMEText(body_text, "plain"))
    message.attach(MIMEText(body_html, "html"))

    kwargs: Dict[str, object] = {
        "hostname": settings.smtp_host,
        "port": settings.smtp_port,
        "start_tls": settings.smtp_use_tls,
    }
    if settings.smtp_user is not None:
        kwargs["username"] = settings.smtp_user
    if settings.smtp_password is not None:
        kwargs["password"] = settings.smtp_password.get_secret_value()

    try:
        async with aiosmtplib.SMTP(**kwargs) as smtp:  # type: ignore[arg-type]
            await smtp.send_message(message)
    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", to, exc)
        raise EmailDeliveryError(f"Failed to send email to {to}") from exc
