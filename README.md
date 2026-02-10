# Secure Voting System

A token-based online voting system with cryptographic security, identity-ballot separation, and immutable vote storage.

## Features

### 1️⃣ Organizer-Controlled Elections
- Organizer account (email + password)
- Create elections with custom options/candidates
- Open/close election control

### 2️⃣ Pre-defined Voter List
- Upload voter emails via CSV
- System generates one-time voting credentials
- No self-registration

### 3️⃣ Single-Use Voting Tokens
- Cryptographically random tokens (URL-safe, 32 bytes)
- Token tied to one election
- Token expiration (default: 7 days)
- Token invalidated after vote

### 4️⃣ Secure Vote Casting
- Token-based ballot access
- Server-side validation
- Vote submission only once
- No vote editing

### 5️⃣ Identity–Ballot Separation
- Token used only to authorize vote
- Vote stored without identity data
- Token and vote stored separately

### 6️⃣ Immutable Vote Storage
- Append-only vote table
- Hash each vote record (SHA-256)
- Optional hash chain for audit trail
- Database triggers prevent vote modification

### 7️⃣ Results After Close
- Tally only after election ends
- Read-only results
- Detailed statistics and audit trail

## Technology Stack

- **Backend**: Python + Flask
- **Database**: PostgreSQL 15
- **Frontend**: Flask + Jinja2 Templates
- **Architecture**: Microservices
- **Containerization**: Docker + Docker Compose
- **Security**: bcrypt (passwords), JWT (auth), secrets module (tokens), SHA-256 (vote hashing)

## Microservices Architecture

```
┌─────────────────┐
│  PostgreSQL DB  │
└────────┬────────┘
         │
    ┌────┴─────────────────────────────────┐
    │                                      │
┌───▼─────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Auth   │  │  Voter   │  │  Voting  │  │ Results  │
│ Service │  │ Service  │  │ Service  │  │ Service  │
│ :5001   │  │ :5002    │  │ :5003    │  │ :5004    │
└───┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
    │            │            │            │
    └────────────┴────────────┴────────────┘
                     │
              ┌──────▼──────┐
              │  Frontend   │
              │  Service    │
              │   :5000     │
              └─────────────┘
```

### Services:
1. **Auth Service** (5001): Organizer authentication and JWT management
2. **Voter Service** (5002): Voter list management and token generation
3. **Voting Service** (5003): Ballot access and vote casting
4. **Results Service** (5004): Result tallying and audit trails
5. **Frontend Service** (5000): Web UI with Jinja templates

## Installation & Setup

### Prerequisites
- Docker Desktop
- Docker Compose
- Git

### Quick Start

1. **Clone the repository**:
```bash
git clone <repository-url>
cd secure-voting-system
```

2. **Start all services**:
```bash
docker-compose up --build
```

3. **Access the application**:
- Frontend: http://localhost:5000
- Auth API: http://localhost:5001
- Voter API: http://localhost:5002
- Voting API: http://localhost:5003
- Results API: http://localhost:5004
- PostgreSQL: localhost:5432

### Database Initialization

The database is automatically initialized with the schema on first startup using the `database/init.sql` file.

## Usage Guide

### For Organizers

1. **Register an Account**
   - Navigate to http://localhost:5000
   - Click "Register as Organizer"
   - Provide email and password

2. **Create an Election**
   - Login to your dashboard
   - Click "Create Election"
   - Enter title, description, and options/candidates
   - Click "Create Election"

3. **Add Voters**
   - Go to election details
   - Click "Manage Voters"
   - Upload a CSV file with voter emails (see `sample-voters.csv`)
   - Or add voters manually

4. **Generate Tokens**
   - In the "Manage Voters" page
   - Click "Generate Tokens"
   - Tokens are created for all voters
   - **Important**: Send tokens to voters via secure channels (email, etc.)

5. **Open the Election**
   - In election details, click "Open Election"
   - Election status changes to "OPEN"
   - Voters can now cast votes

6. **Close the Election**
   - When voting period ends, click "Close Election"
   - Election status changes to "CLOSED"
   - Results become available

7. **View Results**
   - Click "View Results" on closed elections
   - See vote distribution, statistics, and winner

### For Voters

1. **Receive Token**
   - You'll receive a unique voting token from the organizer
   - Token URL format: `http://localhost:5000/vote/<your-token>`

2. **Cast Vote**
   - Click the token URL
   - Review the ballot
   - Select your choice
   - Confirm and submit
   - **Note**: Votes cannot be changed after submission

3. **Receive Confirmation**
   - You'll receive a vote hash as confirmation
   - Save this hash for your records
   - It proves your vote was recorded

## Security Features

### Password Security
- Passwords hashed with bcrypt (salt + hash)
- Never stored in plaintext
- Secure password verification

### Token Security
- Cryptographically random tokens (secrets.token_urlsafe)
- 256-bit entropy
- Single-use (marked as used after vote)
- Time-based expiration
- Cannot be guessed or predicted

### Vote Security
- **Identity Separation**: Votes stored without voter identification
- **Immutability**: Database triggers prevent vote modification/deletion
- **Hashing**: Each vote has SHA-256 hash for integrity
- **Hash Chain**: Optional linkage between votes for audit trail
- **Append-Only**: Votes can only be added, never updated or deleted

### Authentication
- JWT tokens for organizer sessions
- 24-hour token expiration
- Secure session management

## API Documentation

### Auth Service (Port 5001)

**POST /register** - Register organizer
```json
{
  "email": "organizer@example.com",
  "password": "securepassword"
}
```

**POST /login** - Login and get JWT
```json
{
  "email": "organizer@example.com",
  "password": "securepassword"
}
```

**POST /verify** - Verify JWT token
```json
{
  "token": "jwt-token-here"
}
```

### Voter Service (Port 5002)

**POST /elections/{election_id}/voters/upload** - Upload voters CSV

**POST /elections/{election_id}/voters** - Add single voter
```json
{
  "email": "voter@example.com"
}
```

**GET /elections/{election_id}/voters** - List voters

**POST /elections/{election_id}/tokens/generate** - Generate tokens

**GET /tokens/{token}/validate** - Validate token

### Voting Service (Port 5003)

**GET /elections/{election_id}/ballot** - Get ballot
Headers: `X-Voting-Token: <token>`

**POST /elections/{election_id}/vote** - Cast vote
Headers: `X-Voting-Token: <token>`
```json
{
  "option_id": 1
}
```

**GET /votes/{vote_id}/verify** - Verify vote exists

### Results Service (Port 5004)

**GET /elections/{election_id}/results** - Get results (closed elections only)

**GET /elections/{election_id}/audit** - Get audit trail

**GET /elections/{election_id}/statistics** - Get detailed statistics

## File Structure

```
secure-voting-system/
├── auth-service/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── voter-service/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── voting-service/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── results-service/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-service/
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── create_election.html
│   │   ├── election_detail.html
│   │   ├── manage_voters.html
│   │   ├── vote.html
│   │   ├── vote_success.html
│   │   ├── vote_error.html
│   │   └── results.html
│   └── static/
│       └── css/
│           └── style.css
├── shared/
│   ├── database.py
│   └── security.py
├── database/
│   └── init.sql
├── docker-compose.yml
├── sample-voters.csv
└── README.md
```

## Environment Variables

### Database Configuration
- `DB_HOST`: PostgreSQL host (default: postgres)
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: Database name (default: voting_db)
- `DB_USER`: Database user (default: voting_user)
- `DB_PASSWORD`: Database password (default: voting_pass)

### Security Configuration
- `JWT_SECRET`: JWT signing key (CHANGE IN PRODUCTION!)
- `FLASK_SECRET`: Flask session secret (CHANGE IN PRODUCTION!)

## Production Deployment

⚠️ **IMPORTANT**: Before deploying to production:

1. **Change all secrets**:
   - `JWT_SECRET` in auth-service
   - `FLASK_SECRET` in frontend-service
   - Database password

2. **Enable HTTPS**:
   - Use reverse proxy (nginx, traefik)
   - SSL/TLS certificates

3. **Database**:
   - Use managed PostgreSQL service
   - Enable SSL connections
   - Regular backups

4. **Security**:
   - Enable rate limiting
   - Add CORS protection
   - Implement logging and monitoring
   - Regular security audits

5. **Email Integration**:
   - Integrate email service for token distribution
   - Send tokens securely to voters

## Sample Voter CSV Format

```csv
email
voter1@example.com
voter2@example.com
voter3@example.com
```

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose down
docker-compose up --build
```

### Database connection issues
```bash
# Check if PostgreSQL is ready
docker-compose ps
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up --build
```

### Port conflicts
If ports 5000-5004 are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "8000:5000"  # Change 5000 to 8000 on host
```

## Development

### Running individual services
```bash
# Start database only
docker-compose up postgres

# Install dependencies locally
cd auth-service
pip install -r requirements.txt

# Run service
python app.py
```

### Testing
Each service can be tested individually using curl or Postman:

```bash
# Test auth service
curl -X POST http://localhost:5001/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Test login
curl -X POST http://localhost:5001/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

## License

This project is provided as-is for educational and demonstration purposes.

## Support

For issues, questions, or contributions, please open an issue in the repository.

## Roadmap

Future enhancements:
- [ ] Email integration for token distribution
- [ ] SMS notifications
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Mobile app
- [ ] Blockchain integration for enhanced audit trails
- [ ] OAuth2 integration
- [ ] Advanced reporting and exports
