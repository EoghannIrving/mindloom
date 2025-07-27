"""Application configuration handled via environment variables."""

from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseSettings, Field

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
    VAULT_PATH: Path = Field(PROJECT_ROOT / "vault/Projects", env="VAULT_PATH")
    OUTPUT_PATH: Path = Field(PROJECT_ROOT / "projects.yaml", env="OUTPUT_PATH")

    # === Optional tokens ===
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    API_KEY: str = Field(default="", env="API_KEY")

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"

config = Config()
