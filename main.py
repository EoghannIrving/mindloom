"""FastAPI application entrypoint."""

from fastapi import FastAPI
from routes import projects, energy

app = FastAPI()
app.include_router(projects.router)
app.include_router(energy.router)
