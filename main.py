"""FastAPI application entrypoint."""

from fastapi import FastAPI
from routes import projects, energy, web

app = FastAPI()
app.include_router(projects.router)
app.include_router(energy.router)
app.include_router(web.router)
