#!/usr/bin/env python3
"""
U-Vote Test Platform Deployment Script — MailHog

Deploys MailHog (in-cluster fake SMTP server) to uvote-dev and uvote-test
namespaces for local development and testing. Intentionally separate from
deploy_platform.py — MailHog is a test-only tool and must NEVER reach
uvote-prod.

Run AFTER setup_k8s_platform.py and deploy_platform.py. Assumes the Kind
cluster is already running and both target namespaces exist.

Usage:
    python plat_scripts/deploy_test_platform.py [OPTIONS]

Requirements:
    - kubectl on PATH
    - Kind cluster 'evote' running
    - uvote-dev and uvote-test namespaces exist (created by setup_k8s_platform.py)
    - Python 3.8+
    - No external dependencies beyond the standard library
"""

import argparse
import base64
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLUSTER_NAME = "uvote"
ALLOWED_NAMESPACES = ["uvote-dev", "uvote-test"]
FORBIDDEN_NAMESPACE = "uvote-prod"

# MailHog SMTP secret literals — dev/test only.
# These values configure admin-service to send email to the in-cluster
# MailHog pod instead of a real SMTP provider.
SMTP_SECRET_LITERALS: Dict[str, str] = {
    "SMTP_HOST":    "mailhog",
    "SMTP_PORT":    "1025",
    "SMTP_USE_TLS": "false",
    "SMTP_FROM":    "uvote@test.local",
    "SMTP_USER":    "",   # MailHog requires no authentication
    "SMTP_PASS":    "",   # MailHog requires no authentication
    "FRONTEND_URL": "http://frontend-service:5000",
}

# Keys included in the audit log — SMTP_USER and SMTP_PASS excluded even
# though they are empty strings (consistent policy: never log credential keys)
SMTP_AUDIT_KEYS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USE_TLS", "SMTP_FROM", "FRONTEND_URL"]

# Keys asserted by Phase 6 (values we can safely log in verification output)
SMTP_ASSERT: Dict[str, str] = {
    "SMTP_HOST":    "mailhog",
    "SMTP_PORT":    "1025",
    "SMTP_USE_TLS": "false",
}


# ═══════════════════════════════════════════════════════════════════════════
# Logger — matches DeploymentLogger in deploy_platform.py.
# Uses ANSI escape codes directly (no colorama dependency).
# ═══════════════════════════════════════════════════════════════════════════
class DeploymentLogger:
    """Dual logger: ANSI-coloured console + plain-text log file."""

    LEVEL_COLORS: Dict[str, str] = {
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

    # -- core -----------------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain = f"[{ts}] [{level}] {message}"
        color = self.LEVEL_COLORS.get(level, "")
        coloured = f"{color}[{ts}] [{level}]{self.RESET} {message}"

        if level == "DEBUG" and not self.verbose:
            # Write to file only; do not clutter console
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
# Production namespace guard
# ═══════════════════════════════════════════════════════════════════════════
def guard_against_prod(namespace: str) -> None:
    """Hard stop — this script must NEVER run against uvote-prod.

    MailHog is a local development and testing tool. It has no authentication,
    stores messages in memory only, and must not exist in production namespaces.

    This guard runs before any kubectl commands are issued. argparse's
    choices= parameter already excludes uvote-prod, but this explicit check
    provides a second line of defence against any future code path that might
    call deploy() directly.
    """
    if namespace == FORBIDDEN_NAMESPACE:
        print(
            f"\nERROR: Refusing to deploy MailHog to '{FORBIDDEN_NAMESPACE}'.\n"
            "\n"
            "MailHog is a LOCAL DEVELOPMENT AND TESTING TOOL ONLY.\n"
            "It must never be deployed to production namespaces.\n"
            "\n"
            f"Allowed namespaces: {', '.join(ALLOWED_NAMESPACES)}\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# MailHog Deployer — one instance per target namespace
# ═══════════════════════════════════════════════════════════════════════════
class MailHogDeployer:
    """Deploys MailHog and its supporting resources to a single namespace."""

    def __init__(
        self,
        namespace: str,
        logger: DeploymentLogger,
        timeout: int = 60,
    ):
        self.namespace = namespace
        self.logger = logger
        self.timeout = timeout
        self.project_root = Path(__file__).resolve().parent.parent
        self.k8s_dir = self.project_root / "uvote-platform" / "k8s"
        # Keyed by phase label — populated as phases run, used by summary table
        self.phase_results: Dict[str, Optional[bool]] = {}

    # -- helpers --------------------------------------------------------------

    def run_cmd(
        self,
        cmd: List[str],
        check: bool = True,
        timeout: int = 120,
        stdin_data: Optional[bytes] = None,
    ) -> Tuple[int, str, str]:
        """Run a subprocess command; return (returncode, stdout, stderr).

        *stdin_data* — if provided, written to the process stdin (used for
        piped apply commands).  When None, stdin is set to DEVNULL to prevent
        interactive kubectl commands from blocking on input.
        """
        self.logger.debug(f"CMD: {' '.join(cmd)}")
        try:
            run_kwargs: dict = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "timeout": timeout,
            }
            if stdin_data is not None:
                # subprocess.run automatically opens a PIPE when input= is set
                run_kwargs["input"] = stdin_data
            else:
                run_kwargs["stdin"] = subprocess.DEVNULL

            proc = subprocess.run(cmd, **run_kwargs)
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0 and check:
                self.logger.debug(f"STDERR: {stderr.strip()}")
            return (proc.returncode, stdout, stderr)

        except subprocess.TimeoutExpired:
            self.logger.error(
                f"Command timed out after {timeout}s: {' '.join(cmd)}"
            )
            return (1, "", "timeout")
        except FileNotFoundError:
            self.logger.error(f"Command not found: {cmd[0]}")
            return (1, "", f"{cmd[0]} not found")

    def _record(self, phase_label: str, ok: bool) -> bool:
        """Record a phase result and return it (for use in return statements)."""
        self.phase_results[phase_label] = ok
        return ok

    # -----------------------------------------------------------------------
    # Phase 1 — Preflight checks
    # -----------------------------------------------------------------------
    def phase1_preflight(self) -> bool:
        self.logger.header(f"[{self.namespace}] Phase 1: Pre-flight Checks")

        # kubectl on PATH
        rc, _, _ = self.run_cmd(["kubectl", "version", "--client"], check=False)
        if rc != 0:
            self.logger.error("✗ kubectl not found on PATH")
            return self._record("Phase 1: Preflight", False)
        self.logger.success("✓ kubectl is available")

        # Kind cluster accessible
        rc, _, err = self.run_cmd(
            ["kubectl", "cluster-info", "--context", f"kind-{CLUSTER_NAME}"],
            check=False,
        )
        if rc != 0:
            self.logger.error(
                f"✗ Cluster 'kind-{CLUSTER_NAME}' not accessible: {err.strip()}"
            )
            return self._record("Phase 1: Preflight", False)
        self.logger.success(f"✓ Kind cluster 'kind-{CLUSTER_NAME}' is accessible")

        # Target namespace exists
        rc, _, err = self.run_cmd(
            ["kubectl", "get", "namespace", self.namespace], check=False
        )
        if rc != 0:
            self.logger.error(
                f"✗ Namespace '{self.namespace}' does not exist: {err.strip()}"
            )
            return self._record("Phase 1: Preflight", False)
        self.logger.success(f"✓ Namespace '{self.namespace}' exists")

        # PostgreSQL pod running — cluster health signal (matches deploy_platform.py)
        rc, out, _ = self.run_cmd(
            [
                "kubectl", "get", "pods",
                "-n", self.namespace,
                "-l", "app=postgresql",
                "-o", "jsonpath={.items[0].status.phase}",
            ],
            check=False,
        )
        if rc != 0 or out.strip() != "Running":
            self.logger.error(
                f"✗ PostgreSQL pod is not Running in '{self.namespace}' "
                f"(got: '{out.strip() or 'no output'}')"
            )
            return self._record("Phase 1: Preflight", False)
        self.logger.success(f"✓ PostgreSQL pod is Running in '{self.namespace}'")

        return self._record("Phase 1: Preflight", True)

    # -----------------------------------------------------------------------
    # Phase 2 — Create smtp-credentials Secret (idempotent)
    # -----------------------------------------------------------------------
    def phase2_create_smtp_secret(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 2: Create smtp-credentials Secret"
        )

        # Build the kubectl create secret command with all MailHog literals
        create_cmd = [
            "kubectl", "create", "secret", "generic", "smtp-credentials",
            f"--namespace={self.namespace}",
            "--dry-run=client",
            "-o", "yaml",
        ]
        for key, value in SMTP_SECRET_LITERALS.items():
            create_cmd.append(f"--from-literal={key}={value}")

        self.logger.debug(
            "Generating smtp-credentials yaml via --dry-run=client..."
        )
        rc, yaml_out, err = self.run_cmd(create_cmd, check=False)
        if rc != 0:
            self.logger.error(
                f"✗ Failed to generate smtp-credentials yaml: {err.strip()}"
            )
            return self._record("Phase 2: SMTP Secret", False)

        # Pipe the generated yaml into kubectl apply -f - (idempotent: creates
        # or updates the secret without failing if it already exists)
        rc, out, err = self.run_cmd(
            ["kubectl", "apply", "-f", "-"],
            check=False,
            stdin_data=yaml_out.encode("utf-8"),
        )
        if rc != 0:
            self.logger.error(
                f"✗ Failed to apply smtp-credentials: {err.strip()}"
            )
            return self._record("Phase 2: SMTP Secret", False)

        action = out.strip()   # e.g. "secret/smtp-credentials created"
        self.logger.success(f"✓ smtp-credentials: {action}")
        self.logger.info(
            "  Keys configured (values not logged): "
            + ", ".join(SMTP_AUDIT_KEYS)
        )

        return self._record("Phase 2: SMTP Secret", True)

    # -----------------------------------------------------------------------
    # Phase 3 — Apply MailHog manifest
    # -----------------------------------------------------------------------
    def phase3_apply_manifest(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 3: Apply MailHog Manifest"
        )

        manifest = self.k8s_dir / "mailhog" / "mailhog-deployment.yaml"
        if not manifest.exists():
            self.logger.error(f"✗ Manifest not found: {manifest}")
            return self._record("Phase 3: Apply Manifest", False)

        # The -n flag overrides the namespace in the manifest metadata,
        # allowing the same manifest to serve both uvote-dev and uvote-test.
        rc, out, err = self.run_cmd(
            ["kubectl", "apply", "-f", str(manifest), "-n", self.namespace],
            check=False,
        )
        if rc != 0:
            self.logger.error(
                f"✗ Failed to apply MailHog manifest: {err.strip()}"
            )
            return self._record("Phase 3: Apply Manifest", False)

        for line in out.strip().splitlines():
            self.logger.info(f"  {line}")
        self.logger.success("✓ MailHog Deployment and Service applied")

        return self._record("Phase 3: Apply Manifest", True)

    # -----------------------------------------------------------------------
    # Phase 4 — Apply MailHog network policy
    # -----------------------------------------------------------------------
    def phase4_apply_network_policy(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 4: Apply MailHog Network Policy"
        )

        policy = self.k8s_dir / "network-policies" / "05-allow-mailhog.yaml"
        if not policy.exists():
            self.logger.error(f"✗ Network policy not found: {policy}")
            return self._record("Phase 4: Network Policy", False)

        # Same namespace-override approach as Phase 3
        rc, out, err = self.run_cmd(
            ["kubectl", "apply", "-f", str(policy), "-n", self.namespace],
            check=False,
        )
        if rc != 0:
            self.logger.error(
                f"✗ Failed to apply network policy: {err.strip()}"
            )
            return self._record("Phase 4: Network Policy", False)

        for line in out.strip().splitlines():
            self.logger.info(f"  {line}")
        self.logger.success("✓ MailHog network policy applied")

        return self._record("Phase 4: Network Policy", True)

    # -----------------------------------------------------------------------
    # Phase 5 — Wait for MailHog pod readiness
    # -----------------------------------------------------------------------
    def phase5_wait_for_pod(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 5: Wait for MailHog Pod Readiness"
        )

        self.logger.info(
            f"  Polling deployment/mailhog (timeout: {self.timeout}s)..."
        )

        rc, out, err = self.run_cmd(
            [
                "kubectl", "wait", "deployment/mailhog",
                "--for=condition=Available",
                f"--timeout={self.timeout}s",
                "-n", self.namespace,
            ],
            check=False,
            timeout=self.timeout + 10,  # outer Python timeout > kubectl timeout
        )
        if rc == 0:
            self.logger.success("✓ MailHog deployment is Available")
            return self._record("Phase 5: Pod Readiness", True)

        self.logger.error(
            f"✗ MailHog pod did not become ready within {self.timeout}s"
        )

        # Capture pod logs to aid debugging
        self.logger.info("  Fetching pod logs (last 20 lines)...")
        _, log_out, log_err = self.run_cmd(
            [
                "kubectl", "logs",
                "-l", "app=mailhog",
                "-n", self.namespace,
                "--tail=20",
            ],
            check=False,
        )
        log_text = (log_out or log_err or "(no logs available)").strip()
        for line in log_text.splitlines():
            self.logger.info(f"    {line}")

        return self._record("Phase 5: Pod Readiness", False)

    # -----------------------------------------------------------------------
    # Phase 6 — Verify smtp-credentials secret values
    # -----------------------------------------------------------------------
    def phase6_verify_secret(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 6: Verify smtp-credentials Values"
        )

        rc, out, err = self.run_cmd(
            [
                "kubectl", "get", "secret", "smtp-credentials",
                "-n", self.namespace,
                "-o", "jsonpath={.data}",
            ],
            check=False,
        )
        if rc != 0:
            self.logger.error(
                f"✗ Could not read smtp-credentials: {err.strip()}"
            )
            return self._record("Phase 6: Secret Verification", False)

        try:
            data: Dict[str, str] = json.loads(out)
        except ValueError as exc:
            self.logger.error(
                f"✗ Failed to parse secret JSON: {exc} — raw: {out[:200]}"
            )
            return self._record("Phase 6: Secret Verification", False)

        all_ok = True
        for key, expected in SMTP_ASSERT.items():
            b64_val = data.get(key, "")
            if not b64_val:
                self.logger.error(f"✗ Key '{key}' missing from secret")
                all_ok = False
                continue
            actual = base64.b64decode(b64_val).decode("utf-8")
            if actual != expected:
                self.logger.error(
                    f"✗ {key}: expected '{expected}', got '{actual}'"
                )
                all_ok = False
            else:
                self.logger.success(f"✓ {key} == '{expected}'")

        if all_ok:
            self.logger.info(
                "  Note: SMTP_USER and SMTP_PASS not printed "
                "(credential key policy)"
            )

        return self._record("Phase 6: Secret Verification", all_ok)

    # -----------------------------------------------------------------------
    # Phase 7 — Verify MailHog HTTP API is reachable from within the cluster
    # -----------------------------------------------------------------------
    def phase7_verify_connectivity(self) -> bool:
        self.logger.header(
            f"[{self.namespace}] Phase 7: Verify MailHog HTTP API Connectivity"
        )

        # Pod name must be unique across namespaces (K8s name limit: 253 chars)
        ns_short = self.namespace.replace("uvote-", "")   # "dev" or "test"
        pod_name = f"mailhog-test-{ns_short}"

        self.logger.info(f"  Launching temporary curl pod '{pod_name}'...")
        self.logger.info(
            "  Testing: http://mailhog:8025/api/v2/messages (ClusterIP)"
        )

        # --rm cleans up the pod automatically after it exits.
        # -i keeps stdin open; we pass empty bytes to prevent blocking.
        rc, out, err = self.run_cmd(
            [
                "kubectl", "run", pod_name,
                "--image=curlimages/curl:latest",
                "--restart=Never",
                "--rm",
                "-i",
                "-n", self.namespace,
                "--",
                "curl", "-s", "--max-time", "5",
                "http://mailhog:8025/api/v2/messages",
            ],
            check=False,
            timeout=60,
            stdin_data=b"",   # empty stdin — prevents -i from blocking
        )

        if rc != 0:
            self.logger.error(
                f"✗ Connectivity test failed (rc={rc}): "
                f"{(err or out).strip()[:300]}"
            )
            return self._record("Phase 7: HTTP API Connectivity", False)

        response = out.strip()
        self.logger.debug(f"Response: {response[:300]}")

        # MailHog API v2 always returns {"total": <n>, ...} even with 0 messages
        if '"total"' not in response:
            self.logger.error(
                f"✗ Unexpected API response — 'total' key not found. "
                f"Got: {response[:200]}"
            )
            return self._record("Phase 7: HTTP API Connectivity", False)

        self.logger.success(
            "✓ MailHog HTTP API reachable in-cluster "
            "(response contains 'total' — messages API OK)"
        )
        return self._record("Phase 7: HTTP API Connectivity", True)

    # -----------------------------------------------------------------------
    # Orchestration
    # -----------------------------------------------------------------------
    def deploy(self) -> bool:
        """Run all 7 phases in sequence. Abort on first failure."""
        phases = [
            self.phase1_preflight,
            self.phase2_create_smtp_secret,
            self.phase3_apply_manifest,
            self.phase4_apply_network_policy,
            self.phase5_wait_for_pod,
            self.phase6_verify_secret,
            self.phase7_verify_connectivity,
        ]

        for phase_fn in phases:
            ok = phase_fn()
            if not ok:
                self.logger.error(
                    f"Phase failed — aborting deployment for '{self.namespace}'."
                )
                return False

        return True


# ═══════════════════════════════════════════════════════════════════════════
# Banner and summary
# ═══════════════════════════════════════════════════════════════════════════
def print_banner(namespaces: List[str]) -> None:
    print("================================================")
    print("UVote Test Platform Deployment — MailHog")
    print(f"Target namespaces: {', '.join(namespaces)}")
    print("NOTE: MailHog is a test tool — NOT for uvote-prod")
    print("================================================")
    print()


def print_summary(
    all_results: Dict[str, Dict[str, Optional[bool]]],
    elapsed: str,
) -> None:
    """Print a phase-by-phase summary table for every namespace."""
    sep = "=" * 56
    print()
    print(sep)
    print("DEPLOYMENT SUMMARY")
    print(sep)

    total_pass = 0
    total_fail = 0
    total_skip = 0

    for ns, phase_results in all_results.items():
        print(f"\nNamespace: {ns}")
        for phase_label, ok in phase_results.items():
            if ok is True:
                marker = "PASS"
                total_pass += 1
            elif ok is False:
                marker = "FAIL"
                total_fail += 1
            else:
                marker = "SKIP"
                total_skip += 1
            print(f"  {phase_label:<38} {marker}")

    print()
    print(f"  Total PASS: {total_pass}   Total FAIL: {total_fail}"
          + (f"   Total SKIP: {total_skip}" if total_skip else ""))
    print(f"  Elapsed:    {elapsed}")
    print(sep)
    if total_fail == 0:
        print("  Result: SUCCESS")
    else:
        print("  Result: FAILED")
    print(sep)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deploy_test_platform.py",
        description=(
            "Deploy MailHog (fake SMTP server) to uvote-dev and uvote-test.\n"
            "\n"
            "MailHog is a LOCAL DEVELOPMENT AND TESTING TOOL ONLY.\n"
            "It is intentionally separate from deploy_platform.py and must\n"
            "NEVER be deployed to uvote-prod.\n"
            "\n"
            "Run AFTER setup_k8s_platform.py and deploy_platform.py."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # Deploy to both namespaces (default)\n"
            "  python plat_scripts/deploy_test_platform.py\n"
            "\n"
            "  # Deploy to uvote-test only\n"
            "  python plat_scripts/deploy_test_platform.py --namespace uvote-test\n"
            "\n"
            "  # Verbose output with extended readiness timeout\n"
            "  python plat_scripts/deploy_test_platform.py --verbose --timeout 120\n"
            "\n"
            "  # Deploy to uvote-dev only with verbose logging\n"
            "  python plat_scripts/deploy_test_platform.py --namespace uvote-dev --verbose\n"
        ),
    )
    parser.add_argument(
        "--namespace",
        choices=ALLOWED_NAMESPACES,
        default=None,
        metavar="{uvote-dev,uvote-test}",
        help=(
            "Target a single namespace instead of both. "
            f"Choices: {', '.join(ALLOWED_NAMESPACES)}. "
            "Defaults to both. uvote-prod is NEVER allowed."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full kubectl output for every command",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Pod readiness timeout in seconds for Phase 5 (default: 60)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Hard production guard — runs before ANY other logic.
    #
    # argparse's choices= already excludes 'uvote-prod', but this explicit
    # check provides a second line of defence: if this function were ever
    # called programmatically (e.g. from a test harness or wrapper script),
    # no kubectl command will be issued against production under any
    # circumstances.
    # -----------------------------------------------------------------------
    if args.namespace:
        guard_against_prod(args.namespace)
        target_namespaces: List[str] = [args.namespace]
    else:
        for ns in ALLOWED_NAMESPACES:
            guard_against_prod(ns)          # verify the constant list itself is safe
        target_namespaces = list(ALLOWED_NAMESPACES)

    print_banner(target_namespaces)

    # Set up log file in project root (mirrors deploy_platform.py convention)
    project_root = Path(__file__).resolve().parent.parent
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = project_root / f"deploy-mailhog-{timestamp}.log"
    logger = DeploymentLogger(log_file, verbose=args.verbose)

    logger.info("U-Vote Test Platform Deployer — MailHog")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Target namespaces: {', '.join(target_namespaces)}")
    logger.info(f"Pod readiness timeout: {args.timeout}s")

    # Per-namespace phase results — collected for the summary table
    all_results: Dict[str, Dict[str, Optional[bool]]] = {}
    overall_ok = True

    for ns in target_namespaces:
        logger.info("")
        logger.info("━" * 56)
        logger.info(f"  Starting deployment for namespace: {ns}")
        logger.info("━" * 56)

        deployer = MailHogDeployer(
            namespace=ns,
            logger=logger,
            timeout=args.timeout,
        )

        try:
            ok = deployer.deploy()
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            all_results[ns] = deployer.phase_results
            overall_ok = False
            break

        all_results[ns] = deployer.phase_results

        if ok:
            logger.success(f"✓ Namespace '{ns}': all phases passed")
        else:
            logger.error(f"✗ Namespace '{ns}': one or more phases failed")
            overall_ok = False

    print_summary(all_results, logger.elapsed())
    logger.info(f"Log file: {log_file}")
    logger.close()

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════════
# TESTING THIS SCRIPT:
#
# 1. Dry run the help output:
#    python plat_scripts/deploy_test_platform.py --help
#
# 2. Deploy to both namespaces (default):
#    python plat_scripts/deploy_test_platform.py
#
# 3. Deploy to uvote-test only with verbose output:
#    python plat_scripts/deploy_test_platform.py --namespace uvote-test --verbose
#
# 4. Deploy to uvote-dev with extended readiness timeout:
#    python plat_scripts/deploy_test_platform.py --namespace uvote-dev --timeout 120
#
# 5. Verify the production guard:
#    python -c "
#    from plat_scripts.deploy_test_platform import guard_against_prod
#    guard_against_prod('uvote-prod')  # must exit 1 with clear error message
#    "
#
# 6. Check the log file:
#    cat deploy-mailhog-*.log
#
# EXPECTED OUTCOMES:
#
# ✅ SUCCESS (all 7 phases PASS per namespace):
#    - smtp-credentials secret created/updated in each namespace
#    - MailHog Deployment and Service applied
#    - 05-allow-mailhog NetworkPolicy applied
#    - MailHog pod reaches Available state
#    - Secret values verified (SMTP_HOST=mailhog, SMTP_PORT=1025, etc.)
#    - curl pod confirms HTTP API reachable at mailhog:8025
#    - Summary table shows all PASS, exit code 0
#
# ❌ FAILURE:
#    - First failing phase aborts the current namespace
#    - Remaining namespaces are still attempted
#    - Summary table shows PASS/FAIL per phase per namespace
#    - Exit code 1
# ═══════════════════════════════════════════════════════════════════════════
