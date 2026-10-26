import re
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent

Effort = Literal["low", "medium", "high"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # local.env is kept for compatibility with textbook_quality setups
        env_file=(REPO_DIR / "local.env", REPO_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    PROMPT_TEMPLATE_DIR: Path = BASE_DIR / "llm" / "templates"
    FRONTEND_DIST_DIR: Path = REPO_DIR / "frontend" / "dist"

    # Database (any Postgres, including Supabase)
    DATABASE_URL: str = "postgresql://marginalia:marginalia@localhost:5432/marginalia"
    # Set when connecting through PgBouncer in transaction mode (e.g. Supabase's pooler on
    # port 6543). Left unset, it is switched on automatically for that port.
    DATABASE_PGBOUNCER: bool | None = None
    # Postgres schema that holds every Marginalia table, including Alembic's version table.
    # Use a dedicated schema (e.g. "marginalia") to share a database such as a Supabase project.
    # The schema must already exist; migrations never create anything outside it.
    DB_SCHEMA: str = "public"
    # Login role the app connects as; when set, migrations GRANT it access to what they create.
    DB_APP_ROLE: str | None = None
    DEBUG: bool = False

    # Access gate: when a password is set, every page and API route needs it (except
    # /api/health). The login is kept in a signed, httpOnly cookie.
    MARGINALIA_ACCESS_PASSWORD: str | None = None
    SESSION_SECRET: str | None = None  # Signs the login cookie; required with a password
    SESSION_COOKIE_SECURE: bool = True  # Browsers treat http://localhost as secure too
    SESSION_MAX_AGE_DAYS: int = 30

    # LLM
    LLM_PROVIDER: Literal["anthropic", "openai", "fake"] = "anthropic"
    LLM_MODEL: str | None = None  # Overrides the provider's default model
    LLM_TIMEOUT: float = 600
    LLM_MAX_RETRIES: int = 2
    LLM_CACHE: bool = False  # Reuse stored responses for identical requests (the CLI enables it)
    ANTHROPIC_API_KEY: str | None = None  # Falls back to the SDK's own credential lookup
    ANTHROPIC_BASE_URL: str | None = None
    # Retry requests declined by Claude's safety classifiers on Anthropic's recommended
    # fallback model (server-side fallbacks).
    ANTHROPIC_REFUSAL_FALLBACKS: bool = True
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None  # For OpenAI-compatible servers (vLLM, Ollama, ...)
    # "chat" uses Chat Completions, which most OpenAI-compatible servers implement.
    OPENAI_API_MODE: Literal["responses", "chat"] = "responses"
    FAKE_LLM_DELAY: float = 0.0  # Seconds between streamed chunks from the fake provider

    # How hard the model thinks for each task (provider effort / reasoning effort)
    EFFORT_DIAGNOSTICS: Effort = "low"
    EFFORT_PLAN: Effort = "medium"
    EFFORT_RESEARCH: Effort = "low"
    EFFORT_SECTION: Effort = "medium"
    EFFORT_TUTOR: Effort = "low"

    # Research notes gathered with the provider's web search before writing a section
    RESEARCH_BACKEND: Literal["web", "none"] = "web"
    RESEARCH_MAX_SEARCHES: int = 3

    # Generation
    PREFETCH_NEXT_SECTION: bool = True
    GENERATION_STALE_AFTER_SECONDS: int = 900  # A stuck "generating" section can be retried

    @field_validator("DB_SCHEMA", "DB_APP_ROLE")
    @classmethod
    def _plain_identifier(cls, value: str | None) -> str | None:
        # Used in DDL and GRANT statements, so only plain lower-case identifiers are allowed
        if value is not None and not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
            raise ValueError("must be a plain lower-case Postgres identifier")
        return value

    @property
    def access_gate_enabled(self) -> bool:
        return bool(self.MARGINALIA_ACCESS_PASSWORD)

    @property
    def default_model(self) -> str:
        if self.LLM_MODEL:
            return self.LLM_MODEL
        return {
            "anthropic": "claude-opus-5-5",
            "openai": "gpt-6.1-sol",
            "fake": "fake-tutor-1",
        }[self.LLM_PROVIDER]


settings = Settings()
