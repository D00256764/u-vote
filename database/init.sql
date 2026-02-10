-- Secure Voting System Database Schema

-- Organizers table
CREATE TABLE organizers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Elections table
CREATE TABLE elections (
    id SERIAL PRIMARY KEY,
    organizer_id INTEGER REFERENCES organizers(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opened_at TIMESTAMP,
    closed_at TIMESTAMP
);

-- Election options/candidates
CREATE TABLE election_options (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    option_text VARCHAR(255) NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Voters table (pre-defined list)
CREATE TABLE voters (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(election_id, email)
);

-- Voting tokens (one-time use, cryptographically random)
CREATE TABLE voting_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    voter_id INTEGER REFERENCES voters(id) ON DELETE CASCADE,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    is_used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Votes table (immutable, identity-separated)
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    option_id INTEGER REFERENCES election_options(id) ON DELETE CASCADE,
    vote_hash VARCHAR(255) NOT NULL,
    previous_hash VARCHAR(255),  -- For optional hash chain
    cast_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_elections_organizer ON elections(organizer_id);
CREATE INDEX idx_elections_status ON elections(status);
CREATE INDEX idx_voters_election ON voters(election_id);
CREATE INDEX idx_tokens_election ON voting_tokens(election_id);
CREATE INDEX idx_tokens_token ON voting_tokens(token);
CREATE INDEX idx_votes_election ON votes(election_id);
CREATE INDEX idx_votes_option ON votes(option_id);

-- Function to prevent vote updates
CREATE OR REPLACE FUNCTION prevent_vote_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Votes are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

-- Trigger to make votes immutable
CREATE TRIGGER prevent_vote_update
    BEFORE UPDATE OR DELETE ON votes
    FOR EACH ROW
    EXECUTE FUNCTION prevent_vote_modification();

-- Function to generate vote hash
CREATE OR REPLACE FUNCTION generate_vote_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.vote_hash := encode(
        digest(
            NEW.election_id::text || NEW.option_id::text || NEW.cast_at::text || gen_random_uuid()::text,
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate vote hash
CREATE TRIGGER generate_vote_hash_trigger
    BEFORE INSERT ON votes
    FOR EACH ROW
    EXECUTE FUNCTION generate_vote_hash();
