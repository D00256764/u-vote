"""Shared deployment logger — coloured console output with optional log-file sink."""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import click
except ImportError:
    print("ERROR: 'click' package required. Install with: pip install click")
    raise

try:
    from colorama import init, Fore, Style
    init()
except ImportError:
    print("ERROR: 'colorama' package required. Install with: pip install colorama")
    raise


class DeploymentLogger:
    """Dual logger: coloured console + plain-text log file.

    If *log_file* is None the logger writes to the console only.
    """

    LEVEL_COLOURS = {
        "INFO":    Fore.WHITE,
        "SUCCESS": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR":   Fore.RED,
        "DEBUG":   Fore.CYAN,
    }

    def __init__(self, log_file: Optional[Path] = None, verbose: bool = False):
        self.log_file = log_file
        self.verbose = verbose
        self.start_time = time.time()
        self._fh = open(log_file, "a", encoding="utf-8") if log_file else None

    # -- core -----------------------------------------------------------------

    def log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain = f"[{ts}] [{level}] {message}"
        colour = self.LEVEL_COLOURS.get(level, "")
        coloured = f"{colour}[{ts}] [{level}]{Style.RESET_ALL} {message}"

        if level == "DEBUG" and not self.verbose:
            if self._fh:
                self._fh.write(plain + "\n")
                self._fh.flush()
            return

        click.echo(coloured)
        if self._fh:
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

    # -- utility --------------------------------------------------------------

    def elapsed(self) -> str:
        secs = int(time.time() - self.start_time)
        m, s = divmod(secs, 60)
        return f"{m}m {s:02d}s"

    def close(self) -> None:
        if self._fh:
            self._fh.close()
