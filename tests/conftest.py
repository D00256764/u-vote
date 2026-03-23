"""
tests/conftest.py — shared pytest fixtures for the U-Vote test suite.

Fixtures provided:
  mailhog (session)   — MailHogHelper instance with port-forward lifecycle
  clear_mailhog (autouse) — clears MailHog inbox before every test

Usage in a test file:
  def test_token_email(mailhog):
      token = asyncio.run(mailhog.get_voting_token("voter@example.com"))
      assert token is not None

  async def test_token_email_async(mailhog):
      token = await mailhog.get_voting_token("voter@example.com")
      assert token is not None

MailHog must be deployed in the cluster:
  kubectl port-forward svc/mailhog 8025:8025 -n uvote-dev
  (the mailhog fixture handles this automatically)
"""
import asyncio
import logging
import os
import socket
import subprocess
import time

import pytest

NAMESPACE = os.getenv("UVOTE_NAMESPACE", "uvote-dev")

logger = logging.getLogger(__name__)


class MailHogHelper:
    def __init__(self, base_url: str = "http://localhost:8025"):
        self.base_url = base_url
        # Override the module-level MAILHOG_API in the helper module
        # so all calls use this instance's base_url
        import tests.helpers.mailhog as _mh
        _mh.MAILHOG_API = f"{self.base_url}/api/v2/messages"

    async def get_voting_token(self, email: str) -> str:
        """
        Find the most recent email sent to `email` in MailHog and extract
        the voting token from the /vote/{token} URL in the body.
        Delegates to tests.helpers.mailhog.get_latest_voting_token().
        """
        from tests.helpers.mailhog import get_latest_voting_token
        return await get_latest_voting_token(email)

    async def clear_all(self) -> None:
        """
        Delete all messages from the MailHog inbox.
        Delegates to tests.helpers.mailhog.delete_all_messages().
        """
        from tests.helpers.mailhog import delete_all_messages
        await delete_all_messages()


def _start_mailhog_portforward():
    """
    Start kubectl port-forward svc/mailhog 8025:8025 -n <NAMESPACE> as a
    background subprocess.

    Waits up to 10 seconds for the port to become available. If the port is
    already in use, logs a warning and returns None.

    Returns:
        The Popen process handle, or None if the port was already in use.
    """
    # Check if port is already bound before starting a new forward
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        already_open = sock.connect_ex(("localhost", 8025)) == 0

    if already_open:
        logger.warning(
            "Port 8025 is already in use — skipping kubectl port-forward. "
            "Assuming an existing MailHog port-forward is active."
        )
        return None

    proc = subprocess.Popen(
        [
            "kubectl", "port-forward",
            "svc/mailhog", "8025:8025",
            "-n", NAMESPACE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("localhost", 8025)) == 0:
                return proc
        time.sleep(0.5)

    logger.warning(
        "MailHog port-forward did not become ready within 10 seconds. "
        "Tests that contact MailHog will fail with a connection error."
    )
    return proc


def _stop_mailhog_portforward(proc) -> None:
    """
    Terminate the port-forward process if it is still running.

    Waits up to 3 seconds for a clean exit, then kills it. All errors are
    silently ignored — cleanup is best-effort.
    """
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass


@pytest.fixture(scope="session")
def mailhog():
    """
    Session-scoped fixture that starts a kubectl port-forward to the
    MailHog service and returns a MailHogHelper instance.

    The port-forward is torn down automatically at the end of the
    test session.

    If the port-forward cannot be started (e.g. cluster not running),
    the fixture yields the helper anyway — individual tests that call
    mailhog.get_voting_token() will fail with a connection error at
    that point rather than blocking the entire session.
    """
    proc = _start_mailhog_portforward()
    helper = MailHogHelper(base_url="http://localhost:8025")
    yield helper
    _stop_mailhog_portforward(proc)


@pytest.fixture(autouse=True)
def clear_mailhog(mailhog):
    """
    Automatically clear the MailHog inbox before every test function.

    This prevents emails from a previous test leaking into the next
    test's get_voting_token() call.

    Uses asyncio.run() because this is a sync fixture wrapping an
    async helper. Does not fail the test if clearing fails — clearing
    is best-effort.
    """
    try:
        asyncio.run(mailhog.clear_all())
    except Exception:
        pass
    yield


@pytest.fixture(scope="session")
def db_pod():
    """
    Session-scoped fixture that resolves the PostgreSQL pod name in
    uvote-dev and returns it as a string for use in database tests.

    Skips all tests if no PostgreSQL pod is found (cluster not running).
    """
    import os
    namespace = os.getenv("UVOTE_NAMESPACE", "uvote-dev")
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace,
         "-l", "app=postgresql",
         "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True, text=True
    )
    pod_name = result.stdout.strip()
    if not pod_name:
        pytest.skip("No PostgreSQL pod found — is the cluster running?")
    return pod_name


def pytest_collection_modifyitems(items):
    """
    Remove legacy standalone test functions from test_db.py that are not
    pytest-compatible.  The original functions (test_pod_running, test_connection,
    etc.) take non-fixture arguments (pod, results) and are run via the standalone
    CLI runner.  Only the pytest wrapper functions (test_1_* … test_10_*) should
    be collected by pytest.
    """
    keep = []
    for item in items:
        if "test_db.py" in str(getattr(item, "fspath", "")):
            # Keep only the numbered pytest wrappers (test_1_*, test_2_*, …)
            import re
            if not re.match(r"test_\d+_", item.name):
                continue
        keep.append(item)
    items[:] = keep
