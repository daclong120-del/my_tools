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
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.console import Group
from rich.text import Text

# TKinter for folder selection dialog
import tkinter as tk
from tkinter import filedialog

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
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        selected_dir = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Chọn thư mục lưu file tải về"
        )
        root.destroy()
        return selected_dir
    except Exception as e:
        print(f"\n[-] Không thể mở Folder Explorer ({e}).")
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
    tab_state = core.tab_states.get(tab_index, {})
    core_stats = core.stats

    # 1. Info Panel
    info_text = Text()
    info_text.append("Thư mục lưu: ", style="bold white")
    info_text.append(f"{AppState.download_dir}\n", style="cyan")
    info_text.append("Số luồng tải: ", style="bold white")
    info_text.append(f"{AppState.thread_count}  |  ", style="cyan")
    info_text.append("Chrome Debug Port: ", style="bold white")
    info_text.append(f"{AppState.chrome_port}\n", style="cyan")
    info_text.append("Chế độ tải: ", style="bold white")

    mode_map = {
        "all": "Tải tất cả các loại (CDN Video + Youtube Video + Ảnh)",
        "image": "Chỉ tải ảnh",
        "youtube": "Chỉ tải video YouTube"
    }
    mode_text = mode_map.get(core.download_mode, "Tải tất cả")
    info_text.append(f"{mode_text}\n", style="green")
    info_text.append("Phím tắt: ", style="bold white")
    info_text.append("Nhấn ", style="yellow")
    info_text.append("Ctrl + Q", style="bold yellow")
    info_text.append(" để DỪNG AN TOÀN tiến trình cào tải", style="yellow")

    info_panel = Panel(info_text, title="[bold cyan]THÔNG TIN HỆ THỐNG[/]", border_style="cyan")

    # 2. Tab Scraper Panel
    tab_text = Text()
    tab_title = tab_state.get("title", "SocialPeta Page")
    if len(tab_title) > 60:
        tab_title = tab_title[:57] + "..."
    tab_text.append("Đang cào Tab: ", style="bold white")
    tab_text.append(f"#{tab_index} - {tab_title}\n", style="magenta")

    status_raw = tab_state.get("status", "unknown")
    status_style = "green" if status_raw == "running" else "cyan" if status_raw == "done" else "red"
    tab_text.append("Trạng thái cào: ", style="bold white")
    tab_text.append(f"{status_raw.upper()}\n", style=status_style)

    current_page = tab_state.get("current_page", 1)
    target_pages = tab_state.get("target_pages", 0)
    tab_text.append("Tiến trình: ", style="bold white")
    tab_text.append(f"Trang {current_page} / {target_pages}\n", style="yellow")

    scraped_count = tab_state.get("scraped_count", 0)
    tab_text.append("Đã phát hiện từ tab: ", style="bold white")
    tab_text.append(f"{scraped_count} ads\n", style="green")

    tab_panel = Panel(tab_text, title="[bold magenta]TIẾN TRÌNH CÀO (SCRAPER)[/]", border_style="magenta")

    # 3. Stats Table
    table = Table(show_header=True, header_style="bold blue", expand=True)
    table.add_column("Chỉ số", style="bold")
    table.add_column("Số lượng", justify="right")
    table.add_column("Mô tả chi tiết", style="dim")

    table.add_row("Tổng số ad sniffed", f"[bold cyan]{core_stats.get('total_sniffed', 0)}[/]", "Tổng quảng cáo phát hiện từ API")
    table.add_row("Đang chờ tải (Pending)", f"[bold yellow]{core_stats.get('pending', 0)}[/]", "Hàng đợi đang chờ tải xuống")
    table.add_row("Đang tải (Downloading)", f"[bold magenta]{core_stats.get('downloading', 0)}[/]", "Đang tải đồng thời thực tế")
    table.add_row("Thành công (Done)", f"[bold green]{core_stats.get('done', 0)}[/]", "Đã tải và lưu thành công")
    table.add_row("Lỗi tải (Failed)", f"[bold red]{core_stats.get('failed', 0)}[/]", "Lỗi kết nối CDN/Youtube")
    table.add_row("Link CDN hết hạn", f"[bold yellow]{core_stats.get('expired', 0)}[/]", "Link CDN bị quá hạn 403")
    table.add_row("Lọc trùng (Duplicate)", f"[bold magenta]{core_stats.get('duplicate', 0)}[/]", "Phát hiện trùng lặp vân tay video")

    stats_panel = Panel(table, title="[bold blue]THỐNG KÊ TIẾN TRÌNH TẢI[/]", border_style="blue")

    return Group(
        info_panel,
        tab_panel,
        stats_panel
    )


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
                core.update_download_dir(AppState.download_dir)
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
            print(f"\n[*] Đang khởi động hệ thống cào tải với số luồng = {AppState.thread_count}...")
            core.start_system(thread_count=AppState.thread_count)

            scraper_thread = threading.Thread(
                target=core.run_tab_scraper,
                args=(selected_tab, num_pages, AppState.chrome_port),
                daemon=True
            )
            scraper_thread.start()

            # Dashboard loop
            aborted = False
            try:
                with Live(auto_refresh=False, console=console) as live:
                    while True:
                        tab_state = core.tab_states.get(selected_tab, {})
                        tab_status = tab_state.get("status", "unknown")

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

            # Stop & Cleanup
            console.clear()
            if aborted:
                print(f"\n{YELLOW}[*] Đang dừng tiến trình cào tải an toàn và dọn dẹp thư mục tạm...{RESET}")
                core.stop_system()
                clean_temp_dirs(core)
                print(f"{GREEN}[+] Đã dọn dẹp thư mục tạm thành công.{RESET}")
                time.sleep(2)
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
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{GREEN}[+] Đã đóng chương trình.{RESET}\n")
        sys.exit(0)
