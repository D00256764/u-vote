# U-Vote

**A Secure, Accessible Online Voting System for Small-Scale Elections**

> Token-based online voting with cryptographic security, identity-ballot separation, immutable audit logging, and WCAG AA accessibility — deployed on Kubernetes with Calico network isolation.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Project Context](#project-context)
- [Architecture Summary](#architecture-summary)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Development Approach](#development-approach)
- [Security Measures](#security-measures)
- [Project Deliverables](#project-deliverables)
- [Documentation](#documentation)
- [License](#license)

---

## Project Overview

U-Vote is a secure, transparent, and inclusive online voting platform designed for small-scale democratic processes. It targets organisations where trust, accessibility, and auditability are critical but large-scale government infrastructure is unnecessary.

### Target Users

- **Student unions and councils** — campus-wide or departmental elections
- **NGOs and non-profits** — board elections, member votes
- **Local councils and clubs** — committee selections, policy decisions
- **Small organisations** — any group needing verifiable, anonymous voting

### Key Features

- **Token-based voting** — one-time secure URLs sent via email, no voter passwords required
- **Identity-ballot separation** — votes are stored without any link to voter identity
- **Immutable audit trail** — hash-chained event logs with tamper detection
- **Anonymous ballots** — cryptographic hashing (SHA-256) on every vote record
- **CSV voter import** — bulk voter management for administrators
- **Email notifications** — voting invitations and results distribution
- **WCAG AA accessibility** — inclusive design for users with diverse abilities
- **Microservices architecture** — 8 independently deployable services
- **Kubernetes deployment** — Calico network policies for service isolation

### Objectives

1. Implement secure user authentication to prevent identity fraud
2. Protect vote data and system integrity against cybersecurity threats
3. Ensure the platform is accessible to users with impairments or low digital literacy
4. Provide a transparent, verifiable voting process with auditable logs
5. Deliver a production-quality proof-of-concept suitable for real small-scale elections

---

## Project Context

This project is the capstone for the **4th Year BSc in Computing Systems and Operations** programme, fulfilling module **PROJ I8009** (10 credits, 2 semesters).

The module requires students to design, build, and deliver a working software solution supported by a production-quality **DevOps pipeline and operational platform**, demonstrating how modern software is delivered, deployed, and operated.

### Module Learning Outcomes

| # | Outcome |
|---|---------|
| MLO1 | Conduct background reading, research, and user analysis to develop requirements for a complex technical project |
| MLO2 | Build, test, and deploy a substantial artefact while demonstrating best practice in modern DevOps |
| MLO3 | Demonstrate understanding of Development, Configuration Management, CI/CD, and Operations including software tools for automation |
| MLO4 | Communicate technical information clearly and succinctly using a range of media |
| MLO5 | Critically assess project outputs, reflect on objectives, and discuss outcomes in an oral/practical presentation |

### Assessment Breakdown

| Component | Weight |
|-----------|--------|
| Interim Submission (Stage 1 — Design & Prototyping) | 30% |
| Technical Documentation & Implementation (Stage 2) | 40% |
| Project Log & Reflection | 20% |
| Final Presentation & Product Demonstration | 10% |

---

## Architecture Summary

U-Vote follows a **microservices architecture** with 8 services, each with isolated database permissions, deployed on Kubernetes with Calico network policies enforcing a default-deny security model.

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python + FastAPI |
| **Frontend** | FastAPI + Jinja2 (server-side rendering) |
| **Database** | PostgreSQL 15 |
| **Orchestration** | Kubernetes (Kind for local dev) |
| **Networking** | Calico CNI + Network Policies |
| **Ingress** | Nginx Ingress Controller |
| **Security** | bcrypt, JWT (HS256), SHA-256 hash chains |
| **Secrets** | Kubernetes Secrets |
| **Containerisation** | Docker |

### Services

```
                         ┌──────────────┐
                         │   Internet   │
                         └──────┬───────┘
                                │ HTTPS
                    ┌───────────▼────────────┐
                    │   Nginx Ingress        │
                    │  (API Gateway)         │
                    └───────────┬────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        │           │           │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌───▼────┐ ┌────▼────┐ ┌───▼─────┐
   │Frontend │ │  Auth   │ │Election│ │ Voting  │ │ Results │
   │ :3000   │ │ :8001   │ │ :8002  │ │ :8003   │ │ :8004   │
   └─────────┘ └─────────┘ └────────┘ └─────────┘ └─────────┘
        │           │           │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌───▼────┐     │           │
   │  Admin  │ │  Audit  │ │ Email  │     │           │
   │ :8006   │ │ :8005   │ │ :8007  │     │           │
   └─────────┘ └─────────┘ └────────┘     │           │
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                                │
                    ┌───────────▼────────────┐
                    │   PostgreSQL 15        │
                    │   (PersistentVolume)   │
                    └────────────────────────┘
```

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 1 | **Frontend** | 3000 | Jinja2 templates, WCAG AA UI |
| 2 | **Auth** | 8001 | Admin registration, login, JWT tokens |
| 3 | **Election** | 8002 | Election CRUD, lifecycle management |
| 4 | **Voting** | 8003 | Token validation, ballot display, vote casting |
| 5 | **Results** | 8004 | Vote tallying, winner calculation (read-only DB access) |
| 6 | **Audit** | 8005 | Immutable hash-chained event logging |
| 7 | **Admin** | 8006 | Voter/candidate management, CSV import, token generation |
| 8 | **Email** | 8007 | Voting invitations, results notifications |

For the full architecture specification including database schema, API endpoints, data flow diagrams, and security model, see [`.docs/ARCHITECTURE.MD`](.docs/ARCHITECTURE.MD).

---

## Repository Structure

```
u-vote/
├── .docs/                          # Project documentation
│   ├── ARCHITECTURE.MD             # Application architecture (services, APIs, DB schema)
│   ├── PLATFORM.MD                 # Platform infrastructure (Kubernetes, Calico, networking)
│   ├── U-Vote_...pdf               # Research paper (background, risk analysis, UX design)
│   ├── 4th Year Project...pdf      # Project brief & requirements
│   └── Module PROJ I8009...pdf     # Module specification
├── auth-service/                   # Admin authentication service
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── voter-service/                  # Voter list & token management
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── voting-service/                 # Ballot access & vote casting
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── results-service/                # Result tallying & statistics
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-service/               # Web UI (Jinja2 templates)
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── templates/                  # HTML templates
│   └── static/css/                 # Stylesheets
├── shared/                         # Shared utilities
│   ├── database.py                 # Database connection helper
│   └── security.py                 # Security utilities
├── database/
│   └── init.sql                    # Database schema initialisation
├── docker-compose.yml              # Local development orchestration
├── sample-voters.csv               # Example voter CSV format
└── README.md                       # This file
```

---

## Getting Started

### Prerequisites

- **Docker** (v20.10+) and **Docker Compose**
- **Git**

For full Kubernetes deployment, additionally:
- **kubectl** (v1.27+)
- **Kind** (v0.20.0+)
- **Helm** (v3.12+)
- 8GB RAM minimum (16GB recommended), 4 CPU cores, 20GB disk

### Quick Start (Docker Compose)

```bash
# Clone the repository
git clone https://github.com/D00256764/u-vote.git
cd u-vote

# Start all services
docker-compose up --build

# Access the application
# Frontend:  http://localhost:5000
# Auth API:  http://localhost:5001
# Voter API: http://localhost:5002
# Vote API:  http://localhost:5003
# Results:   http://localhost:5004
```

The database is automatically initialised with the schema on first startup via `database/init.sql`.

### Kubernetes Deployment

For production-like deployment with Calico network isolation, see the detailed setup guide in [`.docs/PLATFORM.MD`](.docs/PLATFORM.MD).

```bash
# Create Kind cluster with Calico
./scripts/setup-mvp.sh

# Verify
kubectl get nodes
kubectl get pods -n evote-dev
```

---

## Development Approach

### Voter Authentication (Approach A — Token-Based URLs)

U-Vote uses a **token-based authentication model** where voters never need passwords:

1. Admin creates election and uploads voter list (CSV)
2. System generates cryptographic tokens (`secrets.token_urlsafe(32)`)
3. Email Service sends one-time voting URLs to each voter
4. Voter clicks link, sees ballot, casts vote
5. Token is invalidated — cannot be reused

This approach minimises friction for voters while maintaining security through:
- 256-bit entropy tokens
- 7-day expiration
- Single-use enforcement
- No voter identity stored alongside votes

### Election Lifecycle

```
draft  ──>  active  ──>  closed
  │            │            │
  │ (activate) │  (close)   │
  │            │            │
  Setup        Voting       Results
  phase        open         available
```

### DevOps Requirements

The platform addresses all module-required DevOps capabilities:

- **CI/CD** — Automated testing and quality gates with deployment pipelines
- **Infrastructure as Code** — Kubernetes manifests, Calico network policies
- **Operational Platform** — Kubernetes with multi-node Kind cluster
- **Observability** — Audit logging, hash-chain verification (Prometheus/Grafana planned)
- **Security** — Secrets management, least-privilege DB users, network isolation
- **Resilience** — Service isolation, fault tolerance through independent microservices

---

## Security Measures

| Category | Implementation |
|----------|---------------|
| **Admin Auth** | bcrypt (cost 12), JWT HS256, 24h expiry, account lockout after 5 failures |
| **Voter Auth** | Cryptographic tokens (256-bit), single-use, 7-day expiry |
| **Vote Anonymity** | No voter ID in votes table, audit logs exclude candidate choice |
| **Data Integrity** | SHA-256 hash chains, DB triggers prevent UPDATE/DELETE on votes |
| **Network** | Calico default-deny policies, service-to-service isolation |
| **Database** | Per-service DB users with least-privilege permissions |
| **Input Validation** | Parameterised queries (SQL injection prevention), email format validation |
| **Transport** | TLS termination at Nginx Ingress, internal HTTP only |

---

## Project Deliverables

### Stage 1 — Design & Prototyping (30%)

| Delivery | Schedule | Weight |
|----------|----------|--------|
| Documentation of objectives, user problem, value proposition | Week 3 | 5% |
| MVP prototype demo | Week 9 | 10% |
| Documentation of final MVP functionality and design | End of Semester 1 | 10% |
| Platform design document and demo | End of Semester 1 | 10% |

### Stage 2 — Implementation (40%)

| Delivery | Schedule | Weight |
|----------|----------|--------|
| Provisioned platform and MVP deployment with logging | Week 9 | 10% |
| CI pipeline demonstrating build and test automation | Week 9 | 10% |
| CD pipeline demonstrating automated deployment with iterations | End of Semester 2 | 10% |
| Application monitoring and non-functional testing | End of Semester 2 | 10% |

### Project Log & Reflection (20%)

| Delivery | Schedule | Weight |
|----------|----------|--------|
| Log of work and progress | End of Semester 1 | 5% |
| Log of work and progress | End of Semester 2 | 5% |
| Reflection: lessons learned, challenges, future improvements | End of Semester 2 | 10% |

### Final Presentation (10%)

Slides, poster, live demonstration, and Q&A at end of year.

---

## Documentation

| Document | Description |
|----------|-------------|
| [`.docs/ARCHITECTURE.MD`](.docs/ARCHITECTURE.MD) | Full application architecture — services, APIs, database schema, data flows, security model |
| [`.docs/PLATFORM.MD`](.docs/PLATFORM.MD) | Platform infrastructure — Kubernetes setup, Calico networking, deployment guide |
| [`.docs/U-Vote_...pdf`](.docs/U-Vote_%20A%20Secure%2C%20Accessible%20Online%20Voting%20System%20for%20Small-Scale%20Elections.pdf) | Research paper — background, risk analysis, accessibility, UX design |
| [`.docs/4th Year Project...pdf`](.docs/4th%20Year%20Project%20%E2%80%93%20Computing%20Systems%20and%20Operations.pdf) | Project brief and requirements |
| [`.docs/Module PROJ I8009...pdf`](.docs/Module%20PROJ%20I8009%20Project%20.pdf) | Module specification |

---

## License

This project is developed as part of the BSc in Computing Systems and Operations at Dundalk Institute of Technology (DkIT). It is provided for educational and demonstration purposes.
