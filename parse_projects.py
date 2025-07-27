import re
import yaml
from pathlib import Path
from config import config

PROJECTS_DIR = config.VAULT_PATH
OUTPUT_FILE = config.OUTPUT_PATH
VALID_KEYS = {"status", "area", "effort", "due"}

def extract_frontmatter(text):
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                front = yaml.safe_load(text[3:end])
                return {k: front.get(k) for k in VALID_KEYS if k in front}, text[end+3:].strip()
            except yaml.YAMLError:
                pass
    return {}, text

def extract_tasks(text):
    return re.findall(r"- \[[ xX]\] .+", text)

def summarize_body(text, max_chars=300):
    body = re.sub(r"#+ .*", "", text)
    body = re.sub(r"> .*", "", body)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return paras[0][:max_chars] if paras else ""

def parse_markdown_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    frontmatter, body = extract_frontmatter(content)
    tasks = extract_tasks(body)
    summary = summarize_body(body)
    return {
        "title": filepath.stem,
        "path": str(filepath.relative_to(PROJECTS_DIR.parent)),
        **frontmatter,
        "tasks": tasks,
        "summary": summary
    }

def parse_all_projects(root=PROJECTS_DIR):
    return [parse_markdown_file(md) for md in root.rglob("*.md")]

if __name__ == "__main__":
    all_projects = parse_all_projects()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(all_projects, f, sort_keys=False, allow_unicode=True)
