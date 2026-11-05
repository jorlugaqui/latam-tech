"""mock-tools configuration, from environment variables only. Fails closed at startup."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_TOKEN_LENGTH = 32


class MockToolsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)

    # Least privilege: a token of its own, different from the API token the browser uses.
    tools_api_token: SecretStr = Field(min_length=MIN_TOKEN_LENGTH)
