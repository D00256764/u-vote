#!/usr/bin/env python3
"""
UVote Kibana Dashboard

Opens the UVote Platform Logs Kibana dashboard.
Starts a kubectl port-forward for Kibana, retrieves the elastic password
from the cluster, prints connection details, opens the dashboard in the
default browser, and keeps the port-forward alive until Ctrl+C.

Usage:
    python plat_scripts/kibana_dashboard.py
"""

import signal
import socket
import subprocess
import sys
import time
import webbrowser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KIBANA_NAMESPACE  = "monitoring"
KIBANA_SVC        = "svc/kibana-kibana"
KIBANA_PORT       = 5601
KIBANA_URL        = f"http://localhost:{KIBANA_PORT}"
DASHBOARD_ID      = "77777777-7777-7777-7777-777777777777"
DASHBOARD_URL     = f"{KIBANA_URL}/app/dashboards#/view/{DASHBOARD_ID}"
SECRET_NAME       = "elasticsearch-master-credentials"
SECRET_NAMESPACE  = "monitoring"

POLL_INTERVAL = 0.5   # seconds between TCP connect attempts
POLL_TIMEOUT  = 10.0  # seconds before giving up on port-forward

# ---------------------------------------------------------------------------
# ANSI colours  (pure stdlib — matches setup_k8s_platform.py style)
# ---------------------------------------------------------------------------

class Colors:
    HEADER = '\033[95m'
    BLUE   = '\033[94m'
    CYAN   = '\033[96m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    ENDC   = '\033[0m'
    BOLD   = '\033[1m'


def print_header(message: str) -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(message: str) -> None:
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")


def print_error(message: str) -> None:
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}", file=sys.stderr)


def print_warning(message: str) -> None:
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")


def print_info(message: str) -> None:
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def port_open(port: int) -> bool:
    """Return True if localhost:port accepts a TCP connection."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_for_port(port: int, timeout: float = POLL_TIMEOUT) -> bool:
    """Poll until localhost:port is open or timeout is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(POLL_INTERVAL)
    return False


def get_elastic_password() -> str | None:
    """Retrieve the elastic password from the cluster secret.

    Returns the password string, or None if the secret does not exist or
    the kubectl call fails.
    """
    result = subprocess.run(
        [
            "kubectl", "get", "secret", SECRET_NAME,
            "-n", SECRET_NAMESPACE,
            "-o", "jsonpath={.data.password}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    # Decode the base64 value
    import base64
    try:
        return base64.b64decode(result.stdout.strip()).decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print_header("UVote Kibana Dashboard")

    # ------------------------------------------------------------------
    # Step 1 — port-forward (or detect existing)
    # ------------------------------------------------------------------
    print_info("Checking port 5601...")

    pf_proc: subprocess.Popen | None = None
    already_open = port_open(KIBANA_PORT)

    if already_open:
        print_warning(
            f"Port {KIBANA_PORT} is already in use — "
            "port-forward may already be running."
        )
    else:
        print_info(
            f"Starting kubectl port-forward "
            f"{KIBANA_SVC} {KIBANA_PORT}:{KIBANA_PORT} "
            f"-n {KIBANA_NAMESPACE} ..."
        )
        pf_proc = subprocess.Popen(
            [
                "kubectl", "port-forward",
                KIBANA_SVC,
                f"{KIBANA_PORT}:{KIBANA_PORT}",
                "-n", KIBANA_NAMESPACE,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        print_info(
            f"Waiting up to {POLL_TIMEOUT:.0f}s for port {KIBANA_PORT}..."
        )
        if not wait_for_port(KIBANA_PORT):
            stderr_out = ""
            if pf_proc.poll() is not None:
                try:
                    stderr_out = pf_proc.stderr.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
            suffix = f": {stderr_out}" if stderr_out else ""
            print_error(
                f"Port {KIBANA_PORT} did not open within {POLL_TIMEOUT:.0f}s{suffix}"
            )
            if pf_proc.poll() is None:
                pf_proc.terminate()
            sys.exit(1)

        print_success(f"Port-forward established on port {KIBANA_PORT}.")

    # ------------------------------------------------------------------
    # Step 2 — retrieve credentials
    # ------------------------------------------------------------------
    print_info("Retrieving elastic credentials from cluster...")

    password = get_elastic_password()
    if password is None:
        print_error(
            f"Secret '{SECRET_NAME}' not found in namespace '{SECRET_NAMESPACE}' — "
            "ELK stack not deployed — run boot_platform.py first"
        )
        if pf_proc is not None and pf_proc.poll() is None:
            pf_proc.terminate()
        sys.exit(1)

    print_success("Credentials retrieved.")

    # ------------------------------------------------------------------
    # Step 3 — print connection box
    # ------------------------------------------------------------------
    sep = "─" * 58
    print()
    print(f"{Colors.CYAN}{Colors.BOLD}┌{sep}┐{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}│  Kibana — UVote Platform Logs{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}├{sep}┤{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}│{Colors.ENDC}  Kibana URL :  {Colors.GREEN}{KIBANA_URL}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}│{Colors.ENDC}  Username   :  {Colors.GREEN}elastic{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}│{Colors.ENDC}  Password   :  {Colors.GREEN}{password}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}│{Colors.ENDC}  Dashboard  :  {Colors.GREEN}{DASHBOARD_URL}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}└{sep}┘{Colors.ENDC}")
    print()

    # ------------------------------------------------------------------
    # Step 4 — open browser
    # ------------------------------------------------------------------
    print_info("Opening dashboard in browser...")
    webbrowser.open(DASHBOARD_URL)

    # ------------------------------------------------------------------
    # Step 5 — block until Ctrl+C
    # ------------------------------------------------------------------
    print_info("Press Ctrl+C to stop the port-forward and exit.")
    print()

    def _shutdown(signum=None, frame=None) -> None:
        print()
        print_info("Shutting down port-forward...")
        if pf_proc is not None and pf_proc.poll() is None:
            pf_proc.terminate()
            try:
                pf_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pf_proc.kill()
        print_success("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # If we started the port-forward, wait on it so we can detect crashes.
    # If we're using an existing one, just sleep indefinitely.
    if pf_proc is not None:
        pf_proc.wait()
        # Port-forward died unexpectedly
        stderr_out = ""
        try:
            stderr_out = pf_proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            pass
        msg = f"Port-forward exited (code {pf_proc.returncode})"
        if stderr_out:
            msg += f": {stderr_out}"
        print_warning(msg)
    else:
        # Port was already open — nothing to supervise
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
