import os

class Settings:
    PROJECT_NAME: str = "Web Scraper API"
    API_PORT: int = int(os.getenv("WEB_SCRAPER_PORT", 8002))
    HOST: str = os.getenv("WEB_SCRAPER_HOST", "127.0.0.1")

settings = Settings()
