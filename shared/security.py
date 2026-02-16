"""
Shared security utilities.

Covers:
  - Password hashing (bcrypt via passlib)
  - Voting-token generation (identity-linked, emailed to voters)
  - Blind ballot-token generation (anonymised, unlinkable to voter)
  - Election encryption-key generation (for pgp_sym_encrypt)
  - Receipt-token generation (voter can verify ballot was recorded)
  - Generic hash helpers (SHA-256 hash chains)

Anonymity protocol
------------------
1. Voter authenticates via voting_token + DOB  (identity-linked)
2. Auth-service generates a BLIND ballot_token
   using a fresh random value - NOT derived from voter_id
3. Auth-service marks voter.has_voted = TRUE
   but does NOT store which ballot_token was issued
4. Voter uses ballot_token to cast an encrypted ballot
   (no identity attached to the ballot row)
"""

import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta

from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt via passlib."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return pwd_context.verify(password, hashed)


# ---------------------------------------------------------------------------
# Voting token  (identity-linked - emailed to voters)
# ---------------------------------------------------------------------------

def generate_voting_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token for voter email links."""
    return secrets.token_urlsafe(length)


def generate_token_expiry(hours: int = 168) -> datetime:
    """Generate token expiry timestamp (default 7 days)."""
    return datetime.now() + timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Blind ballot token  (anonymity-preserving)
# ---------------------------------------------------------------------------
_BALLOT_SECRET = os.getenv(
    "BALLOT_TOKEN_SECRET", "ballot-secret-change-in-production"
)


def generate_blind_ballot_token() -> str:
    """Return a ballot token that cannot be linked back to a voter.

    Implementation:
      Pure cryptographic randomness (secrets.token_urlsafe).
      The token is inserted into blind_tokens with only an
      election_id - no voter_id, no voting_token reference.
      Even the issuing server cannot later determine which voter
      received which ballot token.

    For future iterations you could upgrade this to an RSA blind-
    signature scheme (Chaum 1983) where the voter blinds a nonce,
    the server signs it, and the voter unblinds to obtain a valid
    signature the server has never seen in the clear.
    """
    return secrets.token_urlsafe(32)


def generate_receipt_token() -> str:
    """Generate a receipt token so the voter can verify their ballot was recorded."""
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# Election encryption key
# ---------------------------------------------------------------------------

def generate_election_key() -> str:
    """Generate a symmetric passphrase for pgp_sym_encrypt / pgp_sym_decrypt."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Hash utilities
# ---------------------------------------------------------------------------

def hash_vote(election_id, option_id, timestamp, salt=None):
    """Generate a SHA-256 hash for a vote record."""
    if salt is None:
        salt = secrets.token_hex(16)
    data = f"{election_id}{option_id}{timestamp}{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


def create_hash_chain(previous_hash, current_data):
    """Create a hash-chain entry: SHA-256(previous_hash || current_data)."""
    combined = f"{previous_hash}{current_data}"
    return hashlib.sha256(combined.encode()).hexdigest()
