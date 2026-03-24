# U-Vote Local Development Setup

## Prerequisites
- Python 3.10 or higher (`python3 --version`)
- kubectl configured for the Kind cluster
- Docker (for image builds)
- Kind (for cluster management)
- Helm 3.x (for Elasticsearch/Prometheus deployment)

## Quick Start

### 1. Create the virtual environment
```bash
python setup_venv.py
```

### 2. Activate the environment
Linux/macOS:
```bash
source .venv/bin/activate
```
Windows:
```bat
.venv\Scripts\activate.bat
```

### 3. Set up the Kubernetes cluster (first time only)
```bash
python plat_scripts/setup_k8s_platform.py
```

### 4. Deploy all services
```bash
python plat_scripts/deploy_platform.py
```

### 5. Run unit tests (no cluster required)
```bash
python -m pytest \
  auth-service/tests/ \
  voting-service/tests/ \
  election-service/tests/ \
  frontend-service/tests/ \
  admin-service/tests/ \
  -v
```

### 6. Run integration tests (cluster required)
```bash
python -m pytest tests/test_db.py tests/test_api.py -v
```

## Flags
| Flag | Effect |
|------|--------|
| (none) | Full setup — create .venv and install all deps |
| `--clean` | Delete existing .venv and start fresh |
| `--verify-only` | Skip install, just run import checks |
| `--help` | Show usage |

## Script Reference
| Script | Purpose | Cluster required |
|--------|---------|-----------------|
| `plat_scripts/setup_k8s_platform.py` | First-time cluster bootstrap | Creates it |
| `plat_scripts/deploy_platform.py` | Build and deploy all services | YES |
| `plat_scripts/deploy_test_platform.py` | Deploy MailHog test SMTP | YES |
| `plat_scripts/port_forward.py` | Forward ingress to localhost:8080 | YES |
| `plat_scripts/dashboard.py` | Open Kubernetes dashboard | YES |
| `tests/test_db.py` | Database schema and trigger tests | YES |
| `tests/test_api.py` | End-to-end API integration tests | YES |

## Dependency files installed by setup_venv.py
| File | Purpose |
|------|---------|
| `requirements-dev.txt` | pytest, pytest-asyncio, httpx, pytest-mock |
| `plat_scripts/requirements.txt` | colorama, click |
| `auth-service/requirements.txt` | FastAPI, asyncpg, passlib, bcrypt, jose |
| `voting-service/requirements.txt` | FastAPI, httpx, jinja2 |
| `election-service/requirements.txt` | FastAPI, asyncpg, jinja2, itsdangerous |
| `results-service/requirements.txt` | FastAPI, asyncpg, jinja2 |
| `admin-service/requirements.txt` | FastAPI, asyncpg, aiosmtplib, jinja2 |
| `frontend-service/requirements.txt` | FastAPI, httpx, jinja2, itsdangerous |
