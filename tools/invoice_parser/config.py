import os

class Settings:
    PROJECT_NAME: str = "Invoice Parser API"
    API_PORT: int = int(os.getenv("INVOICE_PARSER_PORT", 8001))
    HOST: str = os.getenv("INVOICE_PARSER_HOST", "127.0.0.1")
    UPLOAD_DIR: str = os.getenv("INVOICE_UPLOAD_DIR", os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "uploads"
    ))
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "mock-key")

settings = Settings()

# Dam bao thu muc uploads ton tai
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
