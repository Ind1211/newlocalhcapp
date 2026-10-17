"""
Real email delivery via plain SMTP — deliberately smtplib (Python's own standard
library), not a vendor SDK. This works against any real SMTP provider (Gmail,
SendGrid's SMTP relay, AWS SES's SMTP endpoint, an internal mail server) without
locking this app into one vendor's specific API, and it's the smallest possible
new dependency for what's being asked: literally none, since smtplib ships with
Python itself.

This is a genuinely different concern from Auth0's own password-reset email
(auth0_management.trigger_password_reset_email) — that one is Auth0's own
transactional email, sent by Auth0's infrastructure for account security
specifically. This module is for the app's own notifications, sent through
whatever SMTP credentials the deployment configures.
"""

import os
import smtplib
from email.mime.text import MIMEText


class EmailError(Exception):
    pass


def send_email(to_address: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_address = os.environ.get("SMTP_FROM_ADDRESS", username)

    if not host or not username or not password:
        raise EmailError(
            "SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD are not set — email notifications "
            "require real SMTP credentials from your email provider (Gmail, SendGrid, "
            "AWS SES, or your own mail server all work over plain SMTP)."
        )

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_address, [to_address], message.as_string())
    except smtplib.SMTPException as e:
        raise EmailError(f"Could not send email: {e}") from e
    except OSError as e:
        # Connection-level failures (wrong host, network unreachable, timeout) —
        # a genuinely different failure mode than SMTPException, worth its own
        # branch so the resulting message is honest about what actually failed.
        raise EmailError(f"Could not connect to the SMTP server: {e}") from e
