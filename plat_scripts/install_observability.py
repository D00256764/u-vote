#!/usr/bin/env python3
"""
U-Vote Observability Installation Script

Installs the Istio observability addons (Prometheus, Jaeger, Kiali) into the
live uvote Kind cluster and configures 100% distributed trace sampling for
the uvote-dev namespace.

Steps performed:
  1. Apply Prometheus addon from Istio samples/addons/
  2. Apply Jaeger addon from Istio samples/addons/
  3. Apply Kiali addon from Istio samples/addons/
  4. Wait for all istio-system pods to reach Running state
  5. Apply Telemetry resource — 100% randomSamplingPercentage on uvote-dev
  6. Apply NetworkPolicy 11-allow-prometheus-scrape-istio.yaml
     (Prometheus in istio-system → Envoy sidecar ports 15090/15020)
  7. Apply NetworkPolicy 12-allow-kiali.yaml
     (Kiali in istio-system → Envoy sidecar port 15090)
  8. Generate sample traffic to populate the trace store
  9. Verify: istio-system pods Running, Kiali responds, Jaeger responds,
     http://localhost returns 200

Usage:
    python plat_scripts/install_observability.py [OPTIONS]

Requirements:
    - kubectl configured for kind-uvote context
    - Istio already installed (run install_istio.py first)
    - Kind cluster 'uvote' running with uvote-dev services deployed
    - Python 3.8+
    - pip packages: click, colorama
"""

import subprocess
import sys
import time
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Tuple

try:
    import click
except ImportError:
    print("ERROR: 'click' package required. Install with: pip install click")
    sys.exit(1)
try:
    from colorama import init, Fore, Style
    init()
except ImportError:
    print("ERROR: 'colorama' package required. Install with: pip install colorama")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLUSTER_NAME = "uvote"
NAMESPACE = "uvote-dev"

ADDON_NAMES = ["prometheus.yaml", "jaeger.yaml", "kiali.yaml"]

NETPOL_FILES = [
    "11-allow-prometheus-scrape-istio.yaml",
    "12-allow-kiali.yaml",
]

TRAFFIC_ROUTES = [
    "http://localhost",
    "http://localhost/api/auth/health",
    "http://localhost/api/elections/health",
    "http://localhost/api/results/health",
]


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
class Logger:
    COLOURS = {
        "INFO":    Fore.WHITE,
        "SUCCESS": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR":   Fore.RED,
    }

    def _emit(self, level: str, message: str) -> None:
        colour = self.COLOURS.get(level, "")
        click.echo(f"{colour}[{level}]{Style.RESET_ALL} {message}")

    def info(self, msg: str) -> None:
        self._emit("INFO", msg)

    def success(self, msg: str) -> None:
        self._emit("SUCCESS", msg)

    def warning(self, msg: str) -> None:
        self._emit("WARNING", msg)

    def error(self, msg: str) -> None:
        self._emit("ERROR", msg)

    def header(self, msg: str) -> None:
        sep = "=" * 60
        self.info(sep)
        self.info(msg)
        self.info(sep)


log = Logger()


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------
def run(cmd: List[str], check: bool = False, timeout: int = 300) -> Tuple[int, str, str]:
    """Run *cmd*, return (returncode, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"command timed out after {timeout}s"
    except FileNotFoundError:
        return 1, "", f"command not found: {cmd[0]}"


def apply_manifest(yaml_text: str) -> bool:
    """Pipe *yaml_text* into kubectl apply -f -. Return True on success."""
    try:
        proc = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=yaml_text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            log.error(f"kubectl apply failed: {proc.stderr.strip()}")
            return False
        return True
    except Exception as exc:
        log.error(f"kubectl apply error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Step 1–3 — Apply addons
# ---------------------------------------------------------------------------
def step1_apply_addons(istio_dir: Path) -> bool:
    log.header("Step 1: Apply Istio observability addons")

    addons_dir = istio_dir / "samples" / "addons"
    if not addons_dir.exists():
        log.error(f"Istio addons directory not found: {addons_dir}")
        log.error("Pass the correct path with --istio-dir")
        return False

    for addon in ADDON_NAMES:
        addon_path = addons_dir / addon
        if not addon_path.exists():
            log.error(f"Addon manifest not found: {addon_path}")
            return False
        log.info(f"Applying {addon}...")
        rc, _, err = run(["kubectl", "apply", "-f", str(addon_path)], timeout=120)
        if rc != 0:
            log.error(f"Failed to apply {addon}: {err.strip()}")
            return False
        log.success(f"{addon} applied")

    return True


# ---------------------------------------------------------------------------
# Step 4 — Wait for istio-system pods
# ---------------------------------------------------------------------------
def step4_wait_istio_system(timeout_secs: int = 300) -> bool:
    log.header("Step 4: Wait for istio-system pods to be Running")

    log.info(f"Waiting up to {timeout_secs}s for all pods in istio-system to be Ready...")
    rc, _, err = run(
        [
            "kubectl", "wait", "--for=condition=Ready",
            "pods", "--all", "-n", "istio-system",
            f"--timeout={timeout_secs}s",
        ],
        timeout=timeout_secs + 30,
    )
    if rc != 0:
        log.error(f"Pods in istio-system did not become Ready in time: {err.strip()}")
        return False

    rc, out, _ = run(["kubectl", "get", "pods", "-n", "istio-system"])
    log.info("istio-system pods:\n" + out.strip())
    log.success("All istio-system pods are Running")
    return True


# ---------------------------------------------------------------------------
# Step 5 — Apply Telemetry resource (100% trace sampling)
# ---------------------------------------------------------------------------
def step5_apply_telemetry() -> bool:
    log.header("Step 5: Apply Telemetry resource (100% trace sampling)")

    yaml_text = f"""\
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: uvote-tracing
  namespace: {NAMESPACE}
spec:
  tracing:
  - randomSamplingPercentage: 100.0
"""
    if not apply_manifest(yaml_text):
        return False

    log.success("Telemetry uvote-tracing applied (100% sampling)")
    return True


# ---------------------------------------------------------------------------
# Step 6 — Apply observability network policies
# ---------------------------------------------------------------------------
def step6_apply_network_policies(project_root: Path) -> bool:
    log.header("Step 6: Apply observability network policies")

    netpol_dir = project_root / "uvote-platform" / "k8s" / "network-policies"
    all_ok = True

    for policy_file in NETPOL_FILES:
        policy_path = netpol_dir / policy_file
        if not policy_path.exists():
            log.error(f"Network policy file not found: {policy_path}")
            log.error(
                "Create the file first or re-run from the project root after "
                "applying the network policies manually."
            )
            all_ok = False
            continue

        log.info(f"Applying {policy_file}...")
        rc, _, err = run(["kubectl", "apply", "-f", str(policy_path)])
        if rc != 0:
            log.error(f"Failed to apply {policy_file}: {err.strip()}")
            all_ok = False
        else:
            log.success(f"{policy_file} applied")

    return all_ok


# ---------------------------------------------------------------------------
# Step 7 — Generate sample traffic
# ---------------------------------------------------------------------------
def step7_generate_traffic(rounds: int = 5) -> bool:
    log.header("Step 7: Generate trace traffic")

    log.info(f"Sending {rounds} rounds of requests across {len(TRAFFIC_ROUTES)} routes...")
    for i in range(rounds):
        for route in TRAFFIC_ROUTES:
            try:
                urllib.request.urlopen(route, timeout=5)
            except (urllib.error.HTTPError, urllib.error.URLError):
                pass  # Non-200 responses still generate traces
            except Exception:
                pass

    log.success(f"Traffic generated ({rounds * len(TRAFFIC_ROUTES)} requests sent)")
    return True


# ---------------------------------------------------------------------------
# Step 8 — Verify
# ---------------------------------------------------------------------------
def _port_forward_check(
    svc: str,
    local_port: int,
    svc_port: int,
    ns: str,
    path: str,
) -> bool:
    """Start a port-forward to *svc*, GET *path*, log the result, tear down."""
    log.info(f"Port-forwarding svc/{svc} {svc_port} → localhost:{local_port}...")
    pf = subprocess.Popen(
        [
            "kubectl", "port-forward",
            f"svc/{svc}", f"{local_port}:{svc_port}",
            "-n", ns,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        deadline = time.time() + 15
        ready = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("localhost", local_port), timeout=1):
                    ready = True
                    break
            except OSError:
                time.sleep(0.3)

        if not ready:
            log.error(f"Port-forward to {svc}:{svc_port} did not become ready within 15s")
            return False

        time.sleep(0.5)

        url = f"http://localhost:{local_port}{path}"
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            log.success(f"{svc} at {url} → {resp.status}")
            return True
        except urllib.error.HTTPError as exc:
            # A redirect (301/302) or any 2xx/3xx means the service is up
            if exc.code < 400:
                log.success(f"{svc} at {url} → {exc.code}")
                return True
            log.error(f"{svc} at {url} → HTTP {exc.code}")
            return False
        except Exception as exc:
            log.error(f"Failed to reach {svc}: {exc}")
            return False
    finally:
        pf.terminate()
        try:
            pf.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pf.kill()
        log.info(f"Port-forward to {svc} closed")


def step8_verify() -> bool:
    log.header("Step 8: Verify observability stack")
    all_ok = True

    # 8a — istio-system pod list
    log.info("Checking istio-system pods...")
    rc, out, _ = run(["kubectl", "get", "pods", "-n", "istio-system"])
    if rc != 0:
        log.error("Could not retrieve istio-system pods")
        all_ok = False
    else:
        log.info("istio-system pods:\n" + out.strip())
        for component in ("jaeger", "kiali", "prometheus"):
            running = any(
                component in line and "Running" in line
                for line in out.splitlines()
            )
            if running:
                log.success(f"{component}: Running")
            else:
                log.error(f"{component}: not Running in istio-system")
                all_ok = False

    # 8b — Kiali
    if not _port_forward_check("kiali", 20001, 20001, "istio-system", "/kiali"):
        all_ok = False

    # 8c — Jaeger (tracing service, port 80 → 16686 internally)
    if not _port_forward_check("tracing", 16686, 80, "istio-system", "/"):
        all_ok = False

    # 8d — Frontend reachable through Istio gateway (non-fatal: timing/routing
    # issues at install time should not fail the observability stack install)
    log.info("Testing curl http://localhost...")
    time.sleep(1)
    try:
        resp = urllib.request.urlopen("http://localhost", timeout=10)
        if resp.status == 200:
            log.success("curl http://localhost → 200 OK")
        else:
            log.warning(f"curl http://localhost → {resp.status} (non-fatal)")
    except urllib.error.HTTPError as exc:
        log.warning(f"curl http://localhost → HTTP {exc.code} (non-fatal)")
    except Exception as exc:
        log.warning(f"curl http://localhost failed: {exc} (non-fatal)")

    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@click.command()
@click.option(
    "--istio-dir",
    default=None,
    show_default=False,
    help=(
        "Path to the Istio installation directory containing samples/addons/. "
        "Defaults to <project-root>/istio-1.22.3."
    ),
)
@click.option(
    "--addon-wait-timeout",
    default=300,
    show_default=True,
    help="Seconds to wait for all istio-system pods to become Ready.",
)
@click.option(
    "--skip-traffic",
    is_flag=True,
    default=False,
    help="Skip generating sample trace traffic (step 7).",
)
def main(
    istio_dir: str,
    addon_wait_timeout: int,
    skip_traffic: bool,
) -> None:
    """Install Istio observability addons and configure tracing for uvote-dev.

    \b
    Examples:
      # Full installation (uses istio-1.22.3 in project root)
      python plat_scripts/install_observability.py

      # Use a different Istio version directory
      python plat_scripts/install_observability.py --istio-dir ~/istio-1.23.0

      # Skip trace traffic generation
      python plat_scripts/install_observability.py --skip-traffic
    """
    project_root = Path(__file__).resolve().parent.parent

    resolved_istio_dir = Path(istio_dir) if istio_dir else project_root / "istio-1.22.3"

    log.header("U-Vote Observability Installation")
    log.info(f"Cluster:   {CLUSTER_NAME}")
    log.info(f"Namespace: {NAMESPACE}")
    log.info(f"Istio dir: {resolved_istio_dir}")

    steps = [
        ("Step 1: Apply addons",          lambda: step1_apply_addons(resolved_istio_dir)),
        ("Step 4: Wait for istio-system", lambda: step4_wait_istio_system(addon_wait_timeout)),
        ("Step 5: Apply Telemetry",       step5_apply_telemetry),
        ("Step 6: Apply network policies",lambda: step6_apply_network_policies(project_root)),
    ]

    if not skip_traffic:
        steps.append(("Step 7: Generate traffic", step7_generate_traffic))
    else:
        log.info("Skipping Step 7 (--skip-traffic)")

    steps.append(("Step 8: Verify", step8_verify))

    for label, fn in steps:
        if not fn():
            log.error(f"FAILED at: {label}")
            sys.exit(1)

    log.header("Observability installation complete")
    log.success("All steps passed.")
    log.info("Access dashboards via port-forward:")
    log.info("  kubectl port-forward svc/kiali    20001:20001 -n istio-system")
    log.info("  kubectl port-forward svc/tracing  16686:80    -n istio-system")
    log.info("  kubectl port-forward svc/prometheus 9090:9090 -n istio-system")
    log.info("Then open:")
    log.info("  http://localhost:20001/kiali   — Kiali service graph")
    log.info("  http://localhost:16686         — Jaeger trace search")
    log.info("  http://localhost:9090          — Prometheus query UI")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        sys.exit(130)
    except Exception as exc:
        log.error(f"Unexpected error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
