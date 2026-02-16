#!/usr/bin/env python3
"""
U-Vote Platform Deployment Script

Automates building, deploying, and testing the U-Vote secure online voting
platform on a Kind Kubernetes cluster.

Usage:
    python plat_scripts/deploy_platform.py [OPTIONS]

Requirements:
    - Docker
    - kubectl
    - Kind cluster running
    - Python 3.8+
    - Required packages: click, colorama
"""

import subprocess
import sys
import os
import time
import json
import base64
import secrets
import signal
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
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
# Service registry — maps image name to K8s deployment name, manifest file,
# container port, health endpoint, and whether it should access the database.
# ---------------------------------------------------------------------------
SERVICE_REGISTRY: Dict[str, dict] = {
    "auth-service": {
        "deploy_name": "auth-service",
        "manifest": "auth-deployment.yaml",
        "port": 5001,
        "health_path": "/health",
        "db_access": True,
    },
    "election-service": {
        "deploy_name": "election-service",
        "manifest": "election-deployment.yaml",
        "port": 5005,
        "health_path": "/health",
        "db_access": True,
    },
    "frontend-service": {
        "deploy_name": "frontend-service",
        "manifest": "frontend-deployment.yaml",
        "port": 5000,
        "health_path": "/",
        "db_access": False,
    },
    "results-service": {
        "deploy_name": "results-service",
        "manifest": "results-deployment.yaml",
        "port": 5004,
        "health_path": "/health",
        "db_access": True,
    },
    "voter-service": {
        "deploy_name": "admin-service",
        "manifest": "admin-deployment.yaml",
        "port": 5002,
        "health_path": "/health",
        "db_access": True,
    },
    "voting-service": {
        "deploy_name": "voting-service",
        "manifest": "voting-deployment.yaml",
        "port": 5003,
        "health_path": "/health",
        "db_access": True,
    },
}

# Ordered list of image names (build order)
ALL_SERVICES = list(SERVICE_REGISTRY.keys())

# Backend services deploy first, frontend last
BACKEND_SERVICES = [s for s in ALL_SERVICES if s != "frontend-service"]
FRONTEND_SERVICES = ["frontend-service"]


# ═══════════════════════════════════════════════════════════════════════════
# Logger
# ═══════════════════════════════════════════════════════════════════════════
class DeploymentLogger:
    """Dual logger: coloured console + plain-text log file."""

    LEVEL_COLORS = {
        "INFO": Fore.WHITE,
        "SUCCESS": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "DEBUG": Fore.CYAN,
    }

    def __init__(self, log_file: Path, verbose: bool = False):
        self.log_file = log_file
        self.verbose = verbose
        self.start_time = time.time()
        self._fh = open(log_file, "a", encoding="utf-8")

    # -- core -----------------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain = f"[{ts}] [{level}] {message}"
        color = self.LEVEL_COLORS.get(level, "")
        coloured = f"{color}[{ts}] [{level}]{Style.RESET_ALL} {message}"

        if level == "DEBUG" and not self.verbose:
            # Still write to file, just don't print
            self._fh.write(plain + "\n")
            self._fh.flush()
            return

        click.echo(coloured)
        self._fh.write(plain + "\n")
        self._fh.flush()

    def info(self, msg: str) -> None:
        self.log("INFO", msg)

    def success(self, msg: str) -> None:
        self.log("SUCCESS", msg)

    def warning(self, msg: str) -> None:
        self.log("WARNING", msg)

    def error(self, msg: str) -> None:
        self.log("ERROR", msg)

    def debug(self, msg: str) -> None:
        self.log("DEBUG", msg)

    def header(self, msg: str) -> None:
        sep = "=" * 56
        self.info(sep)
        self.info(msg)
        self.info(sep)

    def elapsed(self) -> str:
        secs = int(time.time() - self.start_time)
        m, s = divmod(secs, 60)
        return f"{m}m {s:02d}s"

    def close(self) -> None:
        self._fh.close()


# ═══════════════════════════════════════════════════════════════════════════
# Deployer
# ═══════════════════════════════════════════════════════════════════════════
class PlatformDeployer:
    """Main deployment orchestrator for the U-Vote platform."""

    def __init__(
        self,
        cluster_name: str,
        namespace: str,
        logger: DeploymentLogger,
        dry_run: bool = False,
    ):
        self.cluster_name = cluster_name
        self.namespace = namespace
        self.logger = logger
        self.dry_run = dry_run
        self.project_root = Path(__file__).resolve().parent.parent
        self.k8s_services_dir = self.project_root / "uvote-platform" / "k8s" / "services"
        self.results: Dict[str, list] = {
            "images_built": [],
            "images_failed": [],
            "images_loaded": [],
            "images_load_failed": [],
            "services_deployed": [],
            "services_failed": [],
            "pods_running": [],
            "pods_failed": [],
            "health_passed": [],
            "health_failed": [],
            "net_passed": [],
            "net_failed": [],
        }

    # -- helpers --------------------------------------------------------------
    def run_cmd(
        self,
        cmd: List[str],
        check: bool = True,
        timeout: int = 300,
        mutating: bool = False,
    ) -> Tuple[int, str, str]:
        """Run a command, return (returncode, stdout, stderr).

        If *mutating* is True and dry_run is active, the command is skipped
        and a simulated success is returned.  Read-only commands always execute.
        """
        self.logger.debug(f"CMD: {' '.join(cmd)}")
        if self.dry_run and mutating:
            self.logger.info(f"  [DRY-RUN] {' '.join(cmd)}")
            return (0, "", "")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode != 0 and check:
                self.logger.debug(f"STDERR: {proc.stderr.strip()}")
            return (proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            return (1, "", "timeout")
        except FileNotFoundError:
            self.logger.error(f"Command not found: {cmd[0]}")
            return (1, "", f"{cmd[0]} not found")

    # -----------------------------------------------------------------------
    # Phase 1: Pre-flight Checks
    # -----------------------------------------------------------------------
    def phase1_preflight_checks(self) -> bool:
        self.logger.header("Phase 1: Pre-flight Checks")
        ok = True

        # Kind cluster running?
        rc, out, _ = self.run_cmd(["kind", "get", "clusters"], check=False)
        if rc != 0 or self.cluster_name not in out.splitlines():
            self.logger.error(f"✗ Kind cluster '{self.cluster_name}' not found")
            return False
        self.logger.success(f"✓ Kind cluster '{self.cluster_name}' is running")

        # kubectl context
        rc, ctx, _ = self.run_cmd(
            ["kubectl", "config", "current-context"], check=False
        )
        expected_ctx = f"kind-{self.cluster_name}"
        if ctx.strip() != expected_ctx:
            self.logger.warning(
                f"⚠ kubectl context is '{ctx.strip()}', expected '{expected_ctx}'"
            )
            self.logger.info(f"  Switching context to {expected_ctx}")
            self.run_cmd(["kubectl", "config", "use-context", expected_ctx], check=False, mutating=True)
        else:
            self.logger.success(f"✓ kubectl context: {expected_ctx}")

        # Docker daemon
        rc, _, _ = self.run_cmd(["docker", "info"], check=False)
        if rc != 0:
            self.logger.error("✗ Docker daemon is not running")
            return False
        self.logger.success("✓ Docker daemon is running")

        # Namespace
        rc, _, _ = self.run_cmd(
            ["kubectl", "get", "namespace", self.namespace], check=False
        )
        if rc != 0:
            self.logger.error(f"✗ Namespace '{self.namespace}' does not exist")
            return False
        self.logger.success(f"✓ Namespace '{self.namespace}' exists")

        # PostgreSQL pod
        rc, out, _ = self.run_cmd(
            [
                "kubectl", "get", "pods", "-n", self.namespace,
                "-l", "app=postgresql", "-o",
                "jsonpath={.items[0].status.phase}",
            ],
            check=False,
        )
        if rc != 0 or out.strip() != "Running":
            self.logger.error("✗ PostgreSQL pod is not running")
            ok = False
        else:
            self.logger.success("✓ PostgreSQL pod is running")

        # Existing deployments
        rc, out, _ = self.run_cmd(
            ["kubectl", "get", "deployments", "-n", self.namespace, "-o", "name"],
            check=False,
        )
        if out.strip():
            deploys = [d.replace("deployment.apps/", "") for d in out.strip().splitlines()]
            svc_deploys = [d for d in deploys if d != "postgresql"]
            if svc_deploys:
                self.logger.warning(f"⚠ Existing deployments found: {', '.join(svc_deploys)}")

        return ok

    # -----------------------------------------------------------------------
    # Phase 2: Build Docker Images
    # -----------------------------------------------------------------------
    def phase2_build_images(self, services: List[str]) -> bool:
        self.logger.header("Phase 2: Building Docker Images")
        all_ok = True

        for svc in services:
            svc_dir = self.project_root / svc
            if not svc_dir.is_dir():
                self.logger.error(f"✗ Directory not found: {svc_dir}")
                self.results["images_failed"].append(svc)
                all_ok = False
                continue

            self.logger.info(f"Building {svc}...")
            rc, out, err = self.run_cmd(
                ["docker", "build", "-t", f"{svc}:latest", str(svc_dir)],
                check=False,
                timeout=600,
                mutating=True,
            )
            if rc != 0:
                self.logger.error(f"✗ Failed to build {svc}")
                self.logger.debug(err)
                self.results["images_failed"].append(svc)
                all_ok = False
                continue

            # Image size
            _, size_out, _ = self.run_cmd(
                ["docker", "images", svc, "--format", "{{.Size}}"], check=False
            )
            size = size_out.strip().splitlines()[0] if size_out.strip() else "unknown"
            self.logger.success(f"✓ {svc}:latest built (Size: {size})")
            self.results["images_built"].append(svc)

        return all_ok

    # -----------------------------------------------------------------------
    # Phase 3: Load Images into Kind
    # -----------------------------------------------------------------------
    def phase3_load_images(self, services: List[str]) -> bool:
        self.logger.header("Phase 3: Loading Images into Kind")
        all_ok = True

        for svc in services:
            if svc in self.results["images_failed"]:
                self.logger.warning(f"⚠ Skipping {svc} (build failed)")
                continue

            self.logger.info(f"Loading {svc}:latest into Kind cluster...")
            rc, out, err = self.run_cmd(
                ["kind", "load", "docker-image", f"{svc}:latest",
                 "--name", self.cluster_name],
                check=False,
                timeout=300,
                mutating=True,
            )
            if rc != 0:
                self.logger.error(f"✗ Failed to load {svc}")
                self.logger.debug(err)
                self.results["images_load_failed"].append(svc)
                all_ok = False
            else:
                self.logger.success(f"✓ {svc}:latest loaded into Kind")
                self.results["images_loaded"].append(svc)

        return all_ok

    # -----------------------------------------------------------------------
    # Phase 4: Secret Management
    # -----------------------------------------------------------------------
    def phase4_manage_secrets(self) -> bool:
        self.logger.header("Phase 4: Secret Management")

        secret_specs = {
            "db-credentials": {
                "type": "generic",
                "literals": {
                    "username": "uvote_admin",
                    "password": secrets.token_urlsafe(24),
                    "postgres-password": secrets.token_urlsafe(24),
                    "database": "evote",
                },
            },
            "jwt-secret": {
                "type": "generic",
                "literals": {
                    "secret": secrets.token_urlsafe(48),
                },
            },
            "flask-secret": {
                "type": "generic",
                "literals": {
                    "secret": secrets.token_urlsafe(48),
                },
            },
        }

        for name, spec in secret_specs.items():
            rc, _, _ = self.run_cmd(
                ["kubectl", "get", "secret", name, "-n", self.namespace],
                check=False,
            )
            if rc == 0:
                self.logger.success(f"✓ Secret '{name}' already exists (preserved)")
                continue

            # Build create command
            cmd = [
                "kubectl", "create", "secret", "generic", name,
                "-n", self.namespace,
            ]
            for k, v in spec["literals"].items():
                cmd.append(f"--from-literal={k}={v}")

            rc, _, err = self.run_cmd(cmd, check=False, mutating=True)
            if rc != 0:
                self.logger.error(f"✗ Failed to create secret '{name}': {err.strip()}")
                return False
            self.logger.success(f"✓ Secret '{name}' created")

        return True

    # -----------------------------------------------------------------------
    # Phase 5: Deploy Services
    # -----------------------------------------------------------------------
    def phase5_deploy_services(self, services: List[str]) -> bool:
        self.logger.header("Phase 5: Deploying Services")
        all_ok = True

        # Split into backend-first, frontend-last
        backends = [s for s in services if s != "frontend-service"]
        frontends = [s for s in services if s == "frontend-service"]

        for group_label, group in [("Backend", backends), ("Frontend", frontends)]:
            if not group:
                continue
            self.logger.info(f"Deploying {group_label} services...")

            for svc in group:
                info = SERVICE_REGISTRY[svc]
                # Skip if image build or load failed
                if svc in self.results["images_failed"] or svc in self.results["images_load_failed"]:
                    self.logger.warning(f"⚠ Skipping {info['deploy_name']} (image not available)")
                    self.results["services_failed"].append(info["deploy_name"])
                    all_ok = False
                    continue

                manifest = self.k8s_services_dir / info["manifest"]
                if not manifest.exists():
                    self.logger.error(f"✗ Manifest not found: {manifest}")
                    self.results["services_failed"].append(info["deploy_name"])
                    all_ok = False
                    continue

                self.logger.info(f"  Applying {info['manifest']}...")
                rc, out, err = self.run_cmd(
                    ["kubectl", "apply", "-f", str(manifest)], check=False, mutating=True
                )
                if rc != 0:
                    self.logger.error(f"✗ Failed to deploy {info['deploy_name']}: {err.strip()}")
                    self.results["services_failed"].append(info["deploy_name"])
                    all_ok = False
                else:
                    self.logger.success(f"✓ {info['deploy_name']} deployed")
                    self.results["services_deployed"].append(info["deploy_name"])

        return all_ok

    # -----------------------------------------------------------------------
    # Phase 6: Health Verification (wait for pods)
    # -----------------------------------------------------------------------
    def phase6_verify_health(self, timeout: int = 300) -> bool:
        self.logger.header("Phase 6: Health Verification")

        if not self.results["services_deployed"]:
            self.logger.warning("⚠ No services were deployed — skipping health verification")
            return True

        self.logger.info(f"Waiting for pods to be ready (timeout: {timeout}s)...")
        start = time.time()
        last_status_msg = ""

        while time.time() - start < timeout:
            rc, out, _ = self.run_cmd(
                ["kubectl", "get", "pods", "-n", self.namespace, "-o", "json"],
                check=False,
            )
            if rc != 0:
                time.sleep(5)
                continue

            pods = json.loads(out)
            app_pods = [
                p for p in pods.get("items", [])
                if p["metadata"].get("labels", {}).get("app") in self.results["services_deployed"]
            ]

            if not app_pods:
                time.sleep(5)
                continue

            all_ready = True
            status_parts = []
            crash_pods = []

            for pod in app_pods:
                name = pod["metadata"]["name"]
                phase = pod["status"].get("phase", "Unknown")
                containers = pod["status"].get("containerStatuses", [])

                # Detect crash states
                for cs in containers:
                    waiting = cs.get("state", {}).get("waiting", {})
                    reason = waiting.get("reason", "")
                    if reason in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImageNeverPull"):
                        crash_pods.append((name, reason))

                if phase != "Running" or not all(
                    cs.get("ready", False) for cs in containers
                ):
                    all_ready = False
                    status_parts.append(f"{name}={phase}")

            if crash_pods:
                for pname, reason in crash_pods:
                    self.logger.error(f"✗ Pod {pname}: {reason}")
                # Don't immediately fail — some pods may recover
                # but report errors

            if all_ready and len(app_pods) > 0:
                self.logger.success(
                    f"✓ All {len(app_pods)} pods are running and ready"
                )
                # Record running pods
                for pod in app_pods:
                    self.results["pods_running"].append(pod["metadata"]["name"])
                return True

            elapsed = int(time.time() - start)
            msg = f"Waiting for pods... ({elapsed}s) — {len(app_pods) - len(status_parts)}/{len(app_pods)} ready"
            if msg != last_status_msg:
                self.logger.info(msg)
                last_status_msg = msg

            time.sleep(5)

        # Timeout — record failures
        self.logger.error(f"✗ Timed out after {timeout}s waiting for pods")
        rc, out, _ = self.run_cmd(
            ["kubectl", "get", "pods", "-n", self.namespace,
             "-o", "wide", "--show-labels"],
            check=False,
        )
        self.logger.info("Current pod status:")
        for line in out.strip().splitlines():
            self.logger.info(f"  {line}")

        # Capture logs for failing pods
        rc, out, _ = self.run_cmd(
            ["kubectl", "get", "pods", "-n", self.namespace, "-o", "json"],
            check=False,
        )
        if rc == 0:
            pods = json.loads(out)
            for pod in pods.get("items", []):
                containers = pod["status"].get("containerStatuses", [])
                for cs in containers:
                    if not cs.get("ready", False):
                        pname = pod["metadata"]["name"]
                        self.results["pods_failed"].append(pname)
                        self.logger.info(f"Fetching logs for {pname}...")
                        _, logs, _ = self.run_cmd(
                            ["kubectl", "logs", "-n", self.namespace, pname,
                             "--tail=30"],
                            check=False,
                        )
                        if logs.strip():
                            for line in logs.strip().splitlines()[-10:]:
                                self.logger.debug(f"  {pname}: {line}")

        return False

    # -----------------------------------------------------------------------
    # Phase 7: Network Policy Testing
    # -----------------------------------------------------------------------
    def phase7_test_network_policies(self) -> bool:
        self.logger.header("Phase 7: Network Policy Testing")
        all_ok = True

        if self.dry_run:
            self.logger.info("[DRY-RUN] Would test network policies")
            return True

        # Test DB access from backend services (should succeed)
        for svc in ALL_SERVICES:
            info = SERVICE_REGISTRY[svc]
            deploy_name = info["deploy_name"]
            should_succeed = info["db_access"]

            if deploy_name not in self.results["services_deployed"]:
                continue

            # Use a timeout on the nc command so we don't wait forever
            rc, out, err = self.run_cmd(
                [
                    "kubectl", "exec", "-n", self.namespace,
                    f"deployment/{deploy_name}", "--",
                    "python3", "-c",
                    "import socket; s=socket.socket(); s.settimeout(5); s.connect(('postgresql',5432)); s.close(); print('ok')",
                ],
                check=False,
                timeout=15,
            )
            connected = rc == 0

            if should_succeed:
                if connected:
                    self.logger.success(f"✓ {deploy_name} → PostgreSQL: Connected (expected)")
                    self.results["net_passed"].append(f"{deploy_name}→db")
                else:
                    self.logger.error(f"✗ {deploy_name} → PostgreSQL: Blocked (expected connection)")
                    self.results["net_failed"].append(f"{deploy_name}→db")
                    all_ok = False
            else:
                if not connected:
                    self.logger.success(f"✓ {deploy_name} → PostgreSQL: Blocked (expected)")
                    self.results["net_passed"].append(f"{deploy_name}→db:blocked")
                else:
                    self.logger.warning(f"⚠ {deploy_name} → PostgreSQL: Connected (expected block)")
                    self.results["net_failed"].append(f"{deploy_name}→db:unexpected")
                    all_ok = False

        # DNS resolution test
        test_deploy = None
        for svc in ALL_SERVICES:
            info = SERVICE_REGISTRY[svc]
            if info["deploy_name"] in self.results["services_deployed"]:
                test_deploy = info["deploy_name"]
                break

        if test_deploy:
            self.logger.info("Testing DNS resolution...")
            rc, out, _ = self.run_cmd(
                [
                    "kubectl", "exec", "-n", self.namespace,
                    f"deployment/{test_deploy}", "--",
                    "python3", "-c",
                    "import socket; print(socket.getaddrinfo('postgresql',5432)[0][4][0])",
                ],
                check=False,
                timeout=15,
            )
            if rc == 0 and out.strip():
                self.logger.success(f"✓ DNS resolution working (postgresql → {out.strip()})")
                self.results["net_passed"].append("dns")
            else:
                self.logger.error("✗ DNS resolution failed")
                self.results["net_failed"].append("dns")
                all_ok = False

        return all_ok

    # -----------------------------------------------------------------------
    # Phase 8: Health Endpoint Testing
    # -----------------------------------------------------------------------
    def phase8_test_health_endpoints(self) -> bool:
        self.logger.header("Phase 8: Health Endpoint Testing")

        if self.dry_run:
            self.logger.info("[DRY-RUN] Would test health endpoints")
            return True

        all_ok = True

        for svc in ALL_SERVICES:
            info = SERVICE_REGISTRY[svc]
            deploy_name = info["deploy_name"]

            if deploy_name not in self.results["services_deployed"]:
                continue

            port = info["port"]
            path = info["health_path"]

            # Use kubectl exec to curl from inside the pod
            rc, out, err = self.run_cmd(
                [
                    "kubectl", "exec", "-n", self.namespace,
                    f"deployment/{deploy_name}", "--",
                    "python3", "-c",
                    f"import urllib.request; r=urllib.request.urlopen('http://localhost:{port}{path}', timeout=10); print(r.status, r.read().decode()[:200])",
                ],
                check=False,
                timeout=20,
            )

            if rc == 0 and out.strip().startswith("200"):
                response_body = out.strip()[4:]  # strip "200 "
                self.logger.success(f"✓ {deploy_name} {path} → 200 OK")
                self.logger.debug(f"  Response: {response_body[:100]}")
                self.results["health_passed"].append(deploy_name)
            else:
                self.logger.error(f"✗ {deploy_name} {path} → Failed")
                self.logger.debug(f"  stdout: {out.strip()}")
                self.logger.debug(f"  stderr: {err.strip()}")
                self.results["health_failed"].append(deploy_name)
                all_ok = False

        return all_ok

    # -----------------------------------------------------------------------
    # Phase 9: Summary
    # -----------------------------------------------------------------------
    def phase9_generate_summary(self) -> None:
        r = self.results
        sep = "=" * 56

        self.logger.info(sep)

        total_svc = len(r["services_deployed"]) + len(r["services_failed"])
        total_pods = len(r["pods_running"]) + len(r["pods_failed"])
        total_health = len(r["health_passed"]) + len(r["health_failed"])
        total_net = len(r["net_passed"]) + len(r["net_failed"])

        has_failures = (
            r["images_failed"]
            or r["services_failed"]
            or r["pods_failed"]
            or r["health_failed"]
        )

        if not has_failures and r["services_deployed"]:
            self.logger.success("Deployment Complete!")
        elif r["services_deployed"]:
            self.logger.warning("Deployment Completed with Warnings")
        else:
            self.logger.error("Deployment Failed")

        self.logger.info(f"Total Time: {self.logger.elapsed()}")
        self.logger.info(
            f"Images Built:       {len(r['images_built'])}/{len(r['images_built']) + len(r['images_failed'])}"
        )
        self.logger.info(
            f"Images Loaded:      {len(r['images_loaded'])}/{len(r['images_loaded']) + len(r['images_load_failed'])}"
        )
        self.logger.info(
            f"Services Deployed:  {len(r['services_deployed'])}/{total_svc}"
        )
        if total_pods:
            self.logger.info(
                f"Pods Running:       {len(r['pods_running'])}/{total_pods}"
            )
        if total_health:
            self.logger.info(
                f"Health Checks:      {len(r['health_passed'])}/{total_health}"
            )
        if total_net:
            self.logger.info(
                f"Network Tests:      {len(r['net_passed'])}/{total_net}"
            )

        if r["images_failed"]:
            self.logger.error(f"Failed images: {', '.join(r['images_failed'])}")
        if r["services_failed"]:
            self.logger.error(f"Failed services: {', '.join(r['services_failed'])}")
        if r["pods_failed"]:
            self.logger.error(f"Failed pods: {', '.join(r['pods_failed'])}")
        if r["health_failed"]:
            self.logger.error(f"Failed health checks: {', '.join(r['health_failed'])}")
        if r["net_failed"]:
            self.logger.error(f"Failed network tests: {', '.join(r['net_failed'])}")

        self.logger.info(sep)

        if r["services_deployed"]:
            self.logger.info("Next steps:")
            self.logger.info("  1. Configure ingress for external access")
            self.logger.info("  2. Set up TLS certificates")
            self.logger.info("  3. Run integration tests")
            self.logger.info(f"  4. Monitor: kubectl get pods -n {self.namespace} -w")

        self.logger.info(f"Log file: {self.logger.log_file}")

    # -----------------------------------------------------------------------
    # Rollback
    # -----------------------------------------------------------------------
    def rollback(self) -> bool:
        self.logger.header("Rolling Back Deployment")

        all_ok = True
        for svc in ALL_SERVICES:
            info = SERVICE_REGISTRY[svc]
            manifest = self.k8s_services_dir / info["manifest"]
            if not manifest.exists():
                continue

            self.logger.info(f"Deleting {info['deploy_name']}...")
            rc, _, err = self.run_cmd(
                ["kubectl", "delete", "-f", str(manifest), "--ignore-not-found"],
                check=False, mutating=True,
            )
            if rc != 0:
                self.logger.error(f"✗ Failed to delete {info['deploy_name']}: {err.strip()}")
                all_ok = False
            else:
                self.logger.success(f"✓ {info['deploy_name']} deleted")

        # Delete secrets (but preserve db-credentials since DB is still running)
        for secret_name in ["jwt-secret", "flask-secret"]:
            self.logger.info(f"Deleting secret '{secret_name}'...")
            self.run_cmd(
                ["kubectl", "delete", "secret", secret_name,
                 "-n", self.namespace, "--ignore-not-found"],
                check=False, mutating=True,
            )
            self.logger.success(f"✓ Secret '{secret_name}' deleted")

        self.logger.info("Rollback complete. Database and db-credentials preserved.")
        return all_ok

    # -----------------------------------------------------------------------
    # Main deploy orchestration
    # -----------------------------------------------------------------------
    def deploy(
        self,
        skip_build: bool,
        skip_tests: bool,
        services: Optional[List[str]],
        timeout: int,
    ) -> bool:
        target_services = services if services else ALL_SERVICES

        # Validate service names
        for svc in target_services:
            if svc not in SERVICE_REGISTRY:
                self.logger.error(f"Unknown service: {svc}")
                self.logger.info(f"Available services: {', '.join(ALL_SERVICES)}")
                return False

        self.logger.info(f"Starting U-Vote platform deployment")
        self.logger.info(f"Cluster: {self.cluster_name}  Namespace: {self.namespace}")
        self.logger.info(f"Services: {', '.join(target_services)}")
        if self.dry_run:
            self.logger.warning("DRY-RUN MODE — no changes will be made")

        # Phase 1: Pre-flight
        if not self.phase1_preflight_checks():
            self.logger.error("Pre-flight checks failed. Aborting.")
            return False

        # Phase 2: Build
        if not skip_build:
            self.phase2_build_images(target_services)
        else:
            self.logger.info("Skipping image build (--skip-build)")
            # Verify images exist locally
            for svc in target_services:
                rc, _, _ = self.run_cmd(
                    ["docker", "image", "inspect", f"{svc}:latest"], check=False
                )
                if rc == 0:
                    self.results["images_built"].append(svc)
                else:
                    self.logger.warning(f"⚠ Image {svc}:latest not found locally")
                    self.results["images_failed"].append(svc)

        # Phase 3: Load into Kind
        self.phase3_load_images(target_services)

        # Phase 4: Secrets
        if not self.phase4_manage_secrets():
            self.logger.error("Secret management failed. Aborting.")
            return False

        # Phase 5: Deploy
        self.phase5_deploy_services(target_services)

        # Phase 6: Wait for healthy pods
        if not self.dry_run:
            self.phase6_verify_health(timeout=timeout)
        else:
            self.logger.info("[DRY-RUN] Would wait for pods to be ready")

        # Phase 7 & 8: Tests
        if not skip_tests and not self.dry_run:
            self.phase7_test_network_policies()
            self.phase8_test_health_endpoints()
        elif skip_tests:
            self.logger.info("Skipping tests (--skip-tests)")
        else:
            self.logger.info("[DRY-RUN] Would run network and health tests")

        # Phase 9: Summary
        self.phase9_generate_summary()

        return len(self.results["services_failed"]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
@click.command()
@click.option("--cluster-name", default="uvote", help="Kind cluster name")
@click.option("--namespace", default="uvote-dev", help="Kubernetes namespace")
@click.option("--skip-build", is_flag=True, help="Skip Docker image building")
@click.option("--skip-tests", is_flag=True, help="Skip network and health tests")
@click.option("--services", default=None, help="Deploy specific services (comma-separated)")
@click.option("--timeout", default=300, help="Pod ready timeout in seconds")
@click.option("--verbose", is_flag=True, help="Enable debug logging")
@click.option("--rollback", "do_rollback", is_flag=True, help="Rollback deployment")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
def main(cluster_name, namespace, skip_build, skip_tests, services, timeout, verbose, do_rollback, dry_run):
    """U-Vote Platform Deployment Script

    Automates building, deploying, and testing the U-Vote secure online
    voting platform on a Kind Kubernetes cluster.

    \b
    Examples:
      # Full deployment
      python plat_scripts/deploy_platform.py

      # Deploy only auth and voting services
      python plat_scripts/deploy_platform.py --services auth-service,voting-service

      # Skip tests for faster deployment
      python plat_scripts/deploy_platform.py --skip-tests

      # Dry run
      python plat_scripts/deploy_platform.py --dry-run

      # Rollback
      python plat_scripts/deploy_platform.py --rollback
    """
    # Set up log file in project root
    project_root = Path(__file__).resolve().parent.parent
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = project_root / f"deploy-{timestamp}.log"
    logger = DeploymentLogger(log_file, verbose=verbose)

    logger.info(f"U-Vote Platform Deployer v1.0")
    logger.info(f"Log file: {log_file}")

    deployer = PlatformDeployer(cluster_name, namespace, logger, dry_run=dry_run)

    # Parse service list
    svc_list = None
    if services:
        svc_list = [s.strip() for s in services.split(",")]

    try:
        if do_rollback:
            ok = deployer.rollback()
        else:
            ok = deployer.deploy(
                skip_build=skip_build,
                skip_tests=skip_tests,
                services=svc_list,
                timeout=timeout,
            )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        ok = False
    finally:
        logger.close()

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════════
# TESTING THIS SCRIPT:
#
# 1. Install dependencies:
#    pip install click colorama
#
# 2. Dry run to verify logic:
#    python plat_scripts/deploy_platform.py --dry-run
#
# 3. Deploy with verbose logging:
#    python plat_scripts/deploy_platform.py --verbose
#
# 4. Deploy specific services only:
#    python plat_scripts/deploy_platform.py --services auth-service,voting-service
#
# 5. Skip tests for faster deployment:
#    python plat_scripts/deploy_platform.py --skip-tests
#
# 6. Rollback everything:
#    python plat_scripts/deploy_platform.py --rollback
#
# 7. Check the log file:
#    cat deploy-*.log
#
# EXPECTED OUTCOMES:
#
# ✅ SUCCESS:
#    - All images built (6/6)
#    - All images loaded into Kind
#    - All pods running (12/12 — 2 replicas each)
#    - Database connectivity tests pass for backend services
#    - Frontend blocked from database (expected)
#    - Health checks pass (6/6)
#
# ⚠️  COMMON ISSUES:
#    - Image build fails: Check Dockerfile, missing dependencies
#    - Pod CrashLoopBackOff: Check logs with kubectl logs -n uvote-dev <pod>
#    - Health check timeout: Increase --timeout value
#    - Network test fails: Verify network policies applied
#    - ErrImageNeverPull: Image not loaded into Kind — check phase 3
#
# 📋 LOG FILE:
#    - deploy-{timestamp}.log in project root
#    - Contains complete execution trace
#    - Include in project documentation
# ═══════════════════════════════════════════════════════════════════════════
