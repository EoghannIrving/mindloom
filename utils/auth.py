"""Simple API key dependency for write endpoints."""

from fastapi import Depends, Header, HTTPException, Query, status

from config import config


def require_api_key(
    api_key_header: str | None = Header(None, alias="X-API-Key"),
    api_key_query: str | None = Query(None, alias="api_key"),
) -> None:
    """Enforce the configured API key when one is set.

    - Skips enforcement when ``config.API_KEY`` is empty (default).
    - Accepts either the ``X-API-Key`` header or an ``api_key`` query parameter.
    - Raises HTTP 401 when no valid key is provided.
    """

    expected = (config.API_KEY or "").strip()
    if not expected:
        return

    provided = (api_key_header or api_key_query or "").strip()
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


# Shallow dependency wrapper to simplify reuse.
def enforce_api_key(_: None = Depends(require_api_key)) -> None:
    """Dependency wrapper to attach to route signatures."""

    return None
