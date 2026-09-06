import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    gemini_api_key: str = ""
    agent_mode: str = "fallback"  # 'llm' or 'fallback'
    
    kaggle_username: str = ""
    kaggle_key: str = ""
    
    db_path: str = "data/ecommerce.db"
    dashboard_db_path: str = "data/dashboard.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
