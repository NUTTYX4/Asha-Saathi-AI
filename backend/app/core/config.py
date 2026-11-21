"""Application settings, loaded from the repository-root `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,https://localhost:5173"
    database_path: str = "./data/asha_saathi.db"
    # V2: when set (Docker Compose sets it), PostgreSQL/PostGIS is used and its schema is
    # managed only by Alembic. When unset, the Round 1 SQLite file above is used.
    # SecretStr: the URL contains the database password.
    database_url: SecretStr | None = None

    # V2 auth. Session cookies are httpOnly + SameSite=Strict; Secure unless explicitly disabled.
    session_ttl_hours: int = Field(default=12, ge=1, le=72)
    session_cookie_secure: bool = True
    login_max_failures: int = 5          # per username+client within the window
    login_failure_window_s: int = 300
    # Round 1 endpoints (/api/visits, /api/followups, /ws/session) have no login. Kept on until
    # the V2 UI replaces them (Phase 7); then set LEGACY_ROUND1_API_ENABLED=false.
    legacy_round1_api_enabled: bool = True

    # Gnani API Platform. SecretStr keeps the key out of reprs and logs.
    gnani_api_key: SecretStr | None = None

    prisma_ws_url: str = "wss://api.vachana.ai/stt/v3/stream"
    prisma_model: str = "prisma-v3.0"
    # Live API (21 Nov 2026) rejects a list here: "exactly one locale is required".
    # With format=codemix, English words still come back in Latin script.
    prisma_languages: str = "kn-IN"
    prisma_format: str = "codemix"
    prisma_min_silence_ms: int = Field(default=700, ge=100, le=2000)
    prisma_sample_rate: int = 16000

    timbre_url: str = "https://api.vachana.ai/api/v1/tts/inference"
    timbre_model: str = "timbre-v3.0"
    timbre_voice: str = "Shruthi"
    timbre_language: str = "kn-IN"
    timbre_sample_rate: int = 24000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    @property
    def gnani_configured(self) -> bool:
        return bool(self.gnani_api_key and self.gnani_api_key.get_secret_value().strip())

    def require_gnani_key(self) -> str:
        if not self.gnani_configured:
            raise RuntimeError(
                "GNANI_API_KEY is not set. Add it to the .env file at the repository root."
            )
        return self.gnani_api_key.get_secret_value().strip()  # type: ignore[union-attr]


@lru_cache
def get_settings() -> Settings:
    return Settings()
