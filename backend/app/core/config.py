"""
Application configuration. Reads from environment variables only -
never hardcodes AWS credentials, region assumptions, or secrets here.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "InfraFox FinOps Platform"
    aws_region: str = "ap-south-1"
    environment: str = "development"

    # Scan behavior
    cloudwatch_lookback_days: int = 7
    # Phase 3: persistence. Defaults to a local SQLite file so the app
    # runs with zero extra setup during development; docker-compose.yml
    # (Phase 5) overrides this to point at the containerized Postgres.
    database_url: str = "sqlite:///./infrafox.db"

    class Config:
        env_file = ".env"
        env_prefix = "INFRAFOX_"


settings = Settings()
