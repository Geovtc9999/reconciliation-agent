"""Configuration de l'agent Réconciliation Retail↔Compta (pydantic-settings)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Service ---
    app_name: str = "Agent Réconciliation Retail↔Compta"
    app_version: str = "0.1.1"
    log_level: str = "INFO"

    # --- RAG (Hermes) — hostname interne STABLE sur le réseau recette ---
    hermes_url: str = "http://hermes:8000"
    hermes_timeout: float = 60.0
    rag_top_k: int = 4

    # --- LLM (Claude) ---
    anthropic_api_key: str = ""
    answer_model: str = "claude-opus-4-8"
    max_tokens: int = 4096

    # --- Stockage objet (MinIO) — bucket « artefacts » ---
    s3_endpoint: str = "minio-r625prgazwx67rtb157fa316:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_secure: bool = False
    s3_bucket: str = "artefacts"
    artefacts_prefix: str = "reconciliations/"

    # --- Observabilité (Langfuse) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://langfuse.nexerp.fr"

    # --- n8n (orchestration / Human-in-the-Loop) ---
    # Webhook n8n notifié à CHAQUE nouvelle proposition en attente de validation.
    n8n_validation_webhook: str = ""
    # Exiger la validation humaine avant toute finalisation (porte HITL).
    hitl_required: bool = True

    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key) and len(self.anthropic_api_key) > 20

    @property
    def s3_configured(self) -> bool:
        return bool(self.s3_access_key and self.s3_secret_key)

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def rag_configured(self) -> bool:
        return bool(self.hermes_url)


settings = Settings()
