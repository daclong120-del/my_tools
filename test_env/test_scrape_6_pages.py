import os
import sys
import time
import shutil
import threading

# Add tools to path to allow importing local services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
from socialpeta_downloader.core import SocialPetaDownloaderCore

def run_6_page_test():
    print("[*] Starting automated 6-page scraper test...")
    
    # 1. Instantiate the Core
    core = SocialPetaDownloaderCore()
    
    # Configure download directory to test_downloads
    test_download_dir = os.path.abspath("data/test_downloads")
    core.update_download_dir(test_download_dir)
    core.quiet_mode = True # quiet mode avoids duplicate print outputs
    core.download_mode = "all"
    
    print(f"[+] Save Directory: {test_download_dir}")
    print(f"[+] Default CSV path: {core.csv_path}")
    
    # 2. Detect active tabs on port 9222
    tabs = core.detect_tabs(9222)
    if not tabs:
        print("[-] ERROR: No SocialPeta tabs detected on Chrome debugging port 9222.")
        sys.exit(1)
        
    # Select first matching SocialPeta tab
    selected_tab = None
    for t in tabs:
        url = t.get("url", "").lower()
        title = t.get("title", "").lower()
        if "socialpeta" in url or "guangdada" in url or "socialpeta" in title or "guangdada" in title:
            selected_tab = t["index"]
            print(f"[+] Hooking Tab #{selected_tab}: '{t.get('title')}'")
            break
            
    if selected_tab is None:
        print("[-] ERROR: No matching SocialPeta/Guangdada tab found.")
        sys.exit(1)
        
    # Reset state for selected tab
    if selected_tab in core.tab_states:
        core.tab_states[selected_tab]["status"] = "new"
        core.tab_states[selected_tab]["current_page"] = 1
        core.tab_states[selected_tab]["scraped_count"] = 0
        core.tab_states[selected_tab]["target_pages"] = 6
        
    # 3. Start the downloader engine and background scraper thread
    print("[*] Starting Core downloader system...")
    core.start_system(thread_count=3)
    
    scraper_thread = threading.Thread(
        target=core.run_tab_scraper,
        args=(selected_tab, 6, 9222),
        daemon=True
    )
    scraper_thread.start()
    
    print("[*] Scraper thread started. Monitoring progress loop...")
    
    start_time = time.time()
    last_scraped = 0
    try:
        while True:
            tab_state = core.tab_states.get(selected_tab, {})
            tab_status = tab_state.get("status", "unknown")
            stats = core.stats
            
            # Print periodic progress
            print(f"    [Progress] Page: {tab_state.get('current_page')}/{tab_state.get('target_pages')} | "
                  f"Scraped Count: {tab_state.get('scraped_count')} | "
                  f"Status: {tab_status} | "
                  f"Stats -> Pending: {stats.get('pending', 0)}, Downloading: {stats.get('downloading', 0)}, Done: {stats.get('done', 0)}")
            
            is_scraper_active = tab_status in ("running", "new")
            if not is_scraper_active and stats.get("pending", 0) == 0 and stats.get("downloading", 0) == 0:
                print("[+] Scraper finished and download queue is empty!")
                break
                
            # Timeout safety check: if nothing scraped after 5 minutes, abort
            elapsed = time.time() - start_time
            if elapsed > 300:
                print("[-] Timeout: Scraper execution exceeded 5 minutes. Aborting...")
                break
                
            time.sleep(3.0)
    except KeyboardInterrupt:
        print("[!] Execution interrupted by user.")
    finally:
        print("[*] Stopping downloader system...")
        core.stop_system()
        
    # 4. Sync SQLite database to CSV and copy to destination
    print("[*] Syncing final SQLite history to CSV...")
    core.session_service.sync_db_to_csv()
    
    source_csv = core.csv_path
    dest_csv = os.path.abspath("test_env/discovered_creatives_6_pages.csv")
    
    if os.path.exists(source_csv):
        shutil.copy2(source_csv, dest_csv)
        print(f"🎉 SUCCESS: Test CSV file generated successfully at {dest_csv}")
        # Print first few lines of the CSV
        try:
            with open(dest_csv, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
                print(f"[+] CSV contains {len(lines) - 1} rows.")
                print("[*] CSV Header:")
                print(f"    {lines[0].strip()}")
                if len(lines) > 1:
                    print("[*] First data row:")
                    print(f"    {lines[1].strip()}")
        except Exception as e_read:
            print(f"[-] Could not read generated CSV: {e_read}")
    else:
        print(f"[-] ERROR: Source CSV {source_csv} does not exist.")
        sys.exit(1)

if __name__ == "__main__":
    run_6_page_test()
