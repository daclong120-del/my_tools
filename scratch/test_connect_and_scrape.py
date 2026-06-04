import sys
import os
import time

# Add tools to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from tools.socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore()
    print("[*] Detecting tabs...")
    tabs = core.detect_tabs(9222)
    print(f"[+] Detected tabs: {tabs}")
    if not tabs:
        print("[-] No tabs found.")
        return
        
    selected_tab = tabs[0]["index"]
    print(f"[*] Running scraper on tab {selected_tab} for 2 pages...")
    
    # Run the scraper in the main thread so we can see exceptions
    try:
        core.run_tab_scraper(selected_tab, total_pages=2, port=9222)
    except Exception as e:
        import traceback
        print(f"[-] Scraper failed with exception: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
