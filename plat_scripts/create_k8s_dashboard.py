#!/usr/bin/env python3
"""
Install the Kubernetes Dashboard and configure admin-user access.

Installation method: kubectl apply with the official v2.7.0 recommended manifest.
(The Helm repo at https://kubernetes.github.io/dashboard is not currently reachable;
the manifest installs identical resources including the kubernetes-dashboard Service
that port_forward.py expects.)

Steps:
  1. Apply the official recommended.yaml (creates namespace + all resources)
  2. Wait for the dashboard Deployment to be Ready
  3. Apply admin-user ServiceAccount + ClusterRoleBinding
  4. Generate a login token for admin-user
  5. Print the dashboard URL and token
"""
import subprocess
import sys

NAMESPACE       = "kubernetes-dashboard"
MANIFEST_URL    = (
    "https://raw.githubusercontent.com/kubernetes/dashboard"
    "/v2.7.0/aio/deploy/recommended.yaml"
)
DASHBOARD_URL   = (
    f"http://localhost:8001/api/v1/namespaces/{NAMESPACE}"
    f"/services/https:kubernetes-dashboard:/proxy/"
)

ADMIN_USER_YAML = f"""\
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: {NAMESPACE}
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
  namespace: {NAMESPACE}
"""


def info(msg):    print(f"[INFO] {msg}")
def success(msg): print(f"[SUCCESS] {msg}")
def error(msg):   print(f"[ERROR] {msg}")


def run(cmd, timeout=120):
    """Run *cmd*, return (returncode, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"command timed out after {timeout}s"
    except FileNotFoundError as e:
        return 1, "", str(e)


def run_or_die(cmd, label, timeout=120):
    rc, out, err = run(cmd, timeout=timeout)
    if rc != 0:
        error(f"{label}: {(err or out).strip()}")
        sys.exit(1)
    return out


if __name__ == "__main__":
    # ── Step 1: Apply the official manifest ───────────────────────────────────
    info(f"Applying Kubernetes Dashboard manifest ({MANIFEST_URL})...")
    run_or_die(
        ["kubectl", "apply", "-f", MANIFEST_URL],
        "kubectl apply recommended.yaml",
        timeout=60,
    )
    success("Manifest applied")

    # ── Step 2: Wait for the Deployment to be Ready ───────────────────────────
    info("Waiting for kubernetes-dashboard Deployment to be Ready (up to 3m)...")
    rc, _, err = run(
        [
            "kubectl", "rollout", "status",
            "deployment/kubernetes-dashboard",
            "-n", NAMESPACE,
            "--timeout=3m",
        ],
        timeout=200,
    )
    if rc != 0:
        error(f"Deployment did not become Ready: {err.strip()}")
        sys.exit(1)
    success("kubernetes-dashboard Deployment is Ready")

    # ── Step 3: admin-user ServiceAccount + ClusterRoleBinding ────────────────
    info("Applying admin-user ServiceAccount and ClusterRoleBinding...")
    result = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=ADMIN_USER_YAML,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"Failed to apply admin-user resources: {result.stderr.strip()}")
        sys.exit(1)
    success("admin-user resources applied")

    # ── Step 4: Generate login token ───────────────────────────────────────────
    info("Generating login token for admin-user...")
    rc, token_out, err = run(
        ["kubectl", "create", "token", "admin-user", "-n", NAMESPACE],
    )
    if rc != 0 or not token_out.strip():
        error(f"Failed to generate token: {err.strip()}")
        sys.exit(1)
    token = token_out.strip()
    success("Login token generated")

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("Kubernetes Dashboard installed successfully")
    print("=" * 70)
    print()
    print("  Access via kubectl proxy:")
    print("    kubectl proxy")
    print()
    print(f"  URL:   {DASHBOARD_URL}")
    print(f"  Token: {token}")
    print()
    print("  Or use port_forward.py to manage all forwards in one session:")
    print("    python3 plat_scripts/port_forward.py")
    print("=" * 70)
