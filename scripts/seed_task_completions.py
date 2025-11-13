#!/usr/bin/env python3
"""Seed the task completion log from existing task metadata."""

from pathlib import Path
import sys

import yaml

from config import config
from tasks import read_tasks, task_completion_history


def main() -> int:
    """Rebuild the completion log file based on task history."""

    target = Path(config.TASK_COMPLETIONS_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    history = task_completion_history(tasks_list=read_tasks(), path=target)
    with open(target, "w", encoding="utf-8") as handle:
        yaml.dump(history, handle, sort_keys=False, allow_unicode=True)
    print(f"Wrote {len(history)} completion entries to {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
