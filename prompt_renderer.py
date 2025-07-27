from pathlib import Path
from jinja2 import Template


def render_prompt(template_path: str, variables: dict) -> str:
    """Return a rendered prompt given a template path and variables."""
    template_text = Path(template_path).read_text()
    template = Template(template_text)
    return template.render(**variables)
