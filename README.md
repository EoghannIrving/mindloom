# Mindloom

Mindloom is an offline-first personal assistant aimed at organizing projects and daily tasks. It parses project notes from an Obsidian vault and exposes a small FastAPI service. The long term vision is tracked in **Mindloom Roadmap.md**.

## Features
- Parse markdown project files from a configured vault directory.
- Store project metadata and summaries in `projects.yaml`.
- Convert each project checklist item into a task entry referencing its project
  in `data/tasks.yaml`.
- Parse inline `Due Date: YYYY-MM-DD` and `Recurrence: interval` markers from
  each task line.
- Provide a `/projects` API endpoint with optional filters for status, area and effort.
- Trigger project parsing via the `/parse-projects` API endpoint or the web interface.
- Save tasks via the `/save-tasks` API endpoint or the web interface.
- Write modified tasks back to markdown via the `/write-tasks` API endpoint or the web interface.
- Retrieve saved tasks through the `/tasks` API endpoint.
- Mark tasks complete via the `/daily-tasks` web page.
- Edit task recurrence, due dates and completion via the `/manage-tasks` page.
- If `data/morning_plan.txt` exists, `/daily-tasks` shows only tasks referenced
  by the latest morning plan.
- Task matching ignores punctuation so titles like `Check garden hose.` still
  match the plan text.
- Render prompt templates via the `/render-prompt` API or the web interface.
- Query ChatGPT via the `/ask` API endpoint.
- Generate a daily plan via the `/plan` API endpoint.
- Expand goals into tasks via the `/goal-breakdown` API endpoint.
- Record daily energy via the `/energy` API or `record_energy.py`.
- Containerized setup using Docker and docker-compose.
- **Planned**: flexible input modes (voice, image capture, quick log) after the UI milestone.

## Task schema
Tasks are stored in `data/tasks.yaml` with the following fields:

- `id`
- `title`
- `project`
- `area`
- `type`
- `due`
- `recurrence`
- `effort`
- `energy_cost`
- `status`
- `last_completed`
- `executive_trigger`
- `next_due` (computed)
- `due_today` (computed)

Recurring tasks populate `next_due` and `due_today` based on the
`recurrence` interval and the `last_completed` date.

### Field definitions

- **effort** – rough estimate of complexity or time commitment (`low`, `medium`, `high`).
- **energy_cost** – numeric 1–5 rating of how taxing the task will be for the individual.
- **executive_trigger** – tasks that are high_friction starts.
- **project** – path of the project this task originated from.

_A future update will add `activation_difficulty` for high-friction starts._

## Setup
1. Install Python 3.10+.
2. Install dependencies with the pinned versions:
   ```bash
   pip install -r requirements.txt
   ```
   All packages including `python-dotenv`, `pydantic`, `pydantic-settings`, `PyYAML`, `fastapi`, `uvicorn`, `python-multipart`, `jinja2`, and `pytest` are version pinned. If you see import errors like `E0401`, ensure these packages are installed by running the above command.
3. Copy `example.env` to `.env` and set `OPENAI_API_KEY` for ChatGPT access. `VAULT_PATH` defaults to `/vault/Projects` when that folder exists, otherwise `vault/Projects` relative to the project root. Paths containing `~` are expanded to your home directory.
4. Ensure the vault directory exists and contains markdown project files.
5. Create a `data/logs` directory to persist logs:
   ```bash
   mkdir -p data/logs
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
The script writes detailed logs to `data/logs/parse_projects.log`.
Other components log to files in the `data/logs` directory as well.
The service runs on `http://localhost:8000` by default.

Open `http://localhost:8000/` in a browser for a simple web interface to parse projects, record energy (including free time blocks) and render prompt templates. Visit `/daily-tasks` to check off today's tasks. Use `/manage-tasks` to edit due dates or recurrence settings.
The prompts section accepts optional JSON variables and automatically injects the contents of `data/tasks.yaml`, a `completed_tasks` list, and the latest energy entry. Selecting **morning_planner.txt** now renders the template automatically. Clicking **Ask** with that template chosen calls the `/plan` endpoint, writes `data/morning_plan.txt` and takes you to `/daily-tasks`. Other templates still require clicking **Render** first and **Ask** sends the prompt to ChatGPT via `/ask`.
You can also query ChatGPT from the command line by posting a JSON payload with a `prompt` key to the `/ask` endpoint.

Generate a daily plan using incomplete tasks and today's energy entry:
```bash
curl -X POST http://localhost:8000/plan
```
The response is stored in `data/morning_plan.txt` and used to filter
`/daily-tasks`.

Break down a high-level goal into actionable tasks:
```bash
curl -X POST http://localhost:8000/goal-breakdown \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Write a blog post about AI"}'
```

Record today's energy, mood and free time blocks from the command line:
```bash
python record_energy.py 3 Upbeat 8
```
Energy is scored 1-5, mood accepts one of Focused, Tired, Flat, Anxious or Upbeat,
and the final argument specifies how many 15-minute blocks of free time you have.
Energy entries are stored in `data/energy_log.yaml`.
Recording again on the same day will update the existing entry instead of adding a new one.

## Development
Pushes and pull requests run automated checks on GitHub Actions. Formatting is
verified with **Black**, linting with Pylint and Flake8, and tests are executed
with Pytest. To avoid CI failures, format your code locally before committing:

```bash
black .
pytest -q
```


## Roadmap
See [Mindloom Roadmap.md](Mindloom%20Roadmap.md) for planned phases and upcoming features.

## License
This project is licensed under the GNU General Public License v3.0.
