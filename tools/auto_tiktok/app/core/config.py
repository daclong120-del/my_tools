import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Auto TikTok API"
    API_V1_STR: str = "/api/v1"
    
    # Cấu hình Database thô
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

    class Config:
        case_sensitive = True

settings = Settings()
