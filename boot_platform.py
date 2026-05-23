#!/usr/bin/env python3
"""
boot_platform.py — single-command full platform orchestrator.

Brings up the full U-Vote platform from nothing by running four scripts in
order, stopping immediately on any failure:

  Step 1 — Cluster setup     plat_scripts/setup_k8s_platform.py
  Step 2 — Istio             plat_scripts/install_istio.py
  Step 3 — App deployment    plat_scripts/deploy_platform.py
  Step 4 — Observability     plat_scripts/install_observability.py

Usage:
    python boot_platform.py
    python boot_platform.py --skip-istio --skip-observability
    python boot_platform.py --skip-deploy
    python boot_platform.py --cluster-name my-cluster --namespace my-ns
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import click
except ImportError:
    print("ERROR: 'click' package required. Install with: pip install click")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent

SETUP_SCRIPT         = PROJECT_ROOT / "plat_scripts" / "setup_k8s_platform.py"
ISTIO_SCRIPT         = PROJECT_ROOT / "plat_scripts" / "install_istio.py"
OBSERVABILITY_SCRIPT = PROJECT_ROOT / "plat_scripts" / "install_observability.py"
DEPLOY_SCRIPT        = PROJECT_ROOT / "plat_scripts" / "deploy_platform.py"

# ---------------------------------------------------------------------------
# Shared logger — boot_platform.py lives at the project root, not inside
# plat_scripts/, so plat_scripts/ must be on sys.path before the import.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(PROJECT_ROOT / "plat_scripts"))
from shared.logger import DeploymentLogger  # noqa: E402


# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

def run_step(log: DeploymentLogger, label: str, cmd: List[str]) -> bool:
    """Run a subprocess, stream its output live to stdout, return success."""
    log.info(f"Starting {label}")
    log.info(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode == 0:
        log.success(f"{label} succeeded")
        return True
    log.error(f"{label} failed (exit code {result.returncode})")
    return False


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

_OUTCOME_ICON = {"pass": "✅", "skip": "⏭ ", "fail": "❌"}

def print_summary(
    log: DeploymentLogger,
    plan: List[Tuple[str, str, bool]],
    outcomes: Dict[str, str],
) -> None:
    log.header("Boot Summary")
    for step_id, script_name, _ in plan:
        outcome = outcomes.get(step_id, "not reached")
        icon = _OUTCOME_ICON.get(outcome, "  ")
        log.info(f"  {icon}  {step_id}  {script_name:<34} {outcome.upper()}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--skip-deploy",
    is_flag=True,
    default=False,
    help="Skip Step 3: application service deployment.",
)
@click.option(
    "--skip-istio",
    is_flag=True,
    default=False,
    help="Skip Step 2: Istio installation.",
)
@click.option(
    "--skip-observability",
    is_flag=True,
    default=False,
    help="Skip Step 4: observability addons (Prometheus, Grafana, Kiali, Jaeger).",
)
@click.option(
    "--cluster-name",
    default="uvote",
    show_default=True,
    help="Kind cluster name — passed to deploy_platform.py.",
)
@click.option(
    "--namespace",
    default="uvote-dev",
    show_default=True,
    help="Kubernetes namespace — passed to deploy_platform.py.",
)
def main(
    skip_istio: bool,
    skip_observability: bool,
    skip_deploy: bool,
    cluster_name: str,
    namespace: str,
) -> None:
    """Bring up the full U-Vote platform from scratch.

    \b
    Boot sequence:
      Step 1  setup_k8s_platform.py     always
      Step 2  install_istio.py          skipped with --skip-istio
      Step 3  deploy_platform.py        skipped with --skip-deploy
      Step 4  install_observability.py  skipped with --skip-observability

    \b
    Notes:
      --skip-build is always passed to deploy_platform.py because images are
      expected to be pre-built before running the boot sequence.

      --skip-nginx-removal is always passed to install_istio.py because Nginx
      removal is managed by setup_k8s_platform.py, not the boot script.
    """
    # Set up logging
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = logs_dir / f"boot-platform-{timestamp}.log"
    log = DeploymentLogger(log_file)

    # Boot plan — (step_id, script_name, skipped)
    plan: List[Tuple[str, str, bool]] = [
        ("Step 1", "setup_k8s_platform.py",   False),
        ("Step 2", "install_istio.py",         skip_istio),
        ("Step 3", "deploy_platform.py",       skip_deploy),
        ("Step 4", "install_observability.py", skip_observability),
    ]

    log.header("U-Vote Platform Boot")
    log.info(f"Log file  : {log_file}")
    log.info(f"Cluster   : {cluster_name}")
    log.info(f"Namespace : {namespace}")
    log.info("")
    log.info("Boot plan:")
    for step_id, script_name, skipped in plan:
        status = "SKIP" if skipped else "RUN "
        log.info(f"  [{status}]  {step_id}  {script_name}")
    log.info("")

    outcomes: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Step 1 — setup_k8s_platform.py (always runs)
    # ------------------------------------------------------------------
    cmd1 = [sys.executable, str(SETUP_SCRIPT)]
    if run_step(log, "Step 1 (setup_k8s_platform.py)", cmd1):
        outcomes["Step 1"] = "pass"
    else:
        outcomes["Step 1"] = "fail"
        log.error("Aborting boot sequence after Step 1 failure.")
        print_summary(log, plan, outcomes)
        log.close()
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2 — install_istio.py
    # ------------------------------------------------------------------
    if skip_istio:
        log.info("Step 2 skipped (--skip-istio)")
        outcomes["Step 2"] = "skip"
    else:
        # --skip-nginx-removal is unconditional: Nginx removal is handled by
        # setup_k8s_platform.py, not the boot script.
        cmd2 = [sys.executable, str(ISTIO_SCRIPT), "--skip-nginx-removal"]
        if run_step(log, "Step 2 (install_istio.py)", cmd2):
            outcomes["Step 2"] = "pass"
        else:
            outcomes["Step 2"] = "fail"
            log.error("Aborting boot sequence after Step 2 failure.")
            print_summary(log, plan, outcomes)
            log.close()
            sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3 — deploy_platform.py
    # ------------------------------------------------------------------
    if skip_deploy:
        log.info("Step 3 skipped (--skip-deploy)")
        outcomes["Step 3"] = "skip"
    else:
        # --skip-build: images are expected to be pre-built in the boot sequence.
        cmd3 = [
            sys.executable, str(DEPLOY_SCRIPT),
            "--skip-build",
            "--cluster-name", cluster_name,
            "--namespace", namespace,
        ]
        if run_step(log, "Step 3 (deploy_platform.py)", cmd3):
            outcomes["Step 3"] = "pass"
        else:
            outcomes["Step 3"] = "fail"
            log.error("Aborting boot sequence after Step 3 failure.")
            print_summary(log, plan, outcomes)
            log.close()
            sys.exit(1)

    # ------------------------------------------------------------------
    # Step 4 — install_observability.py
    # ------------------------------------------------------------------
    if skip_observability:
        log.info("Step 4 skipped (--skip-observability)")
        outcomes["Step 4"] = "skip"
    else:
        cmd4 = [sys.executable, str(OBSERVABILITY_SCRIPT)]
        if run_step(log, "Step 4 (install_observability.py)", cmd4):
            outcomes["Step 4"] = "pass"
        else:
            outcomes["Step 4"] = "fail"
            log.error("Aborting boot sequence after Step 4 failure.")
            print_summary(log, plan, outcomes)
            log.close()
            sys.exit(1)

    # ------------------------------------------------------------------
    # All steps done
    # ------------------------------------------------------------------
    print_summary(log, plan, outcomes)
    log.success(f"Platform boot complete in {log.elapsed()}")
    log.info(f"Log file: {log_file}")
    log.close()
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[WARNING] Boot interrupted by user")
        sys.exit(130)
