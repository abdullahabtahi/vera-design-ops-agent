"""Firebase ID token verification — FastAPI dependency.

Usage:
    @app.post("/api/chat")
    async def chat(req: ChatRequest, uid: str = Depends(require_auth)):
        # uid is the verified Firebase UID
        ...

Set AUTH_REQUIRED=false in .env to skip verification in local dev
(e.g. when running `adk web .` without a browser sign-in).
"""
from __future__ import annotations

import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

_firebase_app = None
_firebase_init_attempted = False


def _init_firebase() -> bool:
    """Initialise firebase-admin once. Returns True if ready."""
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app is not None
    _firebase_init_attempted = True

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            # Cloud Run: use the service account attached to the instance
            _firebase_app = firebase_admin.initialize_app()

        logger.info("Firebase Admin SDK initialised")
        return True
    except Exception as exc:
        logger.warning("Firebase Admin init failed — auth will be unavailable: %s", exc)
        return False


async def require_auth(authorization: str | None = Header(default=None)) -> str:
    """
    FastAPI dependency: validates a Firebase ID token from the Authorization header.

    Returns the verified Firebase UID on success.
    Raises HTTP 401 if the token is missing or invalid.

    Bypass: set AUTH_REQUIRED=false in .env for local dev / ADK playground.
    """
    from config import settings

    if not settings.auth_required:
        # Dev bypass — return a stable placeholder UID so session keying works
        return "dev-user"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    if not _init_firebase():
        logger.error("Firebase Admin not initialised — cannot verify token")
        raise HTTPException(status_code=503, detail="Authentication service unavailable")

    try:
        import firebase_admin.auth as fb_auth
        decoded = fb_auth.verify_id_token(token, check_revoked=True)
        return str(decoded["uid"])
    except Exception as exc:
        logger.warning("Token verification failed: %s", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
