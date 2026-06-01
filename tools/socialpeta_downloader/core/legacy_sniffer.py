# tools/socialpeta_downloader/core/legacy_sniffer.py
"""
Responsibility: Legacy single-tab sniffer worker and pagination loops.
"""

import time
import queue
import threading
from typing import TYPE_CHECKING, Any, Optional

class LegacySnifferMixin:
    last_packet_empty: bool
    ad_id_to_status: dict
    stats_lock: threading.Lock
    stats: dict
    pending_downloads: queue.PriorityQueue
    youtube_extract_queue: queue.Queue
    page_packet_received: threading.Event
    running: bool
    playwright_connected: bool
    active_page: Any
    total_pages: Optional[int]
    pause_event: threading.Event

    if TYPE_CHECKING:
        def _recursive_find_creatives(self, obj: Any) -> list[dict]: ...
        def _parse_creative_item(self, raw_item: dict) -> dict: ...
        def _is_ad_already_downloaded(self, ad_id: str) -> bool: ...
        def _save_item_state(self, item: dict) -> None: ...
        def append_to_csv(self, item: dict) -> None: ...
        def _youtube_extract_worker(self) -> None: ...
        def _click_page_button(self, page: Any, page_num: int) -> bool: ...
        def _jump_to_page(self, page: Any, page_num: int) -> bool: ...

    def _process_api_response(self, data: dict):
        try:
            items = self._recursive_find_creatives(data)
            
            if not items:
                self.last_packet_empty = True
                print("[*] Sniffer: Nhan goi tin nhung danh sach trong.")
            else:
                self.last_packet_empty = False
                
            new_count = 0
            for raw_item in items:
                parsed = self._parse_creative_item(raw_item)
                if not parsed["ad_id"]:
                    continue
                    
                status = self.ad_id_to_status.get(parsed["ad_id"])
                if status and status != "failed":
                    continue
                    
                if self._is_ad_already_downloaded(parsed["ad_id"]):
                    continue

                with self.stats_lock:
                    self.stats["total_sniffed"] += 1
                
                if parsed["media_type"] == "image":
                    self._save_item_state(parsed)
                    self.append_to_csv(parsed)
                    self.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                elif parsed["media_type"] in ("youtube_video", "youtube_thumbnail"):
                    self._save_item_state(parsed)
                    self.append_to_csv(parsed)
                    self.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                elif parsed["media_type"] == "youtube_click_required":
                    print(f"[*] Phat hien quang cao YouTube (ID: {parsed['ad_id']}). Dang sap xep click de lay iframe...")
                    self.youtube_extract_queue.put(parsed)
                else:
                    self._save_item_state(parsed)
                    self.append_to_csv(parsed)
                    self.pending_downloads.put((time.time(), parsed["fpath"]))
                    new_count += 1
                    
            if new_count > 0:
                print(f"[+] Sniffer: Phat hien va xep hang {new_count} media moi.")
                
            self.page_packet_received.set()
        except Exception as e:
            print(f"[-] Sniffer error parsing creative list: {e}")
            self.page_packet_received.set()

    def stream_1_sniffer(self):
        """
        Stream 1 Thread. Handles Chrome CDP connection and Network Sniffing.
        """
        print("[*] Stream 1 (Sniffer) bat dau...")
        
        while self.running:
            try:
                self.playwright_connected = False
                browser = None
                with sync_playwright() as p:
                    print(f"[*] Dang ket noi Chrome qua Debug Port {settings.CHROME_DEBUG_PORT}...")
                    try:
                        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{settings.CHROME_DEBUG_PORT}")
                        context = browser.contexts[0]
                    except Exception as e:
                        print(f"\n[!] CANH BAO: Khong the ket noi Chrome Debug port {settings.CHROME_DEBUG_PORT}! ({e})")
                        print(f"[*] Vui long mo Chrome voi command: chrome.exe --remote-debugging-port={settings.CHROME_DEBUG_PORT}")
                        print("[*] Luong Sniffer se retry sau 5 giay...")
                        time.sleep(5)
                        continue
                        
                    try:
                        print("[+] Ket noi Chrome Debug thanh cong!")
                        self.playwright_connected = True
                        
                        page = None
                        while self.running and not page:
                            pages = context.pages
                            for p_curr in pages:
                                if p_curr.url and is_socialpeta_url(p_curr.url):
                                    page = p_curr
                                    break
                            if not page:
                                print("[*] Chua tim thay tab SocialPeta tren Chrome. Dang cho va retry sau 5 giay...")
                                time.sleep(5)
                                
                        if not self.running or page is None:
                            break
                            
                        print(f"[+] Da nhan dien tab SocialPeta dang hoat dong: {page.url}")
                        self.active_page = page
                        
                        def handle_response(response):
                            url = response.url
                            if response.status in (403, 429, 500):
                                if "/creative/" in url or "/creative-rank/" in url:
                                    print(f"[-] API error returned ({response.status}) on: {url}")
                                return
                                
                            if "/creative/list" in url or "/creative-rank/list" in url:
                                try:
                                    body = response.json()
                                    self._process_api_response(body)
                                except Exception as ex:
                                    print(f"[-] Sniffer error: {ex}")
                                    
                        page.on("response", handle_response)
                        
                        if self.total_pages:
                            try:
                                self.run_pagination_loop(page)
                            except Exception as e:
                                print(f"[-] Loi trong qua trinh dieu huong pagination: {e}")
                            self.total_pages = None
                        
                        while self.running:
                            if page.is_closed():
                                print("\n[-] CANH BAO: Tab SocialPeta da bi dong.")
                                self.active_page = None
                                break
                                
                            self._youtube_extract_worker()
                            
                            url = page.url
                            if "login" in url:
                                print("\n[-] CANH BAO: Trang SocialPeta bi dang xuat / session het han.")
                                self.pause_event.clear()
                                print("[*] Da tam dung luong tai video. Vui long dang nhap lai tren trinh duyet.")
                                
                                while self.running and "login" in page.url:
                                    time.sleep(2)
                                if self.running:
                                    self.pause_event.set()
                                    print("[+] Da phat hien dang nhap lai. Tiep tuc luong tai video.")
                                    
                            time.sleep(0.5)
                    finally:
                        if browser:
                            browser.close()
            except Exception as e:
                print(f"[-] Stream 1 Sniffer crashed: {e}. Dang khoi dong lai sau 5 giay...")
                self.active_page = None
                time.sleep(5)

    def run_pagination_loop(self, page):
        N = self.total_pages
        if not N or N <= 0:
            return
            
        print(f"[*] Bat dau tu dong hoa pagination cho {N} trang...")
        
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        except Exception:
            pass
            
        active_page_num = 1
        try:
            active_item = page.locator("li.ant-pagination-item-active").first
            if active_item.is_visible():
                txt = active_item.text_content().strip()
                if txt.isdigit():
                    active_page_num = int(txt)
        except Exception:
            pass
            
        print(f"[*] Trang hien tai tren browser: {active_page_num}")
        
        if N == 1:
            if active_page_num == 1:
                click_sequence = [2, 1]
            else:
                click_sequence = [1]
        else:
            if active_page_num == 1:
                click_sequence = list(range(2, N + 1)) + [1]
            else:
                click_sequence = list(range(1, N + 1))
        
        for page_num in click_sequence:
            if not self.running:
                break
                
            print(f"[*] Dang chuyen den Trang {page_num}...")
            
            self.page_packet_received.clear()
            self.last_packet_empty = False
            
            success = False
            for retry in range(1, 4):
                if not self.running:
                    break
                    
                nav_ok = False
                if page_num <= 5:
                    nav_ok = self._click_page_button(page, page_num)
                else:
                    nav_ok = self._jump_to_page(page, page_num)
                    
                if not nav_ok:
                    print(f"[-] Retry {retry}/3: Khong tim thay hoac khong the click Trang {page_num}. Dang scroll va thu lai...")
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1.5)
                    except Exception:
                        pass
                    continue
                
                received = self.page_packet_received.wait(timeout=15.0)
                if received:
                    success = True
                    print(f"[+] Da nhan phan hoi API cho Trang {page_num}.")
                    break
                else:
                    print(f"[-] Retry {retry}/3: Timeout cho doi goi tin Trang {page_num}.")
                    
            if not success:
                print(f"[!] CANH BAO: That bai khi chuyen den Trang {page_num} sau 3 lan thu.")
                continue
                
            if self.last_packet_empty:
                print(f"[*] Phanh goi tin Trang {page_num} tra ve danh sach rong. Dung pagination som.")
                break
                
            time.sleep(2)
            
        print("[+] Hoan thanh quynh trinh Pagination Sniffing.")
