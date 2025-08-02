# Fixed Bugs

1. **Pydantic compatibility** - Updated `config.py` to use `BaseSettings` from `pydantic-settings` so the project works with Pydantic v2.
2. **Missing packages** - Added `fastapi` and `uvicorn` to `requirements.txt` so the API runs without extra installs.
3. **Import errors** - All dependencies are now version pinned in `requirements.txt` and the README instructs running `pip install -r requirements.txt` to resolve `E0401` errors.
4. **Test imports** - Added `pytest` to `requirements.txt` and reorganized `tests/test_parse_projects.py` so linting no longer reports import errors.
5. **Prompt variables** - The web interface now includes a JSON textarea so prompts render with provided variables instead of blanks.
6. **OpenAI client closure** - `ask_chatgpt` now uses an async context manager to close `AsyncOpenAI` and avoid connection leaks.
7. **HTTPX compatibility** - Pinned `httpx<0.27` in `requirements.txt` to fix `AsyncClient.__init__()` errors triggered by OpenAI's proxy handling.
8. **Vault directory** - `parse_projects.parse_all_projects` now creates the vault path and returns an empty list when it doesn't exist.
9. **Custom task path** - `tasks.write_tasks` ensures the destination directory is created before writing.
10. **Morning planner tasks** - `index.html` no longer sends the full task list when rendering `morning_planner.txt`, so the backend injects only overdue or soon-due items.
11. **Unknown environment variables** - `config.py` now ignores extraneous keys like `timezone` to avoid `ValidationError` during startup.
