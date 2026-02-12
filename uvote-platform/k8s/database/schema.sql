-- Drop tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS votes CASCADE;
DROP TABLE IF EXISTS voting_tokens CASCADE;
DROP TABLE IF EXISTS voters CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;
DROP TABLE IF EXISTS elections CASCADE;
DROP TABLE IF EXISTS admins CASCADE;

-- Admins table
CREATE TABLE admins (
    admin_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Elections table
CREATE TABLE elections (
    election_id SERIAL PRIMARY KEY,
    admin_id INT REFERENCES admins(admin_id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    closed_at TIMESTAMP,
    CHECK (status IN ('draft', 'active', 'closed'))
);

-- Candidates table
CREATE TABLE candidates (
    candidate_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    photo_url VARCHAR(500),
    display_order INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Voters table
CREATE TABLE voters (
    voter_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(election_id, email)
);

-- Voting tokens table
CREATE TABLE voting_tokens (
    token_id SERIAL PRIMARY KEY,
    token VARCHAR(64) UNIQUE NOT NULL,
    voter_id INT REFERENCES voters(voter_id) ON DELETE CASCADE,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    UNIQUE(voter_id, election_id)
);

-- Votes table (anonymous - no voter_id)
CREATE TABLE votes (
    vote_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id),
    candidate_id INT REFERENCES candidates(candidate_id),
    vote_hash VARCHAR(64),
    previous_hash VARCHAR(64),
    cast_at TIMESTAMP DEFAULT NOW()
);

-- Audit logs table
CREATE TABLE audit_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    user_id INT,
    election_id INT,
    details TEXT,
    ip_address VARCHAR(45),
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64)
);

-- Indexes
CREATE INDEX idx_votes_election ON votes(election_id);
CREATE INDEX idx_votes_candidate ON votes(candidate_id);
CREATE INDEX idx_tokens_token ON voting_tokens(token);
CREATE INDEX idx_tokens_election ON voting_tokens(election_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_event ON audit_logs(event_type);
CREATE INDEX idx_elections_status ON elections(status);

-- Trigger: Prevent vote modification (immutability)
CREATE OR REPLACE FUNCTION prevent_vote_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Votes cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_vote_update
    BEFORE UPDATE ON votes
    FOR EACH ROW EXECUTE FUNCTION prevent_vote_modification();

CREATE TRIGGER prevent_vote_delete
    BEFORE DELETE ON votes
    FOR EACH ROW EXECUTE FUNCTION prevent_vote_modification();

-- Trigger: Automatic vote hash generation
CREATE OR REPLACE FUNCTION generate_vote_hash()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash VARCHAR(64);
BEGIN
    SELECT vote_hash INTO prev_hash
    FROM votes
    WHERE election_id = NEW.election_id
    ORDER BY cast_at DESC
    LIMIT 1;
    
    NEW.previous_hash := COALESCE(prev_hash, REPEAT('0', 64));
    
    NEW.vote_hash := encode(
        digest(
            NEW.election_id::text || 
            NEW.candidate_id::text || 
            NEW.cast_at::text || 
            NEW.previous_hash,
            'sha256'
        ),
        'hex'
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER generate_vote_hash_trigger
    BEFORE INSERT ON votes
    FOR EACH ROW EXECUTE FUNCTION generate_vote_hash();

-- Create database users with limited permissions
CREATE USER auth_service WITH PASSWORD 'auth_pass_CHANGE_ME';
CREATE USER voting_service WITH PASSWORD 'voting_pass_CHANGE_ME';
CREATE USER election_service WITH PASSWORD 'election_pass_CHANGE_ME';
CREATE USER results_service WITH PASSWORD 'results_pass_CHANGE_ME';
CREATE USER audit_service WITH PASSWORD 'audit_pass_CHANGE_ME';
CREATE USER admin_service WITH PASSWORD 'admin_pass_CHANGE_ME';

-- Grant permissions: Auth Service
GRANT SELECT, INSERT, UPDATE ON admins TO auth_service;
GRANT USAGE, SELECT ON SEQUENCE admins_admin_id_seq TO auth_service;

-- Grant permissions: Voting Service
GRANT INSERT ON votes TO voting_service;
GRANT SELECT ON elections, candidates TO voting_service;
GRANT SELECT, UPDATE ON voting_tokens TO voting_service;
GRANT USAGE, SELECT ON SEQUENCE votes_vote_id_seq TO voting_service;

-- Grant permissions: Election Service
GRANT SELECT, INSERT, UPDATE, DELETE ON elections TO election_service;
GRANT USAGE, SELECT ON SEQUENCE elections_election_id_seq TO election_service;

-- Grant permissions: Results Service (READ ONLY)
GRANT SELECT ON votes, elections, candidates TO results_service;

-- Grant permissions: Audit Service
GRANT INSERT, SELECT ON audit_logs TO audit_service;
GRANT USAGE, SELECT ON SEQUENCE audit_logs_log_id_seq TO audit_service;

-- Grant permissions: Admin Service
GRANT SELECT, INSERT, UPDATE, DELETE ON voters, candidates, voting_tokens TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voters_voter_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE candidates_candidate_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voting_tokens_token_id_seq TO admin_service;

-- Insert sample data for testing
INSERT INTO admins (email, password_hash) VALUES 
('admin@uvote.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWVxKfF8.WO'); 
-- password: admin123

INSERT INTO elections (admin_id, title, description, status) VALUES
(1, 'Student Council 2026', 'Annual student council election', 'draft');

INSERT INTO candidates (election_id, name, description, display_order) VALUES
(1, 'Alice Johnson', 'Experienced leader focused on student welfare', 1),
(1, 'Bob Smith', 'Passionate about campus sustainability', 2),
(1, 'Carol White', 'Advocate for improved facilities', 3);
