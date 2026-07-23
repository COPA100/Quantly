from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from common.config import get_settings


class GoogleAuthError(Exception):
    """raised when a google id token fails verification."""


def verify_google_id_token(token: str) -> dict:
    # checks google's signature, audience (our client id), issuer, and expiry
    settings = get_settings()
    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.google_client_id
        )
    except ValueError as exc:
        raise GoogleAuthError("invalid google token") from exc
    # only trust the email if google says it is verified
    if not claims.get("email_verified"):
        raise GoogleAuthError("google email not verified")
    return claims
