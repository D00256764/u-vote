"""
MailHog test helper — query the MailHog HTTP API and extract voting token URLs.

Used by the test suite to retrieve voting tokens from captured emails instead
of inserting them directly into the database via psql.

MailHog must be running and accessible at MAILHOG_API before calling any
function in this module. In the Kubernetes cluster, open a port-forward first:
  kubectl port-forward svc/mailhog 8025:8025 -n uvote-dev
"""
import httpx

MAILHOG_API = "http://localhost:8025/api/v2/messages"


async def get_latest_voting_token(voter_email: str) -> str:
    """
    Query the MailHog API, find the most recent email sent to voter_email,
    and extract the voting token from the /vote/{token} URL in the body.

    The voter-service sends emails containing a URL in the format:
      {FRONTEND_URL}/vote/{token}

    There is no OTP — the token embedded in the URL IS the credential.

    Args:
        voter_email: The email address the token was sent to.

    Returns:
        The voting token string extracted from the URL.

    Raises:
        AssertionError: If no email is found for voter_email in MailHog,
                        or if no /vote/{token} URL can be extracted from
                        the email body.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(MAILHOG_API)
        response.raise_for_status()

    data = response.json()
    messages = data.get("items", [])

    if not messages:
        raise AssertionError(
            f"MailHog inbox is empty — no emails captured. "
            f"Expected email for {voter_email}."
        )

    for msg in messages:
        recipients = [
            r["Mailbox"] + "@" + r["Domain"]
            for r in msg.get("To", [])
        ]
        if voter_email in recipients:
            body = msg["Content"]["Body"]
            if "/vote/" not in body:
                raise AssertionError(
                    f"Email found for {voter_email} but body contains no "
                    f"/vote/{{token}} URL. Body preview: {body[:200]}"
                )
            token = body.split("/vote/")[1].split('"')[0].strip()
            if not token:
                raise AssertionError(
                    f"Found /vote/ in email body for {voter_email} but "
                    f"could not extract token. Body preview: {body[:200]}"
                )
            return token

    raise AssertionError(
        f"No email found for {voter_email} in MailHog. "
        f"Found {len(messages)} message(s) addressed to: "
        + ", ".join(
            r["Mailbox"] + "@" + r["Domain"]
            for msg in messages
            for r in msg.get("To", [])
        )
    )


async def delete_all_messages() -> None:
    """
    Delete all messages from the MailHog inbox.

    Call this after extracting a token to keep the inbox clean between
    test runs and prevent stale emails from interfering with future lookups.
    """
    async with httpx.AsyncClient() as client:
        response = await client.delete("http://localhost:8025/api/v1/messages")
        response.raise_for_status()
