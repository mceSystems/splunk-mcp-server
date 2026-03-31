from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    splunk_host: str
    splunk_token: str
    splunk_port: int = 8089
    splunk_verify_ssl: bool = True
    splunk_timeout: float = 30.0
    splunk_max_wait: float = 120.0
    splunk_max_results: int = 100


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
