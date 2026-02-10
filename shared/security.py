"""
Shared security utilities for authentication and token generation
"""
import secrets
import hashlib
from datetime import datetime, timedelta
import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_voting_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token
    Returns a URL-safe token
    """
    return secrets.token_urlsafe(length)

def generate_token_expiry(hours: int = 168) -> datetime:
    """
    Generate token expiry time (default: 7 days)
    """
    return datetime.now() + timedelta(hours=hours)

def hash_vote(election_id: int, option_id: int, timestamp: str, salt: str = None) -> str:
    """
    Generate a hash for a vote record
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    data = f"{election_id}{option_id}{timestamp}{salt}"
    return hashlib.sha256(data.encode()).hexdigest()

def create_hash_chain(previous_hash: str, current_data: str) -> str:
    """
    Create a hash chain by hashing previous hash + current data
    """
    combined = f"{previous_hash}{current_data}"
    return hashlib.sha256(combined.encode()).hexdigest()
