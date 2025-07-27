"""Simple web interface for Mindloom."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from config import config

router = APIRouter()

LOG_FILE = Path(config.LOG_DIR) / "web.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Mindloom</title>
</head>
<body>
  <h1>Mindloom Interface</h1>
  <h2>Parse Projects</h2>
  <button id=\"parseBtn\">Parse</button>
  <pre id=\"parseResult\"></pre>
  <h2>Record Energy</h2>
  <input type=\"number\" id=\"energy\" placeholder=\"Energy 1-10\">
  <input type=\"number\" id=\"mood\" placeholder=\"Mood 1-10\">
  <button id=\"recordBtn\">Record</button>
  <pre id=\"recordResult\"></pre>
  <h2>Data</h2>
  <button id=\"loadProjects\">Load Projects</button>
  <pre id=\"projects\"></pre>
  <button id=\"loadEnergy\">Load Energy</button>
  <pre id=\"energyData\"></pre>

<script>
const parseBtn = document.getElementById('parseBtn');
parseBtn.onclick = async () => {
  const res = await fetch('/parse-projects', {method: 'POST'});
  const data = await res.json();
  document.getElementById('parseResult').textContent = JSON.stringify(data);
};

const recordBtn = document.getElementById('recordBtn');
recordBtn.onclick = async () => {
  const payload = {
    energy: parseInt(document.getElementById('energy').value),
    mood: parseInt(document.getElementById('mood').value)
  };
  const res = await fetch('/energy', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  document.getElementById('recordResult').textContent = JSON.stringify(data);
};

document.getElementById('loadProjects').onclick = async () => {
  const res = await fetch('/projects');
  const data = await res.json();
  document.getElementById('projects').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('loadEnergy').onclick = async () => {
  const res = await fetch('/energy');
  const data = await res.json();
  document.getElementById('energyData').textContent = JSON.stringify(data, null, 2);
};
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def index():
    """Return the basic web interface."""
    logger.info("GET /")
    return HTMLResponse(content=INDEX_HTML)
