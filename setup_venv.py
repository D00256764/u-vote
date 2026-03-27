#!/usr/bin/env python3
"""
setup_venv.py — Bootstrap a complete local Python venv for the U-Vote project.

Installs every dependency needed to run:
  - All 5 platform scripts  (plat_scripts/)
  - All integration tests   (tests/test_db.py, tests/test_api.py)
  - All 5 service unit-test suites (auth, voting, election, frontend, admin)
  - All 6 service apps      (for test imports)

Uses only Python stdlib — no third-party packages required to run this script.

Usage:
    python setup_venv.py               # full setup
    python setup_venv.py --clean       # delete .venv and start fresh
    python setup_venv.py --verify-only # skip install, just run import checks
    python setup_venv.py --help        # show this help
"""

import argparse
import platform
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers — disabled on Windows and non-TTY output
# ─────────────────────────────────────────────────────────────────────────────
_USE_COLOUR = sys.stdout.isatty() and platform.system() != "Windows"

GREEN  = "\033[92m" if _USE_COLOUR else ""
RED    = "\033[91m" if _USE_COLOUR else ""
YELLOW = "\033[93m" if _USE_COLOUR else ""
CYAN   = "\033[96m" if _USE_COLOUR else ""
BOLD   = "\033[1m"  if _USE_COLOUR else ""
RESET  = "\033[0m"  if _USE_COLOUR else ""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pip_install(venv_pip: Path, req_path: str):
    """
    Run: <venv_pip> install -r <req_path>
    Returns (success: bool, combined_output: str).
    Does NOT print anything — caller decides what to show.
    """
    result = subprocess.run(
        [str(venv_pip), "install", "-r", req_path],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output


def _print_pip_error(req_path: str, output: str) -> None:
    print(f"\n  {RED}ERROR:{RESET} Failed to install {req_path}")
    print(f"  Command: pip install -r {req_path}")
    print("  pip output:")
    for line in output.splitlines():
        print(f"    {line}")
    print()
    print("  Fix the error above and re-run:")
    print("    python setup_venv.py --clean")


def _run_checks(venv_python: Path) -> int:
    """
    Run all import-verification checks against venv_python.
    Prints results and returns 0 if all pass, 1 if any fail.
    """
    results = []  # list of (label, passed, detail)

    # ── Check 1 — Platform script deps ───────────────────────────────────────
    r = subprocess.run(
        [str(venv_python), "-c",
         "import colorama, click; "
         "print(colorama.__version__); "
         "print(click.__version__)"],
        capture_output=True, text=True,
    )
    lines = r.stdout.strip().splitlines()
    ok1 = r.returncode == 0 and len(lines) >= 2
    results.append(("colorama", ok1, lines[0] if len(lines) > 0 else r.stderr.strip()[:120]))
    results.append(("click",    ok1, lines[1] if len(lines) > 1 else ""))

    # ── Check 2 — Test framework ──────────────────────────────────────────────
    r = subprocess.run(
        [str(venv_python), "-c",
         "import pytest, pytest_asyncio, httpx; "
         "print(pytest.__version__); "
         "print(pytest_asyncio.__version__); "
         "print(httpx.__version__)"],
        capture_output=True, text=True,
    )
    lines = r.stdout.strip().splitlines()
    ok2 = r.returncode == 0 and len(lines) >= 3
    results.append(("pytest",         ok2, lines[0] if len(lines) > 0 else r.stderr.strip()[:120]))
    results.append(("pytest-asyncio", ok2, lines[1] if len(lines) > 1 else ""))
    results.append(("httpx",          ok2, lines[2] if len(lines) > 2 else ""))

    # ── Check 3 — Auth service deps ───────────────────────────────────────────
    r = subprocess.run(
        [str(venv_python), "-c",
         "import fastapi, asyncpg, passlib, jose, bcrypt; "
         "print(fastapi.__version__); "
         "print(asyncpg.__version__)"],
        capture_output=True, text=True,
    )
    lines = r.stdout.strip().splitlines()
    ok3 = r.returncode == 0 and len(lines) >= 2
    err3 = r.stderr.strip()[:120]
    results.append(("fastapi",     ok3, lines[0] if len(lines) > 0 else err3))
    results.append(("asyncpg",     ok3, lines[1] if len(lines) > 1 else ""))
    results.append(("passlib",     ok3, "OK"  if ok3 else err3))
    results.append(("python-jose", ok3, "OK"  if ok3 else ""))
    results.append(("bcrypt",      ok3, "OK"  if ok3 else ""))

    # ── Check 4 — Email and template deps ─────────────────────────────────────
    r = subprocess.run(
        [str(venv_python), "-c",
         "import aiosmtplib, jinja2, itsdangerous; "
         "print(aiosmtplib.__version__); "
         "print(jinja2.__version__); "
         "print(itsdangerous.__version__)"],
        capture_output=True, text=True,
    )
    lines = r.stdout.strip().splitlines()
    ok4 = r.returncode == 0 and len(lines) >= 3
    results.append(("aiosmtplib",   ok4, lines[0] if len(lines) > 0 else r.stderr.strip()[:120]))
    results.append(("jinja2",       ok4, lines[1] if len(lines) > 1 else ""))
    results.append(("itsdangerous", ok4, lines[2] if len(lines) > 2 else ""))

    # ── Check 5 — Metrics ─────────────────────────────────────────────────────
    r = subprocess.run(
        [str(venv_python), "-c",
         "from prometheus_fastapi_instrumentator import Instrumentator; print('ok')"],
        capture_output=True, text=True,
    )
    ok5 = r.returncode == 0 and "ok" in r.stdout
    results.append(
        ("prometheus-fastapi-instrumentator",
         ok5,
         "OK" if ok5 else r.stderr.strip()[:120])
    )

    # ── Check 6 — pytest collection ───────────────────────────────────────────
    r = subprocess.run(
        [
            str(venv_python), "-m", "pytest",
            "auth-service/tests/",
            "voting-service/tests/",
            "election-service/tests/",
            "frontend-service/tests/",
            "admin-service/tests/",
            "--collect-only", "-q", "--no-header",
        ],
        capture_output=True, text=True,
    )
    combined = (r.stdout + r.stderr).strip()
    m = re.search(r"(\d+) tests? collected", combined)
    collected = int(m.group(1)) if m else 0
    # "error" in output AND nothing collected → genuine failure
    has_error = "error" in combined.lower() and collected == 0
    ok6 = collected > 0 and not has_error
    if ok6:
        collection_detail = f"{collected} tests, 0 errors"
    else:
        tail = combined.splitlines()[-1] if combined.splitlines() else "no output"
        collection_detail = tail[:100]
    results.append(("pytest collection", ok6, collection_detail))

    # ── Print results ─────────────────────────────────────────────────────────
    all_passed = True
    label_w = 34  # wide enough for "prometheus-fastapi-instrumentator"
    for label, passed, detail in results:
        if not passed:
            all_passed = False
        marker = f"{GREEN}\u2713{RESET}" if passed else f"{RED}\u2717{RESET}"
        label_str = label if passed else f"{RED}{label}{RESET}"
        # Pad the raw label (without colour codes) for alignment
        padding = " " * max(1, label_w - len(label))
        print(f"      {marker} {label_str}{padding}{detail}")

    print()
    if not all_passed:
        print(f"  {RED}Setup failed.{RESET} Fix the errors above and re-run:")
        print("    python setup_venv.py --clean")
        print()
        return 1

    return 0


def _print_footer() -> None:
    sep = "  " + "\u2550" * 46
    print(sep)
    print(f"  {BOLD}Activate with:{RESET}")
    print()
    print(f"    Linux/macOS:  {CYAN}source .venv/bin/activate{RESET}")
    print(f"    Windows:      {CYAN}.venv\\Scripts\\activate.bat{RESET}")
    print()
    print(f"  {BOLD}Run unit tests (no cluster needed):{RESET}")
    print(f"    {CYAN}python -m pytest auth-service/tests/ voting-service/tests/ \\{RESET}")
    print(f"    {CYAN}  election-service/tests/ frontend-service/tests/ \\{RESET}")
    print(f"    {CYAN}  admin-service/tests/ -v{RESET}")
    print()
    print(f"  {BOLD}Run platform scripts:{RESET}")
    print(f"    {CYAN}python plat_scripts/deploy_platform.py --help{RESET}")
    print(f"    {CYAN}python plat_scripts/setup_k8s_platform.py --help{RESET}")
    print()
    print(f"  {BOLD}Run integration tests (cluster required):{RESET}")
    print(f"    {CYAN}python -m pytest tests/test_db.py tests/test_api.py -v{RESET}")
    print(sep)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap the U-Vote Python virtual environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python setup_venv.py               # full setup\n"
            "  python setup_venv.py --clean       # delete .venv and start fresh\n"
            "  python setup_venv.py --verify-only # skip install, just run checks\n"
        ),
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Skip install, just run import checks against existing .venv",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Delete existing .venv and perform a clean install",
    )
    args = parser.parse_args()

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print(f"{BOLD}  \u2554{'═' * 42}\u2557{RESET}")
    print(f"{BOLD}  \u2551     U-Vote Virtual Environment Setup    \u2551{RESET}")
    print(f"{BOLD}  \u255a{'═' * 42}\u255d{RESET}")
    print()

    # ── Sanity check: must be run from the project root ───────────────────────
    root = Path.cwd()
    missing = []
    if not (root / "plat_scripts").is_dir():
        missing.append("plat_scripts/")
    if not (root / "requirements-dev.txt").is_file():
        missing.append("requirements-dev.txt")
    if missing:
        print(f"  {RED}ERROR:{RESET} Must be run from the U-Vote project root.")
        print(f"  Missing in current directory: {', '.join(missing)}")
        print(f"  Current directory: {root}")
        return 1

    # ── Python version check ──────────────────────────────────────────────────
    py_ver = (
        f"{sys.version_info.major}."
        f"{sys.version_info.minor}."
        f"{sys.version_info.micro}"
    )
    print(f"  Python {py_ver} on {sys.platform}")
    print(f"  Project root: {root}")
    print()

    if sys.version_info < (3, 10):
        print(f"  {RED}ERROR:{RESET} Python 3.10+ required, found {py_ver}")
        print("  Install Python 3.10 or higher and re-run.")
        return 1

    # ── Resolve venv paths (cross-platform) ───────────────────────────────────
    venv_dir = root / ".venv"
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip    = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip    = venv_dir / "bin" / "pip"

    TOTAL = 7

    # ── --verify-only: jump straight to checks ────────────────────────────────
    if args.verify_only:
        if not venv_python.exists():
            print(f"  {RED}ERROR:{RESET} No .venv found at {venv_dir}")
            print("  Run without --verify-only first to create the environment.")
            return 1
        print("  Skipping install (--verify-only mode)")
        print()
        return _run_checks(venv_python)

    # ── [1/7] Create (or reuse) virtual environment ───────────────────────────
    if args.clean and venv_dir.exists():
        print(
            f"  {CYAN}[1/{TOTAL}]{RESET} Recreating virtual environment...  ",
            end="", flush=True,
        )
        shutil.rmtree(venv_dir)
        try:
            venv.create(str(venv_dir), with_pip=True, clear=False)
        except Exception as exc:
            print(f"{RED}\u2717{RESET}")
            print(f"\n  {RED}ERROR:{RESET} venv creation failed: {exc}")
            return 1
        print(f"{GREEN}\u2713{RESET}")

    elif venv_dir.exists():
        print(
            f"  {CYAN}[1/{TOTAL}]{RESET} Using existing .venv               "
            f"{GREEN}\u2713{RESET}"
        )

    else:
        print(
            f"  {CYAN}[1/{TOTAL}]{RESET} Creating virtual environment...    ",
            end="", flush=True,
        )
        try:
            venv.create(str(venv_dir), with_pip=True, clear=False)
        except Exception as exc:
            print(f"{RED}\u2717{RESET}")
            print(f"\n  {RED}ERROR:{RESET} venv creation failed: {exc}")
            return 1
        print(f"{GREEN}\u2713{RESET}")

    # ── [2/7] Upgrade pip ─────────────────────────────────────────────────────
    print(
        f"  {CYAN}[2/{TOTAL}]{RESET} Upgrading pip...                   ",
        end="", flush=True,
    )
    r = subprocess.run(
        [str(venv_pip), "install", "--upgrade", "pip"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"{RED}\u2717{RESET}")
        print(f"\n  {RED}ERROR:{RESET} pip upgrade failed")
        print(f"  Command: {venv_pip} install --upgrade pip")
        print(r.stderr)
        return 1
    print(f"{GREEN}\u2713{RESET}")

    # ── [3/7] Dev/test tools ──────────────────────────────────────────────────
    print(
        f"  {CYAN}[3/{TOTAL}]{RESET} Installing dev/test tools...       ",
        end="", flush=True,
    )
    ok, err = _pip_install(venv_pip, "requirements-dev.txt")
    if not ok:
        print(f"{RED}\u2717{RESET}")
        _print_pip_error("requirements-dev.txt", err)
        return 1
    print(f"{GREEN}\u2713{RESET}")

    # ── [4/7] Platform script tools ───────────────────────────────────────────
    print(
        f"  {CYAN}[4/{TOTAL}]{RESET} Installing platform tools...       ",
        end="", flush=True,
    )
    ok, err = _pip_install(venv_pip, "plat_scripts/requirements.txt")
    if not ok:
        print(f"{RED}\u2717{RESET}")
        _print_pip_error("plat_scripts/requirements.txt", err)
        return 1
    print(f"{GREEN}\u2713{RESET}")

    # ── [5/7] Service runtime dependencies ───────────────────────────────────
    services = [
        ("auth-service",     "auth-service/requirements.txt"),
        ("voting-service",   "voting-service/requirements.txt"),
        ("election-service", "election-service/requirements.txt"),
        ("results-service",  "results-service/requirements.txt"),
        ("admin-service",    "admin-service/requirements.txt"),
        ("frontend-service", "frontend-service/requirements.txt"),
    ]

    for i, (svc_name, req_path) in enumerate(services):
        prefix = f"  {CYAN}[5/{TOTAL}]{RESET}" if i == 0 else "        "
        label  = f"Installing {svc_name}..."
        print(f"{prefix} {label:<28}", end="", flush=True)
        ok, err = _pip_install(venv_pip, req_path)
        if not ok:
            print(f"{RED}\u2717{RESET}")
            _print_pip_error(req_path, err)
            return 1
        print(f"{GREEN}\u2713{RESET}")

    # ── [6/7] Verification checks ─────────────────────────────────────────────
    print(f"  {CYAN}[6/{TOTAL}]{RESET} Running verification checks...")
    print()
    rc = _run_checks(venv_python)
    if rc != 0:
        return rc

    # ── [7/7] Done ────────────────────────────────────────────────────────────
    print(f"  {CYAN}[7/{TOTAL}]{RESET} {GREEN}{BOLD}Setup complete!{RESET}")
    print()
    _print_footer()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print("Setup cancelled.")
        sys.exit(1)
