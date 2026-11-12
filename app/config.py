from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    session_secret: str = Field(min_length=32)
    app_env: str = "development"
    session_secure: bool = True
    allowed_origin: str = "http://localhost:8000"
    analysis_mode: str = "baseline"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    provider_timeout: float = Field(default=12, gt=0, le=60)

    @model_validator(mode="after")
    def safe_configuration(self):
        if self.analysis_mode not in {"baseline", "openai"}:
            raise ValueError("analysis_mode must be baseline or openai")
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("Unknown app environment")
        if self.app_env == "production" and (
            not self.session_secure or not self.allowed_origin.startswith("https://")
        ):
            raise ValueError("Production requires HTTPS origin and secure cookies")
        return self


@lru_cache
def settings():
    return Settings()
