# Mindloom

Mindloom is an offline-first personal assistant aimed at organizing projects and daily tasks. It parses project notes from an Obsidian vault and exposes a small FastAPI service. The long term vision is tracked in **Mindloom Roadmap.md**.

## Features
- Parse markdown project files from a configured vault directory.
- Store project metadata and summaries in `projects.yaml`.
- Convert each project checklist item into a task entry referencing its project
  in `data/tasks.yaml`.
- Parse task lines using the format `- [ ] Task description | due:2025-01-01 | recur:weekly`.
- Provide a `/projects` API endpoint with optional filters for status, area and effort.
- Trigger project parsing via the `/parse-projects` API endpoint or the web interface.
- Save tasks via the `/save-tasks` API endpoint or the web interface.
- Write modified tasks back to markdown via the `/write-tasks` API endpoint or the web interface.
- Retrieve saved tasks through the `/tasks` API endpoint.
- Mark tasks complete via the `/daily-tasks` web page.
- Edit all task fields via the `/manage-tasks` page.
- If `data/morning_plan.yaml` exists, `/daily-tasks` shows only tasks referenced
  by the latest morning plan.
- Task matching ignores punctuation so titles like `Check garden hose.` still
  match the plan text.
- Render prompt templates via the `/render-prompt` API or the web interface.
- Query ChatGPT via the `/ask` API endpoint.
- Generate a daily plan via the `/plan` API endpoint.
- Expand goals into tasks via the `/goal-breakdown` API endpoint.
- Record daily energy via the `/energy` API or `record_energy.py`.
- Request a single task suggestion via the `/suggest-task` endpoint when
  [ActivationEngine](https://github.com/EoghannIrving/ActivationEngine) is
  configured.
- Load calendar events from `.ics` files or Google Calendar into `data/calendar_cache.json`.
- View cached events on the `/calendar` page.
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

### Markdown task line format
Tasks in project files store optional metadata on the same line as the
description:

```
- [ ] Example task | due:2025-08-15 | recur:weekly | effort:med | energy:2 | last:2025-07-25 | exec:high
```

Rules:

- Start with `- [ ]` for incomplete or `- [x]` for completed tasks.
- The task description comes first.
- Metadata fields follow separated by `|` and use `key:value`.

Supported keys:

- `due` – due date in `YYYY-MM-DD` format
- `recur` – recurrence rule
- `effort` – estimated effort (`low`, `med`, `high`)
- `energy` – energy cost from 1–5
- `last` – date last completed
- `exec` – executive function demand (`low`, `med`, `high`)

## Setup
1. Install Python 3.10+.
2. Install dependencies with the pinned versions:
   ```bash
   pip install -r requirements.txt
   ```
   All packages including `python-dotenv`, `pydantic`, `pydantic-settings`, `PyYAML`, `fastapi`, `uvicorn`, `python-multipart`, `jinja2`, and `pytest` are version pinned. If you see import errors like `E0401`, ensure these packages are installed by running the above command.
3. Copy `example.env` to `.env` and edit the environment variables:
   - `OPENAI_API_KEY` for ChatGPT access.
   - `CALENDAR_ICS_PATH` path(s) to exported `.ics` files.
   - `TIME_ZONE` sets the IANA time zone for event parsing.
   - `ACTIVATION_ENGINE_URL` endpoint for the optional task suggestion service.
4. *(Optional)* Enable Google Calendar access:
   - Create a Google Cloud service account and enable the Calendar API.
   - Share your calendar with the service account's email address.
   - Download the service account credentials JSON and set `GOOGLE_CREDENTIALS_PATH` to its path.
   - Set `GOOGLE_CALENDAR_ID` to the ID of the calendar you shared.
   - When using Docker, mount the credentials file and update the path accordingly.
5. Ensure the vault directory exists and contains markdown project files.
6. Create a `data/logs` directory to persist logs:
   ```bash
   mkdir -p data/logs
   ```
7. If using GitHub Actions, install dependencies in your workflow before running linters:
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

Open `http://localhost:8000/` in a browser for a simple web interface to parse projects, record energy (including free time blocks) and render prompt templates. Visit `/daily-tasks` to check off today's tasks, `/manage-tasks` to edit them and `/calendar` to view loaded events.
The prompts section accepts optional JSON variables and automatically injects the contents of `data/tasks.yaml`, a `completed_tasks` list, and the latest energy entry. Selecting **morning_planner.txt** now renders the template automatically. Clicking **Ask** with that template chosen calls the `/plan` endpoint, writes `data/morning_plan.yaml` and takes you to `/daily-tasks`. Other templates still require clicking **Render** first and **Ask** sends the prompt to ChatGPT via `/ask`.
You can also query ChatGPT from the command line by posting a JSON payload with a `prompt` key to the `/ask` endpoint.

Generate a daily plan using incomplete tasks and today's energy entry. You can
optionally control how many tasks are recommended by passing an `intensity`
query parameter (`light`, `medium` or `full`):
```bash
curl -X POST 'http://localhost:8000/plan?intensity=full'
```
The response is stored in `data/morning_plan.yaml` and used to filter
`/daily-tasks`.
Tasks with an `energy_cost` higher than your latest logged energy are removed
before generating the plan. Task selection is performed with the
`prompts/plan_intensity_selector.txt` template based on the chosen intensity.

Break down a high-level goal into actionable tasks:
```bash
curl -X POST http://localhost:8000/goal-breakdown \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Write a blog post about AI"}'
```

Record today's energy, mood and free time blocks from the command line:
```bash
python record_energy.py 3 Joyful 8
```
Energy is scored 1-5 and mood accepts one of Sad, Meh, Okay or Joyful,
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
