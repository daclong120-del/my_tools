# tools/socialpeta_downloader/modules/fill_video_names.py
"""
Script điền video_name còn thiếu trong file CSV scraped_creatives_1_to_10.csv
sử dụng core đặt tên duy nhất từ UtilsService.
"""

import os
import sys

# Thêm workspace root vào sys.path để import được socialpeta_downloader
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore(skip_db_init=True)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "scraped_creatives_1_to_10.csv")
    core.fill_video_names_in_csv(csv_path)

if __name__ == "__main__":
    main()
