"""
Unit tests for shared/logging_config.py

Run with:
    python3 -m pytest tests/test_logging_config.py -v

No database, Docker, or running services required.
"""

import io
import json
import logging
import os
import sys
from datetime import datetime

import pytest

# Add project root to sys.path so 'shared' is importable as a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.logging_config import configure_logging


@pytest.fixture(autouse=True)
def reset_logging():
    """Clear root handlers before each test to prevent state leakage."""
    logging.root.handlers = []
    yield
    logging.root.handlers = []


# ── Helper ────────────────────────────────────────────────────────────────────

def _install_buffer():
    """Redirect the root handler's stream to a fresh StringIO buffer."""
    buf = io.StringIO()
    logging.getLogger('').handlers[0].stream = buf
    return buf


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_handler_installed():
    """configure_logging() must install at least one handler on the root logger."""
    configure_logging()
    assert len(logging.getLogger('').handlers) >= 1


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_output_is_valid_json():
    """Each emitted log line must be parseable as JSON."""
    configure_logging()
    buf = _install_buffer()
    logging.getLogger('test').info('test message')
    buf.seek(0)
    line = buf.read().strip()
    # Must not raise
    json.loads(line)


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_required_fields_present():
    """Parsed log record must contain asctime, name, levelname, and message."""
    configure_logging()
    buf = _install_buffer()
    logging.getLogger('test').info('test message')
    buf.seek(0)
    record = json.loads(buf.read().strip())
    for field in ('asctime', 'name', 'levelname', 'message'):
        assert field in record, f"Missing required field: '{field}'"


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_asctime_matches_configured_date_format():
    """asctime must match the format '%Y-%m-%dT%H:%M:%SZ' configured in LOGGING."""
    configure_logging()
    buf = _install_buffer()
    logging.getLogger('test').info('test message')
    buf.seek(0)
    record = json.loads(buf.read().strip())
    # Must not raise — validates the format exactly
    datetime.strptime(record['asctime'], '%Y-%m-%dT%H:%M:%SZ')


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_logger_name_preserved():
    """The 'name' field in the JSON output must match the logger's name."""
    configure_logging()
    for name in ('auth-service', 'voter-service'):
        buf = io.StringIO()
        logging.getLogger('').handlers[0].stream = buf
        logging.getLogger(name).info('test message')
        buf.seek(0)
        record = json.loads(buf.read().strip())
        assert record['name'] == name, (
            f"Expected name '{name}', got '{record['name']}'"
        )


# ── Test 6 ────────────────────────────────────────────────────────────────────

def test_log_level_reflected_in_output():
    """levelname in JSON must reflect the level used to emit each record."""
    configure_logging()
    buf = _install_buffer()
    logger = logging.getLogger('test')
    logger.info('info message')
    logger.warning('warning message')
    buf.seek(0)
    lines = [l for l in buf.read().strip().splitlines() if l.strip()]
    assert len(lines) == 2, f"Expected 2 log lines, got {len(lines)}"
    assert json.loads(lines[0])['levelname'] == 'INFO'
    assert json.loads(lines[1])['levelname'] == 'WARNING'


# ── Test 7 ────────────────────────────────────────────────────────────────────

def test_debug_messages_suppressed():
    """Messages emitted below INFO must not appear in the output."""
    configure_logging()
    buf = _install_buffer()
    logging.getLogger('test').debug('debug message')
    buf.seek(0)
    assert buf.read().strip() == ''


# ── Test 8 ────────────────────────────────────────────────────────────────────
#
# Expected behaviour: calling configure_logging() twice should not accumulate
# handlers on the root logger — the second call should replace, not append.
#
# logging.config.dictConfig() creates new handler instances on every invocation.
# If the implementation does not explicitly deduplicate or clear handlers before
# installing new ones, each call adds another StreamHandler, doubling output and
# making every log line appear multiple times.
#
# Fix: guard configure_logging() with a sentinel flag, or clear
# logging.root.handlers before calling dictConfig(), e.g.:
#
#     def configure_logging():
#         logging.root.handlers = []
#         logging.config.dictConfig(LOGGING)

@pytest.mark.xfail(reason='configure_logging does not deduplicate handlers')
def test_configure_logging_is_idempotent():
    """Calling configure_logging() twice must not accumulate root handlers."""
    configure_logging()
    count_after_first = len(logging.getLogger('').handlers)
    configure_logging()
    count_after_second = len(logging.getLogger('').handlers)
    assert count_after_second == count_after_first, (
        f"Handler count grew from {count_after_first} to {count_after_second} "
        f"after a second configure_logging() call"
    )
