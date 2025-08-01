"""API routes for recording daily energy, mood and free time blocks."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from energy import read_entries, record_entry
from config import config

router = APIRouter()

LOG_FILE = Path(config.LOG_DIR) / "energy_api.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class EnergyInput(BaseModel):  # pylint: disable=too-few-public-methods
    """Input model for energy submissions."""

    energy: int
    mood: str
    time_blocks: int


@router.post("/energy")
def add_energy(data: EnergyInput):
    """Record today's energy, mood and free time blocks."""
    logger.info(
        "POST /energy energy=%s mood=%s time_blocks=%s",
        data.energy,
        data.mood,
        data.time_blocks,
    )
    entry = record_entry(data.energy, data.mood, data.time_blocks)
    logger.info("Recorded entry: %s", entry)
    return entry


@router.get("/energy")
def get_energy():
    """Return all recorded energy entries."""
    logger.info("GET /energy")
    entries = read_entries()
    logger.info("Returning %d entries", len(entries))
    return entries
