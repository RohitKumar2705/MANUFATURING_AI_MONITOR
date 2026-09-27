"""
Basic admin authentication (spec section 57).

Protects camera/worker/process/rule configuration endpoints. Dashboard
viewing itself is left open for the demo (a real deployment would put the
whole app behind auth/SSO). Password is stored only as a bcrypt hash
(never plaintext) - using the `bcrypt` library directly rather than
passlib, which has known version-compatibility issues with recent bcrypt
releases.
"""
from __future__ import annotations
import bcrypt
from fastapi import Request, HTTPException, status
from app.core.config import settings

# The default is for local demo use; production deployments should set
# ADMIN_PASSWORD as an environment variable.
DEFAULT_PASSWORD_HASH = bcrypt.hashpw(settings.admin_password.encode("utf-8"), bcrypt.gensalt())


def verify_login(username: str, password: str) -> bool:
    if username != settings.admin_username:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), DEFAULT_PASSWORD_HASH)
    except Exception:
        return False


def require_admin(request: Request):
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")
    return True


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("is_admin"))
