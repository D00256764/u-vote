#!/usr/bin/env python3
"""
U-Vote Database Test Suite
==========================
Comprehensive testing of the PostgreSQL database deployed via Kubernetes
for the U-Vote secure voting platform.

The suite validates the full database stack across five categories:
  1. Infrastructure  - Pod health and connectivity
  2. Schema          - Tables, indexes, and foreign-key constraints
  3. Data            - Sample/seed data presence
  4. Security        - Vote immutability triggers, least-privilege users
  5. Performance     - Index existence, optional bulk-insert load test

Every test result (PASS / FAIL / WARN) is printed with colour to the
terminal AND written to a timestamped log file under plat_scripts/logs/.

Usage:
    python test_db.py                  # Run all tests
    python test_db.py --quick          # Skip slow tests (pod network, load)
    python test_db.py --load 5000      # Include load test with 5 000 votes
    python test_db.py --pod <name>     # Target a specific pod by name

Exit codes:
    0  - All tests passed (warnings are acceptable)
    1  - One or more tests failed
    130 - Interrupted by user (Ctrl-C)
"""

import subprocess
import sys
import argparse
import logging
import base64
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Optional

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

# Target Kubernetes namespace where the database is deployed
K8S_NAMESPACE = "uvote-dev"

# Default database credentials used for psql connections via kubectl exec
DB_USER = "uvote_admin"
DB_NAME = "uvote"


class Colors:
    """ANSI escape codes for coloured terminal output.

    Used by the print_* helper functions to highlight test results.
    Every colour string must be terminated with ``ENDC`` to reset formatting.
    """

    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


# Global logger instance - initialised once at the start of main().
# Kept at module level so every helper and test function can write to the
# same log file without passing the logger around explicitly.
logger: Optional[logging.Logger] = None


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Create a file logger that writes to ``plat_scripts/logs/test_db_<timestamp>.log``.

    The ``logs/`` directory is created automatically if it does not exist.
    Only file output is configured; console output is handled separately by
    the coloured ``print_*`` helpers so that ANSI codes stay out of the log.

    Returns:
        logging.Logger: Configured logger with a single FileHandler.
    """
    script_dir = Path(__file__).resolve().parent
    log_dir = script_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"test_db_{timestamp}.log"

    log = logging.getLogger("uvote_db_test")
    log.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    log.addHandler(fh)

    log.info("U-Vote Database Test Suite started")
    log.info(f"Log file: {log_file}")

    return log


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class TestResults:
    """Accumulator for test outcomes.

    Every test function calls one of ``add_pass``, ``add_fail``, or
    ``add_warning`` exactly once (some call more for sub-checks).  The
    totals and per-test details are used by ``main()`` to print the
    final summary and to decide the process exit code.

    Attributes:
        passed:   Number of passed checks.
        failed:   Number of failed checks.
        warnings: Number of non-fatal warnings.
        tests:    Ordered list of ``(status, name, details)`` tuples.
    """

    def __init__(self):
        self.passed: int = 0
        self.failed: int = 0
        self.warnings: int = 0
        self.tests: List[Tuple[str, str, str]] = []

    def add_pass(self, test_name: str, details: str = "") -> None:
        """Record a passing check and log it at INFO level."""
        self.passed += 1
        self.tests.append(("PASS", test_name, details))
        if logger:
            logger.info(f"RESULT | PASS | {test_name} | {details}")

    def add_fail(self, test_name: str, details: str = "") -> None:
        """Record a failing check and log it at ERROR level."""
        self.failed += 1
        self.tests.append(("FAIL", test_name, details))
        if logger:
            logger.error(f"RESULT | FAIL | {test_name} | {details}")

    def add_warning(self, test_name: str, details: str = "") -> None:
        """Record a non-fatal warning and log it at WARNING level."""
        self.warnings += 1
        self.tests.append(("WARN", test_name, details))
        if logger:
            logger.warning(f"RESULT | WARN | {test_name} | {details}")

    def summary(self) -> str:
        """Return a one-line summary string, e.g. ``Total: 11 | Passed: 10 | ...``."""
        total = self.passed + self.failed + self.warnings
        return f"Total: {total} | Passed: {self.passed} | Failed: {self.failed} | Warnings: {self.warnings}"


# ---------------------------------------------------------------------------
# Coloured console output helpers
# ---------------------------------------------------------------------------
# Each function prints to the terminal with ANSI colours AND mirrors the
# message to the log file (without colour codes) when the logger is active.

def print_header(message: str) -> None:
    """Print a prominent section header surrounded by ``=`` bars."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")

def print_test(test_num: int, message: str) -> None:
    """Print a numbered test banner, e.g. ``[Test 3] Required Tables Exist``."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[Test {test_num}]{Colors.ENDC} {Colors.BOLD}{message}{Colors.ENDC}")
    if logger:
        logger.info(f"--- [Test {test_num}] {message} ---")

def print_pass(message: str) -> None:
    """Print a green PASS line."""
    print(f"{Colors.GREEN}✅ PASS: {message}{Colors.ENDC}")
    if logger:
        logger.info(f"  PASS: {message}")

def print_fail(message: str) -> None:
    """Print a red FAIL line."""
    print(f"{Colors.RED}❌ FAIL: {message}{Colors.ENDC}")
    if logger:
        logger.error(f"  FAIL: {message}")

def print_warning(message: str) -> None:
    """Print a yellow WARN line."""
    print(f"{Colors.YELLOW}⚠️  WARN: {message}{Colors.ENDC}")
    if logger:
        logger.warning(f"  WARN: {message}")

def print_info(message: str) -> None:
    """Print a blue informational line."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")
    if logger:
        logger.info(f"  INFO: {message}")


# ---------------------------------------------------------------------------
# Kubernetes / PostgreSQL execution helpers
# ---------------------------------------------------------------------------

def run_kubectl(
    args: List[str],
    capture: bool = True,
    input_data: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Tuple[bool, str, str]:
    """Execute a ``kubectl`` command as a subprocess.

    Args:
        args:       Arguments appended after ``kubectl`` (e.g. ``['get', 'pods']``).
        capture:    When True (default), capture stdout/stderr and return them.
                    When False, let output go directly to the terminal.
        input_data: Optional string piped to the command's stdin.
        timeout:    Maximum wall-clock seconds before the process is killed.
                    ``None`` means no limit.

    Returns:
        A ``(success, stdout, stderr)`` tuple.  ``success`` is True when the
        process exits with code 0.  When *capture* is False, stdout and
        stderr are returned as empty strings.
    """
    cmd = ['kubectl'] + args
    if logger:
        logger.debug(f"CMD: {' '.join(cmd)}")
    try:
        if input_data:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout
            )
        elif capture:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
        else:
            # Non-captured mode: output streams go straight to the terminal
            result = subprocess.run(cmd, check=False, timeout=timeout)
            return result.returncode == 0, "", ""

        # Log truncated output for post-mortem debugging
        if logger:
            if result.stdout.strip():
                logger.debug(f"STDOUT: {result.stdout.strip()[:500]}")
            if result.stderr.strip():
                logger.debug(f"STDERR: {result.stderr.strip()[:500]}")

        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        msg = f"Command timed out after {timeout}s"
        if logger:
            logger.error(f"TIMEOUT: {' '.join(cmd)} ({timeout}s)")
        return False, "", msg
    except Exception as e:
        if logger:
            logger.error(f"EXCEPTION: {e}")
        return False, "", str(e)


def get_postgres_pod() -> Optional[str]:
    """Auto-detect the PostgreSQL pod name via its ``app=postgresql`` label.

    Returns:
        The pod name string, or ``None`` if no matching pod was found.
    """
    success, stdout, _ = run_kubectl([
        'get', 'pod',
        '-n', K8S_NAMESPACE,
        '-l', 'app=postgresql',
        '-o', 'jsonpath={.items[0].metadata.name}'
    ])

    if success and stdout.strip():
        return stdout.strip()
    return None


def get_db_password() -> Optional[str]:
    """Retrieve the database password from the ``db-credentials`` Kubernetes Secret.

    The secret stores the value as base64-encoded data (even when defined
    with ``stringData`` in the manifest).  This function decodes it back to
    plain text.

    Returns:
        The decoded password string, or ``None`` on failure.
    """
    success, stdout, _ = run_kubectl([
        'get', 'secret', 'db-credentials',
        '-n', K8S_NAMESPACE,
        '-o', 'jsonpath={.data.password}'
    ])
    if success and stdout.strip():
        try:
            return base64.b64decode(stdout.strip()).decode('utf-8')
        except Exception:
            # Secret may already be in plain text in rare edge cases
            return stdout.strip()
    return None


def exec_psql(
    pod: str,
    sql: str,
    user: str = DB_USER,
    database: str = DB_NAME,
) -> Tuple[bool, str, str]:
    """Run a single SQL statement inside the PostgreSQL pod via ``kubectl exec``.

    Uses the pod-local ``psql`` binary, so no password is needed (``trust``
    authentication applies for local connections inside the container).

    Args:
        pod:      Name of the PostgreSQL pod.
        sql:      SQL statement or psql meta-command (e.g. ``\\dt``).
        user:     PostgreSQL role to connect as.
        database: Target database name.

    Returns:
        ``(success, stdout, stderr)`` - same contract as ``run_kubectl``.
    """
    return run_kubectl([
        'exec', '-i', '-n', K8S_NAMESPACE, pod, '--',
        'psql', '-U', user, '-d', database, '-c', sql
    ])


# ---------------------------------------------------------------------------
# Shared pre-check helpers
# ---------------------------------------------------------------------------

def ensure_pgcrypto(pod: str) -> bool:
    """Ensure the ``pgcrypto`` PostgreSQL extension is installed.

    The ``generate_vote_hash`` trigger uses ``digest()`` from pgcrypto to
    produce SHA-256 hashes on every INSERT into the ``votes`` table.  If
    the extension is missing, *any* vote INSERT will fail, which would
    cascade into false failures for Tests 5 and 6.

    If pgcrypto is not yet installed this function attempts to create it.

    Args:
        pod: Name of the PostgreSQL pod.

    Returns:
        True if pgcrypto is now available, False otherwise.
    """
    success, stdout, _ = exec_psql(pod, "SELECT extname FROM pg_extension WHERE extname = 'pgcrypto';")
    if success and 'pgcrypto' in stdout:
        return True

    # Extension is missing - try to create it (requires superuser or CREATE privilege)
    print_warning("pgcrypto extension not found, attempting to create...")
    success, _, stderr = exec_psql(pod, "CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    if not success:
        print_fail("pgcrypto extension is required but could not be created")
        print_info(f"Error: {stderr[:150]}")
        if logger:
            logger.error(f"pgcrypto creation failed: {stderr}")
        return False
    print_pass("pgcrypto extension created successfully")
    return True


# ===========================================================================
# Test functions
# ===========================================================================
# Naming convention: test_<feature>(pod, results) -> bool
# Each test prints coloured output, records its outcome in *results*,
# and returns True on success.


def test_pod_running(results: TestResults) -> Optional[str]:
    """Test 1 -- Verify the PostgreSQL pod is Running and fully ready (1/1).

    This is the gate-keeper test: if the pod is not healthy, all subsequent
    tests are skipped because they depend on ``kubectl exec`` into the pod.

    Args:
        results: Shared result accumulator.

    Returns:
        The pod name on success, or ``None`` if the pod is not available.
    """
    print_test(1, "Database Pod Running")

    success, stdout, stderr = run_kubectl([
        'get', 'pods', '-n', K8S_NAMESPACE, '-l', 'app=postgresql'
    ])

    if not success:
        print_fail("Failed to get pod status")
        results.add_fail("Pod Running", stderr)
        return None

    # Look for both "Running" status and "1/1" ready containers
    if 'Running' in stdout and '1/1' in stdout:
        pod = get_postgres_pod()
        print_pass(f"Database pod is running: {pod}")
        results.add_pass("Pod Running", pod)
        return pod
    else:
        print_fail("Database pod is not running")
        print_info("Pod status:")
        print(stdout)
        results.add_fail("Pod Running", "Pod not in Running state")
        return None


def test_connection(pod: str, results: TestResults) -> bool:
    """Test 2 -- Confirm psql can connect and retrieve the server version.

    A successful ``SELECT version()`` proves both TCP connectivity and
    authentication from inside the pod.

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if the connection succeeds.
    """
    print_test(2, "Database Connection")

    success, stdout, stderr = exec_psql(pod, "SELECT version();")

    if success and 'PostgreSQL' in stdout:
        version_line = [line for line in stdout.split('\n') if 'PostgreSQL' in line]
        if version_line:
            version = version_line[0].strip()
            print_pass(f"Connection successful")
            print_info(f"Version: {version}")
            results.add_pass("Connection", version)
            return True

    print_fail("Failed to connect to database")
    print_info(f"Error: {stderr}")
    results.add_fail("Connection", stderr)
    return False


def test_tables_exist(pod: str, results: TestResults) -> bool:
    """Test 3 -- Verify all seven required tables are present.

    Expected tables (defined in ``schema.sql``):
        admins, elections, candidates, voters, voting_tokens, votes, audit_logs

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if every expected table is found.
    """
    print_test(3, "Required Tables Exist")

    expected_tables = [
        'admins', 'elections', 'candidates', 'voters',
        'voting_tokens', 'votes', 'audit_logs'
    ]

    # psql meta-command \dt lists all tables in the public schema
    success, stdout, stderr = exec_psql(pod, "\\dt")

    if not success:
        print_fail("Failed to list tables")
        results.add_fail("Tables Exist", stderr)
        return False

    found_tables = []
    missing_tables = []

    for table in expected_tables:
        if table in stdout:
            found_tables.append(table)
        else:
            missing_tables.append(table)

    if len(found_tables) == len(expected_tables):
        print_pass(f"All {len(expected_tables)} required tables exist")
        for table in found_tables:
            print_info(f"  ✓ {table}")
        results.add_pass("Tables Exist", f"{len(found_tables)}/{len(expected_tables)} tables")
        return True
    else:
        print_fail(f"Missing {len(missing_tables)} tables")
        for table in missing_tables:
            print_info(f"  ✗ {table}")
        results.add_fail("Tables Exist", f"Missing: {', '.join(missing_tables)}")
        return False


def test_sample_data(pod: str, results: TestResults) -> bool:
    """Test 4 -- Check that seed data was loaded into core tables.

    The schema's ``INSERT`` statements at the bottom of ``schema.sql``
    populate admins (1 row), elections (1 row), and candidates (3 rows).

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if all three tables contain at least one row.
    """
    print_test(4, "Sample Data Loaded")

    tests_passed = True

    # Check admins
    success, stdout, _ = exec_psql(pod, "SELECT COUNT(*) FROM admins;")
    if success:
        # psql output: header, separator, value, row-count footer
        # The count value is on the second-to-last line
        count = stdout.strip().split('\n')[-2].strip() if '\n' in stdout else '0'
        if count.isdigit() and int(count) > 0:
            print_pass(f"Admins table has {count} record(s)")
        else:
            print_fail("Admins table is empty")
            tests_passed = False

    # Check elections
    success, stdout, _ = exec_psql(pod, "SELECT COUNT(*) FROM elections;")
    if success:
        count = stdout.strip().split('\n')[-2].strip() if '\n' in stdout else '0'
        if count.isdigit() and int(count) > 0:
            print_pass(f"Elections table has {count} record(s)")
        else:
            print_fail("Elections table is empty")
            tests_passed = False

    # Check candidates
    success, stdout, _ = exec_psql(pod, "SELECT COUNT(*) FROM candidates;")
    if success:
        count = stdout.strip().split('\n')[-2].strip() if '\n' in stdout else '0'
        if count.isdigit() and int(count) > 0:
            print_pass(f"Candidates table has {count} record(s)")
        else:
            print_fail("Candidates table is empty")
            tests_passed = False

    if tests_passed:
        results.add_pass("Sample Data", "All sample data loaded")
    else:
        results.add_fail("Sample Data", "Some sample data missing")

    return tests_passed


def test_vote_immutability(pod: str, results: TestResults) -> bool:
    """Test 5 -- Verify that votes cannot be updated or deleted.

    The ``prevent_vote_update`` and ``prevent_vote_delete`` BEFORE triggers
    raise an exception on any UPDATE or DELETE against the ``votes`` table,
    enforcing ballot immutability.

    Approach:
      1. Ensure pgcrypto is loaded (the hash trigger fires on INSERT).
      2. Confirm both immutability triggers exist in ``pg_trigger``.
      3. INSERT a test vote (must succeed).
      4. Attempt UPDATE - expect failure with the trigger's error message.
      5. Attempt DELETE - expect failure with the trigger's error message.

    Note: PostgreSQL does not support ``LIMIT`` directly on UPDATE/DELETE
    statements.  We use a subquery (``WHERE vote_id = (SELECT ... LIMIT 1)``)
    to target a single row instead.

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if votes are confirmed immutable.
    """
    print_test(5, "Vote Immutability (Security)")

    # Pre-check: pgcrypto must be present for the INSERT to succeed
    # because the generate_vote_hash trigger calls digest() from pgcrypto
    print_info("Checking pgcrypto extension (required by vote hash trigger)...")
    if not ensure_pgcrypto(pod):
        results.add_fail("Vote Immutability", "pgcrypto extension unavailable — cannot insert test vote")
        return False

    # Pre-check: verify immutability triggers exist
    print_info("Checking immutability triggers...")
    success, stdout, _ = exec_psql(pod,
        "SELECT tgname FROM pg_trigger WHERE tgrelid = 'votes'::regclass AND tgname LIKE 'prevent_vote%';")
    if not success or 'prevent_vote' not in stdout:
        print_fail("Immutability triggers not found on votes table")
        print_info("Expected triggers: prevent_vote_update, prevent_vote_delete")
        if logger:
            logger.error(f"Missing immutability triggers. pg_trigger output: {stdout}")
        results.add_fail("Vote Immutability", "Triggers not installed")
        return False
    print_pass("Immutability triggers are installed")

    # Insert a test vote (the hash trigger will also fire here)
    print_info("Inserting test vote...")
    success, stdout, stderr = exec_psql(pod, "INSERT INTO votes (election_id, candidate_id) VALUES (1, 1);")

    if not success:
        print_fail(f"Failed to insert test vote: {stderr[:100]}")
        results.add_fail("Vote Immutability", "Cannot insert vote")
        return False

    # Attempt UPDATE -- should be blocked by prevent_vote_update trigger
    # Uses a subquery because PostgreSQL does not allow LIMIT on UPDATE
    print_info("Attempting to UPDATE vote (should fail)...")
    success, stdout, stderr = exec_psql(pod,
        "UPDATE votes SET candidate_id = 2 WHERE vote_id = (SELECT vote_id FROM votes WHERE election_id = 1 LIMIT 1);")

    if success:
        print_fail("SECURITY RISK: Vote was updated (trigger not working)")
        results.add_fail("Vote Immutability", "UPDATE not blocked")
        return False
    else:
        if "Votes cannot be modified or deleted" in stderr:
            print_pass("UPDATE correctly blocked by trigger")
        else:
            print_warning(f"UPDATE blocked but unexpected error: {stderr[:100]}")

    # Attempt DELETE -- should be blocked by prevent_vote_delete trigger
    # Uses a subquery because PostgreSQL does not allow LIMIT on DELETE
    print_info("Attempting to DELETE vote (should fail)...")
    success, stdout, stderr = exec_psql(pod,
        "DELETE FROM votes WHERE vote_id = (SELECT vote_id FROM votes WHERE election_id = 1 LIMIT 1);")

    if success:
        print_fail("SECURITY RISK: Vote was deleted (trigger not working)")
        results.add_fail("Vote Immutability", "DELETE not blocked")
        return False
    else:
        if "Votes cannot be modified or deleted" in stderr:
            print_pass("DELETE correctly blocked by trigger")
            results.add_pass("Vote Immutability", "Votes are immutable")
            return True
        else:
            print_warning(f"DELETE blocked but unexpected error: {stderr[:100]}")
            results.add_warning("Vote Immutability", "Blocked with unexpected error")
            return True


def test_hash_generation(pod: str, results: TestResults) -> bool:
    """Test 6 -- Verify that the hash-chain trigger generates vote hashes.

    The ``generate_vote_hash_trigger`` fires BEFORE INSERT on ``votes`` and:
      - Looks up the most recent ``vote_hash`` for the same election.
      - Sets ``previous_hash`` to that value (or 64 zeroes for the first vote).
      - Computes ``vote_hash = SHA-256(election_id || candidate_id || cast_at || previous_hash)``
        using ``pgcrypto``'s ``digest()`` function.

    This creates a hash chain per election, allowing integrity verification.

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if newly inserted votes have non-NULL hashes.
    """
    print_test(6, "Automatic Hash Generation (Hash Chain)")

    # Pre-check: pgcrypto must be present for digest() to work
    print_info("Checking pgcrypto extension...")
    if not ensure_pgcrypto(pod):
        results.add_fail("Hash Generation", "pgcrypto extension unavailable")
        return False

    # Pre-check: verify the hash generation trigger is present
    print_info("Checking hash generation trigger...")
    success, stdout, _ = exec_psql(pod,
        "SELECT tgname FROM pg_trigger WHERE tgrelid = 'votes'::regclass AND tgname = 'generate_vote_hash_trigger';")
    if not success or 'generate_vote_hash_trigger' not in stdout:
        print_fail("Hash generation trigger not found on votes table")
        if logger:
            logger.error(f"Missing hash trigger. pg_trigger output: {stdout}")
        results.add_fail("Hash Generation", "Trigger not installed")
        return False
    print_pass("Hash generation trigger is installed")

    # Insert 3 test votes across the 3 candidates to exercise the hash chain
    print_info("Inserting 3 test votes...")
    for i in range(3):
        success, _, stderr = exec_psql(pod, f"INSERT INTO votes (election_id, candidate_id) VALUES (1, {(i % 3) + 1});")
        if not success:
            print_fail(f"Failed to insert test vote {i+1}: {stderr[:100]}")
            results.add_fail("Hash Generation", f"Insert failed: {stderr[:100]}")
            return False

    # Query the most recent votes and check whether hashes were populated
    success, stdout, _ = exec_psql(pod, """
        SELECT
            vote_id,
            LEFT(vote_hash, 16) as hash_preview,
            LEFT(previous_hash, 16) as prev_hash_preview,
            CASE WHEN vote_hash IS NULL THEN 'NO' ELSE 'YES' END as has_hash
        FROM votes
        ORDER BY vote_id DESC
        LIMIT 5;
    """)

    if not success:
        print_fail("Failed to query vote hashes")
        results.add_fail("Hash Generation", "Query failed")
        return False

    # A 'YES' in the has_hash column means the trigger populated vote_hash
    if 'YES' in stdout:
        hash_count = stdout.count('YES')
        print_pass(f"Votes have hashes generated: {hash_count} votes checked")
        print_info("Hash chain preview:")
        print(stdout)
        results.add_pass("Hash Generation", f"{hash_count} votes with hashes")
        return True
    else:
        print_fail("Votes do not have hashes")
        results.add_fail("Hash Generation", "No hashes generated")
        return False


def test_user_permissions(pod: str, results: TestResults) -> bool:
    """Test 7 -- Validate least-privilege access for service database roles.

    The schema creates dedicated roles for each micro-service with only
    the minimum grants they need.  This test spot-checks two of them:

    * **auth_service** - should SELECT admins, but NOT access votes.
    * **results_service** - should SELECT votes (read-only), but NOT INSERT.

    A failure here is flagged as a security risk because it means a
    compromised service could access data outside its scope.

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if all permission checks pass.
    """
    print_test(7, "User Permissions (Least Privilege)")

    all_passed = True

    # --- auth_service checks ---
    print_info("Testing auth_service user...")

    # Should SUCCEED: auth_service has SELECT on admins
    success, _, _ = exec_psql(pod, "SELECT COUNT(*) FROM admins;", user="auth_service")
    if success:
        print_pass("auth_service can SELECT from admins ✓")
    else:
        print_fail("auth_service cannot SELECT from admins")
        all_passed = False

    # Should FAIL: auth_service has NO grants on votes
    success, _, stderr = exec_psql(pod, "SELECT COUNT(*) FROM votes;", user="auth_service")
    if not success and "permission denied" in stderr.lower():
        print_pass("auth_service correctly denied access to votes ✓")
    else:
        print_fail("SECURITY RISK: auth_service has access to votes")
        all_passed = False

    # --- results_service checks (read-only role) ---
    print_info("Testing results_service user (read-only)...")

    # Should SUCCEED: results_service has SELECT on votes
    success, _, _ = exec_psql(pod, "SELECT COUNT(*) FROM votes;", user="results_service")
    if success:
        print_pass("results_service can SELECT from votes ✓")
    else:
        print_fail("results_service cannot SELECT from votes")
        all_passed = False

    # Should FAIL: results_service has no INSERT on votes
    success, _, stderr = exec_psql(pod, "INSERT INTO votes (election_id, candidate_id) VALUES (1, 1);", user="results_service")
    if not success and "permission denied" in stderr.lower():
        print_pass("results_service correctly denied INSERT to votes ✓")
    else:
        print_fail("SECURITY RISK: results_service can INSERT into votes")
        all_passed = False

    if all_passed:
        results.add_pass("User Permissions", "All permissions correct")
    else:
        results.add_fail("User Permissions", "Some permissions incorrect")

    return all_passed


def test_complex_queries(pod: str, results: TestResults) -> bool:
    """Test 8 -- Run an election results tally query.

    Exercises a multi-table JOIN with aggregation that mirrors what the
    results micro-service would execute:
      - JOIN candidates to votes on candidate_id
      - GROUP BY candidate, COUNT votes, compute percentage

    This validates that the schema relationships support real query patterns.

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if the tally query returns rows with a 'candidate' column.
    """
    print_test(8, "Complex Queries (Vote Tallying)")

    success, stdout, stderr = exec_psql(pod, """
        SELECT
            c.name as candidate,
            COUNT(v.vote_id) as votes,
            ROUND(COUNT(v.vote_id)::numeric / NULLIF((SELECT COUNT(*) FROM votes WHERE election_id = 1), 0) * 100, 2) as percentage
        FROM candidates c
        LEFT JOIN votes v ON c.candidate_id = v.candidate_id
        WHERE c.election_id = 1
        GROUP BY c.candidate_id, c.name
        ORDER BY votes DESC;
    """)

    if success and 'candidate' in stdout.lower():
        print_pass("Vote tallying query successful")
        print_info("Current vote tally:")
        lines = stdout.split('\n')
        for line in lines:
            if line.strip() and not line.startswith('('):
                print(f"  {line}")
        results.add_pass("Complex Queries", "Tally calculation works")
        return True
    else:
        print_fail("Vote tallying query failed")
        print_info(f"Error: {stderr}")
        results.add_fail("Complex Queries", stderr)
        return False


def test_indexes(pod: str, results: TestResults) -> bool:
    """Test 9 -- Confirm that performance indexes exist.

    The schema defines several indexes to speed up common query patterns.
    This test checks for three critical ones:
      - ``idx_votes_election``  - fast lookup of votes by election
      - ``idx_votes_candidate`` - fast lookup of votes by candidate
      - ``idx_tokens_token``    - fast token validation lookups

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if at least one expected index is found.
    """
    print_test(9, "Database Indexes (Performance)")

    success, stdout, _ = exec_psql(pod, """
        SELECT
            tablename,
            indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)

    if not success:
        print_fail("Failed to query indexes")
        results.add_fail("Indexes", "Query failed")
        return False

    expected_indexes = ['idx_votes_election', 'idx_votes_candidate', 'idx_tokens_token']
    found_indexes = []

    for idx in expected_indexes:
        if idx in stdout:
            found_indexes.append(idx)

    if found_indexes:
        print_pass(f"Found {len(found_indexes)} performance indexes")
        for idx in found_indexes:
            print_info(f"  ✓ {idx}")
        results.add_pass("Indexes", f"{len(found_indexes)} indexes found")
        return True
    else:
        print_warning("No expected indexes found")
        results.add_warning("Indexes", "No indexes found")
        return False


def test_foreign_keys(pod: str, results: TestResults) -> bool:
    """Test 10 -- Check that foreign key constraints are in place.

    Queries ``information_schema.table_constraints`` for all FOREIGN KEY
    constraints in the public schema.  The presence of FK constraints
    ensures referential integrity (e.g. a vote must reference a valid
    election and candidate).

    Args:
        pod:     PostgreSQL pod name.
        results: Shared result accumulator.

    Returns:
        True if at least one foreign key constraint is found.
    """
    print_test(10, "Foreign Key Constraints (Data Integrity)")

    success, stdout, _ = exec_psql(pod, """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name;
    """)

    if success and 'table_name' in stdout.lower():
        # Heuristic: count mentions of known FK-related table names
        fk_count = stdout.count('_fkey') + stdout.count('elections') + stdout.count('candidates')
        if fk_count > 0:
            print_pass(f"Foreign key constraints present")
            print_info("Sample constraints:")
            lines = [l for l in stdout.split('\n') if l.strip() and 'table_name' not in l.lower()][:5]
            for line in lines:
                if line.strip() and not line.startswith('('):
                    print(f"  {line.strip()}")
            results.add_pass("Foreign Keys", "Constraints exist")
            return True

    print_warning("Could not verify foreign keys")
    results.add_warning("Foreign Keys", "Verification inconclusive")
    return False


def test_connection_from_pod(pod: str, results: TestResults) -> bool:
    """Test 11 -- Verify network connectivity from a separate pod.

    Spins up a temporary ``postgres:15-alpine`` pod in the same namespace
    and attempts to connect to the ``postgresql`` ClusterIP service.  This
    validates that:
      - The Kubernetes Service is routing traffic correctly.
      - Network policies (e.g. Calico) allow pod-to-pod DB access.
      - Password-based authentication works over the network (not just
        local trust auth inside the DB pod).

    The ``PGPASSWORD`` environment variable is set explicitly to prevent
    ``psql`` from blocking on an interactive password prompt, which was the
    root cause of the original hang.  A 10-second subprocess timeout acts
    as a safety net.

    Pod cleanup timeouts are set to 35s to accommodate Kubernetes' default
    30-second graceful termination period.

    Args:
        pod:     PostgreSQL pod name (unused directly, but kept for API
                 consistency with other test functions).
        results: Shared result accumulator.

    Returns:
        True if the remote pod can query the database successfully.
    """
    print_test(11, "Service Connection (Network)")

    # Retrieve the password from the Kubernetes secret so we can set PGPASSWORD
    db_password = get_db_password()
    if not db_password:
        print_warning("Could not retrieve password from secret, using dev fallback")
        db_password = "dev_password_CHANGE_IN_PROD"

    print_info("Deploying test client pod...")

    # Clean up any leftover test pod from a previous interrupted run
    run_kubectl([
        'delete', 'pod', 'db-test-client', '-n', K8S_NAMESPACE, '--ignore-not-found'
    ], timeout=35)

    # Create an ephemeral pod with the psql client available.
    # Labels app=auth-service (network policy whitelist) and
    # purpose=network-policy-testing (matches test-pods.yaml pattern)
    # are required for Calico to permit egress to PostgreSQL on port 5432.
    success, _, stderr = run_kubectl([
        'run', 'db-test-client',
        '--image=postgres:15-alpine',
        '-n', K8S_NAMESPACE,
        '--restart=Never',
        '--labels=app=auth-service,purpose=network-policy-testing',
        '--', 'sleep', '3600'
    ], timeout=35)

    if not success:
        print_warning(f"Failed to create test pod: {stderr[:100]}")

    # Block until the pod is Ready (up to 60s inside kubectl, 70s subprocess limit)
    print_info("Waiting for test pod...")
    success, _, stderr = run_kubectl([
        'wait', '--for=condition=Ready',
        'pod/db-test-client',
        '-n', K8S_NAMESPACE,
        '--timeout=60s'
    ], timeout=70)

    if not success:
        print_fail("Test pod did not become ready")
        print_info(f"Error: {stderr[:150]}")
        run_kubectl(['delete', 'pod', 'db-test-client', '-n', K8S_NAMESPACE, '--ignore-not-found'], timeout=35)
        results.add_fail("Service Connection", "Test pod not ready")
        return False

    # Connect to the DB service from the client pod.
    # PGPASSWORD is injected via 'sh -c' to avoid the interactive password prompt
    # that caused the original Test 11 hang.  10s timeout as a safety net.
    print_info("Testing connection from client pod...")
    success, stdout, stderr = run_kubectl([
        'exec', '-i', '-n', K8S_NAMESPACE, 'db-test-client', '--',
        'sh', '-c',
        f"PGPASSWORD='{db_password}' psql -h postgresql -U {DB_USER} -d {DB_NAME} "
        f"-c \"SELECT 'Connection from pod successful!' as status;\""
    ], timeout=10)

    # Always clean up the ephemeral test pod (35s to cover graceful shutdown)
    print_info("Cleaning up test pod...")
    run_kubectl(['delete', 'pod', 'db-test-client', '-n', K8S_NAMESPACE, '--ignore-not-found'], timeout=35)

    if success and 'Connection from pod successful' in stdout:
        print_pass("Connection from another pod works")
        results.add_pass("Service Connection", "Pod-to-pod connection OK")
        return True
    else:
        print_fail("Failed to connect from another pod")
        print_info(f"Error: {stderr[:200]}")
        results.add_fail("Service Connection", stderr[:200])
        return False


def test_load_performance(pod: str, results: TestResults, num_votes: int = 1000) -> bool:
    """Test 12 (optional) -- Bulk-insert votes and verify distribution.

    Uses ``generate_series`` to insert *num_votes* rows in a single
    statement.  Each vote is assigned a random candidate (1-3) to
    produce a roughly uniform distribution.

    This is useful for:
      - Smoke-testing the hash trigger under load.
      - Verifying that indexes keep query times acceptable.
      - Generating realistic data volumes for manual inspection.

    Args:
        pod:       PostgreSQL pod name.
        results:   Shared result accumulator.
        num_votes: Number of votes to insert (default 1000).

    Returns:
        True if the bulk insert succeeds and the distribution query works.
    """
    print_test(12, f"Load Testing ({num_votes} votes)")

    print_info(f"Inserting {num_votes} test votes...")

    # Bulk insert using generate_series for efficiency (single round-trip)
    success, stdout, stderr = exec_psql(pod, f"""
        INSERT INTO votes (election_id, candidate_id)
        SELECT
            1 as election_id,
            (random() * 2 + 1)::int as candidate_id
        FROM generate_series(1, {num_votes});
    """)

    if not success:
        print_fail(f"Failed to insert {num_votes} votes")
        results.add_fail("Load Testing", stderr)
        return False

    print_pass(f"Successfully inserted {num_votes} votes")

    # Verify the distribution across candidates
    print_info("Checking vote distribution...")
    success, stdout, _ = exec_psql(pod, """
        SELECT
            c.name,
            COUNT(v.vote_id) as votes
        FROM candidates c
        LEFT JOIN votes v ON c.candidate_id = v.candidate_id
        WHERE c.election_id = 1
        GROUP BY c.name
        ORDER BY votes DESC;
    """)

    if success:
        print_info("Vote distribution:")
        lines = [l for l in stdout.split('\n') if l.strip() and 'name' not in l.lower() and not l.startswith('(')]
        for line in lines:
            if line.strip():
                print(f"  {line.strip()}")
        results.add_pass("Load Testing", f"{num_votes} votes inserted")
        return True
    else:
        results.add_warning("Load Testing", "Could not verify distribution")
        return False


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    """Parse CLI arguments, run the test suite, and print the summary.

    Test execution order:
        1.  Pod running (gate-keeper - exits early if pod is down)
        2.  Database connection
        3.  Required tables exist
        4.  Sample data loaded
        5.  Vote immutability (security)
        6.  Hash generation (hash chain)
        7.  User permissions (least privilege)
        8.  Complex queries (vote tallying)
        9.  Database indexes (performance)
        10. Foreign key constraints (data integrity)
        11. Service connection from another pod (skipped with --quick)
        12. Load testing (only with --load or interactive prompt)

    Exit codes:
        0   All tests passed (warnings OK)
        1   One or more failures
        130 Interrupted by Ctrl-C
    """
    global logger
    logger = setup_logging()

    parser = argparse.ArgumentParser(
        description='U-Vote Database Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Categories:
  1. Infrastructure - Pod and connection tests
  2. Schema - Tables, indexes, constraints
  3. Data - Sample data and queries
  4. Security - Immutability, permissions
  5. Performance - Indexes, load testing

Examples:
  python test_database.py              # Run all tests
  python test_database.py --quick      # Skip load testing
  python test_database.py --load 5000  # Insert 5000 test votes
        """
    )

    parser.add_argument('--quick', action='store_true',
                       help='Skip slow tests (load testing, connection test)')
    parser.add_argument('--load', type=int, metavar='N',
                       help='Run load test with N votes (default: 1000)')
    parser.add_argument('--pod', type=str, metavar='POD_NAME',
                       help='Specify PostgreSQL pod name (auto-detect if not provided)')

    args = parser.parse_args()

    results = TestResults()

    print_header("U-Vote Database Test Suite")
    print_info("Testing PostgreSQL deployment in Kubernetes\n")

    # Resolve the target pod - either from --pod flag or auto-detect via label
    if args.pod:
        pod = args.pod
        print_info(f"Using specified pod: {pod}")
    else:
        pod = test_pod_running(results)

    if not pod:
        print_fail("Cannot proceed without database pod")
        sys.exit(1)

    # Run the core test suite (Tests 2-10)
    test_connection(pod, results)
    test_tables_exist(pod, results)
    test_sample_data(pod, results)
    test_vote_immutability(pod, results)
    test_hash_generation(pod, results)
    test_user_permissions(pod, results)
    test_complex_queries(pod, results)
    test_indexes(pod, results)
    test_foreign_keys(pod, results)

    # Optional slow tests (Test 11-12) - skipped with --quick
    if not args.quick:
        test_connection_from_pod(pod, results)

        if args.load:
            test_load_performance(pod, results, args.load)
        elif args.load != 0:  # Not explicitly disabled
            response = input(f"\n{Colors.YELLOW}Run load test with 1000 votes? (y/N): {Colors.ENDC}").strip().lower()
            if response == 'y':
                test_load_performance(pod, results, 1000)

    # --- Summary ---
    print_header("Test Summary")

    summary_text = results.summary()
    if logger:
        logger.info("=" * 70)
        logger.info(summary_text)

    print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
    print(f"  {Colors.GREEN}Passed:  {results.passed}{Colors.ENDC}")
    print(f"  {Colors.RED}Failed:  {results.failed}{Colors.ENDC}")
    print(f"  {Colors.YELLOW}Warnings: {results.warnings}{Colors.ENDC}")
    print(f"  {Colors.CYAN}Total:   {results.passed + results.failed + results.warnings}{Colors.ENDC}")

    # List individual failures for quick triage
    if results.failed > 0:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.ENDC}")
        for status, name, details in results.tests:
            if status == "FAIL":
                print(f"  ❌ {name}")
                if details:
                    print(f"     {details[:100]}")

    if results.warnings > 0:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings:{Colors.ENDC}")
        for status, name, details in results.tests:
            if status == "WARN":
                print(f"  ⚠️  {name}")
                if details:
                    print(f"     {details[:100]}")

    # Point the user to the full log file for debugging
    if logger and logger.handlers:
        log_path = logger.handlers[0].baseFilename
        print(f"\n{Colors.BLUE}📄 Full log: {log_path}{Colors.ENDC}")
        logger.info(f"Test suite finished — {summary_text}")
        logger.info("=" * 70)

    # Set exit code based on results
    if results.failed > 0:
        print(f"\n{Colors.RED}❌ Some tests failed{Colors.ENDC}")
        sys.exit(1)
    elif results.warnings > 0:
        print(f"\n{Colors.YELLOW}⚠️  All tests passed with warnings{Colors.ENDC}")
        sys.exit(0)
    else:
        print(f"\n{Colors.GREEN}✅ All tests passed!{Colors.ENDC}")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Tests interrupted by user{Colors.ENDC}")
        if logger:
            logger.warning("Test suite interrupted by user (KeyboardInterrupt)")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Unexpected error: {e}{Colors.ENDC}")
        if logger:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
