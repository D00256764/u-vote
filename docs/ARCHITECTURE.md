# Secure Voting System - Architecture Documentation

## System Architecture

### Overview
The Secure Voting System is built using a microservices architecture where each service has a specific responsibility and communicates through well-defined APIs. All services connect to a shared PostgreSQL database.

### Microservices

#### 1. Auth Service (Port 5001)
**Responsibility**: Organizer authentication and session management

**Components**:
- User registration with bcrypt password hashing
- Login with JWT token generation
- Token verification for protected routes

**Database Tables Used**:
- `organizers`

**Security Features**:
- Password hashing with bcrypt (12 rounds)
- JWT tokens with 24-hour expiration
- Secure session management

#### 2. Voter Service (Port 5002)
**Responsibility**: Voter list management and voting token generation

**Components**:
- CSV upload for bulk voter addition
- Individual voter addition
- Cryptographic token generation
- Token validation

**Database Tables Used**:
- `voters`
- `voting_tokens`

**Security Features**:
- Cryptographically secure random tokens (secrets.token_urlsafe)
- Token expiration (default: 7 days)
- Unique tokens per election-voter combination

#### 3. Voting Service (Port 5003)
**Responsibility**: Secure vote casting and ballot management

**Components**:
- Token-based ballot access
- Vote submission with validation
- Vote verification

**Database Tables Used**:
- `voting_tokens`
- `votes`
- `election_options`
- `elections`

**Security Features**:
- Single-use tokens
- Immutable vote records (database triggers)
- Identity-ballot separation
- SHA-256 vote hashing
- Optional hash chain

#### 4. Results Service (Port 5004)
**Responsibility**: Result tallying and audit trails

**Components**:
- Result calculation after election closes
- Vote distribution statistics
- Audit trail with hash chain verification
- Detailed analytics

**Database Tables Used**:
- `elections`
- `votes`
- `election_options`
- `voters`

**Security Features**:
- Read-only access to votes
- Results only available for closed elections
- Hash chain verification
- Transparent audit trails

#### 5. Frontend Service (Port 5000)
**Responsibility**: Web UI for organizers and voters

**Components**:
- Organizer dashboard
- Election management
- Voter management
- Voting interface
- Results visualization

**Technologies**:
- Flask web framework
- Jinja2 templating
- Bootstrap 5 for UI
- Session management

**Security Features**:
- CSRF protection (Flask)
- Secure session cookies
- Token validation before voting
- Input sanitization

### Database Schema

#### Tables:

1. **organizers**
   - id (PK)
   - email (unique)
   - password_hash
   - created_at

2. **elections**
   - id (PK)
   - organizer_id (FK)
   - title
   - description
   - status (draft/open/closed)
   - created_at, opened_at, closed_at

3. **election_options**
   - id (PK)
   - election_id (FK)
   - option_text
   - display_order

4. **voters**
   - id (PK)
   - election_id (FK)
   - email
   - created_at
   - UNIQUE(election_id, email)

5. **voting_tokens**
   - id (PK)
   - token (unique)
   - voter_id (FK)
   - election_id (FK)
   - is_used
   - expires_at
   - used_at
   - created_at

6. **votes**
   - id (PK)
   - election_id (FK)
   - option_id (FK)
   - vote_hash (SHA-256)
   - previous_hash (for chain)
   - cast_at

#### Security Constraints:
- Votes table has triggers to prevent UPDATE/DELETE
- Automatic hash generation on INSERT
- Foreign key constraints for referential integrity

### Data Flow

#### Election Creation Flow:
```
Organizer → Frontend → Database (elections, election_options)
```

#### Voter Addition Flow:
```
Organizer → Frontend → Voter Service → Database (voters)
```

#### Token Generation Flow:
```
Organizer → Frontend → Voter Service → Database (voting_tokens)
→ Token distributed to voters (manual/email)
```

#### Voting Flow:
```
Voter (with token) → Frontend → Voting Service
→ Validate token → Check election status
→ Store vote (with hash) → Mark token as used
→ Return confirmation hash
```

#### Results Flow:
```
Organizer → Frontend → Results Service
→ Check election closed → Tally votes
→ Return aggregated results
```

### Security Architecture

#### Authentication Layers:
1. **Organizer Authentication**: JWT tokens
2. **Voter Authentication**: One-time cryptographic tokens
3. **Service Communication**: Internal network (Docker)

#### Data Protection:
1. **At Rest**:
   - Passwords: bcrypt hashing
   - Votes: Stored without identity linkage
   - Database: PostgreSQL with auth

2. **In Transit**:
   - HTTP(S) for production
   - Internal Docker network for services

3. **Privacy**:
   - Identity-ballot separation
   - No way to link vote to voter after submission
   - Anonymous vote storage

#### Audit Trail:
1. Vote hashing (SHA-256)
2. Hash chain linking votes
3. Immutable vote records
4. Timestamp tracking
5. Token usage tracking

### Scalability Considerations

#### Horizontal Scaling:
- Each service can be scaled independently
- Load balancer in front of services
- Read replicas for database

#### Performance Optimization:
- Database indexes on frequently queried fields
- Connection pooling (SimpleConnectionPool)
- Caching for static content

### Deployment Architecture

#### Development:
```
Docker Compose
├── PostgreSQL Container
├── Auth Service Container
├── Voter Service Container
├── Voting Service Container
├── Results Service Container
└── Frontend Service Container
```

#### Production Considerations:
- Kubernetes for orchestration
- Managed PostgreSQL (RDS, Cloud SQL)
- Redis for session storage
- Nginx reverse proxy
- SSL/TLS certificates
- CDN for static assets

### Monitoring & Logging

#### Health Checks:
- Each service has /health endpoint
- PostgreSQL health check in docker-compose

#### Logging:
- Application logs (stdout/stderr)
- Database query logs
- Access logs

#### Metrics:
- Service availability
- Response times
- Vote throughput
- Token usage rates

### Disaster Recovery

#### Backup Strategy:
- Regular database backups
- Point-in-time recovery
- Vote data export

#### Data Retention:
- Elections: Indefinite
- Votes: Immutable, indefinite
- Tokens: Can be purged after expiration
- Logs: 90 days

### Compliance & Privacy

#### GDPR Considerations:
- Voter emails can be deleted after election
- Votes remain anonymous
- No personal data in vote records

#### Audit Requirements:
- Complete vote trail
- Hash chain verification
- Immutable records
- Timestamp accuracy

## API Communication

### Inter-Service Communication:
```
Frontend Service
├─→ Auth Service (login, verify)
├─→ Voter Service (manage voters, generate tokens)
├─→ Voting Service (get ballot, cast vote)
└─→ Results Service (get results, audit)
```

All services connect to PostgreSQL directly for database operations.

### External APIs:
None required for MVP. Future integration:
- Email service (SendGrid, AWS SES)
- SMS service (Twilio)
- Storage (S3, GCS)

## Error Handling

### Service Level:
- Try-catch blocks in all API endpoints
- Proper HTTP status codes
- Descriptive error messages
- Database rollback on errors

### Client Level:
- User-friendly error messages
- Validation before submission
- Loading states
- Retry mechanisms

## Testing Strategy

### Unit Tests:
- Service logic
- Security functions
- Database operations

### Integration Tests:
- API endpoints
- Service communication
- Database transactions

### End-to-End Tests:
- Complete voting flow
- Election lifecycle
- Error scenarios

### Security Tests:
- Token validation
- Vote immutability
- SQL injection prevention
- XSS prevention

## Future Enhancements

1. **Enhanced Security**:
   - End-to-end encryption
   - Blockchain integration
   - Zero-knowledge proofs

2. **Features**:
   - Multi-choice voting
   - Ranked-choice voting
   - Live result updates
   - Advanced analytics

3. **Integrations**:
   - OAuth2 (Google, Microsoft)
   - Email/SMS automation
   - Calendar integration
   - Mobile apps

4. **Scalability**:
   - Redis caching
   - Message queue (RabbitMQ)
   - CDN integration
   - Database sharding
