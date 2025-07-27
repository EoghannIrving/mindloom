"""Unit tests for the project parsing utilities."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import parse_projects
from parse_projects import (
    extract_frontmatter,
    extract_tasks,
    summarize_body,
    parse_markdown_file,
)


def test_extract_frontmatter():
    """Ensure YAML frontmatter is parsed correctly."""
    md = textwrap.dedent(
        """---
status: active
area: work
effort: high
---
Body text
"""
    )
    frontmatter, body = extract_frontmatter(md)
    assert frontmatter == {"status": "active", "area": "work", "effort": "high"}
    assert body == "Body text"


def test_extract_tasks():
    """Extract markdown tasks from the body."""
    body = textwrap.dedent(
        """- [ ] Task one
- [x] Task two
Other line
"""
    )
    tasks = extract_tasks(body)
    assert tasks == ["- [ ] Task one", "- [x] Task two"]


def test_summarize_body():
    """Summarize the body by returning the first paragraph."""
    text = textwrap.dedent(
        """# Heading
Paragraph one.

> quoted text

Paragraph two.
"""
    )
    assert summarize_body(text) == "Paragraph one."


def test_parse_markdown_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Parse a markdown file and return expected metadata."""
    md_content = textwrap.dedent(
        """---
status: active
---
Some body
- [ ] Task
"""
    )
    md_file = tmp_path / "example.md"
    md_file.write_text(md_content, encoding="utf-8")

    # patch PROJECTS_DIR so relative path calculation works
    monkeypatch.setattr(parse_projects, "PROJECTS_DIR", tmp_path)
    result = parse_markdown_file(md_file)

    assert result["title"] == "example"
    assert result["status"] == "active"
    assert result["tasks"] == ["- [ ] Task"]
