"""
SMS utility — OTP delivery via Twilio (with console fallback for dev).

Environment variables:
    TWILIO_ACCOUNT_SID   Twilio account SID
    TWILIO_AUTH_TOKEN    Twilio auth token
    TWILIO_FROM_NUMBER   Twilio phone number (E.164 format, e.g. +15551234567)

If any of the three env vars are unset, the OTP is printed to stdout instead
of sending a real SMS. This makes local development work without a Twilio account.
"""

import os
import logging
from base64 import b64encode

import httpx

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

_TWILIO_CONFIGURED = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER])


async def send_otp_sms(phone_number: str, otp_code: str) -> None:
    """Send a one-time passcode to phone_number via SMS.

    Falls back to console logging when Twilio env vars are not configured.
    Raises RuntimeError if Twilio is configured but the request fails.
    """
    if not _TWILIO_CONFIGURED:
        logger.warning(
            "Twilio not configured — OTP for %s: %s  (dev mode, not sent via SMS)",
            phone_number, otp_code,
        )
        return

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{TWILIO_ACCOUNT_SID}/Messages.json"
    )
    credentials = b64encode(
        f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "From": TWILIO_FROM_NUMBER,
                "To":   phone_number,
                "Body": f"Your u-vote verification code is: {otp_code}. Valid for 10 minutes.",
            },
        )

    if resp.status_code not in (200, 201):
        logger.error("Twilio SMS failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Failed to send SMS: {resp.status_code}")

    logger.info("OTP SMS sent to %s", phone_number)
