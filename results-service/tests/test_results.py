"""
results-service/tests/test_results.py — pytest unit tests for results-service.

Coverage:
  - GET /health
  - GET /elections/{id}/results    (JSON API)
  - GET /elections/{id}/audit      (JSON API)
  - GET /elections/{id}/statistics (JSON API)
  - Role permission documentation test (reads create_roles.sql)

Architecture notes:
  - results-service has NO try/except in any JSON API endpoint.
    DB errors propagate as raw 500s (FastAPI default handler).
  - GET /results and GET /audit return 403 when election is open.
  - GET /statistics has NO status check — returns 200 for any status.
  - The "winner" is NOT a named field; results are sorted vote_count DESC
    so the first entry in results[] is always the leading candidate.
  - fetchval is called TWICE in get_results: total_votes then total_voters.
    Use side_effect=[total_votes, total_voters] for both calls.
  - fetchrow is called TWICE in get_statistics: election row then
    token_stats row. Use side_effect=[election_row, token_stats_row].

Run with:
    .venv/bin/python -m pytest results-service/tests/ -v
"""
from datetime import datetime, timedelta
from pathlib import Path


# =============================================================================
# GET /health
# =============================================================================

def test_health_returns_results(client):
    """GET /health returns 200 with service identifier 'results'."""
    r = client["client"].get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "service": "results"}


# =============================================================================
# GET /elections/{id}/results
# =============================================================================

def test_results_blocked_while_open(client, mock_db, open_election_row):
    """
    Returns 403 while election is still open.

    app.py line 106-110:
        if election["status"] != "closed":
            raise HTTPException(status_code=403, ...)
    """
    mock_db.fetchrow.return_value = open_election_row

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 403
    body = r.json()
    assert "detail" in body
    assert "closed" in body["detail"].lower()


def test_results_election_not_found(client, mock_db):
    """Returns 404 for a non-existent election."""
    mock_db.fetchrow.return_value = None

    r = client["client"].get("/elections/999/results")

    assert r.status_code == 404
    assert "detail" in r.json()


def test_results_success_structure(client, mock_db, closed_election_row,
                                   tallied_votes_rows):
    """
    Returns 200 with correct result structure for a closed election.

    get_results DB call order (all within one Database.connection()):
      1. fetchrow  → election (id, title, status, closed_at)
      2. fetch     → tallied results (id, option_text, display_order, vote_count)
      3. fetchval  → total_votes  (COUNT(*) encrypted_ballots)
      4. fetchval  → total_voters (COUNT(*) voters)

    Response shape:
      {
          "election": {"id", "title", "status", "closed_at"},
          "summary":  {"total_votes", "total_voters", "turnout_percentage"},
          "results":  [{"option_id", "option_text", "vote_count", "percentage"}]
      }
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = tallied_votes_rows
    mock_db.fetchval.side_effect = [18, 20]  # total_votes, total_voters

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 200
    body = r.json()

    # Top-level keys
    assert "election" in body
    assert "summary" in body
    assert "results" in body

    # Election sub-dict
    assert body["election"]["id"] == 1
    assert body["election"]["title"] == "Test Election 2026"
    assert body["election"]["status"] == "closed"

    # Summary sub-dict
    assert body["summary"]["total_votes"] == 18
    assert body["summary"]["total_voters"] == 20

    # Results list
    assert len(body["results"]) == 3
    first = body["results"][0]
    assert "option_id" in first
    assert "option_text" in first
    assert "vote_count" in first
    assert "percentage" in first


def test_results_vote_percentages(client, mock_db, closed_election_row,
                                  tallied_votes_rows):
    """
    Vote percentages are calculated correctly.

    tallied_votes_rows: Alice=10, Bob=5, Carol=3 → total=18
    Alice percentage = 10/18 * 100 ≈ 55.56%
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = tallied_votes_rows
    mock_db.fetchval.side_effect = [18, 20]

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 200
    results = r.json()["results"]

    alice = next(item for item in results if item["option_text"] == "Alice Johnson")
    expected_pct = round(10 / 18 * 100, 2)
    assert abs(alice["percentage"] - expected_pct) < 0.1, (
        f"Expected ≈{expected_pct}, got {alice['percentage']}"
    )

    bob = next(item for item in results if item["option_text"] == "Bob Smith")
    expected_bob = round(5 / 18 * 100, 2)
    assert abs(bob["percentage"] - expected_bob) < 0.1


def test_results_winner_identified(client, mock_db, closed_election_row,
                                   tallied_votes_rows):
    """
    The candidate with the most votes appears first in the results list.

    app.py sorts results by vote_count DESC then display_order.
    There is no separate "winner" key — the winner is results[0].
    tallied_votes_rows has Alice Johnson with 10 votes (highest).
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = tallied_votes_rows
    mock_db.fetchval.side_effect = [18, 20]

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["option_text"] == "Alice Johnson"
    assert results[0]["vote_count"] == 10


def test_results_zero_votes_no_division_error(client, mock_db,
                                              closed_election_row):
    """
    When total_votes is 0 the percentage calculation does not divide by zero.

    app.py line 133:
        pct = (r["vote_count"] / total_votes * 100) if total_votes > 0 else 0

    All percentages should be 0; turnout_percentage should also be 0
    (guarded separately: `if total_voters > 0 else 0`).
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = [
        {"id": 1, "option_text": "Alice Johnson", "display_order": 1,
         "vote_count": 0},
    ]
    mock_db.fetchval.side_effect = [0, 20]  # total_votes=0, total_voters=20

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 200
    body = r.json()
    assert body["results"][0]["percentage"] == 0
    assert body["summary"]["total_votes"] == 0
    assert body["summary"]["turnout_percentage"] == 0


def test_results_turnout_percentage_zero_voters(client, mock_db,
                                                closed_election_row):
    """
    When total_voters is 0 the turnout percentage is 0, not a ZeroDivisionError.

    app.py line 151:
        "turnout_percentage": round(...) if total_voters > 0 else 0
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = []
    mock_db.fetchval.side_effect = [0, 0]  # total_votes=0, total_voters=0

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 200
    assert r.json()["summary"]["turnout_percentage"] == 0


def test_results_db_error_returns_500(client, mock_db):
    """
    Unhandled DB errors in get_results propagate as HTTP 500.

    results-service has no try/except in get_results. Any exception from
    the DB layer reaches FastAPI's default error handler → 500.
    """
    mock_db.fetchrow.side_effect = Exception("db connection lost")

    r = client["client"].get("/elections/1/results")

    assert r.status_code == 500


# =============================================================================
# GET /elections/{id}/audit
# =============================================================================

def test_audit_election_not_found(client, mock_db):
    """Returns 404 for a non-existent election."""
    mock_db.fetchrow.return_value = None

    r = client["client"].get("/elections/999/audit")

    assert r.status_code == 404
    assert "detail" in r.json()


def test_audit_blocked_while_open(client, mock_db):
    """
    Returns 403 when election is not yet closed.

    get_audit_trail only fetches status from the DB:
        SELECT status FROM elections WHERE id = $1

    app.py line 168-171:
        if status_row["status"] != "closed":
            raise HTTPException(status_code=403, ...)
    """
    mock_db.fetchrow.return_value = {"status": "open"}

    r = client["client"].get("/elections/1/audit")

    assert r.status_code == 403
    assert "closed" in r.json()["detail"].lower()


def test_audit_returns_hash_chain(client, mock_db, audit_rows):
    """
    Returns audit trail with hash-chained entries.

    get_audit_trail DB call order:
      1. fetchrow → {"status": "closed"}   (just the status column)
      2. fetch    → encrypted_ballots rows (id, vote_hash, previous_hash, cast_at)

    Response shape:
      {
          "election_id":     int,
          "total_votes":     int,
          "hash_chain_valid": bool,
          "audit_trail":    [{"vote_id", "vote_hash", "previous_hash", "cast_at", "sequence"}]
      }

    audit_rows fixture has a valid chain:
      entry[0].vote_hash == "aabbcc" * 10
      entry[1].previous_hash == "aabbcc" * 10  →  chain is valid
    """
    mock_db.fetchrow.return_value = {"status": "closed"}
    mock_db.fetch.return_value = audit_rows

    r = client["client"].get("/elections/1/audit")

    assert r.status_code == 200
    body = r.json()

    assert body["election_id"] == 1
    assert body["total_votes"] == 2
    assert body["hash_chain_valid"] is True

    trail = body["audit_trail"]
    assert len(trail) == 2

    # Sequence numbers assigned in order
    assert trail[0]["sequence"] == 1
    assert trail[1]["sequence"] == 2

    # Hash chain: second entry's previous_hash == first entry's vote_hash
    assert trail[1]["previous_hash"] == trail[0]["vote_hash"]


def test_audit_broken_hash_chain(client, mock_db):
    """
    hash_chain_valid is False when previous_hash does not match preceding vote_hash.

    app.py lines 186-191:
        if i > 0:
            expected = votes[i - 1]["vote_hash"]
            if vote["previous_hash"] != expected:
                hash_chain_valid = False
    """
    bad_chain = [
        {"id": 1, "vote_hash": "aaaa", "previous_hash": None,
         "cast_at": datetime.utcnow() - timedelta(hours=2)},
        {"id": 2, "vote_hash": "bbbb", "previous_hash": "WRONG_HASH",
         "cast_at": datetime.utcnow() - timedelta(hours=1)},
    ]
    mock_db.fetchrow.return_value = {"status": "closed"}
    mock_db.fetch.return_value = bad_chain

    r = client["client"].get("/elections/1/audit")

    assert r.status_code == 200
    assert r.json()["hash_chain_valid"] is False


def test_audit_empty_trail(client, mock_db, closed_election_row):
    """
    Returns 200 with an empty audit_trail list when no votes have been cast.

    Uses closed_election_row to confirm the endpoint selects only the
    'status' field — the extra fields in the fixture dict are ignored.
    """
    mock_db.fetchrow.return_value = closed_election_row
    mock_db.fetch.return_value = []

    r = client["client"].get("/elections/1/audit")

    assert r.status_code == 200
    body = r.json()
    assert body["total_votes"] == 0
    assert body["hash_chain_valid"] is True
    assert body["audit_trail"] == []


def test_audit_db_error_returns_500(client, mock_db):
    """Unhandled DB errors in get_audit_trail propagate as HTTP 500."""
    mock_db.fetchrow.side_effect = Exception("db connection lost")

    r = client["client"].get("/elections/1/audit")

    assert r.status_code == 500


# =============================================================================
# GET /elections/{id}/statistics
# =============================================================================

def test_statistics_election_not_found(client, mock_db):
    """Returns 404 for a non-existent election."""
    mock_db.fetchrow.return_value = None

    r = client["client"].get("/elections/999/statistics")

    assert r.status_code == 404
    assert "detail" in r.json()


def test_statistics_returns_expected_shape(client, mock_db, closed_election_row):
    """
    Returns 200 with correct statistics shape for a closed election.

    get_statistics DB call order (within one Database.connection()):
      1. fetchrow  → election (title, status, created_at, opened_at, closed_at)
      2. fetchval  → total_votes  (COUNT(*) encrypted_ballots)
      3. fetchval  → total_voters (COUNT(*) voters)
      4. fetchrow  → token_stats  (total_tokens, used_tokens)
      5. fetch     → vote timeline (only when status == "closed")

    Response shape:
      {
          "election":   {"title", "status", "created_at", "opened_at", "closed_at"},
          "statistics": {"total_voters", "total_tokens", "used_tokens",
                         "total_votes", "turnout_rate"},
          "vote_timeline": [...]
      }
    """
    token_stats_row = {"total_tokens": 5, "used_tokens": 3}
    mock_db.fetchrow.side_effect = [closed_election_row, token_stats_row]
    mock_db.fetchval.side_effect = [18, 20]  # total_votes, total_voters
    mock_db.fetch.return_value = []           # empty timeline

    r = client["client"].get("/elections/1/statistics")

    assert r.status_code == 200
    body = r.json()

    # Top-level keys
    assert "election" in body
    assert "statistics" in body
    assert "vote_timeline" in body

    # Election sub-dict
    assert body["election"]["title"] == "Test Election 2026"
    assert body["election"]["status"] == "closed"

    # Statistics sub-dict
    stats = body["statistics"]
    assert stats["total_votes"] == 18
    assert stats["total_voters"] == 20
    assert stats["total_tokens"] == 5
    assert stats["used_tokens"] == 3
    assert "turnout_rate" in stats

    # Timeline is a list (may be empty)
    assert isinstance(body["vote_timeline"], list)


def test_statistics_works_for_open_election(client, mock_db):
    """
    GET /statistics returns 200 regardless of election status.

    Unlike get_results and get_audit_trail, get_statistics has NO status
    check — it is designed to be polled during a live election to track
    participation. When status is 'open', the vote_timeline fetch is
    skipped (only runs for closed elections).
    """
    open_stats_row = {
        "title": "Live Election",
        "status": "open",
        "created_at": datetime.utcnow() - timedelta(days=1),
        "opened_at": datetime.utcnow() - timedelta(hours=6),
        "closed_at": None,
    }
    token_stats_row = {"total_tokens": 10, "used_tokens": 0}
    mock_db.fetchrow.side_effect = [open_stats_row, token_stats_row]
    mock_db.fetchval.side_effect = [0, 10]  # total_votes=0, total_voters=10
    # fetch is NOT called when status != "closed" — default [] is fine

    r = client["client"].get("/elections/1/statistics")

    assert r.status_code == 200
    body = r.json()
    assert body["election"]["status"] == "open"
    assert body["vote_timeline"] == []


def test_statistics_turnout_rate_calculated(client, mock_db, closed_election_row):
    """
    Turnout rate is correctly calculated as total_votes / total_voters * 100.

    18 votes, 20 voters → 90.0%
    """
    token_stats_row = {"total_tokens": 20, "used_tokens": 18}
    mock_db.fetchrow.side_effect = [closed_election_row, token_stats_row]
    mock_db.fetchval.side_effect = [18, 20]
    mock_db.fetch.return_value = []

    r = client["client"].get("/elections/1/statistics")

    assert r.status_code == 200
    assert r.json()["statistics"]["turnout_rate"] == 90.0


def test_statistics_zero_voters_no_division_error(client, mock_db,
                                                  closed_election_row):
    """
    When total_voters is 0 the turnout_rate is 0, not a ZeroDivisionError.

    app.py line 272:
        "turnout_rate": round(...) if total_voters > 0 else 0
    """
    token_stats_row = {"total_tokens": 0, "used_tokens": 0}
    mock_db.fetchrow.side_effect = [closed_election_row, token_stats_row]
    mock_db.fetchval.side_effect = [0, 0]
    mock_db.fetch.return_value = []

    r = client["client"].get("/elections/1/statistics")

    assert r.status_code == 200
    assert r.json()["statistics"]["turnout_rate"] == 0


def test_statistics_db_error_returns_500(client, mock_db):
    """Unhandled DB errors in get_statistics propagate as HTTP 500."""
    mock_db.fetchrow.side_effect = Exception("db connection lost")

    r = client["client"].get("/elections/1/statistics")

    assert r.status_code == 500


# =============================================================================
# Role permission documentation test
# =============================================================================

def test_results_service_role_is_read_only():
    """
    Documents that results_service DB role has SELECT on main tables,
    and SELECT + INSERT + UPDATE on tallied_votes only.

    This is a read-only filesystem test — no DB connection required.
    Reads uvote-platform/k8s/database/create_roles.sql and asserts the
    expected GRANT lines are present and no unexpected write grants exist
    for encrypted_ballots, elections, or election_options.

    Expected grants from create_roles.sql:
        GRANT SELECT ON encrypted_ballots, elections, election_options TO results_service;
        GRANT SELECT, INSERT, UPDATE ON tallied_votes TO results_service;
    """
    _project_root = Path(__file__).parent.parent.parent
    sql_path = _project_root / "uvote-platform" / "k8s" / "database" / "create_roles.sql"

    assert sql_path.exists(), f"create_roles.sql not found at {sql_path}"
    sql = sql_path.read_text()

    # SELECT-only grant on the three read-only tables
    assert (
        "GRANT SELECT ON encrypted_ballots, elections, election_options TO results_service"
        in sql
    ), "Expected SELECT-only grant on encrypted_ballots, elections, election_options"

    # tallied_votes has INSERT + UPDATE (for writing tally results)
    assert (
        "GRANT SELECT, INSERT, UPDATE ON tallied_votes" in sql
        and "results_service" in sql
    ), "Expected SELECT, INSERT, UPDATE grant on tallied_votes for results_service"

    # No INSERT or UPDATE grant directly on encrypted_ballots for results_service
    # (results_service may only read ballots, never write them)
    lines_with_results = [
        line for line in sql.splitlines()
        if "results_service" in line and "GRANT" in line
    ]
    for line in lines_with_results:
        if "encrypted_ballots" in line or "elections" in line or "election_options" in line:
            # The only grant touching these tables must be SELECT only
            assert "INSERT" not in line, (
                f"Unexpected INSERT grant for results_service on: {line!r}"
            )
            assert "UPDATE" not in line, (
                f"Unexpected UPDATE grant for results_service on: {line!r}"
            )
            assert "DELETE" not in line, (
                f"Unexpected DELETE grant for results_service on: {line!r}"
            )
