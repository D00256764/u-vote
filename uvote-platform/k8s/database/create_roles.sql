-- ============================================================================
-- U-Vote Database Roles and Permissions
-- ============================================================================
--
-- Creates one PostgreSQL role per micro-service with the minimum grants
-- required for that service to function (least-privilege model).
--
-- Passwords are placeholder values here — they are overridden at deploy time
-- by deploy_platform.py, which generates random secrets and patches them
-- into the db-credentials Kubernetes Secret before pod startup.
--
-- Apply order: schema.sql → create_roles.sql → seed_data.sql
--
-- DO NOT add CREATE TABLE or INSERT statements to this file.
-- ============================================================================

-- ============================================================================
-- CREATE ROLES
-- ============================================================================

CREATE USER auth_service     WITH PASSWORD 'auth_pass_CHANGE_ME';
CREATE USER voting_service   WITH PASSWORD 'voting_pass_CHANGE_ME';
CREATE USER election_service WITH PASSWORD 'election_pass_CHANGE_ME';
CREATE USER results_service  WITH PASSWORD 'results_pass_CHANGE_ME';
CREATE USER audit_service    WITH PASSWORD 'audit_pass_CHANGE_ME';
CREATE USER admin_service    WITH PASSWORD 'admin_pass_CHANGE_ME';

-- ============================================================================
-- Grant permissions: Auth Service
--
-- Handles organiser registration and login (JWT issuance).
-- Validates voter identity (email + DOB) and marks has_voted after MFA.
-- Issues blind ballot tokens to authenticated voters.
-- ============================================================================

GRANT SELECT, INSERT, UPDATE ON organisers TO auth_service;
GRANT SELECT, UPDATE         ON voters     TO auth_service;  -- verify identity, mark has_voted
GRANT SELECT, INSERT         ON voter_mfa  TO auth_service;  -- issue and validate MFA codes
GRANT INSERT                 ON blind_tokens TO auth_service; -- issue blind ballot tokens after MFA

GRANT USAGE, SELECT ON SEQUENCE organisers_id_seq   TO auth_service;
GRANT USAGE, SELECT ON SEQUENCE voter_mfa_id_seq    TO auth_service;
GRANT USAGE, SELECT ON SEQUENCE blind_tokens_id_seq TO auth_service;

-- ============================================================================
-- Grant permissions: Voting Service
--
-- Validates blind ballot tokens, records encrypted ballots on the ledger,
-- issues vote receipts. Read-only access to election metadata.
-- ============================================================================

GRANT INSERT              ON encrypted_ballots TO voting_service;
GRANT INSERT              ON vote_receipts     TO voting_service;
GRANT SELECT ON elections, election_options    TO voting_service;
GRANT SELECT, UPDATE      ON voting_tokens     TO voting_service;
GRANT SELECT, UPDATE      ON blind_tokens      TO voting_service; -- validate and mark as used

GRANT USAGE, SELECT ON SEQUENCE encrypted_ballots_id_seq TO voting_service;
GRANT USAGE, SELECT ON SEQUENCE vote_receipts_id_seq     TO voting_service;

-- ============================================================================
-- Grant permissions: Election Service
--
-- Full lifecycle management of elections and their options (draft → open →
-- closed). Does not access voter identity or ballot data.
-- ============================================================================

GRANT SELECT, INSERT, UPDATE, DELETE ON elections        TO election_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON election_options TO election_service;

GRANT USAGE, SELECT ON SEQUENCE elections_id_seq        TO election_service;
GRANT USAGE, SELECT ON SEQUENCE election_options_id_seq TO election_service;

-- ============================================================================
-- Grant permissions: Results Service (READ ONLY + tally writes)
--
-- Reads encrypted ballots and election metadata to compute results.
-- Writes tallied vote counts to tallied_votes after decryption/counting.
-- ============================================================================

GRANT SELECT ON encrypted_ballots, elections, election_options TO results_service;
GRANT SELECT, INSERT, UPDATE ON tallied_votes                  TO results_service;

GRANT USAGE, SELECT ON SEQUENCE tallied_votes_id_seq TO results_service;

-- ============================================================================
-- Grant permissions: Audit Service
--
-- Append-only writes to the audit_log (INSERT).
-- Reads permitted for audit trail queries and hash verification.
-- ============================================================================

GRANT INSERT, SELECT ON audit_log TO audit_service;

GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO audit_service;

-- ============================================================================
-- Grant permissions: Admin Service
--
-- Manages voter lists, election options, and voting token generation.
-- Can read/create organisations and organisers for tenancy management.
-- ============================================================================

GRANT SELECT, INSERT, UPDATE, DELETE ON voters, election_options, voting_tokens TO admin_service;
GRANT SELECT, INSERT, UPDATE         ON organisations, organisers               TO admin_service;

GRANT USAGE, SELECT ON SEQUENCE voters_id_seq           TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE election_options_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voting_tokens_id_seq    TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE organisations_id_seq    TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE organisers_id_seq       TO admin_service;
