"""Runtime settings, read from the environment (and the repo-root .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_prefix="NEXUS_", extra="ignore"
    )

    # The API and worker connect as nexus_app, to which row-level security applies.
    database_url: str = "postgresql+psycopg://nexus_app:nexus_app_dev@localhost:5544/nexus"
    # Migrations run as the schema owner.
    database_owner_url: str = (
        "postgresql+psycopg://nexus_owner:nexus_owner_dev@localhost:5544/nexus"
    )

    storage_dir: Path = REPO_ROOT / "var" / "storage"

    jwt_secret: str = Field(default="dev-only-change-me", min_length=16)
    session_hours: int = 12
    cookie_secure: bool = False

    # Model. The key is read from ANTHROPIC_API_KEY (environment or .env).
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model: str = "claude-opus-5"
    effort: str = "high"
    # On a policy refusal, let the API retry the request on a fallback model.
    model_fallbacks: bool = True

    # Guardrail limits for every agent run.
    agent_max_steps: int = 30
    agent_max_output_tokens: int = 16000
    agent_budget_usd: float = 5.00

    max_upload_mb: int = 50


@lru_cache
def settings() -> Settings:
    return Settings()
