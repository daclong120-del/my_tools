import os
import sys

class Settings:
    PROJECT_NAME: str = "SocialPeta Downloader API"
    API_PORT: int = int(os.getenv("SOCIALPETA_DOWNLOADER_PORT", 8003))
    CHROME_DEBUG_PORT: int = int(os.getenv("CHROME_DEBUG_PORT", 9222))
    HOST: str = os.getenv("SOCIALPETA_DOWNLOADER_HOST", "127.0.0.1")
    
    # Resolve project root dynamically
    user_data_path = os.getenv("USER_DATA_PATH")
    if user_data_path:
        ROOT_DIR = user_data_path
    elif getattr(sys, 'frozen', False):
        # Running as compiled binary (sys.executable is path to api.exe or CLI exe)
        # We put data folder in the directory of the executable or its parent if inside app_core
        exe_dir = os.path.dirname(sys.executable)
        if os.path.basename(exe_dir).lower() == "app_core":
            ROOT_DIR = os.path.dirname(exe_dir)
        else:
            ROOT_DIR = exe_dir
    else:
        # Running in dev mode
        ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Writable data directory — separated from install dir for frozen builds
    if getattr(sys, 'frozen', False):
        DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SocialPetaDownloader")
    else:
        DATA_DIR = os.path.join(ROOT_DIR, "data")

    DOWNLOAD_DIR: str = os.getenv("SOCIALPETA_DOWNLOAD_DIR", os.path.join(
        ROOT_DIR,
        "data",
        "videos"
    ))
    SESSION_DIR: str = os.getenv("SOCIALPETA_SESSION_DIR", os.path.join(
        DATA_DIR,
        "playwright_session"
    ))

    @property
    def FFMPEG_PATH(self) -> str:
        is_frozen = getattr(sys, 'frozen', False) or '__compiled__' in globals() or '__compiled__' in sys.builtin_module_names
        
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir_candidates = [
            current_file_dir,
            os.path.dirname(current_file_dir),
            os.path.dirname(os.path.dirname(current_file_dir)),
        ]
        if hasattr(sys, '_MEIPASS'):
            temp_dir_candidates.append(sys._MEIPASS)
            
        for temp_dir in temp_dir_candidates:
            local_path = os.path.join(temp_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if os.path.exists(local_path):
                return local_path
            resources_bin_path = os.path.join(temp_dir, "resources", "bin", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if os.path.exists(resources_bin_path):
                return resources_bin_path

        if is_frozen:
            exe_dir = os.path.dirname(sys.executable)
            local_path = os.path.join(exe_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if os.path.exists(local_path):
                return local_path
                
        return "ffmpeg"

    @property
    def FFPROBE_PATH(self) -> str:
        is_frozen = getattr(sys, 'frozen', False) or '__compiled__' in globals() or '__compiled__' in sys.builtin_module_names
        
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir_candidates = [
            current_file_dir,
            os.path.dirname(current_file_dir),
            os.path.dirname(os.path.dirname(current_file_dir)),
        ]
        if hasattr(sys, '_MEIPASS'):
            temp_dir_candidates.append(sys._MEIPASS)
            
        for temp_dir in temp_dir_candidates:
            local_path = os.path.join(temp_dir, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
            if os.path.exists(local_path):
                return local_path
            resources_bin_path = os.path.join(temp_dir, "resources", "bin", "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
            if os.path.exists(resources_bin_path):
                return resources_bin_path

        if is_frozen:
            exe_dir = os.path.dirname(sys.executable)
            local_path = os.path.join(exe_dir, "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
            if os.path.exists(local_path):
                return local_path
                
        return "ffprobe"

settings = Settings()

# Đảm bảo các thư mục tồn tại
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.SESSION_DIR, exist_ok=True)
print(f"[*] DATA_DIR: {settings.DATA_DIR}")

