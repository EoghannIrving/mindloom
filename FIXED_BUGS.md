# Fixed Bugs

1. **Pydantic compatibility** - `config.py` relies on `BaseSettings` from Pydantic v1. `requirements.txt` now pins `pydantic<2` to avoid import errors with v2.
2. **Missing packages** - Added `fastapi` and `uvicorn` to `requirements.txt` so the API runs without extra installs.
