from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Supply Chain Backend"
    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "smart_supply_chain"
    JWT_SECRET_KEY: str = "3595f50f28b7ca2586c8a24c56e7a9568b91f9099f6f8f4caa6ce64b99e7d3e9"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # SMTP Configuration Settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "supplychain-alerts@company.com"

    class Config:
        # Load from .env file relative to the app root or project root
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        extra = "ignore"

settings = Settings()
