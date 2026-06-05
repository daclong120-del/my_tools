import os
import sys

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core.session import SessionService

def main():
    service = SessionService()
    service.run_clear_session_cli()

if __name__ == "__main__":
    main()
