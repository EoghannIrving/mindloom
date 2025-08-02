"""Application configuration handled via environment variables."""

# pylint: disable=invalid-name, arguments-differ

from pathlib import Path
from typing import ClassVar
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# === Load .env and .env.local (if exists) ===
load_dotenv(dotenv_path=".env")
if Path(".env.local").exists():
    load_dotenv(dotenv_path=".env.local", override=True)

# === Dynamically detect project root ===
PROJECT_ROOT = Path(__file__).resolve().parent


class Config(BaseSettings):  # pylint: disable=too-few-public-methods
    """Centralized application settings."""

    # === General ===
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    PORT: int = Field(8000, env="PORT")

    # === Paths ===
    DEFAULT_VAULT: ClassVar[Path] = (
        Path("/vault/Projects")
        if Path("/vault/Projects").exists()
        else PROJECT_ROOT / "vault/Projects"
    )
    VAULT_PATH: Path = Field(DEFAULT_VAULT, env="VAULT_PATH")
    OUTPUT_PATH: Path = Field(PROJECT_ROOT / "projects.yaml", env="OUTPUT_PATH")
    TASKS_PATH: Path = Field(PROJECT_ROOT / "data/tasks.yaml", env="TASKS_PATH")

    LOG_DIR: Path = Field(PROJECT_ROOT / "data/logs", env="LOG_DIR")
    ENERGY_LOG_PATH: Path = Field(
        PROJECT_ROOT / "data/energy_log.yaml", env="ENERGY_LOG_PATH"
    )
    PLAN_PATH: Path = Field(PROJECT_ROOT / "data/morning_plan.yaml", env="PLAN_PATH")
    CALENDAR_ICS_PATH: str = Field(
        str(PROJECT_ROOT / "data/calendar.ics"), env="CALENDAR_ICS_PATH"
    )
    TIME_ZONE: str = Field("UTC", env="TIME_ZONE")
    GOOGLE_CALENDAR_ID: str | None = Field(default=None, env="GOOGLE_CALENDAR_ID")
    GOOGLE_CREDENTIALS_PATH: str | None = Field(
        default=None, env="GOOGLE_CREDENTIALS_PATH"
    )

    # === Optional tokens ===
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    API_KEY: str = Field(default="", env="API_KEY")
    ACTIVATION_ENGINE_URL: str | None = Field(default=None, env="ACTIVATION_ENGINE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown keys like system-provided "timezone"
    )

    def model_post_init(self, __context):  # type: ignore[override]
        """Expand user home in any path settings."""
        self.VAULT_PATH = self.VAULT_PATH.expanduser()
        self.OUTPUT_PATH = self.OUTPUT_PATH.expanduser()
        self.TASKS_PATH = self.TASKS_PATH.expanduser()
        self.LOG_DIR = self.LOG_DIR.expanduser()
        self.ENERGY_LOG_PATH = self.ENERGY_LOG_PATH.expanduser()
        self.PLAN_PATH = self.PLAN_PATH.expanduser()
        self.CALENDAR_ICS_PATH = str(Path(self.CALENDAR_ICS_PATH).expanduser())
        if self.GOOGLE_CREDENTIALS_PATH:
            self.GOOGLE_CREDENTIALS_PATH = str(
                Path(self.GOOGLE_CREDENTIALS_PATH).expanduser()
            )


config = Config()
