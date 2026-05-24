#!/usr/bin/env python3
"""
U-Vote Observability Port-Forward Manager

Opens kubectl port-forwards for all observability and dashboard services in a
single terminal session and cleans them up on Ctrl+C.

Services forwarded:
  Kiali      → http://localhost:20001
  Jaeger     → http://localhost:16686
  Prometheus → http://localhost:9090
  Grafana    → http://localhost:3000
  Kibana     → http://localhost:5601

Also manages:
  Kubernetes Dashboard → http://localhost:8001/... (via kubectl proxy)

Services not present in the cluster are skipped with a [WARNING] rather than
causing the script to fail, so a partial observability stack still works.

Usage:
    python plat_scripts/port_forward.py
    python plat_scripts/port_forward.py --open-browser

Requirements:
    - kubectl configured for the uvote cluster context
    - Python 3.8+
    - pip packages: click, colorama
"""

import base64
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# shared/ is a sibling directory inside plat_scripts/ — insert the parent so
# the import resolves correctly regardless of the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import click
except ImportError:
    print("ERROR: 'click' package required. Install with: pip install click")
    sys.exit(1)

from shared.logger import DeploymentLogger  # noqa: E402


# ---------------------------------------------------------------------------
# Kubernetes Dashboard constants
# ---------------------------------------------------------------------------

K8S_DASHBOARD_NAMESPACE = "kubernetes-dashboard"
K8S_PROXY_PORT          = 8001
K8S_DASHBOARD_URL       = (
    f"http://localhost:{K8S_PROXY_PORT}/api/v1/namespaces/"
    f"{K8S_DASHBOARD_NAMESPACE}/services/https:kubernetes-dashboard:/proxy/"
)

# Inline YAML: admin-user ServiceAccount + ClusterRoleBinding (from k8s_dashboard.py)
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

# Kibana credential secret (ELK stack)
KIBANA_CRED_SECRET    = "elasticsearch-master-credentials"
KIBANA_CRED_NAMESPACE = "monitoring"

# Dashboard deep-link UUID — matches DASH in create_dashboard.py
KIBANA_DASHBOARD_ID  = "77777777-7777-7777-7777-777777777777"
KIBANA_DASHBOARD_URL = (
    f"http://localhost:5601/app/dashboards#/view/{KIBANA_DASHBOARD_ID}"
)


# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

@dataclass
class ForwardSpec:
    """Describes one kubectl port-forward target."""

    name: str          # human-readable label shown in the summary
    svc: str           # Kubernetes Service resource name
    namespace: str
    local_port: int
    remote_port: int

    @property
    def url(self) -> str:
        return f"http://localhost:{self.local_port}"

    @property
    def kubectl_cmd(self) -> List[str]:
        return [
            "kubectl", "port-forward",
            f"svc/{self.svc}",
            f"{self.local_port}:{self.remote_port}",
            "-n", self.namespace,
        ]


SERVICES: List[ForwardSpec] = [
    ForwardSpec("Kiali",      "kiali",         "istio-system", 20001, 20001),
    ForwardSpec("Jaeger",     "tracing",       "istio-system", 16686, 80),
    ForwardSpec("Prometheus", "prometheus",    "istio-system", 9090,  9090),
    ForwardSpec("Grafana",    "grafana",       "istio-system", 3000,  3000),
    ForwardSpec("Kibana",     "kibana-kibana", "monitoring",   5601,  5601),
]


# ---------------------------------------------------------------------------
# Helpers — cluster resource checks
# ---------------------------------------------------------------------------

def service_exists(svc: str, namespace: str) -> bool:
    """Return True if the named Service exists in the given namespace."""
    result = subprocess.run(
        ["kubectl", "get", "svc", svc, "-n", namespace],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def namespace_exists(namespace: str) -> bool:
    """Return True if the named namespace exists in the cluster."""
    result = subprocess.run(
        ["kubectl", "get", "namespace", namespace],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Helpers — Kubernetes Dashboard
# ---------------------------------------------------------------------------

def ensure_k8s_admin_user(log: DeploymentLogger) -> bool:
    """Apply the admin-user ServiceAccount and ClusterRoleBinding. Return True on success."""
    log.info("  Applying admin-user ServiceAccount and ClusterRoleBinding...")
    result = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=ADMIN_USER_YAML.encode(),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        log.warning(
            f"  Could not apply admin-user resources: "
            f"{result.stderr.decode(errors='replace').strip()[:150]}"
        )
        return False
    log.success("  admin-user resources applied")
    return True


def generate_k8s_token(log: DeploymentLogger) -> Optional[str]:
    """Generate and return a bearer token for admin-user, or None on failure."""
    result = subprocess.run(
        ["kubectl", "-n", K8S_DASHBOARD_NAMESPACE, "create", "token", "admin-user"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.warning(
            f"  Failed to generate token: {result.stderr.strip()[:150]}"
        )
        return None
    return result.stdout.strip()


def wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Poll until localhost:port accepts a TCP connection or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


# ---------------------------------------------------------------------------
# Helpers — Kibana credentials (pre-forward hook)
# ---------------------------------------------------------------------------

def get_kibana_credentials(log: DeploymentLogger) -> Optional[Tuple[str, str]]:
    """Decode and return (username, password) from the Elasticsearch credentials secret.

    Returns None if the secret does not exist or cannot be decoded, logging a
    [WARNING] in that case so callers can continue without credentials.
    """
    check = subprocess.run(
        ["kubectl", "get", "secret", KIBANA_CRED_SECRET, "-n", KIBANA_CRED_NAMESPACE],
        capture_output=True,
        check=False,
    )
    if check.returncode != 0:
        log.warning(
            f"  Secret '{KIBANA_CRED_SECRET}' not found in namespace "
            f"'{KIBANA_CRED_NAMESPACE}' — Kibana credentials unavailable "
            "(ELK stack may not be deployed)"
        )
        return None

    # Decode password field (required)
    pw_res = subprocess.run(
        ["kubectl", "get", "secret", KIBANA_CRED_SECRET,
         "-n", KIBANA_CRED_NAMESPACE,
         "-o", "jsonpath={.data.password}"],
        capture_output=True, text=True, check=False,
    )
    # Decode username field (optional; falls back to "elastic" if absent)
    un_res = subprocess.run(
        ["kubectl", "get", "secret", KIBANA_CRED_SECRET,
         "-n", KIBANA_CRED_NAMESPACE,
         "-o", "jsonpath={.data.username}"],
        capture_output=True, text=True, check=False,
    )

    try:
        password = base64.b64decode(pw_res.stdout.strip()).decode("utf-8")
    except Exception:
        log.warning("  Could not decode Kibana password — credentials unavailable")
        return None

    username = "elastic"
    if un_res.returncode == 0 and un_res.stdout.strip():
        try:
            username = base64.b64decode(un_res.stdout.strip()).decode("utf-8")
        except Exception:
            pass  # keep "elastic" fallback

    return username, password


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--open-browser",
    is_flag=True,
    default=False,
    help=(
        "Open each started service URL and the Kubernetes Dashboard "
        "in the default browser after the 2s startup wait."
    ),
)
def main(open_browser: bool) -> None:
    """Open port-forwards for all U-Vote observability services.

    \b
    Services forwarded:
      Kiali      → http://localhost:20001
      Jaeger     → http://localhost:16686
      Prometheus → http://localhost:9090
      Grafana    → http://localhost:3000
      Kibana     → http://localhost:5601

    Also starts kubectl proxy for the Kubernetes Dashboard on port 8001 if
    the kubernetes-dashboard namespace exists.

    Services not found in the cluster are skipped with a warning.
    Press Ctrl+C to stop all forwards and exit cleanly.
    """
    log = DeploymentLogger()

    log.header("U-Vote Observability Port-Forwards")

    # ------------------------------------------------------------------
    # Pre-forward hook: Kibana credentials
    # ------------------------------------------------------------------
    log.info("Checking Kibana credentials...")
    kibana_creds: Optional[Tuple[str, str]] = get_kibana_credentials(log)

    # ------------------------------------------------------------------
    # Start a background Popen for each service that exists in the cluster
    # ------------------------------------------------------------------
    log.info("")
    started: List[Tuple[ForwardSpec, subprocess.Popen]] = []
    skipped: List[ForwardSpec] = []

    for spec in SERVICES:
        log.info(f"Checking {spec.name}  (svc/{spec.svc} -n {spec.namespace})...")

        if not service_exists(spec.svc, spec.namespace):
            log.warning(
                f"  svc/{spec.svc} not found in namespace '{spec.namespace}' — skipping"
            )
            skipped.append(spec)
            continue

        log.info(f"  $ {' '.join(spec.kubectl_cmd)}")
        proc = subprocess.Popen(
            spec.kubectl_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started.append((spec, proc))
        log.success(f"  {spec.name} port-forward started (PID {proc.pid})")

    # ------------------------------------------------------------------
    # Kubernetes Dashboard via kubectl proxy
    # ------------------------------------------------------------------
    log.info("")
    log.info("Checking Kubernetes Dashboard  (kubectl proxy → port 8001)...")

    proxy_proc: Optional[subprocess.Popen] = None
    k8s_token: Optional[str] = None
    k8s_ns_present = namespace_exists(K8S_DASHBOARD_NAMESPACE)

    if not k8s_ns_present:
        log.warning(
            f"  Namespace '{K8S_DASHBOARD_NAMESPACE}' not found — "
            "skipping Kubernetes Dashboard"
        )
    else:
        if ensure_k8s_admin_user(log):
            k8s_token = generate_k8s_token(log)
            if k8s_token:
                log.success("  Bearer token generated")

        log.info("  $ kubectl proxy  (port 8001)")
        proxy_proc = subprocess.Popen(
            ["kubectl", "proxy"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.success(f"  kubectl proxy started (PID {proxy_proc.pid})")

    # ------------------------------------------------------------------
    # Nothing at all was started — warn and exit cleanly
    # ------------------------------------------------------------------
    if not started and proxy_proc is None:
        log.warning("No services were forwarded — is the cluster running?")
        log.close()
        sys.exit(0)

    # Give all forwarders a moment to bind their local ports before reporting.
    log.info("")
    log.info("Waiting 2s for port-forwards to bind...")
    time.sleep(2)

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    name_w = max(len(s.name) for s in SERVICES)

    log.info("")
    log.header("Port-Forward Summary")

    # Kibana credentials — printed before the table for easy copy-paste
    if kibana_creds:
        username, password = kibana_creds
        log.info(f"  Kibana credentials  username: {username}  |  password: {password}")
        log.info(f"  Kibana dashboard    {KIBANA_DASHBOARD_URL}")
        log.info("")

    for spec, proc in started:
        state = "running" if proc.poll() is None else "exited — check kubectl connectivity"
        log.info(f"  {spec.name:<{name_w}}  {spec.url:<28}  [{state}]")

    for spec in skipped:
        log.info(f"  {spec.name:<{name_w}}  {spec.url:<28}  [SKIPPED — service not found]")

    # Kubernetes Dashboard row
    log.info("")
    if proxy_proc is not None:
        proxy_state = "running" if proxy_proc.poll() is None else "exited"
        log.info(f"  Kubernetes Dashboard  [{proxy_state}]")
        log.info(f"    URL  : {K8S_DASHBOARD_URL}")
        if k8s_token:
            log.info(f"    Token: {k8s_token}")
        else:
            log.warning("    Token could not be generated — log in manually")
    else:
        log.info(
            f"  Kubernetes Dashboard  "
            f"[SKIPPED — '{K8S_DASHBOARD_NAMESPACE}' namespace not found]"
        )

    # ------------------------------------------------------------------
    # Optionally open each live URL in the default browser
    # ------------------------------------------------------------------
    if open_browser:
        log.info("")
        log.info("Opening services in browser...")
        for spec, proc in started:
            if proc.poll() is None:
                log.info(f"  Opening {spec.url}")
                webbrowser.open(spec.url)
        if proxy_proc is not None and proxy_proc.poll() is None:
            log.info(f"  Opening {K8S_DASHBOARD_URL}")
            webbrowser.open(K8S_DASHBOARD_URL)

    log.info("")
    log.info("All port-forwards running. Press Ctrl+C to stop.")

    # ------------------------------------------------------------------
    # Block until the user presses Ctrl+C
    # ------------------------------------------------------------------
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # ------------------------------------------------------------------
    # Clean up all background processes
    # ------------------------------------------------------------------
    log.info("")
    log.info("Shutting down port-forwards...")

    for spec, proc in started:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        log.info(f"  Terminated {spec.name} (PID {proc.pid})")

    if proxy_proc is not None:
        if proxy_proc.poll() is None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy_proc.kill()
        log.info(f"  Terminated kubectl proxy (PID {proxy_proc.pid})")

    log.info("All port-forwards stopped.")
    log.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
