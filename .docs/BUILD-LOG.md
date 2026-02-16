# U-Vote Build Log

## Project Development Journal

**Project:** U-Vote — A Secure, Accessible Online Voting System for Small-Scale Elections
**Student:** D00255656 — Luke Doyle
**Programme:** BSc (Hons) Computing Systems and Operations (DK_ICCSO_8)
**Module:** PROJ I8009 — Project (10 Credits, 2 Semesters)
**Institution:** Dundalk Institute of Technology (DkIT)
**Supervisor:** Stephen Larkin
**Status:** Stage 1 — Design and Prototyping

---

## Table of Contents

1. [Project Timeline Overview](#1-project-timeline-overview)
2. [Development Methodology](#2-development-methodology)
3. [Semester 1: Design & Prototyping](#3-semester-1-design--prototyping)
   - [Week 1: Project Initiation & Base Code](#week-1-project-initiation--base-code-jan-27--jan-31)
   - [Week 2: Documentation & Architecture Foundation](#week-2-documentation--architecture-foundation-feb-3--feb-7)
   - [Week 3: Platform Infrastructure & Database](#week-3-platform-infrastructure--database-feb-10--feb-14)
   - [Iteration 1 Retrospective](#iteration-1-retrospective-foundation-sprint)
   - [Week 4 (Partial): Network Security & Service Deployment](#week-4-partial-network-security--service-deployment-feb-15)
   - [Week 4 (Continued): Service Integration & Application Hardening](#week-4-continued-service-integration--application-hardening-feb-16)
   - [Iteration 2 Retrospective](#iteration-2-retrospective-security--deployment-sprint)
   - [Stage 1 Research & Decision Documentation](#stage-1-research--decision-documentation)
4. [Cumulative Metrics](#4-cumulative-metrics)
5. [Technical Debt Log](#5-technical-debt-log)
6. [Learning Journey](#6-learning-journey)
7. [Challenges and Solutions](#7-challenges-and-solutions)
8. [Iteration Retrospectives](#8-iteration-retrospectives)
9. [Final Reflection](#9-final-reflection)

---

# 1. Project Timeline Overview

## Gantt Chart

```
U-Vote Project Timeline — Stage 1 (Restart)
January 27, 2026 — February 16, 2026
═══════════════════════════════════════════════════════════════════════

WEEK 1: Jan 27 - Jan 31 (Project Initiation & Planning)
├── ▓▓▓▓▓ Project scope definition and requirements review
├── ▓▓▓▓▓ Research paper review and technology shortlisting
├── ▓▓▓░░ Initial codebase planning and service architecture
└── ▓▓░░░ Environment setup (Docker, Python 3.11, Kind)

WEEK 2: Feb 3 - Feb 7 (Base Code & Architecture)
├── ▓▓▓▓▓ Application base code (6 microservices)
├── ▓▓▓▓▓ Database schema design (init.sql)
├── ▓▓▓▓░ Docker Compose orchestration
├── ▓▓▓░░ Shared utilities (security.py, database.py, schemas.py)
└── ▓▓░░░ Initial README and ARCHITECTURE.md

WEEK 3: Feb 10 - Feb 14 (Platform & Infrastructure)
├── ▓▓▓▓▓ Kind cluster configuration and Calico CNI
├── ▓▓▓▓▓ PostgreSQL deployment on Kubernetes
├── ▓▓▓▓▓ Database test suite (1,270 lines)
├── ▓▓▓▓░ Platform setup automation script (641 lines)
├── ▓▓▓▓░ Network policies (12 policies, zero-trust)
├── ▓▓▓░░ Network policy validation and testing
└── ▓▓▓░░ Architecture and platform documentation

WEEK 4 (partial): Feb 15 - Feb 16 (Deployment & Documentation)
├── ▓▓▓▓▓ Service deployment manifests (6 services)
├── ▓▓▓▓▓ Deployment automation script (1,030 lines)
├── ▓▓▓▓▓ Stage 1 application hardening (auth, voting, results)
├── ▓▓▓▓▓ Investigation log and ADR documentation
├── ▓▓▓▓░ Platform documentation comprehensive update
└── ▓▓▓▓░ Network security architecture document (828 lines)

═══════════════════════════════════════════════════════════════════════
Legend: ▓ = completed   ░ = partially complete   · = not started
═══════════════════════════════════════════════════════════════════════
```

## Major Milestones

| # | Milestone | Target Date | Actual Date | Status |
|---|-----------|-------------|-------------|--------|
| M1 | Project restart and scope redefinition | Jan 27 | Jan 27 | Completed |
| M2 | Base code: 6 microservices functional | Feb 7 | Feb 8–10 | Completed |
| M3 | Docker Compose local development working | Feb 7 | Feb 10 | Completed |
| M4 | Architecture documentation complete | Feb 7 | Feb 11 | Completed |
| M5 | Kind cluster with Calico operational | Feb 11 | Feb 11 | Completed |
| M6 | PostgreSQL deployed on Kubernetes | Feb 12 | Feb 12 | Completed |
| M7 | Database test suite passing | Feb 12 | Feb 12 | Completed |
| M8 | Network policies implemented and tested | Feb 14 | Feb 15 | Completed |
| M9 | Service deployment manifests complete | Feb 15 | Feb 16 | Completed |
| M10 | Stage 1 application hardening (blind tokens, encryption) | Feb 15 | Feb 16 | Completed |
| M11 | Deployment automation script | Feb 15 | Feb 16 | Completed |
| M12 | ADRs and Investigation Log complete | Feb 16 | Feb 16 | Completed |
| M13 | Stage 1 deliverables submitted | Feb 16 | Feb 16 | Completed |

## Key Deliverables

### Stage 1 Deliverables (Design & Prototyping — 30% of Grade)

| Deliverable | Description | Status | Lines |
|-------------|-------------|--------|-------|
| Research Paper | Initial research document submitted before restart | Submitted | — |
| ARCHITECTURE.MD | Comprehensive architecture specification | Complete | 1,363 |
| PLATFORM.MD | Kubernetes infrastructure documentation | Complete | 3,270 |
| NETWORK-SECURITY.md | Zero-trust network policy specification | Complete | 828 |
| INVESTIGATION-LOG.md | Full investigation and decision process log | Complete | 2,027 |
| ADR-001 through ADR-015 | 15 Architecture Decision Records | Complete | 4,065 |
| ADR-INDEX.md | Decision record index and summary | Complete | 64 |
| database/init.sql | Production-ready database schema | Complete | 269 |
| schema.sql (K8s) | Kubernetes-deployed schema with per-service users | Complete | 194 |
| 6 Microservices | auth, election, voting, results, voter, frontend | Complete | 2,263 |
| Shared Utilities | database.py, security.py, schemas.py, email_util.py | Complete | 520 |
| Docker Compose | Local development orchestration | Complete | 161 |
| Kind Cluster Config | 3-node cluster with Calico | Complete | 15 |
| K8s Manifests | Namespaces, database, services, network policies | Complete | 2,060 |
| Platform Scripts | setup_k8s_platform.py, deploy_platform.py, test_db.py | Complete | 2,941 |
| Network Summaries | 6 validation reports + policy overview | Complete | 926 |

### Team Structure

| Role | Name | Student ID | Responsibility |
|------|------|-----------|----------------|
| Lead Developer / Platform Engineer | Luke Doyle | D00255656 | Platform infrastructure, Kubernetes, network security, documentation, deployment automation |
| Application Developer | Hafsa | — | Application services, database schema, voting logic, frontend templates |

---

## Semester Breakdown

### Semester 1 (Stage 1): Design & Prototyping

**Timeline:** January 27 — February 16, 2026 (accelerated restart)
**Weight:** 30% of total grade
**Focus:** Research, design decisions, architecture, working prototype, platform infrastructure

**Context — The Restart:**

The project underwent a significant restart in late January 2026. The original research paper had been completed earlier in the semester, but the implementation approach needed to be reconsidered and rebuilt from scratch. The restart compressed what would normally be a full semester's prototyping work into approximately three weeks. This required disciplined prioritisation and parallel workstreams between the two team members.

The restart was driven by the need to:
1. Rebuild the codebase with proper microservice separation from day one
2. Implement the blind ballot token anonymity protocol correctly
3. Build the Kubernetes platform infrastructure that was designed in the research phase
4. Produce comprehensive documentation demonstrating the design decision process

### Semester 2 (Stage 2): Implementation & Deployment

**Timeline:** February 2026 — April 2026 (planned)
**Weight:** 40% implementation + 20% reflection + 10% presentation
**Focus:** Complete implementation, testing, CI/CD, production deployment, final documentation

---

# 2. Development Methodology

## Approach: Iterative Prototyping with Kanban

The project used an **iterative prototyping** approach with **Kanban-style task management** rather than formal Scrum sprints. Given the compressed timeline (3 weeks for Stage 1) and two-person team, formal sprint ceremonies would have consumed disproportionate time. Instead, the workflow was organised around:

1. **Daily task prioritisation:** Each morning, review what was accomplished yesterday, identify blockers, and select the day's focus
2. **Parallel workstreams:** Platform infrastructure (Luke) and application development (Hafsa) progressed simultaneously
3. **Integration points:** Defined moments where the two workstreams merged (Docker Compose testing, K8s deployment)
4. **Documentation-driven development:** Architecture decisions documented as ADRs before or during implementation, not after

## Iteration Structure

The Stage 1 work was organised into two major iterations:

### Iteration 1: Foundation Sprint (Jan 27 — Feb 12)
**Goal:** Working application + platform infrastructure
- Base code for all 6 microservices
- Docker Compose local development
- Kind cluster with Calico CNI
- PostgreSQL on Kubernetes
- Database test suite
- Architecture documentation

### Iteration 2: Security & Deployment Sprint (Feb 13 — Feb 16)
**Goal:** Security hardening + deployment automation + documentation
- Network policies (zero-trust model)
- Service deployment manifests
- Application hardening (blind ballot tokens, encrypted ballots)
- Deployment automation scripts
- Research documentation (ADRs, Investigation Log)
- Network security documentation

## Planning Process

### Task Breakdown

Tasks were categorised by domain:

| Domain | Example Tasks |
|--------|--------------|
| **Platform** | Kind cluster setup, Calico installation, namespace creation |
| **Database** | Schema design, K8s deployment, per-service users, test suite |
| **Application** | Service implementation, API endpoints, template rendering |
| **Security** | Network policies, blind ballot tokens, vote encryption, hash chains |
| **Documentation** | ADRs, architecture docs, platform docs, investigation log |
| **Automation** | Setup script, deployment script, test scripts |

### Prioritisation Criteria

1. **Dependency order:** Platform before services, database before application logic
2. **Risk-first:** Security-critical components (anonymity, encryption) prioritised early
3. **Demo-readiness:** Features visible in the prototype prioritised for Stage 1 submission
4. **Documentation debt:** Documentation written alongside implementation, not deferred

## Tools Used

| Tool | Purpose |
|------|---------|
| **Git / GitHub** | Version control, pull request workflow, issue tracking |
| **VS Code** | Primary IDE for Python, YAML, SQL, Markdown |
| **Docker / Docker Compose** | Local development and containerisation |
| **Kind** | Local Kubernetes cluster |
| **kubectl** | Kubernetes management |
| **calicoctl** | Calico network policy management |
| **asyncpg** | Async PostgreSQL access from Python |
| **pgAdmin / psql** | Database administration and testing |

## Definition of Done

A feature or component was considered "done" when:

1. **Code:** Implementation complete and functional
2. **Tested:** Manually tested (integration tests for database, manual API testing for services)
3. **Documented:** Relevant documentation updated (ARCHITECTURE.MD, PLATFORM.MD, or ADR created)
4. **Committed:** Code committed to git with a descriptive commit message
5. **Integrated:** Works with other components (Docker Compose or K8s deployment)

## Review Process

- **Pull Request workflow:** Feature branches merged via GitHub pull requests
- **Code review:** Team members reviewed each other's PRs before merge
- **Integration testing:** Docker Compose `docker-compose up` verified all services start and communicate
- **Platform testing:** Kind cluster deployment verified K8s manifests apply correctly

## Git Workflow

```
main ─────────────────────────────────────────────── (stable)
  │
  ├── dev ────────────────────────────────────────── (integration)
  │     │
  │     ├── PR #1: base code (merged Feb 10)
  │     │
  │     └── PR #2: stage1 hardening (merged Feb 16)
  │
  └── (direct commits to main for platform/docs work)
```

The workflow used a `main` + `dev` branch model:
- Application code developed on `dev`, merged to `main` via pull requests
- Platform infrastructure and documentation committed directly to `main` (single-author workstream)
- Two pull requests during Stage 1: PR #1 (base code) and PR #2 (Stage 1 hardening)

---

# 3. Semester 1: Design & Prototyping

## Week 1: Project Initiation & Base Code (Jan 27 — Jan 31)

### Planned Goals

- Define the project scope and requirements for the restart
- Review the original research paper and extract technology decisions
- Set up the development environment (Python 3.11, Docker, Kind)
- Begin planning the microservice architecture
- Identify the service boundaries and database schema

### What Was Accomplished

**Project Scope Redefinition:**

The project restart required a clear re-scoping exercise. The original research paper had identified the core requirements:
- Secure online voting for small-scale elections (50–1,000 voters)
- Microservices architecture deployed on Kubernetes
- Vote anonymity through blind ballot tokens
- Zero-trust network security
- WCAG AA accessible frontend

The restart focused on building this from scratch with proper separation of concerns from day one, rather than refactoring a monolithic prototype.

**Research Review and Technology Confirmation:**

Reviewed the original research paper to confirm technology decisions:
- **Backend:** Python FastAPI (async, high performance, automatic OpenAPI docs)
- **Database:** PostgreSQL 15 with pgcrypto extension
- **Orchestration:** Kubernetes on Kind (local development)
- **CNI:** Calico (NetworkPolicy enforcement)
- **Frontend:** Server-side rendering with Jinja2 (accessibility-first)
- **Authentication:** JWT for admins, cryptographic tokens for voters

**Environment Setup:**

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11 | Runtime for all services |
| Docker | 24.x | Containerisation |
| Docker Compose | 3.8 | Local development orchestration |
| Kind | 0.20.x | Local Kubernetes clusters |
| kubectl | 1.28.x | Kubernetes CLI |
| PostgreSQL | 15-alpine | Database (Docker image) |

**Service Architecture Planning:**

Defined the six microservices and their responsibilities:

```
┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐
│ frontend-service│  │ election-service │  │  voter-service    │
│ (Admin UI)      │  │ (Election CRUD)  │  │ (Voter Mgmt)     │
│ Port: 5000      │  │ Port: 5005       │  │ Port: 5002        │
└────────┬────────┘  └────────┬─────────┘  └────────┬──────────┘
         │                    │                      │
    ┌────▼─────┐        ┌────▼─────┐          ┌─────▼────┐
    │auth-svc  │        │ voting-  │          │ results- │
    │Port:5001 │        │ service  │          │ service  │
    └──────────┘        │Port:5003 │          │Port:5004 │
                        └──────────┘          └──────────┘
```

**Initial Codebase Planning:**

Created the directory structure that would house the project:

```
u-vote/
├── auth-service/          # JWT auth, blind ballot tokens
├── voter-service/         # Voter CRUD, token generation
├── voting-service/        # Ballot display, vote casting
├── results-service/       # Tallying, decryption
├── election-service/      # Election lifecycle
├── frontend-service/      # Admin dashboard (SSR)
├── shared/                # Common utilities
├── database/              # Schema files
├── uvote-platform/        # K8s infrastructure
│   └── k8s/
│       ├── namespaces/
│       ├── database/
│       ├── services/
│       └── network-policies/
├── plat_scripts/          # Automation scripts
└── .docs/                 # Documentation
    └── decisions/         # ADRs
```

### Challenges Encountered

**Challenge 1: Scope Management Under Time Pressure**

- **Problem:** The restart compressed a full semester's prototyping into ~3 weeks. Needed to decide what was essential for Stage 1 vs. what could wait for Stage 2.
- **Root Cause:** Late restart meant limited time for iterative refinement.
- **Solution:** Created a strict priority list: (1) Core voting flow must work end-to-end, (2) Platform infrastructure must demonstrate Kubernetes + Calico, (3) Security features must be architecturally correct even if not all edge cases are handled, (4) Documentation must be comprehensive for the 30% design grade.
- **Outcome:** Focused effort on the critical path. Deferred CI/CD pipeline, email integration testing, and production deployment to Stage 2.
- **Time Impact:** Saved approximately 1 week by deferring non-essential features.

**Challenge 2: Team Coordination on Restart**

- **Problem:** Two developers needed to work in parallel without blocking each other.
- **Root Cause:** Shared codebase with interdependent components.
- **Solution:** Split responsibilities clearly — Luke focused on platform infrastructure (K8s, networking, database deployment, automation), Hafsa focused on application services (Python code, templates, business logic). Integration points were the shared database schema and Docker Compose file.
- **Outcome:** Parallel progress with minimal merge conflicts. Two clean pull requests during Stage 1.

### Technical Learnings

- **Learning 1:** FastAPI's async architecture pairs naturally with asyncpg for non-blocking database access. The `async with pool.acquire() as conn` pattern keeps the event loop free during queries.
- **Learning 2:** Docker Compose health checks (`pg_isready`) are essential for service startup ordering — without them, services attempt database connections before PostgreSQL is ready.

### Evidence

- **Commits:** `97e68a6` — Initial commit (Feb 8)
- **Documentation Created:** Project planning notes (informal)
- **Files Created:** Initial README.md

### Next Week Planning

- Implement all 6 microservices with basic functionality
- Create the database schema
- Set up Docker Compose for local development
- Write initial architecture documentation

### Time Spent

~20 hours (research, planning, environment setup, team coordination)

---

## Week 2: Documentation & Architecture Foundation (Feb 3 — Feb 7)

### Planned Goals

- Implement all 6 microservices with core functionality
- Design and implement the complete database schema
- Create Docker Compose orchestration for local development
- Write shared utility modules (database, security, schemas)
- Create initial README and ARCHITECTURE.MD

### What Was Accomplished

**Application Base Code — All 6 Microservices:**

The core application code was developed during this week, resulting in a functional voting system with all six services:

**auth-service (Port 5001) — 136 lines initially:**
```python
# Key endpoints implemented:
POST /register          # Organiser registration (bcrypt hashed)
POST /login             # JWT token issuance (HS256, 24h expiry)
POST /validate-token    # Voting token validation
POST /verify-dob        # Date of birth MFA verification
POST /ballot-token/issue # Blind ballot token generation
```

**voter-service (Port 5002) — 246 lines initially:**
```python
# Key endpoints implemented:
GET  /election/{id}/voters     # List voters for an election
POST /election/{id}/voters     # Add individual voter
POST /election/{id}/voters/csv # Bulk CSV upload
POST /generate-tokens          # Generate voting tokens
DELETE /voter/{id}              # Remove voter
```

**voting-service (Port 5003) — 231 lines initially:**
```python
# Key endpoints implemented:
GET  /vote/{token}          # Token validation + identity page
POST /verify-identity       # DOB verification + ballot token
GET  /ballot/{ballot_token} # Display ballot (SSR)
POST /cast-vote             # Encrypt + store vote
GET  /receipt/{token}       # Verify ballot receipt
```

**results-service (Port 5004) — 267 lines initially:**
```python
# Key endpoints implemented:
GET /election/{id}/results  # Tally + display results
GET /election/{id}/stats    # Election statistics
GET /health                 # Health check
```

**election-service (Port 5005) — new service:**
```python
# Key endpoints implemented:
POST   /elections                # Create election
GET    /elections                # List elections
GET    /elections/{id}           # Get election detail
PUT    /elections/{id}           # Update election
DELETE /elections/{id}           # Delete election
PUT    /elections/{id}/status    # Change status (draft/active/closed)
GET    /elections/{id}/options   # List candidates/options
POST   /elections/{id}/options   # Add candidate/option
```

**frontend-service (Port 5000) — 452 lines initially:**
```python
# Admin dashboard with SSR templates:
GET  /                    # Landing page
GET  /login               # Login form
POST /login               # Process login
GET  /register            # Registration form
POST /register            # Process registration
GET  /dashboard           # Admin dashboard
GET  /elections/{id}      # Election detail
GET  /elections/create     # Create election form
POST /elections/create     # Process creation
```

**Database Schema (init.sql — 105 lines initially):**

The initial schema defined the core tables:

```sql
-- Core tables created:
CREATE TABLE admins (...)           -- Organiser accounts
CREATE TABLE elections (...)        -- Election records
CREATE TABLE candidates (...)       -- Election options
CREATE TABLE voters (...)           -- Voter registry
CREATE TABLE voting_tokens (...)    -- One-time voting URLs
CREATE TABLE votes (...)            -- Anonymous ballots (NO voter_id)
CREATE TABLE audit_logs (...)       -- Immutable event log
```

Key design decisions in the initial schema:
- `votes` table had NO `voter_id` foreign key — anonymity enforced at schema level
- `voting_tokens` had `UNIQUE(voter_id, election_id)` — one token per voter per election
- `audit_logs` included `previous_hash` and `current_hash` for hash-chain integrity

**Shared Utilities:**

| File | Lines | Purpose |
|------|-------|---------|
| `shared/database.py` | 59 | asyncpg connection pool management |
| `shared/security.py` | 46 | Password hashing, JWT, token generation |

**Docker Compose (docker-compose.yml — 138 lines):**

Orchestrated all 7 containers (6 services + PostgreSQL):

```yaml
services:
  postgres:      # PostgreSQL 15-alpine with health check
  auth-service:  # Port 5001, depends on postgres
  voter-service: # Port 5002, depends on postgres
  voting-service: # Port 5003, depends on postgres + auth-service
  results-service: # Port 5004, depends on postgres
  election-service: # Port 5005, depends on postgres
  frontend-service: # Port 5000, depends on auth-service
```

**Initial Documentation:**

| File | Lines | Content |
|------|-------|---------|
| README.md | 448 | Project overview, architecture, setup instructions |
| ARCHITECTURE.md | 379 | Initial architecture specification |

### Challenges Encountered

**Challenge 3: Database Connection Pool Race Conditions**

- **Problem:** Services would crash on startup with `asyncpg.exceptions.ConnectionDoesNotExistError` because they attempted to create connection pools before PostgreSQL was ready.
- **Root Cause:** Docker Compose `depends_on` only waits for the container to start, not for PostgreSQL to accept connections. The `pg_isready` health check was needed.
- **Solution:** Added health check configuration to the PostgreSQL service in docker-compose.yml:
  ```yaml
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U voting_user -d voting_db"]
    interval: 10s
    timeout: 5s
    retries: 5
  ```
  Combined with `condition: service_healthy` on dependent services.
- **Outcome:** Services now wait for PostgreSQL to be fully ready before starting.
- **Time Impact:** ~2 hours debugging before identifying the root cause.

**Challenge 4: Shared Code Distribution Across Docker Images**

- **Problem:** Each microservice needed access to shared utilities (`database.py`, `security.py`, `schemas.py`), but each service builds its own Docker image. How to share code without creating a Python package?
- **Root Cause:** Docker build contexts are per-service, but shared code lives in a separate directory.
- **Solution:** Set the Docker build context to the project root and COPY the shared directory into each image:
  ```dockerfile
  # In each Dockerfile:
  COPY shared /app/shared
  COPY auth-service/requirements.txt .
  COPY auth-service/app.py .
  ```
  In docker-compose.yml:
  ```yaml
  auth-service:
    build:
      context: .  # Root context
      dockerfile: auth-service/Dockerfile
  ```
- **Outcome:** All services share the same utility code. Changes to shared/ are picked up on next build.
- **Time Impact:** ~1 hour to figure out the correct Docker context configuration.

**Challenge 5: JWT Token Flow Between Services**

- **Problem:** The frontend-service needed to forward JWT tokens to the auth-service for validation, but session management and token forwarding required careful cookie/header handling.
- **Root Cause:** FastAPI's SessionMiddleware stores data server-side, but the JWT needs to be forwarded in Authorization headers to backend services.
- **Solution:** Frontend stores the JWT in the session after login. For each request to backend services, the frontend extracts the JWT from the session and includes it in the `Authorization: Bearer <token>` header:
  ```python
  headers = {"Authorization": f"Bearer {request.session.get('token')}"}
  async with httpx.AsyncClient() as client:
      response = await client.get(f"{AUTH_URL}/validate", headers=headers)
  ```
- **Outcome:** Seamless authentication flow between frontend and backend services.
- **Time Impact:** ~3 hours including research on FastAPI session management.

### Technical Learnings

- **Learning 3:** FastAPI's automatic OpenAPI schema generation (`/docs`) is invaluable for testing API endpoints during development. Each service has its own Swagger UI at `http://localhost:500X/docs`.
- **Learning 4:** Pydantic v2 models (`shared/schemas.py`) provide both request validation and response serialization. Using `model_validate()` for database rows converts asyncpg Records to typed Python objects.
- **Learning 5:** The `httpx.AsyncClient` is the right choice for inter-service HTTP calls in async FastAPI services — it integrates with the async event loop without blocking.

### Evidence

- **Commits:**
  - `c723de7` — base code (35 files, 3,506 insertions)
  - `ac11b5d` — Merge pull request #1 from D00256764/dev
- **Files Created:** 35 files including all 6 services, shared utilities, database schema, Docker Compose, templates, static CSS
- **Pull Request:** PR #1 — Base code merge

### Code Evolution: auth-service

**Version 1 (Week 2):** Basic JWT authentication
```python
# auth-service v1: 136 lines
# - Organiser registration with bcrypt
# - Login with JWT issuance
# - Token validation endpoint
# - Basic DOB verification
```

**Version 2 (Week 4):** Added blind ballot token issuance
```python
# auth-service v2: 432 lines (+296 lines)
# - Added blind ballot token generation
# - Added voter MFA (DOB verification)
# - Added audit logging integration
# - Added comprehensive error handling
# - Added the "anonymity bridge" protocol
```

### Next Week Planning

- Set up Kind cluster with Calico CNI
- Deploy PostgreSQL to Kubernetes
- Create database test suite
- Write comprehensive architecture documentation
- Begin network policy design

### Time Spent

~35 hours (application development, database design, Docker configuration, testing)

---

## Week 3: Platform Infrastructure & Database (Feb 10 — Feb 14)

### Planned Goals

- Set up Kind cluster with 3 nodes and Calico CNI
- Deploy PostgreSQL to the Kubernetes cluster
- Create comprehensive database test suite
- Build platform setup automation script
- Write architecture and platform documentation
- Design and implement network policies
- Begin network policy validation testing

### What Was Accomplished

This was the most intensive week, with parallel progress on platform infrastructure and documentation. The git history shows 10 commits across 5 days:

**Day 1 — Monday, Feb 10: Project Module Requirements + PR Merge**

```
d933c31 - chore: added project module requirements
ac11b5d - Merge pull request #1 from D00256764/dev
```

- Added the official module specification PDF (PROJ I8009) to `.docs/` for reference
- Merged PR #1 (base code) into main, establishing the application foundation
- This merge brought all 6 microservices, the database schema, Docker Compose, and shared utilities into the main branch

**Day 2 — Tuesday, Feb 11: Documentation & Platform Foundation**

```
581d001 - docs: add project specs, architecture docs, and rewrite README
06c8951 - plat: created a basic kubernetes platform to test calico
```

**Documentation Sprint:**

Created the comprehensive architecture specification and platform documentation:

| File | Lines | Content |
|------|-------|---------|
| `.docs/ARCHITECTURE.MD` | 1,363 | Full microservice architecture, service APIs, database schema, security model, data flows |
| `.docs/PLATFORM.MD` | 559 | Kubernetes infrastructure, Kind config, Calico, namespaces, secrets, troubleshooting |
| `README.md` | 623 → rewritten | Updated project overview reflecting the actual implementation |

The ARCHITECTURE.MD document covered:
- System overview and high-level architecture diagram
- Detailed service descriptions with API endpoints
- Complete database schema with all tables and relationships
- Security architecture (4-layer defence in depth model)
- Per-service database user permission matrix
- Data flow examples (voting flow, authentication flow)
- Deployment architecture (Docker Compose + Kubernetes)

**Kind Cluster Configuration:**

Created the Kind cluster configuration (`uvote-platform/kind-config.yaml`):

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: uvote
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
  - containerPort: 443
    hostPort: 443
- role: worker
- role: worker
networking:
  disableDefaultCNI: true    # Essential for Calico
  podSubnet: 192.168.0.0/16  # Calico default subnet
```

Key configuration decisions:
- **3 nodes** (1 control-plane, 2 workers): Demonstrates real pod scheduling across nodes
- **`disableDefaultCNI: true`**: Required to install Calico instead of the default kindnet
- **`podSubnet: 192.168.0.0/16`**: Calico's default CIDR range
- **Port mappings**: 80 and 443 for future Ingress controller access

**Namespace Configuration:**

Created `uvote-platform/k8s/namespaces/namespaces.yaml`:

```yaml
# Three namespaces for environment separation:
# uvote-dev   — Development environment (primary for Stage 1)
# uvote-test  — Testing environment (future use)
# uvote-prod  — Production environment (future use)
```

**Day 3 — Wednesday, Feb 12: Database Deployment & Testing**

```
b658c9a - chore: created generic .gitignore file
15df12b - plat: added postgres db to platform
e1f05c3 - script: added script to auto delete and set up a k8s Cluster
f5603a2 - test: add comprehensive database test suite for PostgreSQL on K8s
```

**PostgreSQL Kubernetes Deployment:**

Created the database infrastructure manifests:

| File | Lines | Purpose |
|------|-------|---------|
| `db-deployment.yaml` | 86 | PostgreSQL 15 Deployment with resource limits |
| `db-pvc.yaml` | 11 | PersistentVolumeClaim (5Gi storage) |
| `db-secret.yaml` | 10 | Database credentials (base64 encoded) |
| `schema.sql` | 194 | K8s-specific schema with per-service users |

The K8s schema (`schema.sql`) included per-service database users:

```sql
-- Per-service users with least-privilege access:
CREATE USER auth_user WITH PASSWORD '<from-secret>';
GRANT SELECT, INSERT, UPDATE ON organisers TO auth_user;
GRANT SELECT ON voters, elections TO auth_user;
GRANT INSERT ON audit_log TO auth_user;

CREATE USER voting_user WITH PASSWORD '<from-secret>';
GRANT SELECT ON elections, election_options TO voting_user;
GRANT SELECT, INSERT ON encrypted_ballots TO voting_user;
GRANT INSERT ON audit_log TO voting_user;

CREATE USER results_user WITH PASSWORD '<from-secret>';
GRANT SELECT ON elections, election_options, encrypted_ballots TO results_user;
GRANT SELECT, INSERT ON tallied_votes TO results_user;
-- Read-only: cannot modify any data
```

**Platform Setup Automation:**

Created `plat_scripts/setup_k8s_platform.py` (641 lines):

```python
# Automated platform setup steps:
# 1. Delete existing Kind cluster (if present)
# 2. Create new Kind cluster with config
# 3. Install Calico operator and custom resources
# 4. Wait for Calico to become ready
# 5. Create namespaces (dev, test, prod)
# 6. Deploy PostgreSQL (PVC, Secret, Deployment, Service)
# 7. Wait for PostgreSQL to become ready
# 8. Apply database schema
# 9. Apply network policies
# 10. Verify deployment
```

Features of the setup script:
- Coloured terminal output for clear progress indication
- Automatic waiting with timeout for component readiness
- Error handling with meaningful error messages
- Idempotent — safe to run multiple times
- Configurable via command-line arguments

**Comprehensive Database Test Suite:**

Created `plat_scripts/test_db.py` (1,270 lines):

```python
# Test categories:
# 1. Connection Tests — verify each per-service user can connect
# 2. Permission Tests — verify users can only access their tables
# 3. Denial Tests — verify users CANNOT access restricted tables
# 4. Schema Tests — verify all tables, columns, constraints exist
# 5. Trigger Tests — verify immutability triggers work
# 6. Hash Chain Tests — verify SHA-256 hash chains are generated
# 7. Encryption Tests — verify pgp_sym_encrypt/decrypt works
# 8. Performance Tests — verify query times are acceptable
```

This was the most comprehensive testing artefact in Stage 1, validating:
- All 5 per-service database users can connect with correct credentials
- Each user has exactly the permissions documented in ADR-014
- Immutability triggers prevent UPDATE/DELETE on `audit_log` and `encrypted_ballots`
- Hash chain triggers auto-generate SHA-256 hashes
- `pgp_sym_encrypt` correctly encrypts and decrypts vote data

**Day 4 — Thursday, Feb 13: README Update**

```
d5fa9fd - chore: updated README using documentation
```

Updated the README.md to reflect the actual project state:
- Added accurate service descriptions
- Updated architecture diagram
- Added platform infrastructure section
- Added security features summary
- Updated getting started instructions for both Docker Compose and Kubernetes

**Day 5 — Friday, Feb 14: (continued work on network policies — committed next day)**

Network policy design and initial implementation work began on Friday, though the commits landed on Saturday Feb 15 (see Week 4).

### Design Iterations

**Database Schema Evolution:**

| Version | Tables | Key Changes |
|---------|--------|-------------|
| v1 (init.sql, Week 2) | 7 tables | Basic schema: admins, elections, candidates, voters, voting_tokens, votes, audit_logs |
| v2 (schema.sql, Week 3) | 12 tables | Added: organisations, organisers, voter_mfa, blind_tokens, election_options, encrypted_ballots, vote_receipts, tallied_votes. Renamed and restructured for production use. |

Key evolution from v1 to v2:
- **`votes` → `encrypted_ballots`**: Ballots now encrypted with `pgp_sym_encrypt`
- **Added `blind_tokens`**: The anonymity bridge between identity and ballot
- **Added `voter_mfa`**: DOB-based multi-factor authentication records
- **Added `vote_receipts`**: Voter verification tokens
- **Added `tallied_votes`**: Cached tallying results
- **Added per-service users**: 5 PostgreSQL users with GRANT statements
- **Added immutability triggers**: BEFORE UPDATE/DELETE on audit_log and encrypted_ballots
- **Added hash chain triggers**: Auto-generate SHA-256 hashes on INSERT

### Challenges Encountered

**Challenge 6: Calico Installation on Kind**

- **Problem:** After creating the Kind cluster with `disableDefaultCNI: true`, pods were stuck in `Pending` state because no CNI was installed. The Calico operator installation required specific configuration for Kind.
- **Root Cause:** Kind clusters need Calico configured for the same pod CIDR (`192.168.0.0/16`). The default Calico installation assumes a different subnet.
- **Investigation:**
  1. Initial hypothesis: Calico pods weren't scheduling due to resource limits → Incorrect
  2. Checked Calico operator logs: `kubectl logs -n calico-system deployment/calico-kube-controllers`
  3. Found that the custom resource needed `cidr: 192.168.0.0/16` to match Kind's `podSubnet`
  4. Also needed `nodeAddressAutodetectionV4.kubernetes: NodeInternalIP` for Kind's Docker networking
- **Solution:** Created a Calico custom resource with Kind-specific settings:
  ```yaml
  apiVersion: operator.tigera.io/v1
  kind: Installation
  metadata:
    name: default
  spec:
    calicoNetwork:
      ipPools:
      - cidr: 192.168.0.0/16
        encapsulation: VXLANCrossSubnet
      nodeAddressAutodetectionV4:
        kubernetes: NodeInternalIP
  ```
- **Outcome:** Calico fully operational on Kind cluster within 60 seconds of applying the custom resource.
- **Time Impact:** ~4 hours researching, testing, and resolving.
- **Prevention:** Documented the exact installation steps in `setup_k8s_platform.py` so it is automated for future clusters.

**Challenge 7: PostgreSQL PersistentVolumeClaim on Kind**

- **Problem:** The PostgreSQL deployment was stuck in `Pending` because the PVC could not be bound.
- **Root Cause:** Kind uses the `standard` StorageClass by default, which provisions `hostPath` volumes. The PVC needed to use this StorageClass explicitly.
- **Solution:** Set `storageClassName: standard` in the PVC:
  ```yaml
  apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: postgres-pvc
  spec:
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 5Gi
    storageClassName: standard
  ```
- **Outcome:** PVC bound immediately, PostgreSQL pod scheduled and running.
- **Time Impact:** ~1 hour debugging.

**Challenge 8: Schema Initialization in Kubernetes PostgreSQL**

- **Problem:** The PostgreSQL pod started but the schema was not applied — tables did not exist.
- **Root Cause:** Unlike Docker Compose (which mounts `init.sql` to `/docker-entrypoint-initdb.d/`), the Kubernetes deployment needed a different approach for schema initialization.
- **Solution:** Used a ConfigMap to mount the schema file and an `initContainer` to apply it:
  ```yaml
  # ConfigMap containing schema.sql
  # initContainer runs psql to apply schema before main container starts
  ```
  Alternatively, the setup script applies the schema via `kubectl exec`:
  ```python
  # In setup_k8s_platform.py:
  subprocess.run([
      "kubectl", "exec", "-n", "uvote-dev", pod_name, "--",
      "psql", "-U", "postgres", "-d", "voting_db", "-f", "/tmp/schema.sql"
  ])
  ```
- **Outcome:** Schema reliably applied during cluster setup.
- **Time Impact:** ~2 hours finding the right approach.

**Challenge 9: Per-Service Database User Testing**

- **Problem:** The test suite needed to verify that each database user had exactly the right permissions — not more, not less. Testing permission denials is harder than testing grants.
- **Root Cause:** PostgreSQL doesn't raise an error when you try to SELECT from a table you have permission to read — it just works. But trying to INSERT into a read-only table raises `InsufficientPrivilegeError`. The test suite needed to verify both positive and negative cases.
- **Solution:** Created a comprehensive permission matrix test:
  ```python
  # For each user, test:
  # 1. Tables they CAN read (SELECT) → should succeed
  # 2. Tables they CAN write (INSERT) → should succeed
  # 3. Tables they CANNOT read → should raise InsufficientPrivilegeError
  # 4. Tables they CANNOT write → should raise InsufficientPrivilegeError
  ```
  Used `pytest.raises(asyncpg.InsufficientPrivilegeError)` for denial tests.
- **Outcome:** Full permission matrix validated — 5 users × N tables × 4 operations = comprehensive coverage.
- **Time Impact:** ~3 hours writing and debugging the test suite.

### Technical Learnings

- **Learning 6:** Kind's `disableDefaultCNI: true` is essential for Calico — if the default kindnet is installed, Calico and kindnet conflict, causing pod networking failures.
- **Learning 7:** Kubernetes PersistentVolumeClaims on Kind require `storageClassName: standard` to match Kind's default provisioner.
- **Learning 8:** The `kubectl exec` approach for schema initialization is more reliable than initContainers for development clusters, because it allows re-running the schema without restarting the pod.
- **Learning 9:** asyncpg's `InsufficientPrivilegeError` is the specific exception for GRANT violations — catching generic `Exception` would mask other issues.

### Evidence

- **Commits:**
  - `d933c31` — Module requirements (Feb 10)
  - `ac11b5d` — Merge PR #1 (Feb 10)
  - `581d001` — Architecture docs and README rewrite (Feb 11)
  - `06c8951` — Kind platform configuration (Feb 11)
  - `b658c9a` — .gitignore (Feb 12)
  - `15df12b` — PostgreSQL on Kubernetes (Feb 12)
  - `e1f05c3` — Platform setup script (Feb 12)
  - `f5603a2` — Database test suite (Feb 12)
  - `d5fa9fd` — README update (Feb 13)
- **Files Created:** 14 new files, 6 files modified
- **Documentation Created:** ARCHITECTURE.MD (1,363 lines), PLATFORM.MD (559 lines)
- **Test Coverage:** 1,270-line database test suite

### Next Week Planning

- Implement network policies (zero-trust model)
- Create service deployment manifests for Kubernetes
- Complete application hardening (blind ballot tokens, vote encryption)
- Create deployment automation script
- Write investigation documentation (ADRs, Investigation Log)

### Time Spent

~45 hours (platform infrastructure, database deployment, testing, documentation, automation)

---

## Iteration 1 Retrospective: Foundation Sprint

**Dates:** January 27 — February 14, 2026
**Goal:** Working application + platform infrastructure

### Completed

- All 6 microservices implemented with core functionality
- Database schema designed and deployed (2 versions: Docker + K8s)
- Docker Compose local development working
- Kind cluster operational with Calico CNI
- PostgreSQL deployed on Kubernetes with per-service users
- Platform setup automation (641-line script)
- Database test suite (1,270 lines)
- Architecture documentation (1,363 lines)
- Platform documentation (559 lines)

### Partially Completed

- Network policy design started but not yet committed
- Service deployment manifests not yet created
- Application hardening (blind ballot tokens) designed but not coded

### Not Completed

- ADRs and Investigation Log (deferred to Week 4)
- Deployment automation script (deferred to Week 4)
- Network security documentation (deferred to Week 4)

### Velocity

- **Planned:** 8 major tasks
- **Actual:** 7 completed, 1 partially complete
- **Variance:** -12.5% (slightly behind due to Calico installation challenges)

### What Went Well

1. **Parallel workstreams** — Platform and application development progressed independently without blocking
2. **Automation first** — The setup script saved hours of repeated manual cluster creation
3. **Database test suite** — Caught several permission issues before they became production bugs
4. **Documentation-driven** — Writing ARCHITECTURE.MD before implementation clarified many design decisions

### What Could Improve

1. **Calico research** — Should have read the Kind-specific Calico guide before attempting installation
2. **Schema versioning** — Having two schema files (init.sql for Docker, schema.sql for K8s) creates a maintenance burden. Should consolidate.
3. **Time estimation** — Underestimated the Calico setup time by ~3 hours

### Action Items

- [ ] Consolidate schema files (address in Stage 2)
- [ ] Complete network policies
- [ ] Create service deployment manifests
- [ ] Implement blind ballot token protocol in application code
- [ ] Write all ADRs and Investigation Log

---

## Week 4 (Partial): Network Security & Service Deployment (Feb 15)

### Planned Goals

- Implement the complete zero-trust network policy set
- Validate network policies with systematic testing
- Create network security architecture documentation
- Begin service deployment manifest creation

### What Was Accomplished

**Day 1 — Saturday, Feb 15: Network Policies + Documentation**

```
b9ee9d5 - feat: add Kubernetes network policies implementing zero-trust security model
951b7c7 - docs: add network policy validation summaries and test results
e9222d3 - docs: add comprehensive network security architecture document
```

**Zero-Trust Network Policies — 12 Policies Across 5 Files:**

| File | Policies | Purpose |
|------|----------|---------|
| `00-default-deny.yaml` | 2 | Default deny all ingress + egress (zero-trust baseline) |
| `01-allow-dns.yaml` | 1 | Allow DNS resolution to kube-system (port 53 UDP/TCP) |
| `02-allow-to-database.yaml` | 2 | Database ingress (6 services → PostgreSQL:5432) + bidirectional egress |
| `03-allow-from-ingress.yaml` | 6 | Nginx Ingress → 6 exposed services (per-service policies) |
| `04-allow-audit.yaml` | 2 | Audit service ingress (6 services → audit:8005) + bidirectional egress |

**Total: 993 lines of YAML defining the complete network security model.**

The policy architecture follows a layered approach:

```
Layer 0: DEFAULT DENY ALL
  └── Nothing can communicate with anything

Layer 1: ALLOW DNS
  └── All pods can resolve DNS via kube-system:53

Layer 2: ALLOW DATABASE ACCESS
  └── 6 specific services can reach PostgreSQL:5432
  └── frontend-service and email-service are BLOCKED

Layer 3: ALLOW INGRESS CONTROLLER
  └── Nginx Ingress can reach 6 exposed service ports
  └── Internal services (audit) not exposed externally

Layer 4: ALLOW AUDIT SERVICE
  └── 6 services can send audit events to audit-service:8005
```

**Network Policy Validation Testing:**

Created 6 validation summary documents (926 lines total) in `network_summary/`:

| Summary | Lines | Tests |
|---------|-------|-------|
| `00-test-pods-summary.md` | 136 | Test pod deployment and methodology |
| `01-default-deny-summary.md` | 110 | Verified all traffic blocked by default |
| `02-allow-dns-summary.md` | 110 | Verified DNS resolution works |
| `03-database-access-summary.md` | 175 | Verified 6 services can access DB, 2 blocked |
| `04-ingress-access-summary.md` | 182 | Verified ingress routing to 6 services |
| `05-audit-service-summary.md` | 200 | Verified audit service accessibility |

Testing methodology:
1. Deploy diagnostic pods (test-pods.yaml) with `curl` and `nslookup` tools
2. Apply each policy layer incrementally
3. Test connectivity after each layer:
   ```bash
   # Test database access from auth-service pod:
   kubectl exec -n uvote-dev test-auth -- nc -zv postgres 5432
   # Expected: Connection succeeded

   # Test database access from frontend-service pod:
   kubectl exec -n uvote-dev test-frontend -- nc -zv postgres 5432
   # Expected: Connection timed out (BLOCKED)
   ```
4. Document results in summary files with pass/fail for each test

**Network Security Architecture Document:**

Created `NETWORK-SECURITY.md` (828 lines):

```
Contents:
§1  Introduction and Zero-Trust Rationale
§2  Policy Architecture Overview
§3  Default Deny Specification
§4  DNS Resolution Policy
§5  Database Access Policy
§6  Ingress Controller Policy
§7  Audit Service Policy
§8  Service Communication Matrix
§9  Threat Mitigation Analysis
§10 Defence-in-Depth Model
§11 Operational Troubleshooting Guide
§12 Testing Methodology and Results
```

The service communication matrix documented every allowed connection:

```
FROM → TO               │ Allowed? │ Port  │ Policy
────────────────────────┼──────────┼───────┼──────────────────
auth-service → postgres │ YES      │ 5432  │ 02-allow-to-database
frontend → postgres     │ NO       │ —     │ (blocked by default-deny)
voting-svc → auth-svc   │ YES      │ 5001  │ (via ingress internal)
results-svc → postgres  │ YES      │ 5432  │ 02-allow-to-database
any pod → external      │ NO       │ —     │ (blocked by default-deny)
```

### Challenges Encountered

**Challenge 10: Bidirectional Network Policy Requirement**

- **Problem:** After applying the database ingress policy, services still could not connect to PostgreSQL. Connections timed out despite the ingress rule being correct.
- **Root Cause:** In a default-deny architecture, BOTH the sender's egress AND the receiver's ingress must be explicitly allowed. The initial implementation only had ingress on PostgreSQL, but the sending service's egress was still blocked by default-deny.
- **Investigation:**
  1. Initial hypothesis: Ingress policy label selector was wrong → Verified correct with `kubectl get netpol -o yaml`
  2. Tested with `kubectl exec` from diagnostic pod → Connection timed out
  3. Research: Read Kubernetes NetworkPolicy documentation → "If no egress policies apply to a pod, all egress traffic is allowed. If any egress policy applies (including default-deny), only explicitly allowed egress is permitted."
  4. Realisation: The default-deny egress policy blocks all outgoing traffic. Services need egress rules to reach PostgreSQL.
- **Solution:** Added bidirectional policies — each service that needs database access has BOTH:
  ```yaml
  # Ingress on PostgreSQL: allow from auth-service
  - from:
    - podSelector:
        matchLabels:
          app: auth-service
    ports:
    - port: 5432

  # Egress on auth-service: allow to PostgreSQL
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - port: 5432
  ```
- **Outcome:** Bidirectional policies working correctly. Documented as the key lesson learned in NETWORK-SECURITY.md §10.2.
- **Time Impact:** ~5 hours debugging and rewriting all policies. This was the single most time-consuming challenge in Stage 1.
- **Prevention:** Always create egress + ingress policies together. Documented this pattern in the operational guide.

**Challenge 11: DNS Resolution After Default Deny**

- **Problem:** After applying default-deny, pods could not resolve service names (`postgres`, `auth-service`, etc.) — all DNS lookups failed.
- **Root Cause:** Default-deny blocks ALL traffic, including DNS queries to `kube-dns` in the `kube-system` namespace. Without DNS, pods cannot resolve Kubernetes Service names to ClusterIP addresses.
- **Solution:** Created `01-allow-dns.yaml` as the first policy after default-deny:
  ```yaml
  # Allow all pods to query kube-dns
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  ```
- **Outcome:** DNS resolution restored for all pods in the namespace.
- **Time Impact:** ~1 hour. Faster to resolve because the bidirectional lesson (Challenge 10) was already learned.

**Challenge 12: Ingress Controller Network Path**

- **Problem:** The Nginx Ingress Controller (running in `ingress-nginx` namespace) could not reach services in `uvote-dev` namespace after default-deny was applied.
- **Root Cause:** Default-deny blocks ingress from all sources, including the ingress controller in a different namespace. A cross-namespace policy was needed.
- **Solution:** Created per-service ingress policies with namespace selectors:
  ```yaml
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - port: 5000  # frontend-service
  ```
  Each service has its own ingress policy allowing only from the `ingress-nginx` namespace on its specific port.
- **Outcome:** Ingress routing working through network policies.
- **Time Impact:** ~2 hours designing and testing cross-namespace policies.

### Technical Learnings

- **Learning 10:** In Kubernetes NetworkPolicies, default-deny means ABSOLUTELY NOTHING works — not even DNS. The first policy after default-deny must always be DNS resolution.
- **Learning 11:** Bidirectional enforcement is the most critical concept in zero-trust networking. Every connection requires TWO policies: sender egress + receiver ingress.
- **Learning 12:** Cross-namespace policies use `namespaceSelector` instead of `podSelector`. The namespace must be labeled for selection to work (`kubernetes.io/metadata.name` is auto-applied by Kubernetes).
- **Learning 13:** Incremental policy testing is essential — apply one policy at a time and test before proceeding. Applying all policies at once makes debugging impossible.

### Evidence

- **Commits:**
  - `b9ee9d5` — Network policies (6 files, 993 insertions) (Feb 15)
  - `951b7c7` — Validation summaries (7 files, 926 insertions) (Feb 15)
  - `e9222d3` — Network security document (828 lines) (Feb 15)
- **Files Created:** 13 new files (6 policies + 7 summaries + 1 document)
- **Testing:** 6 validation summaries documenting systematic policy testing

### Time Spent

~14 hours (network policy design, implementation, testing, documentation)

---

## Week 4 (Continued): Service Integration & Application Hardening (Feb 16)

### Planned Goals

- Create Kubernetes deployment manifests for all 6 services
- Complete application hardening (blind ballot tokens, vote encryption)
- Create deployment automation script
- Merge Stage 1 application changes
- Write all ADRs and Investigation Log
- Update platform documentation

### What Was Accomplished

**Day 2 — Monday, Feb 16: Full Integration Day**

```
21a0ca6 - Merge pull request #2 from D00256764/dev
e07ead5 - stage1
4256cbd - depl: created deployment manifests for stage 1 mvp services
0a92041 - depl: created basic deployment script for deploying the manifests
71def1e - doc: updated platform document with more comprehensive details
29a9945 - docs: compiled and composed research and decision logs
```

This was the most productive single day of the project — 6 commits covering application hardening, Kubernetes deployment, automation, and comprehensive documentation.

**Application Hardening — PR #2 (Stage 1):**

The `stage1` commit (`e07ead5`) represented a major evolution of the application code:

| File | Before | After | Change |
|------|--------|-------|--------|
| auth-service/app.py | 136 lines | 432 lines | +296 lines (blind ballot tokens, MFA) |
| voting-service/app.py | 231 lines | 572 lines | +341 lines (encrypted ballots, receipts) |
| results-service/app.py | 267 lines | 541 lines | +274 lines (decryption, tallying) |
| voter-service/app.py | 246 lines | 679 lines | +433 lines (CSV upload, token generation) |
| frontend-service/app.py | 452 lines | 589 lines | +137 lines (election delegation) |
| election-service/app.py | NEW | 418 lines | New service (election CRUD) |
| database/init.sql | 105 lines | 296 lines | +191 lines (new tables, triggers) |
| shared/security.py | 46 lines | 114 lines | +68 lines (blind tokens, encryption) |
| shared/database.py | 59 lines | 99 lines | +40 lines (transaction support) |
| shared/schemas.py | NEW | 193 lines | New (Pydantic validation models) |
| shared/email_util.py | NEW | 159 lines | New (email utilities) |

**Key security features added in Stage 1 hardening:**

1. **Blind Ballot Token Protocol:**
   ```python
   # In auth-service/app.py — The Anonymity Bridge:
   # Step 1: Mark voter as having voted (accountability)
   await conn.execute("UPDATE voters SET has_voted = TRUE WHERE id = $1", voter_id)

   # Step 2: Mark voting token as used
   await conn.execute("UPDATE voting_tokens SET is_used = TRUE WHERE id = $1", token_id)

   # Step 3: Generate blind ballot token (NO voter_id stored)
   ballot_token = generate_blind_ballot_token()  # secrets.token_urlsafe(32)
   await conn.execute(
       "INSERT INTO blind_tokens (ballot_token, election_id) VALUES ($1, $2)",
       ballot_token, election_id
   )
   # NO INSERT linking voter_id to ballot_token — the link is permanently severed
   ```

2. **Vote Encryption:**
   ```python
   # In voting-service/app.py:
   await conn.execute("""
       INSERT INTO encrypted_ballots (election_id, encrypted_vote, ballot_hash,
                                       previous_hash, receipt_token)
       VALUES ($1, pgp_sym_encrypt($2::text, $3), $4, $5, $6)
   """, election_id, vote_choice, encryption_key, ballot_hash,
        previous_hash, receipt_token)
   ```

3. **Receipt Token Verification:**
   ```python
   # Voters can verify their ballot was recorded:
   GET /receipt/{receipt_token}
   # Returns: ballot_hash, cast_at (but NOT the vote choice)
   ```

4. **Enhanced Database Schema:**
   ```sql
   -- New tables added:
   CREATE TABLE organisations (...)     -- Multi-tenancy support
   CREATE TABLE organisers (...)        -- Renamed from admins
   CREATE TABLE voter_mfa (...)         -- DOB verification records
   CREATE TABLE blind_tokens (...)      -- NO voter_id column
   CREATE TABLE election_options (...)  -- Renamed from candidates
   CREATE TABLE encrypted_ballots (...) -- NO voter_id, encrypted votes
   CREATE TABLE vote_receipts (...)     -- Voter verification tokens
   CREATE TABLE tallied_votes (...)     -- Cached results

   -- Immutability triggers:
   CREATE TRIGGER prevent_ballot_modification
       BEFORE UPDATE OR DELETE ON encrypted_ballots
       FOR EACH ROW EXECUTE FUNCTION prevent_modification();

   CREATE TRIGGER prevent_audit_modification
       BEFORE UPDATE OR DELETE ON audit_log
       FOR EACH ROW EXECUTE FUNCTION prevent_modification();

   -- Hash chain auto-generation:
   CREATE TRIGGER auto_hash_ballot
       BEFORE INSERT ON encrypted_ballots
       FOR EACH ROW EXECUTE FUNCTION generate_ballot_hash();
   ```

**Service Deployment Manifests:**

Created Kubernetes deployment manifests for all 6 services (`uvote-platform/k8s/services/`):

| Manifest | Lines | Service | Port | Replicas |
|----------|-------|---------|------|----------|
| `frontend-deployment.yaml` | 113 | frontend-service | 5000 | 2 |
| `auth-deployment.yaml` | 131 | auth-service | 5001 | 2 |
| `voting-deployment.yaml` | 123 | voting-service | 5003 | 2 |
| `results-deployment.yaml` | 131 | results-service | 5004 | 2 |
| `election-deployment.yaml` | 131 | election-service | 5005 | 2 |
| `admin-deployment.yaml` | 135 | admin-service | 8006 | 2 |

Each manifest included:
- Deployment with 2 replicas (high availability)
- Resource requests and limits (CPU: 100m–500m, Memory: 128Mi–512Mi)
- Liveness and readiness probes (`/health` endpoint)
- Environment variables from Kubernetes Secrets
- Service (ClusterIP) for internal discovery
- Labels for NetworkPolicy targeting (`app: <service-name>`)

**Deployment Automation Script:**

Created `plat_scripts/deploy_platform.py` (1,030 lines):

```python
# Automated deployment steps:
# 1. Build Docker images for all 6 services
# 2. Load images into Kind cluster (kind load docker-image)
# 3. Create/update Kubernetes Secrets with database credentials
# 4. Apply service deployment manifests
# 5. Wait for all deployments to become ready
# 6. Verify service health endpoints
# 7. Run smoke tests
# 8. Report deployment status
```

Features:
- Parallel image building for faster deployment
- Automatic secret generation with `secrets.token_urlsafe(32)` for database passwords
- Rolling update support (zero-downtime deployments)
- Health check verification after deployment
- Colour-coded terminal output

**Platform Documentation Update:**

Updated `PLATFORM.MD` from 559 lines to 3,270 lines (+2,711 lines):

The comprehensive update covered:
- Complete deployment architecture
- Service deployment details (all 6 services)
- Network policy specification
- Secret management procedures
- Database deployment and schema management
- Troubleshooting guide for common issues
- Monitoring and observability (kubectl commands)
- Capacity planning and resource allocation

**Research Documentation:**

Created the complete investigation and decision documentation:

| File | Lines | Content |
|------|-------|---------|
| `INVESTIGATION-LOG.md` | 2,027 | Comprehensive research and decision process |
| `ADR-001` through `ADR-015` | 4,065 | 15 Architecture Decision Records |
| `ADR-INDEX.md` | 64 | Decision record index |

Total documentation output: **6,156 lines** covering all technology selections, architecture decisions, trade-offs, and rationale.

### Challenges Encountered

**Challenge 13: Service-to-Service Communication in Kubernetes**

- **Problem:** In Docker Compose, services communicate via container names (`http://auth-service:5001`). In Kubernetes, the addressing is different — services use Kubernetes Service DNS names.
- **Root Cause:** Kubernetes Services create DNS records in the format `<service-name>.<namespace>.svc.cluster.local`, not just the container name.
- **Solution:** Environment variables in deployment manifests point to Kubernetes Service names:
  ```yaml
  env:
  - name: AUTH_SERVICE_URL
    value: "http://auth-service.uvote-dev.svc.cluster.local:5001"
  ```
  Within the same namespace, short names also work: `http://auth-service:5001`
- **Outcome:** Inter-service communication working in both Docker Compose and Kubernetes.
- **Time Impact:** ~1 hour adjusting environment variables.

**Challenge 14: Docker Image Loading into Kind**

- **Problem:** After building Docker images locally, `kubectl apply` could not pull them because Kind nodes use their own container runtime, not the host Docker daemon.
- **Root Cause:** Kind nodes run containerd, not Docker. Locally built Docker images are not visible to Kind's containerd.
- **Solution:** Used `kind load docker-image` to copy images from host Docker to Kind nodes:
  ```bash
  kind load docker-image auth-service:latest --name uvote
  kind load docker-image voting-service:latest --name uvote
  # ... for each service
  ```
  Also set `imagePullPolicy: Never` in deployment manifests to prevent Kubernetes from trying to pull from a registry.
- **Outcome:** Local images available in Kind cluster. Automated in `deploy_platform.py`.
- **Time Impact:** ~30 minutes once the `kind load` command was discovered.

**Challenge 15: Deployment Manifest Resource Limits**

- **Problem:** Initial deployment manifests had no resource limits, causing pods to consume unlimited resources and potentially starving the Kind node.
- **Root Cause:** Without resource limits, Kubernetes allows pods to consume all available CPU and memory on the node.
- **Solution:** Added resource requests and limits to all manifests:
  ```yaml
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"
  ```
  These limits were tuned based on observed resource usage during Docker Compose testing.
- **Outcome:** All services run within defined resource boundaries. Total cluster resource usage: ~3GB RAM for all services.
- **Time Impact:** ~1 hour to profile and set appropriate limits.

### Technical Learnings

- **Learning 14:** `kind load docker-image` is essential for local development — it bridges the gap between host Docker and Kind's containerd.
- **Learning 15:** `imagePullPolicy: Never` prevents Kubernetes from attempting to pull images from a registry that doesn't exist. Combined with `kind load`, this creates a fully offline development workflow.
- **Learning 16:** Kubernetes resource limits should always be set, even in development. Without them, a single misbehaving service can starve the entire cluster.

### Evidence

- **Commits:**
  - `21a0ca6` — Merge PR #2 (Feb 16)
  - `e07ead5` — Stage 1 application hardening (50 files, 3,473 insertions)
  - `4256cbd` — Service deployment manifests (5 files, 641 insertions)
  - `0a92041` — Deployment automation script (3 files, 1,155 insertions)
  - `71def1e` — Platform documentation update (2,883 insertions)
  - `29a9945` — ADRs and Investigation Log (17 files, 6,129 insertions)
- **Files Created:** 28 new files, 50 files modified
- **Pull Request:** PR #2 — Stage 1 application hardening

### Time Spent

~16 hours (deployment manifests, automation, application hardening, documentation)

---

## Iteration 2 Retrospective: Security & Deployment Sprint

**Dates:** February 15 — February 16, 2026
**Goal:** Security hardening + deployment automation + documentation

### Completed

- 12 network policies implemented and tested (zero-trust model)
- 6 network policy validation summaries
- Network security architecture document (828 lines)
- 6 service deployment manifests for Kubernetes
- Deployment automation script (1,030 lines)
- Application hardening: blind ballot tokens, vote encryption, hash chains
- Platform documentation comprehensive update (+2,711 lines)
- 15 ADRs + Investigation Log (6,156 lines total)
- PR #2 merged: Stage 1 application changes

### Partially Completed

- Email service integration (SMTP not configured in K8s)
- Admin service full functionality (basic CRUD only)

### Not Completed

- CI/CD pipeline (deferred to Stage 2)
- Automated integration tests for service-to-service communication
- Production deployment (AKS/EKS — Stage 2)
- Row-Level Security in PostgreSQL (Stage 2 consideration)

### Velocity

- **Planned:** 6 major tasks
- **Actual:** 6 completed
- **Variance:** 0% (on target)

### What Went Well

1. **Bidirectional policy lesson** — Once the bidirectional requirement was understood, all subsequent policies were implemented correctly first time
2. **Deployment script** — Automated the entire build-load-deploy cycle, saving 20+ minutes per deployment
3. **Documentation blitz** — Writing 6,000+ lines of documentation in one day was intense but produced comprehensive, coherent results
4. **Application hardening** — The blind ballot token protocol implemented cleanly because the database schema was designed for it from the start

### What Could Improve

1. **Network policy testing should happen earlier** — The bidirectional issue could have been caught during Week 3 if policies were tested incrementally during implementation
2. **Documentation should not be left to the last day** — While the output was comprehensive, writing under time pressure increases the risk of inconsistencies
3. **Deployment manifests should be created alongside the platform** — Creating them as an afterthought meant repeating configuration work

### Action Items

- [ ] Set up CI/CD pipeline (Stage 2 priority)
- [ ] Configure email service SMTP in Kubernetes
- [ ] Add integration tests for service-to-service communication
- [ ] Implement Row-Level Security evaluation
- [ ] Add monitoring (Prometheus/Grafana)

---

## Stage 1 Research & Decision Documentation

### Architecture Decision Records

15 ADRs were created documenting every major technology and architecture decision:

| ADR | Title | Date | Options Evaluated |
|-----|-------|------|-------------------|
| [ADR-001](decisions/ADR-001-python-fastapi-backend.md) | Python FastAPI Backend | Feb 10 | FastAPI, Django, Flask, Express.js |
| [ADR-002](decisions/ADR-002-postgresql-database.md) | PostgreSQL Database | Feb 10 | PostgreSQL, MySQL, MongoDB, SQLite |
| [ADR-003](decisions/ADR-003-kubernetes-platform.md) | Kubernetes Platform | Feb 10 | Kubernetes, Docker Swarm, Docker Compose, Nomad |
| [ADR-004](decisions/ADR-004-calico-networking.md) | Calico CNI | Feb 11 | Calico, Cilium, Flannel, Weave Net |
| [ADR-005](decisions/ADR-005-token-based-voting.md) | Token-Based Voting | Feb 11 | Tokens, Passwords, OAuth 2.0, OTP |
| [ADR-006](decisions/ADR-006-jwt-authentication.md) | JWT Authentication | Feb 11 | JWT, Session-based, OAuth 2.0, API Keys |
| [ADR-007](decisions/ADR-007-hash-chain-audit.md) | Hash-Chain Audit | Feb 12 | Hash chains, Simple logging, Blockchain, Third-party |
| [ADR-008](decisions/ADR-008-microservices-architecture.md) | Microservices | Feb 12 | Microservices, Monolith, Serverless, Modular Monolith |
| [ADR-009](decisions/ADR-009-server-side-rendering.md) | Server-Side Rendering | Feb 13 | Jinja2 SSR, React SPA, Vue.js SPA, Static + API |
| [ADR-010](decisions/ADR-010-network-policy-zero-trust.md) | Zero-Trust Networking | Feb 13 | Zero-trust, Default-allow, Perimeter-only, Istio |
| [ADR-011](decisions/ADR-011-kubernetes-secrets.md) | Kubernetes Secrets | Feb 14 | K8s Secrets, HashiCorp Vault, .env files, AWS Secrets |
| [ADR-012](decisions/ADR-012-kind-local-development.md) | Kind Local Dev | Feb 14 | Kind, Minikube, K3s, Docker Desktop K8s |
| [ADR-013](decisions/ADR-013-service-separation-strategy.md) | Service Separation | Feb 14 | Domain-driven, Technical layer, User role |
| [ADR-014](decisions/ADR-014-database-per-service-users.md) | Per-Service DB Users | Feb 15 | Per-service users, Shared credentials, Separate databases |
| [ADR-015](decisions/ADR-015-vote-anonymity-design.md) | Vote Anonymity | Feb 16 | Blind tokens, Voter-linked, Homomorphic, Mixnets |

### Investigation Log

The `INVESTIGATION-LOG.md` (2,027 lines) documented the complete research process:

```
§1  Executive Summary
§2  Requirements Analysis (user, technical, constraints)
§3  Technology Investigation
    §3.1  Backend Framework
    §3.2  Database Selection
    §3.3  Container Orchestration
    §3.4  CNI Plugin
    §3.5  Frontend Approach
    §3.6  Authentication
    §3.7  Audit Logging
    §3.8  CI/CD (planned)
§4  Architecture Pattern Investigation
§5  Security Approach Investigation
§6  Prototyping Process (4 iterations)
§7  Risk Analysis
§8  Trade-offs (15 documented)
§9  Appendices (methodology, timeline, references)
```

---

# 4. Cumulative Metrics

## Development Statistics

### Commit History

```
Total Commits: 20
Commits by Author:
    15  Luke Doyle    (platform, documentation, automation)
     3  D00256764     (merge commits)
     2  Hafsa         (application code)

Commits by Date:
    2026-02-08  │ █                          1 commit
    2026-02-09  │                            0 commits
    2026-02-10  │ ███                        3 commits
    2026-02-11  │ ██                         2 commits
    2026-02-12  │ ████                       4 commits
    2026-02-13  │ █                          1 commit
    2026-02-14  │                            0 commits
    2026-02-15  │ ███                        3 commits
    2026-02-16  │ ██████                     6 commits
```

### Lines of Code

```
Language Breakdown:
────────────────────────────────────────────
Python          │ ████████████████████████  5,563 lines
  Services      │ ██████████               2,263 lines
  Shared        │ ██                         520 lines
  Scripts       │ ████████████             2,780 lines

YAML            │ ████████                 2,060 lines
  K8s Manifests │ ███████                  1,899 lines
  Docker Comp.  │ █                          161 lines

SQL             │ ██                         463 lines
  init.sql      │ █                          269 lines
  schema.sql    │ █                          194 lines

Markdown        │ ████████████████████████  8,291 lines
  ADRs          │ ████████████████         4,065 lines
  INVESTIGATION │ ████████                 2,027 lines
  PLATFORM.MD   │ ████████████             3,270 lines (included in total)
  Other docs    │ ████                     ~2,000 lines

HTML Templates  │ █████                    1,222 lines

CSS             │ █                          218 lines

Dockerfiles     │                            106 lines
────────────────────────────────────────────
TOTAL           │                         17,923 lines
```

### File Statistics

```
Total Project Files: 101

By Category:
  Python source (.py):     13 files
  YAML manifests (.yaml):  16 files
  SQL schemas (.sql):       2 files
  Markdown docs (.md):     25 files
  HTML templates (.html):  19 files
  CSS stylesheets (.css):   5 files
  Dockerfiles:              6 files
  Config files:            15 files (requirements.txt, .gitignore, etc.)
```

### Git Statistics

```
Total Insertions:  ~22,000 lines
Total Deletions:   ~2,700 lines
Net Lines Added:   ~19,300 lines

Largest Commits (by insertions):
  1. 29a9945  ADRs + Investigation Log     6,129 insertions
  2. c723de7  Base code                    3,506 insertions
  3. e07ead5  Stage 1 hardening            3,473 insertions
  4. 71def1e  Platform doc update          2,883 insertions
  5. f5603a2  Database test suite          1,270 insertions
  6. 581d001  Architecture docs            2,183 insertions
  7. 0a92041  Deploy script + manifest     1,155 insertions
  8. b9ee9d5  Network policies               993 insertions
  9. 951b7c7  Network summaries              926 insertions
 10. e9222d3  Network security doc           828 insertions
```

## Time Tracking

```
Total Project Hours (Stage 1): ~130 hours

Breakdown by Activity:
────────────────────────────────────────────
Research & Planning      │ ████████         25 hours (19%)
  Technology research    │ ███               10 hours
  Architecture design    │ ████              10 hours
  Project planning       │ ██                 5 hours

Implementation           │ ████████████████ 45 hours (35%)
  Application services   │ ██████████       20 hours
  Platform infrastructure│ ████████         15 hours
  Automation scripts     │ █████            10 hours

Testing                  │ ████████         15 hours (12%)
  Database testing       │ ████              8 hours
  Network policy testing │ ████              7 hours

Documentation            │ ████████████     30 hours (23%)
  ADRs                   │ ██████           12 hours
  Investigation Log      │ ████              8 hours
  Platform/Architecture  │ █████            10 hours

Debugging                │ ████             12 hours (9%)
  Calico installation    │ ██                4 hours
  Network policies       │ ██                5 hours
  Database issues        │ █                 3 hours

Environment Setup        │ █                 3 hours (2%)
────────────────────────────────────────────
```

```
Breakdown by Week:
────────────────────────────────────────────
Week 1 (Jan 27 - Jan 31) │ ████            20 hours
Week 2 (Feb 3 - Feb 7)   │ ████████████    35 hours
Week 3 (Feb 10 - Feb 14) │ ████████████████ 45 hours
Week 4 (Feb 15 - Feb 16) │ ████████████    30 hours
────────────────────────────────────────────
```

## Issue/Bug Tracking

```
Total Issues Encountered: 15

By Severity:
  Critical (blocking):    3  (Calico install, bidirectional policies, DB connection race)
  Major (significant):    5  (DNS after deny, schema init, JWT flow, image loading, resources)
  Minor (workaround):     5  (CSS styling, template paths, port conflicts)
  Cosmetic:               2  (log formatting, error messages)

All 15 resolved during Stage 1.

Resolution Time:
  < 1 hour:    7 issues
  1-3 hours:   5 issues
  3-5 hours:   3 issues
  > 5 hours:   0 issues
```

---

# 5. Technical Debt Log

## Debt Accumulated

### TD-001: Dual Database Schemas

- **What:** Two schema files exist — `database/init.sql` (Docker Compose) and `uvote-platform/k8s/database/schema.sql` (Kubernetes). They define similar but not identical tables.
- **Why:** Docker Compose and Kubernetes have different schema initialization mechanisms. The K8s schema includes per-service users that don't exist in the Docker Compose version.
- **Impact:** Changes to the schema must be made in two places. Risk of drift between environments.
- **Remediation Plan:** Consolidate into a single schema file with conditional user creation. Use the same file for both Docker Compose (mounted volume) and Kubernetes (ConfigMap). Target: Stage 2, Week 1.

### TD-002: Hardcoded Service URLs

- **What:** Inter-service URLs are partially hardcoded in application code and partially configured via environment variables.
- **Why:** Time pressure during the restart meant some shortcuts were taken in service discovery.
- **Impact:** Changing a service port or name requires updating multiple files.
- **Remediation Plan:** Move all service URLs to environment variables, configured in Docker Compose and K8s manifests. Target: Stage 2, Week 1.

### TD-003: No Automated Integration Tests

- **What:** The database test suite validates schema and permissions, but there are no integration tests for the complete voting flow (token → identity → ballot → vote → receipt).
- **Why:** Priority was given to infrastructure and security testing over end-to-end application testing.
- **Impact:** Regressions in the voting flow could go undetected until manual testing.
- **Remediation Plan:** Create a `test_voting_flow.py` integration test that exercises the complete path. Target: Stage 2, Week 2.

### TD-004: No CI/CD Pipeline

- **What:** No automated build, test, or deployment pipeline exists. All builds and deployments are manual (via scripts).
- **Why:** CI/CD was deprioritised in favour of core functionality and security for Stage 1.
- **Impact:** Manual processes are error-prone and slow.
- **Remediation Plan:** Set up GitHub Actions with build, test, and deployment stages. Target: Stage 2, Week 3.

### TD-005: Email Service Not Integrated in K8s

- **What:** The `shared/email_util.py` exists but SMTP is not configured in the Kubernetes environment. Voting token emails cannot be sent from K8s-deployed services.
- **Why:** Email requires external SMTP credentials that were not available during Stage 1.
- **Impact:** Voters cannot receive voting tokens via email in the K8s environment. Docker Compose can be configured manually.
- **Remediation Plan:** Configure SMTP via Kubernetes Secrets. Consider using a mock SMTP server (Mailhog) for development. Target: Stage 2, Week 2.

### TD-006: No HTTPS/TLS Configuration

- **What:** All services communicate over unencrypted HTTP within the cluster.
- **Why:** TLS requires certificate management (cert-manager, Let's Encrypt) which was deferred.
- **Impact:** In-cluster traffic is unencrypted. Not a significant risk in a local Kind cluster, but required for production.
- **Remediation Plan:** Install cert-manager and configure TLS on the Ingress controller. Consider mTLS via service mesh for inter-service encryption. Target: Stage 2, Week 4.

### TD-007: Frontend Session Security

- **What:** The frontend-service uses FastAPI's `SessionMiddleware` with a hardcoded secret key in the Docker Compose environment.
- **Why:** Quick setup for local development.
- **Impact:** Sessions could be forged if the secret is known. Not a risk in local development but critical for production.
- **Remediation Plan:** Move session secret to Kubernetes Secrets. Rotate on deployment. Target: Stage 2, Week 1.

## Debt Repaid

### TD-R01: Database Health Check (Repaid Week 2)

- **What:** Services crashed on startup due to database connection race condition.
- **Repaid:** Added Docker Compose health checks and `condition: service_healthy`.
- **Prioritised Because:** Blocking all development — services couldn't start.

### TD-R02: Image Pull Policy (Repaid Week 4)

- **What:** Kubernetes tried to pull images from a non-existent registry.
- **Repaid:** Set `imagePullPolicy: Never` and automated `kind load` in the deployment script.
- **Prioritised Because:** Blocking all Kubernetes deployment testing.

---

# 6. Learning Journey

## Technologies Learned

### Kubernetes

**Before Project:** Theoretical understanding from the Cloud Native Technologies module. Had deployed simple pods and services but never built a multi-service platform with custom CNI, network policies, or per-service database access.

**What I Learned:**
- **Cluster management with Kind:** Creating, configuring, and tearing down clusters rapidly. Understanding the Docker-in-Docker architecture that Kind uses.
- **Custom CNI installation:** Disabling the default CNI, installing Calico operator, configuring custom resources for Kind's networking model.
- **NetworkPolicies:** The zero-trust model, bidirectional enforcement, cross-namespace policies, label-based selectors. This was the deepest learning area — understanding that default-deny means absolutely nothing works, including DNS.
- **Persistent storage:** PersistentVolumeClaims, StorageClasses, and how Kind handles storage differently from cloud providers.
- **Resource management:** CPU/memory requests and limits, how the scheduler uses requests for placement decisions, and how limits enforce ceilings.
- **Service discovery:** Kubernetes DNS naming conventions, ClusterIP services, and how pods resolve service names.

**Key Insight:** Kubernetes is not just an orchestrator — it's a platform for enforcing security policies at the infrastructure level. Network policies, RBAC, resource limits, and secrets management are as important as pod scheduling.

### Calico CNI

**Before Project:** No experience. Knew that Kubernetes supported CNI plugins but had not installed or configured one.

**What I Learned:**
- **Operator-based installation:** Calico uses a Kubernetes operator pattern. Install the operator, then create a custom resource (`Installation`) to configure it.
- **Kind-specific configuration:** Calico on Kind needs `VXLANCrossSubnet` encapsulation and `NodeInternalIP` address autodetection because Kind nodes are Docker containers with unusual networking.
- **NetworkPolicy enforcement:** Calico translates Kubernetes NetworkPolicy resources into iptables rules on each node. Understanding this helped debug policy issues.
- **calicoctl:** The Calico CLI for advanced troubleshooting — `calicoctl get ippools`, `calicoctl node status`, etc.

**Key Insight:** The CNI plugin is the enforcement layer for network policies. Without Calico (or equivalent), NetworkPolicy resources are just YAML — they do nothing. The default kindnet CNI silently ignores all network policies.

### FastAPI

**Before Project:** Basic understanding from web development modules. Had built simple REST APIs but not async microservices.

**What I Learned:**
- **Async patterns:** `async def` endpoints with `await` for database queries. Non-blocking I/O keeps the event loop responsive under concurrent requests.
- **Dependency injection:** FastAPI's `Depends()` pattern for shared resources (database pools, authentication).
- **Pydantic v2 integration:** Request validation, response serialization, and model_validate for database rows.
- **Session middleware:** Server-side session management for the admin dashboard.
- **Inter-service communication:** Using `httpx.AsyncClient` for async HTTP calls between services.

**Key Insight:** FastAPI's automatic OpenAPI documentation (`/docs`) is not just a convenience — it's a development accelerator. Being able to test every endpoint through Swagger UI eliminates the need for Postman or curl during development.

### PostgreSQL Advanced Features

**Before Project:** Basic SQL skills. CREATE TABLE, SELECT, INSERT, JOINs. No experience with extensions, triggers, or role-based access control.

**What I Learned:**
- **pgcrypto extension:** `pgp_sym_encrypt` and `pgp_sym_decrypt` for symmetric encryption. Understanding that encryption happens at the SQL level, not the application level.
- **Triggers:** BEFORE INSERT triggers for auto-generating hash chains. BEFORE UPDATE/DELETE triggers for immutability enforcement. Understanding the trigger execution model (statement-level vs row-level).
- **User roles and GRANT:** Creating per-service PostgreSQL users with specific table-level permissions. Understanding the GRANT/REVOKE model.
- **Hash functions:** `encode(digest(..., 'sha256'), 'hex')` for SHA-256 hashing in PostgreSQL.

**Key Insight:** PostgreSQL's trigger system can enforce security invariants (immutability, hash chains) at the database level, independent of application code. Even if the application has a bug, the database triggers prevent violations.

### Docker & Docker Compose

**Before Project:** Moderate experience. Had built Dockerfiles and used Docker Compose for simple applications.

**What I Learned:**
- **Multi-service orchestration:** Coordinating 7 containers with health checks, environment variables, and dependency ordering.
- **Build context management:** Setting the build context to the project root to share code across service images.
- **Kind integration:** `kind load docker-image` for loading local images into Kind nodes. Understanding the containerd vs Docker runtime distinction.

## Skills Developed

### DevOps Practices

- **Infrastructure as Code:** All Kubernetes manifests are declarative YAML in version control. The entire platform can be recreated from scratch by running two scripts.
- **Automation:** Two automation scripts (setup + deploy) reduce manual effort from ~30 minutes to ~3 minutes for a full cluster rebuild.
- **Environment parity:** Docker Compose and Kubernetes deployments use the same application code and Docker images, ensuring development/production parity.

### Security Hardening

- **Zero-trust networking:** Designing and implementing a default-deny network model with explicit allow rules. Understanding that security requires denying everything and selectively permitting.
- **Least-privilege database access:** Designing per-service database roles that enforce domain boundaries at the data layer.
- **Cryptographic design:** Implementing the blind ballot token protocol, understanding the separation between identity verification and anonymous ballot casting.
- **Defence in depth:** Layering security controls (network → database → application → data encryption) so that no single failure compromises the system.

### Troubleshooting

- **Kubernetes debugging:** `kubectl describe`, `kubectl logs`, `kubectl exec`, and `kubectl get events` for diagnosing pod and service issues.
- **Network policy debugging:** Using diagnostic pods with `nc` (netcat) and `nslookup` to test connectivity through network policies.
- **Database debugging:** `psql` for direct database access, checking GRANT permissions, testing triggers manually.

## Resources Used

### Documentation

| Resource | Used For |
|----------|----------|
| [Kubernetes Official Docs](https://kubernetes.io/docs/) | NetworkPolicy, Deployments, Services, PVC |
| [Calico Docs](https://docs.tigera.io/calico/) | Installation, Kind guide, policy reference |
| [Kind Docs](https://kind.sigs.k8s.io/) | Cluster configuration, image loading |
| [FastAPI Docs](https://fastapi.tiangolo.com/) | Async patterns, middleware, dependencies |
| [PostgreSQL 15 Docs](https://www.postgresql.org/docs/15/) | pgcrypto, triggers, GRANT, functions |
| [asyncpg Docs](https://magicstack.github.io/asyncpg/) | Connection pools, transactions, error handling |
| [Python secrets module](https://docs.python.org/3/library/secrets.html) | CSPRNG for token generation |
| [NIST SP 800-207](https://csrc.nist.gov/publications/detail/sp/800-207/final) | Zero-trust architecture principles |

### Key Research Papers

| Paper | Relevance |
|-------|-----------|
| Chaum, D. (1983) "Blind Signatures for Untraceable Payments" | Foundation for blind ballot token design |
| NIST SP 800-207 "Zero Trust Architecture" | Network security model |
| OWASP Top 10 (2021) | Application security checklist |

---

# 7. Challenges and Solutions

## Challenge 1: Calico Installation on Kind

**Problem:**
After creating the Kind cluster with `disableDefaultCNI: true`, all pods were stuck in `Pending` state. The Calico operator installed but pods remained unschedulable.

**Context:**
Week 3, Day 2 (Feb 11). Setting up the platform infrastructure for the first time. The Kind cluster was created but no networking was functional.

**Investigation Process:**
1. **Initial hypothesis:** Resource limits preventing scheduling → Checked with `kubectl describe node` → Resources available, not the issue
2. **Second hypothesis:** Calico operator not running → `kubectl get pods -n calico-system` → Operator running but calico-node pods in CrashLoopBackOff
3. **Checked logs:** `kubectl logs -n calico-system ds/calico-node` → IP pool conflict with Kind's podSubnet
4. **Research:** Read Calico's Kind-specific installation guide → Found that Kind requires specific CIDR configuration
5. **Root cause identified:** The default Calico Installation custom resource assumes a different pod CIDR than Kind's `192.168.0.0/16`

**Solution:**
Created a Kind-specific Calico Installation custom resource:
```yaml
spec:
  calicoNetwork:
    ipPools:
    - cidr: 192.168.0.0/16         # Match Kind's podSubnet
      encapsulation: VXLANCrossSubnet
    nodeAddressAutodetectionV4:
      kubernetes: NodeInternalIP     # Kind nodes use Docker bridge IPs
```

**Outcome:**
Calico became fully operational within 60 seconds. All pods transitioned from `Pending` to `Running`. Encoded the fix in `setup_k8s_platform.py`.

**Learning:**
Always read the platform-specific installation guide, not just the generic guide. Kind's Docker-based networking has unique requirements that generic Calico docs don't cover.

**Prevention:**
Automated the entire Calico installation in the setup script with the correct configuration baked in.

---

## Challenge 2: Bidirectional Network Policy Enforcement

**Problem:**
After implementing database ingress policies, services still timed out when connecting to PostgreSQL. The policies appeared correct but connections failed silently.

**Context:**
Week 4, Day 1 (Feb 15). Implementing the zero-trust network model. Had applied default-deny and database ingress policies.

**Investigation Process:**
1. **Initial hypothesis:** Label selector mismatch → Verified with `kubectl get netpol -o yaml` → Labels correct
2. **Test:** `kubectl exec test-auth -- nc -zv postgres 5432` → Connection timed out
3. **Hypothesis 2:** Port mismatch → Verified PostgreSQL running on 5432 → Correct
4. **Hypothesis 3:** Default-deny blocking return traffic → Research confirmed: default-deny blocks ALL traffic including responses... wait, that's not how TCP works in netpolicies
5. **Key realisation:** Read Kubernetes docs more carefully: "If any egress policy applies to a pod, only explicitly allowed egress is permitted." The default-deny **egress** policy was blocking the **outgoing** connection from the auth-service to PostgreSQL. The ingress policy on PostgreSQL only controls what PostgreSQL accepts, not what the sender is allowed to send.
6. **Root cause:** Missing egress policies on each service for database connections

**Solution:**
Added egress policies for each service that needs database access:
```yaml
# On each service (e.g., auth-service):
egress:
- to:
  - podSelector:
      matchLabels:
        app: postgres
  ports:
  - port: 5432
```

**Outcome:**
All service-to-database connections working. This pattern was then applied to all inter-service communication (DNS, audit service).

**Learning:**
Bidirectional enforcement is the most critical concept in zero-trust networking. Every connection needs TWO rules: sender egress + receiver ingress. This was the single most time-consuming debugging session in the project.

**Prevention:**
Documented as a key pattern. All new policies are created in pairs (ingress + egress) in the same YAML file.

---

## Challenge 3: DNS Resolution After Default Deny

**Problem:**
After applying default-deny policies, pods could not resolve Kubernetes Service names. `nslookup postgres` returned `SERVFAIL`.

**Context:**
Week 4, Day 1 (Feb 15). Immediately after applying default-deny as the zero-trust baseline.

**Investigation Process:**
1. **Symptoms:** All service-to-service calls failing with hostname resolution errors
2. **Test:** `kubectl exec test-pod -- nslookup kubernetes.default` → Failed
3. **Realisation:** Default-deny blocks ALL egress, including UDP port 53 (DNS) to the `kube-system` namespace where `kube-dns` runs
4. **Confirmed:** DNS queries must cross namespace boundaries (from `uvote-dev` to `kube-system`)

**Solution:**
Created `01-allow-dns.yaml` as the first policy after default-deny:
```yaml
spec:
  podSelector: {}  # All pods in namespace
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

**Outcome:**
DNS resolution restored for all pods. This became the standard first policy in any zero-trust deployment.

**Learning:**
DNS is infrastructure, not application traffic. It must always be explicitly allowed in a default-deny model. The numbered file naming (`00-`, `01-`, `02-`, ...) ensures DNS is always applied immediately after default-deny.

---

## Challenge 4: Database Connection Race Condition

**Problem:**
Services crashed on startup with `asyncpg.exceptions.ConnectionDoesNotExistError`.

**Context:**
Week 2. First attempt at running all services via Docker Compose.

**Investigation Process:**
1. **Symptoms:** Auth-service, voter-service, voting-service all exiting with connection errors
2. **Docker logs:** PostgreSQL still initialising (running init scripts) when services attempted to connect
3. **Root cause:** `depends_on` in Docker Compose only waits for container start, not service readiness

**Solution:**
Added PostgreSQL health check and `condition: service_healthy`:
```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U voting_user -d voting_db"]
    interval: 10s
    timeout: 5s
    retries: 5

auth-service:
  depends_on:
    postgres:
      condition: service_healthy
```

**Outcome:**
Services wait for PostgreSQL to accept connections before starting. Zero startup crashes.

**Learning:**
Container "running" ≠ service "ready". Always use health checks for database dependencies.

---

## Challenge 5: Shared Code in Docker Images

**Problem:**
Each microservice needed `shared/database.py`, `shared/security.py`, and `shared/schemas.py`, but Docker builds are isolated per Dockerfile.

**Context:**
Week 2. Building Docker images for the first time.

**Investigation Process:**
1. **Initial attempt:** `COPY ../shared /app/shared` → Docker error: "COPY failed: forbidden path outside the build context"
2. **Research:** Docker builds cannot access files outside their build context
3. **Solution approaches:** (a) Python package with pip install, (b) Monorepo build context, (c) Build argument

**Solution:**
Set the build context to the project root in Docker Compose:
```yaml
auth-service:
  build:
    context: .           # Root context (not auth-service/)
    dockerfile: auth-service/Dockerfile

# In auth-service/Dockerfile:
COPY shared /app/shared  # Now works because context is root
COPY auth-service/requirements.txt .
COPY auth-service/app.py .
```

**Outcome:**
Clean solution without creating a Python package. All services share identical utility code.

**Learning:**
Docker build context determines the file access boundary. Setting context to the project root allows shared code access while still using per-service Dockerfiles.

---

## Challenge 6: PostgreSQL Schema Initialisation on Kubernetes

**Problem:**
PostgreSQL pod started but tables did not exist. The schema was not applied.

**Context:**
Week 3, Day 3 (Feb 12). First PostgreSQL deployment on Kubernetes.

**Investigation Process:**
1. **Docker Compose works:** init.sql mounted to `/docker-entrypoint-initdb.d/` runs automatically
2. **Kubernetes:** ConfigMap mounting to the same path didn't trigger — PostgreSQL data directory already existed from the PVC
3. **Key insight:** PostgreSQL only runs init scripts when the data directory is empty. With a PVC, the data directory persists across pod restarts.

**Solution:**
Applied schema via `kubectl exec` in the setup script:
```python
# Copy schema to pod, then execute:
subprocess.run(["kubectl", "cp", schema_path, f"{pod_name}:/tmp/schema.sql"])
subprocess.run(["kubectl", "exec", pod_name, "--",
    "psql", "-U", "postgres", "-d", "voting_db", "-f", "/tmp/schema.sql"])
```

**Outcome:**
Schema reliably applied during initial setup. Idempotent — running again on an existing database updates without errors (using `IF NOT EXISTS` clauses).

**Learning:**
PostgreSQL's init mechanism is designed for first-time setup, not ongoing schema management. For Kubernetes, explicit schema application is more reliable.

---

## Challenge 7: Per-Service Database User Testing

**Problem:**
Needed to verify that each of the 5 database users had exactly the right permissions — grants AND denials.

**Context:**
Week 3, Day 3 (Feb 12). Writing the database test suite.

**Investigation Process:**
1. **Testing grants is easy:** Connect as user, run allowed query, verify success
2. **Testing denials is harder:** Need to verify that `InsufficientPrivilegeError` is raised for forbidden operations
3. **Challenge:** 5 users × ~12 tables × 4 operations (SELECT, INSERT, UPDATE, DELETE) = ~240 permission checks

**Solution:**
Created a permission matrix as a data structure and iterated:
```python
PERMISSION_MATRIX = {
    "auth_user": {
        "can_select": ["organisers", "voters", "elections", "voting_tokens"],
        "can_insert": ["organisers", "voter_mfa", "blind_tokens", "audit_log"],
        "cannot_select": ["encrypted_ballots", "tallied_votes"],
        "cannot_insert": ["elections", "encrypted_ballots"],
    },
    # ... for each user
}
```

**Outcome:**
Comprehensive permission validation. Caught two issues: auth_user initially lacked SELECT on voting_tokens, and voting_user had unintended UPDATE on elections.

**Learning:**
Permission testing is best done as a matrix — test every user against every table for every operation. Denials are as important to test as grants.

---

## Challenge 8: Network Policy Cross-Namespace Ingress

**Problem:**
The Nginx Ingress Controller (in `ingress-nginx` namespace) could not reach services in `uvote-dev` namespace after default-deny.

**Context:**
Week 4, Day 1 (Feb 15). Configuring ingress controller access through network policies.

**Investigation Process:**
1. **Test:** External HTTP request → Ingress Controller → Service → Timeout
2. **Ingress controller pods running in different namespace** — podSelector won't match
3. **Need:** namespaceSelector to allow cross-namespace traffic

**Solution:**
```yaml
ingress:
- from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ingress-nginx
  ports:
  - port: 5000
```

**Outcome:**
Ingress routing working through network policies. Each service has its own ingress policy for fine-grained control.

**Learning:**
Cross-namespace policies require `namespaceSelector`. Kubernetes auto-labels namespaces with `kubernetes.io/metadata.name`, so no manual labeling is needed.

---

## Challenge 9: Docker Image Loading into Kind

**Problem:**
Kubernetes deployments stuck in `ImagePullBackOff` because Kind nodes couldn't access locally-built Docker images.

**Context:**
Week 4, Day 2 (Feb 16). First attempt at deploying services to Kubernetes.

**Investigation Process:**
1. **`kubectl describe pod`:** "Failed to pull image: image not found"
2. **Images exist locally:** `docker images` shows all service images
3. **Kind uses containerd, not Docker:** Kind nodes have their own image store
4. **Solution exists:** `kind load docker-image` copies from Docker to Kind

**Solution:**
```bash
kind load docker-image auth-service:latest --name uvote
# Repeat for each service

# In deployment manifests:
imagePullPolicy: Never  # Don't try to pull from registry
```

**Outcome:**
All images available in Kind. Automated in `deploy_platform.py`.

**Learning:**
Kind's containerd runtime is separate from host Docker. `kind load` bridges this gap. `imagePullPolicy: Never` prevents unnecessary pull attempts.

---

## Challenge 10: Blind Ballot Token Protocol Implementation

**Problem:**
Implementing the anonymity bridge — ensuring the auth-service generates a ballot token without any record linking it to the voter who received it.

**Context:**
Week 4, Day 2 (Feb 16). Implementing the core security feature during application hardening.

**Investigation Process:**
1. **Design review:** ADR-015 specifies the 3-phase protocol
2. **Critical code path:** The `INSERT INTO blind_tokens` must NOT include `voter_id`
3. **Risk:** A developer could accidentally add a `voter_id` column or log the mapping
4. **Mitigation:** Schema-level enforcement — the `blind_tokens` table has NO `voter_id` column

**Solution:**
```python
# The Anonymity Bridge (auth-service/app.py):
async with pool.acquire() as conn:
    async with conn.transaction():
        # Step 1: Accountability — mark voter as having voted
        await conn.execute(
            "UPDATE voters SET has_voted = TRUE WHERE id = $1", voter_id
        )

        # Step 2: Mark token as used
        await conn.execute(
            "UPDATE voting_tokens SET is_used = TRUE WHERE id = $1", token_id
        )

        # Step 3: Generate blind ballot token (ANONYMITY)
        ballot_token = generate_blind_ballot_token()
        await conn.execute(
            "INSERT INTO blind_tokens (ballot_token, election_id) "
            "VALUES ($1, $2)",
            ballot_token, election_id
        )
        # NO INSERT linking voter_id to ballot_token
        # The link is permanently severed after this transaction
```

**Outcome:**
Anonymity enforced at both code and schema level. Even a DBA with full SELECT access cannot determine which voter received which ballot token.

**Learning:**
The strongest security controls are ones that cannot be accidentally bypassed. By not having a `voter_id` column in `blind_tokens`, no application bug can store the mapping — the column simply does not exist.

---

# 8. Iteration Retrospectives

## Iteration 1: Foundation Sprint

**Dates:** January 27 — February 14, 2026
**Goal:** Working application + platform infrastructure

### Summary

| Metric | Planned | Actual | Variance |
|--------|---------|--------|----------|
| Tasks Completed | 8 | 7 | -12.5% |
| Commits | — | 13 | — |
| Lines Written | — | ~12,000 | — |
| Hours | 80 | ~100 | +25% |

### Completed

- [x] All 6 microservices implemented
- [x] Database schema designed and deployed
- [x] Docker Compose local development
- [x] Kind cluster with Calico CNI
- [x] PostgreSQL on Kubernetes
- [x] Platform setup automation
- [x] Database test suite

### Partially Completed

- [~] Architecture documentation (comprehensive but continued into Week 4)

### Not Completed (deferred)

- [ ] Network policies (moved to Iteration 2)
- [ ] Service deployment manifests (moved to Iteration 2)
- [ ] ADRs and Investigation Log (moved to Iteration 2)

### What Went Well

1. **Parallel development** worked effectively — platform and application progressed independently
2. **Automation-first approach** paid dividends — the setup script was used dozens of times during the remaining days
3. **Database test suite** caught real permission issues before they became production bugs
4. **Clean base code** from PR #1 provided a solid foundation for hardening in Iteration 2

### What Could Improve

1. **Calico research before implementation** would have saved 4 hours
2. **Network policies should have started in Week 3** instead of being deferred
3. **Better time estimation** — underestimated platform infrastructure complexity

### Action Items (carried to Iteration 2)

- [x] Implement network policies
- [x] Create service deployment manifests
- [x] Write ADRs and Investigation Log
- [x] Complete application hardening

---

## Iteration 2: Security & Deployment Sprint

**Dates:** February 15 — February 16, 2026
**Goal:** Security hardening + deployment automation + documentation

### Summary

| Metric | Planned | Actual | Variance |
|--------|---------|--------|----------|
| Tasks Completed | 6 | 6 | 0% |
| Commits | — | 7 | — |
| Lines Written | — | ~14,000 | — |
| Hours | 25 | ~30 | +20% |

### Completed

- [x] 12 network policies implemented and tested
- [x] 6 network policy validation summaries
- [x] Network security architecture document (828 lines)
- [x] 6 service deployment manifests
- [x] Deployment automation script (1,030 lines)
- [x] Application hardening (blind ballot tokens, vote encryption)
- [x] Platform documentation update (+2,711 lines)
- [x] 15 ADRs + Investigation Log (6,156 lines)
- [x] PR #2 merged

### Not Completed (deferred to Stage 2)

- [ ] CI/CD pipeline
- [ ] Email service integration
- [ ] Integration tests
- [ ] Production deployment

### What Went Well

1. **Clear prioritisation** — every hour was spent on Stage 1 deliverables
2. **Network policy documentation** — writing validation summaries as policies were tested created accountability
3. **ADR quality** — each ADR evaluated 3-4 alternatives with pros/cons/rationale

### What Could Improve

1. **Documentation should not pile up at the end** — the 6,000+ line documentation day was exhausting
2. **Earlier policy testing** — bidirectional issue cost 5 hours that could have been spent elsewhere
3. **Deployment manifests should evolve alongside the platform** — creating them last meant repeating work

---

# 9. Final Reflection

## Project Outcomes vs Original Goals

### Goal 1: Secure Online Voting System — ACHIEVED

The system implements a complete voting flow with cryptographic anonymity:
- Voters authenticate with unique tokens + DOB MFA
- Blind ballot tokens sever the identity-ballot link
- Votes encrypted with `pgp_sym_encrypt` before storage
- Hash-chained audit logs provide tamper evidence
- Receipt tokens allow voter verification

**Evidence:** auth-service implements the 3-phase anonymity bridge protocol. voting-service encrypts ballots. Database schema enforces anonymity at the column level (no `voter_id` in `blind_tokens` or `encrypted_ballots`).

### Goal 2: Microservices on Kubernetes — ACHIEVED

Six microservices deployed on a 3-node Kind cluster:
- Each service has its own Deployment, Service, and NetworkPolicy
- Per-service database users enforce least-privilege access
- Zero-trust network policies prevent lateral movement
- Calico CNI enforces policies at the kernel level

**Evidence:** 16 Kubernetes manifests define the complete infrastructure. 12 network policies implement the zero-trust model. 5 database users with specific GRANT statements.

### Goal 3: Comprehensive Documentation — ACHIEVED

Over 8,000 lines of technical documentation:
- 15 ADRs documenting every major decision
- 2,027-line Investigation Log
- 1,363-line Architecture specification
- 3,270-line Platform documentation
- 828-line Network Security document
- 926 lines of validation summaries

**Evidence:** All documentation in `.docs/` directory, version-controlled in git.

### Goal 4: Working Prototype — ACHIEVED

The prototype demonstrates:
- End-to-end voting flow (token → identity → ballot → vote → receipt)
- Admin dashboard (register, login, create election, manage voters)
- Results tallying with vote decryption
- Docker Compose for local development
- Kubernetes deployment with full infrastructure

**Evidence:** Docker Compose `docker-compose up` starts all services. Kubernetes deployment via `deploy_platform.py` deploys to Kind cluster.

## Technical Achievements

### Most Proud Of: Blind Ballot Token Protocol

The anonymity bridge is the most security-critical design in the system. Implementing it required understanding the tension between accountability (proving who voted) and anonymity (hiding how they voted). The solution — generating a random token with no voter linkage — is elegant in its simplicity:

```python
ballot_token = secrets.token_urlsafe(32)  # 256 bits of pure randomness
# Stored with election_id ONLY — no voter_id, ever
```

The anonymity is enforced at three levels:
1. **Code level:** The INSERT statement doesn't include voter_id
2. **Schema level:** The `blind_tokens` table has no voter_id column
3. **Database level:** The voting_user role cannot access the voters table

### Most Challenging: Zero-Trust Network Policies

The bidirectional enforcement requirement was the single most time-consuming challenge. Understanding that default-deny means absolutely nothing works — not even DNS — required a fundamental shift in thinking about network security. The lesson: security is not about adding protections, it's about denying everything and selectively permitting.

### Most Valuable Learning: Defence in Depth

The project's 4-layer security model — network isolation → database permissions → application logic → data encryption — taught me that no single security control is sufficient. Each layer operates independently:
- If network policies fail → database permissions still restrict access
- If database permissions fail → application logic validates inputs
- If application logic fails → data encryption protects the raw data

## Process Reflection

### What Worked Well

1. **Parallel workstreams** — Clear responsibility split between platform and application allowed continuous progress
2. **Automation-first** — The setup and deployment scripts saved dozens of hours over the project lifetime
3. **Documentation-driven** — Writing architecture docs before implementation clarified design decisions and prevented scope creep
4. **Incremental testing** — Testing each network policy individually caught issues immediately

### What Would I Do Differently

1. **Start documentation earlier** — The final documentation sprint was unnecessarily stressful. Writing ADRs as decisions are made (not retroactively) would be more accurate and less time-pressured.
2. **Network policies from day one** — The zero-trust model should be the first thing deployed, not the last. Building on a secure foundation is easier than retrofitting security.
3. **Single schema file** — Maintaining two schema files (Docker Compose and Kubernetes) creates synchronisation risk. A single file with conditional logic would be better.
4. **Integration tests earlier** — The database test suite was invaluable. An equivalent integration test suite for the voting flow would have caught issues during application hardening.

### How the Project Evolved

The project started as a research paper about secure voting systems and evolved into a production-grade platform:

```
Research Paper (Sep 2025)
  → Technology decisions and threat analysis

Restart (Jan 2026)
  → Clean implementation from scratch

Base Code (Feb 10)
  → 6 working microservices + Docker Compose

Platform Infrastructure (Feb 11-12)
  → Kind cluster + Calico + PostgreSQL on K8s

Security Hardening (Feb 15-16)
  → Network policies + blind ballot tokens + encryption

Documentation (Feb 16)
  → 15 ADRs + Investigation Log + comprehensive docs
```

Each phase built on the previous one, with security becoming progressively more sophisticated. The final system has security controls at every layer, documented decisions for every technology choice, and automation for every operational task.

## Future Work

### Immediate Next Steps (Stage 2, Weeks 1-2)

- [ ] Consolidate dual schema files
- [ ] Set up CI/CD pipeline with GitHub Actions
- [ ] Configure email service SMTP in Kubernetes
- [ ] Create integration tests for the voting flow
- [ ] Add monitoring with Prometheus and Grafana

### Medium-Term (Stage 2, Weeks 3-6)

- [ ] Implement TLS with cert-manager
- [ ] Add rate limiting and API throttling
- [ ] Implement admin audit dashboard
- [ ] Add voter notification system
- [ ] Create load testing suite

### Long-Term Enhancements

- [ ] Upgrade to RSA blind signatures (mathematical anonymity guarantee)
- [ ] Evaluate service mesh (Istio) for mTLS
- [ ] Add Row-Level Security in PostgreSQL
- [ ] Migrate to cloud Kubernetes (AKS/EKS)
- [ ] Implement WebSocket-based real-time results

### Lessons for the Next Project

1. **Security-first architecture** pays for itself — retrofitting security is 10x harder than building it in
2. **Automation is a force multiplier** — every hour spent on scripts saves 10 hours later
3. **Documentation is a deliverable** — treat it with the same rigor as code
4. **Test at every layer** — unit tests catch code bugs, integration tests catch design bugs, infrastructure tests catch deployment bugs
5. **The restart was the right call** — building correctly from scratch produced a better result than patching a flawed foundation

---

## Appendix A: Complete Git History

```
* 29a9945 - Luke Doyle, 2026-02-16 : docs: compiled and composed research and decision logs
* 71def1e - Luke Doyle, 2026-02-16 : doc: updated platform document with comprehensive details
* 0a92041 - Luke Doyle, 2026-02-16 : depl: created basic deployment script for manifests
* 4256cbd - Luke Doyle, 2026-02-16 : depl: created deployment manifests for stage 1 mvp services
*   21a0ca6 - D00256764, 2026-02-16 : Merge pull request #2 from D00256764/dev
|\
| * e07ead5 - hafsa, 2026-02-16 : stage1
* | e9222d3 - Luke Doyle, 2026-02-15 : docs: add comprehensive network security architecture document
* | 951b7c7 - Luke Doyle, 2026-02-15 : docs: add network policy validation summaries and test results
* | b9ee9d5 - Luke Doyle, 2026-02-15 : feat: add Kubernetes network policies (zero-trust)
* | d5fa9fd - Luke Doyle, 2026-02-13 : chore: updated README using documentation
* | f5603a2 - Luke Doyle, 2026-02-12 : test: add comprehensive database test suite for K8s
* | e1f05c3 - Luke Doyle, 2026-02-12 : script: added script to auto set up a K8s cluster
* | 15df12b - Luke Doyle, 2026-02-12 : plat: added postgres db to platform
* | b658c9a - Luke Doyle, 2026-02-12 : chore: created generic .gitignore file
* | 06c8951 - Luke Doyle, 2026-02-11 : plat: created basic kubernetes platform to test calico
* | 581d001 - Luke Doyle, 2026-02-11 : docs: add project specs, architecture docs, README rewrite
* | d933c31 - Luke Doyle, 2026-02-10 : chore: added project module requirements
* | ac11b5d - D00256764, 2026-02-10 : Merge pull request #1 from D00256764/dev
|\|
| * c723de7 - hafsa, 2026-02-10 : base code
|/
* 97e68a6 - D00256764, 2026-02-08 : Initial commit
```

## Appendix B: File Inventory

```
Total: 101 files

Services:
  auth-service/app.py                          342 lines
  voter-service/app.py                         499 lines
  voting-service/app.py                        377 lines
  results-service/app.py                       318 lines
  election-service/app.py                      418 lines
  frontend-service/app.py                      149 lines

Shared:
  shared/database.py                            52 lines
  shared/security.py                           116 lines
  shared/schemas.py                            193 lines
  shared/email_util.py                         159 lines

Platform Scripts:
  plat_scripts/setup_k8s_platform.py           641 lines
  plat_scripts/deploy_platform.py            1,030 lines
  plat_scripts/test_db.py                    1,270 lines

Database:
  database/init.sql                            269 lines
  uvote-platform/k8s/database/schema.sql       194 lines

K8s Infrastructure:
  uvote-platform/kind-config.yaml               15 lines
  uvote-platform/k8s/namespaces/               20 lines
  uvote-platform/k8s/database/                107 lines
  uvote-platform/k8s/services/               764 lines
  uvote-platform/k8s/network-policies/       993 lines

Templates:
  19 HTML files                              1,222 lines

Stylesheets:
  5 CSS files                                  218 lines

Dockerfiles:
  6 Dockerfiles                                106 lines

Documentation:
  .docs/ARCHITECTURE.MD                      1,363 lines
  .docs/PLATFORM.MD                          3,270 lines
  .docs/NETWORK-SECURITY.md                    828 lines
  .docs/INVESTIGATION-LOG.md                 2,027 lines
  .docs/decisions/ (16 files)                4,129 lines
  network_summary/ (7 files)                   926 lines
  README.md                                    421 lines
```

---

**End of Build Log**

*Last updated: February 16, 2026*
*Author: D00255656 — Luke Doyle*
*Project: U-Vote — Secure Online Voting System*
