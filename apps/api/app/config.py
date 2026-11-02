from decimal import Decimal
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: SecretStr
    llm_model: str = Field(pattern=r"\S")
    llm_input_usd_per_million: Decimal = Field(gt=0)
    llm_output_usd_per_million: Decimal = Field(gt=0)
    max_cost_per_run_usd: Decimal = Field(default=Decimal("0.05"), gt=0)
    llm_max_output_tokens: int = Field(default=4096, gt=0, le=16384)
    embedding_model: str = Field(default="text-embedding-3-small", pattern=r"\S")
    embedding_usd_per_million: Decimal = Field(default=Decimal("0.02"), gt=0)
    # Empty URL lets libpq use PG* variables, as in docker-compose.
    database_url: SecretStr = SecretStr("")
    public_demo: bool = True
    jira_dry_run: bool = True
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: SecretStr = SecretStr("")
    jira_project_key: str = ""
    daily_budget_usd: Decimal = Field(default=Decimal("1.00"), gt=0)
    max_pending_runs: int = Field(default=8, ge=1, le=100)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_agent_id: str = Field(
        default="discovery-jira", pattern=r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
    )
    langsmith_agent_environment: Literal[
        "local", "development", "staging", "production"
    ] = "local"
    langsmith_workspace_id: str | None = None
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    @model_validator(mode="after")
    def check_keys(self) -> "Settings":
        if not self.openai_api_key.get_secret_value().strip():
            raise ValueError("OPENAI_API_KEY must not be empty")
        if self.langsmith_tracing and (
            self.langsmith_api_key is None
            or not self.langsmith_api_key.get_secret_value().strip()
        ):
            raise ValueError("LANGSMITH_API_KEY is required for tracing")
        return self
