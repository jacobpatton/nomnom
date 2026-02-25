from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PORT: int = 3002
    DB_PATH: str = "/data/nomnom.db"
    LOG_LEVEL: str = "info"


settings = Settings()
