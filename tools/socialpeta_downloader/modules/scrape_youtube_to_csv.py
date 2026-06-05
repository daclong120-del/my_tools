import os
import sys

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore(skip_db_init=True)
    core.youtube_service.run_scrape_youtube_to_csv_cli(sys.argv)

if __name__ == "__main__":
    main()
