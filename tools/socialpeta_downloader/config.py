import os
import sys

class Settings:
    PROJECT_NAME: str = "SocialPeta Downloader API"
    API_PORT: int = int(os.getenv("SOCIALPETA_DOWNLOADER_PORT", 8003))
    CHROME_DEBUG_PORT: int = int(os.getenv("CHROME_DEBUG_PORT", 9222))
    HOST: str = os.getenv("SOCIALPETA_DOWNLOADER_HOST", "127.0.0.1")
    
    # Resolve project root dynamically
    if getattr(sys, 'frozen', False):
        # Running as compiled binary (sys.executable is path to api.exe)
        # We put data folder in the directory of the executable
        ROOT_DIR = os.path.dirname(sys.executable)
    else:
        # Running in dev mode
        ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    DOWNLOAD_DIR: str = os.getenv("SOCIALPETA_DOWNLOAD_DIR", os.path.join(
        ROOT_DIR,
        "data",
        "videos"
    ))
    SESSION_DIR: str = os.getenv("SOCIALPETA_SESSION_DIR", os.path.join(
        ROOT_DIR,
        "data",
        "playwright_session"
    ))

settings = Settings()

# Đảm bảo các thư mục tồn tại
os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
os.makedirs(settings.SESSION_DIR, exist_ok=True)
