"""Admin login, rate limiting, and privacy for the public demo dashboard."""

import re
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app import config

# ---------------------------------------------------------------- admin auth

# token -> role. "admin" can change things; "viewer" (the public demo login) can only look.
_tokens: dict[str, str] = {}


def login(password: str) -> tuple[str, str] | None:
    """Returns (role, token), or None if the password is wrong."""
    if config.ADMIN_PASSWORD and secrets.compare_digest(password, config.ADMIN_PASSWORD):
        role = "admin"
    elif secrets.compare_digest(password, config.DEMO_PASSWORD):
        role = "viewer"
    else:
        return None
    token = secrets.token_urlsafe(32)
    _tokens[token] = role
    return role, token


def _role(authorization: str | None) -> str:
    token = (authorization or "").removeprefix("Bearer ").strip()
    role = _tokens.get(token)
    if not role:
        raise HTTPException(401, "Please log in again")
    return role


def require_viewer(authorization: str | None = Header(default=None)) -> str:
    return _role(authorization)


def require_admin(authorization: str | None = Header(default=None)) -> str:
    if _role(authorization) != "admin":
        raise HTTPException(403, "Read-only demo account: changes are disabled")
    return "admin"


# ---------------------------------------------------------------- rate limiting

_hits: dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def check_rate(request: Request, bucket: str = "chat") -> None:
    key = f"{bucket}:{client_ip(request)}"
    now = time.monotonic()
    with _rate_lock:
        window = _hits[key]
        while window and now - window[0] > config.RATE_LIMIT_WINDOW:
            window.popleft()
        if len(window) >= config.RATE_LIMIT_MESSAGES:
            raise HTTPException(429, "Trop de messages, réessayez dans quelques minutes.")
        window.append(now)


# ---------------------------------------------------------------- privacy

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\s.-]?){8,}\d")


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain[:1]}•••"


def redact(text: str | None) -> str | None:
    """What demo viewers see: visitors' emails and phone numbers hidden."""
    if not text:
        return text
    text = EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    return PHONE_RE.sub("•• •• •• •• ••", text)
