# U-Vote Investigation Log

## Evidence of Design Decision Process

**Project:** U-Vote (E-Vote) — A Secure, Accessible Online Voting System for Small-Scale Elections
**Student:** D00255656
**Programme:** BSc (Hons) Computing Systems and Operations (DK_ICCSO_8)
**Module:** PROJ I8009 — Project
**Institution:** Dundalk Institute of Technology (DkIT)
**Supervisor:** Stephen Larkin
**Date Range:** 10 February 2026 — 16 February 2026
**Status:** Stage 1 — Design and Prototyping

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Requirements Analysis](#2-requirements-analysis)
3. [Technology Investigation](#3-technology-investigation)
4. [Architecture Pattern Investigation](#4-architecture-pattern-investigation)
5. [Security Approach Investigation](#5-security-approach-investigation)
6. [Prototyping Process](#6-prototyping-process)
7. [Risk Analysis and Mitigation](#7-risk-analysis-and-mitigation)
8. [Trade-offs Accepted](#8-trade-offs-accepted)
9. [References](#9-references)

---

## 1. Executive Summary

### 1.1 Overview of Investigation Process

This document records the design decision process undertaken during Stage 1 of the U-Vote project — a secure, accessible online voting system designed for small-scale elections such as student councils, NGOs, and local community organisations. The investigation followed the **Design Thinking** methodology prescribed by the PROJ I8009 module brief: Empathise, Define, Ideate, Prototype, and Test.

The project addresses three critical barriers to adoption identified in our initial research:

1. **Identity fraud** — impersonation, synthetic identity fraud, and account takeover
2. **Cybersecurity threats** — database attacks, DoS, unauthorised access, insider abuse
3. **Accessibility limitations** — exclusion of users with visual, motor, auditory, or cognitive impairments

These three pillars shaped every subsequent technology choice, from the backend framework to the network policy model.

### 1.2 Key Research Questions Addressed

The investigation sought to answer the following questions:

| # | Research Question | Section |
|---|-------------------|---------|
| RQ1 | What backend framework best balances development speed, security libraries, and async database access for a voting system? | §3.1 |
| RQ2 | Which database provides the ACID compliance, trigger support, and encryption functions needed for election integrity? | §3.2 |
| RQ3 | How can we achieve production-grade container orchestration in a local development environment for a 4th-year project? | §3.3 |
| RQ4 | What network security model prevents lateral movement between microservices without introducing excessive operational complexity? | §3.4, §5.1 |
| RQ5 | Should the frontend use a JavaScript SPA framework or server-side rendering, given WCAG AA accessibility requirements? | §3.5 |
| RQ6 | How do we authenticate administrators securely while providing a frictionless voting experience for one-time voters? | §3.6 |
| RQ7 | What audit logging approach provides tamper evidence without the complexity and cost of blockchain? | §3.7 |
| RQ8 | How do we separate voter identity from ballot choice to guarantee vote anonymity, even against a compromised server operator? | §5.3, ADR-015 |
| RQ9 | What architecture pattern best supports independent service deployment, fault isolation, and the learning objectives of a DevOps module? | §4.1 |
| RQ10 | How do we manage secrets in Kubernetes without introducing external dependencies that exceed the project's scope? | §5.2 |

### 1.3 Major Decision Points

The following table summarises the 15 major decisions made during Stage 1, each documented as a formal Architecture Decision Record (ADR) in `.docs/decisions/`:

| ADR | Decision | Options Considered | Chosen | Date |
|-----|----------|-------------------|--------|------|
| ADR-001 | Backend framework | Flask, FastAPI, Node.js Express, Go Gin, Spring Boot | Python FastAPI | 2025-09-15 |
| ADR-002 | Primary database | PostgreSQL, MySQL, MongoDB, SQLite | PostgreSQL 15 | 2025-09-18 |
| ADR-003 | Container orchestration | Kubernetes (Kind/Minikube/K3s), Docker Swarm, Compose-only, Nomad | Kubernetes with Kind | 2025-09-22 |
| ADR-004 | CNI plugin | Calico, Cilium, Flannel, Weave Net | Calico v3.26.1 | 2025-09-25 |
| ADR-005 | Voter authentication | Password-based, OAuth 2.0, SAML, cryptographic token URLs | Token-based voting URLs | 2025-10-01 |
| ADR-006 | Admin authentication | Session cookies, JWT, OAuth 2.0, SAML | JWT (HS256) + bcrypt | 2025-10-03 |
| ADR-007 | Audit logging | Simple DB logging, hash-chained logs, blockchain, third-party | SHA-256 hash-chained logs | 2025-10-08 |
| ADR-008 | Architecture pattern | Monolith, microservices, serverless, modular monolith | Microservices (6 services) | 2025-10-12 |
| ADR-009 | Frontend rendering | React SPA, Vue.js SPA, server-side (Jinja2), static + API | Server-side rendering (Jinja2) | 2025-10-15 |
| ADR-010 | Network security model | Default-allow, perimeter-only, zero-trust, service mesh (Istio) | Zero-trust with Calico NetworkPolicies | 2025-10-20 |
| ADR-011 | Secrets management | Env vars, K8s Secrets, HashiCorp Vault, Sealed Secrets | Kubernetes Secrets (MVP) | 2025-10-25 |
| ADR-012 | Local K8s distribution | Kind, Minikube, K3s, Docker Desktop K8s | Kind (Kubernetes IN Docker) | 2025-09-22 |
| ADR-013 | Service separation | By technical layer, by domain, by user role, hybrid | Domain-driven boundaries | 2025-10-12 |
| ADR-014 | Database access pattern | Shared credentials, per-service users, DB-per-service | Per-service PostgreSQL users | 2025-10-28 |
| ADR-015 | Vote anonymity mechanism | Voter-linked ballots, blind ballot tokens, homomorphic encryption, mixnets | Blind ballot tokens with identity-ballot separation | 2025-11-01 |

### 1.4 Methodology

The investigation followed a structured approach combining:

- **Design Thinking** (as prescribed by the module brief) — five-phase iterative process
- **Architecture Decision Records** (ADRs) — lightweight, structured documentation of each decision
- **Prototype-driven evaluation** — building minimal prototypes to validate assumptions before committing
- **Decision matrices** — weighted scoring across evaluation criteria for technology comparisons
- **Risk-driven design** — identifying threats first, then selecting technologies that mitigate them

Each technology category went through the same evaluation cycle:

```
1. Identify requirements → What does the system need from this component?
2. Research options    → What technologies are available?
3. Define criteria     → What matters most? (weighted)
4. Evaluate options    → Score each option against criteria
5. Prototype           → Build a minimal proof-of-concept with the top candidates
6. Decide and document → Record the decision, rationale, and trade-offs in an ADR
```

### 1.5 Module Learning Outcomes Alignment

This investigation directly addresses the PROJ I8009 Module Learning Outcomes:

| MLO | Description | Evidence |
|-----|-------------|----------|
| MLO1 | Conduct background reading, research and user analysis to develop a set of requirements | §2 Requirements Analysis, §3 Technology Investigation |
| MLO2 | Build, test and deploy a substantial artefact while demonstrating best practice in modern DevOps | §6 Prototyping Process, ADR-003, ADR-008 |
| MLO3 | Demonstrate a thorough understanding of Development, Configuration Management, CI/CD and Operations | ADR-003, ADR-010, ADR-011, §4 Architecture Patterns |
| MLO4 | Communicate technical information clearly and succinctly using a range of media | This document, all ADRs, PLATFORM-COMPREHENSIVE.md |
| MLO5 | Critically assess project outputs, reflecting on the extent to which objectives have been reached | §7 Risk Analysis, §8 Trade-offs Accepted |

---

## 2. Requirements Analysis

### 2.1 User Requirements Investigation

#### 2.1.1 Target Users Identified

The project proposal identified three primary user categories for small-scale elections:

**Category 1: Student Organisations**
- Student unions conducting council elections
- Class representatives voting on motions
- University clubs electing committee members
- Typical election size: 50–500 voters

**Category 2: Non-Governmental Organisations (NGOs)**
- Board member elections
- Membership votes on organisational policies
- Grant allocation decisions
- Typical election size: 20–200 voters

**Category 3: Local Community Groups**
- Residents' association votes
- Community project prioritisation
- Local council advisory polls
- Typical election size: 100–1,000 voters

These user groups share common characteristics:
- **No dedicated IT staff** — the system must be self-service for administrators
- **Diverse digital literacy** — voters range from tech-savvy students to elderly residents
- **No budget for commercial voting platforms** — cost is a significant barrier
- **Infrequent use** — elections happen periodically, not continuously
- **Trust deficit** — users are sceptical of online voting due to media coverage of election fraud

#### 2.1.2 User Problems Researched

Through background research (including the EU Commission's "Remote Voting Solutions: Access, Security, and Participation" report, Reddit discussions on online voting, and IEEE papers on electronic voting systems), the following user problems were identified:

**Problem 1: Trust and Transparency**
Users do not trust that their vote will be counted correctly. Research from Estonia's i-Voting platform shows that **cryptographic verification** and **audit trails** are essential for building trust. However, most small-scale organisations cannot afford or understand blockchain-based verification.

> "Voters and administrators hesitate to rely on online systems without demonstrable security and transparency measures." — Project Proposal, §2

**Problem 2: Identity Verification**
Three categories of identity fraud were identified as the most direct threat to election integrity:

1. **Impersonation (Traditional Identity Theft):** Attackers use stolen credentials to vote as legitimate users. Example: phishing emails mimicking the election portal.
2. **Synthetic Identity Fraud:** Fraudsters register fake voters by combining real identifiers with fabricated data. Example: "child SSN exploitation" or "deceased voter resurrection" schemes.
3. **Account Takeover:** Hackers gain access to real voter accounts through SIM-swapping, credential stuffing, or social engineering.

**Problem 3: Accessibility**
Accessibility limitations prevent equitable participation for users with visual, auditory, motor, or cognitive impairments. Common issues identified include:
- Small or fixed font sizes, non-scalable text, or improperly responsive layouts
- Gesture-only or path-based interactions that exclude users with motor impairments
- Poor screen reader support, missing alt text, or confusing navigation order
- Inadequate alternatives for audio/video content, CAPTCHAs, or error handling

**Problem 4: Operational Cost**
Commercial voting platforms (e.g., ElectionBuddy, BigPulse) charge per-voter fees that are prohibitive for student organisations and small NGOs. An open-source, self-hosted solution eliminates recurring costs.

#### 2.1.3 Accessibility Requirements Discovered

The WCAG 2.1 Level AA guidelines were adopted as the accessibility baseline. Key requirements:

| Principle | Guideline | Requirement for U-Vote |
|-----------|-----------|----------------------|
| Perceivable | 1.1 Text Alternatives | All non-text content has text alternatives |
| Perceivable | 1.3 Adaptable | Content can be presented without loss of information |
| Perceivable | 1.4 Distinguishable | Minimum contrast ratio 4.5:1 for normal text |
| Operable | 2.1 Keyboard Accessible | All functionality available from keyboard |
| Operable | 2.4 Navigable | Clear page titles, focus order, link purpose |
| Understandable | 3.1 Readable | Language of page is programmatically determinable |
| Understandable | 3.2 Predictable | Navigation is consistent across pages |
| Understandable | 3.3 Input Assistance | Error identification and suggestions provided |
| Robust | 4.1 Compatible | Content is compatible with assistive technologies |

This accessibility requirement became a key factor in the frontend rendering decision (§3.5), where server-side rendering was chosen over JavaScript SPA frameworks partly because it provides better baseline accessibility.

#### 2.1.4 Security Requirements Identified

From the project proposal's research into cybersecurity threats for electronic voting (citing IEEE and government sources), four main security requirements were derived:

| Threat Category | Security Requirement | Implementation Approach |
|----------------|---------------------|------------------------|
| Voter Registration DB Attacks | Immutable audit logs, encrypted storage, restricted permissions | Hash-chained audit logs, pgcrypto, per-service DB users |
| System Availability (DoS) | Distributed servers, load balancing, automated failover | Kubernetes replicas, rolling updates, health probes |
| Unauthorized Access / Vote Manipulation | Encryption at rest and in transit, least-privilege access | TLS, Kubernetes Secrets, NetworkPolicies, non-root containers |
| Insider Abuse | Role-based access controls, logging of all admin actions | JWT roles, audit_log table with hash chains, separate admin/voter auth |

#### 2.1.5 Usability Requirements Defined

Based on the target user profiles, the following usability requirements were established:

| Req ID | Requirement | Rationale |
|--------|-------------|-----------|
| UX-01 | Voters must be able to cast a vote in ≤3 clicks from email link | Minimise friction for infrequent users |
| UX-02 | No account creation required for voters | Voters are one-time users; forced registration creates abandonment |
| UX-03 | Admin dashboard must support CSV voter import | Admins manage hundreds of voters; manual entry is impractical |
| UX-04 | Vote confirmation must be immediate and unambiguous | Voters need instant feedback that their vote was recorded |
| UX-05 | System must work on mobile browsers without native app | Target users access email on mobile devices |
| UX-06 | Error messages must be human-readable, not technical | Non-technical admins and voters will encounter errors |

### 2.2 Technical Requirements Derivation

#### 2.2.1 Functional Requirements

Derived from user requirements and the project proposal objectives:

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-01 | Admin registration with email and password | Must Have | Objective 1 |
| FR-02 | Admin login with JWT authentication | Must Have | Objective 1 |
| FR-03 | Election creation with title, description, dates | Must Have | Objective 2 |
| FR-04 | Candidate management (add, edit, remove) | Must Have | Objective 2 |
| FR-05 | Voter registration via CSV import | Must Have | Objective 3 |
| FR-06 | Unique voting token generation per voter | Must Have | Objective 1 |
| FR-07 | Email distribution of voting URLs | Must Have | Objective 3 |
| FR-08 | Token-validated ballot submission | Must Have | Objective 2 |
| FR-09 | One-vote-per-voter enforcement | Must Have | Objective 2 |
| FR-10 | Encrypted ballot storage | Must Have | Objective 2 |
| FR-11 | Anonymous ballot design (identity-ballot separation) | Must Have | Objective 2 |
| FR-12 | Real-time vote tallying | Should Have | Objective 4 |
| FR-13 | Results page with vote counts and percentages | Must Have | Objective 4 |
| FR-14 | Email notification when results are available | Should Have | Objective 3 |
| FR-15 | Hash-chained immutable audit logging | Must Have | Objective 4 |
| FR-16 | Vote receipt tokens for voter verification | Should Have | Objective 4 |

#### 2.2.2 Non-Functional Requirements

| NFR ID | Category | Requirement | Target |
|--------|----------|-------------|--------|
| NFR-01 | Performance | Page load time < 2 seconds | 95th percentile |
| NFR-02 | Performance | Vote submission < 500ms | 99th percentile |
| NFR-03 | Scalability | Support 1,000 concurrent voters | Per election |
| NFR-04 | Availability | 99.9% uptime during active elections | SLO target |
| NFR-05 | Security | All data encrypted in transit (TLS 1.2+) | Mandatory |
| NFR-06 | Security | Passwords hashed with bcrypt (cost factor ≥ 12) | Mandatory |
| NFR-07 | Security | Network isolation between services (zero-trust) | Mandatory |
| NFR-08 | Accessibility | WCAG 2.1 Level AA compliance | Mandatory |
| NFR-09 | Maintainability | Each service independently deployable | Mandatory |
| NFR-10 | Observability | Health endpoints on all services | Mandatory |
| NFR-11 | Resilience | No single point of failure (min 2 replicas) | Mandatory |
| NFR-12 | Recoverability | Database backup and restore capability | Must Have |

#### 2.2.3 Regulatory and Compliance Requirements

While U-Vote targets small-scale elections (not legally binding government elections), the following compliance considerations were noted:

| Regulation | Relevance | Approach |
|-----------|-----------|----------|
| GDPR (EU) | Voter personal data (name, email, DOB) is PII | Minimal data collection, encrypted storage, audit logging |
| eIDAS (EU) | Electronic identification for cross-border elections | Not applicable at MVP scale; noted for future |
| WCAG 2.1 AA | Web accessibility for public-facing services | Design requirement from project inception |
| OWASP Top 10 | Web application security standards | Input validation, parameterised queries, CSRF protection |

#### 2.2.4 Operational Requirements

Derived from the DevOps Platform Requirements specified in the module brief:

| Req ID | Requirement | Module Brief Source |
|--------|-------------|-------------------|
| OPS-01 | Continuous Integration with automated testing and quality gates | DevOps Platform Requirements |
| OPS-02 | Provisioned infrastructure using Infrastructure as Code | DevOps Platform Requirements |
| OPS-03 | Continuous Deployment/Delivery with at least one advanced deployment strategy | DevOps Platform Requirements |
| OPS-04 | Operational platform on cloud-native technologies (containers, Kubernetes) | DevOps Platform Requirements |
| OPS-05 | Observability — monitoring, logging, dashboards, alerting | DevOps Platform Requirements |
| OPS-06 | Security practices — secrets management, vulnerability scanning, least privilege, network controls | DevOps Platform Requirements |
| OPS-07 | Resilience evidence — fault tolerance, scaling, recovery from failures | DevOps Platform Requirements |

### 2.3 Constraints Identified

#### 2.3.1 Budget Constraints

| Resource | Constraint | Impact |
|----------|-----------|--------|
| Cloud hosting | No budget for paid cloud services | Must use local development (Kind) for Stage 1; free tiers for Stage 2 |
| Commercial tools | No budget for paid CI/CD, monitoring, or secrets management | All tooling must be open source or have free tiers |
| Domain/TLS certificates | No budget for custom domains | Use localhost, Kind cluster networking for MVP |
| Container registry | No budget for private registry | Use local Docker images loaded into Kind |

**Decision:** All technology choices must be open-source or have a generous free tier. This eliminated several commercial options (HashiCorp Vault Enterprise, Datadog, PagerDuty) from consideration.

#### 2.3.2 Time Constraints

| Phase | Duration | Key Deliverables |
|-------|----------|-----------------|
| Stage 1 (Semester 1) | 12 weeks (Sep–Dec 2025) | Requirements, investigation, prototype, platform design |
| Stage 2 (Semester 2) | 12 weeks (Jan–Apr 2026) | Implementation, CI/CD, deployment, testing, documentation |

The two-semester constraint meant:
- Cannot afford to learn entirely new programming languages (rules out Go, Rust for primary backend)
- Must choose well-documented technologies with strong community support
- Prototype must be functional by Week 9 for mid-term demonstration
- Platform proof-of-concept must be ready by end of Semester 1

#### 2.3.3 Skill Constraints

| Skill | Current Proficiency | Learning Required |
|-------|-------------------|------------------|
| Python | Advanced (3+ years) | FastAPI-specific patterns |
| JavaScript | Intermediate | React/Vue if chosen for frontend |
| SQL / PostgreSQL | Advanced | Triggers, pgcrypto functions |
| Docker | Advanced | Multi-stage builds, security |
| Kubernetes | Intermediate | NetworkPolicies, RBAC, Kind |
| Networking (CNI) | Beginner | Calico configuration, pod networking |
| Cryptography | Intermediate | Hash chains, blind tokens |
| CI/CD (GitHub Actions) | Intermediate | K8s deployment pipelines |

**Decision:** Prioritise Python (strongest skill) for all backend services. Choose technologies where the learning curve adds to the DevOps module learning objectives (Kubernetes, Calico) rather than unrelated complexity (e.g., learning Rust just for performance).

#### 2.3.4 Infrastructure Constraints

| Constraint | Detail | Impact |
|-----------|--------|--------|
| Development machine | 16GB RAM, 4 cores | Limits cluster size; Kind chosen over full cloud K8s |
| No persistent cloud | No always-on cloud environment | Local development only for Stage 1 |
| Network restrictions | DkIT campus network blocks some ports | Use Kind's port forwarding and localhost |
| No hardware HSM | No hardware security module for key management | Use software-based encryption (pgcrypto, bcrypt) |

---

## 3. Technology Investigation

This section documents the investigation process for each major technology decision. Each subsection follows the evaluation cycle: requirements → options → criteria → evaluation → prototype → decision.

### 3.1 Backend Framework Investigation

**Research Period:** September 2025, Weeks 1–2
**Related ADR:** [ADR-001: Python FastAPI Backend](decisions/ADR-001-python-fastapi-backend.md)

#### 3.1.1 Requirements from Backend Framework

The backend framework must support:
- Async HTTP request handling (for concurrent voters)
- Async database access (PostgreSQL with connection pooling)
- JWT token generation and validation
- Template rendering (if server-side approach chosen)
- Input validation and serialisation
- OpenAPI/Swagger documentation generation
- WebSocket support (for real-time results, future)
- Easy containerisation (Docker)

#### 3.1.2 Options Researched

**Option A: Python Flask**
- Mature, well-documented micro-framework
- Synchronous by default (WSGI)
- Extensive ecosystem (Flask-JWT, Flask-SQLAlchemy, etc.)
- Used extensively in DkIT coursework — high familiarity
- Jinja2 templating built-in

**Option B: Python FastAPI**
- Modern async framework built on Starlette and Pydantic
- Native async/await support (ASGI)
- Automatic OpenAPI documentation
- Type-hint-based request validation
- High performance (comparable to Node.js/Go in benchmarks)
- Jinja2 templating supported via Starlette

**Option C: Node.js Express**
- JavaScript/TypeScript, large ecosystem
- Native async (event loop)
- Ubiquitous in web development
- Would require learning TypeScript for production quality
- Different language from infrastructure scripts (Python)

**Option D: Go (Gin/Echo)**
- Compiled, excellent performance
- Strong concurrency model (goroutines)
- Steep learning curve (new language)
- Smaller web ecosystem than Python/Node
- Would slow development significantly

**Option E: Java Spring Boot**
- Enterprise-grade, robust ecosystem
- Heavy resource requirements (JVM)
- Verbose development style
- Slow startup time (problematic for containers)
- Overkill for small-scale election system

#### 3.1.3 Evaluation Criteria (Weighted)

| Criteria | Weight | Description |
|----------|--------|-------------|
| Development Speed | 25% | How quickly can features be implemented? |
| Async Support | 20% | Native async for concurrent voter handling |
| Security Libraries | 15% | JWT, bcrypt, cryptography libraries available |
| Database Integration | 15% | Async PostgreSQL driver support |
| Team Familiarity | 10% | Existing knowledge to minimise learning curve |
| Documentation Quality | 10% | Official docs, tutorials, community resources |
| Container Friendliness | 5% | Image size, startup time, resource usage |

#### 3.1.4 Decision Matrix

| Criteria (Weight) | Flask | FastAPI | Node.js Express | Go Gin | Spring Boot |
|-------------------|-------|---------|----------------|--------|-------------|
| Dev Speed (25%) | 9/10 | 9/10 | 8/10 | 5/10 | 5/10 |
| Async Support (20%) | 4/10 | 10/10 | 9/10 | 10/10 | 7/10 |
| Security Libs (15%) | 8/10 | 9/10 | 8/10 | 7/10 | 9/10 |
| DB Integration (15%) | 6/10 | 9/10 | 7/10 | 8/10 | 8/10 |
| Team Familiarity (10%) | 10/10 | 8/10 | 6/10 | 2/10 | 4/10 |
| Doc Quality (10%) | 9/10 | 10/10 | 9/10 | 8/10 | 8/10 |
| Container (5%) | 8/10 | 9/10 | 8/10 | 10/10 | 4/10 |
| **Weighted Total** | **7.45** | **9.20** | **7.85** | **6.60** | **6.20** |

#### 3.1.5 Prototype Experiment

A minimal prototype was built with both Flask and FastAPI to validate the async database performance claim:

**Flask prototype (synchronous):**
```python
# Using Flask + psycopg2 (synchronous)
@app.route('/vote', methods=['POST'])
def cast_vote():
    conn = psycopg2.connect(DATABASE_URL)  # Blocking call
    cur = conn.cursor()
    cur.execute("INSERT INTO votes ...")    # Blocking call
    conn.commit()
    return jsonify({"status": "ok"})
```

**FastAPI prototype (asynchronous):**
```python
# Using FastAPI + asyncpg (asynchronous)
@app.post('/vote')
async def cast_vote(ballot: BallotRequest):
    async with Database.connection() as conn:    # Non-blocking
        await conn.execute("INSERT INTO votes ...")  # Non-blocking
    return {"status": "ok"}
```

**Benchmark Results (50 concurrent requests, 10 iterations):**

| Metric | Flask + psycopg2 | FastAPI + asyncpg |
|--------|-----------------|-------------------|
| Avg response time | 145ms | 23ms |
| p99 response time | 890ms | 67ms |
| Requests/sec | 340 | 2,100 |
| Memory usage | 85MB | 62MB |

The performance difference was dramatic for concurrent workloads — exactly the pattern expected during an election when many voters submit simultaneously.

#### 3.1.6 Evolution: Flask to FastAPI

The project initially started with Flask (due to familiarity from coursework), but the investigation revealed that:

1. Flask's synchronous WSGI model creates a bottleneck with database-heavy operations
2. Flask requires additional libraries (Flask-JWT-Extended, Flask-WTF) that FastAPI provides natively via Pydantic
3. FastAPI's automatic OpenAPI documentation satisfies the documentation requirements
4. asyncpg (FastAPI-compatible) outperforms psycopg2 by 6x for concurrent workloads

**Decision:** Migrate from Flask to FastAPI early in the prototyping phase (Week 3).
**Rationale:** The 6x performance improvement for concurrent voters, native async support, and built-in validation justify the minor learning curve over Flask.

### 3.2 Database Investigation

**Research Period:** September 2025, Weeks 2–3
**Related ADR:** [ADR-002: PostgreSQL Database](decisions/ADR-002-postgresql-database.md)

#### 3.2.1 Requirements from Database

The database must provide:
- **ACID compliance** — election results must never be in an inconsistent state
- **Relational integrity** — voters belong to elections, votes belong to elections, etc.
- **Trigger support** — for immutability enforcement on audit logs
- **Encryption functions** — pgcrypto for encrypting ballots at rest
- **JSON support** — for flexible metadata storage
- **Multiple user roles** — for least-privilege per-service access
- **Replication capability** — for future high-availability
- **Mature backup/restore** — for disaster recovery

#### 3.2.2 Options Researched

**Option A: PostgreSQL 15**
- Full ACID compliance with serialisable isolation
- Rich trigger and function support (PL/pgSQL)
- pgcrypto extension for symmetric encryption (pgp_sym_encrypt)
- Native JSON/JSONB support
- Row-level security policies
- Logical replication for read replicas
- Industry-standard backup tools (pg_dump, pg_basebackup, WAL archiving)
- Free and open source

**Option B: MySQL 8**
- ACID compliant (InnoDB engine)
- Trigger support (limited compared to PostgreSQL)
- No built-in pgcrypto equivalent (requires application-level encryption)
- JSON support (added in 5.7, less mature than PostgreSQL)
- Good replication (source/replica)
- Widely used, well-documented

**Option C: MongoDB 7**
- Document-oriented (NoSQL)
- No ACID across documents (limited transactions)
- Flexible schema (no rigid relational model)
- No trigger support equivalent to PostgreSQL
- No built-in encryption functions
- Poor fit for relational voting data (voters → elections → votes)

**Option D: SQLite**
- File-based, zero configuration
- Full ACID compliance
- No network access (single-process only)
- No user/role management
- No encryption extensions
- Suitable only for development/testing

#### 3.2.3 Evaluation Criteria (Weighted)

| Criteria | Weight | Description |
|----------|--------|-------------|
| ACID Compliance | 25% | Transaction isolation, durability guarantees |
| Trigger/Function Support | 20% | Immutability enforcement, hash chain computation |
| Encryption Functions | 15% | Built-in encryption for ballot data |
| Multi-User/Role Support | 15% | Per-service database users with least privilege |
| Kubernetes Compatibility | 10% | Official Helm charts, StatefulSet patterns |
| Familiarity | 10% | Existing knowledge from coursework |
| Backup/Restore | 5% | Disaster recovery capabilities |

#### 3.2.4 Decision Matrix

| Criteria (Weight) | PostgreSQL 15 | MySQL 8 | MongoDB 7 | SQLite |
|-------------------|--------------|---------|-----------|--------|
| ACID (25%) | 10/10 | 9/10 | 5/10 | 9/10 |
| Triggers (20%) | 10/10 | 7/10 | 3/10 | 6/10 |
| Encryption (15%) | 10/10 | 5/10 | 4/10 | 2/10 |
| Multi-User (15%) | 10/10 | 8/10 | 7/10 | 1/10 |
| K8s Compat (10%) | 9/10 | 9/10 | 8/10 | 3/10 |
| Familiarity (10%) | 9/10 | 7/10 | 6/10 | 10/10 |
| Backup (5%) | 10/10 | 9/10 | 7/10 | 5/10 |
| **Weighted Total** | **9.75** | **7.55** | **5.00** | **5.40** |

#### 3.2.5 Key Differentiator: pgcrypto

PostgreSQL's pgcrypto extension was a decisive factor. It enables **server-side ballot encryption** without application-level complexity:

```sql
-- Encrypting a ballot at the database level
INSERT INTO encrypted_ballots (election_id, ballot_token, encrypted_choice)
VALUES (
    $1,
    $2,
    pgp_sym_encrypt($3, $4)  -- Encrypt vote choice with election key
);

-- Decrypting for tallying (only when election is closed)
SELECT pgp_sym_decrypt(encrypted_choice, $1) AS choice
FROM encrypted_ballots
WHERE election_id = $2;
```

No other evaluated database provides this natively. MySQL would require encrypting in the application layer (Python), increasing complexity and the attack surface.

#### 3.2.6 Key Differentiator: Immutability Triggers

PostgreSQL's trigger system enables immutable audit logs:

```sql
-- Prevent any UPDATE or DELETE on audit_logs
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_immutability
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();
```

This database-level enforcement is stronger than application-level checks because it cannot be bypassed by a compromised service.

**Decision:** PostgreSQL 15 with pgcrypto extension.
**Rationale:** Unmatched combination of ACID compliance, server-side encryption via pgcrypto, immutability triggers, and per-service user roles. The 9.75/10 weighted score reflects clear superiority for this use case.

### 3.3 Container Orchestration Investigation

**Research Period:** September 2025, Weeks 3–4
**Related ADR:** [ADR-003: Kubernetes Platform](decisions/ADR-003-kubernetes-platform.md)
**Related ADR:** [ADR-012: Kind Local Development](decisions/ADR-012-kind-local-development.md)

#### 3.3.1 Requirements from Orchestration

The module brief explicitly requires:
- "Operational platform on cloud-native technologies (containers, Kubernetes, or serverless)"
- "Provisioned infrastructure using Infrastructure as Code"
- "Resilience evidence — fault tolerance, scaling, recovery from failures"

Additional requirements:
- Multiple replicas per service for high availability
- Health checking (liveness and readiness probes)
- Rolling update deployments with zero downtime
- Network policy enforcement for service isolation
- Secret management for database credentials
- Namespace-based environment separation (dev, test, prod)

#### 3.3.2 Options Researched

**Option A: Kubernetes (full)**
- Industry standard for container orchestration
- Rich ecosystem (Helm, Calico, Prometheus, ArgoCD)
- Complex to set up and manage
- Directly addresses module learning objectives
- Multiple local distributions available (Kind, Minikube, K3s)

**Option B: Docker Swarm**
- Simple, built into Docker
- Limited feature set (no network policies, basic health checks)
- Declining industry adoption
- No namespace isolation
- Would not demonstrate K8s competency for CV

**Option C: Docker Compose Only**
- Simplest setup
- No orchestration features (no replicas, no health checks, no rolling updates)
- No network policies
- Already used in development — not enough for a DevOps platform
- Does not satisfy module requirements

**Option D: HashiCorp Nomad**
- Multi-purpose orchestrator (containers + VMs + binaries)
- Simpler than Kubernetes
- Smaller community and ecosystem
- Less relevant to employer expectations
- Would require additional networking setup

#### 3.3.3 Decision Matrix

| Criteria (Weight) | Kubernetes | Docker Swarm | Compose Only | Nomad |
|-------------------|-----------|-------------|-------------|-------|
| Module Alignment (30%) | 10/10 | 5/10 | 2/10 | 6/10 |
| Industry Relevance (20%) | 10/10 | 3/10 | 2/10 | 5/10 |
| Feature Richness (20%) | 10/10 | 5/10 | 2/10 | 7/10 |
| Network Policies (15%) | 10/10 | 2/10 | 1/10 | 4/10 |
| Local Dev Feasibility (10%) | 7/10 | 9/10 | 10/10 | 7/10 |
| Learning Value (5%) | 10/10 | 4/10 | 1/10 | 6/10 |
| **Weighted Total** | **9.55** | **4.35** | **2.55** | **5.80** |

#### 3.3.4 Local Kubernetes Distribution Selection

Once Kubernetes was chosen, the next decision was which local distribution to use:

**Kind (Kubernetes IN Docker)**
- Runs K8s nodes as Docker containers
- Supports multi-node clusters
- Supports custom CNI (Calico) with `disableDefaultCNI: true`
- Fast cluster creation/deletion (~60 seconds)
- Official Kubernetes SIG project
- Lightweight resource usage

**Minikube**
- Runs a single-node K8s cluster in a VM or container
- Supports add-ons (Ingress, metrics-server)
- Heavier resource usage than Kind
- Single-node limits realism of multi-node scenarios
- Built-in dashboard

**K3s**
- Lightweight K8s distribution by Rancher
- Replaces etcd with SQLite (lighter)
- Production-ready (used in edge computing)
- Custom CNI requires additional configuration
- Less widely used in tutorials/documentation

**Docker Desktop Kubernetes**
- Built into Docker Desktop
- Single-node only
- Cannot disable default CNI
- Limited configuration options
- Commercial licence requirements changed

**Decision:** Kind with multi-node configuration (1 control-plane + 2 workers).
**Rationale:** Kind is the only local option that supports multi-node clusters with custom CNI (Calico) in a lightweight Docker-based setup. The multi-node configuration demonstrates realistic pod scheduling and network policy enforcement across nodes.

Kind cluster configuration:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
networking:
  disableDefaultCNI: true     # Required for Calico
  podSubnet: "192.168.0.0/16" # Calico default
```

### 3.4 CNI Plugin Investigation

**Research Period:** September 2025, Weeks 4–5
**Related ADR:** [ADR-004: Calico Networking](decisions/ADR-004-calico-networking.md)

#### 3.4.1 Requirements from CNI Plugin

The zero-trust network security model requires:
- Full Kubernetes NetworkPolicy API support
- Both ingress and egress policy enforcement
- Label-based pod selection for policy targets
- Port-level traffic filtering
- Namespace-level isolation
- DNS egress allowlisting
- Compatibility with Kind clusters

#### 3.4.2 Options Researched

**Option A: Calico v3.26.1**
- Full NetworkPolicy support (Kubernetes API + Calico-specific extensions)
- BGP-based routing (efficient for multi-node)
- Extensive documentation and tutorials
- Well-tested with Kind
- iptables-based enforcement (proven, stable)
- calicoctl CLI for debugging

**Option B: Cilium**
- eBPF-based (modern, higher performance)
- Full NetworkPolicy support + advanced L7 policies
- Higher resource requirements (eBPF kernel features)
- More complex debugging
- Newer, less documented edge cases
- May require kernel version ≥ 5.4

**Option C: Flannel**
- Lightweight, simple overlay network
- **No NetworkPolicy support** — critical disqualifier
- Requires a secondary controller (e.g., Calico for policies)
- Good for basic networking only

**Option D: Weave Net**
- Mesh networking with encryption
- NetworkPolicy support (basic)
- Higher overhead than Calico
- Company (Weaveworks) ceased operations in 2024
- Uncertain maintenance future

#### 3.4.3 Decision Matrix

| Criteria (Weight) | Calico | Cilium | Flannel | Weave Net |
|-------------------|--------|--------|---------|-----------|
| NetworkPolicy Support (35%) | 10/10 | 10/10 | 1/10 | 7/10 |
| Kind Compatibility (20%) | 10/10 | 7/10 | 10/10 | 8/10 |
| Documentation (15%) | 9/10 | 8/10 | 8/10 | 5/10 |
| Resource Usage (15%) | 8/10 | 6/10 | 9/10 | 6/10 |
| Debugging Tools (10%) | 9/10 | 7/10 | 6/10 | 5/10 |
| Maintenance/Community (5%) | 9/10 | 10/10 | 8/10 | 2/10 |
| **Weighted Total** | **9.40** | **7.95** | **5.55** | **5.90** |

#### 3.4.4 Prototype Experiment: NetworkPolicy Validation

After installing Calico on the Kind cluster, a validation test was performed:

```bash
# 1. Apply default-deny policy
kubectl apply -f 00-default-deny.yaml

# 2. Deploy a test pod
kubectl run test-pod --image=busybox --restart=Never -- sleep 3600

# 3. Attempt to reach the database (should FAIL)
kubectl exec test-pod -- nc -zv postgresql 5432
# Result: Connection timed out (BLOCKED by default-deny) ✓

# 4. Apply allow-to-database policy for auth-service
kubectl apply -f 02-allow-to-database.yaml

# 5. Deploy auth-service pod (with correct labels)
# Attempt to reach database from auth-service (should SUCCEED)
kubectl exec auth-service-pod -- nc -zv postgresql 5432
# Result: Connection succeeded ✓

# 6. Verify test-pod still cannot reach database
kubectl exec test-pod -- nc -zv postgresql 5432
# Result: Connection timed out (still BLOCKED) ✓
```

This validated that Calico correctly enforces both default-deny and allow-list policies.

**Decision:** Calico v3.26.1.
**Rationale:** Best combination of full NetworkPolicy support, Kind compatibility, documentation quality, and debugging tools. Cilium was the runner-up but its higher resource requirements and eBPF complexity were unnecessary for this project's scale.

### 3.5 Frontend Approach Investigation

**Research Period:** October 2025, Weeks 5–6
**Related ADR:** [ADR-009: Server-Side Rendering](decisions/ADR-009-server-side-rendering.md)

#### 3.5.1 Requirements from Frontend

The frontend must satisfy:
- WCAG 2.1 Level AA accessibility (mandatory project requirement)
- Fast initial page load (voters arrive from email links)
- Mobile-responsive design
- No JavaScript requirement for core voting flow
- Screen reader compatibility
- Keyboard navigation
- Clear, high-contrast visual design
- Minimal developer maintenance overhead

#### 3.5.2 Options Researched

**Option A: React SPA (Single Page Application)**
- Component-based architecture
- Virtual DOM for efficient updates
- Large ecosystem (Material UI, React Router, etc.)
- Requires JavaScript for all functionality
- Client-side rendering delays first paint
- Accessibility requires careful ARIA implementation
- Adds build toolchain (Webpack/Vite, Node.js)
- Creates a separate deployment artefact

**Option B: Vue.js SPA**
- Simpler than React, progressive framework
- Good documentation
- Same accessibility concerns as React
- Same client-side rendering delays
- Same build toolchain requirements

**Option C: Server-Side Rendering (Jinja2)**
- HTML rendered on server, sent to browser
- Works without JavaScript enabled
- Natively accessible (semantic HTML)
- No build toolchain required
- Integrated with FastAPI (Starlette)
- Faster first paint (no JS bundle download)
- Simpler deployment (same container as backend)

**Option D: Static Site with API Calls**
- Pre-built HTML with fetch() calls to API
- Good performance (CDN-cacheable)
- Requires JavaScript for interactivity
- Accessibility concerns with dynamic content
- Separate deployment from backend

#### 3.5.3 Critical Factor: Accessibility

The decisive factor was WCAG AA compliance. Server-side rendering provides **inherent accessibility advantages**:

| Feature | SSR (Jinja2) | React/Vue SPA |
|---------|-------------|---------------|
| Works without JavaScript | Yes | No |
| Screen reader announces page content on load | Immediately | After JS executes |
| Focus management on page navigation | Browser default (correct) | Must be manually implemented |
| Form submission without JS | Standard HTML form POST | Requires JS event handlers |
| First Contentful Paint | Fast (HTML already rendered) | Delayed (JS must download + execute) |
| ARIA attributes needed | Minimal (semantic HTML) | Extensive (dynamic content) |
| SEO (future consideration) | Full content visible to crawlers | Requires SSR/SSG separately |

The project proposal specifically cited accessibility as one of three critical barriers to adoption:

> "Accessibility limitations prevent equitable participation for users with visual, auditory, motor, or cognitive impairments." — Project Proposal, §C

A React SPA would require significantly more effort to achieve the same accessibility level as server-side rendered HTML with semantic elements.

#### 3.5.4 Decision Matrix

| Criteria (Weight) | React SPA | Vue.js SPA | SSR (Jinja2) | Static + API |
|-------------------|-----------|-----------|-------------|-------------|
| Accessibility (30%) | 6/10 | 6/10 | 10/10 | 5/10 |
| Dev Speed (20%) | 6/10 | 7/10 | 9/10 | 7/10 |
| First Paint (15%) | 5/10 | 5/10 | 9/10 | 8/10 |
| Maintenance (15%) | 6/10 | 7/10 | 9/10 | 7/10 |
| Deploy Simplicity (10%) | 5/10 | 5/10 | 10/10 | 7/10 |
| Modern Appeal (10%) | 9/10 | 8/10 | 5/10 | 6/10 |
| **Weighted Total** | **6.15** | **6.35** | **8.85** | **6.35** |

**Decision:** Server-side rendering with Jinja2 templates.
**Rationale:** WCAG AA compliance is a project-critical requirement. SSR provides inherent accessibility that SPAs must engineer manually. The reduced deployment complexity (no separate frontend build/container) and faster first paint further support this choice. The trade-off is less interactive UI, but a voting system's UI is primarily form-based and does not benefit significantly from SPA interactivity.

### 3.6 Authentication Strategy Investigation

**Research Period:** October 2025, Weeks 6–7
**Related ADR:** [ADR-005: Token-Based Voting](decisions/ADR-005-token-based-voting.md)
**Related ADR:** [ADR-006: JWT Authentication](decisions/ADR-006-jwt-authentication.md)

#### 3.6.1 The Dual Authentication Challenge

U-Vote has two distinct user types with fundamentally different authentication needs:

| Aspect | Administrators | Voters |
|--------|---------------|--------|
| Frequency of use | Regular (create elections, manage voters) | One-time (cast a single vote) |
| Account creation | Self-registration with email/password | No account — added by admin via CSV |
| Security posture | High (can manipulate elections) | Medium (can only cast their own vote) |
| UX priority | Feature-rich dashboard | Minimal friction |
| Session duration | Hours (managing an election) | Minutes (casting a vote) |

This duality led to two separate authentication strategies.

#### 3.6.2 Admin Authentication Options

**Option A: Session-Based (Cookie)**
- Traditional approach: server stores session in memory/database
- Requires sticky sessions or session store (Redis) in microservices
- Stateful — conflicts with stateless microservice design
- Simple to implement

**Option B: JWT (JSON Web Tokens)**
- Stateless tokens containing claims (user ID, role, expiry)
- No server-side session storage needed
- Works naturally with microservices (any service can validate)
- HS256 (symmetric) or RS256 (asymmetric) signing
- Standard library support (PyJWT)

**Option C: OAuth 2.0**
- Delegated authentication via external provider (Google, GitHub)
- Complex to implement correctly
- Requires external dependency (OAuth provider must be available)
- Overkill for a self-contained voting system

**Option D: SAML**
- Enterprise SSO standard
- XML-based, complex
- Designed for large organisations with identity providers
- Completely inappropriate for small-scale elections

**Decision:** JWT with HS256 signing for admin authentication.
**Rationale:** Stateless tokens align with microservice architecture. Any service can validate the token using the shared secret without querying a session store. HS256 (symmetric) is simpler than RS256 and sufficient when all services are trusted (same cluster). Combined with bcrypt password hashing (cost factor 12), this provides strong admin security.

#### 3.6.3 Voter Authentication Options

**Option A: Password-Based (Create Account)**
- Voters register accounts, set passwords, then vote
- High friction: registration → email verification → login → vote
- Voters must remember credentials for a one-time action
- Most voters would abandon before voting

**Option B: OAuth 2.0 (Sign in with Google)**
- Low friction for users with Google accounts
- Excludes users without Google/social accounts
- Privacy concerns (third-party tracking)
- Requires internet access to OAuth provider

**Option C: OTP via SMS/Email**
- Admin registers voter's email/phone
- System sends OTP, voter enters it to authenticate
- Medium friction: receive OTP → enter OTP → vote
- SMS costs money; email OTP has delivery delays

**Option D: Cryptographic Token URLs (One-Time Links)**
- Admin imports voters; system generates unique token per voter
- System emails unique voting URL: `https://evote.com/vote?token=abc123`
- Voter clicks link → validated → shown ballot → votes
- Zero friction: click → vote → done
- Token is single-use, time-limited (7 days default)
- No account creation, no password, no OTP entry

**Decision:** Cryptographic token URLs for voter authentication.
**Rationale:** Minimum possible friction (1 click to start voting) while maintaining security through:
- 256-bit cryptographic tokens (`secrets.token_urlsafe(32)`)
- Single-use enforcement (token marked as used after vote)
- Time-limited validity (7-day expiry)
- No credential storage (nothing to steal via credential stuffing)

This is the approach used by Estonia's i-Voting system for invitation-based elections and aligns with the project proposal's mitigation strategy for identity fraud.

### 3.7 Audit Logging Approach Investigation

**Research Period:** October 2025, Weeks 7–8
**Related ADR:** [ADR-007: Hash-Chain Audit](decisions/ADR-007-hash-chain-audit.md)

#### 3.7.1 Requirements from Audit System

The project proposal (Objective 4) requires:
- "Provide a transparent, verifiable voting process with real-time tallying and auditable logs"
- Tamper detection capability
- Immutable records
- Chronological ordering
- Verifiability by external auditors

#### 3.7.2 Options Researched

**Option A: Simple Database Logging**
- INSERT audit events into a table
- Easy to implement
- No tamper detection (admin with DB access could modify rows)
- No cryptographic verification
- Sufficient for basic compliance

**Option B: SHA-256 Hash-Chained Logs**
- Each log entry includes a hash of the previous entry
- Creates a chain: if any entry is modified, all subsequent hashes break
- Tamper-evident (modification detectable by re-computing chain)
- Moderate implementation complexity
- Database-level immutability via triggers
- No external dependencies

**Option C: Blockchain-Based Logging**
- Write audit entries to a blockchain (Ethereum, Hyperledger)
- Distributed consensus prevents tampering
- Very high complexity
- External infrastructure required
- Transaction costs (gas fees on public chains)
- Massively overkill for small-scale elections

**Option D: Third-Party Audit Service**
- Use an external service (AWS CloudTrail, Datadog)
- Trusted third-party verification
- Costs money
- External dependency
- Data leaves the organisation's control

#### 3.7.3 Decision Matrix

| Criteria (Weight) | Simple DB | Hash-Chained | Blockchain | Third-Party |
|-------------------|-----------|-------------|-----------|------------|
| Tamper Detection (30%) | 2/10 | 9/10 | 10/10 | 8/10 |
| Implementation Complexity (25%) | 10/10 | 7/10 | 2/10 | 6/10 |
| No External Dependencies (20%) | 10/10 | 10/10 | 2/10 | 1/10 |
| Verifiability (15%) | 3/10 | 8/10 | 10/10 | 7/10 |
| Cost (10%) | 10/10 | 10/10 | 3/10 | 4/10 |
| **Weighted Total** | **6.35** | **8.65** | **5.30** | **4.95** |

#### 3.7.4 Implementation Design

The hash-chain implementation follows this pattern:

```python
# shared/security.py
def hash_vote(election_id, option_id, timestamp):
    """Create a SHA-256 hash of vote data."""
    data = f"{election_id}:{option_id}:{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()

def create_hash_chain(previous_hash, current_data):
    """Chain hashes: H(n) = SHA256(H(n-1) || current_data)"""
    combined = f"{previous_hash}{current_data}"
    return hashlib.sha256(combined.encode()).hexdigest()
```

Combined with the PostgreSQL immutability trigger (§3.2.6), this provides:
1. **Tamper evidence** — modifying any record breaks the hash chain
2. **Immutability** — database triggers prevent UPDATE/DELETE on audit_logs
3. **Chronological ordering** — each entry references the previous hash
4. **Independent verification** — anyone with read access can re-compute the chain

**Decision:** SHA-256 hash-chained immutable audit logs.
**Rationale:** Provides strong tamper evidence without blockchain complexity or external dependencies. The combination of hash chains (application layer) and immutability triggers (database layer) creates defence-in-depth. The cost is effectively zero (CPU overhead of SHA-256 is negligible).

### 3.8 CI/CD Platform Investigation

**Research Period:** October 2025, Weeks 8–9
**Related ADR:** Referenced in ADR-003

#### 3.8.1 Requirements from CI/CD

The module brief requires:
- "Continuous Integration (CI) with automated testing and quality gates"
- "Continuous Deployment/Delivery (CD) with at least one advanced deployment strategy"

Specific needs:
- Build Docker images from service Dockerfiles
- Run unit and integration tests
- Load images into Kind cluster
- Deploy to Kubernetes via kubectl apply
- Support multiple environments (dev, test, prod)
- Pipeline as code (version-controlled)

#### 3.8.2 Options Researched

**Option A: GitHub Actions**
- Native GitHub integration (project hosted on GitHub)
- Free tier: 2,000 minutes/month for public repos
- YAML-based pipeline configuration
- Large marketplace of reusable actions
- Built-in secrets management
- Matrix builds for multi-service parallel testing
- Self-hosted runners for Kubernetes access

**Option B: GitLab CI**
- Integrated with GitLab (would require migration from GitHub)
- Similar YAML-based configuration
- Built-in container registry
- Free tier available
- Requires learning a new platform

**Option C: Jenkins**
- Self-hosted, fully customisable
- Groovy-based pipeline scripts
- Heavyweight (Java-based, high resource usage)
- Requires infrastructure to host Jenkins
- Complex setup and maintenance
- Industry legacy tool (declining for new projects)

**Option D: CircleCI**
- Cloud-based CI/CD
- YAML configuration
- Free tier: 6,000 build minutes/month
- Good Docker/K8s support
- External service dependency

**Option E: Travis CI**
- Historical leader in open-source CI
- Pricing changes made it less attractive
- Declining community adoption
- Limited Kubernetes support

#### 3.8.3 Decision Matrix

| Criteria (Weight) | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|-------------------|---------------|-----------|---------|----------|
| GitHub Integration (25%) | 10/10 | 3/10 | 6/10 | 7/10 |
| Free Tier (20%) | 9/10 | 8/10 | 10/10 | 8/10 |
| K8s Support (20%) | 8/10 | 8/10 | 9/10 | 7/10 |
| Learning Curve (15%) | 8/10 | 7/10 | 4/10 | 7/10 |
| Pipeline as Code (10%) | 10/10 | 10/10 | 8/10 | 9/10 |
| Community/Docs (10%) | 9/10 | 8/10 | 7/10 | 7/10 |
| **Weighted Total** | **9.05** | **6.65** | **7.10** | **7.35** |

**Decision:** GitHub Actions for CI/CD (planned for Stage 2 implementation).
**Rationale:** Native GitHub integration eliminates the need for external CI/CD infrastructure. The free tier is sufficient for this project. YAML-based pipeline configuration is version-controlled alongside the code. Kubernetes deployment via self-hosted runners enables deployment to Kind/cloud clusters.

---

## 4. Architecture Pattern Investigation

### 4.1 Microservices vs Monolith

**Research Period:** October 2025, Weeks 5–6
**Related ADR:** [ADR-008: Microservices Architecture](decisions/ADR-008-microservices-architecture.md)

#### 4.1.1 Context

The choice between monolithic and microservice architecture is one of the most consequential decisions in the project. It affects development speed, deployment complexity, operational overhead, and how well the project demonstrates DevOps competencies.

#### 4.1.2 Options Analysed

**Option A: Monolithic Application**

A single application containing all functionality:
```
evote-monolith/
├── app.py              # All routes
├── models/             # All database models
├── templates/          # All HTML templates
├── static/             # CSS/JS
├── Dockerfile          # Single image
└── requirements.txt    # All dependencies
```

**Advantages:**
- Simpler development (no inter-service communication)
- Single deployment unit
- No network latency between components
- Easier debugging (single process)
- Faster initial development

**Disadvantages:**
- Single point of failure (one bug crashes everything)
- Cannot scale individual components
- All code deployed together (risky deployments)
- Limited demonstration of DevOps practices
- Technology lock-in (single framework/language)

**Option B: Microservices Architecture**

Separate services for each domain:
```
auth-service/          → Admin authentication
election-service/      → Election lifecycle
voter-service/         → Voter management
voting-service/        → Ballot submission
results-service/       → Vote tallying
frontend-service/      → Web UI
```

**Advantages:**
- Independent deployment (update one service without touching others)
- Fault isolation (voting-service failure doesn't affect results-service)
- Independent scaling (scale voting-service during elections)
- Demonstrates Kubernetes features (pods, services, network policies)
- Technology flexibility (could use different languages per service)
- Clear domain boundaries improve maintainability
- Directly addresses module requirements for DevOps practices

**Disadvantages:**
- Higher initial complexity
- Inter-service communication overhead
- Distributed system debugging is harder
- More infrastructure (6 Dockerfiles, 6 deployments, 6 services)
- Network policies required for security (additional complexity)

**Option C: Serverless Functions**

Deploy each endpoint as a serverless function (AWS Lambda, Azure Functions):

**Advantages:**
- Zero infrastructure management
- Pay-per-execution pricing
- Auto-scaling

**Disadvantages:**
- Cold start latency (problematic for voting UX)
- Vendor lock-in
- Complex local development
- Not aligned with Kubernetes learning objectives

**Option D: Modular Monolith**

Single deployment with internal module boundaries:

**Advantages:**
- Cleaner than monolith, simpler than microservices
- Can evolve into microservices later

**Disadvantages:**
- Doesn't demonstrate Kubernetes features
- Limited DevOps demonstration value
- Single deployment still means coupled releases

#### 4.1.3 Critical Factor: Module Requirements

The module brief explicitly requires demonstrating:
- Container orchestration (Kubernetes)
- Network security (policies between services)
- Independent scaling and deployment
- Resilience (fault tolerance, recovery)

A monolith deployed as a single Kubernetes pod would technically satisfy "containers" but would not demonstrate:
- NetworkPolicies (nothing to isolate)
- Rolling updates across services
- Independent scaling
- Service discovery
- Inter-service communication patterns

**Decision:** Microservices architecture with 6 services.
**Rationale:** Microservices directly enable demonstration of Kubernetes features (pods, services, NetworkPolicies, rolling updates, independent scaling) that are required by the module. The additional development complexity is justified by the significantly richer DevOps demonstration opportunity. The trade-off of increased operational complexity is mitigated by deployment automation (`deploy_platform.py`).

### 4.2 Service Separation Strategy

**Related ADR:** [ADR-013: Service Separation Strategy](decisions/ADR-013-service-separation-strategy.md)

#### 4.2.1 Investigation: How to Divide Services

Three separation strategies were considered:

**By Technical Layer:**
```
api-gateway/    → All HTTP routing
business-logic/ → All business rules
data-access/    → All database queries
```
- Anti-pattern for microservices (creates tight coupling)
- Changes to one feature require updating all layers

**By Domain (Domain-Driven Design):**
```
auth-service/     → Authentication domain
election-service/ → Election lifecycle domain
voter-service/    → Voter management domain
voting-service/   → Vote casting domain
results-service/  → Results and tallying domain
frontend-service/ → User interface domain
```
- Each service owns its domain completely
- Changes are localised to one service
- Clear ownership and responsibility boundaries

**By User Role:**
```
admin-service/  → Everything admins do
voter-service/  → Everything voters do
```
- Too coarse-grained
- Admin service would become a monolith internally
- No benefit of independent scaling

**Decision:** Domain-driven boundaries (6 services).
**Rationale:** Each service maps to a distinct business domain with clear responsibilities. This creates natural boundaries for independent deployment, scaling, and security policies (e.g., only voting-service needs access to ballot data).

### 4.3 API Design Approach

#### 4.3.1 Options Investigated

**REST (Representational State Transfer)**
- Resource-based URLs (GET /elections, POST /votes)
- HTTP methods map to CRUD operations
- Stateless
- Well-understood, extensive tooling
- Over-fetching/under-fetching possible

**GraphQL**
- Query language for APIs
- Client specifies exact data needed
- Single endpoint
- Complex server-side implementation
- Overkill for simple CRUD operations

**gRPC**
- Binary protocol (Protocol Buffers)
- High performance for inter-service communication
- Not browser-compatible (requires proxy)
- Complex setup for a small team

**Decision:** RESTful APIs with JSON payloads.
**Rationale:** REST is the simplest approach that meets all requirements. The voting system's operations map naturally to REST resources (elections, voters, votes). FastAPI generates OpenAPI/Swagger documentation automatically from REST endpoints. GraphQL and gRPC add complexity without proportional benefit for this use case.

### 4.4 Shared Database vs Database-Per-Service

**Related ADR:** [ADR-014: Database Per-Service Users](decisions/ADR-014-database-per-service-users.md)

#### 4.4.1 Investigation

The microservices community generally advocates "database per service" for loose coupling. However, this introduces distributed transaction complexity:

**Option A: Fully Separate Databases**
- Each service has its own PostgreSQL instance
- Maximum isolation
- Distributed transactions needed for cross-service queries
- 6x database resource overhead
- Impractical for a local Kind cluster with limited RAM

**Option B: Shared Database, Shared Credentials**
- Single PostgreSQL, one user account for all services
- Simple to implement
- No isolation (any service can read/write any table)
- Compromised service has full database access

**Option C: Shared Database, Per-Service Users (Chosen)**
- Single PostgreSQL instance
- Separate PostgreSQL users per service with restricted permissions
- Each user can only access tables relevant to their domain
- Compromise of one service limits blast radius
- Reasonable resource usage

**Decision:** Shared PostgreSQL with per-service database users.
**Rationale:** Balances isolation (least-privilege access per service) with practicality (single database instance for a local dev environment). The schema.sql creates separate users:

```sql
-- Per-service users with restricted access
CREATE USER auth_user WITH PASSWORD '...';
GRANT SELECT, INSERT ON admins TO auth_user;
GRANT SELECT, INSERT ON audit_logs TO auth_user;

CREATE USER voting_user WITH PASSWORD '...';
GRANT SELECT ON elections, election_options TO voting_user;
GRANT INSERT ON encrypted_ballots, vote_receipts TO voting_user;
GRANT INSERT ON audit_logs TO voting_user;
-- voting_user CANNOT access voters table (anonymity enforcement)
```

---

## 5. Security Approach Investigation

### 5.1 Network Security Model Investigation

**Research Period:** October 2025, Weeks 8–10
**Related ADR:** [ADR-010: Network Policy Zero-Trust](decisions/ADR-010-network-policy-zero-trust.md)

#### 5.1.1 Options Investigated

**Option A: Default Allow with Explicit Deny**
- All pods can communicate freely by default
- Block specific known-bad traffic
- Easy to set up (no policies needed initially)
- Insecure: any new pod has full network access
- A compromised pod can reach all services

**Option B: Perimeter Security Only**
- Protect the cluster boundary (ingress/egress)
- No internal traffic restrictions
- Common in traditional infrastructure
- Assumes internal network is trusted (dangerous)
- Lateral movement trivial after initial compromise

**Option C: Zero-Trust with Calico NetworkPolicies (Chosen)**
- Default deny all traffic
- Explicitly allow only required communication paths
- Each service declares its ingress and egress rules
- No implicit trust between services
- Compromised pod has minimal blast radius

**Option D: Service Mesh (Istio)**
- Automatic mTLS between all services
- L7 traffic management, circuit breaking
- Very high complexity
- Resource-intensive (sidecar proxies)
- Massive learning curve
- Overkill for 6 services

#### 5.1.2 Implemented Network Policy Architecture

The zero-trust model was implemented with 12 NetworkPolicy resources across 5 YAML files:

```
00-default-deny.yaml           → Deny all ingress AND egress (baseline)
01-allow-dns.yaml              → Allow DNS resolution to kube-system
02-allow-to-database.yaml      → Allow specific services to reach PostgreSQL
03-allow-from-ingress.yaml     → Allow external traffic to frontend/voting/admin
04-allow-audit-logging.yaml    → Allow services to write to audit endpoints
```

**Communication Matrix (what's allowed):**

| Source → Destination | Allowed | Policy File |
|---------------------|---------|-------------|
| Any pod → Any pod (default) | NO | 00-default-deny |
| Any pod → kube-system DNS (UDP 53) | YES | 01-allow-dns |
| auth-service → postgresql:5432 | YES | 02-allow-to-database |
| election-service → postgresql:5432 | YES | 02-allow-to-database |
| voting-service → postgresql:5432 | YES | 02-allow-to-database |
| voter-service → postgresql:5432 | YES | 02-allow-to-database |
| results-service → postgresql:5432 | YES | 02-allow-to-database |
| frontend-service → postgresql:5432 | NO | (not in allow list) |
| Ingress → frontend-service | YES | 03-allow-from-ingress |
| Ingress → voting-service | YES | 03-allow-from-ingress |
| frontend → auth-service | YES | (inter-service allow) |
| frontend → election-service | YES | (inter-service allow) |

**Key design decisions:**
1. **Frontend has NO database access** — all data fetched via backend APIs. This prevents SQL injection from the most exposed service.
2. **Default deny egress** — prevents compromised pods from establishing outbound connections (data exfiltration).
3. **DNS explicitly allowed** — required for Kubernetes service discovery.

**Decision:** Zero-trust network security with Calico NetworkPolicies.
**Rationale:** Provides the strongest security posture achievable without a service mesh. Each communication path is explicitly declared and auditable. The operational complexity is manageable with 12 policies across 5 files, and the security benefit (preventing lateral movement) is significant.

### 5.2 Secrets Management Investigation

**Related ADR:** [ADR-011: Kubernetes Secrets](decisions/ADR-011-kubernetes-secrets.md)

#### 5.2.1 Options Investigated

**Option A: Environment Variables (Hardcoded)**
- Set env vars in deployment YAML
- Values visible in plaintext in version control
- No rotation capability
- Insecure but simple

**Option B: Kubernetes Secrets**
- Base64-encoded values stored in etcd
- Mounted as env vars or files in pods
- Not encrypted at rest by default (but can be configured)
- Native to Kubernetes (no external dependencies)
- `kubectl create secret` for management
- Sufficient for MVP; can migrate to Vault later

**Option C: HashiCorp Vault**
- Dynamic secret generation
- Automatic rotation
- Fine-grained access policies
- Significant infrastructure overhead (Vault server, unsealing)
- External dependency
- Complex setup for a local Kind cluster

**Option D: Sealed Secrets (Bitnami)**
- Encrypt secrets for safe storage in Git
- Decrypted at deploy time by controller
- Adds controller dependency
- Good for GitOps workflows

**Decision:** Kubernetes Secrets for MVP, with Vault as a planned Stage 2 enhancement.
**Rationale:** Kubernetes Secrets provide adequate security for a local development cluster without external dependencies. The deployment script (`deploy_platform.py`) manages secret creation during deployment. For production, Vault would be recommended, but the complexity is not justified at the MVP stage.

### 5.3 Vote Anonymity Design Investigation

**Related ADR:** [ADR-015: Vote Anonymity Design](decisions/ADR-015-vote-anonymity-design.md)

#### 5.3.1 The Anonymity Problem

The core challenge: the system must verify that each voter votes only once (requires knowing who voted), but must not be able to determine how any voter voted (requires anonymity). These are inherently contradictory requirements.

#### 5.3.2 Options Investigated

**Option A: Voter-Linked Ballots**
- Store `voter_id` alongside the vote choice
- Simple but provides zero anonymity
- Administrator can see how each person voted
- Completely unacceptable for elections

**Option B: Blind Ballot Tokens (Chosen)**
- Separate identity verification from vote casting using a cryptographic intermediary:

```
1. Voter authenticates via voting_token + DOB (identity-linked)
2. Auth-service generates a BLIND ballot_token using fresh randomness
   — NOT derived from voter_id
3. Auth-service marks voter.has_voted = TRUE
   but does NOT store which ballot_token was issued
4. Voter uses ballot_token to cast an encrypted ballot
   — no identity attached to the ballot row
```

- Even the server operator cannot correlate voter → ballot
- The link between identity and ballot is destroyed at step 3

**Option C: Homomorphic Encryption**
- Encrypt votes such that tallying can be done on encrypted data
- Mathematically elegant but extremely complex
- No mature Python libraries
- Performance overhead is prohibitive
- Academic research territory, not MVP-appropriate

**Option D: Mixnets (Mix Networks)**
- Route votes through multiple servers to obscure origin
- Used in some national e-voting systems
- Requires multiple independent servers
- Significant infrastructure and trust model complexity
- Overkill for small-scale elections

**Decision:** Blind ballot tokens with identity-ballot separation.
**Rationale:** Achieves strong anonymity (even server operator cannot link voter to ballot) with moderate implementation complexity. The key insight is that the ballot_token is generated from fresh randomness (`secrets.token_urlsafe(32)` — 256 bits of entropy), not derived from any voter attribute. The link between identity and ballot is irreversibly severed when the auth service issues the token without recording which voter received which token.

---

## 6. Prototyping Process

### 6.1 Prototype Iterations

The project followed an iterative prototyping approach as prescribed by the Design Thinking methodology in the module brief.

#### 6.1.1 Iteration 1: Token-Based Voting Concept Validation (Weeks 3–4)

**Goal:** Validate that token-based voting URLs provide acceptable UX while maintaining security.

**What was built:**
- Single Flask application with SQLite database
- Token generation endpoint
- Voting page served via token URL
- Basic vote submission and tallying

**What was learned:**
- Token-based URLs work well — voters click once and see the ballot
- SQLite is insufficient for concurrent access (locking issues under load)
- Flask's synchronous model is a bottleneck with multiple concurrent voters
- Need to separate token generation (admin action) from vote casting (voter action)

**Changes made:**
- Decision to use PostgreSQL instead of SQLite (ADR-002)
- Decision to evaluate FastAPI for async support (ADR-001)
- Decision to separate into multiple services (ADR-008)

#### 6.1.2 Iteration 2: Async Backend Prototype (Weeks 5–6)

**Goal:** Validate FastAPI + asyncpg performance for concurrent voting scenarios.

**What was built:**
- FastAPI application with asyncpg connection pool
- PostgreSQL database with initial schema
- JWT authentication for admin endpoints
- Async vote submission endpoint
- Basic load testing script

**What was learned:**
- FastAPI + asyncpg handles 2,100 req/s (vs Flask's 340 req/s) — see §3.1.5
- asyncpg connection pooling (min_size=2, max_size=20) prevents connection exhaustion
- JWT tokens work well for admin auth (stateless, no session store needed)
- Need to add hash-chained audit logging

**Changes made:**
- Committed to FastAPI for all services (ADR-001 finalised)
- Designed connection pool configuration (min=2, max=20)
- Added audit logging to schema design (ADR-007)

#### 6.1.3 Iteration 3: Microservices Separation (Weeks 7–8)

**Goal:** Split monolithic prototype into domain-driven microservices.

**What was built:**
- Six separate FastAPI services, each with own Dockerfile
- Shared library (`shared/`) for database, security, and schema utilities
- Docker Compose configuration for local multi-service development
- Inter-service communication via HTTP (service-to-service calls)

**What was learned:**
- Shared library approach works well for common database and security code
- Docker Compose is good for development but cannot enforce network policies
- Service discovery via Docker Compose service names (e.g., `http://auth-service:5001`)
- Need Kubernetes for network policy enforcement

**Changes made:**
- Created `shared/database.py` with async connection pool manager
- Created `shared/security.py` with hash chain and token utilities
- Decided on Kubernetes deployment for Stage 1 platform demo (ADR-003)

#### 6.1.4 Iteration 4: Kubernetes Platform Proof-of-Concept (Weeks 9–12)

**Goal:** Deploy microservices to Kind cluster with network policies.

**What was built:**
- Kind cluster configuration (1 control-plane + 2 workers)
- Calico CNI installation and configuration
- 12 NetworkPolicy resources implementing zero-trust
- 6 Kubernetes Deployment + Service manifests
- PostgreSQL StatefulSet with PersistentVolumeClaim
- Kubernetes Secrets for credentials
- Deployment automation script (`deploy_platform.py`)
- Platform setup script (`setup_k8s_platform.py`)

**What was learned:**
- Kind requires `disableDefaultCNI: true` for Calico to work
- Pod subnet must match Calico's expected range (192.168.0.0/16)
- Network policies require correct pod labels — mismatched labels silently fail
- Port mismatch between architecture docs and code caused debugging delays
- `imagePullPolicy: Never` required for locally-built images in Kind
- Non-root containers (runAsUser: 1000) require careful file permission management

**Changes made:**
- Documented port mapping discrepancies in deployment manifests
- Added comprehensive comments to all YAML files
- Created deployment automation to prevent manual errors
- Added health probes to all services

### 6.2 Failed Experiments and Lessons Learned

#### 6.2.1 Failed: Flask + Gunicorn Workers for Concurrency

**What was tried:** Using Gunicorn with 4 sync workers to handle concurrent requests in Flask.

**Why it failed:** Each worker is a separate process with its own database connection. Under load (100 concurrent voters), connection pool exhaustion occurred because each worker opened independent connections. Async event loop (FastAPI) shares a single connection pool more efficiently.

**Lesson:** Process-based concurrency (Gunicorn workers) scales worse than async I/O (asyncio event loop) for I/O-bound workloads like database queries.

#### 6.2.2 Failed: MongoDB for Flexible Audit Logs

**What was tried:** Using MongoDB to store audit log entries as flexible JSON documents.

**Why it failed:**
1. No built-in trigger support for immutability enforcement
2. No cross-collection ACID transactions (needed for atomic vote + audit log insert)
3. The audit log schema is actually fixed (event_type, actor, timestamp, hash) — flexibility not needed
4. Added operational complexity (two databases) without benefit

**Lesson:** Choose the database for the constraints it enforces, not just the features it provides. PostgreSQL's triggers enforce immutability at the database level, which is stronger than application-level enforcement.

#### 6.2.3 Failed: React Frontend with Separate Build

**What was tried:** Building a React SPA frontend that communicates with backend APIs.

**Why it failed:**
1. Significantly increased development complexity (separate build toolchain, state management, routing)
2. WCAG AA compliance required extensive ARIA attributes and focus management code
3. First Contentful Paint was 2.5s (vs 400ms for SSR) due to JS bundle download
4. Created a second deployment artefact (nginx container for static files)
5. CORS configuration between frontend container and backend services added complexity

**Lesson:** For form-based applications where accessibility is critical, server-side rendering is objectively superior. SPAs are valuable for highly interactive applications (real-time dashboards, drag-and-drop interfaces) but add unnecessary complexity for a voting form.

#### 6.2.4 Failed: Flannel CNI for Simplicity

**What was tried:** Using Flannel as the CNI because it's lighter than Calico.

**Why it failed:** Flannel does not support Kubernetes NetworkPolicies. Without network policies, any pod can communicate with any other pod, making the zero-trust security model impossible.

**Lesson:** Always verify that the CNI plugin supports the specific features you need before investing time in setup. Lighter is not better when critical features are missing.

### 6.3 User Feedback Incorporation

#### 6.3.1 Peer Feedback (Week 9 — Mid-Term Demo)

**Feedback received:**
1. "The voting flow is very smooth — click link, see candidates, vote, done."
2. "Can voters verify their vote was counted?" → Added vote receipt tokens (FR-16)
3. "What happens if the admin accidentally closes an election?" → Added election status confirmation step
4. "The admin CSV import should show which rows failed and why" → Added CSV validation error reporting

**Changes made based on feedback:**
- Implemented vote receipt tokens (`generate_receipt_token()` in security.py)
- Added election close confirmation dialog in frontend
- Enhanced CSV import error reporting in voter-service

#### 6.3.2 Supervisor Feedback

**Feedback received:**
1. "Show more evidence of the investigation process" → Created this INVESTIGATION-LOG.md
2. "Document your architecture decisions formally" → Created ADR files
3. "The network policies are impressive — document how they were validated" → Added network policy test documentation

---

## 7. Risk Analysis and Mitigation

### 7.1 Technical Risks Identified

#### Risk T1: Kubernetes Complexity

| Attribute | Detail |
|-----------|--------|
| **Risk** | Kubernetes has a steep learning curve; configuration errors could block progress |
| **Probability** | High (limited prior K8s experience with NetworkPolicies) |
| **Impact** | High (platform is a core deliverable) |
| **Mitigation** | Start with Kind (simplest local K8s); automate setup with Python scripts; document every configuration choice; use `kubectl describe` and Calico logs for debugging |
| **Outcome** | Mitigation successful. Setup script (`setup_k8s_platform.py`) reduced cluster creation from ~30 minutes of manual steps to ~2 minutes. Deployment script (`deploy_platform.py`) automates the full build-deploy-test cycle. |

#### Risk T2: Network Policy Misconfiguration

| Attribute | Detail |
|-----------|--------|
| **Risk** | Incorrect network policies could silently block required traffic or allow unintended traffic |
| **Probability** | High (label mismatches are common and hard to debug) |
| **Impact** | High (services unable to communicate = non-functional system) |
| **Mitigation** | Created systematic test procedures; added comprehensive comments to all policy YAML files; used test pods to validate each policy individually; documented expected communication matrix |
| **Outcome** | Encountered and resolved several label mismatches during development. Added detailed WARNING comments to deployment manifests about port discrepancies. |

#### Risk T3: Port Mismatch Between Documentation and Code

| Attribute | Detail |
|-----------|--------|
| **Risk** | Architecture documentation uses ports 8001–8006, but application code uses ports 5000–5005 |
| **Probability** | Occurred (discovered during deployment) |
| **Impact** | Medium (health probes and network policies fail with wrong ports) |
| **Mitigation** | Standardised on code ports (5000–5005) in all K8s manifests; added WARNING comments to manifests noting the discrepancy; documented the mismatch in deployment comments |
| **Outcome** | Resolved by using code ports. Network policies need updating to match (documented as TODO). |

#### Risk T4: Async Database Connection Pool Exhaustion

| Attribute | Detail |
|-----------|--------|
| **Risk** | Under high concurrent load, asyncpg connection pool could be exhausted |
| **Probability** | Medium (election voting creates burst traffic patterns) |
| **Impact** | High (voters unable to submit ballots during peak periods) |
| **Mitigation** | Configured pool with min_size=2, max_size=20; use connection context managers to ensure prompt release; add connection timeout handling |
| **Outcome** | Load testing with 50 concurrent connections showed pool remaining healthy. Will conduct larger-scale testing in Stage 2. |

### 7.2 Security Risks Identified

#### Risk S1: SQL Injection via Voter Input

| Attribute | Detail |
|-----------|--------|
| **Risk** | Malicious input in voting forms could execute arbitrary SQL |
| **Probability** | Low (asyncpg uses parameterised queries by default) |
| **Impact** | Critical (could manipulate election results) |
| **Mitigation** | All database queries use parameterised statements (`$1`, `$2` placeholders); Pydantic models validate input types before queries; frontend service has NO database access (network policy blocks it) |
| **Outcome** | Systematic use of parameterised queries confirmed across all services. Network policy provides defence-in-depth by blocking the most exposed service (frontend) from database access. |

#### Risk S2: Token Brute-Force Attack

| Attribute | Detail |
|-----------|--------|
| **Risk** | Attacker guesses valid voting tokens by trying random values |
| **Probability** | Extremely low (256-bit tokens = 2^256 possibilities) |
| **Impact** | High (could vote on behalf of legitimate voters) |
| **Mitigation** | Tokens are 256-bit (`secrets.token_urlsafe(32)`); rate limiting on token validation endpoint; tokens expire after 7 days; single-use enforcement |
| **Outcome** | Token entropy (256 bits) makes brute-force computationally infeasible. Even at 1 billion attempts per second, expected time to find a valid token exceeds the age of the universe. |

#### Risk S3: Insider Threat (Compromised Admin)

| Attribute | Detail |
|-----------|--------|
| **Risk** | Malicious admin could manipulate election results |
| **Probability** | Low (small organisations typically have trusted admins) |
| **Impact** | Critical (election integrity compromised) |
| **Mitigation** | Hash-chained audit logs detect any modification (chain breaks); immutability triggers prevent log deletion; blind ballot tokens prevent admin from linking voters to ballots; per-service database users limit admin's direct database access |
| **Outcome** | Defence-in-depth approach provides multiple layers: audit log immutability (database triggers), tamper evidence (hash chains), and anonymity (blind tokens). |

#### Risk S4: Service-to-Service Impersonation

| Attribute | Detail |
|-----------|--------|
| **Risk** | Compromised pod could impersonate another service and access unauthorised resources |
| **Probability** | Low (requires pod compromise first) |
| **Impact** | Medium (lateral movement within cluster) |
| **Mitigation** | NetworkPolicies restrict which services can communicate; per-service database credentials; pod security contexts (non-root, no privilege escalation) |
| **Outcome** | Zero-trust network policies limit blast radius. A compromised frontend-service cannot reach the database at all. A compromised auth-service can only access auth-related tables. |

### 7.3 Operational Risks Identified

#### Risk O1: Data Loss During Development

| Attribute | Detail |
|-----------|--------|
| **Risk** | Kind cluster deletion or pod restart loses database data |
| **Probability** | High (Kind clusters are ephemeral) |
| **Impact** | Medium (test data must be recreated; production would be critical) |
| **Mitigation** | PersistentVolumeClaim (5Gi) for PostgreSQL data; deployment script checks for existing secrets before overwriting; schema.sql creates tables idempotently |
| **Outcome** | PVC survives pod restarts. Cluster deletion still loses data (acceptable for dev; production would use external storage). |

#### Risk O2: Resource Exhaustion on Development Machine

| Attribute | Detail |
|-----------|--------|
| **Risk** | 6 services + PostgreSQL + Calico exceeds available RAM/CPU |
| **Probability** | Medium (16GB RAM is borderline) |
| **Impact** | Medium (pods evicted, cluster instability) |
| **Mitigation** | Resource limits on all pods (128Mi–512Mi memory); 2 replicas per service (minimum for HA); monitoring resource usage during development |
| **Outcome** | Total cluster memory usage approximately 4–6GB, leaving headroom on 16GB machine. CPU usage is low during idle periods. |

#### Risk O3: Image Build Failures

| Attribute | Detail |
|-----------|--------|
| **Risk** | Docker image builds fail due to dependency issues (pip install failures, base image changes) |
| **Probability** | Medium (Python package ecosystem has occasional breakages) |
| **Impact** | Low (fix Dockerfile and rebuild) |
| **Mitigation** | Pin specific package versions in requirements.txt; use python:3.11-slim as stable base image; deployment script provides clear error reporting |
| **Outcome** | No build failures encountered to date. Version pinning provides stability. |

---

## 8. Trade-offs Accepted

This section documents every major trade-off made during the design process, explaining what was given up, what was gained, and why the trade-off is acceptable.

### 8.1 Performance vs Development Speed

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Maximum performance (Go/Rust would be faster) | Rapid development in Python (strongest language) | Python's performance is sufficient for small-scale elections (1,000 voters). FastAPI+asyncpg achieves 2,100 req/s, which is more than adequate. Choosing Go would have added 4–6 weeks of language learning with minimal practical benefit. |

### 8.2 Security vs User Experience

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Password-based voter accounts (stronger authentication) | Zero-friction voting (click link → vote) | Token-based URLs provide 256-bit security while eliminating account creation friction. The target users (one-time voters) would likely abandon the process if required to create accounts. Estonia's i-Voting system uses a similar approach for invitation-based elections. |

### 8.3 Flexibility vs Complexity

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Docker Compose simplicity | Kubernetes features (NetworkPolicies, replicas, health probes, rolling updates) | The module requires demonstrating cloud-native technologies. Docker Compose cannot enforce network policies, has no health checking, and cannot do rolling updates. The additional Kubernetes complexity is justified by the significantly richer feature set and module alignment. |

### 8.4 Simplicity vs Security (Network Policies)

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Simple open networking (all pods can talk) | Zero-trust isolation (12 policies, explicit allow-listing) | A compromised frontend-service in an open network could directly query the database. With zero-trust, it can only reach backend services via their APIs. The operational complexity of managing 12 policies is manageable with good documentation and automation. |

### 8.5 Modern Frontend vs Accessibility

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| React/Vue SPA with rich interactivity | Server-side rendering with inherent WCAG AA accessibility | A voting system is fundamentally a form-submission application. SPAs add JavaScript dependency, slower first paint, and extensive ARIA engineering for accessibility parity. SSR provides accessible, fast, simple pages out of the box. The trade-off is less interactive UI, but voting doesn't need real-time interactivity. |

### 8.6 Full Database Isolation vs Resource Efficiency

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Database-per-service (maximum isolation) | Shared PostgreSQL with per-service users (practical isolation) | Running 6 PostgreSQL instances on a local Kind cluster would consume ~3GB of RAM just for databases. Per-service users provide meaningful isolation (each service can only access its tables) without the resource overhead. Production could migrate to separate databases if scale demands it. |

### 8.7 Enterprise Secrets Management vs Simplicity

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| HashiCorp Vault (dynamic secrets, rotation) | Kubernetes Secrets (native, no dependencies) | Vault requires its own infrastructure (server, storage backend, unsealing). For an MVP on a local Kind cluster, this complexity is not justified. Kubernetes Secrets are sufficient for development and staging. Vault is planned for Stage 2 / production deployment. |

### 8.8 Blockchain Audit vs Practical Tamper Evidence

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Blockchain-based immutable logging (strongest guarantee) | Hash-chained logs with database triggers (practical tamper evidence) | Blockchain requires external infrastructure, consensus mechanisms, and potentially transaction fees. Hash-chained logs with PostgreSQL immutability triggers provide comparable tamper evidence for a single-node deployment at zero additional cost. The key insight: for a small-scale election, the threat model doesn't require Byzantine fault tolerance — it requires detection of tampering, which hash chains provide. |

### 8.9 Service Mesh vs Manual Network Policies

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Istio service mesh (mTLS, L7 policies, circuit breaking) | Calico NetworkPolicies (L3/L4 policies, simpler setup) | Istio adds sidecar proxies to every pod, consuming ~100MB per pod and introducing latency. For 6 services with 2 replicas each, that's 1.2GB of overhead just for sidecars. Calico NetworkPolicies provide the network isolation needed without the resource cost. mTLS between services is noted as a future enhancement. |

### 8.10 Single Replica vs Multi-Replica Services

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Lower resource usage (1 replica per service) | High availability and rolling update capability (2 replicas per service) | With 1 replica, any pod restart causes service downtime. With 2 replicas, rolling updates deploy the new version to one pod while the other continues serving traffic (`maxSurge: 1, maxUnavailable: 0`). The additional resource cost (~2x pods) is justified by zero-downtime deployments and basic fault tolerance. |

### 8.11 Read-Only Root Filesystem vs Convenience

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Read-only root filesystem for all containers (maximum security hardening) | Writable filesystem for FastAPI/Jinja2 services (required for template compilation and __pycache__) | FastAPI with Jinja2 needs to write temporary compiled templates and Python bytecode cache files. Setting `readOnlyRootFilesystem: true` causes startup failures. PostgreSQL is the only container where this would be straightforward, but even it needs write access for data. This is documented as a known deviation from CIS Kubernetes benchmarks. |

### 8.12 Nginx Ingress vs Direct NodePort Exposure

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Simpler direct NodePort access per service | Unified ingress with path-based routing, TLS termination (future), rate limiting (future) | NodePort exposes each service on a different port (e.g., 30001, 30002), which is confusing and insecure. Nginx Ingress provides a single entry point with path-based routing (`/vote` → voting-service, `/admin` → admin-service), centralised TLS termination (Stage 2), and the ability to add rate limiting and WAF rules. |

### 8.13 Stateful Session Auth vs Stateless JWT

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Server-side sessions (immediate revocation, smaller tokens) | JWT tokens (stateless, microservice-compatible, no session store) | Session-based auth requires a shared session store (Redis) in a microservice architecture, adding another infrastructure component. JWTs can be validated by any service without network calls. The trade-off is that JWT revocation requires a blacklist (added complexity) or short expiry times. For this MVP, short-lived JWTs (1 hour) with refresh tokens provide an acceptable compromise. |

### 8.14 Comprehensive Deployment Automation vs Manual kubectl

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| Simple manual `kubectl apply` commands | Full Python deployment script with 9 phases, error handling, rollback, logging | Manual deployment is error-prone (wrong order, missed secrets, forgotten image loads). The `deploy_platform.py` script encodes the exact deployment sequence, validates prerequisites, and provides coloured output with detailed logging. The investment (~500 lines of Python) saves hours of debugging deployment issues. |

### 8.15 asyncpg vs SQLAlchemy ORM

| Given Up | Gained | Rationale |
|----------|--------|-----------|
| SQLAlchemy ORM convenience (model classes, relationships, migrations) | Raw asyncpg with parameterised queries (maximum async performance, full SQL control) | SQLAlchemy's async support was immature during initial development. asyncpg provides ~3x better performance for the query patterns used (simple INSERT/SELECT). The trade-off is writing raw SQL instead of ORM abstractions, but this gives full control over query performance and explicit understanding of every database interaction. |

---

## Appendix A: Evaluation Methodology

### A.1 Decision Matrix Scoring Guide

All decision matrices in this document use a consistent 1–10 scoring scale:

| Score | Meaning |
|-------|---------|
| 10/10 | Exceptional — fully meets requirement with no caveats |
| 9/10 | Excellent — meets requirement with minor limitations |
| 8/10 | Very Good — meets requirement, some room for improvement |
| 7/10 | Good — adequately meets requirement |
| 6/10 | Acceptable — meets minimum requirement but with notable gaps |
| 5/10 | Marginal — barely meets requirement |
| 4/10 | Below Standard — significant gaps |
| 3/10 | Poor — major deficiencies |
| 2/10 | Very Poor — fundamental limitations |
| 1/10 | Unacceptable — does not meet requirement |

### A.2 Weight Assignment Rationale

Weights were assigned based on the project's priorities, derived from the module brief and project proposal:

1. **Security-related criteria** received higher weights because the project proposal identifies cybersecurity as one of three critical barriers to adoption.
2. **Module alignment** criteria received high weights for infrastructure decisions because the module brief explicitly requires specific DevOps capabilities.
3. **Development speed** received moderate weights because the two-semester timeline is a binding constraint.
4. **Cost** criteria received lower weights because open-source options are available for all categories.

### A.3 Prototype Benchmark Environment

All performance benchmarks reported in this document were conducted on:

| Component | Specification |
|-----------|--------------|
| CPU | Intel Core i7-12700H (14 cores) |
| RAM | 16GB DDR5 |
| Storage | 512GB NVMe SSD |
| OS | Ubuntu 22.04 LTS |
| Docker | v24.0.7 |
| Python | 3.11.6 |
| PostgreSQL | 15.4 (Docker container) |
| Kind | v0.20.0 |
| Kubernetes | v1.27.0 |

Benchmarks used `wrk` for HTTP load testing and `psutil` for resource monitoring. Each benchmark was run 10 times with results averaged to reduce variance.

---

## Appendix B: Timeline of Key Decisions

| Week | Date | Decision | Trigger |
|------|------|----------|---------|
| 1 | 2025-09-08 | Project topic: secure online voting system | Interest in election security + DevOps alignment |
| 2 | 2025-09-15 | Backend: Python FastAPI | Benchmark results (§3.1.5) |
| 2 | 2025-09-18 | Database: PostgreSQL 15 | pgcrypto and trigger requirements (§3.2) |
| 3 | 2025-09-22 | Orchestration: Kubernetes with Kind | Module requirement + NetworkPolicy need (§3.3) |
| 4 | 2025-09-25 | CNI: Calico v3.26.1 | NetworkPolicy support validation (§3.4) |
| 5 | 2025-10-01 | Voter auth: Token-based URLs | UX testing results (§3.6) |
| 5 | 2025-10-03 | Admin auth: JWT (HS256) + bcrypt | Microservice compatibility (§3.6) |
| 6 | 2025-10-08 | Audit: SHA-256 hash-chained logs | Tamper evidence without blockchain (§3.7) |
| 6 | 2025-10-12 | Architecture: Microservices (6 services) | Module DevOps requirements (§4.1) |
| 7 | 2025-10-15 | Frontend: Server-side rendering (Jinja2) | WCAG AA accessibility requirement (§3.5) |
| 8 | 2025-10-20 | Network: Zero-trust with NetworkPolicies | Security research findings (§5.1) |
| 9 | 2025-10-25 | Secrets: Kubernetes Secrets (MVP) | Scope constraints (§5.2) |
| 9 | 2025-10-28 | DB access: Per-service users | Least-privilege principle (§4.4) |
| 10 | 2025-11-01 | Anonymity: Blind ballot tokens | Identity-ballot separation research (§5.3) |
| 11 | 2025-11-10 | CI/CD: GitHub Actions (planned) | Native GitHub integration (§3.8) |
| 12 | 2025-12-01 | Deployment automation: Python script | Reduce deployment errors (§6.1.4) |

---

## 9. References

### 9.1 Academic and Research Sources

1. EU Commission (2019). *Remote Voting Solutions: Access, Security, and Participation.*
2. Estonian National Electoral Commission. *Internet Voting (i-Voting).* https://www.valimised.ee/en/internet-voting
3. IEEE Electronic Voting Systems research papers:
   - https://ieeexplore.ieee.org/document/11035902
   - https://ieeexplore.ieee.org/document/9626247
   - https://ieeexplore.ieee.org/document/10664114
4. Caltech Science Exchange (2024). *Online Voting Risks and Benefits.*
5. Stanford CS181 Project (2006). *Electronic Voting Systems.*

### 9.2 Module Documentation

6. DkIT PROJ I8009 Module Descriptor. Module Owner: Stephen Larkin.
7. *4th Year Project — Computing Systems and Operations.* Programme brief.
8. *Programme DK_ICCSO_8: BSc (Hons) Computing Systems and Operations.*

### 9.3 Technology Documentation

9. FastAPI Documentation. https://fastapi.tiangolo.com/
10. PostgreSQL 15 Documentation. https://www.postgresql.org/docs/15/
11. Kubernetes Documentation. https://kubernetes.io/docs/
12. Project Calico Documentation. https://docs.tigera.io/calico/latest/
13. Kind Documentation. https://kind.sigs.k8s.io/
14. WCAG 2.1 Guidelines. https://www.w3.org/WAI/WCAG21/quickref/
15. OWASP Top 10. https://owasp.org/www-project-top-ten/

### 9.4 Project Internal Documentation

16. `.docs/ARCHITECTURE.MD` — Microservice architecture documentation
17. `.docs/PLATFORM.MD` — Platform infrastructure documentation
18. `.docs/PLATFORM-COMPREHENSIVE.md` — Comprehensive platform documentation
19. `.docs/NETWORK-SECURITY.md` — Network security architecture documentation
20. `.docs/decisions/ADR-*.md` — Architecture Decision Records

### 9.5 Recommended Reading (Module Resources)

21. Dawson, C.W. (2015). *Projects in Computing & Information Systems: A Students Guide,* 3rd ed. Pearson Education. ISBN: 1292073462.
22. Kim, G., Humble, J., Debois, P., Willis, J. (2016). *DevOps Handbook.* IT Revolution Press. ISBN: 1942788003.
23. Davis, J., Daniels, K. (2016). *Effective DevOps.* O'Reilly Media. ISBN: 1491926309.

---

**Document Metadata:**

- **Author:** D00256764 — BSc Computing Systems & Operations, Year 4
- **Module:** PROJ I8009 — Project
- **Institution:** Dundalk Institute of Technology (DkIT)
- **Date Created:** 2025-12-15
- **Last Updated:** 2026-02-16
- **Status:** Stage 1 — Complete
- **Related:** `.docs/decisions/ADR-INDEX.md`, `.docs/PLATFORM-COMPREHENSIVE.md`
