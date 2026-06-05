import os
import sys

# Thêm workspace root vào sys.path để import được socialpeta_downloader
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore(skip_db_init=True)
    core.downloader_service.run_download_videos_not_youtube_cli(sys.argv)

if __name__ == "__main__":
    main()
