# Known Issues

1. **Vault directory** - `parse_projects.py` expects a `vault/Projects` folder. If the directory does not exist the script fails.
2. **OpenAI client not closed** - `openai_client.ask_chatgpt` instantiates `AsyncOpenAI` but never closes it which can leak connections.
3. **Custom task path** - `tasks.write_tasks` assumes the target directory exists when given a custom path.
