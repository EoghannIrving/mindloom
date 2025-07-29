"""FastAPI application entrypoint."""

# pylint: disable=duplicate-code

import logging
from pathlib import Path
from fastapi import FastAPI

from routes import projects, energy, web, openai_route, tasks_page
from config import config

LOG_FILE = Path(config.LOG_DIR) / "server.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.info("Initializing FastAPI app")
app = FastAPI()
app.include_router(projects.router)
app.include_router(energy.router)
app.include_router(web.router)
app.include_router(openai_route.router)
app.include_router(tasks_page.router)
logger.info("Routers registered")
