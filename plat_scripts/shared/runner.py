"""Shared subprocess helper for U-Vote platform scripts."""

import subprocess
from typing import List, Tuple

# Module-level state — configure once per script via configure()
_dry_run: bool = False
_logger = None


def configure(dry_run: bool = False, logger=None) -> None:
    """Set the dry-run flag and optional logger for all subsequent run_cmd calls."""
    global _dry_run, _logger
    _dry_run = dry_run
    _logger = logger


def run_cmd(
    cmd: List[str],
    check: bool = True,
    timeout: int = 60,
    mutating: bool = False,
) -> Tuple[int, str, str]:
    """Run *cmd*, return (returncode, stdout, stderr).

    If *mutating* is True and dry-run mode is active the command is skipped
    and a simulated success (0, "", "") is returned.  Read-only commands
    (mutating=False) always execute regardless of dry-run mode.

    The *check* parameter mirrors deploy_platform.py: when True, stderr from
    a non-zero exit is logged at DEBUG level.  The function never raises on a
    non-zero returncode; the caller must inspect the returned returncode.
    """
    if _logger:
        _logger.debug(f"CMD: {' '.join(cmd)}")

    if _dry_run and mutating:
        if _logger:
            _logger.info(f"  [DRY-RUN] {' '.join(cmd)}")
        return (0, "", "")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0 and check:
            if _logger:
                _logger.debug(f"STDERR: {proc.stderr.strip()}")
        return (proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        if _logger:
            _logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return (1, "", "timeout")
    except FileNotFoundError:
        if _logger:
            _logger.error(f"Command not found: {cmd[0]}")
        return (1, "", f"{cmd[0]} not found")
