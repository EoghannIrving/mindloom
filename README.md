# Mindloom

Mindloom is an offline-first personal assistant aimed at organizing projects and daily tasks. It parses project notes from an Obsidian vault and exposes a small FastAPI service. The long term vision is tracked in **Mindloom Roadmap.md**.

## Features
- Parse markdown project files from a configured vault directory.
- Store project metadata and summaries in `projects.yaml`.
- Convert parsed projects into task entries saved in `data/tasks.yml`.
- Provide a `/projects` API endpoint with optional filters for status, area and effort.
- Trigger project parsing via the `/parse-projects` API endpoint or the web interface.
- Save tasks via the `/save-tasks` API endpoint or the web interface.
- Retrieve saved tasks through the `/tasks` API endpoint.
- Render prompt templates via the `/render-prompt` API or the web interface.
- Containerized setup using Docker and docker-compose.

## Setup
1. Install Python 3.10+.
2. Install dependencies with the pinned versions:
   ```bash
   pip install -r requirements.txt
   ```
   All packages including `python-dotenv`, `pydantic`, `pydantic-settings`, `PyYAML`, `fastapi`, `uvicorn`, `jinja2`, and `pytest` are version pinned. If you see import errors like `E0401`, ensure these packages are installed by running the above command.
3. Create a `.env` file if you need to override paths or API keys. `VAULT_PATH` defaults to `/vault/Projects` when that folder exists, otherwise `vault/Projects` relative to the project root. Paths containing `~` are expanded to your home directory.
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
Other components log to files in the `data` directory as well.
The service runs on `http://localhost:8000` by default.

Open `http://localhost:8000/` in a browser for a simple web interface to parse projects, record energy (including free hours) and render prompt templates.
The prompts section accepts optional JSON variables and automatically injects the contents of `data/tasks.yml` when rendering. Enter additional variables in the textarea next to the dropdown, then click **Render** to see the filled template.

Record today's energy, mood and free hours from the command line:
```bash
python record_energy.py 3 Upbeat 2
```
Energy is scored 1-5, mood accepts one of Focused, Tired, Flat, Anxious or Upbeat,
and the final argument specifies how many hours of free time you have.
Energy entries are stored in `data/energy_log.yaml`.
Recording again on the same day will update the existing entry instead of adding a new one.

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
