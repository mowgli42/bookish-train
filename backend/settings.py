"""Application settings for the Catcher / dispatcher API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Edge Backup Catcher"
    app_version: str = "0.1.0"
    demo_mode: bool = False
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    otel_endpoint: str = Field(default="", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    ebk_ai_status: bool = Field(default=False, validation_alias="EBK_AI_STATUS")
    data_dir: Path = Field(default=Path("/var/lib/edge-backup"), validation_alias="DATA_DIR")

    @field_validator("demo_mode", mode="before")
    @classmethod
    def _parse_demo_mode(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).lower() in ("1", "true", "yes", "on")

    @field_validator("ebk_ai_status", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).lower() in ("1", "true", "yes", "on")

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def sqlite_path(self) -> Path:
        url = self.database_url.strip()
        if url.startswith("sqlite:///"):
            return Path(url.removeprefix("sqlite:///"))
        if url.startswith("sqlite://"):
            return Path(url.removeprefix("sqlite://"))
        return self.data_dir / "catcher.db"

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
