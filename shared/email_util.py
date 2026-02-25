"""
Email utility — async SMTP email delivery using aiosmtplib.

Environment variables:
    SMTP_HOST      SMTP server hostname  (default: smtp.gmail.com)
    SMTP_PORT      SMTP server port      (default: 587 → Gmail STARTTLS)
    SMTP_USER      SMTP username / sender email
    SMTP_PASS      SMTP password (Gmail App Password)
    SMTP_USE_TLS   Set to "true" for STARTTLS connections (default: true)
    SMTP_FROM      Sender address        (default: uvote.verify@gmail.com)
    FRONTEND_URL   Public URL of the frontend, used to build vote links
"""

import os
import logging
from email.message import EmailMessage

import aiosmtplib

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587").strip() or "587")
SMTP_USER = os.getenv("SMTP_USER", "uvote.verify@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_FROM = os.getenv("SMTP_FROM", "uvote.verify@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8081")


async def send_email(to: str, subject: str, body_text: str, body_html: str | None = None):
    """Send an email asynchronously via SMTP."""
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
        "start_tls": SMTP_USE_TLS,
    }
    if SMTP_USER and SMTP_PASS:
        kwargs["username"] = SMTP_USER
        kwargs["password"] = SMTP_PASS

    try:
        await aiosmtplib.send(msg, **kwargs)
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
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
