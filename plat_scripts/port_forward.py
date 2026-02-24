#!/usr/bin/env python3
"""
UVote Port Forwarder

Establishes and maintains a kubectl port-forward tunnel from the
ingress-nginx-controller service (port 80) to localhost:<port>.

The tunnel is automatically restarted if it dies unexpectedly.
Press Ctrl+C to stop.

Usage:
    python plat_scripts/port_forward.py
    python plat_scripts/port_forward.py --port 9090
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INGRESS_NAMESPACE = "ingress-nginx"
INGRESS_SERVICE   = "ingress-nginx-controller"
SERVICE_PORT      = 80
DEFAULT_LOCAL_PORT = 8080

READY_TIMEOUT  = 15   # seconds to wait for the tunnel to accept connections
RESTART_DELAY  = 3    # seconds to wait before restarting a dead tunnel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_ingress_service() -> bool:
    """Return True if ingress-nginx-controller service exists in the cluster."""
    result = subprocess.run(
        ["kubectl", "get", "service", INGRESS_SERVICE, "-n", INGRESS_NAMESPACE],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def port_in_use(port: int) -> bool:
    """Return True if something is already listening on localhost:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def find_pid_on_port(port: int) -> Optional[int]:
    """Return the PID of the process listening on *port*, or None.

    Reads /proc/net/tcp and /proc/net/tcp6 to locate the socket inode, then
    walks /proc/<pid>/fd to match that inode to a running process.
    Pure-Python — no external tool dependency.
    """
    hex_port = f"{port:04X}"
    inode: Optional[int] = None

    for tcp_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(tcp_file) as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) < 10:
                        continue
                    local_port_hex = parts[1].split(":")[1]
                    state = parts[3]
                    if state == "0A" and local_port_hex == hex_port:  # 0A = LISTEN
                        inode = int(parts[9])
                        break
        except FileNotFoundError:
            continue
        if inode is not None:
            break

    if inode is None:
        return None

    socket_link = f"socket:[{inode}]"
    for pid_dir in Path("/proc").iterdir():
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        try:
            for fd_path in fd_dir.iterdir():
                try:
                    if os.readlink(str(fd_path)) == socket_link:
                        return int(pid_dir.name)
                except OSError:
                    pass
        except (PermissionError, FileNotFoundError):
            pass

    return None


def free_port(port: int) -> bool:
    """Send SIGTERM (then SIGKILL if needed) to the process on *port*.

    Returns True if the port was freed, False if it could not be killed.
    """
    pid = find_pid_on_port(port)
    if pid is None:
        return False

    print(f"  Terminating PID {pid} (currently holding port {port})...")
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait up to 1 s for a graceful exit
        for _ in range(10):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)  # raises ProcessLookupError when process is gone
            except ProcessLookupError:
                return True
        # Still alive — force it
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.1)
        return True
    except (ProcessLookupError, PermissionError) as exc:
        print(f"  Could not kill PID {pid}: {exc}", file=sys.stderr)
        return False


def wait_for_port(port: int, timeout: int = READY_TIMEOUT) -> bool:
    """Poll until localhost:port accepts a TCP connection. Return True if ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def start_tunnel(local_port: int) -> subprocess.Popen:
    """Launch kubectl port-forward and return the Popen handle."""
    return subprocess.Popen(
        [
            "kubectl", "port-forward",
            "--namespace", INGRESS_NAMESPACE,
            f"service/{INGRESS_SERVICE}",
            f"{local_port}:{SERVICE_PORT}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def read_stderr(proc: subprocess.Popen) -> str:
    """Read whatever is buffered on stderr without blocking if the pipe is empty."""
    try:
        return proc.stderr.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            f"Forward {INGRESS_SERVICE}:{SERVICE_PORT} to localhost "
            f"so the UVote platform is reachable from the host."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python plat_scripts/port_forward.py\n"
            "  python plat_scripts/port_forward.py --port 9090\n"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_LOCAL_PORT,
        metavar="PORT",
        help=f"Local port to forward to (default: {DEFAULT_LOCAL_PORT})",
    )
    args = parser.parse_args()
    local_port: int = args.port

    # ------------------------------------------------------------------
    # 1. Verify kubectl is available
    # ------------------------------------------------------------------
    if subprocess.run(["kubectl", "version", "--client"], capture_output=True).returncode != 0:
        print("Error: kubectl not found or not working. Is it installed and on PATH?",
              file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Verify the ingress controller service exists
    # ------------------------------------------------------------------
    print(f"Checking for {INGRESS_SERVICE} in namespace {INGRESS_NAMESPACE}...")
    if not check_ingress_service():
        print(
            f"\nError: Service '{INGRESS_SERVICE}' was not found in namespace "
            f"'{INGRESS_NAMESPACE}'.\n"
            f"       The ingress-nginx controller does not appear to be installed.\n"
            f"       Deploy it first, then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  Service found.")

    # ------------------------------------------------------------------
    # 3. Handle port conflict
    # ------------------------------------------------------------------
    if port_in_use(local_port):
        pid = find_pid_on_port(local_port)
        pid_label = f" (PID {pid})" if pid else ""
        print(f"\nPort {local_port} is already in use{pid_label}.")

        if pid is not None:
            if not free_port(local_port):
                print(
                    f"  Failed to free port {local_port}.\n"
                    f"  Try: python plat_scripts/port_forward.py --port {local_port + 1}",
                    file=sys.stderr,
                )
                sys.exit(1)
            # Brief pause to let the OS release the socket
            time.sleep(0.5)
        else:
            print(
                f"  Could not identify the process holding port {local_port}.\n"
                f"  Try: python plat_scripts/port_forward.py --port {local_port + 1}",
                file=sys.stderr,
            )
            sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Port-forward loop with auto-restart
    # ------------------------------------------------------------------
    proc: Optional[subprocess.Popen] = None

    def _shutdown(signum=None, frame=None) -> None:
        print("\nShutting down...")
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Port-forward closed.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(
        f"\nForwarding  localhost:{local_port}  →  "
        f"{INGRESS_SERVICE}:{SERVICE_PORT}\n"
        f"Press Ctrl+C to stop.\n"
    )

    first_connect = True

    while True:
        proc = start_tunnel(local_port)

        if not wait_for_port(local_port, timeout=READY_TIMEOUT):
            # Tunnel never became ready — gather diagnostics
            if proc.poll() is not None:
                reason = read_stderr(proc)
            else:
                proc.terminate()
                proc.wait()
                reason = read_stderr(proc)

            suffix = f": {reason}" if reason else ""
            print(f"Tunnel did not become ready within {READY_TIMEOUT}s{suffix}.")
            print(f"Retrying in {RESTART_DELAY}s...")
            time.sleep(RESTART_DELAY)
            continue

        if first_connect:
            print(f"UVote is available at http://localhost:{local_port}")
            first_connect = False
        else:
            print(f"[reconnected]  Tunnel re-established at http://localhost:{local_port}")

        # Block until the port-forward process exits
        proc.wait()

        # Diagnose the unexpected exit
        reason = read_stderr(proc)
        msg = f"Port-forward exited (code {proc.returncode})"
        if reason:
            msg += f": {reason}"
        print(msg)
        print(f"Restarting in {RESTART_DELAY}s...  (Ctrl+C to quit)")
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    main()
