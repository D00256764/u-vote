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
# Helpers
# ---------------------------------------------------------------------------

def service_exists(svc: str, namespace: str) -> bool:
    """Return True if the named Service exists in the given namespace."""
    result = subprocess.run(
        ["kubectl", "get", "svc", svc, "-n", namespace],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--open-browser",
    is_flag=True,
    default=False,
    help="Open each started service URL in the default browser after the 2s startup wait.",
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

    Services not found in the cluster are skipped with a warning.
    Press Ctrl+C to stop all forwards and exit cleanly.
    """
    log = DeploymentLogger()

    log.header("U-Vote Observability Port-Forwards")

    started: List[Tuple[ForwardSpec, subprocess.Popen]] = []
    skipped: List[ForwardSpec] = []

    # ------------------------------------------------------------------
    # Pre-flight: check each service and start a background Popen for
    # those that exist in the cluster.
    # ------------------------------------------------------------------
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

    if not started:
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

    for spec, proc in started:
        state = "running" if proc.poll() is None else "exited — check kubectl connectivity"
        log.info(f"  {spec.name:<{name_w}}  {spec.url:<28}  [{state}]")

    for spec in skipped:
        log.info(f"  {spec.name:<{name_w}}  {spec.url:<28}  [SKIPPED — service not found]")

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

    log.info("All port-forwards stopped.")
    log.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
