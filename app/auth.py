"""Simple admin cookie authentication helpers."""

import hashlib
import hmac
import os

from fastapi import Request

ADMIN_COOKIE_NAME = "track_number_admin"
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "track-number-demo-secret")


def verify_password(password: str, stored_password: str) -> bool:
    """Check a plain password against the stored admin password."""
    if "$" not in stored_password:
        return hmac.compare_digest(password, stored_password)

    salt, password_hash = stored_password.split("$", 1)
    entered_hash = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(entered_hash, password_hash)


def create_admin_cookie(username: str) -> str:
    """Create a signed cookie value for an admin username."""
    signature = hmac.new(
        ADMIN_SECRET_KEY.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{username}:{signature}"


def is_admin_request(request: Request) -> bool:
    """Return True when the request has a valid admin cookie."""
    cookie_value = request.cookies.get(ADMIN_COOKIE_NAME)
    if not cookie_value or ":" not in cookie_value:
        return False

    username, signature = cookie_value.rsplit(":", 1)
    expected_cookie = create_admin_cookie(username)
    return hmac.compare_digest(cookie_value, expected_cookie)
