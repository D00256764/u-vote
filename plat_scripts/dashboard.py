#!/usr/bin/env python3
"""
UVote Kubernetes Dashboard

Sets up and opens the Kubernetes Dashboard for the UVote platform.
Installs the dashboard and admin-user credentials automatically if they
are not already present, generates a fresh login token, and keeps a
kubectl proxy running so the dashboard stays accessible.

Usage:
    python plat_scripts/dashboard.py
"""

import signal
import socket
import subprocess
import sys
import time
import webbrowser
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DASHBOARD_NAMESPACE = "kubernetes-dashboard"
DEPLOYMENT_NAME     = "kubernetes-dashboard"

MANIFEST_URL = (
    "https://raw.githubusercontent.com/kubernetes/dashboard/"
    "v2.7.0/aio/deploy/recommended.yaml"
)

PROXY_PORT    = 8001
DASHBOARD_URL = (
    f"http://localhost:{PROXY_PORT}/api/v1/namespaces/"
    f"{DASHBOARD_NAMESPACE}/services/https:{DEPLOYMENT_NAME}:/proxy/"
)

READY_TIMEOUT = 120  # seconds to wait for dashboard deployment to be available
PROXY_TIMEOUT =  15  # seconds to wait for proxy to accept connections
RESTART_DELAY =   3  # seconds before restarting a dead proxy

# ---------------------------------------------------------------------------
# Inline YAML — admin-user ServiceAccount + ClusterRoleBinding
# ---------------------------------------------------------------------------

ADMIN_USER_YAML = """\
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: kubernetes-dashboard
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: admin-user
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: admin-user
  namespace: kubernetes-dashboard
"""


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def step(msg: str) -> None:
    """Print a top-level phase heading."""
    print(f"\n>>> {msg}")

def ok(msg: str) -> None:
    print(f"    \u2713 {msg}")

def info(msg: str) -> None:
    print(f"    {msg}")

def warn(msg: str) -> None:
    print(f"    \u26a0 {msg}")

def fail(msg: str) -> None:
    print(f"    \u2717 {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# kubectl wrapper
# ---------------------------------------------------------------------------

def kube(*args: str, stdin_data: Optional[str] = None):
    """Run `kubectl <args>` and return (returncode, stdout, stderr).

    Pass *stdin_data* to supply input on stdin (e.g. for `kubectl apply -f -`).
    stdout and stderr are stripped of surrounding whitespace.
    """
    result = subprocess.run(
        ["kubectl", *args],
        input=stdin_data,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def resource_exists(*get_args: str) -> bool:
    """Return True if `kubectl get <get_args>` exits with code 0."""
    rc, _, _ = kube("get", *get_args)
    return rc == 0


# ---------------------------------------------------------------------------
# Dashboard installation
# ---------------------------------------------------------------------------

def ensure_dashboard() -> bool:
    """Install the Kubernetes Dashboard if not already present.

    Returns True when the dashboard is ready (or was already present),
    False if installation failed.
    """
    step("Checking Kubernetes Dashboard installation...")

    ns_ok     = resource_exists("namespace", DASHBOARD_NAMESPACE)
    deploy_ok = ns_ok and resource_exists(
        "deployment", DEPLOYMENT_NAME, "-n", DASHBOARD_NAMESPACE
    )

    if ns_ok and deploy_ok:
        ok(f"Dashboard already installed in namespace '{DASHBOARD_NAMESPACE}'.")
        return True

    if not ns_ok:
        info(f"Namespace '{DASHBOARD_NAMESPACE}' not found — installing dashboard...")
    else:
        info(f"Deployment '{DEPLOYMENT_NAME}' not found — (re-)installing dashboard...")

    info(f"Applying manifest: {MANIFEST_URL}")
    rc, _, stderr = kube("apply", "-f", MANIFEST_URL)
    if rc != 0:
        fail(f"kubectl apply failed: {stderr}")
        return False
    ok("Manifest applied.")

    info(f"Waiting for deployment to be ready (up to {READY_TIMEOUT}s)...")
    rc, _, stderr = kube(
        "wait",
        "--for=condition=available",
        f"deployment/{DEPLOYMENT_NAME}",
        "-n", DASHBOARD_NAMESPACE,
        f"--timeout={READY_TIMEOUT}s",
    )
    if rc != 0:
        # Non-fatal: dashboard may still be pulling images.  Let the user
        # proceed — they will get the URL and can refresh once it is ready.
        warn(f"Dashboard not fully ready yet: {stderr}")
        warn(f"Check progress with:  kubectl get pods -n {DASHBOARD_NAMESPACE}")
        return True

    ok("Dashboard deployment is ready.")
    return True


# ---------------------------------------------------------------------------
# Admin user credentials
# ---------------------------------------------------------------------------

def ensure_admin_user() -> bool:
    """Create the admin-user ServiceAccount and ClusterRoleBinding if absent.

    Uses `kubectl apply -f -` with inline YAML so no external files are needed.
    Returns True on success (including when resources already exist).
    """
    step("Checking admin-user credentials...")

    sa_ok  = resource_exists("serviceaccount", "admin-user", "-n", DASHBOARD_NAMESPACE)
    crb_ok = resource_exists("clusterrolebinding", "admin-user")

    if sa_ok and crb_ok:
        ok("admin-user ServiceAccount and ClusterRoleBinding already exist.")
        return True

    if not sa_ok:
        info("ServiceAccount  'admin-user'  not found.")
    if not crb_ok:
        info("ClusterRoleBinding  'admin-user'  not found.")

    info("Creating admin-user resources...")
    rc, _, stderr = kube("apply", "-f", "-", stdin_data=ADMIN_USER_YAML)
    if rc != 0:
        fail(f"Failed to create admin-user resources: {stderr}")
        return False

    ok("admin-user ServiceAccount and ClusterRoleBinding created.")
    return True


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def generate_token() -> Optional[str]:
    """Generate and return a fresh login token for admin-user, or None."""
    step("Generating login token...")
    rc, token, stderr = kube(
        "-n", DASHBOARD_NAMESPACE, "create", "token", "admin-user"
    )
    if rc != 0:
        fail(f"Failed to generate token: {stderr}")
        return None
    ok("Token generated.")
    return token


# ---------------------------------------------------------------------------
# Proxy management
# ---------------------------------------------------------------------------

def start_proxy() -> subprocess.Popen:
    """Launch `kubectl proxy` and return the Popen handle."""
    return subprocess.Popen(
        ["kubectl", "proxy"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def wait_for_proxy(timeout: int = PROXY_TIMEOUT) -> bool:
    """Poll until localhost:PROXY_PORT accepts a TCP connection."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def drain_stderr(proc: subprocess.Popen) -> str:
    """Read buffered stderr output after the process has exited."""
    try:
        return proc.stderr.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ------------------------------------------------------------------
    # Sanity-check kubectl
    # ------------------------------------------------------------------
    rc, _, _ = kube("version", "--client")
    if rc != 0:
        print(
            "Error: kubectl not found or not working. Is it installed and on PATH?",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Setup phases
    # ------------------------------------------------------------------
    if not ensure_dashboard():
        sys.exit(1)

    if not ensure_admin_user():
        sys.exit(1)

    token = generate_token()
    if token is None:
        sys.exit(1)

    # ------------------------------------------------------------------
    # Start proxy (initial start)
    # ------------------------------------------------------------------
    step("Starting kubectl proxy...")
    proc: Optional[subprocess.Popen] = None

    def _shutdown(signum=None, frame=None) -> None:
        print("\nShutting down...")
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Proxy stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    proc = start_proxy()
    if not wait_for_proxy():
        reason = drain_stderr(proc) if proc.poll() is not None else ""
        suffix = f": {reason}" if reason else ""
        fail(f"Proxy did not become ready within {PROXY_TIMEOUT}s{suffix}.")
        if proc.poll() is None:
            proc.terminate()
        sys.exit(1)

    ok(f"Proxy running on port {PROXY_PORT}.")

    # ------------------------------------------------------------------
    # Display URL and token
    # ------------------------------------------------------------------
    sep = "=" * 66
    print()
    print(sep)
    print("  Kubernetes Dashboard  \u2014  UVote Platform")
    print(sep)
    print()
    print("  URL:")
    print(f"    {DASHBOARD_URL}")
    print()
    print("  Login token  (paste into the 'Token' field on the sign-in page):")
    print()
    print(f"    {token}")
    print()
    print(sep)
    print()
    print("  Opening dashboard in browser...")
    webbrowser.open(DASHBOARD_URL)
    print()
    print("  Press Ctrl+C to stop the proxy and exit.")
    print()

    # ------------------------------------------------------------------
    # Monitor proxy — restart automatically on unexpected exit
    # ------------------------------------------------------------------
    while True:
        proc.wait()  # blocks until the process exits

        reason = drain_stderr(proc)
        msg = f"kubectl proxy exited (code {proc.returncode})"
        if reason:
            msg += f": {reason}"
        print(msg)

        # Inner retry loop: keep attempting to restart until one succeeds
        while True:
            print(f"Restarting proxy in {RESTART_DELAY}s...  (Ctrl+C to quit)")
            time.sleep(RESTART_DELAY)

            proc = start_proxy()
            if wait_for_proxy():
                print(f"[reconnected]  Proxy re-established on port {PROXY_PORT}.")
                break

            # Restart attempt failed — diagnose and try again
            reason = drain_stderr(proc) if proc.poll() is not None else ""
            suffix = f": {reason}" if reason else ""
            print(f"Proxy did not become ready{suffix}. Retrying...")
            if proc.poll() is None:
                proc.terminate()
                proc.wait()


if __name__ == "__main__":
    main()
