# Known Issues

1. **Missing packages** - `fastapi` and `uvicorn` are required to run the API but are not listed in `requirements.txt`.
2. **Vault directory** - `parse_projects.py` expects a `vault/Projects` folder. If the directory does not exist the script fails.
