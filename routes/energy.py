"""API routes for recording daily energy and mood."""

# pylint: disable=duplicate-code

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from energy import read_entries, record_entry
from config import config
from utils.logging import configure_logger
from utils.auth import enforce_api_key

router = APIRouter()

LOG_FILE = Path(config.LOG_DIR) / "energy_api.log"
logger = configure_logger(__name__, LOG_FILE)


class EnergyInput(BaseModel):  # pylint: disable=too-few-public-methods
    """Input model for energy submissions."""

    energy: int
    mood: str


@router.post("/energy")
def add_energy(data: EnergyInput, _: None = Depends(enforce_api_key)):
    """Record today's energy and mood."""
    logger.info("POST /energy payload_received")
    entry = record_entry(data.energy, data.mood)
    logger.info("Recorded energy entry for date=%s", entry.get("date"))
    logger.debug("Recorded energy entry details: %s", entry)
    return entry


@router.get("/energy")
def get_energy():
    """Return all recorded energy entries."""
    logger.info("GET /energy")
    entries = read_entries()
    logger.info("Returning %d entries", len(entries))
    return entries
