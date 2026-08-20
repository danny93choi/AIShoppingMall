from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "postgresql+asyncpg://commerce:commerce_dev_only@postgres:5432/commerce"
    redis_url: str = "redis://redis:6379/0"
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    openai_api_key: str | None = Field(default=None, repr=False)
    llm_default_model: str = "gpt-5.6-sol"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_run_budget_usd: float = Field(default=1.0, gt=0)
    allow_marketing_draft_before_approval: bool = False
    shopify_shop_domain: str | None = None
    shopify_access_token: SecretStr | None = Field(default=None, repr=False)
    shopify_api_version: str = "2026-07"
    naver_api_hub_client_id: SecretStr | None = Field(default=None, repr=False)
    naver_api_hub_client_secret: SecretStr | None = Field(default=None, repr=False)
    naver_api_hub_base_url: str = "https://naverapihub.apigw.ntruss.com"
    naver_search_ad_api_key: SecretStr | None = Field(default=None, repr=False)
    naver_search_ad_secret_key: SecretStr | None = Field(default=None, repr=False)
    naver_search_ad_customer_id: str | None = Field(default=None, repr=False)
    naver_search_ad_base_url: str = "https://api.searchad.naver.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
