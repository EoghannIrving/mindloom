from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.routing import NoMatchFound

from config import PROJECT_ROOT


def static_url(request: Request, path: str) -> str:
    """Resolve the static asset URL, falling back to the /static prefix when needed."""

    clean_path = path.lstrip("/")
    try:
        resolved = request.url_for("static", path=path)
        return resolved.path or f"/static/{clean_path}"
    except NoMatchFound:
        return f"/static/{clean_path}"


def create_templates() -> Jinja2Templates:
    """Return a Jinja2Templates instance preconfigured with helpers."""

    templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")
    templates.env.globals["static_url"] = static_url
    return templates
