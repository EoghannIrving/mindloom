# Known Issues

1. **Vault directory** - `parse_projects.py` now creates the configured `vault/Projects` folder on demand and returns an empty list when no markdown files are present. Errors can still occur if the configured path already exists as a file or if the process lacks permission to create the directory, so double-check custom paths and filesystem permissions.
