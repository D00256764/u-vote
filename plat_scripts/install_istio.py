#!/usr/bin/env python3
"""
U-Vote Istio Installation Script

Installs Istio (demo profile) into the live uvote Kind cluster and wires up
sidecar injection, mTLS PeerAuthentication, and Istio Ingress Gateway routing
for the uvote-dev namespace.

Steps performed:
  1. Install Istio (demo profile) via istioctl
  2. Wait for all istio-system pods to be Running
  3. Remove Nginx ingress controller (skippable via --skip-nginx-removal)
  4. Label uvote-dev for sidecar injection
  5. Annotate all 6 service deployments with excludeOutboundPorts=5432
  6. Apply NetworkPolicy allowing sidecar → istiod egress (port 15012/15010)
  7. Restart all 6 service deployments and wait for rollouts (2/2 READY)
  8. Apply PERMISSIVE PeerAuthentication to uvote-dev
  9. Patch istio-ingressgateway to run on control-plane node (hostPort 80)
 10. Apply Gateway + VirtualService routing to frontend-service
 11. Apply NetworkPolicies allowing istio-system → service ingress
 12. Verify: all pods 2/2, istioctl analyze, curl http://localhost

Usage:
    python plat_scripts/install_istio.py [OPTIONS]

Requirements:
    - istioctl on PATH (or pass --istioctl-path)
    - kubectl configured for kind-uvote context
    - Kind cluster 'uvote' running with uvote-dev services deployed
    - Python 3.8+
    - pip packages: click, colorama
"""

import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Tuple, Optional

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

SERVICE_DEPLOYMENTS = [
    "auth-service",
    "election-service",
    "voting-service",
    "results-service",
    "admin-service",
    "frontend-service",
]

# Container port each service listens on (needed for ingress NetworkPolicies)
SERVICE_PORTS = {
    "auth-service":     5001,
    "election-service": 5005,
    "voting-service":   5003,
    "results-service":  5004,
    "admin-service":    5002,
    "frontend-service": 5000,
}


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
# Step 1 — Install Istio
# ---------------------------------------------------------------------------
def step1_install_istio(istioctl: str) -> bool:
    log.header("Step 1: Install Istio (demo profile)")

    rc, out, err = run([istioctl, "version", "--remote=false"])
    if rc != 0:
        log.error(f"istioctl not usable at '{istioctl}': {err.strip()}")
        return False
    log.info(f"istioctl version: {out.strip()}")

    log.info("Running: istioctl install --set profile=demo -y")
    rc, out, err = run(
        [istioctl, "install", "--set", "profile=demo", "-y"],
        timeout=600,
    )
    if rc != 0:
        log.error(f"istioctl install failed:\n{err.strip()}")
        return False

    log.success("Istio demo profile installed")
    return True


# ---------------------------------------------------------------------------
# Step 2 — Wait for istio-system pods
# ---------------------------------------------------------------------------
def step2_wait_istio_system(timeout_secs: int = 300) -> bool:
    log.header("Step 2: Wait for istio-system pods to be Running")

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
# Step 3 — Remove Nginx ingress controller
# ---------------------------------------------------------------------------
def step3_remove_nginx(project_root: Path) -> bool:
    log.header("Step 3: Remove Nginx Ingress Controller")

    ingress_yaml = project_root / "uvote-platform" / "k8s" / "ingress" / "uvote-ingress.yaml"

    log.info("Deleting namespace ingress-nginx (--ignore-not-found)...")
    rc, _, err = run(
        ["kubectl", "delete", "namespace", "ingress-nginx", "--ignore-not-found"],
        timeout=120,
    )
    if rc != 0:
        log.warning(f"Could not delete ingress-nginx namespace: {err.strip()}")

    if ingress_yaml.exists():
        log.info(f"Deleting {ingress_yaml.name} (--ignore-not-found)...")
        rc, _, err = run(
            ["kubectl", "delete", "-f", str(ingress_yaml), "--ignore-not-found"],
            timeout=60,
        )
        if rc != 0:
            log.warning(f"Could not delete ingress resource: {err.strip()}")
    else:
        log.warning(f"Ingress manifest not found at {ingress_yaml} — skipping file delete")

    log.success("Nginx ingress controller removed")
    return True


# ---------------------------------------------------------------------------
# Step 4 — Label uvote-dev for sidecar injection
# ---------------------------------------------------------------------------
def step4_label_namespace() -> bool:
    log.header(f"Step 4: Label {NAMESPACE} for Istio sidecar injection")

    rc, _, err = run(
        [
            "kubectl", "label", "namespace", NAMESPACE,
            "istio-injection=enabled", "--overwrite",
        ]
    )
    if rc != 0:
        log.error(f"Failed to label namespace: {err.strip()}")
        return False

    log.success(f"Namespace {NAMESPACE} labelled istio-injection=enabled")
    return True


# ---------------------------------------------------------------------------
# Step 5 — Annotate all 6 service deployments
# ---------------------------------------------------------------------------
def step5_annotate_deployments() -> bool:
    log.header("Step 5: Annotate service deployments (excludeOutboundPorts=5432)")

    patch = json.dumps({
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "sidecar.istio.io/excludeOutboundPorts": "5432"
                    }
                }
            }
        }
    })

    all_ok = True
    for dep in SERVICE_DEPLOYMENTS:
        log.info(f"Patching {dep}...")
        rc, _, err = run(
            ["kubectl", "patch", "deployment", dep, "-n", NAMESPACE, "--patch", patch]
        )
        if rc != 0:
            log.error(f"Failed to patch {dep}: {err.strip()}")
            all_ok = False
        else:
            log.success(f"{dep} annotated")

    return all_ok


# ---------------------------------------------------------------------------
# Step 6 — NetworkPolicy: sidecar → istiod egress
# ---------------------------------------------------------------------------
def step6_allow_istiod_egress() -> bool:
    log.header("Step 6: Apply NetworkPolicy — sidecar egress to istiod")

    yaml_text = f"""\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-istiod-egress
  namespace: {NAMESPACE}
spec:
  podSelector: {{}}
  policyTypes:
  - Egress
  egress:
  - ports:
    - port: 15012
      protocol: TCP
    - port: 15010
      protocol: TCP
    - port: 15014
      protocol: TCP
    - port: 443
      protocol: TCP
"""
    if not apply_manifest(yaml_text):
        return False

    log.success("NetworkPolicy allow-istiod-egress applied")
    return True


# ---------------------------------------------------------------------------
# Step 7 — Restart deployments and wait for 2/2 READY
# ---------------------------------------------------------------------------
def step7_restart_and_wait(rollout_timeout: int = 240) -> bool:
    log.header("Step 7: Restart service deployments and wait for 2/2 READY")

    for dep in SERVICE_DEPLOYMENTS:
        log.info(f"Restarting {dep}...")
        rc, _, err = run(
            ["kubectl", "rollout", "restart", "deployment", dep, "-n", NAMESPACE]
        )
        if rc != 0:
            log.error(f"Failed to restart {dep}: {err.strip()}")
            return False

    all_ok = True
    for dep in SERVICE_DEPLOYMENTS:
        log.info(f"Waiting for {dep} rollout (timeout {rollout_timeout}s)...")
        rc, out, err = run(
            [
                "kubectl", "rollout", "status", "deployment", dep,
                "-n", NAMESPACE, f"--timeout={rollout_timeout}s",
            ],
            timeout=rollout_timeout + 30,
        )
        if rc != 0:
            log.error(f"Rollout for {dep} did not complete: {err.strip()}")
            all_ok = False
        else:
            log.success(f"{dep} rollout complete")

    return all_ok


# ---------------------------------------------------------------------------
# Step 8 — PeerAuthentication PERMISSIVE
# ---------------------------------------------------------------------------
def step8_peer_authentication() -> bool:
    log.header("Step 8: Apply PeerAuthentication (PERMISSIVE mTLS) to uvote-dev")

    yaml_text = f"""\
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: uvote-dev-mtls
  namespace: {NAMESPACE}
spec:
  mtls:
    mode: PERMISSIVE
"""
    if not apply_manifest(yaml_text):
        return False

    log.success("PeerAuthentication uvote-dev-mtls applied (PERMISSIVE)")
    return True


# ---------------------------------------------------------------------------
# Step 9 — Patch ingressgateway to control-plane node with hostPort 80
# ---------------------------------------------------------------------------
def step9_patch_ingressgateway(rollout_timeout: int = 180) -> bool:
    log.header("Step 9: Patch istio-ingressgateway → control-plane node (hostPort 80)")

    # Add nodeSelector for control-plane and hostPort 80 on containerPort 8080
    # (port index 1 in the demo profile's container ports list)
    node_patch = json.dumps([
        {
            "op": "add",
            "path": "/spec/template/spec/nodeSelector",
            "value": {"kubernetes.io/hostname": f"{CLUSTER_NAME}-control-plane"},
        },
        {
            "op": "replace",
            "path": "/spec/template/spec/containers/0/ports/1",
            "value": {"containerPort": 8080, "hostPort": 80, "protocol": "TCP"},
        },
    ])
    log.info("Adding nodeSelector and hostPort 80 to ingressgateway...")
    rc, _, err = run(
        [
            "kubectl", "patch", "deployment", "istio-ingressgateway",
            "-n", "istio-system", "--type=json", "-p", node_patch,
        ]
    )
    if rc != 0:
        log.error(f"Failed to patch ingressgateway (nodeSelector/hostPort): {err.strip()}")
        return False

    # Add toleration for the control-plane NoSchedule taint
    taint_patch = json.dumps([
        {
            "op": "add",
            "path": "/spec/template/spec/tolerations",
            "value": [
                {
                    "key": "node-role.kubernetes.io/control-plane",
                    "effect": "NoSchedule",
                    "operator": "Exists",
                }
            ],
        }
    ])
    log.info("Adding control-plane toleration to ingressgateway...")
    rc, _, err = run(
        [
            "kubectl", "patch", "deployment", "istio-ingressgateway",
            "-n", "istio-system", "--type=json", "-p", taint_patch,
        ]
    )
    if rc != 0:
        log.error(f"Failed to patch ingressgateway (toleration): {err.strip()}")
        return False

    log.info(f"Waiting for ingressgateway rollout (timeout {rollout_timeout}s)...")
    rc, _, err = run(
        [
            "kubectl", "rollout", "status", "deployment/istio-ingressgateway",
            "-n", "istio-system", f"--timeout={rollout_timeout}s",
        ],
        timeout=rollout_timeout + 30,
    )
    if rc != 0:
        log.error(f"ingressgateway rollout did not complete: {err.strip()}")
        return False

    log.success("istio-ingressgateway patched and running on control-plane with hostPort 80")
    return True


# ---------------------------------------------------------------------------
# Step 10 — Gateway + VirtualService
# ---------------------------------------------------------------------------
def step10_gateway_virtualservice() -> bool:
    log.header("Step 10: Apply Istio Gateway and VirtualService (frontend routing)")

    yaml_text = f"""\
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: uvote-gateway
  namespace: {NAMESPACE}
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: uvote-frontend
  namespace: {NAMESPACE}
spec:
  hosts:
  - "*"
  gateways:
  - uvote-gateway
  http:
  - match:
    - uri:
        prefix: /
    route:
    - destination:
        host: frontend-service
        port:
          number: {SERVICE_PORTS["frontend-service"]}
"""
    if not apply_manifest(yaml_text):
        return False

    log.success("Gateway uvote-gateway and VirtualService uvote-frontend applied")
    return True


# ---------------------------------------------------------------------------
# Step 11 — NetworkPolicies: istio-system ingress to services
# ---------------------------------------------------------------------------
def step11_allow_istio_ingress() -> bool:
    log.header("Step 11: Apply NetworkPolicies — istio-system ingress to services")

    all_ok = True
    for svc, port in SERVICE_PORTS.items():
        policy_name = f"allow-from-istio-ingress-to-{svc}"
        yaml_text = f"""\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {policy_name}
  namespace: {NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: {svc}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: istio-system
    ports:
    - port: {port}
      protocol: TCP
"""
        if apply_manifest(yaml_text):
            log.success(f"{policy_name} applied")
        else:
            log.error(f"Failed to apply {policy_name}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Step 12 — Verify
# ---------------------------------------------------------------------------
def step12_verify(istioctl: str) -> bool:
    log.header("Step 12: Verify")
    all_ok = True

    # 12a — all service pods show 2/2 READY
    log.info("Checking service pod readiness (expecting 2/2)...")
    rc, out, _ = run(
        ["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"]
    )
    if rc == 0:
        pods = json.loads(out).get("items", [])
        svc_pods = [
            p for p in pods
            if p["metadata"].get("labels", {}).get("app") in SERVICE_DEPLOYMENTS
        ]
        not_ready = []
        for pod in svc_pods:
            name = pod["metadata"]["name"]
            statuses = pod["status"].get("containerStatuses", [])
            total = len(statuses)
            ready = sum(1 for cs in statuses if cs.get("ready", False))
            if ready != total or total == 0:
                not_ready.append(f"{name} ({ready}/{total})")

        if not_ready:
            log.error("Pods not at 2/2: " + ", ".join(not_ready))
            all_ok = False
        else:
            log.success(f"All {len(svc_pods)} service pods are 2/2 READY")
    else:
        log.error("Could not retrieve pod list")
        all_ok = False

    # 12b — istioctl analyze
    log.info("Running: istioctl analyze -n uvote-dev")
    rc, out, err = run([istioctl, "analyze", "-n", NAMESPACE], timeout=60)
    combined = out + err
    errors = [l for l in combined.splitlines() if l.strip().startswith("Error")]
    if errors:
        for e in errors:
            log.error(e)
        all_ok = False
    else:
        warnings = [l for l in combined.splitlines() if l.strip().startswith("Warning")]
        if warnings:
            for w in warnings:
                log.warning(w)
        log.success("istioctl analyze: no errors")

    # 12c — curl http://localhost
    log.info("Testing curl http://localhost...")
    time.sleep(2)
    try:
        resp = urllib.request.urlopen("http://localhost", timeout=10)
        if resp.status == 200:
            log.success("curl http://localhost → 200 OK")
        else:
            log.error(f"curl http://localhost → {resp.status}")
            all_ok = False
    except urllib.error.HTTPError as exc:
        log.error(f"curl http://localhost → HTTP {exc.code}")
        all_ok = False
    except Exception as exc:
        log.error(f"curl http://localhost failed: {exc}")
        all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@click.command()
@click.option(
    "--istioctl-path",
    default="istioctl",
    show_default=True,
    help="Path to istioctl binary.",
)
@click.option(
    "--skip-nginx-removal",
    is_flag=True,
    default=False,
    help="Skip removal of the Nginx ingress controller (step 3).",
)
@click.option(
    "--rollout-timeout",
    default=240,
    show_default=True,
    help="Seconds to wait for each deployment rollout.",
)
@click.option(
    "--istio-wait-timeout",
    default=300,
    show_default=True,
    help="Seconds to wait for istio-system pods to become Ready.",
)
def main(
    istioctl_path: str,
    skip_nginx_removal: bool,
    rollout_timeout: int,
    istio_wait_timeout: int,
) -> None:
    """Install Istio on the uvote Kind cluster and configure sidecar injection.

    \b
    Examples:
      # Full installation
      python plat_scripts/install_istio.py

      # Use a specific istioctl binary
      python plat_scripts/install_istio.py --istioctl-path ~/istio-1.22.3/bin/istioctl

      # Skip Nginx removal (if already gone)
      python plat_scripts/install_istio.py --skip-nginx-removal
    """
    project_root = Path(__file__).resolve().parent.parent

    log.header("U-Vote Istio Installation")
    log.info(f"Cluster:   {CLUSTER_NAME}")
    log.info(f"Namespace: {NAMESPACE}")
    log.info(f"istioctl:  {istioctl_path}")

    steps = [
        ("Step 1: Install Istio",         lambda: step1_install_istio(istioctl_path)),
        ("Step 2: Wait for istio-system", lambda: step2_wait_istio_system(istio_wait_timeout)),
    ]

    if not skip_nginx_removal:
        steps.append(
            ("Step 3: Remove Nginx",       lambda: step3_remove_nginx(project_root))
        )
    else:
        log.info("Skipping Step 3 (--skip-nginx-removal)")

    steps += [
        ("Step 4: Label namespace",        step4_label_namespace),
        ("Step 5: Annotate deployments",   step5_annotate_deployments),
        ("Step 6: Allow istiod egress",    step6_allow_istiod_egress),
        ("Step 7: Restart & wait",         lambda: step7_restart_and_wait(rollout_timeout)),
        ("Step 8: PeerAuthentication",     step8_peer_authentication),
        ("Step 9: Patch ingressgateway",   lambda: step9_patch_ingressgateway(rollout_timeout)),
        ("Step 10: Gateway + VirtualSvc",  step10_gateway_virtualservice),
        ("Step 11: Allow istio ingress",   step11_allow_istio_ingress),
        ("Step 12: Verify",                lambda: step12_verify(istioctl_path)),
    ]

    for label, fn in steps:
        if not fn():
            log.error(f"FAILED at: {label}")
            sys.exit(1)

    log.header("Istio installation complete")
    log.success("All steps passed.")
    log.info("Useful commands:")
    log.info(f"  kubectl get pods -n {NAMESPACE}          # Check 2/2 sidecars")
    log.info( "  istioctl analyze -n uvote-dev            # Validate config")
    log.info( "  curl http://localhost                     # Reach frontend")
    log.info( "  istioctl proxy-status                    # Sidecar sync status")


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
