"""Tests for the prompt rendering utilities."""

from pathlib import Path
import pytest

from prompt_renderer import render_prompt


def test_render_prompt_missing_vars(tmp_path: Path):
    """Renderer should raise if required variables are absent."""
    tpl = tmp_path / "demo.txt"
    tpl.write_text("Hello {{name}} {{value}}", encoding="utf-8")
    with pytest.raises(KeyError):
        render_prompt(str(tpl), {"name": "John"})


def test_render_prompt_success(tmp_path: Path):
    """Renderer should fill variables correctly."""
    tpl = tmp_path / "demo.txt"
    tpl.write_text("Hello {{name}}", encoding="utf-8")
    result = render_prompt(str(tpl), {"name": "Ada"})
    assert result == "Hello Ada"
