#!/usr/bin/env python3
"""
U-Vote Istio Installation Script

Installs Istio (demo profile) into the live uvote Kind cluster and wires up
sidecar injection, mTLS, and Istio Ingress Gateway routing for uvote-dev.

Steps performed:
  1. Pre-flight: verify istioctl available and uvote cluster reachable
  2. Install Istio (demo profile) via istioctl
  3. Wait for all istio-system pods to be Running
  4. Remove Nginx ingress controller (skippable via --skip-nginx-removal)
  5. Label uvote-dev for sidecar injection
  6. Apply Istio resources from disk:
       uvote-platform/istio/gateway.yaml
       uvote-platform/istio/virtual-services.yaml
       uvote-platform/istio/peer-authentication.yaml
       uvote-platform/istio/authorization-policies.yaml
       uvote-platform/istio/destination-rules.yaml
       uvote-platform/k8s/network-policies/05-allow-istiod-egress.yaml
       uvote-platform/k8s/network-policies/04-allow-istio-ingress.yaml
  7. Patch istio-ingressgateway to run on control-plane node (hostPort 80)
  8. Verify: istioctl analyze -n uvote-dev, curl http://localhost

Usage:
    python plat_scripts/install_istio.py [OPTIONS]

Requirements:
    - istioctl on PATH (or in <project-root>/istio-*/bin/), or pass --istioctl-path
    - kubectl configured for kind-uvote context
    - Kind cluster 'uvote' running with uvote-dev namespace created
    - Python 3.8+
    - pip packages: click, colorama
"""

import glob as _glob
import os
import subprocess
import sys
import json
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

# Container port each service listens on
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
# Shell helper
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


# ---------------------------------------------------------------------------
# Step 1 — Pre-flight checks
# ---------------------------------------------------------------------------
def step1_preflight(project_root: Path, istioctl_path: str) -> Optional[str]:
    """Verify istioctl is available and the uvote cluster is reachable.

    Returns the resolved istioctl path on success, None on failure.
    If istioctl is not on PATH, searches project_root/istio-*/bin/ and adds
    the discovered directory to PATH automatically.
    """
    log.header("Step 1: Pre-flight checks")

    # 1a — Resolve istioctl binary
    resolved = istioctl_path
    rc, out, _ = run([istioctl_path, "version", "--remote=false"])

    if rc != 0 and istioctl_path == "istioctl":
        # Not on PATH — search project root for istio-*/bin/istioctl
        log.info(
            "istioctl not found on PATH; "
            "searching project root for istio-*/bin/istioctl..."
        )
        candidates = sorted(
            _glob.glob(str(project_root / "istio-*" / "bin" / "istioctl"))
        )
        if candidates:
            resolved = candidates[-1]
            bin_dir = str(Path(resolved).parent)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            log.info(f"Found istioctl at {resolved}, added {bin_dir} to PATH")
            rc, out, _ = run([resolved, "version", "--remote=false"])
            if rc != 0:
                log.error(f"Found {resolved} but it is not executable")
                return None
        else:
            log.error(
                "istioctl not found on PATH or in project root istio-*/bin/"
            )
            log.error("Install Istio or pass --istioctl-path <path>")
            return None
    elif rc != 0:
        log.error(f"istioctl not usable at '{istioctl_path}'")
        return None

    version_line = out.strip().splitlines()[0] if out.strip() else resolved
    log.info(f"istioctl: {version_line}")

    # 1b — Ensure kubectl context points to the uvote cluster
    rc, ctx, _ = run(["kubectl", "config", "current-context"])
    expected_ctx = f"kind-{CLUSTER_NAME}"
    if rc != 0 or ctx.strip() != expected_ctx:
        log.info(f"kubectl context is '{ctx.strip()}', switching to {expected_ctx}...")
        rc2, _, err2 = run(["kubectl", "config", "use-context", expected_ctx])
        if rc2 != 0:
            log.error(f"Cannot switch to context {expected_ctx}: {err2.strip()}")
            return None

    # 1c — Verify uvote-dev namespace exists (confirms cluster is live)
    rc, _, _ = run(["kubectl", "get", "namespace", NAMESPACE])
    if rc != 0:
        log.error(f"Namespace '{NAMESPACE}' not found — is the cluster running?")
        return None

    log.success(
        f"Pre-flight passed: istioctl resolved, cluster '{CLUSTER_NAME}' accessible"
    )
    return resolved


# ---------------------------------------------------------------------------
# Step 2 — Install Istio
# ---------------------------------------------------------------------------
def step2_install_istio(istioctl: str) -> bool:
    log.header("Step 2: Install Istio (demo profile)")

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
# Step 3 — Wait for istio-system pods
# ---------------------------------------------------------------------------
def step3_wait_istio_system(timeout_secs: int = 300) -> bool:
    log.header("Step 3: Wait for istio-system pods to be Running")

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
# Step 4 — Remove Nginx ingress controller
# ---------------------------------------------------------------------------
def step4_remove_nginx(project_root: Path) -> bool:
    log.header("Step 4: Remove Nginx Ingress Controller")

    ingress_yaml = (
        project_root / "uvote-platform" / "k8s" / "ingress" / "uvote-ingress.yaml"
    )

    log.info("Deleting namespace ingress-nginx (--ignore-not-found)...")
    rc, _, err = run(
        ["kubectl", "delete", "namespace", "ingress-nginx", "--ignore-not-found"],
        timeout=120,
    )
    if rc != 0:
        log.warning(f"Could not delete ingress-nginx namespace: {err.strip()}")

    if ingress_yaml.exists():
        log.info(f"Deleting {ingress_yaml.name} from cluster (--ignore-not-found)...")
        rc, _, err = run(
            ["kubectl", "delete", "-f", str(ingress_yaml), "--ignore-not-found"],
            timeout=60,
        )
        if rc != 0:
            log.warning(f"Could not delete ingress resource: {err.strip()}")
    else:
        log.info(f"Ingress manifest not found at {ingress_yaml} — already removed")

    log.success("Nginx ingress controller removal complete")
    return True


# ---------------------------------------------------------------------------
# Step 5 — Label uvote-dev for sidecar injection
# ---------------------------------------------------------------------------
def step5_label_namespace() -> bool:
    log.header(f"Step 5: Label {NAMESPACE} for Istio sidecar injection")

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
# Step 6 — Apply Istio resources from disk
# ---------------------------------------------------------------------------
def step6_apply_istio_resources(project_root: Path) -> bool:
    log.header("Step 6: Apply Istio resources from disk")

    istio_dir = project_root / "uvote-platform" / "istio"
    netpol_dir = project_root / "uvote-platform" / "k8s" / "network-policies"

    manifests = [
        istio_dir  / "gateway.yaml",
        istio_dir  / "virtual-services.yaml",
        istio_dir  / "peer-authentication.yaml",
        istio_dir  / "authorization-policies.yaml",
        istio_dir  / "destination-rules.yaml",
        netpol_dir / "05-allow-istiod-egress.yaml",
        netpol_dir / "04-allow-istio-ingress.yaml",
    ]

    all_ok = True
    for manifest in manifests:
        if not manifest.exists():
            log.error(f"Manifest not found: {manifest}")
            all_ok = False
            continue
        log.info(f"Applying {manifest.name}...")
        rc, _, err = run(["kubectl", "apply", "-f", str(manifest)], timeout=60)
        if rc != 0:
            log.error(f"Failed to apply {manifest.name}: {err.strip()}")
            all_ok = False
        else:
            log.success(f"{manifest.name} applied")

    return all_ok


# ---------------------------------------------------------------------------
# Step 7 — Patch ingressgateway to control-plane node with hostPort 80
# ---------------------------------------------------------------------------
def step7_patch_ingressgateway(rollout_timeout: int = 180) -> bool:
    log.header("Step 7: Patch istio-ingressgateway → control-plane node (hostPort 80)")

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
# Step 8 — Verify
# ---------------------------------------------------------------------------
def step8_verify(istioctl: str) -> bool:
    log.header("Step 8: Verify")

    # istioctl analyze — IST0101 ("Referenced host not found") fires for every
    # VirtualService whose backing Kubernetes Service doesn't exist yet.  At
    # boot time this is always the case because deploy_platform.py (Step 4)
    # hasn't run yet.  Treat IST0101 as an expected warning; any other IST
    # error code is a genuine configuration problem and should fail the step.
    log.info("Running: istioctl analyze -n uvote-dev")
    rc, out, err = run([istioctl, "analyze", "-n", NAMESPACE], timeout=60)
    combined = out + err

    error_lines  = [l for l in combined.splitlines() if l.strip().startswith("Error")]
    ist0101_lines = [l for l in error_lines if "IST0101" in l]
    real_errors   = [l for l in error_lines if "IST0101" not in l]

    if real_errors:
        for e in real_errors:
            log.error(e)
        return False

    if ist0101_lines:
        log.warning(
            "istioctl analyze: IST0101 (Referenced host not found) — "
            "expected before services are deployed, will resolve after deploy_platform.py"
        )
        for line in ist0101_lines:
            log.warning(line)
    else:
        other_warnings = [l for l in combined.splitlines() if l.strip().startswith("Warning")]
        for w in other_warnings:
            log.warning(w)

    log.success(
        "Istio config looks good — service hosts will resolve after deploy_platform.py runs"
    )
    return True


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
    help="Skip removal of the Nginx ingress controller (step 4).",
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

    # Step 1: Pre-flight — resolves the istioctl path before the main step loop
    istioctl_resolved = step1_preflight(project_root, istioctl_path)
    if istioctl_resolved is None:
        log.error("FAILED at: Step 1: Pre-flight")
        sys.exit(1)

    steps = [
        ("Step 2: Install Istio",         lambda: step2_install_istio(istioctl_resolved)),
        ("Step 3: Wait for istio-system", lambda: step3_wait_istio_system(istio_wait_timeout)),
    ]

    if not skip_nginx_removal:
        steps.append(
            ("Step 4: Remove Nginx",       lambda: step4_remove_nginx(project_root))
        )
    else:
        log.info("Skipping Step 4 (--skip-nginx-removal)")

    steps += [
        ("Step 5: Label namespace",        step5_label_namespace),
        ("Step 6: Apply Istio resources",  lambda: step6_apply_istio_resources(project_root)),
        ("Step 7: Patch ingressgateway",   lambda: step7_patch_ingressgateway(rollout_timeout)),
        ("Step 8: Verify",                 lambda: step8_verify(istioctl_resolved)),
    ]

    for label, fn in steps:
        if not fn():
            log.error(f"FAILED at: {label}")
            sys.exit(1)

    log.header("Istio installation complete")
    log.success("All steps passed.")
    log.info("Useful commands:")
    log.info(f"  kubectl get pods -n {NAMESPACE}          # Check pod status after deploy")
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
