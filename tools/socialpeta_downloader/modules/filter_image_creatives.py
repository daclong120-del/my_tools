import os
import sys

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    # Thư mục hiện tại chứa script
    modules_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Xác định file đầu vào và đầu ra từ tham số dòng lệnh hoặc mặc định
    input_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(modules_dir, "scraped_creatives_1_to_10.csv")
    output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(modules_dir, "scraped_creatives_image_only.csv")
    
    core = SocialPetaDownloaderCore(skip_db_init=True)
    core.downloader_service.run_filter_image_creatives_cli(input_file=input_file, output_file=output_file)

if __name__ == "__main__":
    main()
