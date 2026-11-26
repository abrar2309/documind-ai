from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "DocuMind - AI Document Intelligence Platform"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    STORAGE_ROOT: str = str(PROJECT_ROOT / "storage" / "documents")
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 150

    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_PROVIDER: str = "ollama"
    CHAT_PROVIDER: str = "ollama"

    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_EMBEDDING_MODEL: str = "all-minilm"
    OLLAMA_CHAT_MODEL: str = "qwen3:1.7b"
    OLLAMA_TIMEOUT_SECONDS: int = 240

    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    RETRIEVAL_TOP_K: int = 5

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_DOCUMENT_TOPIC: str = "documind.document.ingest"
    KAFKA_DOCUMENT_DLQ_TOPIC: str = "documind.document.ingest.dlq"
    KAFKA_CONSUMER_GROUP: str = "documind-document-workers"
    KAFKA_MAX_RETRIES: int = 3
    KAFKA_RETRY_BASE_SECONDS: float = 2.0

    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_FAIL_OPEN: bool = True
    AGENT_MAX_CONCURRENT: int = 4

    OPENAI_INPUT_COST_PER_1M: float = 0.0
    OPENAI_OUTPUT_COST_PER_1M: float = 0.0
    OPENAI_EMBEDDING_COST_PER_1M: float = 0.0

    # Comma-separated exact origins/hosts. No wildcard is accepted in production.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1"
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_HSTS: bool = True
    EXPOSE_API_DOCS: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT.lower() == "production":
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("Production JWT_SECRET_KEY must contain at least 32 characters.")
            if "replace-with" in self.JWT_SECRET_KEY.lower() or "development" in self.JWT_SECRET_KEY.lower():
                raise ValueError("A real production JWT_SECRET_KEY must be configured.")
            origins = [x.strip() for x in self.CORS_ALLOWED_ORIGINS.split(",") if x.strip()]
            if not origins or "*" in origins:
                raise ValueError("Production CORS_ALLOWED_ORIGINS must contain explicit origins.")
            if any(not x.startswith("https://") for x in origins):
                raise ValueError("Production CORS origins must use HTTPS.")
            hosts = [x.strip() for x in self.TRUSTED_HOSTS.split(",") if x.strip()]
            if not hosts or "*" in hosts:
                raise ValueError("Production TRUSTED_HOSTS must contain explicit hostnames.")
            if self.RATE_LIMIT_FAIL_OPEN:
                raise ValueError("Production RATE_LIMIT_FAIL_OPEN must be false.")
            if self.JWT_ALGORITHM != "HS256":
                raise ValueError("This application currently supports HS256 signing only.")
            if self.EXPOSE_API_DOCS:
                raise ValueError("API docs must be disabled in production.")
        return self


settings = Settings()
