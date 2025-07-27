"""FastAPI application entrypoint."""

from fastapi import FastAPI
import logging
from pathlib import Path

from routes import projects, energy, web
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
logger.info("Routers registered")
