import sys
import os

# Thêm workspace root vào sys.path để import được socialpeta_downloader
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core.tab_manager import TabScanner

def main():
    TabScanner().run_connect_first_tab_cli(sys.argv)

if __name__ == "__main__":
    main()
