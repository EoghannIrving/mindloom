"""Routes for ActivationEngine task suggestions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import httpx
from fastapi import APIRouter

from config import config
from tasks import read_tasks
from energy import read_entries

router = APIRouter()

LOG_FILE = Path(config.LOG_DIR) / "activation.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


async def _call_activation_engine(payload: dict) -> List[dict]:
    """Return ranked tasks from the ActivationEngine service."""
    if not config.ACTIVATION_ENGINE_URL:
        return []
    url = f"{config.ACTIVATION_ENGINE_URL.rstrip('/')}/rank-tasks"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    candidates = data.get("candidates")
    return candidates if isinstance(candidates, list) else []


@router.get("/suggest-task")
async def suggest_task():
    """Return the highest ranked task from ActivationEngine."""
    logger.info("GET /suggest-task")
    tasks = [t for t in read_tasks() if t.get("status") != "complete"]
    entries = read_entries()
    latest = entries[-1] if entries else {}
    payload = {
        "tasks": [
            {
                "name": t.get("title", ""),
                "project": t.get("project", "task"),
                "effort": t.get("effort"),
                "energy_cost": t.get("energy_cost"),
                "executive_cost": t.get("executive_trigger"),
            }
            for t in tasks
        ],
        "user_state": {
            "energy": int(latest.get("energy", 3)),
            "mood": latest.get("mood"),
            "context": None,
        },
    }
    try:
        candidates = await _call_activation_engine(payload)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("ActivationEngine request failed: %s", exc)
        return {"error": "An internal error has occurred."}
    return {"suggestion": candidates[0] if candidates else None}
