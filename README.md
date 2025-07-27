# Mindloom

Mindloom is an offline-first personal assistant aimed at organizing projects and daily tasks. It parses project notes from an Obsidian vault and exposes a small FastAPI service. The long term vision is tracked in **Mindloom Roadmap.md**.

## Features
- Parse markdown project files from a configured vault directory.
- Store project metadata and summaries in `projects.yaml`.
- Provide a `/projects` API endpoint with optional filters for status, area and effort.
- Containerized setup using Docker and docker-compose.

## Setup
1. Install Python 3.10+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install fastapi uvicorn
   ```
   `pydantic<2` is pinned in `requirements.txt` to ensure compatibility with Pydantic v1.
3. Create a `.env` file if you need to override paths or API keys. `VAULT_PATH` defaults to `vault/Projects`.
4. Ensure the vault directory exists and contains markdown project files.

## Usage
Parse the projects and start the API:
```bash
python parse_projects.py
uvicorn main:app --reload
```
The service runs on `http://localhost:8000` by default.

## Roadmap
See [Mindloom Roadmap.md](Mindloom%20Roadmap.md) for planned phases and upcoming features.

## License
This project is licensed under the GNU General Public License v3.0.
