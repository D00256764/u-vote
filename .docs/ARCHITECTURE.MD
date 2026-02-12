# E-Vote Application - Microservice Architecture

## System Overview

E-Vote is a secure, accessible online voting system designed for small-scale elections (student councils, NGO boards, small organizations). The system uses **token-based voting URLs**, multi-factor admin authentication, and immutable audit logging to ensure election integrity.

**Current Status:** MVP Prototype  
**Backend:** Python + FastAPI  
**Frontend:** Jinja2 Templates (server-side rendering)  
**Database:** PostgreSQL 15  
**Deployment:** Kubernetes with Calico networking

### Key Features

- ✅ **Token-based voting** (one-time secure URLs sent via email)
- ✅ **Admin authentication** (password + JWT)
- ✅ **CSV voter import** (bulk voter addition)
- ✅ **Secure voting** (one vote per voter, anonymous ballots)
- ✅ **Results distribution** (email notification when results ready)
- ✅ **Audit logging** (immutable, hash-chained event logs)
- ✅ **Accessibility** (WCAG AA compliant templates)

### Target Users

- **Admins:** Register account, create elections, manage voters, manage candidates
- **Voters:** Receive email with voting URL, click to vote, receive results URL when ready

---

## Voting Flow Overview
```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: ELECTION SETUP                                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ 1. Admin registers account                              │
│    → Auth Service                                       │
│                                                          │
│ 2. Admin creates election                               │
│    → Election Service                                   │
│                                                          │
│ 3. Admin adds candidates                                │
│    → Admin Service                                      │
│                                                          │
│ 4. Admin adds voters (CSV or manual)                    │
│    → Admin Service                                      │
│                                                          │
│ 5. Admin clicks "Send Voting Links"                     │
│    → Admin Service generates tokens                     │
│    → Email Service sends voting URLs                    │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 2: VOTING                                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ 6. Voter receives email:                                │
│    ┌──────────────────────────────────────────┐        │
│    │ Subject: Vote in Student Council 2026    │        │
│    │                                           │        │
│    │ Click here to vote:                      │        │
│    │ https://evote.com/vote?token=abc123      │        │
│    │                                           │        │
│    │ Link expires in 7 days                   │        │
│    └──────────────────────────────────────────┘        │
│                                                          │
│ 7. Voter clicks URL                                     │
│    → Voting Service validates token                     │
│    → Shows voting dashboard with candidates             │
│                                                          │
│ 8. Voter selects candidate and submits                  │
│    → Vote recorded in database                          │
│    → Token marked as used                               │
│    → Confirmation shown                                 │
│                                                          │
│ 9. If voter clicks link again                           │
│    → Shows "You already voted"                          │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 3: RESULTS                                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ 10. Admin closes election                               │
│     → Election Service sets status = 'closed'           │
│                                                          │
│ 11. Admin clicks "Send Results Links"                   │
│     → Email Service sends results URLs                  │
│                                                          │
│ 12. Voter receives email:                               │
│     ┌──────────────────────────────────────────┐       │
│     │ Subject: Election Results Available      │       │
│     │                                           │       │
│     │ View results:                            │       │
│     │ https://evote.com/results/5              │       │
│     └──────────────────────────────────────────┘       │
│                                                          │
│ 13. Voter clicks URL                                    │
│     → Results Service shows tallies and winner          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture Diagram
```
                         ┌──────────────┐
                         │   Internet   │
                         └──────┬───────┘
                                │ HTTPS
                                │
                    ┌───────────▼────────────┐
                    │   Nginx Ingress        │
                    │  (API Gateway)         │
                    │                        │
                    │ - Rate Limiting        │
                    │ - TLS Termination      │
                    │ - Request Routing      │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼─────┐          ┌─────▼──────┐          ┌────▼─────┐
   │ Frontend │          │    Auth    │          │ Election │
   │ Service  │          │  Service   │          │ Service  │
   │          │          │            │          │          │
   │ Jinja2   │          │ - Admin    │          │ - Create │
   │Templates │          │   register │          │   elections│
   │          │          │ - Admin    │          │ - Manage │
   │Port 3000 │          │   login    │          │   status │
   └────┬─────┘          │ - JWT      │          │          │
        │                │   tokens   │          │Port 8002 │
        │                │            │          └────┬─────┘
        │                │Port 8001   │               │
        │                └─────┬──────┘               │
        │                      │                      │
   ┌────▼─────┐          ┌────▼──────┐          ┌────▼─────┐
   │  Voting  │          │  Results  │          │  Admin   │
   │ Service  │          │  Service  │          │ Service  │
   │          │          │           │          │          │
   │ - Validate│         │ - Tally   │          │ - Add    │
   │   tokens │          │   votes   │          │   voters │
   │ - Cast   │          │ - Calculate│          │ - Add    │
   │   vote   │          │   winner  │          │   candidates│
   │          │          │           │          │ - Generate│
   │Port 8003 │          │Port 8004  │          │   tokens │
   └────┬─────┘          └─────┬─────┘          │ - CSV    │
        │                      │                │   import │
        │                      │                │          │
        │                      │                │Port 8006 │
        │                      │                └────┬─────┘
        │                      │                     │
   ┌────▼──────────────────────▼─────────────────────▼─────┐
   │                    Audit Service                      │
   │                                                        │
   │  - Immutable event logging                            │
   │  - Hash-chained logs (tamper detection)               │
   │  - Security event tracking                            │
   │                                                        │
   │                    Port 8005                           │
   └────┬───────────────────────────────────────────────────┘
        │
        │                              ┌────────────────────┐
        │                              │  Email Service     │
        │                              │                    │
        │                              │ - Send voting URLs │
        │                              │ - Send results URLs│
        │                              │ - Track delivery   │
        │                              │                    │
        │                              │   Port 8007        │
        │                              └────────────────────┘
        │
        └──────────────────────┬───────────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │  PostgreSQL Database │
                    │                      │
                    │  Tables:             │
                    │  - admins            │
                    │  - elections         │
                    │  - candidates        │
                    │  - voters            │
                    │  - voting_tokens     │
                    │  - votes             │
                    │  - audit_logs        │
                    │                      │
                    │  Port 5432           │
                    └──────────────────────┘
```

---

## Service Descriptions

### 1. Nginx Ingress Controller (API Gateway)

**Purpose:** Single entry point for all client requests; security boundary

**Responsibilities:**
- TLS termination (HTTPS → HTTP internally)
- Rate limiting (prevent DoS attacks)
- Route requests to appropriate services

**Port:** 80 (HTTP), 443 (HTTPS)

**Routing Rules:**
```nginx
/ → Frontend Service (3000)
/api/auth → Auth Service (8001)
/api/elections → Election Service (8002)
/api/voting → Voting Service (8003)
/api/results → Results Service (8004)
/api/admin → Admin Service (8006)
```

---

### 2. Frontend Service

**Purpose:** Serve user interface (HTML via Jinja2 templates)

**Responsibilities:**
- Render admin dashboard
- Display voting interface
- Show results pages
- WCAG AA accessibility compliance
- Client-side form validation
- Make API calls to backend services

**Technology:** Python FastAPI + Jinja2  
**Port:** 3000  
**Dependencies:** All backend services (via API Gateway)

**Key Templates:**
- `admin_register.html` - Admin registration form
- `admin_login.html` - Admin login
- `admin_dashboard.html` - Election management
- `vote.html` - Voting interface (accessed via token URL)
- `vote_confirmation.html` - "Vote recorded" page
- `results.html` - Election results display

**Routes:**
```python
GET  /                          # Home page
GET  /admin/register            # Admin registration page
GET  /admin/login               # Admin login page
GET  /admin/dashboard           # Admin dashboard
GET  /vote?token={token}        # Voting page (token validated)
GET  /results/{election_id}     # Results page
```

---

### 3. Auth Service

**Purpose:** Admin authentication and authorization

**Responsibilities:**
- Admin registration (open registration)
- Admin login (email + password)
- JWT token issuance (24-hour expiration)
- Token validation
- Logout (token invalidation)

**Technology:** Python FastAPI  
**Port:** 8001  
**Database Access:** `auth_service` user (SELECT, INSERT, UPDATE on `admins`)

**API Endpoints:**
```python
POST   /api/auth/register          # Register new admin
POST   /api/auth/login             # Admin login, returns JWT
POST   /api/auth/logout            # Invalidate JWT
GET    /api/auth/verify            # Verify JWT is valid
```

**Authentication Flow:**
```
1. Admin submits email + password
2. Auth Service validates credentials
3. Auth Service generates JWT token (24-hour expiration)
4. Admin uses JWT for all subsequent requests
5. API Gateway validates JWT on each request
```

**Security Measures:**
- Bcrypt password hashing (cost factor: 12)
- JWT signing with HS256 algorithm
- Account lockout after 5 failed attempts
- Rate limiting on login endpoint

**JWT Token Structure:**
```json
{
  "sub": "admin_42",
  "email": "admin@example.com",
  "role": "admin",
  "iat": 1707667200,
  "exp": 1707753600
}
```

---

### 4. Admin Service

**Purpose:** Voter and candidate management (admin-only functions)

**Responsibilities:**
- Add voters (manual entry)
- Upload voters (CSV file)
- Remove voters
- Generate voting tokens
- Trigger Email Service to send voting URLs
- Trigger Email Service to send results URLs
- Add/remove/update candidates

**Technology:** Python FastAPI  
**Port:** 8006  
**Database Access:** `admin_service` user (SELECT, INSERT, UPDATE, DELETE on `voters`, `candidates`, `voting_tokens`)

**API Endpoints:**
```python
# Voter Management
POST   /api/admin/voters                      # Add single voter
POST   /api/admin/voters/bulk                 # CSV upload
DELETE /api/admin/voters/{id}                 # Remove voter
GET    /api/admin/voters?election_id={id}     # List voters for election

# Token Management
POST   /api/admin/elections/{id}/send-voting-links    # Generate tokens, send emails
POST   /api/admin/elections/{id}/send-results-links   # Send results emails
POST   /api/admin/voters/{id}/resend-token            # Resend individual token

# Candidate Management
POST   /api/admin/candidates                  # Add candidate
DELETE /api/admin/candidates/{id}             # Remove candidate
PUT    /api/admin/candidates/{id}             # Update candidate
```

**CSV Upload Format:**
```csv
email,first_name,last_name
alice@example.com,Alice,Johnson
bob@example.com,Bob,Smith
carol@example.com,Carol,White
```

**Token Generation Process:**
```python
# When admin clicks "Send Voting Links"
1. For each voter in election:
   a. Generate cryptographic token (secrets.token_urlsafe(32))
   b. Store token in voting_tokens table
   c. Set expiration (7 days from now)
   d. Call Email Service with token URL

# Token format: 43-character random string
# Example: "x8K3mP9qL2wN7vR4tY6uI1oE5sA0dF8gH3jK9mN2pQ"
```

**Dependencies:**
- Email Service (to send voting/results URLs)
- Audit Service (to log admin actions)

---

### 5. Email Service

**Purpose:** Send transactional emails

**Responsibilities:**
- Send voting invitation emails with token URLs
- Send results notification emails
- Track email delivery status
- Handle email failures with retry logic

**Technology:** Python FastAPI  
**Port:** 8007  
**External Dependencies:** SMTP server (Gmail, SendGrid, AWS SES)

**API Endpoints:**
```python
POST   /api/email/send-voting-invitation      # Send voting URL
POST   /api/email/send-results-notification   # Send results URL
GET    /api/email/status/{id}                 # Check delivery status
```

**Email Templates:**

#### Voting Invitation Email
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background-color: #f8f9fa; padding: 20px;">
    <h1 style="color: #333;">You're Invited to Vote</h1>
    <p>Hi {{ voter_name }},</p>
    <p>You've been invited to vote in <strong>{{ election_title }}</strong>.</p>
    <p>Click the button below to cast your vote:</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{{ voting_url }}" 
         style="background-color: #007bff; color: white; padding: 15px 30px; 
                text-decoration: none; border-radius: 5px; display: inline-block;">
        Vote Now
      </a>
    </div>
    <p style="color: #666; font-size: 14px;">
      This link expires on {{ expires_at }}<br>
      You can only vote once using this link.
    </p>
    <p style="color: #999; font-size: 12px; margin-top: 30px;">
      If you did not expect this email, please ignore it.
    </p>
  </div>
</body>
</html>
```

#### Results Notification Email
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background-color: #f8f9fa; padding: 20px;">
    <h1 style="color: #333;">Election Results Available</h1>
    <p>Hi {{ voter_name }},</p>
    <p>The results for <strong>{{ election_title }}</strong> are now available.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{{ results_url }}" 
         style="background-color: #28a745; color: white; padding: 15px 30px; 
                text-decoration: none; border-radius: 5px; display: inline-block;">
        View Results
      </a>
    </div>
    <p style="color: #666; font-size: 14px;">
      Thank you for participating!
    </p>
  </div>
</body>
</html>
```

**Configuration:**
```python
# Environment variables
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "noreply@evote.com"
SMTP_PASSWORD = "<from-secret>"
SMTP_USE_TLS = True
```

---

### 6. Election Service

**Purpose:** Manage elections (create, configure, control status)

**Responsibilities:**
- Create new elections
- Update election details (title, description, dates)
- Set election status (draft, active, closed)
- Control results visibility
- Delete elections (only if no votes cast)

**Technology:** Python FastAPI  
**Port:** 8002  
**Database Access:** `election_service` user (ALL on `elections`)

**API Endpoints:**
```python
POST   /api/elections                   # Create election
GET    /api/elections                   # List all elections (for admin)
GET    /api/elections/{id}              # Get election details
PUT    /api/elections/{id}              # Update election
DELETE /api/elections/{id}              # Delete election (if no votes)
POST   /api/elections/{id}/activate     # Set status to "active"
POST   /api/elections/{id}/close        # Set status to "closed"
```

**Election Lifecycle:**
```
1. draft (created, not yet started)
   ↓ (admin activates)
2. active (voting period - voters can vote)
   ↓ (admin closes)
3. closed (voting ended - results available)
```

**Business Rules:**
- Cannot activate election without at least 2 candidates
- Cannot close election that was never activated
- Cannot delete election with existing votes (must archive)
- Status changes logged to Audit Service

---

### 7. Voting Service

**Purpose:** Handle token-based vote casting

**Responsibilities:**
- Validate voting tokens from URL
- Check token not expired
- Check token not already used
- Display voting ballot
- Accept vote submission
- Mark token as used
- Record votes anonymously

**Technology:** Python FastAPI  
**Port:** 8003  
**Database Access:** `voting_service` user (INSERT on `votes`, SELECT on `elections`/`candidates`, UPDATE on `voting_tokens`)

**API Endpoints:**
```python
GET    /api/voting/validate-token?token={token}   # Validate token, return election info
GET    /api/voting/ballot?token={token}           # Get candidates for election
POST   /api/voting/cast-vote                      # Submit vote
```

**Voting Flow:**

**Step 1: Validate Token**
```python
GET /api/voting/validate-token?token=abc123

Response (if valid):
{
  "valid": true,
  "election_id": 5,
  "election_title": "Student Council 2026",
  "voter_email": "alice@example.com",
  "expires_at": "2026-02-18T23:59:59Z",
  "has_voted": false
}

Response (if already used):
{
  "valid": false,
  "error": "This voting link has already been used",
  "has_voted": true
}

Response (if expired):
{
  "valid": false,
  "error": "This voting link has expired"
}
```

**Step 2: Get Ballot**
```python
GET /api/voting/ballot?token=abc123

Response:
{
  "election_id": 5,
  "election_title": "Student Council 2026",
  "candidates": [
    {
      "candidate_id": 1,
      "name": "Alice Johnson",
      "description": "Experienced leader...",
      "photo_url": "/uploads/alice.jpg"
    },
    {
      "candidate_id": 2,
      "name": "Bob Smith",
      "description": "Passionate advocate...",
      "photo_url": "/uploads/bob.jpg"
    }
  ]
}
```

**Step 3: Cast Vote**
```python
POST /api/voting/cast-vote
Body: {
  "token": "abc123",
  "candidate_id": 2
}

Process:
1. Re-validate token (ensure not used in the meantime)
2. Check election is active
3. Check candidate exists in this election
4. Insert vote into votes table (with hash)
5. Update voting_tokens SET is_used=true, used_at=NOW()
6. Log to Audit Service (does NOT log which candidate)
7. Return confirmation

Response:
{
  "success": true,
  "message": "Your vote has been recorded",
  "vote_hash": "a3f8c9d2e1b4..."  # SHA-256 hash for verification
}
```

**Vote Anonymity:**
- Votes table does NOT link back to voter
- Only links: election → candidate
- Audit logs record "voter X used token in election Y" (NOT which candidate)

**Database Constraint:**
```sql
-- Voting tokens table ensures one vote per voter per election
UNIQUE(voter_id, election_id)
```

---

### 8. Results Service

**Purpose:** Calculate and display election results

**Responsibilities:**
- Tally votes per candidate
- Calculate percentages
- Determine winner(s)
- Generate results reports
- Display results (when election closed)

**Technology:** Python FastAPI  
**Port:** 8004  
**Database Access:** `results_service` user (SELECT only - read-only)

**API Endpoints:**
```python
GET    /api/results/{election_id}       # Get election results
```

**Results Calculation:**
```sql
SELECT 
    c.candidate_id,
    c.name,
    c.photo_url,
    COUNT(v.vote_id) as vote_count,
    ROUND(COUNT(v.vote_id)::numeric / NULLIF(total.total_votes, 0) * 100, 2) as percentage
FROM candidates c
LEFT JOIN votes v ON c.candidate_id = v.candidate_id
CROSS JOIN (
    SELECT COUNT(*) as total_votes 
    FROM votes 
    WHERE election_id = $1
) total
WHERE c.election_id = $1
GROUP BY c.candidate_id, c.name, c.photo_url, total.total_votes
ORDER BY vote_count DESC;
```

**Response Format:**
```json
{
  "election_id": 5,
  "election_title": "Student Council 2026",
  "status": "closed",
  "total_votes": 150,
  "results": [
    {
      "candidate_id": 2,
      "name": "Bob Smith",
      "photo_url": "/uploads/bob.jpg",
      "vote_count": 75,
      "percentage": 50.0,
      "is_winner": true
    },
    {
      "candidate_id": 1,
      "name": "Alice Johnson",
      "photo_url": "/uploads/alice.jpg",
      "vote_count": 50,
      "percentage": 33.33,
      "is_winner": false
    },
    {
      "candidate_id": 3,
      "name": "Carol White",
      "photo_url": "/uploads/carol.jpg",
      "vote_count": 25,
      "percentage": 16.67,
      "is_winner": false
    }
  ]
}
```

**Business Rules:**
- Results only visible if election status = 'closed'
- Admins can view results anytime
- Results logged to Audit Service when accessed

---

### 9. Audit Service

**Purpose:** Immutable event logging with tamper detection

**Responsibilities:**
- Record all security-relevant events
- Implement hash-chaining (each log entry hashes previous entry)
- Provide audit trail queries
- Detect log tampering
- Store events permanently (append-only)

**Technology:** Python FastAPI  
**Port:** 8005  
**Database Access:** `audit_service` user (INSERT, SELECT on `audit_logs`)

**API Endpoints:**
```python
POST   /api/audit/log                   # Write audit event
GET    /api/audit/logs                  # Query logs (admin only)
GET    /api/audit/verify                # Verify log chain integrity
```

**Events Logged:**
- Admin login attempts (success/failure)
- Admin registration
- Election created/updated/closed
- Candidate added/removed
- Voter added/removed
- Voting token generated
- Vote cast (user + election, NOT candidate choice)
- Results viewed
- Email sent (voting/results)

**Hash-Chaining Algorithm:**
```python
import hashlib
from datetime import datetime

def create_audit_log(event_type: str, user_id: int, details: dict):
    # Get previous log entry
    prev_log = db.query(
        "SELECT current_hash FROM audit_logs ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    
    # Create current entry
    log_entry = {
        "event_type": event_type,
        "user_id": user_id,
        "details": json.dumps(details),
        "timestamp": datetime.utcnow(),
        "previous_hash": prev_log.current_hash if prev_log else "0" * 64
    }
    
    # Hash current entry (includes previous hash)
    hash_input = (
        f"{log_entry['timestamp'].isoformat()}"
        f"{log_entry['event_type']}"
        f"{log_entry['user_id']}"
        f"{log_entry['details']}"
        f"{log_entry['previous_hash']}"
    )
    log_entry["current_hash"] = hashlib.sha256(hash_input.encode()).hexdigest()
    
    # Insert into database
    db.execute(
        """
        INSERT INTO audit_logs 
        (timestamp, event_type, user_id, details, previous_hash, current_hash)
        VALUES (%(timestamp)s, %(event_type)s, %(user_id)s, %(details)s, 
                %(previous_hash)s, %(current_hash)s)
        """,
        log_entry
    )
    
    return log_entry["current_hash"]
```

**Tamper Detection:**
```python
def verify_log_chain() -> tuple[bool, str]:
    """Verify the entire audit log chain is intact"""
    logs = db.query(
        "SELECT * FROM audit_logs ORDER BY timestamp ASC"
    ).fetchall()
    
    for i in range(1, len(logs)):
        # Recalculate hash
        hash_input = (
            f"{logs[i]['timestamp'].isoformat()}"
            f"{logs[i]['event_type']}"
            f"{logs[i]['user_id']}"
            f"{logs[i]['details']}"
            f"{logs[i]['previous_hash']}"
        )
        expected_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Compare with stored hash
        if expected_hash != logs[i]['current_hash']:
            return False, f"Tampering detected at log ID {logs[i]['log_id']}"
        
        # Check chain linkage
        if logs[i]['previous_hash'] != logs[i-1]['current_hash']:
            return False, f"Chain broken between log {logs[i-1]['log_id']} and {logs[i]['log_id']}"
    
    return True, "Log chain intact - no tampering detected"
```

---

### 10. Database (PostgreSQL 15)

**Purpose:** Persistent data storage

**Technology:** PostgreSQL 15  
**Port:** 5432 (internal only, not exposed externally)  
**Storage:** 5Gi PersistentVolume (Kubernetes)

**Database Schema:**
```sql
-- Admins (people who create/manage elections)
CREATE TABLE admins (
    admin_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Elections
CREATE TABLE elections (
    election_id SERIAL PRIMARY KEY,
    admin_id INT REFERENCES admins(admin_id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'active', 'closed'
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    closed_at TIMESTAMP
);

-- Candidates in each election
CREATE TABLE candidates (
    candidate_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    photo_url VARCHAR(500),
    display_order INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Voters (people invited to vote)
CREATE TABLE voters (
    voter_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(election_id, email)  -- One voter record per election
);

-- Voting tokens (one-time URLs)
CREATE TABLE voting_tokens (
    token_id SERIAL PRIMARY KEY,
    token VARCHAR(64) UNIQUE NOT NULL,
    voter_id INT REFERENCES voters(voter_id) ON DELETE CASCADE,
    election_id INT REFERENCES elections(election_id) ON DELETE CASCADE,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    UNIQUE(voter_id, election_id)  -- One token per voter per election
);

-- Votes (anonymous - no link to voter)
CREATE TABLE votes (
    vote_id SERIAL PRIMARY KEY,
    election_id INT REFERENCES elections(election_id),
    candidate_id INT REFERENCES candidates(candidate_id),
    vote_hash VARCHAR(64),  -- SHA-256 hash
    previous_hash VARCHAR(64),  -- For hash chain
    cast_at TIMESTAMP DEFAULT NOW()
);

-- Audit logs (immutable)
CREATE TABLE audit_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    user_id INT,  -- admin_id or voter_id depending on event
    election_id INT,
    details TEXT,  -- JSON
    ip_address VARCHAR(45),
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64)
);

-- Indexes for performance
CREATE INDEX idx_votes_election ON votes(election_id);
CREATE INDEX idx_votes_candidate ON votes(candidate_id);
CREATE INDEX idx_tokens_token ON voting_tokens(token);
CREATE INDEX idx_tokens_election ON voting_tokens(election_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_event ON audit_logs(event_type);
CREATE INDEX idx_elections_status ON elections(status);

-- Triggers to prevent vote modification (immutability)
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

-- Automatic hash generation for votes
CREATE OR REPLACE FUNCTION generate_vote_hash()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash VARCHAR(64);
BEGIN
    -- Get previous vote's hash
    SELECT vote_hash INTO prev_hash
    FROM votes
    WHERE election_id = NEW.election_id
    ORDER BY cast_at DESC
    LIMIT 1;
    
    -- Set previous_hash
    NEW.previous_hash := COALESCE(prev_hash, REPEAT('0', 64));
    
    -- Generate vote hash
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
```

**Database User Permissions:**
```sql
-- Auth Service user
CREATE USER auth_service WITH PASSWORD 'auth_password_change_me';
GRANT SELECT, INSERT, UPDATE ON admins TO auth_service;
GRANT USAGE, SELECT ON SEQUENCE admins_admin_id_seq TO auth_service;

-- Voting Service user
CREATE USER voting_service WITH PASSWORD 'voting_password_change_me';
GRANT INSERT ON votes TO voting_service;
GRANT SELECT ON elections, candidates TO voting_service;
GRANT SELECT, UPDATE ON voting_tokens TO voting_service;
GRANT USAGE, SELECT ON SEQUENCE votes_vote_id_seq TO voting_service;

-- Election Service user
CREATE USER election_service WITH PASSWORD 'election_password_change_me';
GRANT SELECT, INSERT, UPDATE, DELETE ON elections TO election_service;
GRANT USAGE, SELECT ON SEQUENCE elections_election_id_seq TO election_service;

-- Results Service user (READ ONLY)
CREATE USER results_service WITH PASSWORD 'results_password_change_me';
GRANT SELECT ON votes, elections, candidates TO results_service;

-- Audit Service user
CREATE USER audit_service WITH PASSWORD 'audit_password_change_me';
GRANT INSERT, SELECT ON audit_logs TO audit_service;
GRANT USAGE, SELECT ON SEQUENCE audit_logs_log_id_seq TO audit_service;

-- Admin Service user
CREATE USER admin_service WITH PASSWORD 'admin_password_change_me';
GRANT SELECT, INSERT, UPDATE, DELETE ON voters, candidates, voting_tokens TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voters_voter_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE candidates_candidate_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voting_tokens_token_id_seq TO admin_service;
```

---

## Security Measures

### 1. Admin Authentication
- ✅ Password hashing with bcrypt (cost factor 12)
- ✅ JWT tokens (HS256, 24-hour expiration)
- ✅ Rate limiting on login endpoints
- ✅ Account lockout after 5 failed attempts

### 2. Voter Authentication
- ✅ Cryptographic tokens (secrets.token_urlsafe(32))
- ✅ One-time use (token marked as used after vote)
- ✅ Token expiration (7 days)
- ✅ No password needed (reduces friction)

### 3. Vote Anonymity
- ✅ Votes table has NO voter_id column
- ✅ Only stores: election + candidate + timestamp
- ✅ Audit logs do NOT record candidate choice
- ✅ Impossible to trace vote to voter after casting

### 4. Data Integrity
- ✅ Vote immutability (database triggers prevent UPDATE/DELETE)
- ✅ Hash chaining (tamper detection)
- ✅ Database constraints (UNIQUE, FOREIGN KEY)
- ✅ Audit log verification

### 5. Network Security
- ✅ Calico network policies (default deny all)
- ✅ Services isolated (cannot directly access each other)
- ✅ Database not externally accessible
- ✅ All traffic through API Gateway

### 6. Input Validation
- ✅ Email format validation
- ✅ SQL injection prevention (parameterized queries)
- ✅ Request size limits
- ✅ Token format validation

---

## Data Flow Examples

### Example 1: Complete Voting Flow
```
1. Admin creates election
   Frontend → Election Service
   POST /api/elections
   {title: "Student Council 2026", description: "..."}
   → Creates election record (status='draft')

2. Admin adds candidates
   Frontend → Admin Service
   POST /api/admin/candidates
   {election_id: 5, name: "Alice Johnson", description: "..."}
   → Creates candidate record

3. Admin uploads voters CSV
   Frontend → Admin Service
   POST /api/admin/voters/bulk
   File: voters.csv
   → Creates voter records for each email

4. Admin activates election
   Frontend → Election Service
   POST /api/elections/5/activate
   → Updates election status='active'

5. Admin sends voting links
   Frontend → Admin Service
   POST /api/admin/elections/5/send-voting-links
   → For each voter:
      a. Generate token: "x8K3mP9qL2wN7vR4tY6uI1oE5sA0dF8gH3jK9mN2pQ"
      b. Store in voting_tokens table
      c. Call Email Service:
         POST /api/email/send-voting-invitation
         {
           voter_email: "alice@example.com",
           voting_url: "https://evote.com/vote?token=x8K3mP9q...",
           election_title: "Student Council 2026"
         }

6. Voter receives email and clicks link
   Browser → https://evote.com/vote?token=x8K3mP9q...
   Frontend → Voting Service
   GET /api/voting/validate-token?token=x8K3mP9q...
   → Returns election info if valid

7. Voter sees candidates
   Frontend → Voting Service
   GET /api/voting/ballot?token=x8K3mP9q...
   → Returns list of candidates

8. Voter clicks "Vote for Bob Smith"
   Frontend → Voting Service
   POST /api/voting/cast-vote
   {token: "x8K3mP9q...", candidate_id: 2}
   → Voting Service:
      a. Validates token again
      b. Checks election active
      c. Inserts vote (with hash)
      d. Marks token as used
      e. Logs to Audit Service
   → Returns confirmation

9. Admin closes election
   Frontend → Election Service
   POST /api/elections/5/close
   → Updates election status='closed'

10. Admin sends results links
    Frontend → Admin Service
    POST /api/admin/elections/5/send-results-links
    → Email Service sends results URLs to all voters

11. Voter views results
    Browser → https://evote.com/results/5
    Frontend → Results Service
    GET /api/results/5
    → Returns vote tallies and winner
```

---

## Development Guidelines

### Adding a New Service

1. Create service directory: `services/<service-name>/`
2. Create FastAPI application with proper structure:
```
   services/service-name/
   ├── main.py           # FastAPI app
   ├── models.py         # Pydantic models
   ├── routes.py         # API routes
   ├── database.py       # DB connection
   ├── dependencies.py   # Auth, etc.
   ├── requirements.txt
   └── Dockerfile
```
3. Add database user and permissions
4. Create Kubernetes manifests
5. Add network policy rules
6. Update API Gateway routing
7. Update this README

### Coding Standards

**Python (FastAPI):**
- PEP 8 style guide
- Type hints required
- Pydantic models for request/response validation
- Docstrings for all functions
- FastAPI dependency injection

**Database:**
- Always use parameterized queries
- Never concatenate SQL strings
- Use transactions for multi-step operations
- Handle connection errors gracefully

**Security:**
- Never log sensitive data (passwords, tokens)
- Always validate input
- Use environment variables for config
- Secrets via Kubernetes Secrets only

### Testing Requirements

**Unit Tests:**
- All business logic functions
- 80%+ code coverage
- Use pytest

**Integration Tests:**
- API endpoint tests
- Database interaction tests
- Use TestClient from FastAPI

**Security Tests:**
- SQL injection attempts
- Token validation edge cases
- Authorization checks

---

## Deployment

### Docker Images

Each service has a Dockerfile:
```dockerfile
# Example: voting-service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

### Kubernetes Manifests

Location: `k8s/services/<service-name>.yaml`

Example structure:
- Deployment (replicas, image, env vars, resource limits)
- Service (ClusterIP, port mapping)
- HorizontalPodAutoscaler (scaling rules)

### Environment Variables

Required for each service:
```bash
# Database connection
DB_HOST=postgresql
DB_PORT=5432
DB_NAME=evote
DB_USER=<service-specific-user>
DB_PASSWORD=<from-secret>

# JWT (Auth Service only)
JWT_SECRET=<from-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRATION=86400

# SMTP (Email Service only)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<from-secret>
SMTP_PASSWORD=<from-secret>
```

---

## Future Enhancements

### Potential Password Migration (Approach B)

If user feedback indicates voters want to verify their vote later, we can add password authentication:

**Phase 1: Add Password Option (Hybrid)**
```
1. Admin adds voter
2. Voter receives invite email
3. Voter clicks invite → OPTION: Set password or vote immediately
4. If password set: Future logins require password + OTP
5. If vote immediately: Same as current (token-based)
```

**Phase 2: Full Password System**
```
1. Admin adds voter → sends invite
2. Voter MUST set password
3. Voter logs in (password + OTP)
4. Voter votes (session-based, no token)
5. Voter can log in again to verify vote
```

**Database Migration:**
```sql
ALTER TABLE voters ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE voters ADD COLUMN account_status VARCHAR(20) DEFAULT 'invited';

-- NULL password_hash = token-only (current system)
-- NOT NULL password_hash = password-based (new system)
```

### Other Features
- [ ] Ranked-choice voting (STV algorithm)
- [ ] Multiple admins per election
- [ ] Candidate photos/bios upload
- [ ] Vote receipt (anonymized confirmation code)
- [ ] Results analytics dashboard
- [ ] Export results to CSV/PDF

### Technical
- [ ] WebSocket for real-time updates
- [ ] Redis caching layer
- [ ] CDN for static assets
- [ ] Database read replicas
- [ ] Automated backups

---

## Project Structure
```
evote-application/
├── services/
│   ├── auth/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── admin/
│   ├── election/
│   ├── voting/
│   ├── results/
│   ├── audit/
│   ├── email/
│   └── frontend/
│       ├── main.py
│       ├── templates/
│       │   ├── admin_register.html
│       │   ├── admin_login.html
│       │   ├── admin_dashboard.html
│       │   ├── vote.html
│       │   ├── vote_confirmation.html
│       │   └── results.html
│       ├── static/
│       │   ├── css/
│       │   │   └── styles.css
│       │   └── js/
│       │       └── app.js
│       └── Dockerfile
├── shared/
│   ├── database.py
│   ├── models.py
│   └── utils.py
└── README.md (this file)
```

---

## Related Documentation

- [Platform Infrastructure README](../platform/README.md)
- [Database Schema Details](./docs/DATABASE.md)
- [API Reference](http://localhost/api/docs)
- [Security Architecture](./docs/SECURITY.md)
- [Deployment Guide](./docs/DEPLOYMENT.md)

---

## Contributing

1. Create feature branch
2. Write tests
3. Submit pull request
4. Pass code review