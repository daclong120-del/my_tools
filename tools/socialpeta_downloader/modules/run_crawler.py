import os
import sys
import time
import threading

# Add workspace root to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    print("[*] Khoi chay SocialPeta Downloader Core...")
    
    # Check command line arguments for page count
    pages_to_scrape = 10
    if len(sys.argv) > 1:
        try:
            pages_to_scrape = int(sys.argv[1])
            print(f"[*] Thiet lap so trang can cao: {pages_to_scrape}")
        except ValueError:
            print(f"[!] Tham so trang khong hop le: {sys.argv[1]}. Mac dinh la 10.")
            
    # 5 downloader threads as requested
    core = SocialPetaDownloaderCore()
    
    print("[*] Khoi dong he thong voi 5 luong...")
    core.start_system(thread_count=5)
    
    print("[*] Dang quet cac tab dang hoat dong trong Chrome...")
    active_tabs = core.detect_tabs()
    if not active_tabs:
        print("[-] Khong tim thay tab SocialPeta nao. Vui long kiem tra lai Chrome.")
        core.stop_system()
        return

    # Start scraping pages for each active tab
    threads = []
    for tab in active_tabs:
        idx = tab["index"]
        print(f"[*] Bat dau cao tab [{idx}] - {pages_to_scrape} trang...")
        t = threading.Thread(target=core.run_tab_scraper, args=(idx, pages_to_scrape), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        while core.running:
            # Print stats every 5 seconds
            if sys.stdout.isatty():
                os.system('cls' if os.name == 'nt' else 'clear')
            print("==================================================")
            print("         STATUS MONITOR (NON-INTERACTIVE)         ")
            print("==================================================")
            
            scrapers_alive = any(t.is_alive() for t in threads)
            
            # Get pending and downloading counts from in-memory stats
            pending = core.stats.get("pending", 0)
            downloading = core.stats.get("downloading", 0)
            
            stats = core.stats
            print(f"  - Scrapers running: {scrapers_alive}")
            print(f"  - Total sniffed:    {stats['total_sniffed']}")
            print(f"  - Waiting:          {pending}")
            print(f"  - Downloading:      {downloading}")
            print(f"  - Saved (Unique):   {stats['done']}")
            print(f"  - Failed:           {stats['failed']}")
            print(f"  - Expired:          {stats['expired']}")
            print(f"  - Duplicate:        {stats['duplicate']}")
            print("==================================================")
            
            # Check if all scrapers are finished and queues are empty
            if not scrapers_alive and pending == 0 and downloading == 0:
                print("[+] Tat ca luong scraper da hoan thanh va file da tai xong!")
                break
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("[*] Nguoi dung yeu cau dung...")
    finally:
        print("[*] Dang dung SocialPeta Downloader Engine...")
        core.stop_system()
        print("[+] Da dung SocialPeta Downloader.")

if __name__ == "__main__":
    main()
