-- Secure Voting System - Database Schema
--
-- Design principle: ANONYMITY vs ACCOUNTABILITY
--   We can prove a voter voted (prevent double-voting)
--   We CANNOT determine how they voted (ballot secrecy)
--   The encrypted_ballots table has NO voter_id / user_id foreign key
--   Linkage between identity and choice is broken by blind ballot tokens
--
-- Table groups:
--   1. Tenancy      - organisations (who deployed the system)
--   2. Identity     - organisers, voters, MFA records
--   3. Election     - elections, candidates/options (source data)
--   4. Ballot Auth  - voting_tokens, blind_tokens (the anonymity bridge)
--   5. The Ledger   - encrypted_ballots, vote_receipts, audit_log (immutable)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ==========================================================================
-- 1. TENANCY
-- ==========================================================================

CREATE TABLE organisations (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    org_type   VARCHAR(50) CHECK (org_type IN ('government', 'university', 'corporate', 'other')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- 2. IDENTITY
-- ==========================================================================

CREATE TABLE organisers (
    id            SERIAL PRIMARY KEY,
    org_id        INTEGER REFERENCES organisations(id) ON DELETE CASCADE,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) DEFAULT 'admin' CHECK (role IN ('admin', 'super_admin')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- 3. ELECTION METADATA (source data created by admins)
-- ==========================================================================

CREATE TABLE elections (
    id             SERIAL PRIMARY KEY,
    organiser_id   INTEGER REFERENCES organisers(id) ON DELETE CASCADE,
    org_id         INTEGER REFERENCES organisations(id) ON DELETE SET NULL,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    status         VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
    encryption_key TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opened_at      TIMESTAMP,
    closed_at      TIMESTAMP
);

CREATE TABLE voters (
    id          SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    email       VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    has_voted   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(election_id, email)
);

CREATE TABLE voter_mfa (
    id          SERIAL PRIMARY KEY,
    token       VARCHAR(255) NOT NULL,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE election_options (
    id            SERIAL PRIMARY KEY,
    election_id   INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    option_text   VARCHAR(255) NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- 4. BALLOT AUTHORISATION (the anonymity bridge)
--
-- Flow:
--   1. Voter clicks email link     -> voting_token validated (identity-linked)
--   2. Voter passes DOB MFA        -> auth-service issues a BLIND ballot_token
--   3. Auth-service marks voter.has_voted = TRUE
--      but does NOT record which ballot_token was given to which voter
--   4. Voter uses ballot_token to cast encrypted ballot (no identity attached)
--
-- blind_tokens has NO voter_id and NO voting_token FK.
-- This is the critical architectural decision for ballot secrecy.
-- ==========================================================================

CREATE TABLE voting_tokens (
    id          SERIAL PRIMARY KEY,
    token       VARCHAR(255) UNIQUE NOT NULL,
    voter_id    INTEGER REFERENCES voters(id) ON DELETE CASCADE,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    is_used     BOOLEAN DEFAULT FALSE,
    expires_at  TIMESTAMP NOT NULL,
    used_at     TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE voter_mfa
    ADD CONSTRAINT fk_voter_mfa_token
    FOREIGN KEY (token) REFERENCES voting_tokens(token) ON DELETE CASCADE;

CREATE TABLE blind_tokens (
    id           SERIAL PRIMARY KEY,
    ballot_token VARCHAR(255) UNIQUE NOT NULL,
    election_id  INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    is_used      BOOLEAN DEFAULT FALSE,
    issued_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at      TIMESTAMP
    -- NO voter_id or voting_token_id  (this is what makes the vote anonymous)
);

-- ==========================================================================
-- 5. THE LEDGER (immutable encrypted vote records)
--
-- encrypted_ballots has NO voter_id, NO user_id, NO ballot_token_id.
-- Once a ballot is cast it is completely detached from identity.
-- ==========================================================================

CREATE TABLE encrypted_ballots (
    id             SERIAL PRIMARY KEY,
    election_id    INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    encrypted_vote BYTEA NOT NULL,
    ballot_hash    VARCHAR(255) NOT NULL,
    previous_hash  VARCHAR(255),
    receipt_token  VARCHAR(255) UNIQUE NOT NULL,
    cast_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- NO voter_id, NO user_id, NO ballot_token_id
);

CREATE TABLE vote_receipts (
    id            SERIAL PRIMARY KEY,
    election_id   INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    receipt_token VARCHAR(255) UNIQUE NOT NULL,
    ballot_hash   VARCHAR(255) NOT NULL,
    cast_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tallied_votes (
    id          SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    option_id   INTEGER REFERENCES election_options(id) ON DELETE CASCADE,
    vote_count  INTEGER NOT NULL DEFAULT 0,
    tallied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_log (
    id            SERIAL PRIMARY KEY,
    event_type    VARCHAR(50) NOT NULL,
    election_id   INTEGER REFERENCES elections(id) ON DELETE SET NULL,
    actor_type    VARCHAR(20) CHECK (actor_type IN ('organiser', 'voter', 'system')),
    actor_id      INTEGER,
    detail        JSONB,
    event_hash    VARCHAR(255),
    previous_hash VARCHAR(255),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================================
-- INDEXES
-- ==========================================================================

CREATE INDEX idx_organisers_org      ON organisers(org_id);
CREATE INDEX idx_elections_organiser ON elections(organiser_id);
CREATE INDEX idx_elections_org       ON elections(org_id);
CREATE INDEX idx_elections_status    ON elections(status);
CREATE INDEX idx_voters_election     ON voters(election_id);
CREATE INDEX idx_voters_has_voted    ON voters(election_id, has_voted);
CREATE INDEX idx_tokens_election     ON voting_tokens(election_id);
CREATE INDEX idx_tokens_token        ON voting_tokens(token);
CREATE INDEX idx_blind_election      ON blind_tokens(election_id);
CREATE INDEX idx_blind_token         ON blind_tokens(ballot_token);
CREATE INDEX idx_ballots_election    ON encrypted_ballots(election_id);
CREATE INDEX idx_ballots_receipt     ON encrypted_ballots(receipt_token);
CREATE INDEX idx_receipts_token      ON vote_receipts(receipt_token);
CREATE INDEX idx_tallied_election    ON tallied_votes(election_id);
CREATE INDEX idx_audit_election      ON audit_log(election_id);
CREATE INDEX idx_audit_type          ON audit_log(event_type);
CREATE INDEX idx_mfa_token           ON voter_mfa(token);

-- ==========================================================================
-- TRIGGERS - immutability and automatic hashing
-- ==========================================================================

-- Encrypted ballots are IMMUTABLE
CREATE OR REPLACE FUNCTION prevent_ballot_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Encrypted ballots are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER immutable_ballots
    BEFORE UPDATE OR DELETE ON encrypted_ballots
    FOR EACH ROW
    EXECUTE FUNCTION prevent_ballot_modification();

-- Audit log is IMMUTABLE
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER immutable_audit
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

-- Auto-generate ballot hash on insert
CREATE OR REPLACE FUNCTION generate_ballot_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ballot_hash := encode(
        digest(
            NEW.election_id::text || NEW.encrypted_vote::text ||
            NEW.cast_at::text || gen_random_uuid()::text,
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_ballot_hash
    BEFORE INSERT ON encrypted_ballots
    FOR EACH ROW
    EXECUTE FUNCTION generate_ballot_hash();

-- Auto-generate audit event hash on insert
CREATE OR REPLACE FUNCTION generate_audit_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.event_hash := encode(
        digest(
            NEW.event_type ||
            COALESCE(NEW.election_id::text, '') ||
            COALESCE(NEW.actor_id::text, '') ||
            NEW.created_at::text ||
            gen_random_uuid()::text,
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_audit_hash
    BEFORE INSERT ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION generate_audit_hash();

-- ==========================================================================
-- SEED DATA
-- ==========================================================================

INSERT INTO organisations (name, org_type) VALUES ('Demo University', 'university');
