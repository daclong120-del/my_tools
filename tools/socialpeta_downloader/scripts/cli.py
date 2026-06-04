# tools/socialpeta_downloader/cli/cli_v2/cli.py
"""
Responsibility: CLI V2 with arrow-key menus, ASCII banner, Chrome troubleshooting flow,
Folder Explorer picker (in-memory), and Live Scraper Dashboard with Ctrl+Q safe cancel.
"""

import sys
import os
import io
import time
import shutil
import threading
import queue
from datetime import datetime
import subprocess

# Set encoding on Windows to prevent UnicodeEncodeError
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='backslashreplace')
    
    # Fix Tcl/Tk path for Tkinter inside Virtual Environment (.venv) on Windows
    if sys.prefix != sys.base_prefix:
        base_tcl_dir = os.path.join(sys.base_prefix, "tcl")
        if os.path.exists(base_tcl_dir):
            tcl_lib = os.path.join(base_tcl_dir, "tcl8.6")
            tk_lib = os.path.join(base_tcl_dir, "tk8.6")
            if os.path.exists(tcl_lib):
                os.environ["TCL_LIBRARY"] = tcl_lib
            if os.path.exists(tk_lib):
                os.environ["TK_LIBRARY"] = tk_lib

# Setup import path to allow importing socialpeta_downloader core modules
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.config import settings

# For non-blocking keyboard input on Windows
try:
    import msvcrt
except ImportError:
    msvcrt = None

# UI Libraries
import pyfiglet
from InquirerPy import inquirer
from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from rich.console import Console
from rich.live import Live
from rich.text import Text

# Use subprocess for folder selection dialog without UI dependencies
import subprocess

# Global console
console = Console()

# ANSI Color Codes for fallback messages
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


class AppState:
    download_dir = ""
    chrome_port = 9222
    thread_count = 3

global_logs = []
MAX_LOGS = 10

class StdoutRedirector:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.buffer = ""

    def write(self, data):
        if not data: return
        # If the call is from the main thread (rendering UI), bypass capture
        if threading.current_thread() is threading.main_thread():
            self.original_stdout.write(data)
            return

        self.buffer += data
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if line:
                ts = datetime.now().strftime("%H:%M:%S")
                if not line.startswith("["):
                    line = f"[INFO] {line}"
                global_logs.append(f"{ts} {line}")
                if len(global_logs) > MAX_LOGS:
                    global_logs.pop(0)

    def flush(self):
        self.original_stdout.flush()

    def __getattr__(self, name):
        return getattr(self.original_stdout, name)


def show_banner():
    try:
        banner_text = pyfiglet.figlet_format("SOCIALPETA", font="slant")
        console.print(f"[bold cyan]{banner_text}[/bold cyan]")
    except Exception:
        console.print("[bold cyan]███████╗ ██████╗  ██████╗██╗ █████╗ ██╗     ██████╗ ███████╗████████╗ █████╗[/]")
        console.print("[bold cyan]██╔════╝██╔═══██╗██╔════╝██║██╔══██╗██║     ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗[/]")
        console.print("[bold cyan]███████╗██║   ██║██║     ██║███████║██║     ██████╔╝█████╗     ██║   ███████║[/]")
        console.print("[bold cyan]╚════██║██║   ██║██║     ██║██╔══██║██║     ██╔═══╝ ██╔══╝     ██║   ██╔══██║[/]")
        console.print("[bold cyan]███████║╚██████╔╝╚██████╗██║██║  ██║███████╗██║     ███████╗   ██║   ██║  ██║[/]")
        console.print("[bold cyan]╚══════╝ ╚═════╝  ╚═════╝╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝   ╚═╝   ╚═╝  ╚═╝[/]")
    console.print("[dim cyan]═══ HỆ THỐNG TỰ ĐỘNG HÓA TẢI RESOURCE SOCIALPETA (CLI V2) ═══[/]\n")


def ask_directory_dialog(initial_dir):
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide root window
        root.wm_attributes("-topmost", 1)  # Focus and bring to front
        
        path = filedialog.askdirectory(
            parent=root,
            title="Chọn thư mục lưu file tải về",
            initialdir=initial_dir
        )
        root.destroy()
        
        if path:
            return os.path.abspath(path)
        return initial_dir
    except Exception as e:
        print(f"\n[-] Không thể mở Tkinter Folder Explorer ({e}).")
        ans = input(f"Nhập đường dẫn thư mục thủ công (Mặc định: {initial_dir}): ").strip()
        return ans if ans else initial_dir



def clean_temp_dirs(core):
    for folder in [getattr(core, "temp_queue_dir", None), getattr(core, "temp_download_dir", None)]:
        if folder and os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)
            except Exception as e:
                import traceback
                core.log("error", f"[-] Lỗi dọn dẹp thư mục tạm {folder}: {e}\n{traceback.format_exc()}")


def make_dashboard(core, tab_index):
    import psutil
    tab_state = core.tab_states.get(tab_index, {})
    core_stats = core.stats

    # 1. Gather system resource metrics
    cpu = core.sys_monitor.cpu_usage
    try:
        ram_used_gb = psutil.virtual_memory().used / (1024 ** 3)
    except Exception:
        ram_used_gb = 0.0

    try:
        total, used, free = shutil.disk_usage(core.download_dir)
        free_gb = free / (1024 ** 3)
        disk_status = f"OK ({free_gb:.0f} GB free)" if free_gb >= 1.0 else f"LOW ({free_gb:.2f} GB free)"
    except Exception:
        disk_status = "OK"

    active_threads = core_stats.get('downloading', 0)
    total_threads = AppState.thread_count

    sys_line = f"[HỆ THỐNG] Threads: {active_threads}/{total_threads} active | CPU: {cpu:.1f}% | RAM: {ram_used_gb:.1f} GB | Disk: {disk_status}"
    
    # 2. Gather download stats
    total_sniffed = core_stats.get('total_sniffed', 0)
    pending = core_stats.get('pending', 0)
    downloading = core_stats.get('downloading', 0)
    done = core_stats.get('done', 0)
    duplicate = core_stats.get('duplicate', 0)
    failed = core_stats.get('failed', 0) + core_stats.get('expired', 0)
    
    stats_line = f"[THỐNG KÊ] Tổng sniff: {total_sniffed} | Chờ: {pending} | Đang tải: {downloading} | Xong: {done} | Trùng: {duplicate} | Lỗi: {failed}"

    # 3. Construct minimal styled text layout
    dashboard_text = Text()
    dashboard_text.append("[+] Bắt đầu tiến trình cào và tải...\n", style="bold green")
    dashboard_text.append("---------------------------------------------------------------------------------\n", style="dim white")
    dashboard_text.append(f"{sys_line}\n", style="cyan")
    dashboard_text.append(f"{stats_line}\n", style="magenta")
    dashboard_text.append("---------------------------------------------------------------------------------\n\n", style="dim white")

    # 4. Active downloads progress section
    dashboard_text.append("[ĐANG TẢI VIDEO]\n", style="bold yellow")
    if hasattr(core, "download_progress") and core.download_progress:
        active_downloads = {k: v for k, v in core.download_progress.items() if v.get('status') in ('downloading', 'processing')}
        if not active_downloads:
            dashboard_text.append("- Không có tiến trình tải nào đang diễn ra...\n", style="dim white")
        else:
            for ad_id, info in sorted(active_downloads.items()):
                p = info.get('percent', 0.0)
                status = info.get('status')
                filled = int((p / 100.0) * 20)
                bar = "▓" * filled + "░" * (20 - filled)
                speed = info.get('speed', '0 MB/s')
                dl_type = info.get('type', 'Unknown')
                
                dashboard_text.append(f"- Ad #{ad_id}: ", style="bold white")
                dashboard_text.append(f"{bar} {p:5.1f}% ", style="cyan")
                if status == 'processing':
                    dashboard_text.append("[Đang xử lý/Lọc trùng...]\n", style="yellow")
                else:
                    dashboard_text.append(f"[Tải {dl_type}: {speed}]\n", style="dim white")
    else:
        dashboard_text.append("- Không có tiến trình tải nào đang diễn ra...\n", style="dim white")

    dashboard_text.append("\n")

    # 5. Active logs section
    dashboard_text.append("[NHẬT KÝ HOẠT ĐỘNG (LOGS)]\n", style="bold green")
    if not global_logs:
        dashboard_text.append("Đang chờ dữ liệu...\n", style="dim white")
    else:
        for log_line in global_logs:
            lower_line = log_line.lower()
            if "[error]" in lower_line or "[-] " in log_line or "fail" in lower_line or "loi" in lower_line:
                dashboard_text.append(f"{log_line}\n", style="red")
            elif "[warning]" in lower_line or "[!]" in log_line or "[warn]" in lower_line:
                dashboard_text.append(f"{log_line}\n", style="yellow")
            elif "[+]" in log_line or "thanh cong" in lower_line or "done" in lower_line or "success" in lower_line:
                dashboard_text.append(f"{log_line}\n", style="green")
            else:
                dashboard_text.append(f"{log_line}\n", style="white")

    return dashboard_text


def ensure_chrome_connected(core):
    while True:
        port = AppState.chrome_port
        if core.chrome_service._is_chrome_cdp_active(port):
            return True

        console.clear()
        show_banner()
        print(f"\n{RED}[!] Không thể kết nối tới Google Chrome Debug Port ({port}).{RESET}")
        print("[*] Vui lòng chọn giải pháp xử lý sự cố Chrome bên dưới:")

        choices = [
            Choice("restart", "1. Chọn khởi động lại trình duyệt với port đó"),
            Choice("retry", "2. Thử kết nối lại"),
            Choice("exit", "3. Đóng chương trình")
        ]

        action = inquirer.select(
            message="Chọn giải pháp xử lý sự cố:",
            choices=choices,
            default="retry"
        ).execute()

        if action == "restart":
            print(f"[*] Đang khởi chạy Chrome với cổng debug {port}...")
            success = core.chrome_service.check_and_launch_chrome(port)
            if success:
                print(f"{GREEN}[+] Đã khởi chạy Chrome thành công.{RESET}")
            else:
                print(f"{RED}[-] Khởi chạy Chrome thất bại. Vui lòng tự mở Chrome với cờ --remote-debugging-port={port}{RESET}")
            time.sleep(2)
        elif action == "retry":
            print("[*] Đang kiểm tra lại kết nối...")
            time.sleep(1)
        elif action == "exit":
            print(f"{YELLOW}[*] Đang đóng chương trình...{RESET}")
            sys.exit(0)


def configure_settings(core):
    while True:
        console.clear()
        show_banner()
        print(f"\n{CYAN}{BOLD}--- CẤU HÌNH HỆ THỐNG (Lưu Tạm Thời) ---{RESET}\n")

        choices = [
            Choice("threads", f"1. Số luồng tải video song song (Hiện tại: {AppState.thread_count})"),
            Choice("dir", f"2. Thư mục tải mặc định (Hiện tại: {AppState.download_dir})"),
            Choice("port", f"3. Cấu hình Cổng Debug của Chrome (Hiện tại: {AppState.chrome_port})"),
            Choice("back", "Quay lại")
        ]

        sel = inquirer.select(
            message="Chọn cấu hình muốn thay đổi:",
            choices=choices,
            default="back"
        ).execute()

        if sel == "threads":
            ans = inquirer.text(
                message="Nhập số luồng tải song song (1-16):",
                default=str(AppState.thread_count)
            ).execute()
            if ans.isdigit() and 1 <= int(ans) <= 16:
                AppState.thread_count = int(ans)
                print(f"{GREEN}[+] Cập nhật số luồng tải song song thành: {AppState.thread_count}{RESET}")
            else:
                print(f"{RED}[!] Số luồng không hợp lệ (phải từ 1 đến 16).{RESET}")
            time.sleep(1.5)

        elif sel == "dir":
            print("[*] Đang mở Folder Explorer...")
            new_dir = ask_directory_dialog(AppState.download_dir)
            if new_dir:
                AppState.download_dir = os.path.abspath(new_dir)
                core.save_config(AppState.download_dir)
                AppState.download_dir = core.download_dir
                print(f"{GREEN}[+] Cập nhật thư mục tải thành: {AppState.download_dir}{RESET}")
            time.sleep(1.5)

        elif sel == "port":
            ans = inquirer.text(
                message="Nhập cổng debug của Chrome (mặc định: 9222):",
                default=str(AppState.chrome_port)
            ).execute()
            if ans.isdigit() and 1 <= int(ans) <= 65535:
                AppState.chrome_port = int(ans)
                print(f"{GREEN}[+] Cập nhật cổng debug Chrome thành: {AppState.chrome_port}{RESET}")
            else:
                print(f"{RED}[!] Cổng debug không hợp lệ.{RESET}")
            time.sleep(1.5)

        elif sel == "back":
            break


def main_menu():
    core = SocialPetaDownloaderCore()
    # Force defaults at startup
    AppState.download_dir = core.download_dir

    while True:
        console.clear()
        show_banner()

        choices = [
            Choice("select_tab", "1. Chọn trang tải"),
            Choice("open_dir", "2. Mở thư mục tải"),
            Choice("settings", "3. Cài đặt hệ thống"),
            Choice("exit", "4. Thoát chương trình")
        ]

        sel = inquirer.select(
            message="Chọn chức năng chính:",
            choices=choices,
            default="select_tab"
        ).execute()

        if sel == "select_tab":
            # 1. Check Chrome debug port
            if not ensure_chrome_connected(core):
                continue

            # 2. Scan active SocialPeta tabs
            tabs = core.detect_tabs(AppState.chrome_port)
            if not tabs:
                print(f"\n{YELLOW}[!] Không tìm thấy tab SocialPeta nào đang mở trong trình duyệt Chrome.{RESET}")
                print("[*] Vui lòng truy cập trang SocialPeta trên trình duyệt trước khi tiếp tục.")
                input("\nNhấn Enter để tiếp tục...")
                continue

            # 3. Show tab selection
            tab_choices = []
            for t in tabs:
                title_clean = t['title']
                if len(title_clean) > 50:
                    title_clean = title_clean[:47] + "..."
                url_clean = t['url']
                if len(url_clean) > 40:
                    url_clean = url_clean[:37] + "..."
                tab_choices.append(Choice(t['index'], f"Tab #{t['index']} - {title_clean} ({url_clean})"))
            tab_choices.append(Separator())
            tab_choices.append(Choice("reload", "R. Load lại danh sách tab"))
            tab_choices.append(Choice("back", "Quay lại"))

            selected_tab = inquirer.select(
                message="Chọn trang (tab) cần tải:",
                choices=tab_choices,
                default=tabs[0]['index'] if tabs else "back"
            ).execute()

            if selected_tab == "reload":
                continue
            elif selected_tab == "back":
                continue

            # 4. Show resource selection sub-menu
            mode_choices = [
                Choice("all", "1. Tải tất cả các loại"),
                Choice("image", "2. Chỉ tải ảnh"),
                Choice("youtube", "3. Chỉ tải video YouTube"),
                Choice("back", "4. Quay lại")
            ]

            selected_mode = inquirer.select(
                message="Chọn loại tài nguyên muốn tải:",
                choices=mode_choices,
                default="all"
            ).execute()

            if selected_mode == "back":
                continue

            # 5. Open Folder Explorer to override save path in-memory
            print("\n[*] Mở cửa sổ chọn thư mục lưu (Folder Explorer)...")
            save_dir = ask_directory_dialog(AppState.download_dir)
            if not save_dir:
                print(f"{YELLOW}[!] Đã hủy chọn thư mục. Quay lại menu.{RESET}")
                time.sleep(1.5)
                continue

            AppState.download_dir = os.path.abspath(save_dir)
            core.update_download_dir(AppState.download_dir)

            # 6. Ask for number of pages
            pages_input = inquirer.text(
                message="Nhập số lượng trang (page) muốn cào tải (Nhập số nguyên dương, mặc định: 2):",
                default="2"
            ).execute()

            num_pages = 2
            if pages_input.isdigit() and int(pages_input) > 0:
                num_pages = int(pages_input)

            # 7. Start system and run scraper thread
            core.download_mode = selected_mode
            core.quiet_mode = True  # Prevent utils_service.log from printing to stdout, avoiding duplicates
            print(f"\n[*] Đang khởi động hệ thống cào tải với số luồng = {AppState.thread_count}...")
            
            # Reset the state of the selected tab to avoid race conditions/stale status
            if selected_tab in core.tab_states:
                core.tab_states[selected_tab]["status"] = "new"
                core.tab_states[selected_tab]["current_page"] = 1
                core.tab_states[selected_tab]["scraped_count"] = 0
                core.tab_states[selected_tab]["target_pages"] = num_pages

            core.start_system(thread_count=AppState.thread_count)

            scraper_thread = threading.Thread(
                target=core.run_tab_scraper,
                args=(selected_tab, num_pages, AppState.chrome_port),
                daemon=True
            )
            scraper_thread.start()

            # Dashboard loop
            aborted = False
            original_stdout = sys.stdout
            redirector = StdoutRedirector(original_stdout)
            sys.stdout = redirector

            try:
                live_console = Console(file=original_stdout)
                with Live(auto_refresh=False, console=live_console) as live:
                    while True:
                        tab_state = core.tab_states.get(selected_tab, {})
                        tab_status = tab_state.get("status", "unknown")

                        # Drain log queue
                        while not core.log_queue.empty():
                            try:
                                msg = core.log_queue.get_nowait()
                                ts = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))
                                level = msg.get("type", "info").upper()
                                text = msg.get("message", "")
                                global_logs.append(f"{ts} [{level}] {text}")
                                if len(global_logs) > MAX_LOGS:
                                    global_logs.pop(0)
                            except queue.Empty:
                                break

                        # Draw the live dashboard
                        dashboard_renderable = make_dashboard(core, selected_tab)
                        live.update(dashboard_renderable, refresh=True)

                        # Check for keyboard safe cancel (Ctrl + Q)
                        if msvcrt and msvcrt.kbhit():
                            key = msvcrt.getch()
                            # Ctrl+Q has ASCII value 17 (0x11)
                            if key == b'\x11':
                                aborted = True
                                break

                        # Terminate loop when scraper is done and queue is empty
                        core_stats = core.stats
                        pending = core_stats.get("pending", 0)
                        downloading = core_stats.get("downloading", 0)

                        is_scraper_active = tab_status in ("running", "new")
                        if not is_scraper_active and pending == 0 and downloading == 0:
                            break

                        time.sleep(0.5)
            except KeyboardInterrupt:
                aborted = True
            finally:
                sys.stdout = original_stdout

            # Stop & Cleanup
            console.clear()
            tab_state = core.tab_states.get(selected_tab, {})
            tab_status = tab_state.get("status", "unknown")

            if aborted:
                print(f"\n{YELLOW}[*] Đang dừng tiến trình cào tải an toàn và dọn dẹp thư mục tạm...{RESET}")
                core.stop_system()
                clean_temp_dirs(core)
                print(f"{GREEN}[+] Đã dọn dẹp thư mục tạm thành công.{RESET}")
                time.sleep(2)
            elif tab_status in ("closed", "failed", "expired"):
                print(f"\n{RED}[-] Quá trình cào tải thất bại hoặc tab đã bị đóng (Trạng thái: {tab_status})!{RESET}")
                print(f"{YELLOW}[*] Xem lại các log hoạt động cuối cùng của phiên chạy:{RESET}")
                for log_line in global_logs:
                    print(log_line)
                core.stop_system()
                clean_temp_dirs(core)
                input("\nNhấn Enter để quay lại Menu chính...")
            else:
                print(f"\n{GREEN}[+] Đã hoàn thành cào tải và lưu trữ thành công!{RESET}")
                core.stop_system()
                clean_temp_dirs(core)
                input("\nNhấn Enter để quay lại Menu chính...")

        elif sel == "open_dir":
            if not os.path.exists(AppState.download_dir):
                os.makedirs(AppState.download_dir, exist_ok=True)
            print(f"\n[*] Đang mở thư mục tải: {AppState.download_dir} trong Explorer...")
            try:
                os.startfile(AppState.download_dir)
            except Exception as e:
                print(f"{RED}[!] Không thể mở thư mục: {e}{RESET}")
                time.sleep(2)

        elif sel == "settings":
            configure_settings(core)

        elif sel == "exit":
            print(f"\n{GREEN}[+] Cảm ơn bạn đã sử dụng SocialPeta Downloader CLI V2! Tạm biệt.{RESET}\n")
            sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check-deps":
        print(f"FFMPEG_PATH: {settings.FFMPEG_PATH}")
        print(f"FFPROBE_PATH: {settings.FFPROBE_PATH}")
        sys.exit(0)
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{GREEN}[+] Đã đóng chương trình.{RESET}\n")
        sys.exit(0)
