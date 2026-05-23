"""
CSRF token utilities using itsdangerous.URLSafeTimedSerializer.

generate_csrf_token — create a signed, time-limited token and store it in the session.
validate_csrf_token — verify the submitted token against the session value.
"""
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _get_serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    return URLSafeTimedSerializer(secret)


def generate_csrf_token(session: dict) -> str:
    """Generate a signed CSRF token, store it in the session, and return it."""
    s = _get_serializer()
    payload = secrets.token_hex(16)
    token = s.dumps(payload)
    session["csrf_token"] = token
    return token


def validate_csrf_token(
    session: dict, submitted_token: str, max_age: int = 3600
) -> bool:
    """Return True iff submitted_token matches the session value and is not expired."""
    if not submitted_token:
        return False
    stored = session.get("csrf_token")
    if not stored:
        return False
    if submitted_token != stored:
        return False
    s = _get_serializer()
    try:
        s.loads(submitted_token, max_age=max_age)
        return True
    except (BadSignature, SignatureExpired):
        return False
