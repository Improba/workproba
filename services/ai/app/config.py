import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.limits import Limits


ProviderName = Literal["openai_compat", "openai", "mistral", "ollama", "vllm", "anthropic"]


class Settings(BaseSettings):
    """Runtime settings for the desktop AI sidecar."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = Field(default="127.0.0.1", validation_alias="HOST")
    port: int = Field(default=8765, ge=1, le=65535, validation_alias="PORT")
    project_root: Path | None = Field(default=None, validation_alias="PROJECT_ROOT")
    cors_origins: str = Field(
        default=(
            "http://127.0.0.1:5053,"
            "http://localhost:5053,"
            "http://127.0.0.1:8765,"
            "http://localhost:8765,"
            "tauri://localhost,"
            "http://tauri.localhost"
        ),
        validation_alias="CORS_ORIGINS",
    )

    internal_secret: str = Field(
        default="desktop-dev-secret",
        validation_alias="INTERNAL_SECRET",
    )

    llm_default_provider: ProviderName = Field(
        default="openai_compat",
        validation_alias="LLM_DEFAULT_PROVIDER",
    )
    llm_default_base_url: str | None = Field(
        default=None,
        validation_alias="LLM_DEFAULT_BASE_URL",
    )
    llm_default_api_key: str | None = Field(
        default=None,
        validation_alias="LLM_DEFAULT_API_KEY",
    )
    llm_default_model: str = Field(
        default="mistral",
        validation_alias="LLM_DEFAULT_MODEL",
    )

    llm_embedding_provider: str | None = Field(
        default=None,
        validation_alias="LLM_EMBEDDING_PROVIDER",
    )
    llm_embedding_model: str | None = Field(
        default=None,
        validation_alias="LLM_EMBEDDING_MODEL",
    )
    llm_embedding_base_url: str | None = Field(
        default=None,
        validation_alias="LLM_EMBEDDING_BASE_URL",
    )
    llm_embedding_api_key: str | None = Field(
        default=None,
        validation_alias="LLM_EMBEDDING_API_KEY",
    )

    sandbox_timeout_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias="SANDBOX_TIMEOUT_SECONDS",
    )

    max_agent_iterations: int = Field(
        default=6,
        ge=1,
        le=32,
        validation_alias="MAX_AGENT_ITERATIONS",
    )

    # --- Limites outils (tunables ops) ---
    read_max_lines: int = Field(default=2000, ge=1, validation_alias="READ_MAX_LINES")
    read_max_bytes: int = Field(
        default=262_144, ge=1024, validation_alias="READ_MAX_BYTES"
    )
    extract_max_pages: int = Field(
        default=50, ge=1, validation_alias="EXTRACT_MAX_PAGES"
    )
    extract_max_chars: int = Field(
        default=200_000, ge=1024, validation_alias="EXTRACT_MAX_CHARS"
    )
    search_max_limit: int = Field(
        default=20, ge=1, le=100, validation_alias="SEARCH_MAX_LIMIT"
    )
    search_max_files: int = Field(
        default=20_000, ge=100, validation_alias="SEARCH_MAX_FILES"
    )
    sandbox_output_max_bytes: int = Field(
        default=262_144, ge=1024, validation_alias="SANDBOX_OUTPUT_MAX_BYTES"
    )
    sandbox_memory_mb: int = Field(
        default=1024, ge=16, validation_alias="SANDBOX_MEMORY_MB"
    )
    sandbox_cpu_seconds: int = Field(
        default=30, ge=1, validation_alias="SANDBOX_CPU_SECONDS"
    )
    sandbox_file_size_mb: int = Field(
        default=50, ge=1, validation_alias="SANDBOX_FILE_SIZE_MB"
    )
    sandbox_block_network: bool = Field(
        default=True, validation_alias="SANDBOX_BLOCK_NETWORK"
    )
    generate_max_bytes: int = Field(
        default=5_242_880, ge=1024, validation_alias="GENERATE_MAX_BYTES"
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("project_root", mode="before")
    @classmethod
    def empty_project_root_as_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        value = self.cors_origins.strip()
        if not value:
            return []

        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(origin) for origin in parsed]

        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def limits(self) -> Limits:
        """Construit l'objet Limits partagé par les clients et le sandbox."""
        return Limits(
            read_max_lines=self.read_max_lines,
            read_max_bytes=self.read_max_bytes,
            extract_max_pages=self.extract_max_pages,
            extract_max_chars=self.extract_max_chars,
            search_max_limit=self.search_max_limit,
            search_max_files=self.search_max_files,
            sandbox_output_max_bytes=self.sandbox_output_max_bytes,
            sandbox_memory_mb=self.sandbox_memory_mb,
            sandbox_cpu_seconds=self.sandbox_cpu_seconds,
            sandbox_file_size_mb=self.sandbox_file_size_mb,
            sandbox_block_network=self.sandbox_block_network,
            generate_max_bytes=self.generate_max_bytes,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
