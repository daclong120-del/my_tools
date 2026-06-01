import argparse
import sys
import os
import json
import time
import csv
import collections
import threading
import io

# Set encoding on Windows to prevent UnicodeEncodeError
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='backslashreplace')

# Setup import path if run directly
if __name__ == "__main__" and __package__ is None:
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.config import settings

# For non-blocking keyboard input on Windows
try:
    import msvcrt
except ImportError:
    msvcrt = None

# ANSI colors
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def handle_login(args):
    print("[*] Dang kiem tra trang thai dang nhap hien tai...")
    core = SocialPetaDownloaderCore()
    logged_in = core.check_login_status()
    if logged_in:
        print("[+] Ban da dang nhap thanh cong va phien lam viec van con hieu luc!")
        re_login = input("[?] Ban co muon dang nhap lai de cap nhat cookie khong? (y/N): ").strip().lower()
        if re_login not in ("y", "yes"):
            return
            
    print("[*] Chuan bi mo trinh duyet de dang nhap...")
    success = core.run_login_flow()
    if success:
        print("[+] Dang nhap hoan tat va da luu phien lam viec.")
    else:
        print("[-] Dang nhap that bai hoac bi huy.")

def handle_download(args):
    core = SocialPetaDownloaderCore()
    print(f"[*] Dang xu ly tai tu URL: {args.url}")
    
    if not core.check_login_status():
        print("[-] Canh bao: Chua dang nhap SocialPeta hoac phien da het han.")
        print("[*] Vui long tien hanh dang nhap truoc.")
        success = core.run_login_flow()
        if not success:
            print("[-] Loi: Phai dang nhap moi co the tai duoc video.")
            sys.exit(1)

    try:
        if getattr(args, 'search', False):
            limit = getattr(args, 'limit', 10)
            print(f"[*] Dang cao trang tim kiem, gioi han toi da {limit} ket qua...")
            results = core.scrape_search_page_and_download(args.url, max_results=limit)
            print("\n[+] Hoan thanh quet trang tim kiem:")
            print(json.dumps(results, indent=4, ensure_ascii=False))
        else:
            result = core.download_single_ad(args.url)
            print("\n[+] Ket qua xu ly:")
            print(json.dumps(result, indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"[!] Loi khi tai: {e}", file=sys.stderr)
        sys.exit(1)

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def show_reports_menu(core):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f"{MAGENTA}{BOLD}         THONG KE & CONG CU LOC DU LIEU           {RESET}")
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f" {GREEN}[1]{RESET} Thong ke tong quan kho video da tai")
        print(f" {GREEN}[2]{RESET} Loc danh sach CSV theo tieu chi")
        print(f" {GREEN}[3]{RESET} Xem nhat ky loc trung lap (Audit Log)")
        print(f" {GREEN}[4]{RESET} Quay lai Menu chinh")
        print(f"{CYAN}--------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Nhap lua chon cua ban (1-4): {RESET}").strip()
        
        if choice == "1":
            # UC-10a: CLI stats
            if not os.path.exists(core.csv_path):
                print(f"\n{YELLOW}[!] Chua co du lieu trong file CSV.{RESET}")
                input("Nhan Enter de tiep tuc...")
                continue
                
            total_count = 0
            total_size = 0
            platforms = collections.Counter()
            regions = collections.Counter()
            apps = collections.Counter()
            
            try:
                with open(core.csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        if r.get("status") == "saved":
                            total_count += 1
                            total_size += int(r.get("file_size") or 0)
                            plat = r.get("platform")
                            if plat:
                                platforms[plat.lower()] += 1
                            area = r.get("area")
                            if area:
                                regions[area.upper()] += 1
                            app = r.get("app_name")
                            if app:
                                apps[app] += 1
                                
                print(f"\n{GREEN}{BOLD}--- THONG KE TONG QUAN ---{RESET}")
                print(f" * Tong so video duy nhat da tai: {BOLD}{total_count}{RESET}")
                print(f" * Tong dung luong luu tru: {BOLD}{format_size(total_size)}{RESET}")
                
                print(f"\n{CYAN}{BOLD}* Phan bo theo Nen tang (Platform):{RESET}")
                for plat, val in platforms.items():
                    print(f"   - {plat.capitalize()}: {val} video")
                    
                print(f"\n{CYAN}{BOLD}* Phan bo theo Quoc gia/Vung (Region/Area):{RESET}")
                for reg, val in regions.items():
                    print(f"   - {reg}: {val} video")
                    
                print(f"\n{CYAN}{BOLD}* Top 5 ung dung tai nhieu nhat:{RESET}")
                for app, val in apps.most_common(5):
                    print(f"   - {app}: {val} video")
                    
            except Exception as e:
                print(f"[-] Loi doc thong ke: {e}")
            input(f"\n{GREEN}Nhan Enter de tiep tuc...{RESET}")
            
        elif choice == "2":
            # UC-10b: Filter CSV
            if not os.path.exists(core.csv_path):
                print(f"\n{YELLOW}[!] Chua co du lieu trong file CSV.{RESET}")
                input("Nhan Enter de tiep tuc...")
                continue
                
            filter_type = input(f"{BOLD}Chon loc theo [p] nen tang (platform) hoac [a] khu vuc (area/region): {RESET}").strip().lower()
            if filter_type not in ("p", "platform", "a", "area"):
                print("[-] Lua chon khong hop le.")
                input("Nhan Enter de tiep tuc...")
                continue
                
            query = input(f"{BOLD}Nhap gia tri muon loc (vi du: ios, japan, us...): {RESET}").strip().lower()
            
            try:
                results = []
                with open(core.csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        val_to_check = r.get("platform", "").lower() if filter_type in ("p", "platform") else r.get("area", "").lower()
                        if val_to_check == query or query in val_to_check:
                            results.append(r)
                            
                print(f"\n{GREEN}{BOLD}--- KET QUA LOC ({len(results)} matches) ---{RESET}")
                if results:
                    print(f"{'Ad ID':<12} | {'App Name':<25} | {'Plat':<6} | {'Region':<8} | {'Status':<10}")
                    print("-" * 70)
                    for r in results[:20]:  # Show top 20
                        print(f"{r.get('ad_id'):<12} | {r.get('app_name')[:25]:<25} | {r.get('platform'):<6} | {r.get('area'):<8} | {r.get('status'):<10}")
                    if len(results) > 20:
                        print(f"... va {len(results) - 20} dong khac.")
                else:
                    print("[-] Khong co ban ghi nao khop voi bo loc.")
            except Exception as e:
                print(f"[-] Loi loc du lieu: {e}")
            input(f"\n{GREEN}Nhan Enter de tiep tuc...{RESET}")
            
        elif choice == "3":
            # UC-10c: Audit Log for duplicates
            if not os.path.exists(core.audit_csv_path):
                print(f"\n{YELLOW}[!] Chua co ban ghi loc trung lap nao duoc luu.{RESET}")
                input("Nhan Enter de tiep tuc...")
                continue
                
            try:
                print(f"\n{GREEN}{BOLD}--- NHAT KY LOC TRUNG LAP (AUDIT LOG) ---{RESET}")
                with open(core.audit_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        print(f"{'Time':<19} | {'Ad ID':<10} | {'App':<20} | {'Match ID':<10} | {'Reason'}")
                        print("-" * 80)
                        for r in rows[-20:]:  # Show last 20 duplicates caught
                            print(f"{(r.get('timestamp') or ''):<19} | {(r.get('ad_id') or ''):<10} | {(r.get('app_name') or '')[:20]:<20} | {(r.get('duplicate_ad_id') or ''):<10} | {(r.get('reason') or '')}")
                    else:
                        print("[-] Nhat ky dang trong.")
            except Exception as e:
                print(f"[-] Loi doc audit log: {e}")
            input(f"\n{GREEN}Nhan Enter de tiep tuc...{RESET}")
            
        elif choice == "4":
            break

def run_concurrent_crawler(core, initial_threads=3, total_pages=2):
    """
    Launches the concurrent pipeline, detects active tabs, and enters the real-time Dashboard (UC-06c, UC-T07)
    """
    print(f"[*] Dang khoi chay crawler voi {initial_threads} luong download...")
    core.start_system(thread_count=initial_threads)
    
    print(f"[*] Dang quet cac tab SocialPeta dang hoat dong...")
    core.detect_tabs()
    
    # Dashboard loop
    try:
        while core.running:
            # Get stats
            sys_stats = core.sys_monitor.get_stats()
            
            # Clear screen
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Header
            print(f"{CYAN}{BOLD}=================================================={RESET}")
            print(f"{MAGENTA}{BOLD}    DASHBOARD THEO DOI - SOCIALPETA CONCURRENT    {RESET}")
            print(f"{CYAN}{BOLD}=================================================={RESET}")
            
            # Connection and System stats
            ram_status = f"{RED}{sys_stats['ram_usage']:.1f}% (Critical! Throttling){RESET}" if sys_stats["is_ram_critical"] else f"{GREEN}{sys_stats['ram_usage']:.1f}%{RESET}"
            cpu_status = f"{RED}{sys_stats['cpu_usage']:.1f}% (Critical!){RESET}" if sys_stats["is_cpu_critical"] else f"{GREEN}{sys_stats['cpu_usage']:.1f}%{RESET}"
            print(f" * System: CPU: {cpu_status} | RAM: {ram_status} | Luong khuyen nghi: {BOLD}{sys_stats['max_threads_recommended']}{RESET}")
            print(f" * So luong luong download active: {BOLD}{core.download_semaphore.value}{RESET}")
            disk_status = f"{RED}{BOLD}FULL (PAUSED){RESET}" if core.disk_full else f"{GREEN}OK{RESET}"
            print(f" * O dia: {disk_status} | Luong dedup active: {GREEN}Yes{RESET}")
            state_str = f"{GREEN}RUNNING{RESET}" if core.pause_event.is_set() else f"{YELLOW}PAUSED{RESET}"
            print(f" * Trang thai download: {state_str}")
            
            # Tab listing (UC-T02)
            print(f"{CYAN}--------------------------------------------------{RESET}")
            print(f"{BOLD} DANH SACH TAB SOCIALPETA PHAT HIEN DUOC:{RESET}")
            if not core.tab_states:
                print(f"  {YELLOW}(Chua phat hien tab nao. Bam [r] de quet){RESET}")
            else:
                for idx, tstate in sorted(core.tab_states.items()):
                    status_raw = tstate["status"]
                    # Map raw status to Vietnamese UI status label
                    if status_raw == "running":
                        status_lbl = f"{GREEN}[ĐANG TẢI]{RESET}"
                    elif status_raw == "new":
                        status_lbl = f"{CYAN}[NEW]{RESET}"
                    elif status_raw == "done":
                        status_lbl = f"{GREEN}[XONG]{RESET}"
                    elif status_raw == "expired":
                        status_lbl = f"{RED}[HẾT HẠN]{RESET}"
                    elif status_raw == "closed":
                        status_lbl = f"{RED}[ĐÃ ĐÓNG]{RESET}"
                    elif status_raw == "failed":
                        status_lbl = f"{RED}[LỖI]{RESET}"
                    else:
                        status_lbl = f"[{status_raw.upper()}]"
                        
                    app_name = tstate.get("app_name", "Unknown App")
                    if len(app_name) > 30:
                        app_name = app_name[:27] + "..."
                        
                    print(f"  [{idx}] {status_lbl} {app_name} | Cào: {BOLD}{tstate.get('scraped_count', 0)}{RESET} items (Trang {tstate.get('current_page', 1)}/{tstate.get('target_pages', 0)})")
            
            # Downloader stats (UC-T07)
            core_stats = core.stats
            # Get pending and downloading counts from in-memory stats
            pending_count = core_stats.get("pending", 0)
            downloading_count = core_stats.get("downloading", 0)
            
            print(f"{CYAN}--------------------------------------------------{RESET}")
            print(f"{BOLD} THONG KE TOAN BO HE THONG:{RESET}")
            print(f"  - Tong so video sniffed:   {BOLD}{core_stats['total_sniffed']}{RESET}")
            print(f"  - Dang cho download:       {YELLOW}{pending_count}{RESET}")
            print(f"  - Dang tai (Downloading):  {CYAN}{downloading_count}{RESET}")
            print(f"  - Hoan thanh (Saved):      {GREEN}{core_stats['done']}{RESET}")
            print(f"  - Loi download (Failed):   {RED}{core_stats['failed']}{RESET}")
            print(f"  - Link CDN het han:        {YELLOW}{core_stats['expired']}{RESET}")
            print(f"  - Trung lap da loc:        {MAGENTA}{core_stats['duplicate']}{RESET}")
            
            print(f"{CYAN}--------------------------------------------------{RESET}")
            print(f" {BOLD}Phím dieu khien nhanh:{RESET}")
            print(f"  {GREEN}[r]{RESET} Quét / Lam moi danh sach Tab")
            print(f"  {GREEN}[c]{RESET} Bat dau cao mot Tab cu the")
            print(f"  {GREEN}[a]{RESET} Bat dau cao tat ca cac Tab")
            print(f"  {GREEN}[l]{RESET} Kich hoat Soft Trigger de force data")
            print(f"  {GREEN}[p]{RESET} Tam dung / tiep tuc downloader")
            print(f"  {GREEN}[t]{RESET} Thay doi so luong luong tai")
            print(f"  {GREEN}[q]{RESET} Dung crawler va quay lai Menu")
            print(f"{CYAN}=================================================={RESET}")
            
            # Non-blocking key checking (Windows specific)
            if msvcrt:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    if key == 'r':
                        print(f"\n[*] Dang quet danh sach tab...")
                        core.detect_tabs()
                        time.sleep(1)
                    elif key == 'c':
                        try:
                            val = input(f"\n{BOLD}Nhap index tab muon bat dau cao: {RESET}").strip()
                            if val.isdigit():
                                idx = int(val)
                                if idx in core.tab_states:
                                    p_str = input(f"{BOLD}So trang muon cao (mac dinh {total_pages}): {RESET}").strip()
                                    pages = total_pages
                                    if p_str.isdigit() and int(p_str) > 0:
                                        pages = int(p_str)
                                    # Start scraper in daemon thread
                                    t = threading.Thread(target=core.run_tab_scraper, args=(idx, pages), daemon=True)
                                    t.start()
                                    print(f"{GREEN}[+] Da khoi chay thread cao cho Tab {idx} (Pages: {pages}).{RESET}")
                                else:
                                    print(f"{RED}[!] Loi: Tab index {idx} khong ton tai.{RESET}")
                            else:
                                print(f"{RED}[!] Loi: Index phai la so.{RESET}")
                        except Exception as ex:
                            print(f"{RED}[!] Loi: {ex}{RESET}")
                        time.sleep(1)
                    elif key == 'a':
                        print(f"\n[*] Dang khoi chay cao cho TAT CA cac tab active...")
                        # Run detect_tabs first to ensure current state is up-to-date
                        active = core.detect_tabs()
                        for tab_info in active:
                            idx = tab_info["index"]
                            if core.tab_states[idx]["status"] not in ("running", "closed"):
                                t = threading.Thread(target=core.run_tab_scraper, args=(idx, total_pages), daemon=True)
                                t.start()
                        print(f"{GREEN}[+] Da khoi chay thread cao cho tat ca cac tab.{RESET}")
                        time.sleep(1.5)
                    elif key == 'l':
                        try:
                            val = input(f"\n{BOLD}Nhap index tab muon kich hoat Soft Trigger: {RESET}").strip()
                            if val.isdigit():
                                idx = int(val)
                                if idx in core.tab_states:
                                    # Call soft trigger
                                    threading.Thread(target=core.soft_trigger, args=(idx,), daemon=True).start()
                                    print(f"{GREEN}[+] Da kich hoat soft trigger cho Tab {idx}.{RESET}")
                                else:
                                    print(f"{RED}[!] Loi: Tab index {idx} khong ton tai.{RESET}")
                            else:
                                print(f"{RED}[!] Loi: Index phai la so.{RESET}")
                        except Exception as ex:
                            print(f"{RED}[!] Loi: {ex}{RESET}")
                        time.sleep(1)
                    elif key == 'p':
                        if core.pause_event.is_set():
                            core.pause_event.clear()
                            print(f"\n{YELLOW}[*] Da tam dung download.{RESET}")
                        else:
                            core.pause_event.set()
                            print(f"\n{GREEN}[*] Tiep tuc download.{RESET}")
                        time.sleep(1)
                    elif key == 't':
                        try:
                            # Restore terminal input mode temporarily
                            val = input(f"\n{BOLD}Nhap so luong luong tai moi (1-16): {RESET}").strip()
                            if val.isdigit() and 1 <= int(val) <= 16:
                                new_t = int(val)
                                core.download_semaphore.set_value(new_t)
                                print(f"{GREEN}[+] Da thay doi so luong luong tai thanh: {new_t}{RESET}")
                            else:
                                print(f"{RED}[!] Gia tri khong hop le.{RESET}")
                        except Exception:
                            pass
                        time.sleep(1)
                    elif key == 'q':
                        print(f"\n{YELLOW}[*] Dang shutdown crawler...{RESET}")
                        core.stop_system()
                        break
            else:
                # Fallback simple sleep for Linux/macOS
                time.sleep(2)
                
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[*] Phat hien huy tu ban phim. Dang shutdown crawler...{RESET}")
        core.stop_system()

def handle_server(args):
    print(f"[*] Dang khoi dong FastAPI server tren {args.host}:{args.port}...")
    import uvicorn
    uvicorn.run("socialpeta_downloader.api:app", host=args.host, port=args.port, reload=args.reload)

def interactive_menu():
    core = SocialPetaDownloaderCore()
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f"{MAGENTA}{BOLD}   GIAO DIEN TUONG TAC - SOCIALPETA DOWNLOADER    {RESET}")
        print(f"{CYAN}{BOLD}=================================================={RESET}")
        print(f" {GREEN}[1]{RESET} Kiem tra trang thai / Dang nhap SocialPeta")
        print(f" {GREEN}[2]{RESET} Tai video tu mot Link chi tiet (Single Ad)")
        print(f" {GREEN}[3]{RESET} Tai video tu Link trang tim kiem (Search Page)")
        print(f" {GREEN}[4]{RESET} Khoi chay tu dong hoa concurrent 3-Stream (Sniffer/Downloader/Dedup)")
        print(f" {GREEN}[5]{RESET} Bao cao thong ke & Bo loc du lieu")
        print(f" {GREEN}[6]{RESET} Khoi chay API Server (FastAPI)")
        print(f" {GREEN}[7]{RESET} Thoat chuong trinh")
        print(f"{CYAN}--------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Nhap lua chon cua ban (1-7): {RESET}").strip()
        
        if choice == "1":
            print(f"\n{YELLOW}[*] Kiem tra phien lam viec...{RESET}")
            class DummyArgs:
                pass
            handle_login(DummyArgs())
            input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
            
        elif choice == "2":
            url = input(f"{BOLD}Nhap Link chi tiet quang cao SocialPeta: {RESET}").strip().strip("\"'")
            if not url:
                input(f"\n{YELLOW}Duong dan trong. Nhan Enter de tiep tuc...{RESET}")
                continue
            class ArgsSingle:
                url = url
                search = False
            handle_download(ArgsSingle())
            input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
            
        elif choice == "3":
            url = input(f"{BOLD}Nhap Link trang tim kiem SocialPeta: {RESET}").strip().strip("\"'")
            if not url:
                input(f"\n{YELLOW}Duong dan trong. Nhan Enter de tiep tuc...{RESET}")
                continue
            limit_str = input(f"{BOLD}Gioi han so luong video muon tai (Mac dinh: 10): {RESET}").strip()
            search_limit = 10
            if limit_str.isdigit():
                search_limit = int(limit_str)
            class ArgsSearch:
                url = url
                search = True
                limit = search_limit
            handle_download(ArgsSearch())
            input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
            
        elif choice == "4":
            t_str = input(f"{BOLD}Nhap so luong luong download song song (Mac dinh: 3): {RESET}").strip()
            threads = 3
            if t_str.isdigit():
                threads = int(t_str)
            
            pages = 2
            while True:
                p_str = input(f"{BOLD}So trang muon tai? (mac dinh: 2): {RESET}").strip()
                if not p_str:
                    pages = 2
                    break
                if p_str.isdigit() and int(p_str) > 0:
                    pages = int(p_str)
                    break
                else:
                    print(f"{RED}[!] Loi: So trang phai la mot so nguyen duong.{RESET}")
                    
            run_concurrent_crawler(core, initial_threads=threads, total_pages=pages)
            input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
            
        elif choice == "5":
            show_reports_menu(core)
            
        elif choice == "6":
            print(f"\n{CYAN}[*] Khoi chay API server...{RESET}")
            class ArgsServer:
                host = settings.HOST
                port = settings.API_PORT
                reload = True
            try:
                handle_server(ArgsServer())
            except KeyboardInterrupt:
                print(f"\n{YELLOW}[*] Da dung API server.{RESET}")
                input(f"\n{GREEN}Nhan Enter de quay lai Menu chinh...{RESET}")
                
        elif choice == "7":
            print(f"\n{GREEN}Cam on ban da su dung SocialPeta Downloader! Tam biet.{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n[!] Lua chon khong hop le.")
            input(f"\n{YELLOW}Nhan Enter de tiep tuc...{RESET}")

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        description="SocialPeta Downloader Command Line Interface (CLI)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Cac lenh hoat dong")
    subparsers.required = True

    # Subcommand: login
    login_parser = subparsers.add_parser("login", help="Dang nhap va luu phien SocialPeta")
    login_parser.set_defaults(func=handle_login)

    # Subcommand: download
    download_parser = subparsers.add_parser("download", help="Tai video tu link SocialPeta")
    download_parser.add_argument("url", type=str, help="Link chi tiet hoac link tim kiem cua SocialPeta")
    download_parser.add_argument("--search", action="store_true", help="Xac dinh day la link tim kiem")
    download_parser.add_argument("--limit", type=int, default=10, help="Gioi han video tai ve neu la trang tim kiem")
    download_parser.set_defaults(func=handle_download)

    # Subcommand: start (to launch the concurrent sniffer and crawler)
    start_parser = subparsers.add_parser("start", help="Khoi chay concurrent crawler ba luong")
    start_parser.add_argument("--threads", type=int, default=3, help="So luong luong download song song ban dau")
    start_parser.add_argument("--pages", type=int, default=2, help="So trang muon duyet va tai tu dong")
    
    # Subcommand: server
    server_parser = subparsers.add_parser("server", help="Khoi chay API server FastAPI")
    server_parser.add_argument("--host", type=str, default=settings.HOST, help="IP Host")
    server_parser.add_argument("--port", type=int, default=settings.API_PORT, help="Port hoat dong")
    server_parser.add_argument("--reload", action="store_true", help="Bat auto-reload")
    server_parser.set_defaults(func=handle_server)

    args = parser.parse_args()
    
    if args.command == "start":
        core = SocialPetaDownloaderCore()
        run_concurrent_crawler(core, initial_threads=args.threads, total_pages=args.pages)
    else:
        args.func(args)

if __name__ == "__main__":
    main()
