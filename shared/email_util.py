"""
Email utility — async SMTP email delivery using aiosmtplib.

Environment variables:
    SMTP_HOST      SMTP server hostname  (default: smtp.gmail.com)
    SMTP_PORT      SMTP server port      (default: 587 → Gmail STARTTLS)
    SMTP_USER      SMTP username / sender email
    SMTP_PASSWORD  SMTP password (Gmail App Password)
    SMTP_USE_TLS   Set to "true" for STARTTLS connections (default: true)
    SMTP_USE_SSL   Set to "true" for implicit TLS/SSL on port 465 (default: false)
    SMTP_FROM      Sender address        (default: uvote.verify@gmail.com)
    FRONTEND_URL   Public URL of the voting service, used to build vote links
"""

import os
import logging
from email.message import EmailMessage
from typing import Optional

import aiosmtplib
import httpx

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
SMTP_FROM = os.getenv("SMTP_FROM", "uvote.verify@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5003")

# SendGrid support (preferred if SENDGRID_API_KEY is set)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM = os.getenv("SENDGRID_FROM", SMTP_FROM)


async def _send_via_sendgrid(to: str, subject: str, body_text: str, body_html: Optional[str] = None):
    """Send email via SendGrid Web API (async using httpx).

    This is used when SENDGRID_API_KEY environment variable is present.
    """
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY is not configured")

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    personalizations = [{"to": [{"email": to}]}]
    content = [{"type": "text/plain", "value": body_text}]
    if body_html:
        content.append({"type": "text/html", "value": body_html})

    payload = {
        "personalizations": personalizations,
        "from": {"email": SENDGRID_FROM},
        "subject": subject,
        "content": content,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 200 and resp.status_code < 300:
            logger.info("SendGrid accepted message to %s: %s", to, subject)
            return
        else:
            logger.error("SendGrid failed (%s): %s", resp.status_code, resp.text)
            resp.raise_for_status()


async def send_email(to: str, subject: str, body_text: str, body_html: Optional[str] = None):
    """Send an email asynchronously.

    If SENDGRID_API_KEY is present, prefer using SendGrid via HTTPS. Otherwise
    fall back to SMTP using aiosmtplib.
    """
    # Prefer SendGrid when configured (works around outbound SMTP blocking)
    if SENDGRID_API_KEY:
        try:
            await _send_via_sendgrid(to, subject, body_text, body_html)
            return
        except Exception as e:
            logger.warning("SendGrid send failed, falling back to SMTP: %s", e)

    # --- Build EmailMessage for SMTP fallback ---
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)

    if body_html:
        msg.add_alternative(body_html, subtype="html")

    kwargs: dict = {
        "hostname": SMTP_HOST,
        "port": SMTP_PORT,
        "timeout": 10,
    }
    if SMTP_USE_SSL:
        kwargs["use_tls"] = True
    else:
        kwargs["start_tls"] = SMTP_USE_TLS

    if SMTP_USER and SMTP_PASSWORD:
        kwargs["username"] = SMTP_USER
        kwargs["password"] = SMTP_PASSWORD

    logger.info("Sending email to %s via %s:%s (start_tls=%s use_ssl=%s)",
                to, SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USE_SSL)
    try:
        await aiosmtplib.send(msg, **kwargs)
        logger.info("Email sent to %s: %s", to, subject)
    except Exception as e:
        logger.error("Failed to send email to %s via %s:%s (start_tls=%s use_ssl=%s): %s",
                     to, SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USE_SSL, e)
        raise


async def send_voting_token_email(
    to_email: str,
    token: str,
    election_title: str,
    expires_at: str,
):
    """Send a voter their unique voting link."""
    vote_url = f"{FRONTEND_URL}/vote/{token}"

    subject = f"Your Voting Token — {election_title}"

    body_text = (
        f"You have been invited to vote in: {election_title}\n\n"
        f"Your unique voting link:\n{vote_url}\n\n"
        f"This link expires at: {expires_at}\n\n"
        "Important:\n"
        "- This link can only be used ONCE.\n"
        "- Your vote is anonymous and cannot be traced back to you.\n"
        "- Do not share this link with anyone.\n\n"
        "— Secure Voting System"
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0d6efd; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">🗳️ Secure Voting System</h1>
        </div>
        <div style="padding: 30px; background: #f8f9fa;">
            <h2>You've been invited to vote</h2>
            <p><strong>Election:</strong> {election_title}</p>
            <p>Click the button below to cast your vote:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{vote_url}"
                   style="background: #0d6efd; color: white; padding: 15px 40px;
                          text-decoration: none; border-radius: 5px; font-size: 18px;">
                    Cast Your Vote
                </a>
            </div>
            <p style="color: #6c757d; font-size: 14px;">
                Or copy this link into your browser:<br>
                <code style="background: #e9ecef; padding: 5px 10px; border-radius: 3px;">
                    {vote_url}
                </code>
            </p>
            <hr style="border: 1px solid #dee2e6;">
            <p style="color: #6c757d; font-size: 13px;">
                ⏰ <strong>Expires:</strong> {expires_at}<br>
                🔒 This link is single-use and anonymous.<br>
                ⚠️ Do not share this link with anyone.
            </p>
        </div>
    </div>
    """

    await send_voting_token_email_raw(to_email, subject, body_text, body_html)


async def send_voting_token_email_raw(to: str, subject: str, text: str, html: str):
    """Wrapper to make testing easier."""
    await send_email(to, subject, text, html)


async def send_otp_email(to_email: str, otp_code: str, election_title: str):
    """Send a 6-digit OTP code for voter MFA verification."""
    subject = f"Your Verification Code — {election_title}"

    body_text = (
        f"Your verification code for {election_title} is:\n\n"
        f"    {otp_code}\n\n"
        "This code expires in 10 minutes.\n"
        "If you did not request this, please ignore this email.\n\n"
        "— Secure Voting System"
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0d6efd; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">🗳️ Secure Voting System</h1>
        </div>
        <div style="padding: 30px; background: #f8f9fa; text-align: center;">
            <h2>Verification Code</h2>
            <p>Enter this code to verify your identity for:</p>
            <p><strong>{election_title}</strong></p>
            <div style="background: #ffffff; border: 2px dashed #0d6efd;
                        padding: 20px; margin: 25px auto; max-width: 250px;
                        border-radius: 10px;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px;
                             color: #0d6efd; font-family: monospace;">
                    {otp_code}
                </span>
            </div>
            <p style="color: #6c757d; font-size: 14px;">
                ⏰ This code expires in <strong>10 minutes</strong>.<br>
                🔒 Do not share this code with anyone.
            </p>
        </div>
    </div>
    """

    await send_email(to_email, subject, body_text, body_html)


async def check_smtp_connection() -> tuple[bool, str]:
    """Attempt to connect to the configured SMTP server and authenticate.

    Returns (True, 'ok') on success or (False, error_message) on failure.
    """
    try:
        if SMTP_USE_SSL:
            smtp = aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT, timeout=10, use_tls=True)
        else:
            smtp = aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT, timeout=10, use_tls=False)

        await smtp.connect()
        if not SMTP_USE_SSL and SMTP_USE_TLS:
            await smtp.starttls()

        if SMTP_USER and SMTP_PASSWORD:
            await smtp.login(SMTP_USER, SMTP_PASSWORD)

        await smtp.quit()
        return True, "ok"
    except Exception as e:
        logger.error("SMTP connectivity check failed: %s", e)
        return False, str(e)
