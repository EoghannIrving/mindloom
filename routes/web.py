"""Simple web interface for Mindloom."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

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
    return HTMLResponse(content=INDEX_HTML)
