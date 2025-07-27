# Fixed Bugs

1. **Pydantic compatibility** - Updated `config.py` to use `BaseSettings` from `pydantic-settings` so the project works with Pydantic v2.
2. **Missing packages** - Added `fastapi` and `uvicorn` to `requirements.txt` so the API runs without extra installs.
3. **Import errors** - All dependencies are now version pinned in `requirements.txt` and the README instructs running `pip install -r requirements.txt` to resolve `E0401` errors.
