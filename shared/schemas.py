"""
Shared Pydantic schemas — request validation and response serialisation.

Organised by bounded context:
    1. Auth        — registration, login, JWT, blind ballot tokens
    2. Election    — CRUD, voters, results, audit
    3. Voting      — ballot, encrypted vote submission, receipt verification
    4. Common      — health, errors
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTH SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_id: int | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenVerifyRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    message: str | None = None
    organiser_id: int | None = None
    token: str | None = None


class TokenVerifyResponse(BaseModel):
    valid: bool
    organiser_id: int | None = None
    email: str | None = None
    error: str | None = None


# Blind ballot token (issued after MFA, unlinkable to voter identity)
class BallotTokenResponse(BaseModel):
    ballot_token: str
    election_id: int


# ══════════════════════════════════════════════════════════════════════════════
# 2. ELECTION SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class ElectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    options: list[str] = Field(min_length=2)


class ElectionOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    voter_count: int = 0
    vote_count: int = 0


class ElectionOptionOut(BaseModel):
    id: int
    text: str
    order: int


# Voter management
class VoterAddRequest(BaseModel):
    email: EmailStr
    date_of_birth: str  # YYYY-MM-DD


class VoterOut(BaseModel):
    id: int
    email: str
    date_of_birth: str
    has_voted: bool
    has_token: bool
    created_at: datetime


class TokenGenerateRequest(BaseModel):
    expiry_hours: int = 168  # 7 days


class GeneratedToken(BaseModel):
    email: str
    token: str
    expires_at: datetime


class TokenValidateResponse(BaseModel):
    valid: bool
    election_id: int | None = None
    voter_id: int | None = None
    error: str | None = None


# Results
class ResultOption(BaseModel):
    option_id: int
    option_text: str
    vote_count: int
    percentage: float


class ResultSummary(BaseModel):
    total_votes: int
    total_voters: int
    turnout_percentage: float


class ElectionResults(BaseModel):
    election: dict
    summary: ResultSummary
    results: list[ResultOption]


# Audit
class AuditEntry(BaseModel):
    vote_id: int
    ballot_hash: str
    previous_hash: str | None
    cast_at: datetime
    sequence: int


class AuditTrail(BaseModel):
    election_id: int
    total_votes: int
    hash_chain_valid: bool
    audit_trail: list[AuditEntry]


# ══════════════════════════════════════════════════════════════════════════════
# 3. VOTING SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class BallotOption(BaseModel):
    id: int
    text: str
    order: int


class BallotResponse(BaseModel):
    election: dict
    options: list[BallotOption]


class CastVoteRequest(BaseModel):
    ballot_token: str
    option_id: int


class VoteResponse(BaseModel):
    message: str
    receipt_token: str
    ballot_hash: str


class ReceiptVerifyResponse(BaseModel):
    verified: bool
    receipt_token: str | None = None
    ballot_hash: str | None = None
    election_id: int | None = None
    cast_at: datetime | None = None


# ══════════════════════════════════════════════════════════════════════════════
# 4. COMMON
# ══════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorResponse(BaseModel):
    error: str
