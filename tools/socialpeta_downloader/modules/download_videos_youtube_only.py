import os
import sys

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore(skip_db_init=True)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "scraped_creatives_1_to_10.csv")
    output_dir = os.path.join(current_dir, "download_videos_youtube_only")
    core.youtube_service.run_download_video_youtube_only_cli(sys.argv, csv_path=csv_path, output_dir=output_dir)

if __name__ == "__main__":
    main()
