#!/usr/bin/env python3
"""
boot_platform.py — single-command dev/production platform orchestrator.

Brings up the full U-Vote platform from nothing to fully running by running
the following steps in order, stopping on any failure:

  Step 1 — Cluster setup      (plat_scripts/setup_k8s_platform.py)
  Step 2 — App deployment     (plat_scripts/deploy_platform.py)
  Step 3 — ELK stack          (helm install elasticsearch / kibana / fluent-bit)
  Step 4 — Final health check (kubectl get pods -n uvote-dev / monitoring)
  Step 5 — Kibana dashboard   (plat_scripts/create_dashboard.py)
  Step 6 — Kubernetes dashboard reminder (run plat_scripts/k8s_dashboard.py manually)

Usage:
    python boot_platform.py
    python boot_platform.py --skip-cluster
    python boot_platform.py --skip-elk
    python boot_platform.py --skip-cluster --skip-elk

Steps: cluster setup → app deployment → ELK stack → health check →
       Kibana dashboard → Kubernetes dashboard.
"""

import argparse
import base64
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
SETUP_SCRIPT      = PROJECT_ROOT / "plat_scripts" / "setup_k8s_platform.py"
DEPLOY_SCRIPT     = PROJECT_ROOT / "plat_scripts" / "deploy_platform.py"
ELK_VALUES_DIR    = PROJECT_ROOT / "uvote-platform" / "k8s" / "logging"
DASHBOARD_SCRIPT  = PROJECT_ROOT / "plat_scripts" / "create_dashboard.py"


# ═══════════════════════════════════════════════════════════════════════════
# Logger — matches DeploymentLogger in deploy_test_platform.py.
# Uses ANSI escape codes directly (no colorama dependency).
# ═══════════════════════════════════════════════════════════════════════════
class DeploymentLogger:
    """Dual logger: ANSI-coloured console + plain-text log file."""

    LEVEL_COLOURS = {
        "INFO":    "\033[37m",   # white
        "SUCCESS": "\033[32m",   # green
        "WARNING": "\033[33m",   # yellow
        "ERROR":   "\033[31m",   # red
        "DEBUG":   "\033[36m",   # cyan
    }
    RESET = "\033[0m"

    def __init__(self, log_file: Path, verbose: bool = False):
        self.log_file = log_file
        self.verbose = verbose
        self.start_time = time.time()
        self._fh = open(log_file, "a", encoding="utf-8")

    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain = f"[{ts}] [{level}] {message}"
        colour = self.LEVEL_COLOURS.get(level, "")
        coloured = f"{colour}[{ts}] [{level}]{self.RESET} {message}"
        if level == "DEBUG" and not self.verbose:
            self._fh.write(plain + "\n")
            self._fh.flush()
            return
        print(coloured)
        self._fh.write(plain + "\n")
        self._fh.flush()

    def info(self, msg: str) -> None:    self.log("INFO", msg)
    def success(self, msg: str) -> None: self.log("SUCCESS", msg)
    def warning(self, msg: str) -> None: self.log("WARNING", msg)
    def error(self, msg: str) -> None:   self.log("ERROR", msg)
    def debug(self, msg: str) -> None:   self.log("DEBUG", msg)

    def header(self, msg: str) -> None:
        sep = "=" * 60
        self.info(sep)
        self.info(msg)
        self.info(sep)

    def elapsed(self) -> str:
        secs = int(time.time() - self.start_time)
        m, s = divmod(secs, 60)
        return f"{m}m {s:02d}s"

    def close(self) -> None:
        self._fh.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(cmd: list, cwd: Path = None, timeout: int = 120) -> Tuple[int, str, str]:
    """Run a command, capture output, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"timed out after {timeout}s"
    except FileNotFoundError:
        return 1, "", f"command not found: {cmd[0]}"


def run_subprocess_step(logger: DeploymentLogger, description: str, cmd: list) -> bool:
    """Run a subprocess, streaming its output to the terminal, return success."""
    logger.info(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        logger.error(f"{description} failed (exit code {result.returncode})")
        return False
    logger.success(f"{description} completed")
    return True


# ---------------------------------------------------------------------------
# Step 1 — Cluster setup
# ---------------------------------------------------------------------------
def step1_cluster_setup(logger: DeploymentLogger, skip_cluster: bool) -> bool:
    logger.header("Step 1 — Cluster Setup (setup_k8s_platform.py)")

    cmd = [sys.executable, str(SETUP_SCRIPT)]
    if skip_cluster:
        cmd.append("--skip-cluster")

    return run_subprocess_step(logger, "Cluster setup", cmd)


# ---------------------------------------------------------------------------
# Step 2 — Application deployment
# ---------------------------------------------------------------------------
def step2_app_deployment(logger: DeploymentLogger) -> bool:
    logger.header("Step 2 — Application Deployment (deploy_platform.py)")
    return run_subprocess_step(
        logger, "Application deployment", [sys.executable, str(DEPLOY_SCRIPT)]
    )


# ---------------------------------------------------------------------------
# Step 3 — ELK stack deployment (inline)
# ---------------------------------------------------------------------------
def step3_elk_deployment(logger: DeploymentLogger) -> bool:
    logger.header("Step 3 — ELK Stack Deployment")

    es_values   = ELK_VALUES_DIR / "elasticsearch-values.yaml"
    kb_values   = ELK_VALUES_DIR / "kibana-values.yaml"
    fb_values   = ELK_VALUES_DIR / "fluent-bit-values.yaml"

    for f in (es_values, kb_values, fb_values):
        if not f.exists():
            logger.error(f"Values file not found: {f}")
            return False

    # -- Elasticsearch -------------------------------------------------------
    logger.info("Installing Elasticsearch via Helm...")
    rc, out, err = run_cmd(
        [
            "helm", "install", "elasticsearch", "elastic/elasticsearch",
            "--namespace", "monitoring",
            "-f", str(es_values),
            "--timeout", "10m",
            "--wait",
        ],
        timeout=620,
    )
    if rc != 0 and "already exists" not in err and "already exists" not in out:
        logger.error(f"Elasticsearch install failed: {err.strip() or out.strip()}")
        return False
    if rc == 0:
        logger.success("Elasticsearch installed")
    else:
        logger.warning("Elasticsearch release already exists — skipping install")

    # Wait for elasticsearch-master-0 to be Ready
    logger.info("Waiting for elasticsearch-master-0 to be Ready (up to 10m)...")
    rc, out, err = run_cmd(
        [
            "kubectl", "wait", "pod/elasticsearch-master-0",
            "-n", "monitoring",
            "--for=condition=Ready",
            "--timeout=600s",
        ],
        timeout=620,
    )
    if rc != 0:
        logger.error(f"elasticsearch-master-0 did not become Ready: {err.strip()}")
        return False
    logger.success("elasticsearch-master-0 is Ready")

    # -- Kibana --------------------------------------------------------------
    logger.info("Installing Kibana via Helm...")
    rc, out, err = run_cmd(
        [
            "helm", "install", "kibana", "elastic/kibana",
            "--namespace", "monitoring",
            "-f", str(kb_values),
            "--timeout", "5m",
            "--wait",
        ],
        timeout=320,
    )
    if rc != 0 and "already exists" not in err and "already exists" not in out:
        logger.error(f"Kibana install failed: {err.strip() or out.strip()}")
        return False
    if rc == 0:
        logger.success("Kibana installed")
    else:
        logger.warning("Kibana release already exists — skipping install")

    # -- Fluent Bit ----------------------------------------------------------
    logger.info("Installing Fluent Bit via Helm...")
    rc, out, err = run_cmd(
        [
            "helm", "install", "fluent-bit", "fluent/fluent-bit",
            "--namespace", "monitoring",
            "-f", str(fb_values),
            "--timeout", "3m",
            "--wait",
        ],
        timeout=200,
    )
    if rc != 0 and "already exists" not in err and "already exists" not in out:
        logger.error(f"Fluent Bit install failed: {err.strip() or out.strip()}")
        return False
    if rc == 0:
        logger.success("Fluent Bit installed")
    else:
        logger.warning("Fluent Bit release already exists — skipping install")

    return True


# ---------------------------------------------------------------------------
# Step 4 — Final health check
# ---------------------------------------------------------------------------
def step4_health_check(logger: DeploymentLogger) -> None:
    logger.header("Step 4 — Final Health Check")

    for ns in ("uvote-dev", "monitoring"):
        logger.info(f"Pods in namespace '{ns}':")
        rc, out, err = run_cmd(["kubectl", "get", "pods", "-n", ns])
        if rc == 0:
            for line in out.strip().splitlines():
                logger.info(f"  {line}")
        else:
            logger.warning(f"  Could not list pods in '{ns}': {err.strip()}")

    # Count running pods in each namespace
    for ns in ("uvote-dev", "monitoring"):
        rc, out, _ = run_cmd(["kubectl", "get", "pods", "-n", ns, "--no-headers"])
        if rc == 0:
            lines = [l for l in out.strip().splitlines() if l]
            running = sum(1 for l in lines if "Running" in l)
            total   = len(lines)
            if running == total and total > 0:
                logger.success(f"All {total} pods Running in '{ns}'")
            else:
                logger.warning(f"{running}/{total} pods Running in '{ns}'")


# ---------------------------------------------------------------------------
# Step 5 — Kibana dashboard setup
# ---------------------------------------------------------------------------

def _wait_for_port(port: int, interval: float = 0.5, timeout: float = 30.0) -> bool:
    """Poll until localhost:port accepts a TCP connection."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(interval)
    return False


def step5_kibana_dashboard(logger: DeploymentLogger) -> None:
    logger.header("Step 5 — Kibana Dashboard Setup")

    # 1. Wait for Kibana API to be ready
    logger.info("Waiting 15s for Kibana API to become ready...")
    time.sleep(15)

    # 2. Start temporary port-forward
    logger.info("Starting temporary port-forward: svc/kibana-kibana 5601:5601 -n monitoring")
    pf_proc = subprocess.Popen(
        [
            "kubectl", "port-forward",
            "-n", "monitoring",
            "svc/kibana-kibana",
            "5601:5601",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        # 3. Poll port 5601
        logger.info("Polling port 5601 (0.5s interval, 30s timeout)...")
        if not _wait_for_port(5601):
            logger.warning("Port 5601 did not open within 30s — skipping dashboard creation")
            return

        logger.success("Kibana port-forward established on port 5601")

        # 4. Retrieve elastic password
        rc, out, err = run_cmd(
            [
                "kubectl", "get", "secret", "elasticsearch-master-credentials",
                "-n", "monitoring",
                "-o", "jsonpath={.data.password}",
            ]
        )
        if rc != 0 or not out.strip():
            logger.warning(
                f"Could not retrieve elastic password: {err.strip() or 'empty output'} "
                "— skipping dashboard creation"
            )
            return

        try:
            password = base64.b64decode(out.strip()).decode("utf-8")
        except Exception as exc:
            logger.warning(f"Could not decode elastic password: {exc} — skipping dashboard creation")
            return

        # 5. Run create_dashboard.py with ES_PASSWORD injected
        logger.info(f"Running {DASHBOARD_SCRIPT.name}...")
        env = {**os.environ, "ES_PASSWORD": password}
        result = subprocess.run(
            [sys.executable, str(DASHBOARD_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # 7. Log outcome (non-fatal)
        if result.returncode == 0:
            logger.success("Kibana dashboard created successfully")
            for line in result.stdout.strip().splitlines():
                logger.info(f"  {line}")
        else:
            logger.warning("Kibana dashboard creation failed (non-fatal)")
            for line in (result.stdout + result.stderr).strip().splitlines():
                logger.warning(f"  {line}")

    finally:
        # 6. Terminate port-forward
        if pf_proc.poll() is None:
            pf_proc.terminate()
            try:
                pf_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pf_proc.kill()
        logger.info("Temporary port-forward terminated")


# ---------------------------------------------------------------------------
# Step 6 — Kubernetes Dashboard reminder
# ---------------------------------------------------------------------------
def step6_k8s_dashboard(logger: DeploymentLogger) -> None:
    logger.header("Step 6 — Kubernetes Dashboard")
    logger.info("To open the Kubernetes dashboard run:")
    logger.info("  python plat_scripts/k8s_dashboard.py")
    logger.info("The token will be printed to the terminal when you run it.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="boot_platform.py",
        description=(
            "Bring up the full U-Vote platform from scratch.\n"
            "\n"
            "Steps: cluster setup → app deployment → ELK stack → health check → Kibana dashboard."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # Full boot (from nothing)\n"
            "  python boot_platform.py\n"
            "\n"
            "  # Cluster already exists\n"
            "  python boot_platform.py --skip-cluster\n"
            "\n"
            "  # Skip ELK (already deployed)\n"
            "  python boot_platform.py --skip-elk\n"
        ),
    )
    parser.add_argument(
        "--skip-cluster",
        action="store_true",
        help="Skip Step 1: cluster setup (use existing Kind cluster)",
    )
    parser.add_argument(
        "--skip-elk",
        action="store_true",
        help="Skip Step 3: ELK stack deployment (already deployed)",
    )
    args = parser.parse_args()

    # Set up logging
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = logs_dir / f"boot-platform-{timestamp}.log"
    logger = DeploymentLogger(log_file)

    logger.header("U-Vote Platform Boot")
    logger.info(f"Log file: {log_file}")
    logger.info(f"--skip-cluster: {args.skip_cluster}")
    logger.info(f"--skip-elk:     {args.skip_elk}")

    ok = True

    # Step 1
    if not args.skip_cluster:
        ok = step1_cluster_setup(logger, skip_cluster=False)
    else:
        logger.info("Step 1: Cluster setup skipped (--skip-cluster)")

    # Step 2
    if ok:
        ok = step2_app_deployment(logger)

    # Step 3
    if ok:
        if not args.skip_elk:
            ok = step3_elk_deployment(logger)
        else:
            logger.info("Step 3: ELK stack skipped (--skip-elk)")

    # Step 4 — always run (informational only)
    if ok:
        step4_health_check(logger)

    # Step 5 — non-fatal; skipped when --skip-elk (no ELK stack to connect to)
    if ok:
        if not args.skip_elk:
            step5_kibana_dashboard(logger)
        else:
            logger.info("Step 5: Kibana dashboard skipped (--skip-elk)")

    # Step 6 — always run (non-fatal)
    if ok:
        step6_k8s_dashboard(logger)

    # Final result
    elapsed = logger.elapsed()
    logger.info("")
    if ok:
        logger.success(f"Platform boot complete in {elapsed}")
        logger.info(f"Log file: {log_file}")
        logger.close()
        sys.exit(0)
    else:
        logger.error(f"Platform boot FAILED after {elapsed}")
        logger.info(f"Log file: {log_file}")
        logger.close()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[WARNING] Boot interrupted by user")
        sys.exit(130)
