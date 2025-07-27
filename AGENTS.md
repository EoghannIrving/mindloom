# Development Guidelines

- Run `python -m py_compile $(git ls-files '*.py')` before committing to catch syntax errors.
- Format code with `black .` before committing. CI autoformats on each push.
- Keep commit messages short and descriptive.
- Update `README.md` when adding new commands or major functionality.
- Pin package versions in `requirements.txt` when compatibility issues arise.
- When resolving an item from `BUGS.md`, document the fix in `FIXED_BUGS.md`.
