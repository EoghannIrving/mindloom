# Known Issues

1. **Pydantic compatibility** - `config.py` relies on `BaseSettings` from Pydantic v1. Installing Pydantic v2 raises `PydanticImportError`. Pin `pydantic<2` or update the code.
2. **Missing packages** - `fastapi` and `uvicorn` are required to run the API but are not listed in `requirements.txt`.
3. **Vault directory** - `parse_projects.py` expects a `vault/Projects` folder. If the directory does not exist the script fails.
