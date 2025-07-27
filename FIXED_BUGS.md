# Fixed Bugs

1. **Pydantic compatibility** - Updated `config.py` to use `BaseSettings` from `pydantic-settings` so the project works with Pydantic v2.
2. **Missing packages** - Added `fastapi` and `uvicorn` to `requirements.txt` so the API runs without extra installs.
3. **Import errors** - All dependencies are now version pinned in `requirements.txt` and the README instructs running `pip install -r requirements.txt` to resolve `E0401` errors.
4. **Test imports** - Added `pytest` to `requirements.txt` and reorganized `tests/test_parse_projects.py` so linting no longer reports import errors.
