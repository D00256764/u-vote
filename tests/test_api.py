#!/usr/bin/env python3
"""
U-Vote API Integration Tests

Tests run sequentially; each stage passes state (JWT, election_id, tokens,
ballot_token) to the next.  All port-forwards are opened once upfront and
torn down in a finally block, so cleanup runs even on crashes.

Usage:
    python tests/test_api.py [--namespace uvote-dev] [--verbose] [--keep-data]
"""

import argparse
import base64
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Service registry  (Kubernetes deploy name → container port)
# ─────────────────────────────────────────────────────────────────────────────

SERVICES: Dict[str, Dict[str, Any]] = {
    "auth":     {"app": "auth-service",     "port": 5001},
    "election": {"app": "election-service", "port": 5005},
    "admin":    {"app": "admin-service",    "port": 5002},
    "voting":   {"app": "voting-service",   "port": 5003},
    "results":  {"app": "results-service",  "port": 5004},
    "frontend": {"app": "frontend-service", "port": 5000},
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: subprocess and HTTP
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, "", str(exc)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _resolve_pod(namespace: str, app_label: str) -> str:
    """Return 'pod/<name>' for a real service pod (tier=backend),
    falling back to 'deployment/<app>' so test pods are excluded."""
    for selector in [f"app={app_label},tier=backend", f"app={app_label}"]:
        rc, out, _ = _run([
            "kubectl", "get", "pods", "-n", namespace,
            "-l", selector,
            "-o", "jsonpath={.items[0].metadata.name}",
        ])
        pod = out.strip()
        if rc == 0 and pod:
            return f"pod/{pod}"
    return f"deployment/{app_label}"


def http(
    method: str,
    url: str,
    body: Optional[dict] = None,
    form: bool = False,
) -> Tuple[int, Any]:
    """Make an HTTP request, return (status_code, parsed_body).

    Body is JSON by default; pass form=True for application/x-www-form-urlencoded.
    Returns the raw string if JSON decode fails.
    """
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            ct = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            ct = "application/json"
    else:
        data = None
        ct = "application/json"

    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", ct)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def get(url: str) -> Tuple[int, Any]:
    return http("GET", url)


def post(url: str, body: Optional[dict] = None) -> Tuple[int, Any]:
    return http("POST", url, body=body)


def post_form(url: str, body: dict) -> Tuple[int, str]:
    status, resp = http("POST", url, body=body, form=True)
    return status, resp if isinstance(resp, str) else json.dumps(resp)


# ─────────────────────────────────────────────────────────────────────────────
# Port-forward manager
# ─────────────────────────────────────────────────────────────────────────────

class PortForwardManager:
    """Opens kubectl port-forwards for every service and tracks local ports."""

    def __init__(self, namespace: str):
        self.namespace = namespace
        self._procs: Dict[str, subprocess.Popen] = {}
        self._ports: Dict[str, int] = {}

    def start(self) -> None:
        for name, cfg in SERVICES.items():
            local = _free_port()
            target = _resolve_pod(self.namespace, cfg["app"])
            proc = subprocess.Popen(
                [
                    "kubectl", "port-forward", "-n", self.namespace,
                    target, f"{local}:{cfg['port']}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 15
            ready = False
            while time.time() < deadline:
                try:
                    with socket.create_connection(("localhost", local), timeout=1):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.3)
                    if proc.poll() is not None:
                        break
            if not ready:
                proc.terminate()
                raise RuntimeError(
                    f"port-forward to {name} ({cfg['app']}:{cfg['port']}) "
                    f"did not become ready in 15 s"
                )
            self._procs[name] = proc
            self._ports[name] = local

    def stop(self) -> None:
        for proc in self._procs.values():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def url(self, name: str) -> str:
        return f"http://localhost:{self._ports[name]}"


# ─────────────────────────────────────────────────────────────────────────────
# Test result tracking
# ─────────────────────────────────────────────────────────────────────────────

class Results:
    def __init__(self) -> None:
        self._cats: Dict[str, list] = {}
        self._cur = ""

    def section(self, name: str) -> None:
        self._cur = name
        self._cats[name] = []
        print(f"\n  {name}")

    def check(self, label: str, passed: bool, detail: str = "") -> bool:
        icon = "\033[32m[PASS]\033[0m" if passed else "\033[31m[FAIL]\033[0m"
        suffix = f"  ← {detail}" if (detail and not passed) else (f"  — {detail}" if detail else "")
        print(f"    {icon} {label}{suffix}")
        self._cats[self._cur].append(passed)
        return passed

    @property
    def n_pass(self) -> int:
        return sum(v for cat in self._cats.values() for v in cat)

    @property
    def n_total(self) -> int:
        return sum(len(cat) for cat in self._cats.values())

    def all_passed(self) -> bool:
        return self.n_pass == self.n_total


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: AUTH
# ─────────────────────────────────────────────────────────────────────────────

def stage_auth(res: Results, pf: PortForwardManager, state: dict) -> bool:
    res.section("[AUTH]")
    base = pf.url("auth")
    run_id = state["run_id"]
    email = f"test_{run_id}@uvote-test.example.com"
    password = "TestPass123!"

    # 1. Register
    status, body = post(f"{base}/register", {"email": email, "password": password})
    ok = status == 201 and isinstance(body, dict) and "organiser_id" in body
    if ok:
        state["organiser_id"] = body["organiser_id"]
    res.check(f"POST /register → {status}", ok,
              "" if ok else str(body)[:100])

    # 2. Login
    status, body = post(f"{base}/login", {"email": email, "password": password})
    ok = status == 200 and isinstance(body, dict) and "token" in body
    if ok:
        state["jwt"] = body["token"]
        # auth service returns organiser_id (may be None if already set above)
        if body.get("organiser_id") is not None:
            state["organiser_id"] = body["organiser_id"]
    res.check(f"POST /login → {status}, JWT received", ok,
              "" if ok else str(body)[:100])

    if not state.get("jwt"):
        res.check("JWT structure valid", False, "no token to inspect")
        res.check("POST /login (wrong password) → 401", False, "skipped")
        return False

    # 3. JWT structure
    try:
        parts = state["jwt"].split(".")
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad))
        jwt_ok = (
            "organiser_id" in payload
            and "email" in payload
            and "exp" in payload
        )
    except Exception as exc:
        jwt_ok = False
        payload = {}
    res.check("JWT structure valid", jwt_ok,
              f"keys={list(payload.keys())}" if not jwt_ok else "")

    # 4. Wrong password → 401
    status, _ = post(f"{base}/login", {"email": email, "password": "WrongPass999!"})
    res.check(f"POST /login (wrong password) → {status}", status == 401)

    return bool(state.get("jwt") and state.get("organiser_id") is not None)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: ELECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def stage_elections(res: Results, pf: PortForwardManager, state: dict) -> bool:
    res.section("[ELECTIONS]")
    base = pf.url("election")
    run_id = state["run_id"]
    org_id = state.get("organiser_id")

    if org_id is None:
        for label in ["POST /elections", "GET /elections", "GET /elections/{id}"]:
            res.check(label, False, "skipped — no organiser_id")
        return False

    title = f"[TEST] {run_id}"

    # 1. Create election
    status, body = post(
        f"{base}/elections?organiser_id={org_id}",
        {"title": title, "description": "Integration test election",
         "options": ["Option A", "Option B", "Option C"]},
    )
    ok = status == 201 and isinstance(body, dict) and "election_id" in body
    if ok:
        state["election_id"] = body["election_id"]
    res.check(f"POST /elections → {status}, election created", ok,
              "" if ok else str(body)[:100])

    eid = state.get("election_id")
    if eid is None:
        res.check("GET /elections → list", False, "skipped — no election_id")
        res.check("GET /elections/{id}", False, "skipped — no election_id")
        return False

    # 2. List elections — test election appears
    status, body = get(f"{base}/elections?organiser_id={org_id}")
    ok = (
        status == 200
        and isinstance(body, dict)
        and any(e.get("id") == eid for e in body.get("elections", []))
    )
    res.check(f"GET /elections → {status}, test election in list", ok,
              "" if ok else f"ids={[e.get('id') for e in body.get('elections', [])]}")

    # 3. Get election detail
    status, body = get(f"{base}/elections/{eid}")
    ok = (
        status == 200
        and isinstance(body, dict)
        and body.get("election", {}).get("id") == eid
    )
    if ok:
        state["options"] = body.get("options", [])
    res.check(f"GET /elections/{eid} → {status}", ok,
              "" if ok else str(body)[:100])

    return eid is not None


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: VOTING
# ─────────────────────────────────────────────────────────────────────────────

def stage_voting(res: Results, pf: PortForwardManager, state: dict) -> bool:
    res.section("[VOTING]")
    eid = state.get("election_id")
    org_id = state.get("organiser_id")
    run_id = state["run_id"]

    if eid is None:
        for label in [
            "POST /elections/{id}/open",
            "POST /elections/{id}/voters (voter)",
            "POST /elections/{id}/tokens/generate",
            "GET auth/tokens/{token}/validate",
            "POST auth/mfa/verify",
            "POST auth/ballot-token/issue",
            "POST voting/vote/submit",
            "POST voting/vote/submit (duplicate)",
        ]:
            res.check(label, False, "skipped — no election_id")
        return False

    election_base = pf.url("election")
    auth_base = pf.url("auth")
    admin_base = pf.url("admin")
    vote_base = pf.url("voting")

    # Open election
    status, body = post(f"{election_base}/elections/{eid}/open?organiser_id={org_id}")
    ok = status == 200
    if ok:
        state["election_open"] = True
    res.check(f"POST /elections/{eid}/open → {status}", ok,
              "" if ok else str(body)[:100])

    # Add voter (unique email for this run)
    voter_email = f"voter_{run_id}@uvote-test.example.com"
    voter_dob = "1990-06-15"
    status, body = post(
        f"{admin_base}/elections/{eid}/voters",
        {"email": voter_email, "date_of_birth": voter_dob},
    )
    ok = status == 201
    if ok:
        state["voter_id"] = body.get("voter_id")
    res.check(f"POST /elections/{eid}/voters (voter) → {status}", ok,
              "" if ok else str(body)[:100])

    # Generate voting token directly via DB (SMTP unavailable in test cluster)
    # The tokens/generate endpoint generates tokens then emails them; the email
    # step hangs because outbound SMTP is blocked by network policy.  We test
    # the token-generation DB path by inserting a token directly and then
    # exercising every downstream endpoint (validate → MFA → ballot-token →
    # vote/submit) via the real API.
    voter_id = state.get("voter_id")
    voting_token: Optional[str] = None
    if voter_id is not None:
        raw_tok = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
        rc, _out, err = _run([
            "kubectl", "exec", "-n", pf.namespace, "deployment/postgresql",
            "--", "psql", "-U", "uvote_admin", "-d", "uvote",
            "-c",
            f"INSERT INTO voting_tokens (token, voter_id, election_id, expires_at) "
            f"VALUES ('{raw_tok}', {voter_id}, {eid}, NOW() + INTERVAL '7 days')",
        ])
        ok = rc == 0
        if ok:
            voting_token = raw_tok
            state["voting_token"] = voting_token
        res.check(
            "voting token inserted via DB (SMTP bypass)",
            ok,
            "" if ok else err[:100],
        )
    else:
        res.check("voting token inserted via DB (SMTP bypass)", False,
                  "skipped — voter_id missing")

    if voting_token is None:
        for label in [
            "GET auth/tokens/{token}/validate",
            "POST auth/mfa/verify (wrong DOB)",
            "POST auth/mfa/verify",
            "POST auth/ballot-token/issue",
            "POST voting/vote/submit",
            "POST voting/vote/submit (duplicate)",
        ]:
            res.check(label, False, "skipped — no voting token")
        return False

    # Validate voting token via auth-service
    status, body = get(f"{auth_base}/tokens/{voting_token}/validate")
    ok = status == 200 and isinstance(body, dict) and body.get("valid") is True
    res.check(
        f"GET auth/tokens/…/validate → {status}",
        ok,
        "" if ok else str(body)[:100],
    )

    # MFA failure path (wrong DOB — must run before successful verify)
    status, body = post(
        f"{auth_base}/mfa/verify?token={voting_token}&date_of_birth=1900-01-01"
    )
    ok = status in (400, 401)
    res.check(f"POST auth/mfa/verify (wrong DOB) → {status}", ok,
              "" if ok else str(body)[:100])

    # MFA identity verification (DOB)
    status, body = post(
        f"{auth_base}/mfa/verify?token={voting_token}&date_of_birth={voter_dob}"
    )
    ok = status == 200 and isinstance(body, dict) and body.get("verified") is True
    res.check(f"POST auth/mfa/verify → {status}", ok,
              "" if ok else str(body)[:100])

    # Issue blind ballot token (the anonymity bridge)
    status, body = post(f"{auth_base}/ballot-token/issue?token={voting_token}")
    ok = status == 200 and isinstance(body, dict) and "ballot_token" in body
    ballot_token: Optional[str] = None
    if ok:
        ballot_token = body["ballot_token"]
        state["ballot_token"] = ballot_token
    res.check(f"POST auth/ballot-token/issue → {status}", ok,
              "" if ok else str(body)[:100])

    if ballot_token is None:
        res.check("POST voting/vote/submit", False, "skipped — no ballot_token")
        res.check("POST voting/vote/submit (duplicate)", False, "skipped")
        return False

    # Choose first option from stored election detail
    options = state.get("options", [])
    option_id = options[0]["id"] if options else 1

    # Cast vote (form submission → returns HTML)
    status, html = post_form(
        f"{vote_base}/vote/submit",
        {"ballot_token": ballot_token, "option_id": option_id, "election_id": eid},
    )
    # Success page contains "receipt_token"; error page says "error" near the top
    success_indicators = ("receipt", "successfully cast", "vote submitted", "ballot hash")
    error_indicators = ("already been used", "invalid ballot", "election is not",
                        "encryption not configured")
    is_success = status == 200 and any(s in html.lower() for s in success_indicators)
    is_error = any(e in html.lower() for e in error_indicators)
    vote_ok = is_success and not is_error

    # Extract receipt_token from the verify link embedded in the page
    m = re.search(r'/vote/verify/([A-Za-z0-9_\-]{20,})', html)
    if m:
        state["receipt_token"] = m.group(1)

    res.check(
        f"POST voting/vote/submit → {status}",
        vote_ok,
        "" if vote_ok else html[:150].strip(),
    )

    # Duplicate vote (same ballot_token should be rejected)
    status2, html2 = post_form(
        f"{vote_base}/vote/submit",
        {"ballot_token": ballot_token, "option_id": option_id, "election_id": eid},
    )
    dup_rejected = status2 == 200 and any(
        phrase in html2.lower()
        for phrase in ("already been used", "invalid ballot token", "already used")
    )
    res.check(
        f"POST voting/vote/submit (duplicate) → error",
        dup_rejected,
        "" if dup_rejected else html2[:150].strip(),
    )

    return vote_ok


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: RESULTS
# ─────────────────────────────────────────────────────────────────────────────

def stage_results(res: Results, pf: PortForwardManager, state: dict) -> bool:
    res.section("[RESULTS]")
    eid = state.get("election_id")
    org_id = state.get("organiser_id")

    if eid is None:
        res.check("GET /elections/{id}/results", False, "skipped — no election_id")
        return False

    election_base = pf.url("election")
    results_base = pf.url("results")

    # Results before close should be blocked
    if state.get("election_open"):
        status, body = get(f"{results_base}/elections/{eid}/results")
        ok = status in (400, 403)
        res.check(
            f"GET /elections/{eid}/results (open) → {status}",
            ok,
            "" if ok else str(body)[:100],
        )

    # Close the election (required before results are visible)
    if state.get("election_open"):
        close_status, close_body = post(
            f"{election_base}/elections/{eid}/close?organiser_id={org_id}"
        )
        ok = close_status == 200
        res.check(f"POST /elections/{eid}/close → {close_status}", ok,
                  "" if ok else str(close_body)[:100])
        if ok:
            state["election_open"] = False
    else:
        # Already closed or never opened; still try to get results
        pass

    # Fetch results
    status, body = get(f"{results_base}/elections/{eid}/results")
    ok = (
        status == 200
        and isinstance(body, dict)
        and "election" in body
        and "summary" in body
        and "results" in body
    )
    total = body.get("summary", {}).get("total_votes", "?") if ok else "?"
    res.check(
        f"GET /elections/{eid}/results → {status}, total_votes={total}",
        ok,
        "" if ok else str(body)[:100],
    )

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

def stage_cleanup(res: Results, pf: PortForwardManager,
                  state: dict, keep: bool) -> None:
    res.section("[CLEANUP]")

    run_id = state["run_id"]
    eid = state.get("election_id")
    org_id = state.get("organiser_id")

    if keep:
        print(f"      --keep-data: test data preserved")
        print(f"      run_id:        {run_id}")
        if org_id:
            print(f"      organiser_id:  {org_id}")
            print(f"      email:         test_{run_id}@uvote-test.example.com")
        if eid:
            print(f"      election_id:   {eid}")
            print(f"      title:         [TEST] {run_id}")
        res.check("Data preserved (--keep-data)", True)
        return

    # Best-effort: ensure election is closed so it cannot receive more votes.
    # The API has no DELETE endpoints for elections or organisers.
    if eid and state.get("election_open"):
        election_base = pf.url("election")
        status, _ = post(
            f"{election_base}/elections/{eid}/close?organiser_id={org_id}"
        )
        closed = status == 200
        res.check(f"Election {eid} closed", closed)
        if closed:
            state["election_open"] = False
    else:
        res.check(f"Election {eid} already closed", True,
                  "no DELETE endpoint — data remains in DB")

    if eid:
        print(f"      NOTE: no DELETE endpoint — test data remains in the DB.")
        print(f"      To remove manually:")
        print(f"        kubectl exec -n uvote-dev deployment/postgresql -- \\")
        print(f"          psql -U uvote_admin -d uvote -c \\")
        print(f"          \"DELETE FROM elections WHERE title LIKE '[TEST] {run_id}%';\"")


# ─────────────────────────────────────────────────────────────────────────────
# Receipt verification (bonus check run after VOTING stage)
# ─────────────────────────────────────────────────────────────────────────────

def stage_receipt(res: Results, pf: PortForwardManager, state: dict) -> None:
    """Verify the vote receipt returned by the voting service."""
    rt = state.get("receipt_token")
    if not rt:
        return  # receipt wasn't captured; skip silently

    res.section("[RECEIPT]")
    vote_base = pf.url("voting")
    status, body = get(f"{vote_base}/receipt/{rt}")
    ok = status == 200 and isinstance(body, dict) and body.get("verified") is True
    res.check(
        f"GET /receipt/{rt[:10]}… → {status}, verified={body.get('verified') if isinstance(body, dict) else '?'}",
        ok,
        "" if ok else str(body)[:100],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: FRONTEND
# ─────────────────────────────────────────────────────────────────────────────

def stage_frontend(res: Results, pf: PortForwardManager, state: dict) -> None:
    res.section("[FRONTEND]")
    status, body = get(f"{pf.url('frontend')}/")
    res.check(f"GET / → {status}", status == 200,
              "" if status == 200 else str(body)[:100])


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="U-Vote API Integration Tests")
    parser.add_argument("--namespace", default="uvote-dev",
                        help="Kubernetes namespace (default: uvote-dev)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show extra debug output")
    parser.add_argument("--keep-data", action="store_true",
                        help="Skip cleanup — leave test data in the database")
    args = parser.parse_args()

    SEP = "═" * 40
    print(f"\n{SEP}")
    print("  U-Vote API Integration Tests")
    print(SEP)

    state: dict = {"run_id": uuid.uuid4().hex[:8]}
    res = Results()
    pf = PortForwardManager(args.namespace)

    print(f"\n  Starting port-forwards (namespace: {args.namespace})…")
    try:
        pf.start()
    except RuntimeError as exc:
        print(f"\n  \033[31mFATAL:\033[0m {exc}")
        sys.exit(1)
    print(f"  ✓ {len(SERVICES)} port-forwards ready\n")

    t0 = time.time()
    try:
        stage_auth(res, pf, state)
        stage_frontend(res, pf, state)
        stage_elections(res, pf, state)
        stage_voting(res, pf, state)
        stage_receipt(res, pf, state)
        stage_results(res, pf, state)
        stage_cleanup(res, pf, state, args.keep_data)
    finally:
        elapsed = time.time() - t0
        pf.stop()

        print(f"\n{SEP}")
        colour = "\033[32m" if res.all_passed() else "\033[31m"
        print(f"  {colour}Results: {res.n_pass}/{res.n_total} passed\033[0m")
        print(f"  Time: {elapsed:.1f}s")
        print(SEP + "\n")

    sys.exit(0 if res.all_passed() else 1)


if __name__ == "__main__":
    main()
