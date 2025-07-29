"""Utility for rendering Jinja templates used in the prompts."""

from pathlib import Path
from jinja2 import Environment, Template, meta


def render_prompt(template_path: str, variables: dict) -> str:
    """Return a rendered prompt given a template path and variables."""
    template_text = Path(template_path).read_text(encoding="utf-8")
    env = Environment()
    parsed = env.parse(template_text)
    required = meta.find_undeclared_variables(parsed)
    missing = required - variables.keys()
    if missing:
        raise KeyError(
            f"Missing variables for {template_path}: {', '.join(sorted(missing))}"
        )
    template = env.from_string(template_text)
    return template.render(**variables)
