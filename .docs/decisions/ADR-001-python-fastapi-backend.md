# ADR-001: Python FastAPI Backend

## Status

**Status:** Accepted
**Date:** 2026-02-10
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system requires a backend framework that can handle concurrent voter submissions during active elections while providing strong security libraries for JWT authentication, password hashing, and cryptographic token generation. The framework must support asynchronous database access (PostgreSQL with asyncpg) to avoid connection bottlenecks under load.

### Background

The project initially prototyped with Flask (the framework used throughout the DkIT programme). During Week 2 load testing, Flask's synchronous WSGI model showed significant performance degradation under concurrent load — 50 simultaneous voters caused response times to exceed 800ms at the 99th percentile due to blocking database calls.

The team's primary expertise is in Python (3+ years), with intermediate JavaScript knowledge. Learning an entirely new language (Go, Java) for the backend would consume 4–6 weeks of the 12-week Stage 1 timeline.

### Requirements

- **R1:** Handle 1,000 concurrent voters with <500ms response time at p99
- **R2:** Native async/await for non-blocking database queries (asyncpg)
- **R3:** JWT token generation and validation libraries
- **R4:** bcrypt password hashing (cost factor 12)
- **R5:** Jinja2 template rendering for server-side HTML
- **R6:** Automatic OpenAPI documentation generation
- **R7:** Input validation and request serialisation
- **R8:** Containerisable with small Docker image footprint
- **R9:** Active maintenance and community support

### Constraints

- **C1:** Must be Python (team's strongest language — see §2.3.3 of Investigation Log)
- **C2:** Must integrate with asyncpg connection pool (shared/database.py)
- **C3:** Must run on python:3.11-slim Docker base image
- **C4:** Two-semester timeline limits framework learning investment

---

## Options Considered

### Option 1: Flask (Micro-Framework)

**Description:**
Flask is a lightweight WSGI web framework. It is synchronous by default and relies on extensions for features like JWT, input validation, and async support. Flask is the most familiar framework from DkIT coursework.

**Pros:**
- Maximum team familiarity (used in multiple modules)
- Mature ecosystem with battle-tested extensions
- Simple, minimal API (easy to get started)
- Jinja2 templating built-in
- Extensive documentation and tutorials

**Cons:**
- Synchronous by default (WSGI) — blocking database calls under concurrent load
- Flask-Async exists but is not production-grade
- Requires separate libraries for JWT (Flask-JWT-Extended), validation (Flask-WTF), OpenAPI (Flask-Swagger)
- No built-in request validation via type hints
- Gunicorn workers model scales via processes, not async I/O

**Evaluation:**
Flask meets most requirements but fails R1 (concurrent performance) and R2 (native async). Workarounds exist (gevent, Flask-Async) but are complex and less reliable than natively async frameworks.

### Option 2: FastAPI (ASGI Framework) — Chosen

**Description:**
FastAPI is a modern Python web framework built on Starlette (ASGI) and Pydantic. It provides native async/await support, automatic OpenAPI documentation, and type-hint-based request validation. First released in 2018, it has rapidly become one of the most popular Python web frameworks.

**Pros:**
- Native async/await (ASGI — non-blocking I/O)
- Automatic OpenAPI/Swagger documentation from code
- Pydantic-based request/response validation via type hints
- High performance (benchmarks comparable to Node.js and Go)
- Jinja2 support via Starlette
- Built-in dependency injection
- Excellent documentation with interactive examples
- Growing rapidly (most starred Python web framework on GitHub)

**Cons:**
- Less familiar than Flask (not used in DkIT coursework)
- Smaller extension ecosystem than Flask (though Starlette's ecosystem compensates)
- Pydantic v2 migration caused some library compatibility issues in 2024
- async patterns require understanding of Python's asyncio event loop

**Evaluation:**
FastAPI natively satisfies all requirements (R1–R9). The learning curve over Flask is modest (~1 week) due to Python familiarity.

### Option 3: Node.js Express

**Description:**
Express is a minimal Node.js web framework. JavaScript's event loop provides native async I/O.

**Pros:**
- Native async via event loop
- Largest package ecosystem (npm)
- Ubiquitous in web development

**Cons:**
- Requires learning TypeScript for production quality
- Different language from infrastructure scripts (Python)
- Less familiar than Python frameworks
- npm dependency management is notoriously fragile

**Evaluation:**
Express meets performance requirements but introduces a language switch. All infrastructure scripts, shared libraries, and DevOps tooling are Python. Mixing languages adds cognitive overhead without proportional benefit.

### Option 4: Go Gin

**Description:**
Gin is a high-performance HTTP framework for Go with a martini-like API.

**Pros:**
- Compiled binary (fastest performance)
- Goroutines for concurrency (elegant model)
- Small Docker images (~10MB)

**Cons:**
- Entirely new language (Go) — 4–6 week learning investment
- Smaller web ecosystem than Python/Node
- More verbose than Python for equivalent functionality
- Would slow Stage 1 delivery significantly

**Evaluation:**
Go would provide the best raw performance but the learning investment is prohibitive given the timeline. The performance difference between Go and FastAPI (2x at best) is irrelevant for an election with 1,000 voters.

### Option 5: Java Spring Boot

**Description:**
Spring Boot is an enterprise Java framework providing convention-over-configuration development.

**Pros:**
- Enterprise-grade, robust ecosystem
- Mature security framework (Spring Security)
- Strong typing and IDE support

**Cons:**
- JVM startup time (10–30 seconds) — problematic for container health probes
- High memory usage (~200MB baseline per service)
- Verbose development style (Java boilerplate)
- Overkill for small-scale election system
- Limited team familiarity

**Evaluation:**
Spring Boot's JVM overhead and verbosity make it unsuitable for lightweight microservices in a resource-constrained Kind cluster.

---

## Decision

**Chosen Option:** FastAPI (Option 2)

**Rationale:**
FastAPI provides the optimal combination of Python familiarity, native async support, and automatic documentation. The benchmark results (§3.1.5 of Investigation Log) demonstrated a 6x throughput improvement over Flask for concurrent database-bound requests:

| Metric | Flask + psycopg2 | FastAPI + asyncpg |
|--------|-----------------|-------------------|
| Avg response time | 145ms | 23ms |
| p99 response time | 890ms | 67ms |
| Requests/sec | 340 | 2,100 |
| Memory usage | 85MB | 62MB |

**Key Factors:**

1. **Async performance (R1, R2):** 6x throughput for concurrent voters. During an active election, many voters submit simultaneously — async I/O is essential.

2. **Security library compatibility (R3, R4):** PyJWT and bcrypt work natively with FastAPI. No wrappers or adapters needed.

3. **Developer productivity (C1, C4):** Python syntax, type hints for validation, automatic OpenAPI docs. Estimated 30% faster feature development than Flask due to built-in validation and docs.

4. **asyncpg integration (R2):** FastAPI's async request handlers work naturally with asyncpg's async connection pool, enabling non-blocking database access throughout the request lifecycle.

---

## Consequences

### Positive Consequences

- **Performance:** 2,100 req/s handles the 1,000 concurrent voter requirement with significant headroom.
- **Documentation:** OpenAPI spec auto-generated from code — always up-to-date, no manual maintenance.
- **Validation:** Pydantic models catch malformed requests before they reach business logic, reducing security attack surface.
- **Async consistency:** async/await throughout the stack (HTTP → business logic → database) — no mixed sync/async anti-patterns.

### Negative Consequences

- **Learning curve:** ~1 week to learn FastAPI-specific patterns (dependency injection, Pydantic models). Mitigated by excellent documentation.
- **Less community content:** Fewer Stack Overflow answers and tutorials than Flask. Mitigated by official FastAPI docs being exceptionally comprehensive.
- **Pydantic compatibility:** Some third-party libraries were slow to support Pydantic v2. Mitigated by pinning Pydantic version in requirements.txt.

### Trade-offs Accepted

- **Familiarity vs Performance:** Accepted a small learning curve (Flask → FastAPI) in exchange for 6x performance improvement. The investment (1 week learning) pays back across the entire project timeline.
- **Ecosystem size vs Feature set:** Accepted a smaller extension ecosystem in exchange for built-in features (validation, OpenAPI, async) that Flask requires separate libraries for.

---

## Implementation Notes

### Technical Details

Each microservice follows a consistent FastAPI application structure:

```python
from fastapi import FastAPI
from shared.database import Database

app = FastAPI(title="Auth Service", version="1.0.0")

@app.on_event("startup")
async def startup():
    await Database.get_pool()

@app.on_event("shutdown")
async def shutdown():
    await Database.close()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth"}
```

### Configuration

- **ASGI server:** Uvicorn (production: `uvicorn app:app --host 0.0.0.0 --port 5001`)
- **Pydantic version:** v2 (pinned in requirements.txt)
- **Python version:** 3.11 (matching Docker base image)

### Integration Points

- **Database:** Via shared/database.py (asyncpg connection pool)
- **Security:** Via shared/security.py (bcrypt, JWT, hash chains)
- **Templates:** Via Starlette's Jinja2Templates (frontend-service)
- **Deployment:** Via Kubernetes Deployment manifests

---

## Validation

### Success Criteria

- [x] All 6 services start and respond to health checks
- [x] Load test: ≥1,000 req/s with <500ms p99 latency
- [x] JWT authentication working across services
- [x] Async database queries with connection pooling
- [x] OpenAPI documentation accessible at `/docs`

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Throughput | ≥1,000 req/s | 2,100 req/s |
| p99 Latency | <500ms | 67ms |
| Memory per service | <256MB | ~62MB |
| Startup time | <5s | ~2s |

### Review Date

End of Stage 2 (April 2026) — assess whether FastAPI meets production requirements.

---

## References

- [Investigation Log §3.1](../INVESTIGATION-LOG.md#31-backend-framework-investigation) — Full evaluation details
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Starlette Documentation](https://www.starlette.io/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [ADR-002](ADR-002-postgresql-database.md) — Database choice (asyncpg dependency)
- [ADR-008](ADR-008-microservices-architecture.md) — Architecture pattern
- [ADR-009](ADR-009-server-side-rendering.md) — Frontend rendering via Jinja2

## Notes

The migration from Flask to FastAPI occurred in Week 3 (Iteration 2 of prototyping). All Flask prototype code was rewritten to FastAPI — no Flask dependencies remain in the project.
