from __future__ import annotations

from pathlib import Path


def normalize_slug_path(slug: str, vault_root: Path) -> Path:
    """Normalize a slug to a relative path under the vault root."""

    slug_path = Path(slug)
    if slug_path.is_absolute():
        raise ValueError("slug must be a relative path without traversal")

    parts: list[str] = []
    for part in slug_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("slug must be a relative path without traversal")
        parts.append(part)

    if not parts:
        raise ValueError("slug must reference a file within the vault")

    vault_parts = [p for p in vault_root.parts if p not in {"", "/"}]
    prefix_length = len(vault_parts)
    while (
        prefix_length
        and len(parts) >= prefix_length
        and parts[:prefix_length] == vault_parts
    ):
        parts = parts[prefix_length:]

    root_name = vault_root.name
    while root_name and parts and parts[0] == root_name:
        parts = parts[1:]

    normalized = Path(*parts)
    if normalized.suffix != ".md":
        normalized = normalized.with_suffix(".md")

    return normalized


def resolve_slug_path(slug: str, vault_root: Path) -> Path:
    """Return the filesystem path for a slug within the vault."""

    normalized = normalize_slug_path(slug, vault_root)
    candidate = (vault_root / normalized).resolve()
    try:
        candidate.relative_to(vault_root)
    except ValueError as exc:
        raise ValueError("slug must resolve within the vault") from exc
    return candidate
