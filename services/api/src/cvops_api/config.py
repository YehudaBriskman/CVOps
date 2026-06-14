from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cvops:cvops@localhost:5432/cvops"

    # S3-compatible storage (Garage by default; works against AWS S3, MinIO, etc.)
    S3_ENDPOINT: str = "http://localhost:3900"
    S3_ACCESS_KEY: str = "GKchangeme"
    S3_SECRET_KEY: str = "changeme"
    S3_BUCKET: str = "cvops-blobs"
    S3_REGION: str = "garage"
    S3_BACKEND: str = "garage"  # value recorded in blobs.storage_backend
    # Browser-reachable endpoint used ONLY to sign presigned URLs. S3_ENDPOINT
    # (e.g. http://garage:3900) is internal and unresolvable from a browser, so
    # presigned PUT/GET are signed against this instead (e.g. http://localhost:3900,
    # or a dev VM's host). Empty → fall back to S3_ENDPOINT (single-host/local).
    S3_PUBLIC_ENDPOINT: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "change-me-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    WORKER_TOKEN: str = "change-me-worker-token"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # CVAT (Phase 2)
    CVAT_URL: str = "http://cvat:8080"
    CVAT_USERNAME: str = "admin"
    CVAT_PASSWORD: str = "cvops"

    # Model Deployer
    MODEL_DEPLOYER_URL: str = "http://model-deployer:8001"


settings = Settings()
