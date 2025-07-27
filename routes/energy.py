"""API routes for recording daily energy and mood."""

from fastapi import APIRouter
from pydantic import BaseModel

from energy import read_entries, record_entry

router = APIRouter()


class EnergyInput(BaseModel):
    """Input model for energy submissions."""

    energy: int
    mood: int


@router.post("/energy")
def add_energy(data: EnergyInput):
    """Record today's energy and mood."""
    return record_entry(data.energy, data.mood)


@router.get("/energy")
def get_energy():
    """Return all recorded energy entries."""
    return read_entries()
