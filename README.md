# Mindloom

Mindloom is an offline-first personal assistant aimed at organizing projects and daily tasks. It parses project notes from an Obsidian vault and exposes a small FastAPI service. The long term vision is tracked in **Mindloom Roadmap.md**.

## Features
- Parse markdown project files from a configured vault directory.
- Store project metadata and summaries in `projects.yaml`.
- Provide a `/projects` API endpoint with optional filters for status, area and effort.
- Trigger project parsing via the `/parse-projects` API endpoint or the web interface.
- Containerized setup using Docker and docker-compose.

## Setup
1. Install Python 3.10+.
2. Install dependencies with the pinned versions:
   ```bash
   pip install -r requirements.txt
   ```
   All packages including `python-dotenv`, `pydantic`, `pydantic-settings`, `PyYAML`, `fastapi`, `uvicorn`, and `pytest` are version pinned. If you see import errors like `E0401`, ensure these packages are installed by running the above command.
3. Create a `.env` file if you need to override paths or API keys. `VAULT_PATH` defaults to `vault/Projects`.
4. Ensure the vault directory exists and contains markdown project files.
5. Create a `data` directory to persist logs:
   ```bash
   mkdir -p data
   ```
6. If using GitHub Actions, install dependencies in your workflow before running linters:
   ```yaml
   - name: Install dependencies
     run: |
       python -m pip install --upgrade pip
       pip install pylint
       if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
   ```

## Usage
Parse the projects and start the API:
```bash
python parse_projects.py
uvicorn main:app --reload
```
The script writes detailed logs to `data/parse_projects.log`.
The service runs on `http://localhost:8000` by default.

Open `http://localhost:8000/` in a browser for a simple web interface to parse projects and record energy.

Record today's energy and mood from the command line:
```bash
python record_energy.py 7 8
```
Energy entries are stored in `data/energy_log.yaml`.

## Development
Pushes and pull requests run automated checks on GitHub Actions. Formatting is
verified with **Black**, linting with Pylint and Flake8, and tests are executed
with Pytest. To avoid CI failures, format your code locally before committing:
```bash
black .
```

## Roadmap
See [Mindloom Roadmap.md](Mindloom%20Roadmap.md) for planned phases and upcoming features.

## License
This project is licensed under the GNU General Public License v3.0.
