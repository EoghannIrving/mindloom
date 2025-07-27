# Fixed Bugs

1. **Pydantic compatibility** - `config.py` relies on `BaseSettings` from Pydantic v1. `requirements.txt` now pins `pydantic<2` to avoid import errors with v2.
2. **Missing packages** - Added `fastapi` and `uvicorn` to `requirements.txt` so the API runs without extra installs.
3. **Import errors** - All dependencies are now version pinned in `requirements.txt` and the README instructs running `pip install -r requirements.txt` to resolve `E0401` errors.
