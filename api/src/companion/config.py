"""Runtime configuration, read from environment variables only (design D3).

Secrets are ``SecretStr`` so they are masked in ``repr``/logs, and validation errors never
echo input values. Invalid configuration raises at construction, so the API fails closed.
"""

from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_TOKEN_LENGTH = 32


class DatabaseSettings(BaseSettings):
    """The only setting migrations need, so the migrate service never receives the API token."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr


class Settings(DatabaseSettings):
    api_token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
    enable_docs: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Read tools (design D7, D14). The tools token is not the API token (least privilege).
    tools_base_url: AnyHttpUrl
    tools_api_token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
    tools_timeout_seconds: float = Field(default=3.0, gt=0, le=10)
