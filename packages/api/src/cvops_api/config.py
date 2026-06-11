from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cvops:cvops@localhost:5432/cvops"

    # MinIO / S3
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "cvops-blobs"

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
