import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.limits import Limits


logger = logging.getLogger(__name__)

ProviderName = Literal["openai_compat", "openai", "mistral", "ollama", "vllm", "anthropic"]
EnvName = Literal["development", "production"]
DEFAULT_DEV_SECRET = "desktop-dev-secret"


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
    # Regex d'origines autorisées en complément de la liste explicite `cors_origins`.
    # Sidecar bureau loopback-only : on accepte tout origin loopback (IPv4/IPv6/tauri)
    # sur n'importe quel port pour couvrir les dev servers Vite/Quasar, Tauri dev/prod,
    # et le flag Private Network Access de Chrome. Vide = désactivé.
    cors_origin_regex: str | None = Field(
        default=(
            r"^(https?://(localhost|127\.0\.0\.1|\[::1\]|tauri\.localhost)(:\d+)?"
            r"|tauri://localhost)$"
        ),
        validation_alias="CORS_ORIGIN_REGEX",
    )

    env: EnvName = Field(default="development", validation_alias="ENV")

    internal_secret: str = Field(
        default=DEFAULT_DEV_SECRET,
        validation_alias="INTERNAL_SECRET",
    )

    # Timeout global d'un tour agent (LLM + outils + attente de confirmation).
    turn_timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=3600,
        validation_alias="TURN_TIMEOUT_SECONDS",
    )

    # Compaction automatique de l'historique.
    compaction_usage_threshold: float = Field(
        default=0.7,
        gt=0.0,
        lt=1.0,
        validation_alias="COMPACTION_USAGE_THRESHOLD",
    )
    compaction_keep_messages: int = Field(
        default=6,
        ge=2,
        validation_alias="COMPACTION_KEEP_MESSAGES",
    )
    compaction_min_history: int = Field(
        default=8,
        ge=4,
        validation_alias="COMPACTION_MIN_HISTORY",
    )
    compaction_min_old: int = Field(
        default=2,
        ge=1,
        validation_alias="COMPACTION_MIN_OLD",
    )
    compaction_fallback_keep_messages: int = Field(
        default=4,
        ge=0,
        validation_alias="COMPACTION_FALLBACK_KEEP_MESSAGES",
    )

    # Bornes d'entrée sur /agent/turn.
    max_history_messages: int = Field(
        default=200,
        ge=1,
        le=1000,
        validation_alias="MAX_HISTORY_MESSAGES",
    )
    max_user_message_length: int = Field(
        default=32_000,
        ge=1,
        le=500_000,
        validation_alias="MAX_USER_MESSAGE_LENGTH",
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

    llm_utility_provider: str | None = Field(
        default=None,
        validation_alias="LLM_UTILITY_PROVIDER",
    )
    llm_utility_model: str | None = Field(
        default=None,
        validation_alias="LLM_UTILITY_MODEL",
    )
    llm_utility_base_url: str | None = Field(
        default=None,
        validation_alias="LLM_UTILITY_BASE_URL",
    )
    llm_utility_api_key: str | None = Field(
        default=None,
        validation_alias="LLM_UTILITY_API_KEY",
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
    index_max_files: int = Field(
        default=500, ge=1, validation_alias="INDEX_MAX_FILES"
    )
    index_max_file_bytes: int = Field(
        default=524_288, ge=1024, validation_alias="INDEX_MAX_FILE_BYTES"
    )
    index_max_total_chars: int = Field(
        default=1_000_000, ge=1024, validation_alias="INDEX_MAX_TOTAL_CHARS"
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("project_root", mode="before")
    @classmethod
    def empty_project_root_as_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def validate_production_secret(self) -> Self:
        if self.env == "production":
            if not self.internal_secret or self.internal_secret == DEFAULT_DEV_SECRET:
                raise ValueError(
                    "INTERNAL_SECRET must be set to a non-default value when ENV=production"
                )
        elif self.internal_secret == DEFAULT_DEV_SECRET:
            logger.warning(
                "Using default INTERNAL_SECRET (%s); set a custom secret for non-dev use.",
                DEFAULT_DEV_SECRET,
            )
        return self

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

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
    def compiled_cors_origin_regex(self) -> str | None:
        value = (self.cors_origin_regex or "").strip()
        return value or None

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
            index_max_files=self.index_max_files,
            index_max_file_bytes=self.index_max_file_bytes,
            index_max_total_chars=self.index_max_total_chars,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
