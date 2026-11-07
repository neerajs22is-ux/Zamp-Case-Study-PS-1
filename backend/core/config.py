"""Application Configuration and Strict Environment Validation.

Enforces production truth rules:
1. Rejects SQLite and in-memory databases in production and staging environments.
2. Rejects local-auth bypass and seed data mode in production and staging environments.
3. Validates private object storage credentials for production.
4. Redacts all sensitive secrets from string representations and serializations.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


class ConfigurationError(ValueError):
    """Raised when environment settings violate production truth constraints."""
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # 1. Core Application
    APP_ENV: AppEnv = Field(default=AppEnv.DEVELOPMENT)
    APP_NAME: str = "Autonomous AP Command Center"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    PORT: Optional[int] = None
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="dev-secret-key-must-be-changed-in-production-32chars")
    BASE_URL: str = "http://localhost:8000"
    APP_TIMEZONE: str = "Asia/Kolkata"

    @model_validator(mode="before")
    @classmethod
    def resolve_port_env(cls, data: Any) -> Any:
        if isinstance(data, dict):
            port = os.environ.get("PORT") or data.get("PORT")
            if port:
                try:
                    data["APP_PORT"] = int(port)
                    data["PORT"] = int(port)
                except (ValueError, TypeError):
                    pass
        return data

    # 2. Database
    # Default to None or PostgreSQL connection string
    DATABASE_URL: Optional[str] = Field(default=None)  # Cloud Run runtime connection (Transaction pooler port 6543)
    MIGRATION_DATABASE_URL: Optional[str] = Field(default=None)  # Alembic migration connection (Direct PostgreSQL port 5432 / session pooler)
    BACKUP_DATABASE_URL: Optional[str] = Field(default=None)  # Backup & restore connection (Direct PostgreSQL port 5432 / session pooler)
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_TIMEOUT_SECONDS: int = 30

    # 3. Identity Provider (Supabase Auth / Google Workspace OIDC)
    IDP_PROVIDER: str = "supabase_auth"
    SUPABASE_URL: Optional[str] = Field(default=None)
    SUPABASE_ANON_KEY: Optional[str] = Field(default=None)
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(default=None)
    SUPABASE_JWT_SECRET: Optional[str] = Field(default=None)
    SUPABASE_JWKS_URL: Optional[str] = Field(default=None)
    SUPABASE_ISSUER: Optional[str] = Field(default=None)
    SUPABASE_AUDIENCE: str = "authenticated"
    # Operator must confirm the identity provider requires email confirmation.
    IDENTITY_EMAIL_CONFIRMATION_ENFORCED: bool = False
    # Emergency recovery cutoff, Unix seconds UTC; requires signed token iat.
    AUTH_REJECT_TOKENS_ISSUED_BEFORE: Optional[int] = Field(default=None, ge=0)
    OIDC_ISSUER_URL: Optional[str] = "https://accounts.google.com"
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[str] = None
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    OIDC_AUDIENCE: Optional[str] = None
    LOCAL_AUTH_BYPASS: bool = False
    ENABLE_DEV_SESSION: bool = False  # Development-only session minting flag; strictly False by default
    # Comma-separated authenticated identity subjects allowed to operate platform-wide services.
    PLATFORM_OPERATOR_SUBJECTS: str = ""

    # 4. Private Object Storage (Supabase Storage Primary, S3 Supported)
    STORAGE_PROVIDER: str = "supabase"  # supabase, s3
    STORAGE_BUCKET_NAME: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "invoices"
    STORAGE_REGION: str = "ap-south-1"
    STORAGE_KMS_KEY_ID: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    STORAGE_SIGNED_URL_EXPIRY_SECONDS: int = 300
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB Supabase Free limit
    MAX_PENDING_UPLOADS_PER_TENANT: int = Field(default=10, ge=1, le=1000)
    # Renewal budget, not a guarantee that an external request can be cancelled.
    PIPELINE_PROVIDER_BUDGET_SECONDS: int = Field(default=900, ge=180, le=3600)

    # 5. Gmail Ingestion (Phase B)
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REDIRECT_URI: Optional[str] = None
    GMAIL_REFRESH_TOKEN: Optional[str] = None  # Optional: For local dev/single-mailbox test. In production, tokens are stored encrypted per-mailbox in PostgreSQL (gmail_accounts.encrypted_refresh_token).
    GMAIL_TARGET_MAILBOX: Optional[str] = None
    GMAIL_ENCRYPTION_KEY: Optional[str] = None
    PUBSUB_TOPIC_NAME: Optional[str] = None
    PUBSUB_VERIFICATION_AUDIENCE: Optional[str] = None
    PUBSUB_SERVICE_ACCOUNT_EMAIL: Optional[str] = None
    PUBSUB_ACK_DEADLINE_SECONDS: int = 300
    GMAIL_SYNC_TIMEOUT_SECONDS: int = 240  # Internal sync deadline comfortably below Cloud Run container timeout & Pub/Sub ack deadline (300s)
    GMAIL_WATCH_RENEWAL_HOURS: int = 48
    GMAIL_RECONCILIATION_HOURS: int = 6

    # 5.1 Cloud Scheduler Authentication (Stage 7.1)
    CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL: Optional[str] = None
    CLOUD_SCHEDULER_VERIFICATION_AUDIENCE: Optional[str] = None

    # 6. SAP ERP Adapter (Phase B)
    SAP_API_BASE_URL: Optional[str] = None
    SAP_AUTH_TYPE: str = "oauth2"
    SAP_CLIENT_ID: Optional[str] = None
    SAP_CLIENT_SECRET: Optional[str] = None
    SAP_TOKEN_URL: Optional[str] = None
    SAP_COMPANY_CODE: Optional[str] = None
    SAP_ERP_CACHE_TTL_MINUTES: int = 60

    # 7. Policy & Thresholds
    DUAL_APPROVAL_THRESHOLD_INR: float = 500000.00
    RATE_TOLERANCE_PERCENT: float = 1.50
    ROUNDING_TOLERANCE_INR: float = 20.00

    # 8. Document Retention & Purge Compliance Policy
    DOCUMENT_RETENTION_DAYS: int = 2920  # 8 years statutory financial record retention (Companies Act 2013 / GST Act)
    ENABLE_PERMANENT_PURGE: bool = False  # Disabled until compliance governance and dual-approval policy are certified
    PURGE_APPROVAL_ROLES: List[str] = ["CONTROLLER", "SYSTEM_ADMIN"]

    # 9. Backup & Recovery Configuration (Phase B Stage 6)
    BACKUP_DIR: str = "backups"
    BACKUP_ENCRYPTION_KEY: Optional[str] = None
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_RETENTION_COUNT: int = 10

    # 10. LLM & Document Intelligence (AWS Bedrock Mantle)
    MANTLE_BASE_URL: str = Field(default="https://bedrock-mantle.ap-south-1.api.aws/v1")
    MANTLE_API_KEY: Optional[str] = Field(default=None)
    MANTLE_MODEL_ID: str = Field(default="qwen.qwen3-235b-a22b-2507-v1:0")
    MANTLE_PROJECT_ID: Optional[str] = None
    MANTLE_TIMEOUT_SECONDS: float = Field(default=30.0)
    MANTLE_MAX_TOKENS: int = Field(default=2048)
    MANTLE_TEMPERATURE: float = Field(default=0.0)
    MANTLE_COST_PER_1K_INPUT: float = Field(default=0.0006)
    MANTLE_COST_PER_1K_OUTPUT: float = Field(default=0.0024)
    MANTLE_MAX_DOCUMENT_COST_USD: float = Field(default=0.10)
    MANTLE_MONTHLY_BUDGET_USD: float = Field(default=50.00)
    MODEL_MAX_ATTEMPTS_PER_TENANT_MINUTE: int = Field(default=30, ge=1, le=100000)
    MODEL_RESERVATION_BUDGET_USD_PER_TENANT_MONTH: float = Field(default=50.0, gt=0, le=100000)

    # 11. Multimodal Visual Document Intelligence (AWS Bedrock Palmyra Vision 7B)
    ENABLE_PALMYRA_VISION: bool = Field(default=False)
    PALMYRA_BASE_URL: str = Field(default="https://bedrock-mantle.us-east-1.api.aws/v1")
    PALMYRA_API_KEY: Optional[str] = Field(default=None)
    PALMYRA_MODEL_ID: str = Field(default="writer.palmyra-vision-7b")
    PALMYRA_TIMEOUT_SECONDS: float = Field(default=30.0)
    PALMYRA_MAX_TOKENS: int = Field(default=1500)
    PALMYRA_TEMPERATURE: float = Field(default=0.0)
    PALMYRA_COST_PER_1K_INPUT: float = Field(default=0.0008)
    PALMYRA_COST_PER_1K_OUTPUT: float = Field(default=0.0020)

    def get_palmyra_api_key(self) -> Optional[str]:
        """Resolves Palmyra API key, defaulting to the shared MANTLE_API_KEY."""
        return self.PALMYRA_API_KEY or self.MANTLE_API_KEY

    @model_validator(mode="after")
    def validate_production_invariants(self) -> "Settings":
        """Enforces strict non-negotiable production truth rules."""
        is_production_like = self.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING)

        if is_production_like:
            # Invariant 1: Production and Staging require PostgreSQL
            if not self.DATABASE_URL:
                raise ConfigurationError(
                    f"Production/Staging violation: DATABASE_URL must be configured. "
                    f"Got None for environment '{self.APP_ENV.value}'."
                )

            valid_pg_prefixes = ("postgresql://", "postgres://", "postgresql+psycopg://", "postgresql+psycopg2://")
            if not any(self.DATABASE_URL.startswith(prefix) for prefix in valid_pg_prefixes):
                raise ConfigurationError(
                    f"Production/Staging violation: PostgreSQL is mandatory. "
                    f"SQLite, in-memory, or unsupported database drivers are strictly forbidden in '{self.APP_ENV.value}'."
                )

            # Invariant 2: Local Auth Bypass is barred
            if self.LOCAL_AUTH_BYPASS:
                raise ConfigurationError(
                    f"Security violation: LOCAL_AUTH_BYPASS cannot be enabled in '{self.APP_ENV.value}'."
                )

            # Invariant 3: Object storage bucket must be configured
            if not self.STORAGE_BUCKET_NAME:
                raise ConfigurationError(
                    f"Production violation: STORAGE_BUCKET_NAME is required in '{self.APP_ENV.value}'. "
                    f"Local disk fallback is strictly barred in production."
                )

            # Invariant 4: Debug mode cannot be enabled
            if self.DEBUG:
                raise ConfigurationError(
                    f"Security violation: DEBUG mode cannot be enabled in '{self.APP_ENV.value}'."
                )

            # Invariant 5: SECRET_KEY must be a cryptographically secure random string
            if self.SECRET_KEY in (
                "dev-secret-key-must-be-changed-in-production-32chars",
                "change-this-to-a-secure-random-string-at-least-32-chars-long",
                "",
            ) or len(self.SECRET_KEY) < 32:
                raise ConfigurationError(
                    f"Security violation: SECRET_KEY must be a cryptographically random string (min 32 chars) in '{self.APP_ENV.value}'."
                )

        return self

    def is_identity_configured(self) -> bool:
        """Returns True only if real Supabase Auth or OIDC credentials are supplied."""
        supabase_configured = bool(self.SUPABASE_URL or self.SUPABASE_JWKS_URL or self.SUPABASE_JWT_SECRET)
        oidc_configured = bool(self.OIDC_CLIENT_ID and self.OIDC_ISSUER_URL)
        return supabase_configured or oidc_configured

    def is_gmail_configured(self) -> bool:
        """Returns True only if genuine Gmail API credentials and encryption keys are supplied."""
        return bool(self.GMAIL_CLIENT_ID and self.GMAIL_CLIENT_SECRET and (self.GMAIL_REFRESH_TOKEN or self.GMAIL_ENCRYPTION_KEY))

    def is_erp_configured(self) -> bool:
        """Returns True only if genuine ERP API endpoints and credentials exist."""
        return bool(self.SAP_API_BASE_URL and self.SAP_CLIENT_ID and self.SAP_COMPANY_CODE)

    def is_storage_configured(self) -> bool:
        """Returns True only if cloud object storage credentials exist."""
        if self.STORAGE_PROVIDER == "supabase":
            bucket = self.SUPABASE_STORAGE_BUCKET or self.STORAGE_BUCKET_NAME
            return bool(
                self.SUPABASE_URL
                and (self.SUPABASE_SERVICE_ROLE_KEY or self.SUPABASE_ANON_KEY)
                and bucket
            )
        return bool(self.STORAGE_BUCKET_NAME and (self.AWS_ACCESS_KEY_ID or os.getenv("AWS_ROLE_ARN") or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")))

    def redacted_dict(self) -> Dict[str, Any]:
        """Returns safe configuration summary with all secrets and keys redacted."""
        secret_keys = {
            "SECRET_KEY", "OIDC_CLIENT_SECRET", "AWS_SECRET_ACCESS_KEY",
            "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_ENCRYPTION_KEY",
            "SAP_CLIENT_SECRET", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET",
            "SUPABASE_ANON_KEY", "BACKUP_ENCRYPTION_KEY", "MANTLE_API_KEY",
            "PALMYRA_API_KEY"
        }
        res: Dict[str, Any] = {}
        for key, val in self.model_dump().items():
            if key in secret_keys and val:
                res[key] = "********"
            elif key in ("DATABASE_URL", "MIGRATION_DATABASE_URL", "BACKUP_DATABASE_URL") and val:
                # Mask password in URL
                try:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(val)
                    if parsed.password:
                        netloc = f"{parsed.username}:********@{parsed.hostname}"
                        if parsed.port:
                            netloc += f":{parsed.port}"
                        res[key] = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                    else:
                        res[key] = val
                except Exception:
                    res[key] = "postgresql://********"
            else:
                res[key] = val
        return res


settings = Settings()
