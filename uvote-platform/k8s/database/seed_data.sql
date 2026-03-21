-- ============================================================================
-- U-Vote Baseline Seed Data
-- ============================================================================
--
-- Baseline data for development and testing only.
-- This establishes the minimum records required to run the platform and
-- exercise the test suite immediately after schema creation.
--
-- WARNING: The organiser password below is 'admin123' (bcrypt hash).
--          Change this before any real deployment.
--
-- DO NOT add real voter or election data here.
-- DO NOT add CREATE TABLE or GRANT statements to this file.
--
-- Apply order: schema.sql → create_roles.sql → seed_data.sql
-- ============================================================================

-- Default organisation (required as foreign-key anchor for organiser row)
INSERT INTO organisations (name, org_type)
VALUES ('Demo University', 'university');

-- Default organiser account
-- email: admin@uvote.com | password: admin123 (bcrypt, cost 12)
INSERT INTO organisers (org_id, email, password_hash)
VALUES (
    1,
    'admin@uvote.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWVxKfF8.WO'
);

-- Sample election for development testing
INSERT INTO elections (organiser_id, org_id, title, description, status)
VALUES (1, 1, 'Student Council 2026', 'Annual student council election', 'draft');

-- Sample election options (replaces old candidates table)
INSERT INTO election_options (election_id, option_text, display_order)
VALUES
    (1, 'Alice Johnson', 1),
    (1, 'Bob Smith',     2),
    (1, 'Carol White',   3);
